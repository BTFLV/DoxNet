"""Conservative, source-aware Verilog/SystemVerilog interface extraction.

This is a lexical/header parser, NOT a complete IEEE 1800 frontend. In
particular it does not preprocess macros or elaborate generate statements.
It deliberately avoids guessing when it cannot recognize a declaration.
"""
from dataclasses import dataclass
import logging
import re
from pathlib import Path

from .model import DesignUnit, Diagnostic, Parameter, Port

logger = logging.getLogger("doxnet")
_UNIT_END = {"module": "endmodule", "macromodule": "endmodule", "interface": "endinterface", "package": "endpackage"}
_IDENT = re.compile(r"[A-Za-z_$][\w$]*|\\\S+")
_QUALIFIERS = {"automatic", "static"}
_DIRECTIONS = {"input", "output", "inout", "ref"}


@dataclass
class Token:
    value: str
    start: int
    end: int
    line: int
    kind: str = "token"


@dataclass
class DocBlock:
    start: int
    end: int
    text: str
    line: int
    style: str


def lex(source):
    """Tokenize HDL while ignoring comments, strings and preprocessor directives.

    Returns (tokens, docblocks). Token offsets refer to the original source.
    """
    tokens, docs = [], []
    i, line, n = 0, 1, len(source)
    while i < n:
        c = source[i]
        if c.isspace():
            if c == "\n":
                line += 1
            i += 1
            continue
        if source.startswith("//", i):
            end = source.find("\n", i)
            if end == -1:
                end = n
            comment = source[i:end]
            if comment.startswith("///") or comment.startswith("//!"):
                if docs and docs[-1].style == "line" and not source[docs[-1].end:i].strip():
                    docs[-1].text += "\n" + comment
                    docs[-1].end = end
                else:
                    docs.append(DocBlock(i, end, comment, line, "line"))
            i = end
            continue
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            end = n if end < 0 else end + 2
            comment = source[i:end]
            if comment.startswith("/**") or comment.startswith("/*!"):
                docs.append(DocBlock(i, end, comment, line, "block"))
            line += comment.count("\n")
            i = end
            continue
        if c == '"':
            start, start_line = i, line
            i += 1
            while i < n:
                if source[i] == "\\":
                    i += 2
                elif source[i] == '"':
                    i += 1
                    break
                else:
                    if source[i] == "\n":
                        line += 1
                    i += 1
            tokens.append(Token("<string>", start, min(i, n), start_line, "string"))
            continue
        if c == "`":
            m = re.match(r"`([A-Za-z_][\w]*)", source[i:])
            if m and m.group(1) in {
                "define", "include", "timescale", "ifdef", "ifndef", "else", "elsif",
                "endif", "undef", "line", "default_nettype", "resetall", "celldefine", "endcelldefine",
            }:
                # `define macros can continue across lines with a trailing backslash.
                end = source.find("\n", i)
                if end == -1:
                    end = n
                while end < n and source[i:end].rstrip().endswith("\\"):
                    next_end = source.find("\n", end + 1)
                    end = n if next_end == -1 else next_end
                line += source[i:end].count("\n")
                i = end  # directive payload must not create fake design units
                continue
        m = _IDENT.match(source, i)
        if m:
            tokens.append(Token(m.group(), i, m.end(), line, "identifier"))
            i = m.end()
        else:
            tokens.append(Token(c, i, i + 1, line))
            i += 1
    return tokens, docs


