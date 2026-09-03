"""Spatial geometry for the planar squat model."""

from __future__ import annotations

from math import atan2, cos, pi, radians, sin

from .anthropometry import Anthropometry
from .kinematics_models import (
    METATARSAL_HEAD_FRACTION,
    Pose,
    Vector,
    _PoseGeometry,
    _SegmentAngles,
)


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


def local_point(
    origin: Vector, angle: float, anterior: float, longitudinal: float
) -> Vector:
    return add(
        origin,
        add(
            scale(anterior_unit_from_vertical(angle), anterior),
            scale(unit_from_vertical(angle), longitudinal),
        ),
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


def joint_values_from_segment_values(
    values: tuple[float, float, float],
) -> dict[str, float]:
    """Convert stored segment values to the signed joint-value convention."""

    return _SegmentAngles.from_values(values).joint_values()


def segment_values_from_joint_values(
    ankle: float, knee: float, hip: float
) -> tuple[float, float, float]:
    """Convert signed joint values to the stored segment-value convention."""

    return _SegmentAngles.from_joint_values(ankle, knee, hip).as_tuple()


def clinical_joint_values_from_segment_values(
    values: tuple[float, float, float],
) -> dict[str, float]:
    """Return the editable clinical convention in the input units.

    Squat_GUI historically stores knee flexion with a negative sign.  The
    numerical posture editor follows the usual teaching convention where
    knee flexion is displayed as a positive value.  Ankle dorsiflexion and
    hip flexion retain their existing signs.
    """
    joints = joint_values_from_segment_values(values)
    return {
        "cheville": joints["cheville"],
        "genou": -joints["genou"],
        "hanche": joints["hanche"],
    }


def segment_values_from_clinical_joint_values(
    ankle: float, knee_flexion: float, hip_flexion: float
) -> tuple[float, float, float]:
    """Convert editable clinical joint values to segment orientations."""
    return segment_values_from_joint_values(ankle, -knee_flexion, hip_flexion)


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


def _absolute_segment_angles(
    anthro: Anthropometry,
    q: tuple[float, float, float],
) -> _SegmentAngles:
    """Apply the platform wedge to the model's three segment values."""

    return _SegmentAngles.from_values(tuple(angle + anthro.wedge_angle for angle in q))


def _pose_geometry(anthro: Anthropometry, angles: _SegmentAngles) -> _PoseGeometry:
    """Build the articulated landmarks for already wedge-adjusted angles."""

    shank_angle, thigh_angle, trunk_angle = angles.as_tuple()
    foot = anthro.foot
    shank = anthro.shank
    thigh = anthro.thigh
    trunk = anthro.trunk

    heel = (0.0, foot.length * sin(anthro.wedge_angle))
    toe = add(heel, rotate_clockwise((foot.length, 0.0), anthro.wedge_angle))
    ankle = add(
        heel,
        rotate_clockwise(
            (anthro.ankle_x_from_heel, anthro.ankle_height), anthro.wedge_angle
        ),
    )
    knee = add(ankle, scale(unit_from_vertical(shank_angle), shank.length))
    hip = add(knee, scale(unit_from_vertical(thigh_angle), thigh.length))
    shoulder = add(hip, scale(unit_from_vertical(trunk_angle), trunk.length))
    bar = local_point(
        shoulder,
        trunk_angle,
        anthro.bar_anterior_offset,
        anthro.bar_longitudinal_offset,
    )

    return _PoseGeometry(heel, toe, ankle, knee, hip, shoulder, bar)


def _segment_com_positions(
    anthro: Anthropometry,
    geometry: _PoseGeometry,
    angles: _SegmentAngles,
) -> dict[str, Vector]:
    """Locate each segment centre of mass in the global frame."""

    shank_angle, thigh_angle, trunk_angle = angles.as_tuple()
    foot = anthro.foot
    shank = anthro.shank
    thigh = anthro.thigh
    trunk = anthro.trunk

    foot_com = add(
        geometry.heel,
        rotate_clockwise(
            (foot.length * foot.com_fraction, anthro.foot_com_transverse_offset),
            anthro.wedge_angle,
        ),
    )
    shank_com = add(
        geometry.ankle,
        scale(unit_from_vertical(shank_angle), shank.length * shank.com_fraction),
    )
    thigh_com = add(
        geometry.knee,
        scale(unit_from_vertical(thigh_angle), thigh.length * thigh.com_fraction),
    )
    trunk_com = local_point(
        geometry.hip,
        trunk_angle,
        trunk.com_anterior_offset,
        trunk.length * trunk.com_fraction,
    )
    return {
        "foot": foot_com,
        "shank": shank_com,
        "thigh": thigh_com,
        "trunk": trunk_com,
        "bar": geometry.bar,
    }


def _whole_body_com(
    anthro: Anthropometry,
    segment_coms: dict[str, Vector],
) -> Vector:
    """Return the mass-weighted global centre of mass."""

    foot_com = segment_coms["foot"]
    shank_com = segment_coms["shank"]
    thigh_com = segment_coms["thigh"]
    trunk_com = segment_coms["trunk"]
    bar_com = segment_coms["bar"]
    foot = anthro.foot
    shank = anthro.shank
    thigh = anthro.thigh
    trunk = anthro.trunk
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
    return (weighted_x / anthro.total_mass, weighted_y / anthro.total_mass)


def pose_from_angles(anthro: Anthropometry, q: tuple[float, float, float]) -> Pose:
    """Build pose landmarks and centre-of-mass projections from segment angles."""

    angles = _absolute_segment_angles(anthro, q)
    geometry = _pose_geometry(anthro, angles)
    segment_coms = _segment_com_positions(anthro, geometry, angles)
    return geometry.pose(_whole_body_com(anthro, segment_coms), segment_coms)


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
