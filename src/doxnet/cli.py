"""Command-line interface."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys
from typing import Dict, Optional

from . import __version__
from .config import FORMATS, Settings, load_settings
from .render import TRANSLATIONS, convert_md_to_pdf, render_html, render_json, render_markdown
from .sources import collect_project

logger = logging.getLogger("doxnet")
EXIT_OK = 0
EXIT_INPUT_ERROR = 1
EXIT_COVERAGE_FAILED = 2
EXIT_GENERATION_ERROR = 3


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doxnet",
        description="Generate documentation from Verilog/SystemVerilog sources and check its coverage.",
        epilog="Exit codes: 0 ok, 1 input/config error, 2 coverage below threshold, "
               "3 output error or warnings with --fail-on-warnings.")
    inputs = parser.add_argument_group("input")
    inputs.add_argument("--input", "-i", metavar="DIR", help="directory searched recursively for .v/.sv/.vh/.svh")
    inputs.add_argument("--filelist", "-f", metavar="FILE", help="simulator-style filelist (.f)")
    inputs.add_argument("--config", "-c", metavar="FILE", help="config file (.json, .toml or pyproject.toml)")
    inputs.add_argument("--exclude", action="append", metavar="GLOB",
                        help="skip files matching this glob, relative to the input root (repeatable)")
    inputs.add_argument("--encoding", help="source file encoding (default: utf-8)")

    pre = parser.add_argument_group("preprocessing")
    pre.add_argument("-D", "--define", action="append", metavar="NAME[=VALUE]",
                     help="define a macro for `ifdef evaluation (repeatable)")
    pre.add_argument("--incdir", action="append", metavar="DIR", help="search directory for `include (repeatable)")
    pre.add_argument("--no-preprocess", action="store_true",
                     help="do not evaluate `ifdef; every branch is parsed")

    docs = parser.add_argument_group("documentation")
    docs.add_argument("--title")
    docs.add_argument("--language", choices=sorted(TRANSLATIONS))
    docs.add_argument("--top", action="append", metavar="UNIT", help="root of the hierarchy view (repeatable)")
    docs.add_argument("--plain-comments", action="store_true",
                      help="use ordinary // comments after a port or parameter as its description")
    docs.add_argument("--no-source", action="store_true", help="do not embed the RTL source")
    docs.add_argument("--source-url", metavar="URL",
                      help="HTTPS prefix for source links, e.g. https://github.com/org/repo/blob/main")

    out = parser.add_argument_group("output")
    out.add_argument("--output", "-o", metavar="DIR", help="output directory")
    out.add_argument("--formats", metavar="LIST", help=f"comma-separated subset of {','.join(FORMATS)}")
    for key in ("html", "md", "pdf", "json"):
        out.add_argument(f"--{key}-file", dest=f"{key}_file", metavar="NAME")
    out.add_argument("--no-pdf", action="store_true", help="skip the PDF output")
    out.add_argument("--pdf-required", action="store_true", help="fail if the PDF cannot be produced")
    out.add_argument("--check", action="store_true", help="validate only; do not write any output")

    gates = parser.add_argument_group("quality gates")
    gates.add_argument("--min-coverage", type=float, metavar="PCT", help="minimum documented design units")
    gates.add_argument("--min-port-coverage", type=float, metavar="PCT", help="minimum documented ports")
    gates.add_argument("--min-parameter-coverage", type=float, metavar="PCT",
                       help="minimum documented parameters")
    gates.add_argument("--strict", action="store_true", help="require every design unit to be documented")
    gates.add_argument("--fail-on-warnings", action="store_true", help="exit with 3 if there are warnings")
    gates.add_argument("--disable", action="append", metavar="CODE",
                       help="suppress a warning code such as DOC004 (repeatable or comma-separated)")
    gates.add_argument("--diagnostics-format", choices=("text", "github"), default="text",
                       help="'github' prints workflow commands that annotate pull requests")

    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("--version", action="version", version=f"doxnet {__version__}")
    return parser


def configure_logging(verbosity: int, quiet: bool) -> None:
    level = logging.WARNING if quiet else (logging.DEBUG if verbosity >= 2 else logging.INFO)
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", force=True)


def _workspace_path(path: Optional[Path], fallback: str) -> str:
    """Path relative to the working directory, which is the repository root in a CI job."""
    if path is None:
        return fallback
    try:
        return path.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _report(project, settings: Settings, locations: Dict[str, Path]) -> None:
    for diag in project.diagnostics:
        if settings.diagnostics_format == "github":
            message = diag.message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            file = _workspace_path(locations.get(diag.file), diag.file)
            print(f"::{diag.severity} file={file},line={diag.line},title={diag.code}::{message}")
        else:
            log = logger.error if diag.severity == "error" else logger.warning
            log("%s:%d: %s: %s", diag.file, diag.line, diag.code, diag.message)


def _coverage_failed(settings: Settings, project) -> bool:
    minimums = {"units": 100.0 if settings.strict else settings.min_coverage,
                "ports": settings.min_port_coverage, "parameters": settings.min_parameter_coverage}
    failed = False
    for name, item in project.coverage().items():
        value = item["percent"]
        shown = "n/a" if value is None else f"{value:.1f}%"
        logger.info("%s coverage: %d/%d (%s)", name, item["documented"], item["total"], shown)
        minimum = minimums[name]
        if minimum is not None and (value is None or value < minimum):
            logger.error("%s coverage %s is below the required %.1f%%", name, shown, minimum)
            failed = True
    return failed


def _write(settings: Settings, project, sources) -> bool:
    out = settings.output
    out.mkdir(parents=True, exist_ok=True)
    formats = settings.formats
    if "markdown" in formats:
        (out / settings.md_file).write_text(
            render_markdown(project, sources, settings.language, settings.include_source), encoding="utf-8")
    if "html" in formats:
        (out / settings.html_file).write_text(
            render_html(project, sources, settings.language, settings.include_source, settings.source_url),
            encoding="utf-8")
    if "json" in formats:
        (out / settings.json_file).write_text(render_json(project), encoding="utf-8")
    if "pdf" in formats:
        ok = convert_md_to_pdf(out / settings.md_file, out / settings.pdf_file)
        if settings.pdf_required and not ok:
            return False
    return True


def run(args) -> int:
    settings = load_settings(args)
    project, sources, locations = collect_project(settings)
    _report(project, settings, locations)
    # A malformed header would produce a misleading partial interface, so
    # errors stop before anything is written.
    if any(d.severity == "error" for d in project.diagnostics):
        return EXIT_INPUT_ERROR
    if not settings.check and not _write(settings, project, sources):
        return EXIT_GENERATION_ERROR
    if _coverage_failed(settings, project):
        return EXIT_COVERAGE_FAILED
    if settings.fail_on_warnings and project.diagnostics:
        logger.error("%d warning(s) and --fail-on-warnings is set", len(project.diagnostics))
        return EXIT_GENERATION_ERROR
    target = "checked" if settings.check else f"written to {settings.output}"
    logger.info("%d design units in %d files %s", len(project.units), len(project.files), target)
    return EXIT_OK


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    configure_logging(args.verbose, args.quiet)
    try:
        return run(args)
    except (ValueError, OSError, UnicodeError) as exc:  # includes JSON and TOML decode errors
        logger.error("%s", exc)
        return EXIT_INPUT_ERROR


if __name__ == "__main__":
    sys.exit(main())

