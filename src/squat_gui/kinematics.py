"""Planar kinematics for the squat model."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, pi, radians, sin

from .anthropometry import Anthropometry
from .yeadon import QuinticBoundaryTrajectory


Vector = tuple[float, float]
# The simplified foot model has no separate toe-joint.  The metatarsal head is
# therefore represented by the anterior 85% point of the heel-to-toe segment;
# the remaining 15% represents the distal toes beyond the functional forefoot.
METATARSAL_HEAD_FRACTION = 0.85
DEFAULT_SAMPLE_PERIOD_S = 0.05


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


def frame_count_for_duration(
    duration: float | PhaseDurations,
    sample_period_s: float = DEFAULT_SAMPLE_PERIOD_S,
) -> int:
    """Return an endpoint-inclusive sample count for a target time step."""
    durations = phase_durations(duration)
    if sample_period_s <= 0.0:
        raise ValueError("Le pas temporel doit être strictement positif.")
    return max(2, int(round(durations.total / sample_period_s)) + 1)


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


def _wrapped_angle(angle: float) -> float:
    """Wrap an angle to [-pi, pi)."""
    return (angle + pi) % (2.0 * pi) - pi


def segment_orientations(pose: Pose) -> dict[str, float]:
    """Return absolute segment orientations in the global x-y frame.

    Orientations are measured from global +x, with counter-clockwise angles
    positive. Segment directions are heel->toe, ankle->knee, knee->hip and
    hip->shoulder.
    """

    endpoints = {
        "foot": (pose.heel, pose.toe),
        "shank": (pose.ankle, pose.knee),
        "thigh": (pose.knee, pose.hip),
        "trunk": (pose.hip, pose.shoulder),
    }
    return {
        name: atan2(end[1] - start[1], end[0] - start[0])
        for name, (start, end) in endpoints.items()
    }


def joint_angles_from_orientations(orientations: dict[str, float]) -> dict[str, float]:
    """Reconstruct the signed joint angles used by Squat_GUI.

    Ankle dorsiflexion is positive relative to the foot. Knee flexion keeps
    the historical negative sign, and hip flexion is positive for a trunk
    orientation anterior to the thigh in the current squat convention.
    """

    foot = orientations["foot"]
    shank = orientations["shank"]
    thigh = orientations["thigh"]
    trunk = orientations["trunk"]
    return {
        "cheville": _wrapped_angle(pi / 2.0 - _wrapped_angle(shank - foot)),
        "genou": _wrapped_angle(shank - thigh),
        "hanche": _wrapped_angle(thigh - trunk),
    }


def joint_angles_from_pose(pose: Pose) -> dict[str, float]:
    return joint_angles_from_orientations(segment_orientations(pose))


def joint_values_from_segment_values(values: tuple[float, float, float]) -> dict[str, float]:
    shank, thigh, trunk = values
    return {
        "cheville": shank,
        "genou": thigh - shank,
        "hanche": trunk - thigh,
    }


def segment_values_from_joint_values(ankle: float, knee: float, hip: float) -> tuple[float, float, float]:
    shank = ankle
    thigh = shank + knee
    trunk = thigh + hip
    return (shank, thigh, trunk)


def geometric_support_limits(pose: Pose) -> tuple[float, float]:
    """Return the projected heel-to-toe support interval on the ground plane."""

    return (min(pose.heel[0], pose.toe[0]), max(pose.heel[0], pose.toe[0]))


def metatarsal_head_point(pose: Pose) -> Vector:
    """Return the modelled head of the metatarsals on the foot segment.

    The raster foot and the analytical model share only heel/toe endpoints, so
    the head is placed at a documented fraction of the segment rather than
    inventing an additional anatomical landmark in the pose state.
    """

    return add(
        pose.heel,
        scale(sub(pose.toe, pose.heel), METATARSAL_HEAD_FRACTION),
    )


def functional_support_limits(pose: Pose) -> tuple[float, float]:
    """Return the functional AP interval from ankle to metatarsal head.

    The full projected heel-to-toe segment remains the geometric base.  The
    functional teaching zone starts at the ankle projection and ends at the
    modelled metatarsal head, leaving the distal toes outside the accepted
    interval.  Bounds are sorted so the convention remains valid with a wedge.
    """

    metatarsal_head = metatarsal_head_point(pose)
    return (
        min(pose.ankle[0], metatarsal_head[0]),
        max(pose.ankle[0], metatarsal_head[0]),
    )


def zmp_support_limits(pose: Pose) -> tuple[float, float]:
    """Compatibility alias for the functional support interval."""

    return functional_support_limits(pose)


def zmp_in_support(pose: Pose, zmp_x: float) -> bool:
    posterior, anterior = functional_support_limits(pose)
    return posterior <= zmp_x <= anterior


def rotate_clockwise(vector: Vector, angle: float) -> Vector:
    return (
        vector[0] * cos(angle) + vector[1] * sin(angle),
        -vector[0] * sin(angle) + vector[1] * cos(angle),
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

    heel = (0.0, foot.length * sin(anthro.wedge_angle))
    toe = add(heel, rotate_clockwise((foot.length, 0.0), anthro.wedge_angle))
    ankle = add(
        heel,
        rotate_clockwise((anthro.ankle_x_from_heel, anthro.ankle_height), anthro.wedge_angle),
    )
    knee = add(ankle, scale(unit_from_vertical(shank_angle), shank.length))
    hip = add(knee, scale(unit_from_vertical(thigh_angle), thigh.length))
    shoulder = add(hip, scale(unit_from_vertical(trunk_angle), trunk.length))
    bar = local_point(shoulder, trunk_angle, anthro.bar_anterior_offset, anthro.bar_longitudinal_offset)

    foot_com = add(
        heel,
        rotate_clockwise(
            (foot.length * foot.com_fraction, anthro.foot_com_transverse_offset),
            anthro.wedge_angle,
        ),
    )
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


def balanced_standing_angles(
    anthro: Anthropometry,
    target_fraction: float = 0.5,
    max_lean_deg: float = 12.0,
) -> tuple[float, float, float]:
    """Return an extended standing posture whose static CoP is safely supported.

    All three absolute segment orientations share the same small lean, keeping
    the knee and hip extended.  At rest the analytical CoP equals the global
    centre-of-mass projection, so centring that projection in the functional
    support interval provides a stable upright endpoint for every squat.
    """

    neutral_q = tuple(-anthro.wedge_angle for _ in range(3))
    neutral_pose = pose_from_angles(anthro, neutral_q)
    posterior, anterior = functional_support_limits(neutral_pose)
    fraction = min(0.9, max(0.1, target_fraction))
    target_x = posterior + fraction * (anterior - posterior)

    lower_lean = -radians(max_lean_deg)
    upper_lean = radians(max_lean_deg)

    def posture(lean: float) -> tuple[tuple[float, float, float], float]:
        q = tuple(lean - anthro.wedge_angle for _ in range(3))
        return q, pose_from_angles(anthro, q).com[0] - target_x

    lower_q, lower_error = posture(lower_lean)
    upper_q, upper_error = posture(upper_lean)
    if lower_error >= 0.0:
        return lower_q
    if upper_error <= 0.0:
        return upper_q

    for _ in range(48):
        midpoint = (lower_lean + upper_lean) / 2.0
        midpoint_q, midpoint_error = posture(midpoint)
        if abs(midpoint_error) <= 1e-10:
            return midpoint_q
        if midpoint_error < 0.0:
            lower_lean = midpoint
        else:
            upper_lean = midpoint
    return posture((lower_lean + upper_lean) / 2.0)[0]


def com_velocities(
    anthro: Anthropometry,
    q: tuple[float, float, float],
    qdot: tuple[float, float, float],
) -> dict[str, Vector]:
    """Return analytical global velocities of all segment CoM points."""

    shank_angle, thigh_angle, trunk_angle = tuple(angle + anthro.wedge_angle for angle in q)
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
            QuinticBoundaryTrajectory(isometric_end, durations.total, squat_angle, end_angle)
            for squat_angle, end_angle in zip(final_q, standing_q)
        ]
        q = tuple(item.position(time) for item in trajectories)
        qdot = tuple(item.velocity(time) for item in trajectories)
        qddot = tuple(item.acceleration(time) for item in trajectories)
    return MotionState(time, q, qdot, qddot, pose_from_angles(anthro, q), phase)
