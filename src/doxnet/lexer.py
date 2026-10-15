"""Tokenizer for Verilog/SystemVerilog source text.

The lexer only knows enough about the language to keep comments, strings,
attributes and compiler directives from being mistaken for declarations.
Every token keeps its character offsets so later stages can slice the
original text back out.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Tuple

IDENT = re.compile(r"[A-Za-z_][\w$]*|\\\S+")
_NUMBER = re.compile(
    r"(?:\d[\d_]*\s*)?'[sS]?[bBoOdDhH]\s*[0-9a-fA-FxXzZ?_]+"  # sized / based literal
    r"|\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?(?:fs|ps|ns|us|ms|s)?"  # decimal, real, time
    r"|'[01xXzZ](?![\w'])"  # unbased unsized literal
)
_SYSTEM_NAME = re.compile(r"\$[A-Za-z_][\w$]*")
_DIRECTIVE = re.compile(r"`([A-Za-z_]\w*)")
_LINE_DIRECTIVES = {
    "define", "timescale", "default_nettype", "line", "pragma", "begin_keywords",
    "unconnected_drive", "default_decay_time", "default_trireg_strength", "delay_mode_distributed",
    "delay_mode_path", "delay_mode_unit", "delay_mode_zero",
}
_BARE_DIRECTIVES = {
    "else", "endif", "resetall", "celldefine", "endcelldefine", "undefineall",
    "nounconnected_drive", "end_keywords", "__FILE__", "__LINE__",
}
_NAME_DIRECTIVES = {"ifdef", "ifndef", "elsif", "undef"}
DIRECTIVES = _LINE_DIRECTIVES | _BARE_DIRECTIVES | _NAME_DIRECTIVES | {"include"}


@dataclass
class Token:
    value: str
    start: int
    end: int
    line: int
    kind: str = "token"


@dataclass
class DocBlock:
    """A documentation comment.

    ``style`` is ``block`` for ``/** */`` and ``/*! */``, ``line`` for runs of
    ``///`` or ``//!`` lines, and ``plain`` for an ordinary ``//`` comment
    (only kept so that trailing plain comments can document members when the
    user asks for it). ``trailing`` marks the Doxygen ``<`` form that
    documents the preceding declaration.
    """

    start: int
    end: int
    text: str
    line: int
    style: str
    trailing: bool = False


def _line_comment(source: str, i: int, line: int, docs: List[DocBlock]) -> int:
    end = source.find("\n", i)
    if end == -1:
        end = len(source)
    comment = source[i:end]
    if comment.startswith(("///", "//!")) and not comment.startswith("////"):
        trailing = comment[3:4] == "<"
        previous = docs[-1] if docs else None
        if (previous is not None and previous.style == "line" and previous.trailing == trailing
                and not source[previous.end:i].strip() and source[previous.end:i].count("\n") == 1):
            previous.text += "\n" + comment
            previous.end = end
        else:
            docs.append(DocBlock(i, end, comment, line, "line", trailing))
    else:
        docs.append(DocBlock(i, end, comment, line, "plain"))
    return end


def _skip_directive(source: str, i: int, name: str) -> int:
    """Return the offset just past a compiler directive and its arguments."""
    n = len(source)
    end = i + 1 + len(name)
    if name in _LINE_DIRECTIVES:
        stop = source.find("\n", end)
        stop = n if stop == -1 else stop
        while name == "define" and stop < n and source[end:stop].rstrip().endswith("\\"):
            nxt = source.find("\n", stop + 1)
            stop = n if nxt == -1 else nxt
        return stop
    if name in _BARE_DIRECTIVES:
        return end
    k = end
    while k < n and source[k] in " \t":
        k += 1
    if name == "include":
        closing = {'"': '"', "<": ">"}.get(source[k:k + 1])
        if closing:
            stop = source.find(closing, k + 1)
            return n if stop == -1 else stop + 1
        return k
    if source[k:k + 1] == "(":
        depth = 0
        while k < n:
            if source[k] == "(":
                depth += 1
            elif source[k] == ")":
                depth -= 1
                if depth == 0:
                    return k + 1
            elif source[k] == "\n":
                return k
            k += 1
        return k
    m = IDENT.match(source, k)
    return m.end() if m else k


def lex(source: str) -> Tuple[List[Token], List[DocBlock]]:
    """Tokenize HDL text.

    Returns ``(tokens, comments)``. Comments, strings, attributes and compiler
    directives never produce identifier tokens. String literals become a single
    token of kind ``string``; macro usages become a single ``macro`` token.
    """
    tokens: List[Token] = []
    docs: List[DocBlock] = []
    i, line, n = 0, 1, len(source)
    while i < n:
        c = source[i]
        if c.isspace():
            if c == "\n":
                line += 1
            i += 1
            continue
        if source.startswith("//", i):
            i = _line_comment(source, i, line, docs)
            continue
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            end = n if end < 0 else end + 2
            comment = source[i:end]
            if comment.startswith(("/**", "/*!")) and comment not in ("/**/", "/*!*/"):
                docs.append(DocBlock(i, end, comment, line, "block", comment[3:4] == "<"))
            line += comment.count("\n")
            i = end
            continue
        if source.startswith("(*", i) and not source.startswith("(*)", i):
            end = source.find("*)", i + 2)
            end = n if end < 0 else end + 2
            line += source.count("\n", i, end)
            i = end
            continue
        if c == '"':
            start, start_line = i, line
            triple = source.startswith('"""', i)
            i += 3 if triple else 1
            while i < n:
                if source[i] == "\\":
                    i += 2
                elif triple and source.startswith('"""', i):
                    i += 3
                    break
                elif not triple and source[i] == '"':
                    i += 1
                    break
                elif not triple and source[i] == "\n":
                    break  # unterminated literal; resume on the next line
                else:
                    i += 1
            i = min(i, n)
            line += source.count("\n", start, i)
            tokens.append(Token(source[start:i], start, i, start_line, "string"))
            continue
        if c == "`":
            m = _DIRECTIVE.match(source, i)
            if m and m.group(1) in DIRECTIVES:
                end = _skip_directive(source, i, m.group(1))
                line += source.count("\n", i, end)
                i = end
                continue
            if m:
                tokens.append(Token(m.group(), i, m.end(), line, "macro"))
                i = m.end()
                continue
        if c.isdigit() or c == "'":
            m = _NUMBER.match(source, i)
            if m and m.end() > i:
                tokens.append(Token(m.group(), i, m.end(), line, "number"))
                line += m.group().count("\n")
                i = m.end()
                continue
        if c == "$":
            m = _SYSTEM_NAME.match(source, i)
            if m:
                tokens.append(Token(m.group(), i, m.end(), line, "system"))
                i = m.end()
                continue
        m = IDENT.match(source, i)
        if m:
            tokens.append(Token(m.group(), i, m.end(), line, "identifier"))
            i = m.end()
            continue
        if source.startswith("::", i):
            tokens.append(Token("::", i, i + 2, line))
            i += 2
            continue
        tokens.append(Token(c, i, i + 1, line))
        i += 1
    return tokens, docs


def token_text(source: str, tokens: List[Token]) -> str:
    """Rebuild the text spanned by ``tokens`` with normalized whitespace.

    Comments and line breaks between tokens collapse into a single space, so
    multi-line declarations render on one line.
    """
    if not tokens:
        return ""
    parts = [source[tokens[0].start:tokens[0].end]]
    for prev, tok in zip(tokens, tokens[1:]):
        if tok.start > prev.end:
            parts.append(" ")
        parts.append(source[tok.start:tok.end])
    return "".join(parts)
