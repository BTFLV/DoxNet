"""Rendering of parsed documentation into Markdown, HTML and PDF."""
import logging
import os
import shutil
import subprocess

from markdown import markdown
from pygments.formatters import HtmlFormatter

logger = logging.getLogger("doxnet")


def generate_markdown(docs, lang, title, base_path):
    toc_md = f"# {title}\n\n"
    toc_md += f"## {lang['toc']}\n\n"
    for file_path in sorted(docs.keys()):
        file_anchor = f"file-{file_path.lower().replace('/', '-').replace('.', '-').replace('_', '-')}"
        toc_md += f"- **[{lang['file']}: {file_path}](#{file_anchor})**\n"
        for doc in docs[file_path]:
            mod = doc.get('module', 'Unknown')
            if mod != 'Unknown':
                anchor = f"module-{mod.lower()}"
                toc_md += f"  - [{lang['module']}: {mod}](#{anchor})\n"
    body_md = ""
    for file_path in sorted(docs.keys()):
        file_anchor = f"file-{file_path.lower().replace('/', '-').replace('.', '-').replace('_', '-')}"
        body_md += f"## {lang['file']}: {file_path} {{#{file_anchor}}}\n\n"
        for doc in docs[file_path]:
            mod = doc.get('module', 'Unknown')
            if mod != 'Unknown':
                anchor = f"module-{mod.lower()}"
                body_md += f"### {lang['module']}: {mod} {{#{anchor}}}\n\n"
            if doc.get('brief'):
                body_md += f"**{lang['brief']}:** {doc.get('brief', '')}\n\n"
            if doc.get('description'):
                body_md += f"{doc['description']}\n\n"
            if doc.get('parameters'):
                body_md += f"**{lang['parameters']}:**\n\n"
                for par in doc['parameters']:
                    tokens = par.split(' ', 1)
                    if len(tokens) == 2:
                        body_md += f"- `{tokens[0]}` {tokens[1]}\n"
                    else:
                        body_md += f"- `{par}`\n"
                body_md += "\n"
            if doc.get('localparams'):
                body_md += f"**{lang['localparams']}:**\n\n"
                for lpar in doc['localparams']:
                    tokens = lpar.split(' ', 1)
                    if len(tokens) == 2:
                        body_md += f"- `{tokens[0]}` {tokens[1]}\n"
                    else:
                        body_md += f"- `{lpar}`\n"
                body_md += "\n"
            if doc.get('inputs'):
                body_md += f"**{lang['inputs']}:**\n\n"
                for inp in doc['inputs']:
                    body_md += format_port_line(inp)
                body_md += "\n"
            if doc.get('outputs'):
                body_md += f"**{lang['outputs']}:**\n\n"
                for out in doc['outputs']:
                    body_md += format_port_line(out)
                body_md += "\n"
            if doc.get('inouts'):
                body_md += f"**{lang['inouts']}:**\n\n"
                for io in doc['inouts']:
                    body_md += format_port_line(io)
                body_md += "\n"
        full_path = os.path.join(base_path, file_path)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                code = f.read()
            code = remove_doxnet_comments(code)
            body_md += "<details>\n<summary>Source Code</summary>\n\n"
            body_md += "```verilog\n" + code + "\n```\n"
            body_md += "</details>\n\n"
        except OSError as e:
            logger.warning("Could not embed source for %s: %s", file_path, e)
            body_md += f"*Error reading source code for {file_path}: {e}*\n\n"
    return toc_md, body_md


# local imports kept here to avoid a circular import at module load time
from .parser import remove_doxnet_comments, format_port_line  # noqa: E402


