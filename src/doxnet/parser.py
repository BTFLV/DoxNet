"""Parsing of Doxygen-style comments and design units from Verilog/SystemVerilog sources."""
import logging
import re

logger = logging.getLogger("doxnet")

UNIT_KEYWORDS = ("module", "interface", "package")
_UNIT_RE = re.compile(r'\b(' + '|'.join(UNIT_KEYWORDS) + r')\s+(\w+)')


def parse_doxygen_comment(comment_lines):
    info = {
        'brief': '',
        'inputs': [],
        'outputs': [],
        'inouts': [],
        'description': '',
        'parameters': [],
        'localparams': [],
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


def _strip_comments(lines):
    """Blank out comment text so prose inside doc comments can't be mistaken
    for a module/interface/package declaration."""
    out = []
    in_block = False
    for line in lines:
        if in_block:
            if '*/' in line:
                in_block = False
            out.append('')
            continue
        stripped = line.strip()
        if stripped.startswith('/*'):
            if '*/' not in line:
                in_block = True
            out.append('')
            continue
        if stripped.startswith('//'):
            out.append('')
            continue
        out.append(re.sub(r'//.*$', '', line))
    return out


def _find_unit_after(lines, start_idx):
    """Find the next module/interface/package declaration at or after start_idx."""
    j = start_idx
    while j < len(lines):
        m = _UNIT_RE.search(lines[j])
        if m:
            return m.group(1), m.group(2), j
        j += 1
    return None, None, None


def find_all_units(lines):
    """Return every module/interface/package declaration in the file as (kind, name, line_idx)."""
    units = []
    for idx, line in enumerate(lines):
        m = _UNIT_RE.search(line)
        if m:
            units.append((m.group(1), m.group(2), idx))
    return units


def parse_verilog_file(file_path):
    """Parse a single Verilog/SystemVerilog file.

    Returns (documentation, coverage) where documentation is a list of doc-info
    dicts for every documented unit, and coverage is (documented_count, total_count).
    """
    documentation = []
    documented_lines = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except OSError as e:
        logger.error("Could not read %s: %s", file_path, e)
        raise

    code_lines = _strip_comments(lines)
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
            unit_kind, unit_name, unit_line = _find_unit_after(code_lines, i + 1)
            doc_info['module'] = unit_name if unit_name else 'Unknown'
            doc_info['unit_kind'] = unit_kind if unit_kind else 'module'
            documentation.append(doc_info)
            if unit_line is not None:
                documented_lines.add(unit_line)
        elif re.match(r'\s*///', lines[i]):
            comment_lines = []
            while i < len(lines) and re.match(r'\s*///', lines[i]):
                comment_lines.append(lines[i].strip())
                i += 1
            doc_info = parse_doxygen_comment(comment_lines)
            unit_kind, unit_name, unit_line = _find_unit_after(code_lines, i)
            doc_info['module'] = unit_name if unit_name else 'Unknown'
            doc_info['unit_kind'] = unit_kind if unit_kind else 'module'
            documentation.append(doc_info)
            if unit_line is not None:
                documented_lines.add(unit_line)
        else:
            i += 1

    all_units = find_all_units(code_lines)
    total = len(all_units)
    documented = sum(1 for _, _, idx in all_units if idx in documented_lines)
    undocumented = [name for kind, name, idx in all_units if idx not in documented_lines]
    return documentation, (documented, total, undocumented)


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
    return f"- `{line.strip()}`\n"