def parse_doxygen_comment(comment_lines):
    """Parse legacy Doxygen-like tags without interpreting HDL syntax."""
    info = dict(brief="", inputs=[], outputs=[], inouts=[], ports=[], description="",
                parameters=[], localparams=[])
    descriptions = []
    for raw in comment_lines:
        line = raw.strip()
        if line.startswith(("/**", "/*!", "///", "//!")):
            line = line[3:]
        elif line.startswith("*/"):
            line = line[2:]
        elif line.startswith("*"):
            line = line[1:]
        line = re.sub(r"\s*\*/\s*$", "", line).strip()
        if not line:
            continue
        match = re.match(r"^@(brief|input|output|inout|port|parameter|localparam)\b\s*(.*)", line)
        if match:
            tag, value = match.groups()
            if tag == "brief":
                info["brief"] = value
            else:
                plural = {"input": "inputs", "output": "outputs", "inout": "inouts",
                          "port": "ports", "parameter": "parameters", "localparam": "localparams"}[tag]
                info[plural].append(value)
        else:
            descriptions.append(line)
    info["description"] = "\n".join(descriptions)
    return info


def _matching(tokens, start, opening="(", closing=")"):
    if start >= len(tokens) or tokens[start].value != opening:
        return None
    depth = 0
    for i in range(start, len(tokens)):
        if tokens[i].value == opening:
            depth += 1
        elif tokens[i].value == closing:
            depth -= 1
            if depth == 0:
                return i
    return None


def _split_commas(tokens):
    result, begin, depth = [], 0, [0, 0, 0]
    pairs = {"(": (0, 1), ")": (0, -1), "[": (1, 1), "]": (1, -1),
             "{": (2, 1), "}": (2, -1)}
    for i, token in enumerate(tokens):
        if token.value == "," and not any(depth):
            if tokens[begin:i]:
                result.append(tokens[begin:i])
            begin = i + 1
        elif token.value in pairs:
            index, change = pairs[token.value]
            depth[index] += change
    if tokens[begin:]:
        result.append(tokens[begin:])
    return result


def _slice(source, tokens):
    return source[tokens[0].start:tokens[-1].end].strip() if tokens else ""


def _declaration_name(tokens):
    """Locate the declared name before defaults and optional unpacked dimensions."""
    if not tokens:
        return None
    limit = next((i for i, t in enumerate(tokens) if t.value == "="), len(tokens))
    k = limit - 1
    while k >= 0:
        if tokens[k].value == "]":
            depth = 1
            k -= 1
            while k >= 0 and depth:
                if tokens[k].value == "]":
                    depth += 1
                elif tokens[k].value == "[":
                    depth -= 1
                k -= 1
            continue
        if tokens[k].kind == "identifier":
            return k
        k -= 1
    return None


def _parse_parameters(source, tokens, local=False):
    result, inherited_type = [], ""
    for part in _split_commas(tokens):
        part = [t for t in part if t.value not in ("parameter", "localparam")]
        if not part:
            continue
        index = _declaration_name(part)
        if index is None:
            continue
        name = part[index].value
        if name == "type" or name.startswith("$"):
            continue
        prefix = _slice(source, part[:index])
        if prefix:
            inherited_type = prefix
        eq = next((i for i, t in enumerate(part) if t.value == "="), None)
        default = _slice(source, part[eq + 1:]) if eq is not None else ""
        result.append(Parameter(name=name, type=prefix or inherited_type, default=default,
                                line=part[index].line, local=local))
    return result


def _parse_ports(source, tokens):
    result, inherited_direction, inherited_type = [], "", ""
    for part in _split_commas(tokens):
        if not part:
            continue
        # ANSI-style ports inherit their type and direction across commas.
        direction = part[0].value if part[0].value in _DIRECTIONS else ""
        content = part[1:] if direction else part
        index = _declaration_name(content)
        if index is None:
            continue
        name = content[index].value
        if name.startswith("$"):
            continue
        prefix = _slice(source, content[:index])
        if direction:
            inherited_direction = direction
            # `output ready` has no explicit type, unlike `output logic ready`.
            inherited_type = prefix
        elif prefix:
            inherited_type = prefix
        # An ANSI header is explicit only when direction has appeared.
        result.append(Port(name=name, direction=direction or inherited_direction,
                           type=prefix or inherited_type, line=content[index].line))
    return result


