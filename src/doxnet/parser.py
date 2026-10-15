"""Extraction of design units and their interfaces from Verilog/SystemVerilog.

This is a declaration-level parser, not an IEEE 1800 frontend. It reads unit
headers, body declarations (parameters, non-ANSI ports, typedefs, functions,
tasks, modports) and instantiations. It does not evaluate expressions or
elaborate generate constructs, and it prefers to report an error over guessing
when a header cannot be read.
"""
from __future__ import annotations

import bisect
from pathlib import Path
from typing import List, Optional, Tuple

from .comments import DocComment, parse_comment, parse_doxygen_comment
from .keywords import KEYWORDS
from .lexer import DocBlock, Token, lex, token_text
from .model import Connection, DesignUnit, Diagnostic, FileDoc, Instance, Member, Modport, Parameter, Port

__all__ = [
    "ParseResult", "parse_source", "parse_file", "parse_verilog_file", "parse_doxygen_comment",
    "find_all_units", "remove_doxnet_comments", "lex",
]


UNIT_END = {
    "module": "endmodule", "macromodule": "endmodule", "interface": "endinterface",
    "package": "endpackage", "program": "endprogram", "primitive": "endprimitive",
}
DIRECTIONS = {"input", "output", "inout", "ref"}
_LIFETIME = {"automatic", "static"}
# Body constructs that are skipped as a whole. Their contents are not
# interface declarations of the enclosing unit.
_SKIP_BLOCKS = {
    "class": "endclass", "covergroup": "endgroup", "property": "endproperty",
    "sequence": "endsequence", "clocking": "endclocking", "specify": "endspecify",
    "table": "endtable", "checker": "endchecker", "config": "endconfig",
}
_STATEMENT_END = {
    ";", "begin", "end", "generate", "endgenerate", "else", ")", "endfunction", "endtask",
    "endclass", "endgroup", "endproperty", "endsequence", "endclocking", "endchecker",
}


class ParseResult(tuple):
    """``(units, diagnostics)`` with the file-level comment as an attribute.

    It unpacks like the tuple returned by DoxNet 2.x.
    """

    file_doc: Optional[FileDoc]

    def __new__(cls, units, diagnostics, file_doc=None):
        obj = super().__new__(cls, (units, diagnostics))
        obj.file_doc = file_doc
        return obj

    @property
    def units(self) -> List[DesignUnit]:
        return self[0]

    @property
    def diagnostics(self) -> List[Diagnostic]:
        return self[1]


def _matching(tokens: List[Token], start: int, opening="(", closing=")") -> Optional[int]:
    if start >= len(tokens) or tokens[start].value != opening:
        return None
    depth = 0
    for i in range(start, len(tokens)):
        value = tokens[i].value
        if value == opening:
            depth += 1
        elif value == closing:
            depth -= 1
            if depth == 0:
                return i
    return None


def _split_commas(tokens: List[Token]) -> List[List[Token]]:
    result, begin, depth = [], 0, 0
    for i, token in enumerate(tokens):
        if token.value in "([{":
            depth += 1
        elif token.value in ")]}":
            depth -= 1
        elif token.value == "," and depth == 0:
            if i > begin:
                result.append(tokens[begin:i])
            begin = i + 1
    if tokens[begin:]:
        result.append(tokens[begin:])
    return result


def _declaration_name(tokens: List[Token]) -> Optional[int]:
    """Index of the declared name: the last identifier before ``=`` that is
    not part of an unpacked dimension."""
    limit, depth = len(tokens), 0
    for i, t in enumerate(tokens):
        if t.value in "([{":
            depth += 1
        elif t.value in ")]}":
            depth -= 1
        elif t.value == "=" and depth == 0:
            limit = i
            break
    k = limit - 1
    while k >= 0:
        if tokens[k].value == "]":
            depth = 1
            k -= 1
            while k >= 0 and depth:
                depth += {"]": 1, "[": -1}.get(tokens[k].value, 0)
                k -= 1
            continue
        if tokens[k].kind == "identifier" and tokens[k].value not in KEYWORDS:
            return k
        k -= 1
    return None


