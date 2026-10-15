"""SVG block diagrams of a unit's ports.

Inputs and interface ports are drawn on the left, outputs and inouts on the
right. Vector ports get a thicker line and their packed range as a label.
Colors come from CSS so the diagram follows the page theme.
"""
from __future__ import annotations

from html import escape
import re
from typing import List

from ..model import DesignUnit, Port

_PITCH = 22
_STUB = 34
_CHAR = 7.2  # average glyph width of the 12px monospace labels
_PAD = 14


def _range(port: Port) -> str:
    dims = re.findall(r"\[[^\]]*\]", port.type)
    if dims:
        return "".join(dims)
    return port.type if port.direction == "interface" else ""


def _shorten(text: str, limit: int = 28) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _width(text: str) -> float:
    return len(text) * _CHAR


def block_diagram(unit: DesignUnit) -> str:
    if not unit.ports:
        return ""
    left: List[Port] = [p for p in unit.ports if p.direction not in ("output", "inout")]
    right: List[Port] = [p for p in unit.ports if p.direction in ("output", "inout")]
    params = ", ".join(f"{p.name}={p.default}" if p.default else p.name for p in unit.parameters)
    params = _shorten(f"#({params})", 48) if params else ""

    left_labels = [_shorten(_range(p)) for p in left]
    right_labels = [_shorten(_range(p)) for p in right]
    outer_left = max([_width(t) for t in left_labels] + [0]) + (14 if any(left_labels) else 0)
    outer_right = max([_width(t) for t in right_labels] + [0]) + (8 if any(right_labels) else 0)
    inner = max([_width(p.name) for p in left] + [0]) + max([_width(p.name) for p in right] + [0]) + 40
    box_w = max(inner, _width(unit.name) * 1.15 + 2 * _PAD, _width(params) + 2 * _PAD, 120)
    header = 28 + (16 if params else 0)
    rows = max(len(left), len(right))
    box_h = header + rows * _PITCH + 8
    x0 = _PAD + outer_left + _STUB
    width = x0 + box_w + _STUB + outer_right + _PAD
    height = box_h + 2 * _PAD

    out = [f'<svg class="block-diagram" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
           f'width="{width:.0f}" height="{height:.0f}" role="img" aria-label="{escape(unit.name, quote=True)}">',
           f'<rect class="dg-box" x="{x0:.1f}" y="{_PAD}" width="{box_w:.1f}" height="{box_h}" rx="6"/>',
           f'<text class="dg-title" x="{x0 + box_w / 2:.1f}" y="{_PAD + 20}" text-anchor="middle">'
           f'{escape(unit.name)}</text>']
    if params:
        out.append(f'<text class="dg-param" x="{x0 + box_w / 2:.1f}" y="{_PAD + 36}" text-anchor="middle">'
                   f'{escape(params)}</text>')

    def pins(ports, labels, side):
        for row, (port, label) in enumerate(zip(ports, labels)):
            y = _PAD + header + row * _PITCH + _PITCH / 2
            bus = " dg-bus" if label else ""
            if side == "left":
                x_out, x_in = x0 - _STUB, x0
                name_x, anchor, label_x, label_anchor = x0 + 8, "start", x_out - 6, "end"
            else:
                x_out, x_in = x0 + box_w + _STUB, x0 + box_w
                name_x, anchor, label_x, label_anchor = x_in - 8, "end", x_out + 6, "start"
            kind = {"input": "in", "output": "out", "inout": "inout", "interface": "intf"}.get(port.direction, "in")
            out.append(f'<g class="dg-pin dg-{kind}"><title>{escape((port.direction + " " + port.type + " " + port.name).strip())}</title>'
                       f'<line class="dg-wire{bus}" x1="{x_out:.1f}" y1="{y:.1f}" x2="{x_in:.1f}" y2="{y:.1f}"/>')
            out.append(_marker(kind, side, x_out, x_in, y))
            if kind == "intf":  # leave room for the circle
                label_x += -6 if side == "left" else 6
            out.append(f'<text class="dg-name" x="{name_x:.1f}" y="{y + 4:.1f}" text-anchor="{anchor}">'
                       f'{escape(port.name)}</text>')
            if label:
                out.append(f'<text class="dg-range" x="{label_x:.1f}" y="{y + 4:.1f}" '
                           f'text-anchor="{label_anchor}">{escape(label)}</text>')
            out.append("</g>")

    pins(left, left_labels, "left")
    pins(right, right_labels, "right")
    out.append("</svg>")
    return "".join(out)


def _arrow(x: float, y: float, direction: int) -> str:
    """A small filled triangle pointing right (+1) or left (-1) with its tip at x."""
    return (f'<path class="dg-arrow" d="M{x:.1f},{y:.1f} l{-7 * direction},-4 v8 z"/>')


def _marker(kind: str, side: str, x_out: float, x_in: float, y: float) -> str:
    towards_box = 1 if side == "left" else -1
    if kind == "intf":
        return f'<circle class="dg-intf" cx="{x_out:.1f}" cy="{y:.1f}" r="4"/>'
    if kind == "inout":
        return _arrow(x_in, y, towards_box) + _arrow(x_out, y, -towards_box)
    if kind == "out":
        return _arrow(x_out, y, -towards_box)
    return _arrow(x_in, y, towards_box)
