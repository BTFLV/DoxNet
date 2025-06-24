#!/usr/bin/env python3
import os
import re
import argparse
import subprocess
import shutil
import json
from markdown import markdown
from pygments.formatters import HtmlFormatter

def parse_doxygen_comment(comment_lines):
    info = {
        'brief': '',
        'inputs': [],
        'outputs': [],
        'inouts': [],
        'description': '',
        'parameters': [],
        'localparams': []
    }
    cleaned_lines = []
    for line in comment_lines:
        line = line.replace('/**', '').replace('*/', '')
        line = re.sub(r'^(\s*///*\s*|\s*\*+\s*)', '', line)
        cleaned_lines.append(line)
    for line in cleaned_lines:
        if '@brief' in line:
            info['brief'] = line.split('@brief', 1)[1].strip()
        elif '@input' in line:
            info['inputs'].append(line.split('@input', 1)[1].strip())
        elif '@output' in line:
            info['outputs'].append(line.split('@output', 1)[1].strip())
        elif '@inout' in line:
            info['inouts'].append(line.split('@inout', 1)[1].strip())
        elif '@parameter' in line:
            info['parameters'].append(line.split('@parameter', 1)[1].strip())
        elif '@localparam' in line:
            info['localparams'].append(line.split('@localparam', 1)[1].strip())
        else:
            info['description'] += line + " "
    info['description'] = info['description'].strip()
    return info

def parse_verilog_file(file_path):
    documentation = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return documentation
    i = 0
    while i < len(lines):
        if re.match(r'\s*/\*\*', lines[i]):
            comment_lines = []
            while i < len(lines) and "*/" not in lines[i]:
                comment_lines.append(lines[i].strip())
                i += 1
            if i < len(lines):
                comment_lines.append(lines[i].strip())
            doc_info = parse_doxygen_comment(comment_lines)
            j = i + 1
            module_name = None
            while j < len(lines):
                if "module" in lines[j]:
                    m = re.search(r'\bmodule\s+(\w+)', lines[j])
                    if m:
                        module_name = m.group(1)
                        break
                j += 1
            doc_info['module'] = module_name if module_name else 'Unknown'
            documentation.append(doc_info)
        elif re.match(r'\s*///', lines[i]):
            comment_lines = []
            while i < len(lines) and re.match(r'\s*///', lines[i]):
                comment_lines.append(lines[i].strip())
                i += 1
            doc_info = parse_doxygen_comment(comment_lines)
            j = i
            module_name = None
            while j < len(lines):
                if "module" in lines[j]:
                    m = re.search(r'\bmodule\s+(\w+)', lines[j])
                    if m:
                        module_name = m.group(1)
                        break
                j += 1
            doc_info['module'] = module_name if module_name else 'Unknown'
            documentation.append(doc_info)
        else:
            i += 1
    return documentation

def remove_doxnet_comments(code):
    code = re.sub(r'/\*\*.*?\*/', '', code, flags=re.DOTALL)
    code = re.sub(r'^\s*///.*$', '', code, flags=re.MULTILINE)
    return code

def format_port_line(line):
    match = re.match(r'^\s*(?P<decl>.*?)\s+(?P<desc>[A-Z].*)$', line)
    if match:
        declaration = match.group('decl').strip()
        description = match.group('desc').strip()
        return f"- `{declaration}` {description}\n"
    else:
        return f"- `{line.strip()}`\n"

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
        except Exception as e:
            body_md += f"*Error reading source code for {file_path}: {e}*\n\n"
    return toc_md, body_md

