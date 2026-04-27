"""Canvas renderer for JSON side-view segment shapes."""

from __future__ import annotations

import json
from functools import lru_cache
from math import cos, sin
from pathlib import Path
from typing import Callable

from .kinematics import Vector


ASSET_DIR = Path(__file__).resolve().parents[2] / "assets" / "side_view_segments"


@lru_cache(maxsize=1)
def load_segments() -> dict[str, dict]:
    return {
        name: json.loads((ASSET_DIR / f"{name}.json").read_text(encoding="utf-8"))
        for name in ("foot", "shank", "thigh", "trunk_bar")
    }


def transform_point(local_xy: list[float], origin: Vector, angle: float, scale: float) -> Vector:
    x = local_xy[0] * scale
    y = local_xy[1] * scale
    c = cos(angle)
    s = sin(angle)
    return (origin[0] + c * x - s * y, origin[1] + s * x + c * y)


def draw_segment(
    canvas,
    segment: dict,
    origin: Vector,
    angle: float,
    scale: float,
    world_to_canvas: Callable[[Vector], Vector],
    draw_joints: bool = False,
) -> None:
    style = segment.get("style", {})
    facecolor = style.get("facecolor", "#f1c7a1")
    edgecolor = style.get("edgecolor", "#1f1f1f")
    linewidth = max(1, int(style.get("linewidth", 2.0)))

    for path in segment.get("paths", []):
        vertices = path.get("vertices", [])
        if len(vertices) < 2:
            continue
        points: list[float] = []
        for local in vertices:
            x, y = world_to_canvas(transform_point(local, origin, angle, scale))
            points.extend([x, y])
        if path.get("closed", False):
            canvas.create_polygon(points, fill=facecolor, outline=edgecolor, width=linewidth, joinstyle="round")
        else:
            width = 6 if path.get("name") == "bar" else linewidth
            canvas.create_line(points, fill=edgecolor, width=width, capstyle="round", joinstyle="round")

    if draw_joints:
        radius = style.get("joint_radius", 0.035) * scale
        for local in segment.get("joints", {}).values():
            x, y = world_to_canvas(transform_point(local, origin, angle, scale))
            rx = max(4.0, radius * 120.0)
            canvas.create_oval(
                x - rx,
                y - rx,
                x + rx,
                y + rx,
                fill=style.get("joint_facecolor", "white"),
                outline=style.get("joint_edgecolor", "#1f1f1f"),
                width=2,
            )
