"""Markdown output (GitHub Flavored Markdown, also the input for Pandoc)."""
from __future__ import annotations

from html import escape
import re
from typing import Dict, List

from .. import __version__
from ..hierarchy import walk
from ..model import DesignUnit, Project
from .common import by_file, by_kind, percent, unit_coverage, unit_id, unit_index
from .i18n import TRANSLATIONS

_CODE = re.compile(r"(^|\n)(```|~~~)[^\n]*\n.*?(\n\2[ \t]*(?=\n|$)|$)|(`+)(?:(?!\4).)+?\4", re.S)


def safe_md(text: str) -> str:
    """Escape raw HTML and table delimiters but keep Markdown formatting.

    Code spans and fenced blocks are left alone; Markdown shows them literally.
    """
    text = text or ""
    out, last = [], 0
    for m in _CODE.finditer(text):
        out.append(escape(text[last:m.start()], quote=False).replace("|", r"\|"))
        out.append(m.group())
        last = m.end()
    out.append(escape(text[last:], quote=False).replace("|", r"\|"))
    return "".join(out)


def code(text: str, table: bool = False) -> str:
    """An inline code span that survives backticks and, in tables, pipes."""
    text = (text or "").replace("\n", " ")
    if not text:
        return ""
    longest = max((len(m.group()) for m in re.finditer(r"`+", text)), default=0)
    fence = "`" * (longest + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    if table:
        text = text.replace("|", r"\|")
    return f"{fence}{pad}{text}{pad}{fence}"


def _cell(text: str) -> str:
    # Inside a table even a pipe in a code span ends the cell unless escaped.
    return re.sub(r"(?<!\\)\|", r"\\|", safe_md(text)).replace("\n\n", " ").replace("\n", " ")


def _table(headers: List[str], rows: List[List[str]]) -> str:
    if not rows:
        return ""
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    lines += ["| " + " | ".join(cell or " " for cell in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def _link(name: str, index: Dict[str, DesignUnit]) -> str:
    unit = index.get(name)
    return f"[{code(name)}](#{unit_id(unit)})" if unit else code(name)


def _source_fence(source: str) -> str:
    # An HDL string containing ``` must not end the code block early.
    longest = max((len(m.group()) for m in re.finditer(r"`+", source)), default=0)
    fence = "`" * max(3, longest + 1)
    return fence + "systemverilog\n" + source.rstrip("\n") + "\n" + fence + "\n"


def _unit(unit: DesignUnit, tr, index) -> str:
    kind = tr["kind_names"].get(unit.kind, unit.kind)
    out = [f'<a id="{unit_id(unit)}"></a>', "", f"### {kind} {code(unit.name)}", ""]
    if unit.deprecated is not None:
        out += [f"> **{tr['deprecated']}.** {safe_md(unit.deprecated)}".rstrip(), ""]
    if not unit.documented:
        out += [f"*{tr['undocumented']}*", ""]
    if unit.brief:
        out += [f"**{safe_md(unit.brief)}**", ""]
    if unit.description:
        out += [safe_md(unit.description), ""]
    facts = [f"{tr['defined_in']}: {code(unit.file + ':' + str(unit.line))}"]
    facts += [f"{tr.get(key, key.capitalize())}: {safe_md(value)}" for key, value in unit.metadata.items()]
    out += ["  \n".join(facts), ""]
    for items, label in ((unit.notes, "note"), (unit.warnings, "warning")):
        for text in items:
            out += [f"> **{tr[label]}:** {safe_md(text)}", ""]

    if unit.parameters:
        out += [f"#### {tr['parameters']}", "", _table(
            [tr["name"], tr["type"], tr["default"], tr["description"]],
            [[code(p.name, True), code(p.type, True), code(p.default, True), _cell(p.description)]
             for p in unit.parameters])]
    if unit.ports:
        out += [f"#### {tr['ports']}", "", _table(
            [tr["name"], tr["direction"], tr["type"], tr["description"]],
            [[code(p.name, True), p.direction, code(p.type, True), _cell(p.description)] for p in unit.ports])]
    if unit.modports:
        out += [f"#### {tr['modports']}", "", _table(
            [tr["name"], tr["ports"], tr["description"]],
            [[code(m.name, True), ", ".join(code(f"{p.direction} {p.name}".strip(), True) for p in m.ports),
              _cell(m.description)] for m in unit.modports])]
    if unit.localparams:
        out += [f"#### {tr['localparams']}", "", _table(
            [tr["name"], tr["type"], tr["default"], tr["description"]],
            [[code(p.name, True), code(p.type, True), code(p.default, True), _cell(p.description)]
             for p in unit.localparams])]
    if unit.instances:
        out += [f"#### {tr['instances']}", "", _table(
            [tr["instance"], tr["module"], tr["overrides"], tr["description"]],
            [[code(i.name + i.array, True),
              _link(i.module, index) + ("" if i.resolved else f" ({tr['external']})"),
              ", ".join(code(f"{c.formal}={c.actual}" if c.formal else c.actual, True) for c in i.parameters),
              _cell(i.description)] for i in unit.instances])]
    if unit.members:
        out += [f"#### {tr['members']}", ""]
        for member in unit.members:
            out += [f"- {tr['kind_names'].get(member.kind, member.kind)} {code(member.name)}"
                    + (f": {_cell(member.description)}" if member.description else ""),
                    "", "  " + code(member.signature), ""]
    if unit.instantiated_by:
        out += [f"{tr['instantiated_by']}: " + ", ".join(_link(name, index) for name in unit.instantiated_by), ""]
    if unit.todos:
        out += [f"**{tr['todo']}:**", ""] + [f"- {safe_md(t)}" for t in unit.todos] + [""]
    if unit.see:
        out += [f"**{tr['see']}:** " + ", ".join(safe_md(s) for s in unit.see), ""]
    return "\n".join(out)


def render_markdown(project: Project, sources: Dict[str, str], language: str = "en",
                    include_source: bool = True) -> str:
    tr = TRANSLATIONS[language]
    index = unit_index(project)
    cov = project.coverage()
    out = ["# " + safe_md(project.title), "", f"*{tr['generated_by']} {__version__}*", ""]

    out += [f"## {tr['overview']}", "", _table(
        ["", tr["documented"], tr["total"], "%"],
        [[tr["metrics"][key], str(cov[key]["documented"]), str(cov[key]["total"]), percent(cov[key], tr["n_a"])]
         for key in ("units", "ports", "parameters")])]
    for kind, units in by_kind(project).items():
        out.append(f"**{tr['kinds'].get(kind, kind)}:** " + ", ".join(_link(u.name, index) for u in units) + "  ")
    out.append("")

    if project.hierarchy:
        out += [f"### {tr['hierarchy']}", ""]
        for depth, node in walk(project.hierarchy):
            label = _link(node.module, index)
            if node.instance:
                label = f"{code(node.instance)}: {label}"
            if not node.resolved:
                label += f" ({tr['external']})"
            if node.recursive:
                label += f" ({tr['recursive']})"
            out.append("  " * depth + "- " + label)
        out.append("")

    out += [f"## {tr['files']}", ""]
    groups = by_file(project)
    for filename, units in groups.items():
        doc = project.file_docs.get(filename)
        line = "- " + code(filename) + (f": {safe_md(doc.brief)}" if doc and doc.brief else "")
        out.append(line)
        for unit in units:
            out.append(f"  - {tr['kind_names'].get(unit.kind, unit.kind)} {_link(unit.name, index)}")
    out.append("")

    for filename, units in groups.items():
        out += [f"## {tr['file']}: {code(filename)}", ""]
        doc = project.file_docs.get(filename)
        if doc:
            if doc.brief:
                out += [f"**{safe_md(doc.brief)}**", ""]
            if doc.description:
                out += [safe_md(doc.description), ""]
        for unit in units:
            out.append(_unit(unit, tr, index))
        if include_source and filename in sources:
            out += [f"### {tr['source']}", "", _source_fence(sources[filename])]

    out += [f"## {tr['diagnostics']}", ""]
    if project.diagnostics:
        out.append(_table([tr["file"], tr["line"], tr["code"], tr["message"]], [
            [code(d.file, True), str(d.line), f"{d.code} ({d.severity})", _cell(d.message)]
            for d in project.diagnostics]))
    else:
        out += [tr["no_diagnostics"], ""]
    out += [f"## {tr['unit_coverage']}", "", _table(
        [tr["name"], tr["kind"], tr["documented"], tr["ports"], tr["parameters"]],
        [[_link(u.name, index) if index.get(u.name) is u else code(u.name), u.kind,
          tr["yes"] if u.documented else f"**{tr['no']}**",
          "{}/{}".format(*unit_coverage(u)["ports"]), "{}/{}".format(*unit_coverage(u)["parameters"])]
         for u in project.units])]
    return "\n".join(out).rstrip() + "\n"
