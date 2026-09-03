"""Analytical generalized forces and joint-moment decomposition."""

from __future__ import annotations

from .anthropometry import Anthropometry
from .kinematics import (
    MotionState,
    Vector,
    angle_derivative_vector,
    com_accelerations,
    cross_z,
    dot,
    local_angle_derivative_vector,
    sub,
)
from .torque_capacity import GRAVITY

JOINT_NAMES = ("cheville", "genou", "hanche")


def _segment_forces(
    anthro: Anthropometry,
    state: MotionState,
    include_velocity: bool,
    include_acceleration: bool,
    include_gravity: bool,
) -> dict[str, Vector]:
    qdot = state.qdot if include_velocity else (0.0, 0.0, 0.0)
    qddot = state.qddot if include_acceleration else (0.0, 0.0, 0.0)
    accs = com_accelerations(anthro, state.q, qdot, qddot)
    gravity = GRAVITY if include_gravity else 0.0
    return {
        "foot": (
            anthro.foot.mass * accs["foot"][0],
            anthro.foot.mass * (accs["foot"][1] + gravity),
        ),
        "shank": (
            anthro.shank.mass * accs["shank"][0],
            anthro.shank.mass * (accs["shank"][1] + gravity),
        ),
        "thigh": (
            anthro.thigh.mass * accs["thigh"][0],
            anthro.thigh.mass * (accs["thigh"][1] + gravity),
        ),
        "trunk": (
            anthro.trunk.mass * accs["trunk"][0],
            anthro.trunk.mass * (accs["trunk"][1] + gravity),
        ),
        "bar": (
            anthro.bar_mass * accs["bar"][0],
            anthro.bar_mass * (accs["bar"][1] + gravity),
        ),
    }


def _jacobians(anthro: Anthropometry, state: MotionState) -> dict[str, list[Vector]]:
    shank_angle, thigh_angle, trunk_angle = tuple(
        angle + anthro.wedge_angle for angle in state.q
    )
    shank = anthro.shank
    thigh = anthro.thigh
    trunk = anthro.trunk
    zero = (0.0, 0.0)
    dknee_ds = angle_derivative_vector(shank_angle, shank.length)
    dhip_ds = dknee_ds
    dhip_dt = angle_derivative_vector(thigh_angle, thigh.length)
    dshoulder_ds = dhip_ds
    dshoulder_dt = dhip_dt
    dshoulder_dr = angle_derivative_vector(trunk_angle, trunk.length)
    return {
        "foot": [zero, zero, zero],
        "shank": [
            angle_derivative_vector(shank_angle, shank.length * shank.com_fraction),
            zero,
            zero,
        ],
        "thigh": [
            dknee_ds,
            angle_derivative_vector(thigh_angle, thigh.length * thigh.com_fraction),
            zero,
        ],
        "trunk": [
            dhip_ds,
            dhip_dt,
            local_angle_derivative_vector(
                trunk_angle,
                trunk.com_anterior_offset,
                trunk.length * trunk.com_fraction,
            ),
        ],
        "bar": [
            dshoulder_ds,
            dshoulder_dt,
            (
                dshoulder_dr[0]
                + local_angle_derivative_vector(
                    trunk_angle,
                    anthro.bar_anterior_offset,
                    anthro.bar_longitudinal_offset,
                )[0],
                dshoulder_dr[1]
                + local_angle_derivative_vector(
                    trunk_angle,
                    anthro.bar_anterior_offset,
                    anthro.bar_longitudinal_offset,
                )[1],
            ),
        ],
    }


def _absolute_generalized_torque(
    anthro: Anthropometry,
    state: MotionState,
    include_velocity: bool,
    include_acceleration: bool,
    include_gravity: bool,
) -> tuple[float, float, float]:
    forces = _segment_forces(
        anthro, state, include_velocity, include_acceleration, include_gravity
    )
    jacobians = _jacobians(anthro, state)
    absolute = [0.0, 0.0, 0.0]
    for name, force in forces.items():
        for index, jacobian in enumerate(jacobians[name]):
            absolute[index] += dot(jacobian, force)
    if include_acceleration:
        absolute[0] += anthro.shank.inertia * state.qddot[0]
        absolute[1] += anthro.thigh.inertia * state.qddot[1]
        absolute[2] += anthro.trunk.inertia * state.qddot[2]
    return (absolute[0], absolute[1], absolute[2])


def _joint_from_absolute(absolute: tuple[float, float, float]) -> dict[str, float]:
    shank, thigh, trunk = absolute
    return {
        "cheville": shank + thigh + trunk,
        "genou": thigh + trunk,
        "hanche": trunk,
    }


def _contact_moments(
    state: MotionState, reaction: Vector, cop_x: float
) -> dict[str, float]:
    """Return GRF moments in the historical subtractive convention."""

    cop = (cop_x, 0.0)
    return {
        "cheville": -cross_z(sub(cop, state.pose.ankle), reaction),
        "genou": -cross_z(sub(cop, state.pose.knee), reaction),
        "hanche": -cross_z(sub(cop, state.pose.hip), reaction),
    }


def _subtract_joint_terms(
    minuend: dict[str, float],
    subtrahend: dict[str, float],
) -> dict[str, float]:
    return {joint: minuend[joint] - subtrahend[joint] for joint in JOINT_NAMES}


def _sum_joint_terms(*terms: dict[str, float]) -> dict[str, float]:
    return {joint: sum(term[joint] for term in terms) for joint in JOINT_NAMES}


def _analytical_inverse_dynamics_decomposition(
    anthro: Anthropometry,
    state: MotionState,
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    """Return fixed-foot analytical terms in joint-moment coordinates."""

    mass_acceleration = _joint_from_absolute(
        _absolute_generalized_torque(
            anthro,
            state,
            include_velocity=False,
            include_acceleration=True,
            include_gravity=False,
        )
    )
    velocity = _joint_from_absolute(
        _absolute_generalized_torque(
            anthro,
            state,
            include_velocity=True,
            include_acceleration=False,
            include_gravity=False,
        )
    )
    gravity = _joint_from_absolute(
        _absolute_generalized_torque(
            anthro,
            state,
            include_velocity=False,
            include_acceleration=False,
            include_gravity=True,
        )
    )
    return mass_acceleration, velocity, gravity
