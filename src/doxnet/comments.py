"""Parsing of Doxygen-style documentation comments.

The parser is independent of HDL syntax: it turns the text of one comment
into a :class:`DocComment` and leaves it to :mod:`doxnet.parser` to match the
named entries against declarations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional

# Tags that document a named entity: "@port clk Clock input".
ENTRY_TAGS = {
    "port": "port", "input": "port", "output": "port", "inout": "port", "ref": "port",
    "param": "param", "parameter": "parameter", "localparam": "localparam",
    "modport": "modport", "instance": "instance",
}
METADATA_TAGS = {"author": "author", "authors": "author", "version": "version", "since": "since",
                 "date": "date", "copyright": "copyright", "license": "license"}
LIST_TAGS = {"note": "notes", "remark": "notes", "remarks": "notes", "warning": "warnings",
             "attention": "warnings", "todo": "todos", "see": "see", "sa": "see"}
OTHER_TAGS = {"brief", "short", "details", "deprecated", "file"}
KNOWN_TAGS = set(ENTRY_TAGS) | set(METADATA_TAGS) | set(LIST_TAGS) | OTHER_TAGS

_TAG = re.compile(r"^[@\\]([A-Za-z]+)(?:\[([A-Za-z, ]+)\])?(?=\s|$)\s*(.*)$")
_DIRECTION_HINTS = {"in": "input", "out": "output", "in,out": "inout", "inout": "inout"}


@dataclass
class Entry:
    """A named documentation entry such as ``@port clk Clock``."""

    tag: str
    name: str
    text: str
    line: int
    direction: str = ""


@dataclass
class DocComment:
    brief: str = ""
    paragraphs: List[str] = field(default_factory=list)
    entries: List[Entry] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
    lists: Dict[str, List[str]] = field(default_factory=lambda: {k: [] for k in set(LIST_TAGS.values())})
    deprecated: Optional[str] = None
    is_file: bool = False
    unknown_tags: List[tuple] = field(default_factory=list)

    @property
    def description(self) -> str:
        return "\n\n".join(self.paragraphs)

    @property
    def text(self) -> str:
        """Brief and description as one string, used for member comments."""
        return "\n\n".join(part for part in [self.brief] + self.paragraphs if part)

    @property
    def has_content(self) -> bool:
        return bool(self.brief or self.paragraphs or self.entries or self.metadata
                    or any(self.lists.values()) or self.deprecated is not None)

    @property
    def has_tags(self) -> bool:
        return bool(self.brief or self.entries or self.metadata or any(self.lists.values())
                    or self.deprecated is not None)

    def autobrief(self) -> DocComment:
        """Use the first paragraph as brief when no ``@brief`` was given."""
        if not self.brief and self.paragraphs:
            self.brief = self.paragraphs.pop(0)
        return self


def strip_comment(text: str) -> List[str]:
    """Return the content lines of a comment without its delimiters."""
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        for opener in ("/**<", "/*!<", "///<", "//!<", "/**", "/*!", "///", "//!", "//"):
            if line.startswith(opener):
                line = line[len(opener):]
                break
        else:
            if line.startswith("*/"):
                line = line[2:]
            elif line.startswith("*"):
                line = line[1:]
        line = re.sub(r"\*+/\s*$", "", line)
        lines.append(line.rstrip())
    # Common leading indentation is not significant, but relative indentation
    # (nested Markdown lists) is.
    indents = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
    cut = min(indents) if indents else 0
    return [line[cut:] for line in lines]


def parse_comment(text: str, first_line: int = 1) -> DocComment:
    """Parse the raw text of a documentation comment.

    A tag's text continues on the following lines until a blank line or the
    next tag. Untagged paragraphs form the description.
    """
    doc = DocComment()
    current: Optional[str] = None  # where continuation lines go
    target = None
    paragraph: List[str] = []

    def flush_paragraph():
        if paragraph:
            doc.paragraphs.append("\n".join(paragraph).strip())
            paragraph.clear()

    for offset, line in enumerate(strip_comment(text)):
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            current = None
            continue
        m = _TAG.match(stripped)
        if m and m.group(1).lower() in KNOWN_TAGS:
            flush_paragraph()
            tag, hint, value = m.group(1).lower(), (m.group(2) or "").replace(" ", "").lower(), m.group(3).strip()
            current, target = _apply_tag(doc, tag, hint, value, first_line + offset)
            continue
        if m and not stripped.startswith("\\"):
            doc.unknown_tags.append((m.group(1), first_line + offset))
        if current is not None:
            target = _continue(doc, current, target, stripped)
        else:
            paragraph.append(line)
    flush_paragraph()
    return doc


def _apply_tag(doc: DocComment, tag: str, hint: str, value: str, line: int):
    if tag in ("brief", "short"):
        doc.brief = (doc.brief + " " + value).strip() if doc.brief else value
        return "brief", None
    if tag == "details":
        doc.paragraphs.append(value)
        return "details", None
    if tag == "file":
        doc.is_file = True
        return None, None
    if tag == "deprecated":
        doc.deprecated = value
        return "deprecated", None
    if tag in METADATA_TAGS:
        key = METADATA_TAGS[tag]
        doc.metadata[key] = (doc.metadata[key] + ", " + value) if key in doc.metadata else value
        return "metadata", key
    if tag in LIST_TAGS:
        items = doc.lists[LIST_TAGS[tag]]
        items.append(value)
        return "list", items
    name, _, text = value.partition(" ")
    if name.endswith(":"):
        name = name[:-1]
    text = re.sub(r"^\s*(?:-|:)\s*", "", text.strip())
    direction = tag if tag in ("input", "output", "inout", "ref") else _DIRECTION_HINTS.get(hint, "")
    entry = Entry(ENTRY_TAGS[tag], name, text, line, direction)
    doc.entries.append(entry)
    return "entry", entry


def _continue(doc: DocComment, current: str, target, line: str):
    if current == "brief":
        doc.brief = (doc.brief + " " + line).strip()
    elif current == "details":
        doc.paragraphs[-1] = (doc.paragraphs[-1] + "\n" + line).strip()
    elif current == "deprecated":
        doc.deprecated = ((doc.deprecated or "") + " " + line).strip()
    elif current == "metadata":
        doc.metadata[target] = (doc.metadata[target] + " " + line).strip()
    elif current == "list":
        target[-1] = (target[-1] + " " + line).strip()
    elif current == "entry":
        target.text = (target.text + " " + line).strip()
    return target


def parse_doxygen_comment(comment_lines):
    """Legacy (v1/v2) dictionary interface kept for existing scripts."""
    doc = parse_comment("\n".join(comment_lines))
    info = dict(brief=doc.brief, inputs=[], outputs=[], inouts=[], ports=[], description=doc.description,
                parameters=[], localparams=[])
    plural = {"input": "inputs", "output": "outputs", "inout": "inouts"}
    for entry in doc.entries:
        if entry.tag == "port":
            key = plural.get(entry.direction, "ports")
        elif entry.tag in ("parameter", "param"):
            key = "parameters"
        elif entry.tag == "localparam":
            key = "localparams"
        else:
            continue
        info[key].append((entry.name + " " + entry.text).strip())
    return info
