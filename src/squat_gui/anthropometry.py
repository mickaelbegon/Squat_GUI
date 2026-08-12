"""Anthropometric parameters for a combined left/right 2D squat model."""

from __future__ import annotations

from dataclasses import dataclass
from math import radians

from .bar_calibration import physical_bar_offsets

SUBJECT_PROFILES = ("homme", "femme enceinte")
BAR_POSITIONS = ("front", "back", "over-head")
ANTHROPOMETRY_MODES = ("longueur seule", "morphotype recalibre")

BASE_MASS_FRACTIONS = {
    "foot": 0.029,
    "shank": 0.093,
    "thigh": 0.200,
    "trunk": 0.678,
}


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
        return (
            self.inertia_scale
            * self.mass
            * (self.radius_of_gyration * self.length) ** 2
        )


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
    scaling_mode: str = "longueur seule"

    def __post_init__(self) -> None:
        if self.subject_profile not in SUBJECT_PROFILES:
            raise ValueError(f"Profil inconnu: {self.subject_profile}")
        if self.bar_position not in BAR_POSITIONS:
            raise ValueError(f"Position de barre inconnue: {self.bar_position}")
        if self.scaling_mode not in ANTHROPOMETRY_MODES:
            raise ValueError(f"Mode anthropométrique inconnu: {self.scaling_mode}")

    @property
    def segment_mass_fractions(self) -> dict[str, float]:
        """Return the effective body-mass fractions used by the model.

        ``longueur seule`` holds masses fixed. ``morphotype recalibre`` uses a
        transparent constant-linear-density sensitivity: each reference mass
        fraction is multiplied by its length scale, then all four fractions
        are renormalized to preserve total body mass. This is a didactic rule,
        not a population regression.
        """
        if self.scaling_mode == "longueur seule":
            return dict(BASE_MASS_FRACTIONS)
        weighted = {
            "foot": BASE_MASS_FRACTIONS["foot"] * self.foot_scale,
            "shank": BASE_MASS_FRACTIONS["shank"] * self.shank_scale,
            "thigh": BASE_MASS_FRACTIONS["thigh"] * self.thigh_scale,
            "trunk": BASE_MASS_FRACTIONS["trunk"] * self.trunk_scale,
        }
        total = sum(weighted.values())
        return {key: value / total for key, value in weighted.items()}

    @property
    def scaling_rule(self) -> str:
        if self.scaling_mode == "longueur seule":
            return "longueurs variables; masses et inerties de reference conservees"
        return (
            "hypothese didactique de densite lineique constante; masses "
            "renormalisees a la masse corporelle; inerties m(kL)^2 recalculees"
        )

    def _segment_mass(self, key: str) -> float:
        return self.segment_mass_fractions[key] * self.body_mass

    def _inertia_scale(self, length_scale: float, profile_scale: float = 1.0) -> float:
        if self.scaling_mode == "longueur seule":
            return profile_scale / (length_scale * length_scale)
        return profile_scale

    @property
    def foot(self) -> SegmentSpec:
        return SegmentSpec(
            "pied",
            0.152 * self.height * self.foot_scale,
            self._segment_mass("foot"),
            0.50,
            0.475,
            inertia_scale=self._inertia_scale(self.foot_scale),
        )

    @property
    def shank(self) -> SegmentSpec:
        # Winter/Dempster gives the longitudinal CoM from the knee, whereas
        # this chain constructs the shank from the ankle towards the knee.
        return SegmentSpec(
            "jambe",
            0.246 * self.height * self.shank_scale,
            self._segment_mass("shank"),
            1.0 - 0.433,
            0.302,
            inertia_scale=self._inertia_scale(self.shank_scale),
        )

    @property
    def thigh(self) -> SegmentSpec:
        # Winter/Dempster gives the longitudinal CoM from the hip, whereas
        # this chain constructs the thigh from the knee towards the hip.
        return SegmentSpec(
            "cuisse",
            0.245 * self.height * self.thigh_scale,
            self._segment_mass("thigh"),
            1.0 - 0.433,
            0.323,
            inertia_scale=self._inertia_scale(self.thigh_scale),
        )

    @property
    def trunk(self) -> SegmentSpec:
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
            self._segment_mass("trunk"),
            hold_fraction,
            0.496,
            com_anterior_offset=hold_offset + pregnancy_offset,
            inertia_scale=self._inertia_scale(self.trunk_scale, inertia_scale),
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
    def foot_com_transverse_offset(self) -> float:
        return 0.025

    @property
    def wedge_angle(self) -> float:
        return radians(self.wedge_angle_deg)

    @property
    def bar_anterior_offset(self) -> float:
        return physical_bar_offsets(
            self.trunk.length, self.subject_profile, self.bar_position
        )[0]

    @property
    def bar_longitudinal_offset(self) -> float:
        return physical_bar_offsets(
            self.trunk.length, self.subject_profile, self.bar_position
        )[1]


def scale_from_percent(percent: float) -> float:
    return 1.0 + percent / 100.0
