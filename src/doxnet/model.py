"""Typed, renderer-independent representation of a documented HDL design."""
from dataclasses import dataclass, field, asdict
from typing import List


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


@dataclass
class Diagnostic:
    code: str
    message: str
    file: str
    line: int
    severity: str = "warning"


@dataclass
class Project:
    title: str
    units: List[DesignUnit] = field(default_factory=list)
    diagnostics: List[Diagnostic] = field(default_factory=list)
    files: List[str] = field(default_factory=list)

    def coverage(self):
        """Return None for empty denominators; never report empty input as 100%."""
        def metric(items, documented):
            return {
                "documented": sum(bool(documented(item)) for item in items),
                "total": len(items),
                "percent": (100.0 * sum(bool(documented(item)) for item in items) / len(items)) if items else None,
            }

        ports = [port for unit in self.units for port in unit.ports]
        params = [par for unit in self.units for par in unit.parameters]
        return {
            "units": metric(self.units, lambda u: u.documented),
            "ports": metric(ports, lambda p: p.description),
            "parameters": metric(params, lambda p: p.description),
        }

    def as_dict(self):
        data = asdict(self)
        data["coverage"] = self.coverage()
        data["schema_version"] = 1
        return data
