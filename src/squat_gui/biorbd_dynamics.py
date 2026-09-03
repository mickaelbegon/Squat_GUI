"""Adapter between squat motion states and biorbd dynamics APIs."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .joint_dynamics import JOINT_NAMES, _subtract_joint_terms
from .kinematics import MotionState, Vector
from .torque_capacity import GRAVITY


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
    """Decompose biorbd inverse dynamics without deriving a term by residual."""

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
    """Return the subtractive GRF diagnostic through biorbd."""

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
        for joint in JOINT_NAMES
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
        # biorbd's bindings do not expose a stable exception hierarchy across
        # releases; the analytical fallback remains an intentional path.
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
