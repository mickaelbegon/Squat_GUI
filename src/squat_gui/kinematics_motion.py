"""Temporal sampling and analytical derivatives for squat kinematics."""

from __future__ import annotations

from math import cos, sin

from .anthropometry import Anthropometry
from .kinematics_geometry import (
    _absolute_segment_angles,
    add,
    balanced_standing_angles,
    pose_from_angles,
    scale,
)
from .kinematics_models import (
    DEFAULT_SAMPLE_PERIOD_S,
    MotionState,
    PhaseDurations,
    Vector,
)
from .yeadon import QuinticBoundaryTrajectory


def phase_durations(duration: float | PhaseDurations) -> PhaseDurations:
    if isinstance(duration, PhaseDurations):
        return duration
    half = max(0.05, duration / 2.0)
    return PhaseDurations(half, 0.0, half)


def _validate_sample_period(sample_period_s: float) -> None:
    if sample_period_s <= 0.0:
        raise ValueError("Le pas temporel doit être strictement positif.")


def frame_count_for_duration(
    duration: float | PhaseDurations,
    sample_period_s: float = DEFAULT_SAMPLE_PERIOD_S,
) -> int:
    """Return an endpoint-inclusive sample count for a target time step."""
    durations = phase_durations(duration)
    _validate_sample_period(sample_period_s)
    return max(2, int(round(durations.total / sample_period_s)) + 1)


def angle_derivative_vector(angle: float, length: float) -> Vector:
    return (length * cos(angle), -length * sin(angle))


def local_angle_derivative_vector(
    angle: float, anterior: float, longitudinal: float
) -> Vector:
    return (
        -anterior * sin(angle) + longitudinal * cos(angle),
        -anterior * cos(angle) - longitudinal * sin(angle),
    )


def angle_second_derivative_vector(
    angle: float, length: float, velocity: float, acceleration: float
) -> Vector:
    return (
        length * (-sin(angle) * velocity**2 + cos(angle) * acceleration),
        length * (-cos(angle) * velocity**2 - sin(angle) * acceleration),
    )


def local_angle_second_derivative_vector(
    angle: float,
    anterior: float,
    longitudinal: float,
    velocity: float,
    acceleration: float,
) -> Vector:
    return (
        (-anterior * cos(angle) - longitudinal * sin(angle)) * velocity**2
        + (-anterior * sin(angle) + longitudinal * cos(angle)) * acceleration,
        (anterior * sin(angle) - longitudinal * cos(angle)) * velocity**2
        + (-anterior * cos(angle) - longitudinal * sin(angle)) * acceleration,
    )


def com_velocities(
    anthro: Anthropometry,
    q: tuple[float, float, float],
    qdot: tuple[float, float, float],
) -> dict[str, Vector]:
    """Return analytical global velocities of all segment CoM points."""

    shank_angle, thigh_angle, trunk_angle = _absolute_segment_angles(
        anthro, q
    ).as_tuple()
    shank_dot, thigh_dot, trunk_dot = qdot
    shank = anthro.shank
    thigh = anthro.thigh
    trunk = anthro.trunk

    zero = (0.0, 0.0)
    knee_velocity = scale(angle_derivative_vector(shank_angle, shank.length), shank_dot)
    hip_velocity = add(
        knee_velocity,
        scale(angle_derivative_vector(thigh_angle, thigh.length), thigh_dot),
    )
    shoulder_velocity = add(
        hip_velocity,
        scale(angle_derivative_vector(trunk_angle, trunk.length), trunk_dot),
    )
    return {
        "foot": zero,
        "shank": scale(
            angle_derivative_vector(shank_angle, shank.length * shank.com_fraction),
            shank_dot,
        ),
        "thigh": add(
            knee_velocity,
            scale(
                angle_derivative_vector(thigh_angle, thigh.length * thigh.com_fraction),
                thigh_dot,
            ),
        ),
        "trunk": add(
            hip_velocity,
            scale(
                local_angle_derivative_vector(
                    trunk_angle,
                    trunk.com_anterior_offset,
                    trunk.length * trunk.com_fraction,
                ),
                trunk_dot,
            ),
        ),
        "bar": add(
            shoulder_velocity,
            scale(
                local_angle_derivative_vector(
                    trunk_angle,
                    anthro.bar_anterior_offset,
                    anthro.bar_longitudinal_offset,
                ),
                trunk_dot,
            ),
        ),
    }


