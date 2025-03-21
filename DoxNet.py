#!/usr/bin/env python3
import os
import re
import argparse
import subprocess
import shutil
from markdown import markdown

def parse_doxygen_comment(comment_lines):
    info = {'brief': '', 'inputs': [], 'outputs': [], 'description': '', 'parameters': [], 'localparams': []}
    cleaned_lines = []
    for line in comment_lines:
        line = line.replace('/**', '').replace('*/', '')
        line = re.sub(r'^(\s*///*\s*|\s*\*+\s*)', '', line)
        cleaned_lines.append(line)
    for line in cleaned_lines:
        if '@brief' in line:
            info['brief'] = line.split('@brief',1)[1].strip()
        elif '@input' in line:
            info['inputs'].append(line.split('@input',1)[1].strip())
        elif '@ouput' in line:
            info['outputs'].append(line.split('@ouput',1)[1].strip())
        elif '@parameter' in line:
            info['parameters'].append(line.split('@parameter',1)[1].strip())
        elif '@localparam' in line:
            info['localparams'].append(line.split('@localparam',1)[1].strip())
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

def generate_markdown(docs, lang, title):
    toc_md = f"# {title}\n\n"
    toc_md += f"## {lang['toc']}\n\n"
    for file_path in sorted(docs.keys()):
        toc_md += f"- **{lang['file']}:** {file_path}\n"
        for doc in docs[file_path]:
            mod = doc.get('module', 'Unknown')
            anchor = f"module-{mod.lower()}"
            toc_md += f"  - [{lang['module']}: {mod}](#{anchor})\n"
    body_md = ""
    for file_path in sorted(docs.keys()):
        body_md += f"## {lang['file']}: {file_path}\n\n"
        for doc in docs[file_path]:
            mod = doc.get('module', 'Unknown')
            anchor = f"module-{mod.lower()}"
            body_md += f"### <a name=\"{anchor}\"></a>{lang['module']}: {mod}\n\n"
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
                    tokens = inp.split(' ', 1)
                    if len(tokens) == 2:
                        body_md += f"- `{tokens[0]}` {tokens[1]}\n"
                    else:
                        body_md += f"- `{inp}`\n"
                body_md += "\n"
            if doc.get('outputs'):
                body_md += f"**{lang['outputs']}:**\n\n"
                for out in doc['outputs']:
                    tokens = out.split(' ', 1)
                    if len(tokens) == 2:
                        body_md += f"- `{tokens[0]}` {tokens[1]}\n"
                    else:
                        body_md += f"- `{out}`\n"
                body_md += "\n"
    return toc_md, body_md

def convert_md_to_html(toc_md, content_md, title):
    toc_html = markdown(toc_md, extensions=['extra', 'nl2br'])
    content_html = markdown(content_md, extensions=['extra', 'nl2br'])
    style = """
    <style>
    body {
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        background-color: #0d1117;
        color: #c9d1d9;
        display: flex;
    }
    .header {
        display: none;
    }
    .sidebar {
        background-color: #161b22;
        width: 250px;
        padding: 20px;
        position: fixed;
        top: 0;
        left: 0;
        height: 100%;
        overflow-y: auto;
        transition: transform 0.3s ease;
    }
    .content {
        margin-left: 300px;
        padding: 20px;
        flex: 1;
    }
    a {
        color: #58a6ff;
        text-decoration: none;
    }
    a:hover {
        text-decoration: underline;
    }
    pre, code {
        background-color: #161b22;
        border-radius: 4px;
        padding: 4px;
    }
    @media (max-width: 768px) {
        .header {
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
        }
        .burger {
            cursor: pointer;
            font-size: 24px;
        }
        .sidebar {
            width: 250px;
            height: calc(100% - 50px);
            position: fixed;
            top: 50px;
            left: 0;
            transform: translateX(-100%);
            transition: transform 0.3s ease;
            z-index: 999;
        }
        .sidebar.active {
            transform: translateX(0);
        }
        .content {
            margin-left: 0;
            padding: 70px 20px 20px 20px;
        }
    }
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
        subprocess.run(["pandoc", md_file, "--wrap=preserve", "-o", pdf_file], check=True)
        print(f"PDF generated: {pdf_file}")
    except subprocess.CalledProcessError as e:
        print("Error generating PDF:", e)

def main():
    parser = argparse.ArgumentParser(description="Doxygen-lite documentation generator for Verilog files.")
    parser.add_argument("--input", "-i", required=True, help="Input directory containing verilog files")
    parser.add_argument("--output", "-o", required=True, help="Output directory for documentation files")
    parser.add_argument("--language", default="en", help="Language for the documentation (en or de)")
    parser.add_argument("--title", default="Project Documentation", help="Title for the documentation")
    args = parser.parse_args()
    translations = {
        "en": {
            "toc": "Table of Contents",
            "file": "File",
            "module": "Module",
            "brief": "Brief",
            "inputs": "Inputs",
            "outputs": "Outputs",
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
            "parameters": "Parameter",
            "localparams": "Lokale Parameter"
        }
    }
    lang = translations.get(args.language, translations["en"])
    input_dir = args.input
    output_dir = args.output
    if not os.path.isdir(input_dir):
        print(f"Input directory '{input_dir}' does not exist.")
        return
    os.makedirs(output_dir, exist_ok=True)
    docs = {}
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.endswith((".v", ".sv")):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, input_dir)
                doc_items = parse_verilog_file(full_path)
                if doc_items:
                    docs[rel_path] = doc_items
    toc_md, body_md = generate_markdown(docs, lang, args.title)
    md_text = toc_md + "\n\n" + body_md
    md_path = os.path.join(output_dir, "documentation.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_text)
    print(f"Markdown documentation generated: {md_path}")
    html_text = convert_md_to_html(toc_md, body_md, args.title)
    html_path = os.path.join(output_dir, "documentation.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_text)
    print(f"HTML documentation generated: {html_path}")
    pdf_path = os.path.join(output_dir, "documentation.pdf")
    convert_md_to_pdf(md_path, pdf_path)

if __name__ == '__main__':
    main()
