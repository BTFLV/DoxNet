"""Command-line interface for DoxNet."""
import argparse
import json
import logging
import os
import sys

from . import __version__
from .parser import parse_verilog_file
from .render import generate_markdown, convert_md_to_html, convert_md_to_pdf

logger = logging.getLogger("doxnet")

EXIT_OK = 0
EXIT_INPUT_ERROR = 1
EXIT_COVERAGE_FAILED = 2

TRANSLATIONS = {
    "en": {
        "toc": "Table of Contents",
        "file": "File",
        "module": "Module",
        "brief": "Brief",
        "inputs": "Inputs",
        "outputs": "Outputs",
        "inouts": "Inouts",
        "parameters": "Parameters",
        "localparams": "Local Parameters",
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
        "localparams": "Lokale Parameter",
    },
}


def build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="doxnet",
        description="Doxygen-lite documentation generator for Verilog and SystemVerilog.",
    )
    parser.add_argument("--input", "-i", help="Input directory containing .v/.sv files")
    parser.add_argument("--output", "-o", required=True, help="Output directory for documentation files")
    parser.add_argument("--language", default="en", choices=sorted(TRANSLATIONS), help="Documentation language")
    parser.add_argument("--title", default="Project Documentation", help="Title for the documentation")
    parser.add_argument("--html-file", default="documentation.html", help="Output HTML filename")
    parser.add_argument("--md-file", default="documentation.md", help="Output Markdown filename")
    parser.add_argument("--pdf-file", default="documentation.pdf", help="Output PDF filename")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation even if Pandoc is available")
    parser.add_argument("--config", help="Optional JSON configuration file")
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=None,
        metavar="PERCENT",
        help="Fail (exit 2) if the percentage of documented modules/interfaces/packages is below PERCENT",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Shortcut for --min-coverage 100",
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity (-v, -vv)")
    parser.add_argument("-q", "--quiet", action="store_true", help="Only log warnings and errors")
    parser.add_argument("--version", action="version", version=f"doxnet {__version__}")
    return parser


def configure_logging(verbosity, quiet):
    if quiet:
        level = logging.WARNING
    elif verbosity >= 2:
        level = logging.DEBUG
    elif verbosity == 1:
        level = logging.INFO
    else:
        level = logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def load_config(args):
    if not args.config:
        return None
    try:
        with open(args.config, 'r', encoding='utf-8') as cf:
            config = json.load(cf)
    except (OSError, json.JSONDecodeError) as e:
        logger.error("Error loading config file: %s", e)
        raise

    for key, attr in (
        ("title", "title"),
        ("language", "language"),
        ("html_file", "html_file"),
        ("md_file", "md_file"),
        ("pdf_file", "pdf_file"),
    ):
        if key in config:
            setattr(args, attr, config[key])
    return config.get("files")


def collect_docs(args, file_list):
    docs = {}
    coverage_totals = {"documented": 0, "total": 0, "undocumented": []}
    had_error = False

    def ingest(file_path, key):
        nonlocal had_error
        try:
            doc_items, (documented, total, undocumented) = parse_verilog_file(file_path)
        except OSError:
            had_error = True
            return
        if doc_items:
            docs[key] = doc_items
        coverage_totals["documented"] += documented
        coverage_totals["total"] += total
        coverage_totals["undocumented"].extend(f"{key}: {name}" for name in undocumented)

    if file_list:
        for file_path in file_list:
            if os.path.isfile(file_path):
                ingest(file_path, file_path)
            else:
                logger.warning("File %s does not exist.", file_path)
                had_error = True
        base_path = ""
    else:
        if not args.input or not os.path.isdir(args.input):
            logger.error("Input directory '%s' does not exist.", args.input)
            raise FileNotFoundError(args.input)
        base_path = args.input
        for root, _, files in os.walk(args.input):
            for file in files:
                if file.endswith((".v", ".sv")):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, args.input)
                    ingest(full_path, rel_path)

    return docs, base_path, coverage_totals, had_error


def report_coverage(coverage_totals):
    total = coverage_totals["total"]
    documented = coverage_totals["documented"]
    pct = 100.0 if total == 0 else (documented / total) * 100.0
    logger.info("Documentation coverage: %d/%d units documented (%.1f%%)", documented, total, pct)
    for entry in coverage_totals["undocumented"]:
        logger.info("  undocumented: %s", entry)
    return pct


def run(args):
    file_list = load_config(args)
    lang = TRANSLATIONS[args.language]
    os.makedirs(args.output, exist_ok=True)

    docs, base_path, coverage_totals, had_error = collect_docs(args, file_list)

    toc_md, body_md = generate_markdown(docs, lang, args.title, base_path)
    md_text = toc_md + "\n\n" + body_md
    md_path = os.path.join(args.output, args.md_file)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_text)
    logger.info("Markdown documentation generated: %s", md_path)

    html_text = convert_md_to_html(toc_md, body_md, args.title)
    html_path = os.path.join(args.output, args.html_file)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_text)
    logger.info("HTML documentation generated: %s", html_path)

    if not args.no_pdf:
        pdf_path = os.path.join(args.output, args.pdf_file)
        convert_md_to_pdf(md_path, pdf_path)

    pct = report_coverage(coverage_totals)

    min_coverage = 100.0 if args.strict else args.min_coverage
    if min_coverage is not None and pct < min_coverage:
        logger.error(
            "Documentation coverage %.1f%% is below the required %.1f%%.",
            pct,
            min_coverage,
        )
        return EXIT_COVERAGE_FAILED

    if had_error:
        return EXIT_INPUT_ERROR

    return EXIT_OK


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose, args.quiet)

    try:
        return run(args)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return EXIT_INPUT_ERROR


if __name__ == "__main__":
    sys.exit(main())
