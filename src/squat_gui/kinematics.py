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


def angle_derivative_vector(angle: float, length: float) -> Vector:
    return (length * cos(angle), -length * sin(angle))


def angle_second_derivative_vector(angle: float, length: float, velocity: float, acceleration: float) -> Vector:
    return (
        length * (-sin(angle) * velocity**2 + cos(angle) * acceleration),
        length * (-cos(angle) * velocity**2 - sin(angle) * acceleration),
    )


def pose_from_angles(anthro: Anthropometry, q: tuple[float, float, float]) -> Pose:
    shank_angle, thigh_angle, trunk_angle = q
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
    bar = shoulder

    foot_com = (foot.length * foot.com_fraction, 0.025)
    shank_com = add(ankle, scale(unit_from_vertical(shank_angle), shank.length * shank.com_fraction))
    thigh_com = add(knee, scale(unit_from_vertical(thigh_angle), thigh.length * thigh.com_fraction))
    trunk_com = add(hip, scale(unit_from_vertical(trunk_angle), trunk.length * trunk.com_fraction))
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
    shank_angle, thigh_angle, trunk_angle = q
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
        "trunk": add(hip_acc, angle_second_derivative_vector(trunk_angle, trunk.length * trunk.com_fraction, trunk_dot, trunk_ddot)),
        "bar": shoulder_acc,
    }


def motion_state(anthro: Anthropometry, final_q: tuple[float, float, float], duration: float, time: float) -> MotionState:
    midpoint = duration / 2.0
    if time <= midpoint:
        phase = "excentrique"
        trajectories = [QuinticBoundaryTrajectory(0.0, midpoint, 0.0, angle) for angle in final_q]
    else:
        phase = "concentrique"
        trajectories = [QuinticBoundaryTrajectory(midpoint, duration, angle, 0.0) for angle in final_q]
    q = tuple(item.position(time) for item in trajectories)
    qdot = tuple(item.velocity(time) for item in trajectories)
    qddot = tuple(item.acceleration(time) for item in trajectories)
    return MotionState(time, q, qdot, qddot, pose_from_angles(anthro, q), phase)
