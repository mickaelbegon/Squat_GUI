"""Analytical 2D inverse dynamics for the first GUI iteration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import cos
from typing import Any

from .anthropometry import Anthropometry
from .kinematics import (
    MotionState,
    Pose,
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
class AndersonTorqueParameters:
    c1: float
    c2: float
    c3: float


@dataclass(frozen=True)
class TorquePreset:
    name: str
    torques: dict[str, float]
    source: str


ANDERSON_2007_YOUNG_MALE = {
    "cheville": AndersonTorqueParameters(c1=0.095, c2=1.391, c3=0.408),  # ankle plantar flexion
    "genou": AndersonTorqueParameters(c1=0.163, c2=1.258, c3=1.133),  # knee extension
    "hanche": AndersonTorqueParameters(c1=0.161, c2=0.958, c3=0.932),  # hip extension
}


ATHLETE_REFERENCE_TORQUES_PER_KG = {
    "cheville": (104.9 + 100.0) / 62.6,  # So et al. 1994, soccer players, PF at 60 deg/s
    "genou": 3.55 + 3.55,  # Keytsman et al. 2024, elite soccer, quadriceps isometric at 90 deg
    "hanche": 2.36 + 2.35,  # female footballers, hip extension at 30 deg after training
}


@dataclass(frozen=True)
class DynamicsResult:
    ground_reaction: Vector
    cop_x: float
    torques: dict[str, float]
    torque_components: dict[str, dict[str, float]]
    powers: dict[str, float]
    effort_ratios: dict[str, float]
    backend: str = "analytical"
    com: Vector = (0.0, 0.0)
    com_velocity: Vector = (0.0, 0.0)
    com_acceleration: Vector = (0.0, 0.0)
    dynamic_moment_z: float = 0.0


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


def ground_reaction_and_cop(anthro: Anthropometry, state: MotionState) -> tuple[Vector, float, Vector, float]:
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
    return reaction, cop_x, com_acc, inertial_moment


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
    """Generalized external-contact term to subtract from the inverse-dynamics total."""
    cop = (cop_x, 0.0)
    return {
        "cheville": -cross_z(sub(cop, state.pose.ankle), reaction),
        "genou": -cross_z(sub(cop, state.pose.knee), reaction),
        "hanche": -cross_z(sub(cop, state.pose.hip), reaction),
    }


def anderson_reference_max_torques(body_mass: float, height: float, side_count: int = 2) -> dict[str, float]:
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
    params = ANDERSON_2007_YOUNG_MALE[joint]
    return max(0.05, cos(params.c2 * (angle - params.c3)))


def angle_adapted_max(base_max: float, angle: float, enabled: bool, joint: str | None = None) -> float:
    if not enabled:
        return base_max
    if joint is None:
        return base_max
    return base_max * anderson_angle_factor(joint, angle)


def joint_angles_for_limits(state: MotionState) -> dict[str, float]:
    return {
        "cheville": abs(state.q[0]),
        "genou": abs(state.q[1] - state.q[0]),
        "hanche": abs(state.q[2] - state.q[1]),
    }


def available_joint_torque_limits(
    state: MotionState,
    max_torques: dict[str, float],
    adapt_max_by_angle: bool,
) -> dict[str, float]:
    joint_angles = joint_angles_for_limits(state)
    eccentric_factor = 1.35 if state.phase == "excentrique" else 1.0
    return {
        joint: max(
            1.0,
            eccentric_factor * angle_adapted_max(
                max_torques[joint],
                joint_angles[joint],
                adapt_max_by_angle,
                joint,
            ),
        )
        for joint in ("cheville", "genou", "hanche")
    }


def _joint_torques_from_components(
    total: dict[str, float],
    contact: dict[str, float],
) -> dict[str, float]:
    return {
        joint: total[joint] - contact[joint]
        for joint in ("cheville", "genou", "hanche")
    }


def inverse_dynamics(
    anthro: Anthropometry,
    state: MotionState,
    max_torques: dict[str, float],
    adapt_max_by_angle: bool,
    biorbd_model: Any | None = None,
) -> DynamicsResult:
    reaction, cop_x, com_acceleration, dynamic_moment_z = ground_reaction_and_cop(anthro, state)
    com_velocity = (0.0, 0.0)
    backend = "analytical"
    if biorbd_model is not None:
        reaction, cop_x, com_velocity, com_acceleration, dynamic_moment_z = _biorbd_ground_reaction_and_cop(
            biorbd_model,
            state,
        )
        inverse_dynamics_total, _, _ = _biorbd_joint_torques(biorbd_model, state)
        backend = "biorbd"
    else:
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
        inverse_dynamics_total = _joint_from_absolute(total_abs)
    contact = _contact_moments(state, reaction, cop_x)
    torques = _joint_torques_from_components(inverse_dynamics_total, contact)
    components = {
        joint: {
            "total": inverse_dynamics_total[joint],
            "contact": contact[joint],
            "inertiels_non_lineaires": torques[joint],
        }
        for joint in torques
    }
    joint_velocities = {
        "cheville": state.qdot[0],
        "genou": state.qdot[1] - state.qdot[0],
        "hanche": state.qdot[2] - state.qdot[1],
    }
    powers = {joint: torques[joint] * joint_velocities[joint] for joint in torques}
    available_limits = available_joint_torque_limits(state, max_torques, adapt_max_by_angle)
    effort_ratios = {}
    for joint, torque in torques.items():
        effort_ratios[joint] = abs(torque) / available_limits[joint]
    return DynamicsResult(
        reaction,
        cop_x,
        torques,
        components,
        powers,
        effort_ratios,
        backend,
        state.pose.com,
        com_velocity,
        com_acceleration,
        dynamic_moment_z,
    )


def _biorbd_coordinates(state: MotionState) -> tuple[list[float], list[float], list[float]]:
    q0, q1, q2 = state.q
    qd0, qd1, qd2 = state.qdot
    qdd0, qdd1, qdd2 = state.qddot
    return (
        [-q0, -(q1 - q0), -(q2 - q1)],
        [-qd0, -(qd1 - qd0), -(qd2 - qd1)],
        [-qdd0, -(qdd1 - qdd0), -(qdd2 - qdd1)],
    )


def _numpy_biorbd_coordinates(state: MotionState):
    import numpy as np

    q, qdot, qddot = _biorbd_coordinates(state)
    return np.asarray(q, dtype=float), np.asarray(qdot, dtype=float), np.asarray(qddot, dtype=float)


def _array_from_biorbd(value: Any) -> list[float]:
    array = value.to_array()
    return [float(array[index]) for index in range(len(array))]


def _joint_dict_from_biorbd_tau(tau: list[float]) -> dict[str, float]:
    return {
        "cheville": -tau[0],
        "genou": -tau[1],
        "hanche": -tau[2],
    }


def _biorbd_joint_torques(biorbd_model: Any, state: MotionState) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    import numpy as np

    q, qdot, qddot = _numpy_biorbd_coordinates(state)
    zero = np.zeros(3)
    total = _array_from_biorbd(biorbd_model.InverseDynamics(q, qdot, qddot))
    nle = _array_from_biorbd(biorbd_model.NonLinearEffect(q, qdot))
    inertial_with_static_nle = _array_from_biorbd(biorbd_model.InverseDynamics(q, zero, qddot))
    static_nle = _array_from_biorbd(biorbd_model.NonLinearEffect(q, zero))
    inertial = [inertial_with_static_nle[index] - static_nle[index] for index in range(3)]
    return (
        _joint_dict_from_biorbd_tau(total),
        _joint_dict_from_biorbd_tau(inertial),
        _joint_dict_from_biorbd_tau(nle),
    )


def _biorbd_motion_state_with_com(biorbd_model: Any, state: MotionState) -> MotionState:
    q, _, _ = _numpy_biorbd_coordinates(state)
    com = biorbd_model.CoM(q).to_array()
    pose = replace(state.pose, com=(float(com[0]), float(com[1])))
    return replace(state, pose=pose)


def _biorbd_angular_momentum_derivative_z(biorbd_model: Any, state: MotionState) -> float:
    q, qdot, qddot = _numpy_biorbd_coordinates(state)
    step = 1e-6
    forward = biorbd_model.CalcAngularMomentum(q + step * qdot, qdot + step * qddot, True).to_array()
    backward = biorbd_model.CalcAngularMomentum(q - step * qdot, qdot - step * qddot, True).to_array()
    return float((forward[2] - backward[2]) / (2.0 * step))


def _biorbd_native_cop_x(biorbd_model: Any, q: Any, qdot: Any, qddot: Any) -> float | None:
    zmp_function = getattr(biorbd_model, "CalcZeroMomentPoint", None)
    if zmp_function is None:
        return None
    import numpy as np

    try:
        zmp = zmp_function(q, qdot, qddot, np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 0.0])).to_array()
    except Exception:
        return None
    return float(zmp[0])


def _biorbd_ground_reaction_and_cop(biorbd_model: Any, state: MotionState) -> tuple[Vector, float, Vector, Vector, float]:
    q, qdot, qddot = _numpy_biorbd_coordinates(state)
    mass = float(biorbd_model.mass())
    com = biorbd_model.CoM(q).to_array()
    comdot = biorbd_model.CoMdot(q, qdot).to_array()
    comddot = biorbd_model.CoMddot(q, qdot, qddot).to_array()
    reaction = (mass * float(comddot[0]), mass * (float(comddot[1]) + GRAVITY))
    hdot_com_z = _biorbd_angular_momentum_derivative_z(biorbd_model, state)
    dynamic_moment_z = hdot_com_z + float(com[0]) * reaction[1] - float(com[1]) * reaction[0]
    native_cop_x = _biorbd_native_cop_x(biorbd_model, q, qdot, qddot)
    if native_cop_x is not None:
        cop_x = native_cop_x
    else:
        cop_x = dynamic_moment_z / reaction[1] if abs(reaction[1]) > 1e-9 else state.pose.ankle[0]
    return (
        reaction,
        cop_x,
        (float(comdot[0]), float(comdot[1])),
        (float(comddot[0]), float(comddot[1])),
        dynamic_moment_z,
    )


def simulate(
    anthro: Anthropometry,
    final_q: tuple[float, float, float],
    duration: float,
    frame_count: int,
    max_torques: dict[str, float],
    adapt_max_by_angle: bool,
    model_cache: Any | None = None,
) -> tuple[list[MotionState], list[DynamicsResult]]:
    states: list[MotionState] = []
    dynamics: list[DynamicsResult] = []
    biorbd_model = None
    if model_cache is not None:
        try:
            biorbd_model = model_cache.model_for(anthro)
        except Exception:
            biorbd_model = None
    for index in range(frame_count):
        time = duration * index / max(1, frame_count - 1)
        state = motion_state(anthro, final_q, duration, time)
        if biorbd_model is not None:
            state = _biorbd_motion_state_with_com(biorbd_model, state)
        states.append(state)
        dynamics.append(inverse_dynamics(anthro, state, max_torques, adapt_max_by_angle, biorbd_model))
    return states, dynamics
