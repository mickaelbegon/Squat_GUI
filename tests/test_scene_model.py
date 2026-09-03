"""Tests for the renderer-independent scene geometry."""

from math import isclose, radians

from squat_gui.anthropometry import Anthropometry
from squat_gui.kinematics import (
    MotionState,
    functional_support_limits,
    geometric_support_limits,
    pose_from_angles,
)
from squat_gui.scene_model import (
    ViewportTransform,
    build_scene_geometry,
    project_point_on_line,
    scene_bounds,
)


def _state(anthro: Anthropometry) -> MotionState:
    q = (radians(22.0), radians(-58.0), radians(20.0))
    pose = pose_from_angles(anthro, q)
    return MotionState(
        0.5,
        q,
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        pose,
        "isometrique",
    )


def test_scene_geometry_centralizes_landmarks_segments_and_support_bases():
    anthro = Anthropometry(subject_profile="femme enceinte", bar_position="front")
    state = _state(anthro)

    scene = build_scene_geometry(anthro, state, support_x=0.12)

    assert scene.point("ankle") == state.pose.ankle
    assert scene.point("com") == state.pose.com
    assert scene.ground_line == (state.pose.heel, state.pose.toe)
    assert scene.geometric_support.limits == geometric_support_limits(state.pose)
    assert scene.functional_support.limits == functional_support_limits(state.pose)
    assert scene.support_point == (0.12, 0.0)
    assert tuple(segment.name for segment in scene.segments) == (
        "foot",
        "shank",
        "thigh",
        "trunk",
    )
    assert scene.segments[-1].variant == ("femme enceinte", "front")
    assert scene.segments[1].distal == scene.point("ankle")
    assert scene.segments[1].proximal == scene.point("knee")


def test_scene_x_offset_moves_every_rendered_coordinate_without_changing_pose():
    anthro = Anthropometry(wedge_angle_deg=12.0)
    state = _state(anthro)
    shift = 1.75

    scene = build_scene_geometry(anthro, state, support_x=0.2, x_offset=shift)

    assert scene.point("hip") == (state.pose.hip[0] + shift, state.pose.hip[1])
    assert scene.support_point == (0.2 + shift, 0.0)
    assert scene.wedge_polygon is not None
    assert scene.wedge_polygon[2] == (state.pose.heel[0] + shift, 0.0)
    expected_geometric = geometric_support_limits(state.pose)
    assert scene.geometric_support.limits == (
        expected_geometric[0] + shift,
        expected_geometric[1] + shift,
    )
    assert all(
        isclose(shifted.position[0], state.pose.segment_coms[shifted.name][0] + shift)
        for shifted in scene.segment_coms
    )


def test_viewport_transform_round_trip_is_renderer_independent():
    transform = ViewportTransform(
        width=640,
        height=480,
        bounds=(-0.36, 1.5, -0.08, 1.92),
        padding=42,
    )
    world = (0.42, 0.83)

    restored = transform.pixel_to_world(transform.world_to_pixel(world))

    assert isclose(restored[0], world[0], abs_tol=1e-12)
    assert isclose(restored[1], world[1], abs_tol=1e-12)


def test_scene_bounds_cover_multiple_subjects_and_horizontal_offset():
    back = Anthropometry(bar_position="back")
    overhead = Anthropometry(bar_position="over-head", height=2.0)

    bounds = scene_bounds((back, overhead), extra_x=0.7)

    assert bounds[0] == -0.36
    assert bounds[2:] == (-0.08, 2.22)
    expected_xmax = max(
        anthro.foot.length + anthro.shank.length + 0.78
        for anthro in (back, overhead)
    )
    assert isclose(bounds[1], expected_xmax + 0.7)


def test_force_line_projection_handles_regular_and_zero_force_vectors():
    assert project_point_on_line((2.0, 3.0), (1.0, 1.0), (0.0, 4.0)) == (
        1.0,
        3.0,
    )
    assert project_point_on_line((2.0, 3.0), (1.0, 1.0), (0.0, 0.0)) == (
        1.0,
        1.0,
    )
