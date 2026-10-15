"""JSON output for CI tooling. The format is described in docs/schema/doxnet.schema.json."""
from __future__ import annotations

import json

from .. import __version__
from ..model import Project


def render_json(project: Project) -> str:
    data = project.as_dict()
    data["generator"] = {"name": "doxnet", "version": __version__}
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
