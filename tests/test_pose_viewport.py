"""Regression tests for the single-pose viewport framing."""

from math import radians

from squat_gui.anthropometry import Anthropometry
from squat_gui.app import SquatGui
from squat_gui.dynamics import DynamicsResult
from squat_gui.kinematics import MotionState, pose_from_angles


class _Canvas:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

    def winfo_width(self) -> int:
        return self.width

    def winfo_height(self) -> int:
        return self.height


class _ViewportOwner:
    @staticmethod
    def scene_bounds(**_kwargs) -> tuple[float, float, float, float]:
        return (-0.36, 1.46, -0.08, 1.92)


def test_pose_editor_viewport_centres_crouched_subject_and_reduces_dead_space():
    anthro = Anthropometry(bar_mass=20.0)
    q = (radians(22.0), radians(-58.0), radians(20.0))
    pose = pose_from_angles(anthro, q)
    state = MotionState(0.0, q, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), pose, "isometrique")
    result = DynamicsResult((0.0, 900.0), 0.12, {}, {}, {}, {}, {})
    canvas = _Canvas(360, 500)
    owner = _ViewportOwner()

    bounds = SquatGui.pose_editor_bounds(owner, canvas, state, result, anthro)
    points = (
        pose.heel,
        pose.toe,
        pose.ankle,
        pose.knee,
        pose.hip,
        pose.shoulder,
        pose.bar,
        pose.com,
        *pose.segment_coms.values(),
        (result.cop_x, 0.0),
    )
    xmin = min(point[0] for point in points)
    xmax = max(point[0] for point in points)
    scale = min(
        (canvas.winfo_width() - 84) / (bounds[1] - bounds[0]),
        (canvas.winfo_height() - 84) / (bounds[3] - bounds[2]),
    )
    projected_middle = 42 + ((xmin + xmax) / 2.0 - bounds[0]) * scale

    assert abs(projected_middle - canvas.winfo_width() / 2.0) <= 1e-9
    assert bounds[0] < xmin < xmax < bounds[1]
    assert bounds[2] <= -0.16
    assert bounds[1] - bounds[0] < 1.46 - (-0.36)
