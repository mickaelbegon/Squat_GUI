"""Centre-of-mass aggregation and analytical ground reactions."""

from __future__ import annotations

from .anthropometry import Anthropometry
from .kinematics import MotionState, Vector, com_accelerations, cross_z
from .torque_capacity import GRAVITY


def _mass_weighted_segment_vector(
    anthro: Anthropometry, values: dict[str, Vector]
) -> Vector:
    foot = anthro.foot
    shank = anthro.shank
    thigh = anthro.thigh
    trunk = anthro.trunk
    total = anthro.total_mass
    ax = (
        foot.mass * values["foot"][0]
        + shank.mass * values["shank"][0]
        + thigh.mass * values["thigh"][0]
        + trunk.mass * values["trunk"][0]
        + anthro.bar_mass * values["bar"][0]
    ) / total
    ay = (
        foot.mass * values["foot"][1]
        + shank.mass * values["shank"][1]
        + thigh.mass * values["thigh"][1]
        + trunk.mass * values["trunk"][1]
        + anthro.bar_mass * values["bar"][1]
    ) / total
    return (ax, ay)


def total_com_velocity(anthro: Anthropometry, velocities: dict[str, Vector]) -> Vector:
    """Return the whole-system centre-of-mass velocity."""

    return _mass_weighted_segment_vector(anthro, velocities)


def total_com_acceleration(
    anthro: Anthropometry, accelerations: dict[str, Vector]
) -> Vector:
    """Return the whole-system centre-of-mass acceleration."""

    return _mass_weighted_segment_vector(anthro, accelerations)


def ground_reaction_and_cop(
    anthro: Anthropometry, state: MotionState
) -> tuple[Vector, float, Vector, float]:
    """Compute analytical ground reaction, CoP and dynamic moment."""

    accs = com_accelerations(anthro, state.q, state.qdot, state.qddot)
    com_acc = total_com_acceleration(anthro, accs)
    reaction = (
        anthro.total_mass * com_acc[0],
        anthro.total_mass * (com_acc[1] + GRAVITY),
    )

    inertial_moment = 0.0
    segment_data = [
        (anthro.foot, state.pose.segment_coms["foot"], accs["foot"], 0.0),
        (anthro.shank, state.pose.segment_coms["shank"], accs["shank"], state.qddot[0]),
        (anthro.thigh, state.pose.segment_coms["thigh"], accs["thigh"], state.qddot[1]),
        (anthro.trunk, state.pose.segment_coms["trunk"], accs["trunk"], state.qddot[2]),
    ]
    if anthro.bar_mass > 0.0:
        segment_data.append((None, state.pose.segment_coms["bar"], accs["bar"], 0.0))

    for segment, com, acc, alpha in segment_data:
        mass = anthro.bar_mass if segment is None else segment.mass
        inertia = 0.0 if segment is None else segment.inertia
        effective_force = (mass * acc[0], mass * (acc[1] + GRAVITY))
        inertial_moment += cross_z(com, effective_force) + inertia * alpha

    cop_x = (
        inertial_moment / reaction[1]
        if abs(reaction[1]) > 1e-9
        else state.pose.ankle[0]
    )
    return reaction, cop_x, com_acc, inertial_moment
