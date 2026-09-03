"""Pure interaction rules for the deep-squat pose editor."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import atan2, degrees, isfinite, radians

from .kinematics import (
    CLINICAL_JOINT_LIMITS_DEG,
    Pose,
    Vector,
    clinical_joint_values_from_segment_values,
    segment_values_from_clinical_joint_values,
)

SegmentAngles = tuple[float, float, float]

CLINICAL_JOINT_LABELS = {
    "cheville": "Cheville (dorsiflexion)",
    "genou": "Genou (flexion)",
    "hanche": "Hanche (flexion)",
}
HANDLE_NAMES = ("knee", "hip", "shoulder")


@dataclass(frozen=True)
class ClinicalAngleEditorSpec:
    """Text and value displayed by the precise angle editor."""

    joint: str
    label: str
    lower_deg: float
    upper_deg: float
    value_deg: float

    @property
    def display_label(self) -> str:
        return f"{self.label} — {self.lower_deg:g} à {self.upper_deg:g} deg"


@dataclass(frozen=True)
class ClinicalAngleUpdate:
    """Result of parsing and applying a precise clinical angle value."""

    accepted: bool
    q: SegmentAngles | None = None
    bounded_deg: float | None = None
    error_message: str | None = None

    @property
    def was_clamped(self) -> bool:
        return (
            self.accepted
            and self.bounded_deg is not None
            and self.requested_deg is not None
            and self.bounded_deg != self.requested_deg
        )

    requested_deg: float | None = None


def format_pose_angle(value: float) -> str:
    """Format a precise degree value without insignificant zeroes."""

    return f"{value:.2f}".rstrip("0").rstrip(".")


def nearest_named_point(
    x: float,
    y: float,
    candidates: Mapping[str, Vector],
    *,
    radius_px: float = 20.0,
) -> str | None:
    """Return the first named target within the editor's hit radius."""

    for name, (px, py) in candidates.items():
        if (px - x) ** 2 + (py - y) ** 2 < radius_px**2:
            return name
    return None


def clamp_segment_angles(q: SegmentAngles) -> SegmentAngles:
    """Keep the segment orientations within the displayed clinical limits."""

    ankle = max(radians(-30.0), min(radians(40.0), q[0]))
    knee = max(radians(-140.0), min(radians(0.0), q[1] - ankle))
    thigh = ankle + knee
    hip = max(radians(-15.0), min(radians(120.0), q[2] - thigh))
    return (ankle, thigh, thigh + hip)


def drag_updated_q(
    q: SegmentAngles,
    handle: str,
    point: Vector,
    pose: Pose,
) -> SegmentAngles:
    """Rotate exactly one segment from a dragged pose handle and clamp it."""

    shank, thigh, trunk = q
    if handle == "knee":
        dx = point[0] - pose.ankle[0]
        dy = point[1] - pose.ankle[1]
        shank = atan2(dx, dy)
    elif handle == "hip":
        dx = point[0] - pose.knee[0]
        dy = point[1] - pose.knee[1]
        thigh = atan2(dx, dy)
    elif handle == "shoulder":
        dx = point[0] - pose.hip[0]
        dy = point[1] - pose.hip[1]
        trunk = atan2(dx, dy)
    return clamp_segment_angles((shank, thigh, trunk))


def clinical_joint_angles_deg(q: SegmentAngles) -> tuple[float, float, float]:
    """Return ankle, knee and hip values in the GUI's clinical convention."""

    values = clinical_joint_values_from_segment_values(q)
    return (
        degrees(values["cheville"]),
        degrees(values["genou"]),
        degrees(values["hanche"]),
    )


def clinical_angle_editor_spec(
    joint: str, q: SegmentAngles
) -> ClinicalAngleEditorSpec:
    """Return the label, limits and current value for one clinical joint."""

    if joint not in CLINICAL_JOINT_LABELS:
        raise KeyError(joint)
    values = clinical_joint_values_from_segment_values(q)
    lower, upper = CLINICAL_JOINT_LIMITS_DEG[joint]
    return ClinicalAngleEditorSpec(
        joint=joint,
        label=CLINICAL_JOINT_LABELS[joint],
        lower_deg=lower,
        upper_deg=upper,
        value_deg=degrees(values[joint]),
    )


def apply_clinical_angle(
    q: SegmentAngles, joint: str, raw_value: str
) -> ClinicalAngleUpdate:
    """Validate a user-entered angle and return a new clamped pose on success."""

    try:
        requested = float(raw_value.strip().replace(",", "."))
    except (AttributeError, TypeError, ValueError):
        return ClinicalAngleUpdate(
            accepted=False,
            error_message=(
                f"angle invalide ({joint}) : entrez une valeur numérique en degrés"
            ),
        )
    if not isfinite(requested):
        return ClinicalAngleUpdate(
            accepted=False,
            error_message=(
                f"angle invalide ({joint}) : entrez une valeur numérique en degrés"
            ),
        )
    if joint not in CLINICAL_JOINT_LABELS:
        raise KeyError(joint)
    lower, upper = CLINICAL_JOINT_LIMITS_DEG[joint]
    bounded = max(lower, min(upper, requested))
    values = clinical_joint_values_from_segment_values(q)
    values[joint] = radians(bounded)
    updated_q = clamp_segment_angles(
        segment_values_from_clinical_joint_values(
            values["cheville"], values["genou"], values["hanche"]
        )
    )
    return ClinicalAngleUpdate(
        accepted=True,
        q=updated_q,
        bounded_deg=bounded,
        requested_deg=requested,
    )
