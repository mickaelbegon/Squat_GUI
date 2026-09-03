"""Renderer-independent geometry for the squat scene.

The GUI canvas and the off-screen Pillow renderer intentionally keep their
own drawing styles.  This module owns the world-space geometry they share so
that a landmark, segment, support limit, or viewport transform cannot silently
drift between the two renderers.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .anthropometry import Anthropometry
from .kinematics import (
    MotionState,
    Vector,
    functional_support_limits,
    geometric_support_limits,
)


@dataclass(frozen=True)
class NamedPoint:
    """A named world-space point used by renderers and hit testing."""

    name: str
    position: Vector


@dataclass(frozen=True)
class SegmentPrimitive:
    """World-space placement of one anatomical sprite or fallback segment."""

    name: str
    distal: Vector
    proximal: Vector
    variant: tuple[str, str] | None = None


@dataclass(frozen=True)
class SupportInterval:
    """A horizontal support interval on the ground plane."""

    posterior: float
    anterior: float

    @property
    def limits(self) -> tuple[float, float]:
        return (self.posterior, self.anterior)


@dataclass(frozen=True)
class SceneGeometry:
    """World-space primitives required by both supported renderers."""

    body_points: tuple[NamedPoint, ...]
    segments: tuple[SegmentPrimitive, ...]
    segment_coms: tuple[NamedPoint, ...]
    ground_line: tuple[Vector, Vector]
    wedge_polygon: tuple[Vector, Vector, Vector] | None
    com_projection: Vector
    support_point: Vector
    geometric_support: SupportInterval
    functional_support: SupportInterval

    def point(self, name: str) -> Vector:
        """Return a body landmark by its stable renderer-facing name."""

        for point in self.body_points:
            if point.name == name:
                return point.position
        raise KeyError(name)


@dataclass(frozen=True)
class ViewportTransform:
    """Pure world/pixel transform shared by Tk and Pillow renderers."""

    width: float
    height: float
    bounds: tuple[float, float, float, float]
    padding: float

    @property
    def scale(self) -> float:
        xmin, xmax, ymin, ymax = self.bounds
        return min(
            (self.width - 2.0 * self.padding) / (xmax - xmin),
            (self.height - 2.0 * self.padding) / (ymax - ymin),
        )

    def world_to_pixel(self, point: Vector) -> Vector:
        xmin, _, ymin, _ = self.bounds
        scale = self.scale
        return (
            self.padding + (point[0] - xmin) * scale,
            self.height - self.padding - (point[1] - ymin) * scale,
        )

    def pixel_to_world(self, point: Vector) -> Vector:
        xmin, _, ymin, _ = self.bounds
        scale = self.scale
        return (
            xmin + (point[0] - self.padding) / scale,
            ymin + (self.height - self.padding - point[1]) / scale,
        )


def scene_bounds(
    anthropometries: Iterable[Anthropometry], *, extra_x: float = 0.0
) -> tuple[float, float, float, float]:
    """Return stable bounds large enough for every supplied subject."""

    subjects = tuple(anthropometries)
    if not subjects:
        raise ValueError("Au moins une anthropométrie est requise.")
    ymax = max(
        2.22 if anthro.bar_position == "over-head" else 1.92
        for anthro in subjects
    )
    xmax = max(
        anthro.foot.length + anthro.shank.length + 0.78 for anthro in subjects
    )
    return (-0.36, xmax + extra_x, -0.08, ymax)


def build_scene_geometry(
    anthro: Anthropometry,
    state: MotionState,
    support_x: float,
    *,
    x_offset: float = 0.0,
) -> SceneGeometry:
    """Build the common world-space representation of one simulation frame."""

    pose = state.pose

    def shifted(point: Vector) -> Vector:
        return (point[0] + x_offset, point[1])

    body_points = tuple(
        NamedPoint(name, shifted(point))
        for name, point in (
            ("heel", pose.heel),
            ("toe", pose.toe),
            ("ankle", pose.ankle),
            ("knee", pose.knee),
            ("hip", pose.hip),
            ("shoulder", pose.shoulder),
            ("bar", pose.bar),
            ("com", pose.com),
        )
    )
    segments = (
        SegmentPrimitive("foot", shifted(pose.ankle), shifted(pose.toe)),
        SegmentPrimitive("shank", shifted(pose.ankle), shifted(pose.knee)),
        SegmentPrimitive("thigh", shifted(pose.knee), shifted(pose.hip)),
        SegmentPrimitive(
            "trunk",
            shifted(pose.hip),
            shifted(pose.shoulder),
            (anthro.subject_profile, anthro.bar_position),
        ),
    )
    geometric = geometric_support_limits(pose)
    functional = functional_support_limits(pose)
    heel = shifted(pose.heel)
    toe = shifted(pose.toe)
    return SceneGeometry(
        body_points=body_points,
        segments=segments,
        segment_coms=tuple(
            NamedPoint(name, shifted(point))
            for name, point in pose.segment_coms.items()
        ),
        ground_line=(heel, toe),
        wedge_polygon=(heel, toe, (heel[0], 0.0))
        if anthro.wedge_angle_deg
        else None,
        com_projection=(pose.com[0] + x_offset, 0.0),
        support_point=(support_x + x_offset, 0.0),
        geometric_support=SupportInterval(
            geometric[0] + x_offset, geometric[1] + x_offset
        ),
        functional_support=SupportInterval(
            functional[0] + x_offset, functional[1] + x_offset
        ),
    )


def project_point_on_line(point: Vector, origin: Vector, direction: Vector) -> Vector:
    """Return the orthogonal projection of ``point`` on an infinite line."""

    norm_squared = direction[0] ** 2 + direction[1] ** 2
    if norm_squared < 1e-12:
        return origin
    relative = (point[0] - origin[0], point[1] - origin[1])
    factor = (
        relative[0] * direction[0] + relative[1] * direction[1]
    ) / norm_squared
    return (
        origin[0] + factor * direction[0],
        origin[1] + factor * direction[1],
    )
