"""Helpers shared by the Markdown and HTML renderers."""
from __future__ import annotations

from collections import OrderedDict
import re
from typing import Dict, List

from ..model import DesignUnit, Project

KIND_ORDER = ("module", "interface", "package", "program", "primitive")


def unit_id(unit: DesignUnit) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", (unit.file + "-" + unit.kind + "-" + unit.name).lower()).strip("-")
    return "unit-" + slug + "-" + str(unit.line)


def file_id(filename: str) -> str:
    return "file-" + re.sub(r"[^a-z0-9-]+", "-", filename.lower()).strip("-")


def by_file(project: Project) -> Dict[str, List[DesignUnit]]:
    groups: Dict[str, List[DesignUnit]] = OrderedDict((name, []) for name in project.files)
    for unit in project.units:
        groups.setdefault(unit.file, []).append(unit)
    return groups


def by_kind(project: Project) -> Dict[str, List[DesignUnit]]:
    groups: Dict[str, List[DesignUnit]] = OrderedDict((kind, []) for kind in KIND_ORDER)
    for unit in project.units:
        groups.setdefault(unit.kind, []).append(unit)
    for units in groups.values():
        units.sort(key=lambda u: u.name.lower())
    return OrderedDict((k, v) for k, v in groups.items() if v)


def percent(metric, na="n/a") -> str:
    return na if metric["percent"] is None else f"{metric['percent']:.1f}%"


def unit_coverage(unit: DesignUnit):
    ports = sum(1 for p in unit.ports if p.description)
    params = sum(1 for p in unit.parameters if p.description)
    return {"ports": (ports, len(unit.ports)), "parameters": (params, len(unit.parameters))}


def unit_index(project: Project) -> Dict[str, DesignUnit]:
    index: Dict[str, DesignUnit] = {}
    for unit in project.units:
        index.setdefault(unit.name, unit)
    return index
