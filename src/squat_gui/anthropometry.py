"""Anthropometric parameters for a combined left/right 2D squat model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SegmentSpec:
    name: str
    length: float
    mass: float
    com_fraction: float
    radius_of_gyration: float

    @property
    def inertia(self) -> float:
        return self.mass * (self.radius_of_gyration * self.length) ** 2


@dataclass(frozen=True)
class Anthropometry:
    body_mass: float = 70.0
    height: float = 1.70
    foot_scale: float = 1.0
    shank_scale: float = 1.0
    thigh_scale: float = 1.0
    trunk_scale: float = 1.0
    bar_mass: float = 0.0

    @property
    def foot(self) -> SegmentSpec:
        return SegmentSpec("pied", 0.152 * self.height * self.foot_scale, 0.029 * self.body_mass, 0.50, 0.475)

    @property
    def shank(self) -> SegmentSpec:
        return SegmentSpec("jambe", 0.246 * self.height * self.shank_scale, 0.093 * self.body_mass, 0.433, 0.302)

    @property
    def thigh(self) -> SegmentSpec:
        return SegmentSpec("cuisse", 0.245 * self.height * self.thigh_scale, 0.200 * self.body_mass, 0.433, 0.323)

    @property
    def trunk(self) -> SegmentSpec:
        lower_limb_mass = self.foot.mass + self.shank.mass + self.thigh.mass
        rest_mass = self.body_mass - lower_limb_mass
        return SegmentSpec("tronc", 0.300 * self.height * self.trunk_scale, rest_mass, 0.55, 0.496)

    @property
    def segments(self) -> tuple[SegmentSpec, SegmentSpec, SegmentSpec, SegmentSpec]:
        return (self.foot, self.shank, self.thigh, self.trunk)

    @property
    def total_mass(self) -> float:
        return self.body_mass + self.bar_mass

    @property
    def ankle_x_from_heel(self) -> float:
        return 0.38 * self.foot.length

    @property
    def ankle_height(self) -> float:
        return 0.07


def scale_from_percent(percent: float) -> float:
    return 1.0 + percent / 100.0
