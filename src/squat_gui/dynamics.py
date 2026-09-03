"""Analytical 2D inverse dynamics for the first GUI iteration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .anthropometry import Anthropometry
from .backend import resolve_biorbd_model
from .kinematics import (
    MotionState,
    Pose,
    Vector,
    angle_derivative_vector,
    local_angle_derivative_vector,
    com_accelerations,
    com_velocities,
    cross_z,
    dot,
    motion_state,
    phase_durations,
    PhaseDurations,
    sub,
)
from .torque_capacity import GRAVITY, TorqueCapacity, joint_torque_capacities


@dataclass(frozen=True)
class DynamicsResult:
    ground_reaction: Vector
    cop_x: float
    torques: dict[str, float]
    torque_components: dict[str, dict[str, float]]
    powers: dict[str, float]
    effort_ratios: dict[str, float | None]
    torque_capacities: dict[str, TorqueCapacity]
    backend: str = "analytical"
    com: Vector = (0.0, 0.0)
    com_velocity: Vector = (0.0, 0.0)
    com_acceleration: Vector = (0.0, 0.0)
    dynamic_moment_z: float = 0.0
    support_point_label: str = "CoP"
    support_point_source: str = "bilan dynamique analytique"
    contact_source: str = "moment géométrique de la GRF"
    backend_diagnostic: str = "Backend analytique sélectionné."


@dataclass(frozen=True)
class ForceBalance:
    weight_magnitude_N: float
    weight_vector_N: Vector
    inertial_resultant_N: Vector
    external_resultant_N: Vector
    residual_N: Vector


def force_balance(anthro: Anthropometry, result: DynamicsResult) -> ForceBalance:
    """Return GRF + weight = mass * CoM acceleration in the global frame."""

    weight = anthro.total_mass * GRAVITY
    weight_vector = (0.0, -weight)
    inertial_resultant = (
        anthro.total_mass * result.com_acceleration[0],
        anthro.total_mass * result.com_acceleration[1],
    )
    external_resultant = (
        result.ground_reaction[0] + weight_vector[0],
        result.ground_reaction[1] + weight_vector[1],
    )
    residual = (
        external_resultant[0] - inertial_resultant[0],
        external_resultant[1] - inertial_resultant[1],
    )
    return ForceBalance(
        weight_magnitude_N=weight,
        weight_vector_N=weight_vector,
        inertial_resultant_N=inertial_resultant,
        external_resultant_N=external_resultant,
        residual_N=residual,
    )


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
    return _mass_weighted_segment_vector(anthro, velocities)


def total_com_acceleration(
    anthro: Anthropometry, accelerations: dict[str, Vector]
) -> Vector:
    return _mass_weighted_segment_vector(anthro, accelerations)


def ground_reaction_and_cop(
    anthro: Anthropometry, state: MotionState
) -> tuple[Vector, float, Vector, float]:
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


def _contact_moments(
    state: MotionState, reaction: Vector, cop_x: float
) -> dict[str, float]:
    """GRF moment around each joint, in the historical subtractive convention.

    The analytical and biorbd models have a fixed foot. Their inverse-dynamics
    torque therefore reconstructs ``M(q)qddot + velocity + gravity`` without an
    explicit ground-contact generalized force. This geometric diagnostic is
    kept separate and its *signed additive* counterpart is ``-contact``.
    """
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
    return {
        joint: minuend[joint] - subtrahend[joint]
        for joint in ("cheville", "genou", "hanche")
    }


def _sum_joint_terms(*terms: dict[str, float]) -> dict[str, float]:
    return {
        joint: sum(term[joint] for term in terms)
        for joint in ("cheville", "genou", "hanche")
    }


def _analytical_inverse_dynamics_decomposition(
    anthro: Anthropometry,
    state: MotionState,
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    """Return the fixed-foot analytical terms in joint-moment coordinates.

    ``state.q`` contains absolute segment orientations. The virtual-work
    transform in :func:`_joint_from_absolute` reports the corresponding
    moments at the ankle, knee and hip. Zeroing ``qdot``, ``qddot`` and gravity
    isolates the three terms without using a residual identity.
    """

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


def inverse_dynamics(
    anthro: Anthropometry,
    state: MotionState,
    max_torques: dict[str, float],
    adapt_max_by_angle: bool,
    biorbd_model: Any | None = None,
    adapt_max_by_velocity: bool = True,
    backend_diagnostic: str | None = None,
) -> DynamicsResult:
    reaction, cop_x, com_acceleration, dynamic_moment_z = ground_reaction_and_cop(
        anthro, state
    )
    com_velocity = total_com_velocity(
        anthro, com_velocities(anthro, state.q, state.qdot)
    )
    backend = "analytical"
    support_point_label = "CoP"
    support_point_source = "bilan dynamique analytique"
    contact_source = "moment géométrique de la GRF"
    if biorbd_model is not None:
        (
            reaction,
            cop_x,
            com_velocity,
            com_acceleration,
            dynamic_moment_z,
            support_point_label,
            support_point_source,
        ) = _biorbd_ground_reaction_and_cop(biorbd_model, state)
        (
            inverse_dynamics_total,
            mass_acceleration,
            velocity,
            gravity,
        ) = _biorbd_inverse_dynamics_decomposition(biorbd_model, state)
        try:
            contact = _biorbd_contact_torques(
                biorbd_model, state, reaction, cop_x, inverse_dynamics_total
            )
            contact_source = "biorbd.ExternalForceSet"
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            contact = _contact_moments(state, reaction, cop_x)
            contact_source = (
                "moment géométrique de la GRF (fallback biorbd : "
                f"{type(exc).__name__})"
            )
        backend = "biorbd"
    else:
        mass_acceleration, velocity, gravity = (
            _analytical_inverse_dynamics_decomposition(
                anthro,
                state,
            )
        )
        inverse_dynamics_total = _sum_joint_terms(mass_acceleration, velocity, gravity)
        contact = _contact_moments(state, reaction, cop_x)
    reconstructed = _sum_joint_terms(mass_acceleration, velocity, gravity)
    reconstruction_residual = _subtract_joint_terms(
        inverse_dynamics_total, reconstructed
    )
    external_contact = {joint: -contact[joint] for joint in contact}
    total_with_external_contact = _sum_joint_terms(
        inverse_dynamics_total, external_contact
    )
    torques = inverse_dynamics_total
    components = {
        joint: {
            "total": inverse_dynamics_total[joint],
            "mass_acceleration": mass_acceleration[joint],
            "velocity": velocity[joint],
            "gravity": gravity[joint],
            "contact": contact[joint],
            "external_contact": external_contact[joint],
            "total_with_external_contact": total_with_external_contact[joint],
            "reconstruction_residual": reconstruction_residual[joint],
            # Compatibility only: this historical field was total-contact and
            # must not be interpreted as M(q)qddot or a nonlinear effect.
            "inertiels_non_lineaires": total_with_external_contact[joint],
        }
        for joint in torques
    }
    joint_velocities = {
        "cheville": state.qdot[0],
        "genou": state.qdot[1] - state.qdot[0],
        "hanche": state.qdot[2] - state.qdot[1],
    }
    powers = {joint: torques[joint] * joint_velocities[joint] for joint in torques}
    torque_capacities = joint_torque_capacities(
        state,
        max_torques,
        adapt_max_by_angle,
        adapt_max_by_velocity,
        powers,
    )
    effort_ratios: dict[str, float | None] = {}
    for joint, torque in torques.items():
        capacity = torque_capacities[joint].available_torque_Nm
        effort_ratios[joint] = abs(torque) / capacity if capacity > 0.0 else None
    return DynamicsResult(
        ground_reaction=reaction,
        cop_x=cop_x,
        torques=torques,
        torque_components=components,
        powers=powers,
        effort_ratios=effort_ratios,
        torque_capacities=torque_capacities,
        backend=backend,
        com=state.pose.com,
        com_velocity=com_velocity,
        com_acceleration=com_acceleration,
        dynamic_moment_z=dynamic_moment_z,
        support_point_label=support_point_label,
        support_point_source=support_point_source,
        contact_source=contact_source,
        backend_diagnostic=backend_diagnostic
        or (
            "Backend biorbd actif."
            if biorbd_model is not None
            else "Backend analytique sélectionné (biorbd non demandé)."
        ),
    )


def _biorbd_coordinates(
    state: MotionState,
) -> tuple[list[float], list[float], list[float]]:
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
    return (
        np.asarray(q, dtype=float),
        np.asarray(qdot, dtype=float),
        np.asarray(qddot, dtype=float),
    )


def _array_from_biorbd(value: Any) -> list[float]:
    array = value.to_array()
    return [float(array[index]) for index in range(len(array))]


def _joint_dict_from_biorbd_tau(tau: list[float]) -> dict[str, float]:
    return {
        "cheville": -tau[0],
        "genou": -tau[1],
        "hanche": -tau[2],
    }


def _biorbd_tau_from_coordinates(
    biorbd_model: Any,
    q: Any,
    qdot: Any,
    qddot: Any,
    external_forces: Any | None = None,
) -> dict[str, float]:
    if external_forces is None:
        tau = biorbd_model.InverseDynamics(q, qdot, qddot)
    else:
        tau = biorbd_model.InverseDynamics(q, qdot, qddot, external_forces)
    return _joint_dict_from_biorbd_tau(_array_from_biorbd(tau))


def _biorbd_inverse_dynamics_torques(
    biorbd_model: Any, state: MotionState, external_forces: Any | None = None
) -> dict[str, float]:
    q, qdot, qddot = _numpy_biorbd_coordinates(state)
    return _biorbd_tau_from_coordinates(
        biorbd_model,
        q,
        qdot,
        qddot,
        external_forces,
    )


def _biorbd_inverse_dynamics_decomposition(
    biorbd_model: Any,
    state: MotionState,
) -> tuple[dict[str, float], dict[str, float], dict[str, float], dict[str, float]]:
    """Decompose biorbd inverse dynamics without deriving a term by residual.

    biorbd's ``massMatrix(q)`` supplies ``M(q)qddot`` explicitly. Gravity is
    ``InverseDynamics(q, 0, 0)`` and the velocity-dependent term is the
    difference ``InverseDynamics(q, qdot, 0) - gravity``. The latter is a
    controlled zero-acceleration evaluation, not ``total - contact``.
    """

    import numpy as np

    q, qdot, qddot = _numpy_biorbd_coordinates(state)
    zero = np.zeros_like(q)
    total = _biorbd_tau_from_coordinates(biorbd_model, q, qdot, qddot)

    mass_matrix_value = biorbd_model.massMatrix(q)
    mass_matrix = (
        mass_matrix_value.to_array()
        if hasattr(mass_matrix_value, "to_array")
        else mass_matrix_value
    )
    mass_product = np.asarray(mass_matrix, dtype=float) @ qddot
    mass_acceleration = _joint_dict_from_biorbd_tau(
        [float(value) for value in np.asarray(mass_product, dtype=float).reshape(-1)]
    )

    gravity = _biorbd_tau_from_coordinates(biorbd_model, q, zero, zero)
    velocity_and_gravity = _biorbd_tau_from_coordinates(biorbd_model, q, qdot, zero)
    velocity = _subtract_joint_terms(velocity_and_gravity, gravity)
    return total, mass_acceleration, velocity, gravity


def _biorbd_contact_torques(
    biorbd_model: Any,
    state: MotionState,
    reaction: Vector,
    cop_x: float,
    inverse_dynamics_total: dict[str, float],
) -> dict[str, float]:
    """Return the subtractive GRF diagnostic through biorbd.

    The fixed foot is the model base and has no generalized coordinate.
    Applying a world-frame wrench at the ZMP to the terminal actuated segment
    therefore defines a counterfactual external-force evaluation; it does not
    replace the constrained inverse-dynamics total.
    """
    import numpy as np

    external_forces = biorbd_model.externalForceSet()
    external_forces.add(
        "tronc",
        np.array([0.0, 0.0, 0.0, reaction[0], reaction[1], 0.0]),
        np.array([cop_x, 0.0, 0.0]),
    )
    with_contact = _biorbd_inverse_dynamics_torques(
        biorbd_model, state, external_forces
    )
    return {
        joint: inverse_dynamics_total[joint] - with_contact[joint]
        for joint in ("cheville", "genou", "hanche")
    }


def _biorbd_motion_state_with_com(biorbd_model: Any, state: MotionState) -> MotionState:
    q, _, _ = _numpy_biorbd_coordinates(state)
    com = biorbd_model.CoM(q).to_array()
    pose = replace(state.pose, com=(float(com[0]), float(com[1])))
    return replace(state, pose=pose)


def _biorbd_angular_momentum_derivative_z(
    biorbd_model: Any, state: MotionState
) -> float:
    q, qdot, qddot = _numpy_biorbd_coordinates(state)
    step = 1e-6
    forward = biorbd_model.CalcAngularMomentum(
        q + step * qdot, qdot + step * qddot, True
    ).to_array()
    backward = biorbd_model.CalcAngularMomentum(
        q - step * qdot, qdot - step * qddot, True
    ).to_array()
    return float((forward[2] - backward[2]) / (2.0 * step))


def _biorbd_native_cop_x(
    biorbd_model: Any, q: Any, qdot: Any, qddot: Any
) -> float | None:
    cop_x, _ = _biorbd_native_cop(biorbd_model, q, qdot, qddot)
    return cop_x


def _biorbd_native_cop(
    biorbd_model: Any, q: Any, qdot: Any, qddot: Any
) -> tuple[float | None, str | None]:
    """Try biorbd's native ZMP API and explain a compatible fallback."""

    zmp_function = getattr(biorbd_model, "CalcZeroMomentPoint", None)
    if zmp_function is None:
        return None, "CalcZeroMomentPoint absent"
    import numpy as np

    try:
        zmp = zmp_function(
            q, qdot, qddot, np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 0.0])
        ).to_array()
    except Exception as exc:
        # biorbd's bindings do not have a stable public exception hierarchy
        # across releases. The analytical ZMP reconstruction is intentional;
        # retain it while exposing why the native API was unavailable.
        return None, f"CalcZeroMomentPoint indisponible ({type(exc).__name__}: {exc})"
    return float(zmp[0]), None


