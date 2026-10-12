"""Markdown, HTML, JSON and optional PDF output from DoxNet's typed project model."""
from collections import defaultdict
from html import escape
import json
import logging
import re
import shutil
import subprocess
from urllib.parse import quote, urlsplit

import bleach
from markdown import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

logger = logging.getLogger("doxnet")

TRANSLATIONS = {
    "en": {"files": "Files", "parameters": "Parameters", "localparams": "Local parameters",
           "ports": "Ports", "name": "Name", "direction": "Direction", "type": "Type / width",
           "default": "Default", "description": "Description", "source": "Source code",
           "undocumented": "Undocumented", "coverage": "Documentation coverage",
           "search": "Search design units..."},
    "de": {"files": "Dateien", "parameters": "Parameter", "localparams": "Lokale Parameter",
           "ports": "Ports", "name": "Name", "direction": "Richtung", "type": "Typ / Breite",
           "default": "Standardwert", "description": "Beschreibung", "source": "Quelltext",
           "undocumented": "Undokumentiert", "coverage": "Dokumentationsabdeckung",
           "search": "Design-Units suchen..."},
}

_ALLOWED_TAGS = ["a", "p", "div", "span", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li",
                 "strong", "em", "code", "pre", "blockquote", "table", "thead", "tbody", "tr", "td", "th",
                 "br", "hr", "del", "sup", "sub"]
_ALLOWED_ATTRS = {"*": ["class", "id"], "a": ["href", "title"]}


def _safe_md(s):
    """Escape raw HTML and Markdown table delimiters while retaining Markdown formatting."""
    return escape(s or "", quote=False).replace("|", r"\|")


def _code(s):
    """Inline code using HTML escaping rather than user-controlled backtick fences."""
    return "<code>" + escape(s or "", quote=False) + "</code>"


def _id(unit):
    slug = re.sub(r"[^a-z0-9-]+", "-", (unit.file + "-" + unit.kind + "-" + unit.name).lower()).strip("-")
    return "unit-" + slug + "-" + str(unit.line)


def _table(headers, rows):
    if not rows:
        return ""
    return "| " + " | ".join(headers) + " |\n| " + " | ".join(["---"] * len(headers)) + " |\n" + "\n".join(
        "| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |" for row in rows) + "\n\n"


def _unit_md(unit, lang):
    tr = TRANSLATIONS[lang]
    md = f"### {unit.kind.capitalize()}: {_code(unit.name)}\n\n"
    if not unit.documented:
        md += f"*{tr['undocumented']}*\n\n"
    if unit.brief:
        md += f"**{_safe_md(unit.brief)}**\n\n"
    if unit.description:
        md += _safe_md(unit.description).replace("\n", "  \n") + "\n\n"
    if unit.parameters:
        md += f"#### {tr['parameters']}\n\n"
        md += _table([tr['name'], tr['type'], tr['default'], tr['description']], [
            [_code(p.name), _code(p.type), _code(p.default), _safe_md(p.description)] for p in unit.parameters])
    if unit.localparams:
        md += f"#### {tr['localparams']}\n\n"
        md += _table([tr['name'], tr['type'], tr['default'], tr['description']], [
            [_code(p.name), _code(p.type), _code(p.default), _safe_md(p.description)] for p in unit.localparams])
    if unit.ports:
        md += f"#### {tr['ports']}\n\n"
        md += _table([tr['name'], tr['direction'], tr['type'], tr['description']], [
            [_code(p.name), _safe_md(p.direction), _code(p.type), _safe_md(p.description)] for p in unit.ports])
    return md


def _source_fence(source):
    # Avoid early termination when an HDL string contains a Markdown code fence.
    longest = max((len(m.group()) for m in re.finditer(r"`+", source)), default=0)
    fence = "`" * max(3, longest + 1)
    return fence + "systemverilog\n" + source.rstrip("\n") + "\n" + fence + "\n\n"