class _SourceParser:
    def __init__(self, source: str, filename: str, plain_comments: bool):
        self.source = source
        self.filename = filename
        self.plain_comments = plain_comments
        self.tokens, comments = lex(source)
        self.docs = [d for d in comments if d.style != "plain"]
        self.plain = [d for d in comments if d.style == "plain"]
        self.doc_ends = [d.end for d in self.docs]
        self.position = {t.start: k for k, t in enumerate(self.tokens)}
        self.used: set = set()
        self.units: List[DesignUnit] = []
        self.diagnostics: List[Diagnostic] = []
        self.file_doc: Optional[FileDoc] = None

    # -- helpers ---------------------------------------------------------
    def text(self, tokens: List[Token]) -> str:
        return token_text(self.source, tokens)

    def diag(self, code, message, line, severity="warning"):
        self.diagnostics.append(Diagnostic(code, message, self.filename, line, severity))

    def after(self, token: Token, skip: int = 1) -> int:
        """Offset of the token ``skip`` places after ``token`` (end of text if none)."""
        k = self.position[token.start] + skip
        return self.tokens[k].start if k < len(self.tokens) else len(self.source) + 1

    def leading_doc(self, token: Token) -> Optional[DocBlock]:
        """The documentation comment directly in front of ``token``, if any."""
        k = bisect.bisect_right(self.doc_ends, token.start) - 1
        if k < 0:
            return None
        doc = self.docs[k]
        if doc.trailing or doc.start in self.used:
            return None
        # Comments, attributes and compiler directives may sit in between; code may not.
        previous = self.position[token.start] - 1
        if previous >= 0 and self.tokens[previous].start >= doc.end:
            return None
        return doc

    # -- top level -------------------------------------------------------
    def parse(self) -> ParseResult:
        tokens = self.tokens
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            prev = tokens[i - 1].value if i else ""
            if tok.value == "extern":
                i = self._skip_to(i, ";") + 1
            elif (tok.value == "class" and prev != "typedef") or (
                    tok.value == "interface" and i + 1 < len(tokens) and tokens[i + 1].value == "class"):
                i = self._skip_block(i if tok.value == "class" else i + 1, "class", "endclass")
            elif tok.value in UNIT_END and prev not in ("virtual", ".", "::"):
                i = self._unit(i)
            else:
                i += 1
        self._file_comment()
        for doc in self.docs:
            if doc.start in self.used:
                continue
            parsed = parse_comment(doc.text, doc.line)
            if parsed.has_tags and not parsed.is_file:
                self.diag("DOC004", "Documentation comment is not attached to a design unit or declaration",
                          doc.line)
        return ParseResult(self.units, self.diagnostics, self.file_doc)

    def _file_comment(self):
        for doc in self.docs:
            parsed = parse_comment(doc.text, doc.line)
            if parsed.is_file:
                self.used.add(doc.start)
                self.file_doc = FileDoc(parsed.autobrief().brief, parsed.description, parsed.metadata)
                return

    def _skip_to(self, i: int, value: str) -> int:
        while i < len(self.tokens) and self.tokens[i].value != value:
            i += 1
        return i

    def _skip_block(self, i: int, opening: str, closing: str) -> int:
        depth = 0
        while i < len(self.tokens):
            value = self.tokens[i].value
            if value == opening and (i == 0 or self.tokens[i - 1].value not in ("typedef", "virtual")):
                depth += 1
            elif value == closing:
                depth -= 1
                if depth <= 0:
                    return i + 1
            i += 1
        return i

    def _unit(self, start: int) -> int:
        tokens = self.tokens
        keyword = tokens[start]
        kind = "module" if keyword.value == "macromodule" else keyword.value
        end_keyword = UNIT_END[keyword.value]
        i = start + 1
        if i < len(tokens) and tokens[i].value in _LIFETIME:
            i += 1
        if i >= len(tokens) or tokens[i].kind != "identifier":
            return i
        name = tokens[i].value
        i = self._skip_imports(i + 1)
        parameters: List[Parameter] = []
        ports: List[Port] = []
        header_locals: List[Parameter] = []
        has_parameter_list = False
        header_parts: List[List[Token]] = []
        if i + 1 < len(tokens) and tokens[i].value == "#" and tokens[i + 1].value == "(":
            end = _matching(tokens, i + 1)
            if end is None:
                self.diag("HDL001", f"Unclosed parameter list for {name}", keyword.line, "error")
                return len(tokens)
            has_parameter_list = True
            parameters = self._parameters(tokens[i + 2:end], local=False, parts=header_parts)
            header_locals = [p for p in parameters if p.local]
            parameters = [p for p in parameters if not p.local]
            i = end + 1
        if i < len(tokens) and tokens[i].value == "(":
            end = _matching(tokens, i)
            if end is None:
                self.diag("HDL001", f"Unclosed port list for {name}", keyword.line, "error")
                return len(tokens)
            ports = self._ports(tokens[i + 1:end], parts=header_parts)
            i = end + 1
        if i >= len(tokens) or tokens[i].value != ";":
            self.diag("HDL001", f"Expected ';' after header of {name}", keyword.line, "error")
            return len(tokens)
        body_start = i + 1
        j, depth = body_start, 0
        while j < len(tokens):
            value = tokens[j].value
            if value == end_keyword:
                if depth == 0:
                    break
                depth -= 1
            elif value == keyword.value and tokens[j - 1].value not in ("virtual", "extern", ".", "::"):
                depth += 1
            j += 1
        if j == len(tokens):
            self.diag("HDL001", f"Missing {end_keyword} for {name}", keyword.line, "error")
            return len(tokens)
        unit = DesignUnit(kind=kind, name=name, file=self.filename, line=keyword.line,
                          end_line=tokens[j].line, parameters=parameters, ports=ports,
                          localparams=header_locals)
        anchors = _Anchors()
        for part, entity in header_parts:
            anchors.add(self, part, entity)
        self._body(unit, body_start, j, has_parameter_list, anchors)
        anchors.attach(self, unit)
        self._unit_comment(unit, keyword)
        self.units.append(unit)
        # Skip an optional end label: "endmodule : name".
        return j + 1

    def _skip_imports(self, i: int) -> int:
        """Skip ``import pkg::*;`` items allowed in a module header."""
        tokens = self.tokens
        while i < len(tokens) and tokens[i].value == "import":
            while i < len(tokens) and tokens[i].value != ";":
                if tokens[i].value in UNIT_END.values():
                    return i
                i += 1
            i += 1
        return i

    # -- declarations ----------------------------------------------------
    def _parameters(self, tokens: List[Token], local: bool, parts=None) -> List[Parameter]:
        result: List[Parameter] = []
        inherited_type = ""
        is_local = local
        for part in _split_commas(tokens):
            original = part
            if part[0].value in ("parameter", "localparam"):
                is_local = local or part[0].value == "localparam"
                inherited_type = ""
                part = part[1:]
            if not part:
                continue
            if part[0].value == "type":
                index = _declaration_name(part)
                if index is None:
                    continue
                eq = next((k for k, t in enumerate(part) if t.value == "="), None)
                param = Parameter(part[index].value, "type", self.text(part[eq + 1:]) if eq else "",
                                  line=part[index].line, local=is_local)
            else:
                index = _declaration_name(part)
                if index is None:
                    continue
                prefix = self.text(part[:index])
                if prefix:
                    inherited_type = prefix
                eq = next((k for k, t in enumerate(part) if t.value == "="), None)
                param = Parameter(part[index].value, prefix or inherited_type,
                                  self.text(part[eq + 1:]) if eq is not None else "",
                                  line=part[index].line, local=is_local)
            result.append(param)
            if parts is not None:
                parts.append((original, param))
        return result

    def _ports(self, tokens: List[Token], parts=None) -> List[Port]:
        result: List[Port] = []
        direction, port_type = "", ""
        for part in _split_commas(tokens):
            if part[0].value == ".":
                continue  # explicit port expressions are not supported
            explicit = part[0].value if part[0].value in DIRECTIONS else ""
            content = part[1:] if explicit else part
            index = _declaration_name(content)
            if index is None:
                continue
            prefix = self.text(content[:index])
            port_direction = direction
            if explicit:
                direction = port_direction = explicit
                port_type = prefix
            elif prefix:
                port_type = prefix
                # "intf.modport name" and "interface name" declare interface ports.
                if prefix.startswith("interface") or (len(content) >= 3 and content[1].value == "."):
                    port_direction = "interface"
            port = Port(content[index].value, port_direction, prefix or port_type, line=content[index].line)
            result.append(port)
            if parts is not None:
                parts.append((part, port))
        return result

    def _statement_end(self, i: int, stop: int) -> int:
        """Index of the ``;`` that ends the statement starting at ``i``."""
        depth = 0
        tokens = self.tokens
        while i < stop:
            value = tokens[i].value
            if value in "([{":
                depth += 1
            elif value in ")]}":
                depth -= 1
            elif value == ";" and depth <= 0:
                return i
            i += 1
        return stop

    def _body(self, unit: DesignUnit, start: int, stop: int, has_parameter_list: bool, anchors: _Anchors):
        tokens = self.tokens
        ports = {p.name: p for p in unit.ports}
        i = start
        while i < stop:
            tok = tokens[i]
            value = tok.value
            if value in _SKIP_BLOCKS and self._block_start(i, start, stop):
                if value == "class":
                    header_end = self._skip_to(i, ";")
                    self._member(unit, anchors, "class", i, header_end, self._name_after(i + 1),
                                 self.text(tokens[i:header_end]))
                i = self._skip_block(i, value, _SKIP_BLOCKS[value])
                continue
            if value in ("function", "task") and not any(
                    t.value in ("import", "export", "extern", "pure") for t in tokens[max(start, i - 2):i]):
                i = self._subroutine(unit, anchors, i, stop)
                continue
            if value in ("import", "export") and i + 1 < stop and tokens[i + 1].kind == "string":
                i = self._statement_end(i, stop) + 1
                continue
            if value in ("localparam", "parameter"):
                end = self._statement_end(i, stop)
                local = value == "localparam" or has_parameter_list or unit.kind == "package"
                parts: list = []
                for param in self._parameters(tokens[i + 1:end], local=local, parts=parts):
                    (unit.localparams if param.local else unit.parameters).append(param)
                for part, entity in parts:
                    anchors.add(self, part, entity, statement_start=tok)
                i = end + 1
                continue
            if value in DIRECTIONS and self._statement_start(i, start):
                end = self._statement_end(i, stop)
                parts = []
                for parsed in self._ports(tokens[i:end], parts=parts):
                    if parsed.name in ports:  # ignore names that are not unit ports
                        ports[parsed.name].direction = parsed.direction
                        ports[parsed.name].type = parsed.type
                for part, entity in parts:
                    if entity.name in ports:
                        anchors.add(self, part, ports[entity.name], statement_start=tok)
                i = end + 1
                continue
            if value == "typedef":
                end = self._statement_end(i, stop)
                statement = tokens[i:end]
                index = _declaration_name(statement)
                if index is not None and len(statement) > 2:
                    self._member(unit, anchors, "typedef", i, end, statement[index], self.text(statement) + ";")
                i = end + 1
                continue
            if value == "modport":
                i = self._modports(unit, anchors, i, stop)
                continue
            if tok.kind == "identifier" and value not in KEYWORDS and self._statement_start(i, start):
                found = self._instances(unit, anchors, i, stop)
                if found is not None:
                    i = found
                    continue
            i += 1

    def _block_start(self, i: int, start: int, stop: int) -> bool:
        """Whether ``class``/``property``/... at ``i`` opens a block with an end keyword."""
        value = self.tokens[i].value
        prev = self.tokens[i - 1].value if i > start else ";"
        if prev in ("typedef", "disable", ".", "::"):
            return False
        if value == "clocking":
            return any(t.value == "@" for t in self.tokens[i:self._statement_end(i, stop)])
        if value == "class" and prev in ("virtual", "interface"):
            return True
        return self._statement_start(i, start) or prev in ("default", "global")

    def _statement_start(self, i: int, start: int) -> bool:
        if i == start:
            return True
        prev = self.tokens[i - 1]
        if prev.value in _STATEMENT_END:
            return True
        # "begin : label", "end : label" and "label :"
        return i - 2 >= start and self.tokens[i - 2].value == ":" and prev.kind == "identifier"

    def _name_after(self, i: int) -> Optional[Token]:
        while i < len(self.tokens) and (self.tokens[i].kind != "identifier" or self.tokens[i].value in KEYWORDS):
            if self.tokens[i].value == ";":
                return None
            i += 1
        return self.tokens[i] if i < len(self.tokens) else None

    def _member(self, unit, anchors, kind, i, end, name_token, signature):
        if name_token is None:
            return
        member = Member(kind, name_token.value, signature, line=self.tokens[i].line)
        unit.members.append(member)
        anchors.add_member(self, self.tokens[i], name_token, member, self.after(self.tokens[min(end, len(self.tokens) - 1)]))

    def _subroutine(self, unit, anchors, i, stop) -> int:
        tokens = self.tokens
        keyword = tokens[i].value
        header_end = self._statement_end(i, stop)
        header = tokens[i:header_end]
        paren = next((k for k, t in enumerate(header) if t.value == "("), len(header))
        name = next((t for t in reversed(header[:paren]) if t.kind == "identifier" and t.value not in KEYWORDS),
                    None)
        start = i
        while start - 1 >= 0 and tokens[start - 1].value in ("static", "virtual", "protected", "local"):
            start -= 1
        self._member(unit, anchors, keyword, start, header_end, name, self.text(tokens[start:header_end]) + ";")
        end_keyword = "end" + keyword
        j = header_end
        while j < stop and tokens[j].value != end_keyword:
            j += 1
        return j + 1

    def _modports(self, unit, anchors, i, stop) -> int:
        tokens = self.tokens
        end = self._statement_end(i, stop)
        for n, item in enumerate(_split_commas(tokens[i + 1:end])):
            if len(item) < 2 or item[0].kind != "identifier" or item[1].value != "(":
                continue
            close = _matching(item, 1)
            modport = Modport(item[0].value, line=item[0].line)
            direction = ""
            for part in _split_commas(item[2:close] if close else []):
                head = part[0].value
                if head in DIRECTIONS or head in ("import", "export", "clocking"):
                    direction, part = head, part[1:]
                if part and part[0].kind == "identifier":
                    modport.ports.append(Port(part[0].value, direction, line=part[0].line))
            unit.modports.append(modport)
            anchors.add_member(self, tokens[i] if n == 0 else item[0], item[0], modport, self.after(item[-1], 2))
        return end + 1

    def _connections(self, tokens: List[Token]) -> List[Connection]:
        result = []
        for part in _split_commas(tokens):
            if part[0].value == "." and len(part) > 1:
                formal = part[1].value
                if formal == "*":
                    result.append(Connection("*", "*"))
                elif len(part) > 2 and part[2].value == "(":
                    close = _matching(part, 2) or len(part)
                    result.append(Connection(formal, self.text(part[3:close])))
                else:
                    result.append(Connection(formal, formal))
            else:
                result.append(Connection("", self.text(part)))
        return result

    def _instances(self, unit, anchors, i, stop) -> Optional[int]:
        """Recognize ``mod #(...) u_a (...), u_b (...);`` at a statement start."""
        tokens = self.tokens
        module = tokens[i]
        k = i + 1
        overrides: List[Connection] = []
        if k + 1 < stop and tokens[k].value == "#":
            if tokens[k + 1].value != "(":
                return None
            close = _matching(tokens, k + 1)
            if close is None or close >= stop:
                return None
            overrides = self._connections(tokens[k + 2:close])
            k = close + 1
        found = []
        while True:
            if k >= stop or tokens[k].kind != "identifier" or tokens[k].value in KEYWORDS:
                return None
            name = tokens[k]
            k += 1
            array_start = k
            while k < stop and tokens[k].value == "[":
                close = _matching(tokens, k, "[", "]")
                if close is None:
                    return None
                k = close + 1
            array = self.text(tokens[array_start:k])
            if k >= stop or tokens[k].value != "(":
                return None
            close = _matching(tokens, k)
            if close is None or close >= stop:
                return None
            found.append((Instance(module.value, name.value, name.line, array, overrides,
                                   self._connections(tokens[k + 1:close])), name))
            k = close + 1
            if k < stop and tokens[k].value == ",":
                k += 1
                continue
            if k < stop and tokens[k].value == ";":
                break
            return None
        for n, (instance, name_token) in enumerate(found):
            unit.instances.append(instance)
            anchors.add_member(self, module if n == 0 else name_token, name_token, instance, self.after(tokens[k]))
        return k + 1

    # -- documentation ---------------------------------------------------
    def _unit_comment(self, unit: DesignUnit, keyword: Token):
        doc = self.leading_doc(keyword)
        if doc is None:
            return
        parsed = parse_comment(doc.text, doc.line)
        if parsed.is_file:
            return
        self.used.add(doc.start)
        parsed.autobrief()
        unit.brief, unit.description = parsed.brief, parsed.description
        unit.metadata = dict(parsed.metadata)
        unit.deprecated = parsed.deprecated
        unit.notes = parsed.lists["notes"]
        unit.warnings = parsed.lists["warnings"]
        unit.todos = parsed.lists["todos"]
        unit.see = parsed.lists["see"]
        unit.documented = parsed.has_content
        for tag, line in parsed.unknown_tags:
            self.diag("DOC005", f"Unknown documentation tag @{tag}", line)
        self._entries(unit, parsed)

    def _entries(self, unit: DesignUnit, doc: DocComment):
        tables = {
            "port": {p.name: p for p in unit.ports},
            "parameter": {p.name: p for p in unit.parameters},
            "localparam": {p.name: p for p in unit.localparams},
            "modport": {m.name: m for m in unit.modports},
            "instance": {m.name: m for m in unit.instances},
        }
        seen = set()
        for entry in doc.entries:
            tag = entry.tag
            if tag == "param":
                if entry.direction or (entry.name not in tables["parameter"] and entry.name in tables["port"]):
                    tag = "port"
                elif entry.name in tables["localparam"] and entry.name not in tables["parameter"]:
                    tag = "localparam"
                else:
                    tag = "parameter"
            label = "@" + (entry.direction or tag)
            key = (tag, entry.name)
            if key in seen:
                self.diag("DOC003", f"Duplicate documentation for {entry.name}", entry.line)
                continue
            seen.add(key)
            target = tables[tag].get(entry.name)
            if target is None:
                self.diag("DOC001", f"{label} refers to unknown {tag} {entry.name}", entry.line)
                continue
            if not entry.text:
                self.diag("DOC006", f"{label} {entry.name} has no description", entry.line)
            if target.description:
                self.diag("DOC003", f"{entry.name} is documented both inline and in the unit comment", entry.line)
            target.description = entry.text
            if (tag == "port" and entry.direction and target.direction
                    and target.direction != entry.direction and target.direction != "interface"):
                self.diag("DOC002", f"{label} {entry.name} is declared {target.direction}", entry.line)


