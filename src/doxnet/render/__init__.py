"""Output formats. Every renderer takes a linked :class:`~doxnet.model.Project`."""
from .html import render_html
from .i18n import TRANSLATIONS
from .json import render_json
from .markdown import render_markdown
from .pdf import convert_md_to_pdf

__all__ = ["TRANSLATIONS", "convert_md_to_pdf", "render_html", "render_json", "render_markdown"]
