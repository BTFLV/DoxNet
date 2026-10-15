"""Renderer-independent representation of a documented HDL design."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

SCHEMA_VERSION = 2


@dataclass
class Port:
    name: str
    direction: str = ""
    type: str = ""
    description: str = ""
    line: int = 0


@dataclass
class Parameter:
    name: str
    type: str = ""
    default: str = ""
    description: str = ""
    line: int = 0
    local: bool = False


@dataclass
class Modport:
    """An interface modport; its ports carry only a direction and a name."""

    name: str
    ports: List[Port] = field(default_factory=list)
    description: str = ""
    line: int = 0


@dataclass
class Connection:
    """One entry of a parameter override or port connection list.

    ``formal`` is empty for positional connections and ``*`` for ``.*``.
    """

    formal: str
    actual: str = ""


@dataclass
class Instance:
    module: str
    name: str
    line: int = 0
    array: str = ""
    parameters: List[Connection] = field(default_factory=list)
    connections: List[Connection] = field(default_factory=list)
    description: str = ""
    resolved: bool = False


@dataclass
class Member:
    """A typedef, function, task or class declared inside a design unit."""

    kind: str
    name: str
    signature: str = ""
    description: str = ""
    line: int = 0


@dataclass
class DesignUnit:
    kind: str
    name: str
    file: str
    line: int
    end_line: int
    brief: str = ""
    description: str = ""
    documented: bool = False
    ports: List[Port] = field(default_factory=list)
    parameters: List[Parameter] = field(default_factory=list)
    localparams: List[Parameter] = field(default_factory=list)
    modports: List[Modport] = field(default_factory=list)
    instances: List[Instance] = field(default_factory=list)
    members: List[Member] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
    deprecated: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    todos: List[str] = field(default_factory=list)
    see: List[str] = field(default_factory=list)
    instantiated_by: List[str] = field(default_factory=list)


@dataclass
class FileDoc:
    brief: str = ""
    description: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class Diagnostic:
    code: str
    message: str
    file: str
    line: int
    severity: str = "warning"


@dataclass
class HierarchyNode:
    module: str
    instance: str = ""
    resolved: bool = True
    recursive: bool = False
    children: List[HierarchyNode] = field(default_factory=list)


def _metric(items, documented):
    count = sum(1 for item in items if documented(item))
    total = len(items)
    return {"documented": count, "total": total, "percent": (100.0 * count / total) if total else None}


@dataclass
class Project:
    title: str
    units: List[DesignUnit] = field(default_factory=list)
    diagnostics: List[Diagnostic] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    file_docs: Dict[str, FileDoc] = field(default_factory=dict)
    top: List[str] = field(default_factory=list)
    hierarchy: List[HierarchyNode] = field(default_factory=list)

    def coverage(self):
        """Documentation coverage per entity class.

        An empty denominator yields ``percent: None``; an input without ports
        is not "100% documented".
        """
        ports = [port for unit in self.units for port in unit.ports]
        params = [par for unit in self.units for par in unit.parameters]
        return {
            "units": _metric(self.units, lambda u: u.documented),
            "ports": _metric(ports, lambda p: p.description),
            "parameters": _metric(params, lambda p: p.description),
        }

    def unit(self, name: str) -> Optional[DesignUnit]:
        return next((u for u in self.units if u.name == name), None)

    def as_dict(self):
        data = {"schema_version": SCHEMA_VERSION}
        data.update(asdict(self))
        data["coverage"] = self.coverage()
        return data