def render_markdown(project, sources, language="en", include_source=True):
    tr = TRANSLATIONS[language]
    lines = ["# " + _safe_md(project.title), "", "## " + tr["files"], ""]
    grouped = defaultdict(list)
    for unit in project.units:
        grouped[unit.file].append(unit)
    for filename in project.files:
        lines.append("- " + _code(filename))
        for unit in grouped.get(filename, []):
            lines.append("  - " + unit.kind + " " + _code(unit.name))
    lines.append("")
    cov = project.coverage()
    for key in ("units", "ports", "parameters"):
        item = cov[key]
        value = "N/A" if item["percent"] is None else f"{item['percent']:.1f}%"
        lines.append(f"**{key.capitalize()}:** {item['documented']}/{item['total']} ({value})  ")
    lines.append("")
    for filename in project.files:
        lines.extend(["## " + tr["files"] + ": " + _code(filename), ""])
        for unit in grouped.get(filename, []):
            lines.append(_unit_md(unit, language))
        if include_source and filename in sources:
            lines.extend(["### " + tr["source"], "", _source_fence(sources[filename])])
    return "\n".join(lines) + "\n"


def _highlight(code):
    try:
        lexer = get_lexer_by_name("systemverilog")
    except ClassNotFound:
        lexer = get_lexer_by_name("verilog")
    return highlight(code, lexer, HtmlFormatter(cssclass="highlight"))


def _safe_fragment(md):
    html = markdown(md, extensions=["tables", "fenced_code", "sane_lists"])
    return bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS,
                        protocols=["http", "https", "mailto"], strip=True)


