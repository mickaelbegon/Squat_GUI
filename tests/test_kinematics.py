"""Public-characterization tests for the planar kinematics module."""

from math import isclose, radians

from squat_gui.anthropometry import Anthropometry
from squat_gui.kinematics import (
    clinical_joint_values_from_segment_values,
    joint_values_from_segment_values,
    pose_from_angles,
    segment_values_from_clinical_joint_values,
    segment_values_from_joint_values,
)


def test_joint_value_conventions_round_trip_without_losing_signs() -> None:
    segment_values = (radians(18.0), radians(-73.0), radians(34.0))

    signed_joints = joint_values_from_segment_values(segment_values)
    clinical_joints = clinical_joint_values_from_segment_values(segment_values)

    restored_signed = segment_values_from_joint_values(
        signed_joints["cheville"],
        signed_joints["genou"],
        signed_joints["hanche"],
    )
    restored_clinical = segment_values_from_clinical_joint_values(
        clinical_joints["cheville"],
        clinical_joints["genou"],
        clinical_joints["hanche"],
    )
    assert all(
        isclose(actual, expected)
        for actual, expected in zip(restored_signed, segment_values)
    )
    assert all(
        isclose(actual, expected)
        for actual, expected in zip(restored_clinical, segment_values)
    )
    assert clinical_joints["genou"] == -signed_joints["genou"]


def test_pose_com_matches_the_public_segment_mass_projection() -> None:
    anthro = Anthropometry(bar_mass=26.0, wedge_angle_deg=12.0, bar_position="front")
    pose = pose_from_angles(
        anthro,
        (radians(24.0), radians(-69.0), radians(31.0)),
    )

    masses = {
        "foot": anthro.foot.mass,
        "shank": anthro.shank.mass,
        "thigh": anthro.thigh.mass,
        "trunk": anthro.trunk.mass,
        "bar": anthro.bar_mass,
    }
    expected = tuple(
        sum(masses[name] * pose.segment_coms[name][axis] for name in masses)
        / anthro.total_mass
        for axis in range(2)
    )

    assert pose.com == expected
