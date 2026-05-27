"""Planar kinematics for the squat model."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin

from .anthropometry import Anthropometry
from .yeadon import QuinticBoundaryTrajectory


Vector = tuple[float, float]


@dataclass(frozen=True)
class Pose:
    heel: Vector
    toe: Vector
    ankle: Vector
    knee: Vector
    hip: Vector
    shoulder: Vector
    bar: Vector
    com: Vector
    segment_coms: dict[str, Vector]


@dataclass(frozen=True)
class MotionState:
    time: float
    q: tuple[float, float, float]
    qdot: tuple[float, float, float]
    qddot: tuple[float, float, float]
    pose: Pose
    phase: str = "statique"


@dataclass(frozen=True)
class PhaseDurations:
    excentrique: float = 4.0
    isometrique: float = 2.0
    concentrique: float = 4.0

    @property
    def total(self) -> float:
        return self.excentrique + self.isometrique + self.concentrique

    @property
    def squat_reference_time(self) -> float:
        return self.excentrique + self.isometrique / 2.0


def phase_durations(duration: float | PhaseDurations) -> PhaseDurations:
    if isinstance(duration, PhaseDurations):
        return duration
    half = max(0.05, duration / 2.0)
    return PhaseDurations(half, 0.0, half)


def add(a: Vector, b: Vector) -> Vector:
    return (a[0] + b[0], a[1] + b[1])


def sub(a: Vector, b: Vector) -> Vector:
    return (a[0] - b[0], a[1] - b[1])


def scale(v: Vector, factor: float) -> Vector:
    return (v[0] * factor, v[1] * factor)


def dot(a: Vector, b: Vector) -> float:
    return a[0] * b[0] + a[1] * b[1]


def cross_z(a: Vector, b: Vector) -> float:
    return a[0] * b[1] - a[1] * b[0]


def unit_from_vertical(angle: float) -> Vector:
    return (sin(angle), cos(angle))


def anterior_unit_from_vertical(angle: float) -> Vector:
    return (cos(angle), -sin(angle))


def local_point(origin: Vector, angle: float, anterior: float, longitudinal: float) -> Vector:
    return add(
        origin,
        add(scale(anterior_unit_from_vertical(angle), anterior), scale(unit_from_vertical(angle), longitudinal)),
    )


def angle_derivative_vector(angle: float, length: float) -> Vector:
    return (length * cos(angle), -length * sin(angle))


def local_angle_derivative_vector(angle: float, anterior: float, longitudinal: float) -> Vector:
    return (
        -anterior * sin(angle) + longitudinal * cos(angle),
        -anterior * cos(angle) - longitudinal * sin(angle),
    )


def angle_second_derivative_vector(angle: float, length: float, velocity: float, acceleration: float) -> Vector:
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


def pose_from_angles(anthro: Anthropometry, q: tuple[float, float, float]) -> Pose:
    shank_angle, thigh_angle, trunk_angle = tuple(angle + anthro.wedge_angle for angle in q)
    foot = anthro.foot
    shank = anthro.shank
    thigh = anthro.thigh
    trunk = anthro.trunk

    heel = (0.0, 0.0)
    toe = (foot.length, 0.0)
    ankle = (anthro.ankle_x_from_heel, anthro.ankle_height)
    knee = add(ankle, scale(unit_from_vertical(shank_angle), shank.length))
    hip = add(knee, scale(unit_from_vertical(thigh_angle), thigh.length))
    shoulder = add(hip, scale(unit_from_vertical(trunk_angle), trunk.length))
    bar = local_point(shoulder, trunk_angle, anthro.bar_anterior_offset, anthro.bar_longitudinal_offset)

    foot_com = (foot.length * foot.com_fraction, 0.025)
    shank_com = add(ankle, scale(unit_from_vertical(shank_angle), shank.length * shank.com_fraction))
    thigh_com = add(knee, scale(unit_from_vertical(thigh_angle), thigh.length * thigh.com_fraction))
    trunk_com = local_point(hip, trunk_angle, trunk.com_anterior_offset, trunk.length * trunk.com_fraction)
    bar_com = bar
    segment_coms = {
        "foot": foot_com,
        "shank": shank_com,
        "thigh": thigh_com,
        "trunk": trunk_com,
        "bar": bar_com,
    }
    weighted_x = (
        foot.mass * foot_com[0]
        + shank.mass * shank_com[0]
        + thigh.mass * thigh_com[0]
        + trunk.mass * trunk_com[0]
        + anthro.bar_mass * bar_com[0]
    )
    weighted_y = (
        foot.mass * foot_com[1]
        + shank.mass * shank_com[1]
        + thigh.mass * thigh_com[1]
        + trunk.mass * trunk_com[1]
        + anthro.bar_mass * bar_com[1]
    )
    com = (weighted_x / anthro.total_mass, weighted_y / anthro.total_mass)
    return Pose(heel, toe, ankle, knee, hip, shoulder, bar, com, segment_coms)


def com_accelerations(anthro: Anthropometry, q: tuple[float, float, float], qdot: tuple[float, float, float], qddot: tuple[float, float, float]) -> dict[str, Vector]:
    shank_angle, thigh_angle, trunk_angle = tuple(angle + anthro.wedge_angle for angle in q)
    shank_dot, thigh_dot, trunk_dot = qdot
    shank_ddot, thigh_ddot, trunk_ddot = qddot
    shank = anthro.shank
    thigh = anthro.thigh
    trunk = anthro.trunk

    zero = (0.0, 0.0)
    knee_acc = angle_second_derivative_vector(shank_angle, shank.length, shank_dot, shank_ddot)
    hip_acc = add(knee_acc, angle_second_derivative_vector(thigh_angle, thigh.length, thigh_dot, thigh_ddot))
    shoulder_acc = add(hip_acc, angle_second_derivative_vector(trunk_angle, trunk.length, trunk_dot, trunk_ddot))
    return {
        "foot": zero,
        "shank": angle_second_derivative_vector(shank_angle, shank.length * shank.com_fraction, shank_dot, shank_ddot),
        "thigh": add(knee_acc, angle_second_derivative_vector(thigh_angle, thigh.length * thigh.com_fraction, thigh_dot, thigh_ddot)),
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
    eccentric_end = durations.excentrique
    isometric_end = eccentric_end + durations.isometrique
    if time <= eccentric_end:
        phase = "excentrique"
        trajectories = [QuinticBoundaryTrajectory(0.0, eccentric_end, 0.0, angle) for angle in final_q]
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
        trajectories = [QuinticBoundaryTrajectory(isometric_end, durations.total, angle, 0.0) for angle in final_q]
        q = tuple(item.position(time) for item in trajectories)
        qdot = tuple(item.velocity(time) for item in trajectories)
        qddot = tuple(item.acceleration(time) for item in trajectories)
    return MotionState(time, q, qdot, qddot, pose_from_angles(anthro, q), phase)
