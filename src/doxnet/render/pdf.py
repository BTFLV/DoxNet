"""Optional PDF output through Pandoc."""
from __future__ import annotations

import logging
from pathlib import Path
import shutil
import subprocess

logger = logging.getLogger("doxnet")


def convert_md_to_pdf(md_file: Path, pdf_file: Path) -> bool:
    """Convert the Markdown output with Pandoc. Returns False instead of raising."""
    if shutil.which("pandoc") is None:
        logger.warning("Pandoc is not installed; PDF output skipped")
        return False
    command = ["pandoc", str(md_file), "--from=gfm", "--wrap=preserve", "-V", "geometry:margin=0.7in",
               "-o", str(pdf_file)]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        logger.error("PDF generation failed: %s", (exc.stderr or str(exc)).strip())
        return False
    except OSError as exc:
        logger.error("PDF generation failed: %s", exc)
        return False
    return True
