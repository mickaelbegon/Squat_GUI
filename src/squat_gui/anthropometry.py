"""Anthropometric parameters for a combined left/right 2D squat model."""

from __future__ import annotations

from dataclasses import dataclass
from math import radians


SUBJECT_PROFILES = ("homme", "femme enceinte")
BAR_POSITIONS = ("front", "back", "over-head")


@dataclass(frozen=True)
class SegmentSpec:
    name: str
    length: float
    mass: float
    com_fraction: float
    radius_of_gyration: float
    com_anterior_offset: float = 0.0
    inertia_scale: float = 1.0

    @property
    def inertia(self) -> float:
        return self.inertia_scale * self.mass * (self.radius_of_gyration * self.length) ** 2


@dataclass(frozen=True)
class Anthropometry:
    body_mass: float = 70.0
    height: float = 1.70
    foot_scale: float = 1.0
    shank_scale: float = 1.0
    thigh_scale: float = 1.0
    trunk_scale: float = 1.0
    bar_mass: float = 0.0
    subject_profile: str = "homme"
    bar_position: str = "back"
    wedge_angle_deg: float = 0.0

    def __post_init__(self) -> None:
        if self.subject_profile not in SUBJECT_PROFILES:
            raise ValueError(f"Profil inconnu: {self.subject_profile}")
        if self.bar_position not in BAR_POSITIONS:
            raise ValueError(f"Position de barre inconnue: {self.bar_position}")

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
        hold_offset = {
            "front": 0.025,
            "back": -0.012,
            "over-head": 0.006,
        }[self.bar_position]
        hold_fraction = {
            "front": 0.55,
            "back": 0.55,
            "over-head": 0.61,
        }[self.bar_position]
        pregnancy_offset = 0.060 if self.subject_profile == "femme enceinte" else 0.0
        inertia_scale = 1.18 if self.subject_profile == "femme enceinte" else 1.0
        return SegmentSpec(
            "tronc",
            0.300 * self.height * self.trunk_scale,
            rest_mass,
            hold_fraction,
            0.496,
            com_anterior_offset=hold_offset + pregnancy_offset,
            inertia_scale=inertia_scale,
        )

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

    @property
    def wedge_angle(self) -> float:
        return radians(self.wedge_angle_deg)

    @property
    def bar_anterior_offset(self) -> float:
        return {"front": 0.14, "back": -0.07, "over-head": 0.0}[self.bar_position]

    @property
    def bar_longitudinal_offset(self) -> float:
        return {"front": -0.02, "back": -0.02, "over-head": self.trunk.length}[self.bar_position]


def scale_from_percent(percent: float) -> float:
    return 1.0 + percent / 100.0
