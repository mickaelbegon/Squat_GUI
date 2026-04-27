"""Analytical 2D inverse dynamics for the first GUI iteration."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp

from .anthropometry import Anthropometry
from .kinematics import (
    MotionState,
    Vector,
    angle_derivative_vector,
    com_accelerations,
    cross_z,
    dot,
    motion_state,
    sub,
)


GRAVITY = 9.80665


@dataclass(frozen=True)
class DynamicsResult:
    ground_reaction: Vector
    cop_x: float
    torques: dict[str, float]
    torque_components: dict[str, dict[str, float]]
    powers: dict[str, float]
    effort_ratios: dict[str, float]


def total_com_acceleration(anthro: Anthropometry, accs: dict[str, Vector]) -> Vector:
    foot = anthro.foot
    shank = anthro.shank
    thigh = anthro.thigh
    trunk = anthro.trunk
    total = anthro.total_mass
    ax = (
        foot.mass * accs["foot"][0]
        + shank.mass * accs["shank"][0]
        + thigh.mass * accs["thigh"][0]
        + trunk.mass * accs["trunk"][0]
        + anthro.bar_mass * accs["bar"][0]
    ) / total
    ay = (
        foot.mass * accs["foot"][1]
        + shank.mass * accs["shank"][1]
        + thigh.mass * accs["thigh"][1]
        + trunk.mass * accs["trunk"][1]
        + anthro.bar_mass * accs["bar"][1]
    ) / total
    return (ax, ay)


def ground_reaction_and_cop(anthro: Anthropometry, state: MotionState) -> tuple[Vector, float]:
    accs = com_accelerations(anthro, state.q, state.qdot, state.qddot)
    com_acc = total_com_acceleration(anthro, accs)
    reaction = (anthro.total_mass * com_acc[0], anthro.total_mass * (com_acc[1] + GRAVITY))

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

    cop_x = inertial_moment / reaction[1] if abs(reaction[1]) > 1e-9 else state.pose.ankle[0]
    return reaction, cop_x


def _segment_forces(
    anthro: Anthropometry,
    state: MotionState,
    include_velocity: bool,
    include_acceleration: bool,
    include_gravity: bool,
) -> dict[str, Vector]:
    qdot = state.qdot if include_velocity else (0.0, 0.0, 0.0)
    qddot = state.qddot if include_acceleration else (0.0, 0.0, 0.0)
    accs = com_accelerations(
        anthro,
        state.q,
        qdot,
        qddot,
    )
    gravity = GRAVITY if include_gravity else 0.0
    return {
        "foot": (anthro.foot.mass * accs["foot"][0], anthro.foot.mass * (accs["foot"][1] + gravity)),
        "shank": (anthro.shank.mass * accs["shank"][0], anthro.shank.mass * (accs["shank"][1] + gravity)),
        "thigh": (anthro.thigh.mass * accs["thigh"][0], anthro.thigh.mass * (accs["thigh"][1] + gravity)),
        "trunk": (anthro.trunk.mass * accs["trunk"][0], anthro.trunk.mass * (accs["trunk"][1] + gravity)),
        "bar": (anthro.bar_mass * accs["bar"][0], anthro.bar_mass * (accs["bar"][1] + gravity)),
    }


def _jacobians(anthro: Anthropometry, state: MotionState) -> dict[str, list[Vector]]:
    shank_angle, thigh_angle, trunk_angle = state.q
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
        "shank": [angle_derivative_vector(shank_angle, shank.length * shank.com_fraction), zero, zero],
        "thigh": [dknee_ds, angle_derivative_vector(thigh_angle, thigh.length * thigh.com_fraction), zero],
        "trunk": [dhip_ds, dhip_dt, angle_derivative_vector(trunk_angle, trunk.length * trunk.com_fraction)],
        "bar": [dshoulder_ds, dshoulder_dt, dshoulder_dr],
    }


def _absolute_generalized_torque(
    anthro: Anthropometry,
    state: MotionState,
    include_velocity: bool,
    include_acceleration: bool,
    include_gravity: bool,
) -> tuple[float, float, float]:
    forces = _segment_forces(anthro, state, include_velocity, include_acceleration, include_gravity)
    jacobians = _jacobians(anthro, state)
    absolute = [0.0, 0.0, 0.0]
    for name, force in forces.items():
        for index, jac in enumerate(jacobians[name]):
            absolute[index] += dot(jac, force)
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


def _contact_moments(state: MotionState, reaction: Vector, cop_x: float) -> dict[str, float]:
    cop = (cop_x, 0.0)
    return {
        "cheville": cross_z(sub(cop, state.pose.ankle), reaction),
        "genou": cross_z(sub(cop, state.pose.knee), reaction),
        "hanche": cross_z(sub(cop, state.pose.hip), reaction),
    }


def angle_adapted_max(base_max: float, angle: float, enabled: bool) -> float:
    if not enabled:
        return base_max
    return base_max * (0.55 + 0.45 * exp(-((angle - 0.75) / 0.75) ** 2))


def inverse_dynamics(
    anthro: Anthropometry,
    state: MotionState,
    max_torques: dict[str, float],
    adapt_max_by_angle: bool,
) -> DynamicsResult:
    reaction, cop_x = ground_reaction_and_cop(anthro, state)
    inertial_abs = _absolute_generalized_torque(
        anthro,
        state,
        include_velocity=False,
        include_acceleration=True,
        include_gravity=False,
    )
    nle_abs = _absolute_generalized_torque(
        anthro,
        state,
        include_velocity=True,
        include_acceleration=False,
        include_gravity=True,
    )
    total_abs = tuple(inertial_abs[i] + nle_abs[i] for i in range(3))
    torques = _joint_from_absolute(total_abs)
    inertial = _joint_from_absolute(inertial_abs)
    nle = _joint_from_absolute(nle_abs)
    contact = _contact_moments(state, reaction, cop_x)
    components = {
        joint: {
            "Mqddot": inertial[joint],
            "NLeffects": nle[joint],
            "contact": contact[joint],
        }
        for joint in torques
    }
    joint_velocities = {
        "cheville": state.qdot[0],
        "genou": state.qdot[1] - state.qdot[0],
        "hanche": state.qdot[2] - state.qdot[1],
    }
    powers = {joint: torques[joint] * joint_velocities[joint] for joint in torques}
    joint_angles = {
        "cheville": abs(state.q[0]),
        "genou": abs(state.q[1] - state.q[0]),
        "hanche": abs(state.q[2] - state.q[1]),
    }
    effort_ratios = {}
    for joint, torque in torques.items():
        eccentric_factor = 1.35 if state.phase == "excentrique" else 1.0
        adjusted = max(
            1.0,
            eccentric_factor * angle_adapted_max(max_torques[joint], joint_angles[joint], adapt_max_by_angle),
        )
        effort_ratios[joint] = abs(torque) / adjusted
    return DynamicsResult(reaction, cop_x, torques, components, powers, effort_ratios)


def simulate(
    anthro: Anthropometry,
    final_q: tuple[float, float, float],
    duration: float,
    frame_count: int,
    max_torques: dict[str, float],
    adapt_max_by_angle: bool,
) -> tuple[list[MotionState], list[DynamicsResult]]:
    states: list[MotionState] = []
    dynamics: list[DynamicsResult] = []
    for index in range(frame_count):
        time = duration * index / max(1, frame_count - 1)
        state = motion_state(anthro, final_q, duration, time)
        states.append(state)
        dynamics.append(inverse_dynamics(anthro, state, max_torques, adapt_max_by_angle))
    return states, dynamics
