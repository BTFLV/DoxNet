"""Cross-file analysis: resolving instances and building the design hierarchy."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

from .model import DesignUnit, Diagnostic, HierarchyNode, Project

_INSTANTIABLE = {"module", "interface", "program"}
_MAX_DEPTH = 64


def link(project: Project, top: Optional[Sequence[str]] = None) -> None:
    """Resolve references between units and compute ``project.hierarchy``.

    ``top`` restricts the hierarchy roots. Without it, every module or program
    that nothing in the project instantiates is a root.
    """
    index: Dict[str, DesignUnit] = {}
    for unit in project.units:
        first = index.get(unit.name)
        if first is None:
            index[unit.name] = unit
        else:
            project.diagnostics.append(Diagnostic(
                "HDL002", f"{unit.kind} {unit.name} is already defined in {first.file}:{first.line}",
                unit.file, unit.line))

    for unit in project.units:
        unit.instantiated_by = []
    for unit in project.units:
        for instance in unit.instances:
            target = index.get(instance.module)
            instance.resolved = target is not None and target.kind in _INSTANTIABLE
            if instance.resolved and unit.name not in target.instantiated_by:
                target.instantiated_by.append(unit.name)
        for port in unit.ports:
            base = re.split(r"[\s.\[]", port.type, maxsplit=1)[0] if port.type else ""
            target = index.get(base)
            if target is not None and target.kind == "interface":
                port.direction = "interface"

    if top:
        missing = [name for name in top if name not in index]
        if missing:
            raise ValueError("Unknown top-level unit(s): " + ", ".join(missing))
        roots = list(top)
    else:
        roots = [u.name for u in project.units
                 if u.kind in ("module", "program") and not u.instantiated_by and index[u.name] is u]
    project.top = roots
    project.hierarchy = [_tree(index, name, "", [], 0) for name in roots]


def _tree(index: Dict[str, DesignUnit], module: str, instance: str, path: List[str], depth: int) -> HierarchyNode:
    unit = index.get(module)
    node = HierarchyNode(module, instance, resolved=unit is not None)
    if unit is None:
        return node
    if module in path or depth >= _MAX_DEPTH:
        node.recursive = True
        return node
    for inst in unit.instances:
        name = inst.name + inst.array
        node.children.append(_tree(index, inst.module, name, path + [module], depth + 1))
    return node


def walk(nodes: List[HierarchyNode], depth: int = 0):
    """Yield ``(depth, node)`` in depth-first order."""
    for node in nodes:
        yield depth, node
        yield from walk(node.children, depth + 1)
