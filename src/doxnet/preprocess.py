"""Conditional compilation for documentation extraction.

DoxNet does not expand macros. It does evaluate ``ifdef``/``ifndef``/
``elsif``/``else``/``endif`` against the macros known at that point, so that
disabled code neither shows up as design units nor counts towards coverage.

Inactive text is replaced by spaces while line breaks are kept. Offsets and
line numbers in the result therefore still match the original file, which is
what the parser and the source links rely on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .lexer import IDENT
from .model import Diagnostic

_DIRECTIVE = re.compile(r"`([A-Za-z_]\w*)")
_MAX_INCLUDE_DEPTH = 32
# Predefined by the standard and by every simulator we care about.
_BUILTIN = {"SYSTEMVERILOG": ""}


@dataclass
class _Branch:
    parent_active: bool
    taken: bool
    active: bool
    line: int
    seen_else: bool = False


@dataclass
class Preprocessor:
    """Tracks macro definitions across the files of one compilation unit.

    Like most tools, DoxNet treats all inputs as a single compilation unit:
    a ``define`` in one file is visible in the files that follow it.
    """

    defines: Dict[str, str] = field(default_factory=dict)
    include_dirs: Sequence[Path] = ()
    encoding: str = "utf-8"

    def __post_init__(self):
        merged = dict(_BUILTIN)
        merged.update(self.defines)
        self.defines = merged
        self.include_dirs = [Path(p) for p in self.include_dirs]

    def process(self, source: str, filename: str, path: Optional[Path] = None) -> Tuple[str, List[Diagnostic]]:
        diagnostics: List[Diagnostic] = []
        inactive = self._scan(source, filename, path, diagnostics, depth=0, stack=[])
        return _blank(source, inactive), diagnostics

    # The scanner is shared by top-level files and by included headers. For
    # headers only the macro side effects matter; their text is discarded.
    def _scan(self, source, filename, path, diagnostics, depth, stack) -> List[Tuple[int, int]]:
        branches: List[_Branch] = []
        ranges: List[Tuple[int, int]] = []
        inactive_from: Optional[int] = None
        i, n, line = 0, len(source), 1

        def active():
            return not branches or branches[-1].active

        while i < n:
            c = source[i]
            if c == "\n":
                line += 1
                i += 1
            elif source.startswith("//", i):
                end = source.find("\n", i)
                i = n if end == -1 else end
            elif source.startswith("/*", i):
                end = source.find("*/", i + 2)
                end = n if end == -1 else end + 2
                line += source.count("\n", i, end)
                i = end
            elif c == '"':
                j = i + 1
                while j < n and source[j] not in '"\n':
                    j += 2 if source[j] == "\\" else 1
                j = min(j + 1, n) if j < n and source[j] == '"' else j
                line += source.count("\n", i, j)
                i = j
            elif c == "`" and _DIRECTIVE.match(source, i):
                name = _DIRECTIVE.match(source, i).group(1)
                was_active = active()
                start = i
                i = self._directive(name, source, i, line, filename, path, branches, diagnostics,
                                    depth, stack, was_active)
                line += source.count("\n", start, i)
                now_active = active()
                if was_active and not now_active:
                    inactive_from = i
                elif not was_active and now_active:
                    ranges.append((inactive_from, start))
                    inactive_from = None
            else:
                i += 1
        for branch in branches:
            diagnostics.append(Diagnostic("PP001", "`ifdef/`ifndef without matching `endif",
                                          filename, branch.line, "error"))
        if inactive_from is not None:
            ranges.append((inactive_from, n))
        return ranges

    def _directive(self, name, source, i, line, filename, path, branches, diagnostics, depth, stack,
                   active) -> int:
        end = i + 1 + len(name)
        if name in ("ifdef", "ifndef", "elsif"):
            arg_end, defined = self._condition(source, end)
            if defined is None:
                diagnostics.append(Diagnostic("PP003", f"`{name} without a macro name", filename, line, "error"))
                return arg_end
            if name == "ifndef":
                defined = not defined
            if name == "elsif":
                if not branches or branches[-1].seen_else:
                    diagnostics.append(Diagnostic("PP001", "`elsif without matching `ifdef", filename, line, "error"))
                    return arg_end
                branch = branches[-1]
                branch.active = branch.parent_active and not branch.taken and defined
                branch.taken = branch.taken or branch.active
            else:
                branches.append(_Branch(active, active and defined, active and defined, line))
            return arg_end
        if name == "else":
            if not branches or branches[-1].seen_else:
                diagnostics.append(Diagnostic("PP001", "`else without matching `ifdef", filename, line, "error"))
                return end
            branch = branches[-1]
            branch.active = branch.parent_active and not branch.taken
            branch.taken = True
            branch.seen_else = True
            return end
        if name == "endif":
            if not branches:
                diagnostics.append(Diagnostic("PP001", "`endif without matching `ifdef", filename, line, "error"))
            else:
                branches.pop()
            return end
        if not active:
            return end
        if name == "define":
            stop = _line_end(source, end, continuation=True)
            m = IDENT.match(source, _skip_blanks(source, end))
            if m:
                body = source[m.end():stop]
                self.defines[m.group()] = re.sub(r"\\\n", " ", body).strip()
            return stop
        if name == "undef":
            k = _skip_blanks(source, end)
            m = IDENT.match(source, k)
            if m:
                self.defines.pop(m.group(), None)
                return m.end()
            return k
        if name == "undefineall":
            self.defines = dict(_BUILTIN)
            return end
        if name == "include":
            return self._include(source, end, line, filename, path, diagnostics, depth, stack)
        return end

    def _condition(self, source, k) -> Tuple[int, Optional[bool]]:
        k = _skip_blanks(source, k)
        if source[k:k + 1] == "(":
            depth, j = 0, k
            while j < len(source) and source[j] != "\n":
                depth += {"(": 1, ")": -1}.get(source[j], 0)
                j += 1
                if depth == 0:
                    break
            return j, _evaluate(source[k:j], self.defines)
        m = IDENT.match(source, k)
        if not m:
            return k, None
        return m.end(), m.group() in self.defines

    def _include(self, source, k, line, filename, path, diagnostics, depth, stack) -> int:
        k = _skip_blanks(source, k)
        closing = {'"': '"', "<": ">"}.get(source[k:k + 1])
        if not closing:
            return k  # `include `MACRO is not resolved
        stop = source.find(closing, k + 1)
        if stop == -1:
            return k
        target = source[k + 1:stop]
        found = self._resolve(target, path)
        if found is None:
            diagnostics.append(Diagnostic("PP002", f"Include file not found: {target}", filename, line))
        elif found in stack or depth >= _MAX_INCLUDE_DEPTH:
            diagnostics.append(Diagnostic("PP002", f"Include nesting too deep or recursive: {target}",
                                          filename, line))
        else:
            try:
                text = found.read_text(encoding=self.encoding)
            except (OSError, UnicodeError) as exc:
                diagnostics.append(Diagnostic("PP002", f"Cannot read include file {target}: {exc}", filename, line))
            else:
                header_diags: List[Diagnostic] = []
                self._scan(text, target, found, header_diags, depth + 1, stack + [found])
                diagnostics.extend(d for d in header_diags if d.severity == "error")
        return stop + 1

    def _resolve(self, target: str, path: Optional[Path]) -> Optional[Path]:
        candidates: Iterable[Path] = ([path.parent] if path else []) + list(self.include_dirs)
        for directory in candidates:
            candidate = (directory / target).resolve()
            if candidate.is_file():
                return candidate
        return None


def _skip_blanks(source: str, k: int) -> int:
    while k < len(source) and source[k] in " \t":
        k += 1
    return k


def _line_end(source: str, k: int, continuation: bool = False) -> int:
    n = len(source)
    stop = source.find("\n", k)
    stop = n if stop == -1 else stop
    while continuation and stop < n and source[k:stop].rstrip().endswith("\\"):
        nxt = source.find("\n", stop + 1)
        stop = n if nxt == -1 else nxt
    return stop


def _evaluate(expression: str, defines: Dict[str, str]) -> Optional[bool]:
    """Evaluate an IEEE 1800-2023 ``ifdef`` expression such as ``(A && !B)``."""
    tokens = re.findall(r"[A-Za-z_]\w*|&&|\|\||->|<->|[()!]", expression)
    pos = 0

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def take():
        nonlocal pos
        pos += 1
        return tokens[pos - 1]

    def primary():
        tok = take() if peek() else None
        if tok == "!":
            return not primary()
        if tok == "(":
            value = implication()
            if take() != ")":
                raise ValueError
            return value
        if tok and IDENT.fullmatch(tok):
            return tok in defines
        raise ValueError

    def conjunction():
        value = primary()
        while peek() == "&&":
            take()
            value = primary() and value
        return value

    def disjunction():
        value = conjunction()
        while peek() == "||":
            take()
            value = conjunction() or value
        return value

    def implication():
        value = disjunction()
        while peek() in ("->", "<->"):
            op = take()
            rhs = disjunction()
            value = (not value or rhs) if op == "->" else (value == rhs)
        return value

    try:
        result = implication()
    except (ValueError, IndexError):
        return None
    return result if pos == len(tokens) else None


def _blank(source: str, ranges: List[Tuple[int, int]]) -> str:
    if not ranges:
        return source
    parts, last = [], 0
    for start, end in ranges:
        parts.append(source[last:start])
        parts.append(re.sub(r"[^\n]", " ", source[start:end]))
        last = end
    parts.append(source[last:])
    return "".join(parts)


def parse_define(text: str) -> Tuple[str, str]:
    """Split ``NAME`` or ``NAME=VALUE`` as given on the command line."""
    name, _, value = text.partition("=")
    name = name.strip()
    if not IDENT.fullmatch(name) or name.startswith("\\"):
        raise ValueError(f"Invalid macro name in define: {text!r}")
    return name, value.strip()
