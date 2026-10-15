"""Finding the input files and turning them into a linked project."""
from __future__ import annotations

from dataclasses import dataclass, field
import fnmatch
import logging
import os
from pathlib import Path
import re
from typing import Dict, List, Optional, Set, Tuple

from .config import Settings
from .hierarchy import link
from .model import Project
from .parser import parse_source
from .preprocess import Preprocessor, parse_define

logger = logging.getLogger("doxnet")
EXTENSIONS = {".v", ".sv", ".vh", ".svh"}
_ENV = re.compile(r"\$(\w+)|\$\{([^}]+)\}|\$\(([^)]+)\)")


@dataclass
class Filelist:
    files: List[Path] = field(default_factory=list)
    include_dirs: List[Path] = field(default_factory=list)
    defines: Dict[str, str] = field(default_factory=dict)


def _expand(entry: str, where: str) -> str:
    def replace(match):
        name = match.group(1) or match.group(2) or match.group(3)
        if name not in os.environ:
            raise ValueError(f"{where}: environment variable {name} is not set")
        return os.environ[name]
    return _ENV.sub(replace, entry)


def read_filelist(path, result: Optional[Filelist] = None, visited: Optional[Set[Path]] = None) -> Filelist:
    """Read a simulator-style ``.f`` file.

    Supported: one source path per line, ``#`` and ``//`` comments,
    ``-f``/``-F`` nested filelists, ``+incdir+``, ``+define+`` and environment
    variables (``$VAR``, ``${VAR}``, ``$(VAR)``). Relative paths are relative
    to the filelist that contains them. Anything else is rejected rather than
    ignored.
    """
    path = Path(path).resolve()
    result = Filelist() if result is None else result
    visited = set() if visited is None else visited
    if path in visited:
        raise ValueError(f"Recursive filelist reference: {path}")
    visited.add(path)
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        entry = re.split(r"\s//|^//|\s#|^#", raw, maxsplit=1)[0].strip()
        if not entry:
            continue
        where = f"{path.name}:{number}"
        items = _expand(entry, where).split()
        k = 0
        while k < len(items):
            item = items[k]
            k += 1
            if item in ("-f", "-F"):
                if k >= len(items):
                    raise ValueError(f"{where}: {item} needs a file name")
                read_filelist(path.parent / items[k], result, visited)
                k += 1
            elif item.startswith("+incdir+"):
                result.include_dirs += [path.parent / d for d in item[len("+incdir+"):].split("+") if d]
            elif item.startswith("+define+"):
                for definition in item[len("+define+"):].split("+"):
                    if definition:
                        name, value = parse_define(definition)
                        result.defines[name] = value
            elif item.startswith(("+", "-")):
                raise ValueError(f"{where}: unsupported filelist option {item}")
            else:
                result.files.append(path.parent / item)
    visited.remove(path)
    return result


def _display_name(path: Path, root: Optional[Path]) -> str:
    if root is not None:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            pass
    return path.name


def collect_project(settings: Settings) -> Tuple[Project, Dict[str, str], Dict[str, Path]]:
    """Read, preprocess and parse all inputs.

    Returns the project, the original source text and the resolved path of
    every file, all keyed by display name.
    """
    explicit = list(settings.files)
    include_dirs = list(settings.include_dirs)
    defines = dict(settings.defines)
    if settings.filelist:
        filelist = read_filelist(settings.filelist)
        explicit += filelist.files
        include_dirs += filelist.include_dirs
        for name, value in filelist.defines.items():
            defines.setdefault(name, value)  # command line and config win
    root = settings.input.resolve() if settings.input else (
        settings.filelist.resolve().parent if settings.filelist else None)
    if explicit:
        paths = explicit
    else:
        if root is None or not root.is_dir():
            raise ValueError("Supply an existing --input directory, a filelist or a config with files")
        paths = sorted((p for p in root.rglob("*") if p.suffix.lower() in EXTENSIONS and p.is_file()),
                       key=lambda p: p.relative_to(root).as_posix())
    if not paths:
        raise ValueError("No HDL files found")

    project = Project(title=settings.title)
    preprocessor = Preprocessor(defines, include_dirs, settings.encoding) if settings.preprocess else None
    sources: Dict[str, str] = {}
    locations: Dict[str, Path] = {}
    seen: Set[Path] = set()
    for item in paths:
        path = Path(item).resolve()
        if not explicit and root not in path.parents:
            raise ValueError(f"An HDL symlink points outside the input root: {item}")
        if path in seen:
            continue
        seen.add(path)
        if not path.is_file():
            raise ValueError(f"HDL file does not exist: {path}")
        relative = _display_name(path, root)
        if any(fnmatch.fnmatch(relative, pattern) for pattern in settings.exclude):
            logger.debug("Excluded %s", relative)
            continue
        if relative in sources:
            raise ValueError(f"Two HDL inputs share the same display path: {relative}")
        try:
            source = path.read_text(encoding=settings.encoding)
        except UnicodeDecodeError as exc:
            raise ValueError(f"{relative} is not valid {settings.encoding} ({exc.reason} at byte {exc.start}); "
                             "set the encoding option") from None
        sources[relative] = source
        locations[relative] = path
        project.files.append(relative)
        text = source
        if preprocessor is not None:
            text, diagnostics = preprocessor.process(source, relative, path)
            project.diagnostics.extend(diagnostics)
        logger.debug("Parsing %s", relative)
        result = parse_source(text, relative, settings.plain_comments)
        project.units.extend(result.units)
        project.diagnostics.extend(result.diagnostics)
        if result.file_doc is not None:
            project.file_docs[relative] = result.file_doc
    if not project.files:
        raise ValueError("No HDL files remained after exclusions")
    if not project.units:
        raise ValueError("No design units detected; refusing to report coverage for an empty design")
    link(project, settings.top)
    if settings.disable:
        disabled = {code.upper() for code in settings.disable}
        project.diagnostics = [d for d in project.diagnostics if d.code not in disabled or d.severity == "error"]
    return project, sources, locations
