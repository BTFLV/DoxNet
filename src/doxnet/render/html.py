"""Standalone HTML output: one file, no external resources."""
from __future__ import annotations

from html import escape
from importlib import resources
from typing import Dict, List, Optional
from urllib.parse import quote, urlsplit

from markdown import Markdown
from markdown.extensions import Extension
import nh3
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

from .. import __version__
from ..model import DesignUnit, HierarchyNode, Project
from .common import by_file, by_kind, file_id, percent, unit_coverage, unit_id, unit_index
from .diagram import block_diagram
from .i18n import TRANSLATIONS

_ALLOWED_TAGS = {"a", "p", "div", "span", "ul", "ol", "li", "strong", "em", "code", "pre", "blockquote",
                 "table", "thead", "tbody", "tr", "td", "th", "br", "hr", "del", "sup", "sub", "h5", "h6"}
_ALLOWED_ATTRS = {"a": {"href", "title"}, "td": {"align"}, "th": {"align"}}
_THEME_INIT = ("(function(){var r=document.documentElement;try{r.dataset.theme=localStorage.getItem('doxnet-theme')"
               "||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light')}catch(e){r.dataset.theme='light'}})();")


def _asset(name: str) -> str:
    return resources.files("doxnet.render").joinpath("assets", name).read_text(encoding="utf-8")


class _NoRawHtml(Extension):
    """Treat HTML in comments as text instead of passing it through."""

    def extendMarkdown(self, md):  # noqa: N802 - Markdown API
        md.preprocessors.deregister("html_block")
        md.inlinePatterns.deregister("html")


_MARKDOWN = Markdown(extensions=["tables", "fenced_code", "sane_lists", _NoRawHtml()])


def prose(text: str) -> str:
    """Render comment text as Markdown, with raw HTML escaped and the result sanitized."""
    if not text:
        return ""
    html = _MARKDOWN.reset().convert(text)
    return nh3.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS,
                     url_schemes={"http", "https", "mailto"}, link_rel="noopener noreferrer")


def _code(text: str) -> str:
    return f"<code>{escape(text)}</code>" if text else ""


def _highlight(source: str, anchor: str) -> str:
    try:
        lexer = get_lexer_by_name("systemverilog")
    except ClassNotFound:  # very old Pygments
        lexer = get_lexer_by_name("verilog")
    formatter = HtmlFormatter(cssclass="highlight", linenos="table", lineanchors=anchor, anchorlinenos=True)
    return highlight(source, lexer, formatter)