def com_accelerations(
    anthro: Anthropometry,
    q: tuple[float, float, float],
    qdot: tuple[float, float, float],
    qddot: tuple[float, float, float],
) -> dict[str, Vector]:
    """Return analytical global accelerations of all segment CoM points."""

    shank_angle, thigh_angle, trunk_angle = _absolute_segment_angles(
        anthro, q
    ).as_tuple()
    shank_dot, thigh_dot, trunk_dot = qdot
    shank_ddot, thigh_ddot, trunk_ddot = qddot
    shank = anthro.shank
    thigh = anthro.thigh
    trunk = anthro.trunk

    zero = (0.0, 0.0)
    knee_acc = angle_second_derivative_vector(
        shank_angle, shank.length, shank_dot, shank_ddot
    )
    hip_acc = add(
        knee_acc,
        angle_second_derivative_vector(
            thigh_angle, thigh.length, thigh_dot, thigh_ddot
        ),
    )
    shoulder_acc = add(
        hip_acc,
        angle_second_derivative_vector(
            trunk_angle, trunk.length, trunk_dot, trunk_ddot
        ),
    )
    return {
        "foot": zero,
        "shank": angle_second_derivative_vector(
            shank_angle,
            shank.length * shank.com_fraction,
            shank_dot,
            shank_ddot,
        ),
        "thigh": add(
            knee_acc,
            angle_second_derivative_vector(
                thigh_angle,
                thigh.length * thigh.com_fraction,
                thigh_dot,
                thigh_ddot,
            ),
        ),
        "trunk": add(
            hip_acc,
            local_angle_second_derivative_vector(
                trunk_angle,
                trunk.com_anterior_offset,
                trunk.length * trunk.com_fraction,
                trunk_dot,
                trunk_ddot,
            ),
        ),
        "bar": add(
            shoulder_acc,
            local_angle_second_derivative_vector(
                trunk_angle,
                anthro.bar_anterior_offset,
                anthro.bar_longitudinal_offset,
                trunk_dot,
                trunk_ddot,
            ),
        ),
    }


def motion_state(
    anthro: Anthropometry,
    final_q: tuple[float, float, float],
    duration: float | PhaseDurations,
    time: float,
) -> MotionState:
    durations = phase_durations(duration)
    standing_q = balanced_standing_angles(anthro)
    eccentric_end = durations.excentrique
    isometric_end = eccentric_end + durations.isometrique
    if time <= eccentric_end:
        phase = "excentrique"
        trajectories = [
            QuinticBoundaryTrajectory(0.0, eccentric_end, start_angle, squat_angle)
            for start_angle, squat_angle in zip(standing_q, final_q)
        ]
        q = tuple(item.position(time) for item in trajectories)
        qdot = tuple(item.velocity(time) for item in trajectories)
        qddot = tuple(item.acceleration(time) for item in trajectories)
    elif time <= isometric_end:
        phase = "isometrique"
        q = final_q
        qdot = (0.0, 0.0, 0.0)
        qddot = (0.0, 0.0, 0.0)
    else:
        phase = "concentrique"
        trajectories = [
            QuinticBoundaryTrajectory(
                isometric_end, durations.total, squat_angle, end_angle
            )
            for squat_angle, end_angle in zip(final_q, standing_q)
        ]
        q = tuple(item.position(time) for item in trajectories)
        qdot = tuple(item.velocity(time) for item in trajectories)
        qddot = tuple(item.acceleration(time) for item in trajectories)
    return MotionState(time, q, qdot, qddot, pose_from_angles(anthro, q), phase)
