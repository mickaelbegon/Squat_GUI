"""Backend-independent orchestration of inverse-dynamics simulations."""

from __future__ import annotations

from typing import Any

from .anthropometry import Anthropometry
from .backend import resolve_biorbd_model
from .biorbd_dynamics import (
    _biorbd_contact_torques,
    _biorbd_ground_reaction_and_cop,
    _biorbd_inverse_dynamics_decomposition,
    _biorbd_motion_state_with_com,
)
from .dynamics_models import DynamicsResult
from .ground_reaction import ground_reaction_and_cop, total_com_velocity
from .joint_dynamics import (
    _analytical_inverse_dynamics_decomposition,
    _contact_moments,
    _subtract_joint_terms,
    _sum_joint_terms,
)
from .kinematics import (
    MotionState,
    PhaseDurations,
    com_velocities,
    motion_state,
    phase_durations,
)
from .torque_capacity import joint_torque_capacities


def inverse_dynamics(
    anthro: Anthropometry,
    state: MotionState,
    max_torques: dict[str, float],
    adapt_max_by_angle: bool,
    biorbd_model: Any | None = None,
    adapt_max_by_velocity: bool = True,
    backend_diagnostic: str | None = None,
) -> DynamicsResult:
    """Compute inverse dynamics for one motion state."""

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
                f"moment géométrique de la GRF (fallback biorbd : {type(exc).__name__})"
            )
        backend = "biorbd"
    else:
        mass_acceleration, velocity, gravity = (
            _analytical_inverse_dynamics_decomposition(anthro, state)
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
            # Compatibility only: historical total-contact field.
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
    """Sample a complete motion and compute dynamics for every frame."""

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