def _biorbd_ground_reaction_and_cop(
    biorbd_model: Any,
    state: MotionState,
) -> tuple[Vector, float, Vector, Vector, float, str, str]:
    q, qdot, qddot = _numpy_biorbd_coordinates(state)
    mass = float(biorbd_model.mass())
    com = biorbd_model.CoM(q).to_array()
    comdot = biorbd_model.CoMdot(q, qdot).to_array()
    comddot = biorbd_model.CoMddot(q, qdot, qddot).to_array()
    reaction = (mass * float(comddot[0]), mass * (float(comddot[1]) + GRAVITY))
    hdot_com_z = _biorbd_angular_momentum_derivative_z(biorbd_model, state)
    dynamic_moment_z = (
        hdot_com_z + float(com[0]) * reaction[1] - float(com[1]) * reaction[0]
    )
    native_cop_x, native_cop_diagnostic = _biorbd_native_cop(
        biorbd_model, q, qdot, qddot
    )
    if native_cop_x is not None:
        cop_x = native_cop_x
        support_point_source = "biorbd.CalcZeroMomentPoint"
    else:
        cop_x = (
            dynamic_moment_z / reaction[1]
            if abs(reaction[1]) > 1e-9
            else state.pose.ankle[0]
        )
        support_point_source = (
            "bilan dynamique biorbd (fallback : "
            f"{native_cop_diagnostic or 'raison inconnue'})"
        )
    return (
        reaction,
        cop_x,
        (float(comdot[0]), float(comdot[1])),
        (float(comddot[0]), float(comddot[1])),
        dynamic_moment_z,
        "ZMP",
        support_point_source,
    )


def simulate(
    anthro: Anthropometry,
    final_q: tuple[float, float, float],
    duration: float | PhaseDurations,
    frame_count: int,
    max_torques: dict[str, float],
    adapt_max_by_angle: bool,
    model_cache: Any | None = None,
    adapt_max_by_velocity: bool = True,
) -> tuple[list[MotionState], list[DynamicsResult]]:
    states: list[MotionState] = []
    dynamics: list[DynamicsResult] = []
    backend_resolution = resolve_biorbd_model(model_cache, anthro)
    biorbd_model = backend_resolution.model
    durations = phase_durations(duration)
    for index in range(frame_count):
        time = durations.total * index / max(1, frame_count - 1)
        state = motion_state(anthro, final_q, duration, time)
        if biorbd_model is not None:
            state = _biorbd_motion_state_with_com(biorbd_model, state)
        states.append(state)
        dynamics.append(
            inverse_dynamics(
                anthro,
                state,
                max_torques,
                adapt_max_by_angle,
                biorbd_model,
                adapt_max_by_velocity,
                backend_resolution.diagnostic,
            )
        )
    return states, dynamics