def _body_declarations(source, tokens, ports):
    """Resolve old-style port declarations and simple body localparams."""
    by_name = {p.name: p for p in ports}
    localparams = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.value not in _DIRECTIONS | {"localparam"}:
            i += 1
            continue
        j = i + 1
        while j < len(tokens) and tokens[j].value != ";":
            j += 1
        if j >= len(tokens):
            break
        statement = tokens[i:j]
        if token.value == "localparam":
            localparams.extend(_parse_parameters(source, statement, local=True))
        else:
            for parsed in _parse_ports(source, statement):
                # Do not add function arguments or unrelated names as module ports.
                if parsed.name in by_name:
                    old = by_name[parsed.name]
                    old.direction, old.type = parsed.direction, parsed.type
        i = j + 1
    return localparams


def _comment_for_unit(source, docs, token):
    previous = [d for d in docs if d.end <= token.start]
    if not previous:
        return None
    comment = previous[-1]
    # No code may intervene; a distant comment must not document another unit.
    between = source[comment.end:token.start]
    if between.strip():
        return None
    return comment


def _skip_package_imports(tokens, start):
    """Skip import declarations allowed before module parameter/port lists.

    Examples: `module m import pkg::*; #(parameter int W=8)(...);`.
    Package members are not resolved: this only finds the correct header.
    """
    i = start
    while i < len(tokens) and tokens[i].value == "import":
        i += 1
        while i < len(tokens) and tokens[i].value != ";":
            if tokens[i].value in _UNIT_END:
                return i
            i += 1
        if i < len(tokens):
            i += 1
    return i


def _annotations(info, unit, diagnostics):
    """Merge semantic documentation with parsed declarations and flag stale tags."""
    ports = {p.name: p for p in unit.ports}
    params = {p.name: p for p in unit.parameters}
    locals_ = {p.name: p for p in unit.localparams}
    seen = set()
    aliases = [("inputs", "input"), ("outputs", "output"), ("inouts", "inout"), ("ports", "port"),
               ("parameters", "parameter"), ("localparams", "localparam")]
    for plural, tag in aliases:
        for raw in info[plural]:
            name, _, description = raw.partition(" ")
            key = ("port" if tag in _DIRECTIONS | {"port"} else tag, name)
            if key in seen:
                diagnostics.append(Diagnostic("DOC003", f"Duplicate documentation for {name}",
                                              unit.file, unit.line))
                continue
            seen.add(key)
            target_map = ports if tag in _DIRECTIONS | {"port"} else (locals_ if tag == "localparam" else params)
            if name not in target_map:
                diagnostics.append(Diagnostic("DOC001", f"@{tag} refers to unknown {name}",
                                              unit.file, unit.line))
                continue
            target = target_map[name]
            target.description = description.strip()
            if tag in _DIRECTIONS and target.direction and target.direction != tag:
                diagnostics.append(Diagnostic("DOC002", f"@{tag} {name} is declared {target.direction}",
                                              unit.file, unit.line))