def _source_link(source_url, unit):
    if not source_url:
        return ""
    parsed = urlsplit(source_url)
    if (parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        raise ValueError("--source-url must be an HTTPS base URL without credentials, query or fragment")
    url = source_url.rstrip("/") + "/" + quote(unit.file.replace("\\", "/"), safe="/") + f"#L{unit.line}"
    return f'<a class="source-link" href="{escape(url, quote=True)}">{escape(unit.file)}:{unit.line}</a>'


def render_html(project, sources, language="en", include_source=True, source_url=None):
    tr = TRANSLATIONS[language]
    groups = defaultdict(list)
    for unit in project.units:
        groups[unit.file].append(unit)
    nav, content = [], []
    for filename in project.files:
        nav.append(f'<li class="nav-file">{escape(filename)}</li>')
        for unit in groups.get(filename, []):
            uid = _id(unit)
            nav.append(f'<li><a href="#{uid}">{escape(unit.kind)} {escape(unit.name)}</a></li>')
            description = _safe_fragment(_unit_md(unit, language))
            source_link = _source_link(source_url, unit)
            content.append(f'<article class="design-unit" id="{uid}" data-search="{escape((unit.kind + " " + unit.name + " " + filename).lower(), quote=True)}">'
                           f'{description}<div class="source-ref">{source_link or escape(filename) + ":" + str(unit.line)}</div></article>')
        if include_source and filename in sources:
            code = _highlight(sources[filename])
            content.append(f'<details class="source"><summary>{escape(tr["source"])} – {escape(filename)}</summary>{code}</details>')
    dark_css = HtmlFormatter(style="monokai").get_style_defs('[data-theme="dark"] .highlight')
    light_css = HtmlFormatter(style="friendly").get_style_defs('[data-theme="light"] .highlight')
    cov = project.coverage()
    summary = " · ".join(f'{key}: {value["documented"]}/{value["total"]}'
                         for key, value in cov.items())
    title = escape(project.title)
    styles = """
:root{--bg:#0d1117;--panel:#161b22;--fg:#d1d8df;--link:#79c0ff;--border:#30363d;--muted:#89939e}
[data-theme=light]{--bg:#fff;--panel:#f6f8fa;--fg:#24292f;--link:#0969da;--border:#d0d7de;--muted:#57606a}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.65 system-ui,sans-serif}
a{color:var(--link)}header{position:sticky;top:0;z-index:4;display:flex;align-items:center;gap:1rem;padding:.7rem 1rem;background:var(--panel);border-bottom:1px solid var(--border)}
header strong{font-size:1.05rem}button,input{border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--fg);padding:.5rem}button{cursor:pointer}
#search{min-width:9rem;flex:1;max-width:25rem}#menu{display:none}aside{position:fixed;top:60px;bottom:0;width:260px;overflow:auto;padding:1rem;background:var(--panel);border-right:1px solid var(--border)}
aside ul{padding-left:1.1rem;list-style:none}aside li{padding:.15rem 0}.nav-file{font-weight:700;margin-top:.8rem;overflow-wrap:anywhere}
main{margin-left:260px;padding:2rem;max-width:1200px}article{padding:1rem 0 1.8rem;border-bottom:1px solid var(--border);scroll-margin-top:80px}
article[hidden]{display:none}h3{font-size:1.4rem}h3,h4{margin-bottom:.4rem}table{border-collapse:collapse;width:100%;display:block;overflow-x:auto}td,th{padding:.45rem .8rem;border:1px solid var(--border);text-align:left}th{background:var(--panel)}
code{background:var(--panel);padding:.1rem .3rem;border-radius:3px}pre{overflow:auto}pre code{background:none}.source{margin:1rem 0;border:1px solid var(--border);border-radius:8px;padding:1rem}
.source summary{cursor:pointer}.source .highlight{margin-top:1rem;overflow:auto}.source .highlight pre{padding:.8rem;overflow:auto}.source-ref{font-size:.85rem;color:var(--muted)}.metrics{color:var(--muted);font-size:.85rem;margin-bottom:1rem}
@media(max-width:800px){#menu{display:inline-block}aside{transform:translateX(-110%);transition:transform .2s;z-index:3;width:min(85vw,290px)}aside.open{transform:translateX(0)}main{margin-left:0;padding:1rem}header{flex-wrap:wrap}#search{min-width:30%}}
"""
    js = """
(function(){
  var root=document.documentElement;
  try{root.dataset.theme=localStorage.getItem('doxnet-theme')||(matchMedia('(prefers-color-scheme: light)').matches?'light':'dark');}catch(e){root.dataset.theme='dark'}
  document.getElementById('theme').addEventListener('click',function(){root.dataset.theme=root.dataset.theme==='dark'?'light':'dark';try{localStorage.setItem('doxnet-theme',root.dataset.theme)}catch(e){}});
  document.getElementById('menu').addEventListener('click',function(){var a=document.querySelector('aside');a.classList.toggle('open');this.setAttribute('aria-expanded',a.classList.contains('open'))});
  document.getElementById('search').addEventListener('input',function(){var q=this.value.toLowerCase().trim();document.querySelectorAll('.design-unit').forEach(function(a){a.hidden=!a.dataset.search.includes(q)})});
  document.querySelectorAll('aside a').forEach(function(a){a.addEventListener('click',function(){document.querySelector('aside').classList.remove('open')})});
})();
"""
    return (f'<!doctype html>\n<html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{title}</title><style>{styles}\n{dark_css}\n{light_css}</style></head><body>'
            f'<header><button id="menu" aria-label="Menu" aria-expanded="false">☰</button><strong>{title}</strong>'
            f'<input id="search" type="search" aria-label="Search" placeholder="{escape(tr["search"], quote=True)}">'
            f'<button id="theme" aria-label="Toggle light/dark theme">◐</button></header>'
            f'<aside aria-label="Navigation"><ul>{"".join(nav)}</ul></aside>'
            f'<main><h1>{title}</h1><p class="metrics">{escape(tr["coverage"])}: {escape(summary)}</p>{"".join(content)}</main>'
            f'<script>{js}</script></body></html>\n')


def render_json(project):
    return json.dumps(project.as_dict(), indent=2, ensure_ascii=False) + "\n"


def convert_md_to_pdf(md_file, pdf_file):
    if shutil.which("pandoc") is None:
        logger.warning("Pandoc is not installed; optional PDF generation skipped")
        return False
    try:
        subprocess.run(["pandoc", str(md_file), "--wrap=preserve", "-V", "geometry:margin=0.7in",
                        "-o", str(pdf_file)], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        logger.error("PDF generation failed: %s", exc)
        return False
    return True