class _Anchors:
    """Collects documentable declarations inside one unit.

    A leading comment documents the declaration that starts right after it;
    a trailing ``///<`` comment documents the closest declared name before it.
    """

    def __init__(self):
        self.leading: List[Tuple[Token, object]] = []
        # (offset of the name, name token, entity, offset where trailing comments stop counting)
        self.names: List[Tuple[int, Token, object, int]] = []

    def add(self, parser: _SourceParser, part: List[Token], entity, statement_start: Optional[Token] = None):
        index = _declaration_name(part[1:] if part[0].value in DIRECTIONS else part)
        offset = 1 if part[0].value in DIRECTIONS else 0
        name = part[index + offset] if index is not None else part[-1]
        self.leading.append((part[0], entity))
        if statement_start is not None and statement_start is not part[0]:
            self.leading.append((statement_start, entity))
        # A trailing comment may follow the separator: "input a, ///< doc".
        self.names.append((name.start, name, entity, parser.after(part[-1], 2)))

    def add_member(self, parser, first: Token, name: Token, entity, limit: int):
        self.leading.append((first, entity))
        self.names.append((name.start, name, entity, limit))

    def attach(self, parser: _SourceParser, unit: DesignUnit):
        documented = set()
        for first, entity in self.leading:
            if id(entity) in documented:
                continue
            doc = parser.leading_doc(first)
            if doc is not None:
                parsed = parse_comment(doc.text, doc.line)
                if parsed.is_file:
                    continue
                parser.used.add(doc.start)
                entity.description = parsed.text
                documented.add(id(entity))
        self.names.sort(key=lambda item: item[0])
        starts = [item[0] for item in self.names]
        trailing = [d for d in parser.docs if d.trailing and d.start not in parser.used]
        if parser.plain_comments:
            trailing += [d for d in parser.plain if d.start not in parser.used]
        for doc in trailing:
            k = bisect.bisect_left(starts, doc.start) - 1
            if k < 0:
                continue
            _, name, entity, limit = self.names[k]
            if not (unit.line <= doc.line <= unit.end_line) or doc.start > limit:
                continue
            if doc.style == "plain":
                # Ordinary comments count only on the declaration's own line.
                if doc.line != name.line or id(entity) in documented:
                    continue
                text = doc.text[2:].strip()
                if not text:
                    continue
            else:
                text = parse_comment(doc.text, doc.line).text
                if id(entity) in documented:
                    parser.diag("DOC003", f"{name.value} has more than one inline comment", doc.line)
            parser.used.add(doc.start)
            entity.description = text
            documented.add(id(entity))


