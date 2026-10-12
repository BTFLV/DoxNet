"""Command-line interface and project orchestration for DoxNet."""
import argparse
import fnmatch
import json
import logging
from pathlib import Path
import sys
from urllib.parse import urlsplit

from . import __version__
from .model import Project
from .parser import parse_file
from .render import TRANSLATIONS, convert_md_to_pdf, render_html, render_json, render_markdown

logger = logging.getLogger("doxnet")
EXIT_OK = 0
EXIT_INPUT_ERROR = 1
EXIT_COVERAGE_FAILED = 2
EXIT_GENERATION_ERROR = 3
EXTENSIONS = {".v", ".sv", ".vh", ".svh"}

DEFAULTS = {
    "title": "Project Documentation",
    "language": "en",
    "html_file": "documentation.html",
    "md_file": "documentation.md",
    "pdf_file": "documentation.pdf",
    "json_file": "documentation.json",
    "min_coverage": None,
    "min_port_coverage": None,
    "min_parameter_coverage": None,
    "source_url": None,
}


def build_arg_parser():
    parser = argparse.ArgumentParser(prog="doxnet", description="HDL documentation and interface validation")
    parser.add_argument("--input", "-i", help="Root directory with Verilog/SystemVerilog sources")
    parser.add_argument("--output", "-o", required=True, help="Directory for generated documents")
    parser.add_argument("--config", help="JSON configuration file")
    parser.add_argument("--filelist", help="Filelist (.f) with paths, one per line")
    parser.add_argument("--exclude", action="append", default=None, help="Exclude glob relative to input (repeatable)")
    parser.add_argument("--title")
    parser.add_argument("--language", choices=sorted(TRANSLATIONS))
    for key in ("html", "md", "pdf", "json"):
        parser.add_argument(f"--{key}-file", dest=f"{key}_file")
    parser.add_argument("--no-pdf", action="store_true", help="Do not call Pandoc")
    parser.add_argument("--pdf-required", action="store_true", help="Fail when Pandoc cannot generate PDF")
    parser.add_argument("--no-source", action="store_true", help="Do not embed RTL source code")
    parser.add_argument("--source-url", help="HTTPS URL prefix for source links, e.g. GitHub blob/main")
    parser.add_argument("--min-coverage", type=float, help="Minimum documented units percentage")
    parser.add_argument("--min-port-coverage", type=float, help="Minimum documented ports percentage")
    parser.add_argument("--min-parameter-coverage", type=float, help="Minimum documented parameters percentage")
    parser.add_argument("--strict", action="store_true", help="Require all design units to be documented")
    parser.add_argument("--fail-on-warnings", action="store_true", help="Fail if stale/duplicate annotations exist")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("--version", action="version", version=f"doxnet {__version__}")
    return parser


