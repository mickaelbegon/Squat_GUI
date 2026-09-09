"""Experimental analytical estimate of patellofemoral loading.

The model is deliberately small and transparent.  It combines the net knee
extension moment from inverse dynamics with published angle-dependent
regressions for the quadriceps moment arm, patellar mechanism and contact area.
It is intended for teaching and within-condition comparisons, not diagnosis.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import radians, sin

from .torque_capacity import GRAVITY


MODEL_NAME = "analytique 2D moment-angle (expérimental)"
DIRECT_VALIDITY_MAX_FLEXION_DEG = 90.0


@dataclass(frozen=True)
class PatellofemoralEstimate:
    """Per-knee outputs of the simplified patellofemoral model."""

    knee_flexion_deg: float
    knee_extension_moment_per_side_Nm: float
    quadriceps_moment_arm_m: float
    quadriceps_force_per_side_N: float
    reaction_force_per_side_N: float
    reaction_force_body_weight_ratio: float
    contact_area_mm2: float
    stress_MPa: float
    extrapolated: bool
    validity: str
    model: str = MODEL_NAME


def quadriceps_moment_arm_m(knee_flexion_deg: float) -> float:
    """Return the published piecewise effective quadriceps lever arm."""

    angle = max(0.0, float(knee_flexion_deg))
    if angle < 30.0:
        arm_cm = 0.036 * angle + 3.0
    elif angle < 60.0:
        arm_cm = -0.043 * angle + 5.4
    elif angle < DIRECT_VALIDITY_MAX_FLEXION_DEG:
        arm_cm = -0.027 * angle + 4.3
    else:
        arm_cm = 2.0
    return arm_cm / 100.0


def patellar_mechanism_angle_deg(knee_flexion_deg: float) -> float:
    """Return the angle between quadriceps and patellar-tendon force lines."""

    return 30.46 + 0.53 * max(0.0, float(knee_flexion_deg))


def patellofemoral_contact_area_mm2(knee_flexion_deg: float) -> float:
    """Return the generic angle-dependent patellofemoral contact area."""

    angle = max(0.0, float(knee_flexion_deg))
    return 0.0781 * angle**2 + 0.6763 * angle + 151.75


def estimate_patellofemoral_load(
    knee_flexion_deg: float,
    combined_knee_extension_moment_Nm: float,
    body_mass_kg: float,
    *,
    side_count: int = 2,
) -> PatellofemoralEstimate:
    """Estimate force and mean contact stress for one knee.

    Squat GUI's planar anthropometry combines both lower limbs.  The default
    therefore divides the net model moment equally between two knees.  A
    negative net extension moment is not interpreted as quadriceps compression
    and contributes zero force in this simplified model.
    """

    if body_mass_kg <= 0.0:
        raise ValueError("La masse corporelle doit être strictement positive.")
    if side_count <= 0:
        raise ValueError("Le nombre de côtés doit être strictement positif.")

    angle = max(0.0, float(knee_flexion_deg))
    extension_moment = max(0.0, float(combined_knee_extension_moment_Nm))
    moment_per_side = extension_moment / side_count
    moment_arm = quadriceps_moment_arm_m(angle)
    quadriceps_force = moment_per_side / moment_arm
    mechanism_angle = patellar_mechanism_angle_deg(angle)
    reaction_force = 2.0 * quadriceps_force * sin(radians(mechanism_angle / 2.0))
    contact_area = patellofemoral_contact_area_mm2(angle)
    stress = reaction_force / contact_area
    extrapolated = angle > DIRECT_VALIDITY_MAX_FLEXION_DEG
    validity = (
        "extrapolation_flexion_profonde"
        if extrapolated
        else "plage_directe_0_90_deg"
    )
    return PatellofemoralEstimate(
        knee_flexion_deg=angle,
        knee_extension_moment_per_side_Nm=moment_per_side,
        quadriceps_moment_arm_m=moment_arm,
        quadriceps_force_per_side_N=quadriceps_force,
        reaction_force_per_side_N=reaction_force,
        reaction_force_body_weight_ratio=reaction_force
        / (body_mass_kg * GRAVITY),
        contact_area_mm2=contact_area,
        stress_MPa=stress,
        extrapolated=extrapolated,
        validity=validity,
    )