def check_source_url(source_url: Optional[str]) -> None:
    if not source_url:
        return
    parsed = urlsplit(source_url)
    if (parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        raise ValueError("source_url must be an HTTPS base URL without credentials, query or fragment")


def _location(unit: DesignUnit, source_url: Optional[str], embedded: bool, line: Optional[int] = None) -> str:
    line = line or unit.line
    label = f"{escape(unit.file)}:{line}"
    if source_url:
        url = source_url.rstrip("/") + "/" + quote(unit.file.replace("\\", "/"), safe="/") + f"#L{line}"
        return f'<a class="source-link" href="{escape(url, quote=True)}">{label}</a>'
    if embedded:
        return f'<a class="source-link" href="#{file_id(unit.file)}-{line}">{label}</a>'
    return label


class _Page:
    def __init__(self, project: Project, sources: Dict[str, str], language: str, include_source: bool,
                 source_url: Optional[str]):
        self.project = project
        self.sources = sources
        self.tr = TRANSLATIONS[language]
        self.language = language
        self.include_source = include_source
        self.source_url = source_url
        self.index = unit_index(project)

    def link(self, name: str) -> str:
        unit = self.index.get(name)
        if unit is None:
            return _code(name)
        return f'<a href="#{unit_id(unit)}"><code>{escape(name)}</code></a>'

    def where(self, unit: DesignUnit, line: Optional[int] = None) -> str:
        embedded = self.include_source and unit.file in self.sources
        return _location(unit, self.source_url, embedded, line)

    # -- page parts ------------------------------------------------------
    def sidebar(self) -> str:
        tr = self.tr
        out = ['<nav class="sidebar" aria-label="Navigation"><ul>',
               f'<li><a href="#overview">{escape(tr["overview"])}</a></li>']
        if self.project.hierarchy:
            out.append(f'<li><a href="#hierarchy">{escape(tr["hierarchy"])}</a></li>')
        out.append(f'<li><a href="#coverage">{escape(tr["unit_coverage"])}</a></li>')
        count = len(self.project.diagnostics)
        out.append(f'<li><a href="#diagnostics">{escape(tr["diagnostics"])}<span>{count}</span></a></li></ul>')
        for kind, units in by_kind(self.project).items():
            out.append(f'<h2>{escape(tr["kinds"].get(kind, kind))}</h2><ul>')
            for unit in units:
                css = "" if unit.documented else ' class="undoc"'
                out.append(f'<li data-search="{escape(self._search_text(unit), quote=True)}">'
                           f'<a href="#{unit_id(unit)}"{css}>{escape(unit.name)}</a></li>')
            out.append("</ul>")
        out.append(f'<h2>{escape(tr["files"])}</h2><ul>')
        for filename in self.project.files:
            out.append(f'<li><a href="#{file_id(filename)}">{escape(filename)}</a></li>')
        out.append("</ul></nav>")
        return "".join(out)

    def overview(self) -> str:
        tr = self.tr
        cov = self.project.coverage()
        cards = [f'<div class="card"><div class="label">{escape(tr["design_units"])}</div>'
                 f'<div class="value">{len(self.project.units)}</div></div>',
                 f'<div class="card"><div class="label">{escape(tr["files"])}</div>'
                 f'<div class="value">{len(self.project.files)}</div></div>']
        for key in ("units", "ports", "parameters"):
            metric = cov[key]
            value = metric["percent"]
            level = "" if value is None or value >= 90 else (" mid" if value >= 60 else " low")
            width = 0 if value is None else value
            cards.append(f'<div class="card" title="{escape(tr["coverage"], quote=True)}">'
                         f'<div class="label">{escape(tr["metrics"][key])} · {escape(tr["documented"])}</div>'
                         f'<div class="value">{percent(metric, tr["n_a"])}</div>'
                         f'<div class="label">{metric["documented"]} / {metric["total"]}</div>'
                         f'<div class="bar{level}"><span style="width:{width:.1f}%"></span></div></div>')
        return (f'<section id="overview"><h1>{escape(self.project.title)}</h1>'
                f'<p class="subtitle">{escape(tr["generated_by"])} {escape(__version__)}</p>'
                f'<div class="cards">{"".join(cards)}</div></section>')

    def hierarchy(self) -> str:
        if not self.project.hierarchy:
            return ""

        def render(nodes: List[HierarchyNode]) -> str:
            items = []
            for node in nodes:
                label = self.link(node.module)
                if node.instance:
                    label = f'<span class="inst">{escape(node.instance)}</span> : {label}'
                if not node.resolved:
                    label += f' <span class="badge">{escape(self.tr["external"])}</span>'
                if node.recursive:
                    label += f' <span class="badge">{escape(self.tr["recursive"])}</span>'
                children = f"<ul>{render(node.children)}</ul>" if node.children else ""
                items.append(f"<li>{label}{children}</li>")
            return "".join(items)

        return (f'<section id="hierarchy"><h2>{escape(self.tr["hierarchy"])}</h2>'
                f'<ul class="tree">{render(self.project.hierarchy)}</ul></section>')

    def coverage(self) -> str:
        tr = self.tr
        rows = []
        for unit in self.project.units:
            cov = unit_coverage(unit)
            mark = '<span class="ok">✓</span>' if unit.documented else '<span class="no">✗</span>'
            cells = []
            for key in ("ports", "parameters"):
                done, total = cov[key]
                css = ' class="no"' if done < total else ""
                cells.append(f"<td{css}>{done}/{total}</td>" if total else "<td>–</td>")
            rows.append(f"<tr><td>{self.link(unit.name) if self.index.get(unit.name) is unit else _code(unit.name)}"
                        f"</td><td>{escape(unit.kind)}</td><td>{mark}</td>{''.join(cells)}</tr>")
        return (f'<section id="coverage"><h2>{escape(tr["unit_coverage"])}</h2><table><thead><tr>'
                f'<th>{escape(tr["name"])}</th><th>{escape(tr["kind"])}</th><th>{escape(tr["documented"])}</th>'
                f'<th>{escape(tr["ports"])}</th><th>{escape(tr["parameters"])}</th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table></section>')

    def diagnostics(self) -> str:
        tr = self.tr
        if not self.project.diagnostics:
            body = f"<p>{escape(tr['no_diagnostics'])}</p>"
        else:
            rows = "".join(
                f'<tr><td><code>{escape(d.file)}:{d.line}</code></td>'
                f'<td class="diag-{escape(d.severity)}">{escape(d.code)}</td><td>{escape(d.message)}</td></tr>'
                for d in self.project.diagnostics)
            body = (f'<table><thead><tr><th>{escape(tr["file"])}</th><th>{escape(tr["code"])}</th>'
                    f'<th>{escape(tr["message"])}</th></tr></thead><tbody>{rows}</tbody></table>')
        return f'<section id="diagnostics"><h2>{escape(tr["diagnostics"])}</h2>{body}</section>'

    def files(self) -> str:
        tr = self.tr
        out = []
        for filename, units in by_file(self.project).items():
            doc = self.project.file_docs.get(filename)
            fid = file_id(filename)
            head = f'<div class="file-head" id="{fid}"><h2>{escape(filename)}</h2>'
            if doc and doc.brief:
                head += f"<p>{escape(doc.brief)}</p>"
            head += "</div>"
            parts = [head]
            if doc and doc.description:
                parts.append(f'<div class="prose">{prose(doc.description)}</div>')
            parts += [self.unit(unit) for unit in units]
            if self.include_source and filename in self.sources:
                parts.append(f'<details class="source"><summary>{escape(tr["source"])}: {escape(filename)}</summary>'
                             f'{_highlight(self.sources[filename], fid)}</details>')
            out.append(f'<div class="file-block">{"".join(parts)}</div>')
        return f'<section id="units">{"".join(out)}</section>'

    # -- one design unit -------------------------------------------------
    def _search_text(self, unit: DesignUnit) -> str:
        words = [unit.kind, unit.name, unit.file, unit.brief]
        words += [p.name for p in unit.ports] + [p.name for p in unit.parameters]
        words += [m.name for m in unit.members] + [i.module for i in unit.instances]
        return " ".join(w for w in words if w).lower()

    def unit(self, unit: DesignUnit) -> str:
        tr = self.tr
        uid = unit_id(unit)
        head = [f'<span class="badge">{escape(tr["kind_names"].get(unit.kind, unit.kind))}</span>',
                f"<h3>{escape(unit.name)}</h3>"]
        if unit.deprecated is not None:
            head.append(f'<span class="badge deprecated">{escape(tr["deprecated"])}</span>')
        if not unit.documented:
            head.append(f'<span class="badge undocumented">{escape(tr["undocumented"])}</span>')
        head.append(f'<span class="loc">{self.where(unit)}</span>')
        out = [f'<article class="unit" id="{uid}" data-search="{escape(self._search_text(unit), quote=True)}">',
               f'<div class="unit-head">{"".join(head)}</div>']
        if unit.deprecated:
            out.append(f'<div class="callout deprecated"><strong>{escape(tr["deprecated"])}</strong>'
                       f'{prose(unit.deprecated)}</div>')
        if unit.brief:
            out.append(f'<div class="brief">{prose(unit.brief)}</div>')
        if unit.description:
            out.append(f'<div class="prose">{prose(unit.description)}</div>')
        if unit.metadata:
            out.append('<dl class="meta">' + "".join(
                f"<dt>{escape(tr.get(k, k.capitalize()))}</dt><dd>{escape(v)}</dd>"
                for k, v in unit.metadata.items()) + "</dl>")
        for items, css, label in ((unit.notes, "note", "note"), (unit.warnings, "warning", "warning")):
            for text in items:
                out.append(f'<div class="callout {css}"><strong>{escape(tr[label])}</strong>{prose(text)}</div>')
        diagram = block_diagram(unit) if unit.kind != "package" else ""
        if diagram:
            out.append(f'<figure class="diagram" aria-label="{escape(tr["block_diagram"], quote=True)}">'
                       f'{diagram}</figure>')
        out.append(self._parameters(unit, unit.parameters, tr["parameters"], "param"))
        out.append(self._ports(unit))
        out.append(self._modports(unit))
        out.append(self._parameters(unit, unit.localparams, tr["localparams"], "localparam"))
        out.append(self._instances(unit))
        out.append(self._members(unit))
        if unit.instantiated_by:
            out.append(f'<p><strong>{escape(tr["instantiated_by"])}:</strong> '
                       + ", ".join(self.link(name) for name in unit.instantiated_by) + "</p>")
        if unit.todos:
            out.append(f'<h4>{escape(tr["todo"])}</h4><ul>'
                       + "".join(f"<li>{prose(t)}</li>" for t in unit.todos) + "</ul>")
        if unit.see:
            out.append(f'<p><strong>{escape(tr["see"])}:</strong> '
                       + ", ".join(self.link(s) if s in self.index else escape(s) for s in unit.see) + "</p>")
        out.append("</article>")
        return "".join(out)

    def _row_id(self, unit: DesignUnit, prefix: str, name: str) -> str:
        return f"{unit_id(unit)}-{prefix}-{escape(name.lstrip(chr(92)), quote=True)}"

    def _parameters(self, unit, params, title, prefix) -> str:
        if not params:
            return ""
        tr = self.tr
        rows = "".join(
            f'<tr id="{self._row_id(unit, prefix, p.name)}"{"" if p.description else " class=missing"}>'
            f"<td>{_code(p.name)}</td><td>{_code(p.type)}</td><td>{_code(p.default)}</td>"
            f'<td class="desc">{prose(p.description)}</td></tr>' for p in params)
        return (f"<h4>{escape(title)}</h4><table><thead><tr><th>{escape(tr['name'])}</th>"
                f"<th>{escape(tr['type'])}</th><th>{escape(tr['default'])}</th>"
                f"<th>{escape(tr['description'])}</th></tr></thead><tbody>{rows}</tbody></table>")

    def _ports(self, unit) -> str:
        if not unit.ports:
            return ""
        tr = self.tr
        rows = []
        for p in unit.ports:
            port_type = _code(p.type)
            if p.direction == "interface":
                base = p.type.split(".")[0].split()[0] if p.type else ""
                if base in self.index:
                    port_type = self.link(base) + (_code(p.type[len(base):]) if p.type[len(base):] else "")
            rows.append(f'<tr id="{self._row_id(unit, "port", p.name)}"{"" if p.description else " class=missing"}>'
                        f"<td>{_code(p.name)}</td><td>{escape(p.direction)}</td><td>{port_type}</td>"
                        f'<td class="desc">{prose(p.description)}</td></tr>')
        return (f"<h4>{escape(tr['ports'])}</h4><table><thead><tr><th>{escape(tr['name'])}</th>"
                f"<th>{escape(tr['direction'])}</th><th>{escape(tr['type'])}</th>"
                f"<th>{escape(tr['description'])}</th></tr></thead><tbody>{''.join(rows)}</tbody></table>")

    def _modports(self, unit) -> str:
        if not unit.modports:
            return ""
        tr = self.tr
        rows = "".join(
            f'<tr id="{self._row_id(unit, "modport", m.name)}"><td>{_code(m.name)}</td><td>'
            + ", ".join(_code(f"{p.direction} {p.name}".strip()) for p in m.ports)
            + f'</td><td class="desc">{prose(m.description)}</td></tr>' for m in unit.modports)
        return (f"<h4>{escape(tr['modports'])}</h4><table><thead><tr><th>{escape(tr['name'])}</th>"
                f"<th>{escape(tr['ports'])}</th><th>{escape(tr['description'])}</th></tr></thead>"
                f"<tbody>{rows}</tbody></table>")

    def _instances(self, unit) -> str:
        if not unit.instances:
            return ""
        tr = self.tr
        rows = []
        for inst in unit.instances:
            target = self.link(inst.module)
            if not inst.resolved:
                target += f' <span class="badge">{escape(tr["external"])}</span>'
            overrides = ", ".join(_code(f"{c.formal}={c.actual}" if c.formal else c.actual) for c in inst.parameters)
            rows.append(f"<tr><td>{_code(inst.name + inst.array)}</td><td>{target}</td><td>{overrides}</td>"
                        f'<td class="desc">{prose(inst.description)}</td><td>{self.where(unit, inst.line)}</td></tr>')
        return (f"<h4>{escape(tr['instances'])}</h4><table><thead><tr><th>{escape(tr['instance'])}</th>"
                f"<th>{escape(tr['module'])}</th><th>{escape(tr['overrides'])}</th>"
                f"<th>{escape(tr['description'])}</th><th>{escape(tr['line'])}</th></tr></thead>"
                f"<tbody>{''.join(rows)}</tbody></table>")

    def _members(self, unit) -> str:
        if not unit.members:
            return ""
        tr = self.tr
        items = []
        for m in unit.members:
            items.append(f'<dt id="{self._row_id(unit, m.kind, m.name)}">'
                         f'<span class="badge">{escape(tr["kind_names"].get(m.kind, m.kind))}</span> '
                         f'{escape(m.name)} <small>{self.where(unit, m.line)}</small></dt>'
                         f"<dd><pre><code>{escape(m.signature)}</code></pre>{prose(m.description)}</dd>")
        return f'<h4>{escape(tr["members"])}</h4><dl class="members">{"".join(items)}</dl>'

    def render(self) -> str:
        tr = self.tr
        dark = HtmlFormatter(style="github-dark" if _has_style("github-dark") else "monokai")
        light = HtmlFormatter(style="friendly")
        css = (_asset("doxnet.css") + "\n" + light.get_style_defs(':root:not([data-theme="dark"]) .highlight')
               + "\n" + dark.get_style_defs(':root[data-theme="dark"] .highlight'))
        title = escape(self.project.title)
        return (
            f'<!doctype html>\n<html lang="{escape(self.language, quote=True)}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="generator" content="DoxNet {escape(__version__, quote=True)}">'
            f"<title>{title}</title><script>{_THEME_INIT}</script><style>{css}</style></head><body>"
            f'<header class="topbar"><button id="menu" aria-label="{escape(tr["menu"], quote=True)}" '
            f'aria-expanded="false">☰</button><span class="title">{title}</span><span class="spacer"></span>'
            f'<input id="search" type="search" aria-label="{escape(tr["search"], quote=True)}" '
            f'placeholder="{escape(tr["search"], quote=True)}"><kbd>/</kbd>'
            f'<button id="theme" aria-label="{escape(tr["theme"], quote=True)}">◐</button></header>'
            f"{self.sidebar()}<main>{self.overview()}{self.hierarchy()}{self.files()}{self.coverage()}"
            f"{self.diagnostics()}<footer>{escape(tr['generated_by'])} {escape(__version__)}</footer></main>"
            f"<script>{_asset('doxnet.js')}</script></body></html>\n")


def _has_style(name: str) -> bool:
    try:
        from pygments.styles import get_style_by_name
        get_style_by_name(name)
        return True
    except ClassNotFound:
        return False


def render_html(project: Project, sources: Dict[str, str], language: str = "en", include_source: bool = True,
                source_url: Optional[str] = None) -> str:
    check_source_url(source_url)
    return _Page(project, sources, language, include_source, source_url).render()