def configure_logging(verbosity, quiet):
    level = logging.WARNING if quiet else (logging.DEBUG if verbosity >= 2 else logging.INFO)
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def load_config(args):
    """Read and merge config: CLI options override config; config overrides defaults."""
    config = {}
    config_dir = Path.cwd()
    if args.config:
        config_path = Path(args.config).resolve()
        config_dir = config_path.parent
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a JSON object")
    for key, default in DEFAULTS.items():
        val = getattr(args, key)
        if val is None:
            val = config.get(key, default)
        setattr(args, key, val)
    if args.input is None:
        args.input = config.get("input")
        if args.input:
            args.input = str(config_dir / args.input)
    if args.filelist is None and config.get("filelist"):
        args.filelist = str(config_dir / config["filelist"])
    if args.exclude is None:
        args.exclude = config.get("exclude", [])
    if not isinstance(args.exclude, list) or not all(isinstance(s, str) for s in args.exclude):
        raise ValueError("exclude must be an array of patterns")
    if args.language not in TRANSLATIONS:
        raise ValueError("Unsupported language: " + str(args.language))
    if not isinstance(args.title, str):
        raise ValueError("title must be a string")
    for key in ("html_file", "md_file", "pdf_file", "json_file"):
        filename = getattr(args, key)
        if not isinstance(filename, str) or not filename or filename != Path(filename).name or filename in (".", "..") or "\\" in filename:
            raise ValueError(f"{key} must be a file name, not a path")
    if len({args.html_file, args.md_file, args.pdf_file, args.json_file}) != 4:
        raise ValueError("Output file names must be distinct")
    for key in ("min_coverage", "min_port_coverage", "min_parameter_coverage"):
        value = getattr(args, key)
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not 0 <= value <= 100:
                raise ValueError(f"{key} must be a number from 0 to 100")
    if args.no_pdf and args.pdf_required:
        raise ValueError("--no-pdf cannot be combined with --pdf-required")
    if args.source_url:
        if not isinstance(args.source_url, str):
            raise ValueError("source_url must be an HTTPS URL")
        parsed = urlsplit(args.source_url)
        if (parsed.scheme != "https" or not parsed.netloc or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("source_url must be an HTTPS URL without credentials, query or fragment")
    if "files" in config and (not isinstance(config["files"], list) or not all(isinstance(s, str) for s in config["files"])):
        raise ValueError("files must be an array of paths")
    if not args.input and config.get("files"):
        args.input = str(config_dir)
    return [config_dir / name for name in config.get("files", [])]


def _read_filelist(path, visited=None):
    path = Path(path).resolve()
    visited = set() if visited is None else visited
    if path in visited:
        raise ValueError(f"Recursive filelist reference: {path}")
    visited.add(path)
    paths = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        entry = raw.strip()
        if not entry or entry.startswith(("#", "//")):
            continue
        if entry.startswith("-f "):
            paths.extend(_read_filelist(path.parent / entry[3:].strip(), visited))
        elif entry.startswith(('+', '-')):
            raise ValueError(f"Unsupported filelist directive: {entry}; preprocessing is not supported")
        else:
            paths.append(path.parent / entry)
    visited.remove(path)
    return paths


def collect_project(args, config_files):
    project = Project(title=args.title)
    explicit = list(config_files)
    if args.filelist:
        explicit.extend(_read_filelist(args.filelist))
    root = Path(args.input).resolve() if args.input else (Path(args.filelist).resolve().parent if args.filelist else None)
    if explicit:
        paths = explicit
    else:
        if root is None or not root.is_dir():
            raise ValueError("Supply an existing --input directory or a config/files filelist")
        paths = sorted(p for p in root.rglob("*") if p.suffix.lower() in EXTENSIONS and p.is_file())
    if not paths:
        raise ValueError("No HDL files found")
    processed = set()
    sources = {}
    for item in paths:
        path = Path(item).resolve()
        if not explicit and root not in path.parents:
            raise ValueError(f"An HDL symlink points outside the input root: {item}")
        if path in processed:
            continue
        processed.add(path)
        if not path.is_file():
            raise ValueError(f"HDL file does not exist: {path}")
        try:
            relative = path.relative_to(root).as_posix() if root else path.name
        except ValueError:
            relative = path.name
        if any(fnmatch.fnmatch(relative, pattern) for pattern in args.exclude):
            continue
        if relative in sources:
            raise ValueError(f"Two HDL inputs share the same display path: {relative}")
        source = path.read_text(encoding="utf-8")
        sources[relative] = source
        project.files.append(relative)
        units, diagnostics = parse_file(path, display_name=relative)
        project.units.extend(units)
        project.diagnostics.extend(diagnostics)
    if not project.files:
        raise ValueError("No HDL files remained after exclusions")
    if not project.units:
        raise ValueError("No design units detected; refusing to report 100% coverage")
    return project, sources


def _coverage_failed(args, project):
    cov = project.coverage()
    minimums = {"units": (100.0 if args.strict else args.min_coverage),
                "ports": args.min_port_coverage, "parameters": args.min_parameter_coverage}
    failed = False
    for name, item in cov.items():
        percentage = item["percent"]
        msg = "n/a" if percentage is None else f"{percentage:.1f}%"
        logger.info("%s coverage: %d/%d (%s)", name, item["documented"], item["total"], msg)
        minimum = minimums[name]
        if minimum is not None and (percentage is None or percentage < minimum):
            logger.error("%s coverage %s is below the required %.1f%%", name, msg, minimum)
            failed = True
    return failed


def run(args):
    config_files = load_config(args)
    project, sources = collect_project(args, config_files)
    for diag in project.diagnostics:
        getattr(logger, "error" if diag.severity == "error" else "warning")(
            "%s:%d: %s: %s", diag.file, diag.line, diag.code, diag.message
        )
    # Do not publish a potentially misleading partial interface when a header
    # or end delimiter is malformed. This also makes CI fail without a gate.
    if any(diag.severity == "error" for diag in project.diagnostics):
        return EXIT_INPUT_ERROR
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    md_path = out / args.md_file
    md_path.write_text(render_markdown(project, sources, args.language, not args.no_source), encoding="utf-8")
    (out / args.html_file).write_text(render_html(project, sources, args.language,
                                                 not args.no_source, args.source_url), encoding="utf-8")
    (out / args.json_file).write_text(render_json(project), encoding="utf-8")
    if not args.no_pdf:
        success = convert_md_to_pdf(md_path, out / args.pdf_file)
        if args.pdf_required and not success:
            return EXIT_GENERATION_ERROR
    if _coverage_failed(args, project):
        return EXIT_COVERAGE_FAILED
    if args.fail_on_warnings and project.diagnostics:
        return EXIT_GENERATION_ERROR
    logger.info("Generated documentation for %d units across %d files in %s",
                len(project.units), len(project.files), out)
    return EXIT_OK


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose, args.quiet)
    try:
        return run(args)
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        logger.error("%s", exc)
        return EXIT_INPUT_ERROR


if __name__ == "__main__":
    sys.exit(main())