def parse_source(source, filename="<memory>"):
    """Return design units and validation diagnostics for one source string."""
    tokens, docs = lex(source)
    units, diagnostics = [], []
    associated_docs = set()
    i = 0
    while i < len(tokens):
        keyword = tokens[i]
        if keyword.value not in _UNIT_END:
            i += 1
            continue
        kind = "module" if keyword.value == "macromodule" else keyword.value
        i += 1
        if i < len(tokens) and tokens[i].value in _QUALIFIERS:
            i += 1
        if i >= len(tokens) or tokens[i].kind != "identifier" or tokens[i].value == "class":
            continue
        name = tokens[i].value
        i += 1
        i = _skip_package_imports(tokens, i)
        parameters, ports = [], []
        if i + 1 < len(tokens) and tokens[i].value == "#" and tokens[i + 1].value == "(":
            end = _matching(tokens, i + 1)
            if end is None:
                diagnostics.append(Diagnostic("HDL001", f"Unclosed parameter list for {name}",
                                              filename, keyword.line, "error"))
                break
            parameters = _parse_parameters(source, tokens[i + 2:end])
            i = end + 1
        if i < len(tokens) and tokens[i].value == "(":
            end = _matching(tokens, i)
            if end is None:
                diagnostics.append(Diagnostic("HDL001", f"Unclosed port list for {name}",
                                              filename, keyword.line, "error"))
                break
            ports = _parse_ports(source, tokens[i + 1:end])
            i = end + 1
        # Move to the header's semicolon, without mistaking tokens inside strings for declarations.
        if i >= len(tokens) or tokens[i].value != ";":
            diagnostics.append(Diagnostic("HDL001", f"Expected ';' after header of {name}",
                                          filename, keyword.line, "error"))
            break
        body_start = min(i + 1, len(tokens))
        j = body_start
        while j < len(tokens) and tokens[j].value != _UNIT_END[keyword.value]:
            j += 1
        if j == len(tokens):
            diagnostics.append(Diagnostic("HDL001", f"Missing {_UNIT_END[keyword.value]} for {name}",
                                          filename, keyword.line, "error"))
            break
        end_line = tokens[j].line if j < len(tokens) else keyword.line
        unit = DesignUnit(kind=kind, name=name, file=filename, line=keyword.line,
                          end_line=end_line, parameters=parameters, ports=ports)
        unit.localparams = _body_declarations(source, tokens[body_start:j], ports)
        comment = _comment_for_unit(source, docs, keyword)
        if comment:
            associated_docs.add(comment.start)
            info = parse_doxygen_comment(comment.text.splitlines())
            unit.brief, unit.description = info["brief"], info["description"]
            unit.documented = bool(unit.brief or unit.description or any(info[tag] for tag in (
                "inputs", "outputs", "inouts", "ports", "parameters", "localparams")))
            _annotations(info, unit, diagnostics)
        units.append(unit)
        i = j + 1 if j < len(tokens) else len(tokens)
    for block in docs:
        if block.start in associated_docs:
            continue
        info = parse_doxygen_comment(block.text.splitlines())
        if info["brief"] or any(info[tag] for tag in (
            "inputs", "outputs", "inouts", "ports", "parameters", "localparams"
        )):
            diagnostics.append(Diagnostic("DOC004", "Documentation comment is not attached to a design unit",
                                          filename, block.line))
    return units, diagnostics


def parse_file(file_path, display_name=None):
    path = Path(file_path)
    source = path.read_text(encoding="utf-8")
    return parse_source(source, display_name or path.as_posix())


def parse_verilog_file(file_path):
    """Legacy API (documented dicts, (documented, total, missing))."""
    units, _ = parse_file(file_path)
    documented = [u for u in units if u.documented]
    docs = []
    for u in documented:
        docs.append({"module": u.name, "unit_kind": u.kind, "brief": u.brief,
                     "description": u.description,
                     "inputs": [p.name + " " + p.description for p in u.ports if p.direction == "input" and p.description],
                     "outputs": [p.name + " " + p.description for p in u.ports if p.direction == "output" and p.description],
                     "inouts": [p.name + " " + p.description for p in u.ports if p.direction == "inout" and p.description],
                     "parameters": [p.name + " " + p.description for p in u.parameters if p.description],
                     "localparams": [p.name + " " + p.description for p in u.localparams if p.description]})
    return docs, (len(documented), len(units), [u.name for u in units if not u.documented])


def find_all_units(lines):
    units, _ = parse_source("".join(lines))
    return [(u.kind, u.name, u.line - 1) for u in units]


def remove_doxnet_comments(code):
    _, docs = lex(code)
    parts, last = [], 0
    for doc in docs:
        parts.extend((code[last:doc.start], "\n" * code[doc.start:doc.end].count("\n")))
        last = doc.end
    parts.append(code[last:])
    return "".join(parts)


def format_port_line(line):
    name, _, description = line.strip().partition(" ")
    return f"- `{name}` {description}\n" if description else f"- `{name}`\n"
