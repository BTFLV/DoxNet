"""Settings: defaults, config file (JSON or TOML) and command-line overrides.

Precedence is command line > config file > defaults. Paths in a config file
are relative to the file's directory.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from .preprocess import parse_define
from .render import TRANSLATIONS
from .render.html import check_source_url

FORMATS = ("html", "markdown", "json", "pdf")
OUTPUT_NAMES = {"html": "html_file", "markdown": "md_file", "json": "json_file", "pdf": "pdf_file"}


@dataclass
class Settings:
    title: str = "Project Documentation"
    language: str = "en"
    input: Optional[Path] = None
    files: List[Path] = field(default_factory=list)
    filelist: Optional[Path] = None
    exclude: List[str] = field(default_factory=list)
    output: Optional[Path] = None
    html_file: str = "documentation.html"
    md_file: str = "documentation.md"
    pdf_file: str = "documentation.pdf"
    json_file: str = "documentation.json"
    formats: List[str] = field(default_factory=lambda: list(FORMATS))
    pdf_required: bool = False
    include_source: bool = True
    source_url: Optional[str] = None
    min_coverage: Optional[float] = None
    min_port_coverage: Optional[float] = None
    min_parameter_coverage: Optional[float] = None
    strict: bool = False
    fail_on_warnings: bool = False
    defines: Dict[str, str] = field(default_factory=dict)
    include_dirs: List[Path] = field(default_factory=list)
    preprocess: bool = True
    plain_comments: bool = False
    top: List[str] = field(default_factory=list)
    disable: List[str] = field(default_factory=list)
    encoding: str = "utf-8"
    check: bool = False
    diagnostics_format: str = "text"


# Config keys and the type each one must have.
_KEYS: Dict[str, Any] = {
    "title": str, "language": str, "input": "path", "files": "paths", "filelist": "path",
    "exclude": "strings", "output": "path", "html_file": str, "md_file": str, "pdf_file": str,
    "json_file": str, "formats": "strings", "pdf_required": bool, "include_source": bool,
    "source_url": str, "min_coverage": "percent", "min_port_coverage": "percent",
    "min_parameter_coverage": "percent", "strict": bool, "fail_on_warnings": bool, "defines": "defines",
    "include_dirs": "paths", "preprocess": bool, "plain_comments": bool, "top": "strings",
    "disable": "strings", "encoding": str,
}


def read_config_file(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".toml":
        if sys.version_info >= (3, 11):
            import tomllib
        else:  # pragma: no cover - depends on the interpreter
            import tomli as tomllib
        data = tomllib.loads(text)
        if path.name == "pyproject.toml":
            data = data.get("tool", {}).get("doxnet")
            if data is None:
                raise ValueError(f"{path} has no [tool.doxnet] table")
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Configuration must be an object")
    return data


def _convert(key: str, value: Any, kind: Any, base: Path) -> Any:
    def fail(expected):
        raise ValueError(f"Config option {key} must be {expected}")

    if kind is str:
        if not isinstance(value, str):
            fail("a string")
        return value
    if kind is bool:
        if not isinstance(value, bool):
            fail("true or false")
        return value
    if kind == "path":
        if not isinstance(value, str):
            fail("a path string")
        return base / value
    if kind in ("paths", "strings"):
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            fail("an array of strings")
        return [base / v for v in value] if kind == "paths" else list(value)
    if kind == "percent":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            fail("a number from 0 to 100")
        return float(value)
    if kind == "defines":
        if isinstance(value, dict):
            return {str(k): "" if v is None or v is True else str(v) for k, v in value.items()}
        if isinstance(value, list) and all(isinstance(v, str) for v in value):
            return dict(parse_define(v) for v in value)
        fail("an object or an array of NAME[=VALUE] strings")
    raise AssertionError(kind)


def load_settings(args) -> Settings:
    """Build validated settings from parsed command-line arguments."""
    settings = Settings()
    base = Path.cwd()
    if args.config:
        config_path = Path(args.config).resolve()
        config = read_config_file(config_path)
        base = config_path.parent
        unknown = sorted(set(config) - set(_KEYS))
        if unknown:
            raise ValueError("Unknown config option(s): " + ", ".join(unknown))
        for key, value in config.items():
            setattr(settings, key, _convert(key, value, _KEYS[key], base))
        if settings.files and settings.input is None:
            settings.input = base

    cli = {
        "title": args.title, "language": args.language, "filelist": args.filelist, "output": args.output,
        "html_file": args.html_file, "md_file": args.md_file, "pdf_file": args.pdf_file,
        "json_file": args.json_file, "source_url": args.source_url, "min_coverage": args.min_coverage,
        "min_port_coverage": args.min_port_coverage, "min_parameter_coverage": args.min_parameter_coverage,
        "encoding": args.encoding,
    }
    for key, value in cli.items():
        if value is not None:
            setattr(settings, key, Path(value) if key in ("filelist", "output") else value)
    if args.input is not None:
        settings.input = Path(args.input)
    if args.exclude:
        settings.exclude = list(args.exclude)
    if args.formats:
        settings.formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    for flag in ("strict", "fail_on_warnings", "pdf_required", "plain_comments", "check"):
        if getattr(args, flag):
            setattr(settings, flag, True)
    if args.no_source:
        settings.include_source = False
    if args.no_preprocess:
        settings.preprocess = False
    if args.no_pdf and "pdf" in settings.formats:
        settings.formats.remove("pdf")
    if args.define:
        settings.defines.update(parse_define(d) for d in args.define)
    if args.incdir:
        settings.include_dirs += [Path(d) for d in args.incdir]
    if args.top:
        settings.top = list(args.top)
    if args.disable:
        settings.disable += [code for item in args.disable for code in item.split(",") if code]
    settings.diagnostics_format = args.diagnostics_format
    validate(settings, args)
    return settings


def validate(settings: Settings, args=None) -> None:
    if settings.language not in TRANSLATIONS:
        raise ValueError(f"Unsupported language: {settings.language} (available: {', '.join(TRANSLATIONS)})")
    unknown = [f for f in settings.formats if f not in FORMATS]
    if unknown:
        raise ValueError(f"Unknown output format(s): {', '.join(unknown)}; choose from {', '.join(FORMATS)}")
    names = []
    for fmt in FORMATS:
        key = OUTPUT_NAMES[fmt]
        name = getattr(settings, key)
        if not name or name in (".", "..") or name != Path(name).name or "\\" in name:
            raise ValueError(f"{key} must be a file name, not a path")
        names.append(name)
    if len(set(names)) != len(names):
        raise ValueError("Output file names must be distinct")
    for key in ("min_coverage", "min_port_coverage", "min_parameter_coverage"):
        value = getattr(settings, key)
        if value is not None and not 0 <= value <= 100:
            raise ValueError(f"{key} must be a number from 0 to 100")
    if args is not None and args.no_pdf and args.pdf_required:
        raise ValueError("--no-pdf cannot be combined with --pdf-required")
    if settings.pdf_required and "pdf" not in settings.formats:
        raise ValueError("pdf_required needs the pdf output format")
    if "pdf" in settings.formats and "markdown" not in settings.formats:
        raise ValueError("The pdf format is produced from Markdown; enable the markdown format as well")
    check_source_url(settings.source_url)
    if settings.output is None and not settings.check:
        raise ValueError("Specify --output (or use --check to validate without writing files)")
    try:
        "".encode(settings.encoding)
    except LookupError:
        raise ValueError(f"Unknown encoding: {settings.encoding}") from None