def convert_md_to_html(toc_md, content_md, title):
    pygments_css = HtmlFormatter(style="monokai").get_style_defs('.codehilite')
    
    extensions = ['extra', 'nl2br', 'codehilite', 'toc', 'attr_list']
    toc_html = markdown(toc_md, extensions=extensions)
    content_html = markdown(content_md, extensions=extensions)
    
    style = f"""
    <style>
    body {{
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        background-color: #0d1117;
        color: #c9d1d9;
        display: flex;
    }}
    .header {{
        display: none;
    }}
    .sidebar {{
        background-color: #161b22;
        width: 250px;
        padding: 20px;
        position: fixed;
        top: 0;
        left: 0;
        height: 100%;
        overflow-y: auto;
        transition: transform 0.3s ease;
    }}
    .content {{
        margin-left: 300px;
        padding: 20px;
        flex: 1;
    }}
    a {{
        color: #58a6ff;
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
        background-color: #272822;
        border-radius: 3px;
        padding: 0.2em 0.4em;
        display: inline-block;
    }}
    {pygments_css}
    @media (max-width: 768px) {{
        .header {{
            display: flex;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 50px;
            background-color: #161b22;
            color: #c9d1d9;
            align-items: center;
            padding: 0 15px;
            z-index: 1000;
        }}
        .burger {{
            cursor: pointer;
            font-size: 24px;
        }}
        .sidebar {{
            width: 250px;
            height: calc(100% - 50px);
            position: fixed;
            top: 50px;
            left: 0;
            transform: translateX(-100%);
            transition: transform 0.3s ease;
            z-index: 999;
        }}
        .sidebar.active {{
            transform: translateX(0);
        }}
        .content {{
            margin-left: 0;
            padding: 70px 20px 20px 20px;
        }}
    }}
    </style>
    """
    script = """
    <script>
    function toggleSidebar() {
        var sidebar = document.getElementById('sidebar');
        sidebar.classList.toggle('active');
    }
    document.addEventListener("DOMContentLoaded", function () {
        var links = document.querySelectorAll(".sidebar a");
        links.forEach(function (link) {
            link.addEventListener("click", function () {
                var sidebar = document.getElementById('sidebar');
                if (window.innerWidth <= 768) {
                    sidebar.classList.remove('active');
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
    <div class="title" style="flex: 1; text-align: center; font-size: 18px;">{title}</div>
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
        print("Pandoc is not installed or not found in PATH. Skipping PDF generation.")
        return
    try:
        subprocess.run(["pandoc", md_file, "--wrap=preserve", "-V", "geometry:margin=0.5in", "-o", pdf_file], check=True)
        print(f"PDF generated: {pdf_file}")
    except subprocess.CalledProcessError as e:
        print("Error generating PDF:", e)

def main():
    parser = argparse.ArgumentParser(description="Doxygen-lite documentation generator for Verilog files.")
    parser.add_argument("--input", "-i", help="Input directory containing verilog files")
    parser.add_argument("--output", "-o", required=True, help="Output directory for documentation files")
    parser.add_argument("--language", default="en", help="Language for the documentation (en or de)")
    parser.add_argument("--title", default="Project Documentation", help="Title for the documentation")
    parser.add_argument("--html-file", default="documentation.html", help="Output HTML filename")
    parser.add_argument("--md-file", default="documentation.md", help="Output Markdown filename")
    parser.add_argument("--pdf-file", default="documentation.pdf", help="Output PDF filename")
    parser.add_argument("--config", help="Optional JSON configuration file")
    args = parser.parse_args()

    if args.config:
        try:
            with open(args.config, 'r', encoding='utf-8') as cf:
                config = json.load(cf)
            if "title" in config:
                args.title = config["title"]
            if "language" in config:
                args.language = config["language"]
            if "html_file" in config:
                args.html_file = config["html_file"]
            if "md_file" in config:
                args.md_file = config["md_file"]
            if "pdf_file" in config:
                args.pdf_file = config["pdf_file"]
            file_list = config.get("files", None)
        except Exception as e:
            print(f"Error loading config file: {e}")
            file_list = None
    else:
        file_list = None

    translations = {
        "en": {
            "toc": "Table of Contents",
            "file": "File",
            "module": "Module",
            "brief": "Brief",
            "inputs": "Inputs",
            "outputs": "Outputs",
            "inouts": "Inouts",
            "parameters": "Parameters",
            "localparams": "Local Parameters"
        },
        "de": {
            "toc": "Inhaltsverzeichnis",
            "file": "Datei",
            "module": "Modul",
            "brief": "Kurzbeschreibung",
            "inputs": "Eingänge",
            "outputs": "Ausgänge",
            "inouts": "Bidirektionale Signale",
            "parameters": "Parameter",
            "localparams": "Lokale Parameter"
        }
    }
    lang = translations.get(args.language, translations["en"])
    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)
    docs = {}
    if file_list:
        for file_path in file_list:
            if os.path.isfile(file_path):
                doc_items = parse_verilog_file(file_path)
                if doc_items:
                    docs[file_path] = doc_items
            else:
                print(f"Warning: File {file_path} does not exist.")
        base_path = ""
    else:
        if not args.input or not os.path.isdir(args.input):
            print(f"Input directory '{args.input}' does not exist.")
            return
        base_path = args.input
        for root, _, files in os.walk(args.input):
            for file in files:
                if file.endswith((".v", ".sv")):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, args.input)
                    doc_items = parse_verilog_file(full_path)
                    if doc_items:
                        docs[rel_path] = doc_items

    toc_md, body_md = generate_markdown(docs, lang, args.title, base_path)
    md_text = toc_md + "\n\n" + body_md
    md_path = os.path.join(output_dir, args.md_file)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_text)
    print(f"Markdown documentation generated: {md_path}")
    html_text = convert_md_to_html(toc_md, body_md, args.title)
    html_path = os.path.join(output_dir, args.html_file)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_text)
    print(f"HTML documentation generated: {html_path}")
    pdf_path = os.path.join(output_dir, args.pdf_file)
    convert_md_to_pdf(md_path, pdf_path)

if __name__ == '__main__':
    main()