def convert_md_to_html(toc_md, content_md, title):
    dark_css = HtmlFormatter(style="monokai").get_style_defs('[data-theme="dark"] .codehilite')
    light_css = HtmlFormatter(style="friendly").get_style_defs('[data-theme="light"] .codehilite')

    extensions = ['extra', 'nl2br', 'codehilite', 'toc', 'attr_list']
    toc_html = markdown(toc_md, extensions=extensions)
    content_html = markdown(content_md, extensions=extensions)

    style = f"""
    <style>
    :root {{
        --bg: #0d1117;
        --bg-alt: #161b22;
        --fg: #c9d1d9;
        --link: #58a6ff;
        --code-bg: #272822;
        --border: #30363d;
    }}
    [data-theme="light"] {{
        --bg: #ffffff;
        --bg-alt: #f6f8fa;
        --fg: #24292f;
        --link: #0969da;
        --code-bg: #f6f8fa;
        --border: #d0d7de;
    }}
    body {{
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        background-color: var(--bg);
        color: var(--fg);
        display: flex;
    }}
    .header {{
        display: flex;
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 50px;
        background-color: var(--bg-alt);
        border-bottom: 1px solid var(--border);
        color: var(--fg);
        align-items: center;
        padding: 0 15px;
        z-index: 1000;
    }}
    .header .title {{
        flex: 1;
        font-size: 16px;
        font-weight: 600;
    }}
    .theme-toggle {{
        cursor: pointer;
        background: none;
        border: 1px solid var(--border);
        border-radius: 6px;
        color: var(--fg);
        padding: 4px 10px;
        font-size: 14px;
    }}
    .burger {{
        cursor: pointer;
        font-size: 24px;
        margin-right: 10px;
        display: none;
    }}
    .sidebar {{
        background-color: var(--bg-alt);
        border-right: 1px solid var(--border);
        width: 250px;
        padding: 20px;
        position: fixed;
        top: 50px;
        left: 0;
        height: calc(100% - 50px);
        overflow-y: auto;
        transition: transform 0.3s ease;
    }}
    .content {{
        margin-left: 250px;
        padding: 70px 20px 20px 20px;
        flex: 1;
        min-width: 0;
    }}
    a {{
        color: var(--link);
        text-decoration: none;
    }}
    a:hover {{
        text-decoration: underline;
    }}
    .codehilite pre {{
        border-radius: 4px;
        padding: 0.3em 0.6em;
        overflow-x: auto;
    }}
    code {{
        background-color: var(--code-bg);
        border-radius: 3px;
        padding: 0.2em 0.4em;
        display: inline-block;
    }}
    {dark_css}
    {light_css}
    @media (max-width: 768px) {{
        .burger {{
            display: inline-block;
        }}
        .sidebar {{
            width: 250px;
            transform: translateX(-100%);
            transition: transform 0.3s ease;
            z-index: 999;
        }}
        .sidebar.active {{
            transform: translateX(0);
        }}
        .content {{
            margin-left: 0;
        }}
    }}
    </style>
    """
    script = """
    <script>
    (function () {
        var stored = null;
        try { stored = localStorage.getItem('doxnet-theme'); } catch (e) {}
        var preferred = stored || (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
        document.documentElement.setAttribute('data-theme', preferred);
    })();
    function toggleSidebar() {
        document.getElementById('sidebar').classList.toggle('active');
    }
    function toggleTheme() {
        var current = document.documentElement.getAttribute('data-theme');
        var next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        try { localStorage.setItem('doxnet-theme', next); } catch (e) {}
    }
    document.addEventListener("DOMContentLoaded", function () {
        var links = document.querySelectorAll(".sidebar a");
        links.forEach(function (link) {
            link.addEventListener("click", function () {
                if (window.innerWidth <= 768) {
                    document.getElementById('sidebar').classList.remove('active');
                }
            });
        });
    });
    </script>
    """
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
{style}
</head>
<body>
<div class="header">
    <span class="burger" onclick="toggleSidebar()">&#9776;</span>
    <div class="title">{title}</div>
    <button class="theme-toggle" onclick="toggleTheme()" aria-label="Toggle theme">&#9788;/&#9790;</button>
</div>
<div class="sidebar" id="sidebar">
{toc_html}
</div>
<div class="content">
{content_html}
</div>
{script}
</body>
</html>
"""
    return html


def convert_md_to_pdf(md_file, pdf_file):
    if shutil.which("pandoc") is None:
        logger.warning("Pandoc is not installed or not found in PATH. Skipping PDF generation.")
        return False
    try:
        subprocess.run(
            ["pandoc", md_file, "--wrap=preserve", "-V", "geometry:margin=0.5in", "-o", pdf_file],
            check=True,
        )
        logger.info("PDF generated: %s", pdf_file)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Error generating PDF: %s", e)
        return False
