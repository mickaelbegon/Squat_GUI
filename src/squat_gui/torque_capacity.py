"""Joint torque-capacity domain model, independent from inverse dynamics.

This module contains the Anderson angle-velocity surface and the condition
torque presets. It depends only on kinematics, so analytical and biorbd
inverse-dynamics paths can consume the same capacity model without a cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi

from .kinematics import (
    MotionState,
    joint_angles_from_pose,
    joint_values_from_segment_values,
)


GRAVITY = 9.80665
JOINTS = ("cheville", "genou", "hanche")


@dataclass(frozen=True)
class AndersonTorqueParameters:
    c1: float
    c2: float
    c3: float
    c4: float
    c5: float
    c6: float


@dataclass(frozen=True)
class TorqueCapacity:
    """Active joint-torque capacity under the selected model assumptions."""

    available_torque_Nm: float
    base_torque_Nm: float
    angle_rad: float
    angular_velocity_rad_s: float
    angle_factor: float
    velocity_factor: float
    regime: str
    angle_in_domain: bool
    regime_source: str = "signe de la puissance articulaire tau*omega"
    model: str = (
        "surface active angle-vitesse Anderson appliquée au couple de base "
        "de la condition"
    )
    source: str = (
        "surface: doi:10.1016/j.jbiomech.2007.03.022; amplitude de base: "
        "torque_preset et max_*_Nm de la condition"
    )


@dataclass(frozen=True)
class TorquePreset:
    name: str
    torques: dict[str, float]
    source: str


ANDERSON_2007_YOUNG_MALE = {
    "cheville": AndersonTorqueParameters(
        c1=0.095, c2=1.391, c3=0.408, c4=0.987, c5=3.558, c6=0.295
    ),  # ankle plantar flexion
    "genou": AndersonTorqueParameters(
        c1=0.163, c2=1.258, c3=1.133, c4=1.517, c5=3.952, c6=0.095
    ),  # knee extension
    "hanche": AndersonTorqueParameters(
        c1=0.161, c2=0.958, c3=0.932, c4=1.578, c5=3.190, c6=0.242
    ),  # hip extension
}

ATHLETE_REFERENCE_TORQUES_PER_KG = {
    "cheville": (104.9 + 100.0)
    / 62.6,  # So et al. 1994, soccer players, PF at 60 deg/s
    "genou": 3.55
    + 3.55,  # Keytsman et al. 2024, elite soccer, quadriceps isometric at 90 deg
    "hanche": 2.36 + 2.35,  # female footballers, hip extension at 30 deg after training
}


def anderson_reference_max_torques(
    body_mass: float, height: float, side_count: int = 2
) -> dict[str, float]:
    body_weight_height = body_mass * GRAVITY * height
    return {
        joint: side_count * params.c1 * body_weight_height
        for joint, params in ANDERSON_2007_YOUNG_MALE.items()
    }


def athlete_reference_max_torques(body_mass: float) -> dict[str, float]:
    return {
        joint: factor * body_mass
        for joint, factor in ATHLETE_REFERENCE_TORQUES_PER_KG.items()
    }


def torque_presets(body_mass: float, height: float) -> dict[str, TorquePreset]:
    return {
        "Anderson actif x2": TorquePreset(
            "Anderson actif x2",
            anderson_reference_max_torques(body_mass, height),
            "Anderson et al. 2007, homme actif 18-25 ans, valeurs par membre sommees gauche+droite",
        ),
        "Sportifs": TorquePreset(
            "Sportifs",
            athlete_reference_max_torques(body_mass),
            "Cheville: So et al. 1994; genou: Keytsman et al. 2024; hanche: footballers PLOS One 2026",
        ),
    }


def anderson_angle_factor(joint: str, angle: float) -> float:
    """Return Anderson's active angle multiplier for a flexion-positive angle.

    The active cosine is zero outside its positive lobe. No physiological
    capacity floor is invented outside that domain.
    """

    params = ANDERSON_2007_YOUNG_MALE[joint]
    phase = params.c2 * (angle - params.c3)
    if abs(phase) >= pi / 2.0:
        return 0.0
    return cos(phase)


def anderson_angle_domain(joint: str) -> tuple[float, float]:
    params = ANDERSON_2007_YOUNG_MALE[joint]
    half_width = pi / (2.0 * params.c2)
    return params.c3 - half_width, params.c3 + half_width


def anderson_velocity_factor(joint: str, angular_velocity: float) -> float:
    """Return Anderson's active torque-velocity multiplier.

    ``angular_velocity`` is positive for concentric shortening and negative
    for eccentric lengthening of the tested muscle group, in rad/s.
    """

    params = ANDERSON_2007_YOUNG_MALE[joint]
    speed = abs(angular_velocity)
    numerator = 2.0 * params.c4 * params.c5 + speed * (
        params.c5 - 3.0 * params.c4
    )
    denominator = 2.0 * params.c4 * params.c5 + speed * (
        2.0 * params.c5 - 4.0 * params.c4
    )
    if denominator <= 0.0:
        return 0.0
    concentric_surface = max(0.0, numerator / denominator)
    if angular_velocity < 0.0:
        return concentric_surface * (1.0 - params.c6 * angular_velocity)
    return concentric_surface


def angle_adapted_max(
    base_max: float, angle: float, enabled: bool, joint: str | None = None
) -> float:
    if not enabled or joint is None:
        return base_max
    return base_max * anderson_angle_factor(joint, angle)


def joint_angles_for_limits(state: MotionState) -> dict[str, float]:
    gui_angles = joint_angles_from_pose(state.pose)
    # Anderson: flexion/dorsiflexion positive. Squat_GUI retains its historical
    # negative knee-flexion convention, hence the single sign inversion below.
    return {
        "cheville": gui_angles["cheville"],
        "genou": -gui_angles["genou"],
        "hanche": gui_angles["hanche"],
    }


def joint_velocities_for_limits(
    state: MotionState,
    joint_powers: dict[str, float] | None = None,
) -> dict[str, float]:
    """Return velocities in the direction of the modeled extensor/PF effort."""

    gui_velocities = joint_values_from_segment_values(state.qdot)
    exertion_velocities = {
        "cheville": -gui_velocities["cheville"],
        "genou": gui_velocities["genou"],
        "hanche": -gui_velocities["hanche"],
    }
    if joint_powers is None:
        return exertion_velocities
    # Couple and kinematic coordinate signs are backend conventions. Deriving
    # the contraction regime from tau*omega keeps the capacity surface exactly
    # coherent with the power reported by the GUI: generating is concentric,
    # absorbing is eccentric. The speed magnitude remains the measured joint
    # angular speed.
    for joint, gui_velocity in gui_velocities.items():
        speed = abs(gui_velocity)
        power = joint_powers[joint]
        if speed < 1e-12 or abs(power) < 1e-12:
            exertion_velocities[joint] = 0.0
        else:
            exertion_velocities[joint] = speed if power > 0.0 else -speed
    return exertion_velocities


def joint_torque_capacities(
    state: MotionState,
    max_torques: dict[str, float],
    adapt_max_by_angle: bool,
    adapt_max_by_velocity: bool = True,
    joint_powers: dict[str, float] | None = None,
) -> dict[str, TorqueCapacity]:
    angles = joint_angles_for_limits(state)
    velocities = joint_velocities_for_limits(state, joint_powers)
    capacities: dict[str, TorqueCapacity] = {}
    for joint in JOINTS:
        angle = angles[joint]
        velocity = velocities[joint]
        lower, upper = anderson_angle_domain(joint)
        angle_in_domain = lower < angle < upper
        angle_factor = (
            anderson_angle_factor(joint, angle) if adapt_max_by_angle else 1.0
        )
        velocity_factor = (
            anderson_velocity_factor(joint, velocity)
            if adapt_max_by_velocity
            else 1.0
        )
        if abs(velocity) < 1e-12:
            regime = "isometrique"
        elif velocity > 0.0:
            regime = "concentrique"
        else:
            regime = "excentrique"
        capacities[joint] = TorqueCapacity(
            available_torque_Nm=max_torques[joint] * angle_factor * velocity_factor,
            base_torque_Nm=max_torques[joint],
            angle_rad=angle,
            angular_velocity_rad_s=velocity,
            angle_factor=angle_factor,
            velocity_factor=velocity_factor,
            regime=regime,
            angle_in_domain=angle_in_domain,
        )
    return capacities


def available_joint_torque_limits(
    state: MotionState,
    max_torques: dict[str, float],
    adapt_max_by_angle: bool,
    adapt_max_by_velocity: bool = True,
) -> dict[str, float]:
    return {
        joint: capacity.available_torque_Nm
        for joint, capacity in joint_torque_capacities(
            state,
            max_torques,
            adapt_max_by_angle,
            adapt_max_by_velocity,
        ).items()
    }