def parse_source(source: str, filename: str = "<memory>", plain_comments: bool = False) -> ParseResult:
    """Return design units and diagnostics for one (preprocessed) source text."""
    return _SourceParser(source, filename, plain_comments).parse()


def parse_file(file_path, display_name: Optional[str] = None, encoding: str = "utf-8",
               plain_comments: bool = False) -> ParseResult:
    path = Path(file_path)
    return parse_source(path.read_text(encoding=encoding), display_name or path.as_posix(), plain_comments)


def parse_verilog_file(file_path):
    """Legacy API returning ``(docs, (documented, total, missing))``."""
    units, _ = parse_file(file_path)
    documented = [u for u in units if u.documented]

    def described(items, direction=None):
        return [p.name + " " + p.description for p in items
                if p.description and (direction is None or p.direction == direction)]

    docs = [{"module": u.name, "unit_kind": u.kind, "brief": u.brief, "description": u.description,
             "inputs": described(u.ports, "input"), "outputs": described(u.ports, "output"),
             "inouts": described(u.ports, "inout"), "parameters": described(u.parameters),
             "localparams": described(u.localparams)} for u in documented]
    return docs, (len(documented), len(units), [u.name for u in units if not u.documented])


def find_all_units(lines) -> List[Tuple[str, str, int]]:
    units, _ = parse_source("".join(lines))
    return [(u.kind, u.name, u.line - 1) for u in units]


def remove_doxnet_comments(code: str) -> str:
    """Remove documentation comments, keeping line numbers intact."""
    _, comments = lex(code)
    parts, last = [], 0
    for doc in comments:
        if doc.style == "plain":
            continue
        parts.extend((code[last:doc.start], "\n" * code.count("\n", doc.start, doc.end)))
        last = doc.end
    parts.append(code[last:])
    return "".join(parts)

