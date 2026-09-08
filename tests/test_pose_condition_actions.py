"""Interaction-level regressions for the editable squat pose."""

from types import SimpleNamespace
from unittest.mock import patch

from squat_gui.pose_condition_actions import PoseConditionActionsController


class RecordingPoseApp:
    def __init__(self) -> None:
        self.final_q = (0.1, 0.2, 0.3)
        self._pose_editor_bounds = (0.0, 1.0, 0.0, 1.0)
        self._pose_drag_bounds = None
        self.drag_target = None
        self.pose_canvas = object()
        self.pose_redraws = 0
        self.angle_syncs = 0
        self.recomputes = 0

    def anthro(self) -> object:
        return object()

    def scene_bounds(self) -> tuple[float, float, float, float]:
        return (-1.0, 1.0, -1.0, 1.0)

    def canvas_to_world(
        self,
        _canvas: object,
        x: float,
        y: float,
        _bounds: tuple[float, float, float, float],
    ) -> tuple[float, float]:
        return x, y

    def sync_pose_angle_fields_from_final_q(self) -> None:
        self.angle_syncs += 1

    def draw_pose_drag_preview(self) -> None:
        self.pose_redraws += 1

    def on_parameter_changed(self) -> None:
        self.recomputes += 1


def test_drag_redraws_only_pose_then_recomputes_once_on_release() -> None:
    app = RecordingPoseApp()
    controller = PoseConditionActionsController(app)
    controller.nearest_handle = lambda _x, _y: "knee"  # type: ignore[method-assign]
    first_q = (0.1, 0.25, 0.3)
    second_q = (0.1, 0.3, 0.3)

    controller.on_pose_press(SimpleNamespace(x=10.0, y=20.0))
    with (
        patch(
            "squat_gui.pose_condition_actions.pose_from_angles",
            return_value=object(),
        ),
        patch(
            "squat_gui.pose_condition_actions.drag_updated_q",
            side_effect=(first_q, second_q),
        ),
    ):
        controller.on_pose_drag(SimpleNamespace(x=11.0, y=21.0))
        controller.on_pose_drag(SimpleNamespace(x=12.0, y=22.0))

    assert app.final_q == second_q
    assert app.pose_redraws == 2
    assert app.angle_syncs == 2
    assert app.recomputes == 0

    controller.on_pose_release(SimpleNamespace())

    assert app.recomputes == 1
    assert app.drag_target is None
    assert app._pose_drag_bounds is None

    # A duplicate release event must not commit the same drag twice.
    controller.on_pose_release(SimpleNamespace())
    assert app.recomputes == 1


def test_release_does_not_recompute_when_drag_keeps_the_same_angles() -> None:
    app = RecordingPoseApp()
    controller = PoseConditionActionsController(app)
    controller.nearest_handle = lambda _x, _y: "hip"  # type: ignore[method-assign]

    controller.on_pose_press(SimpleNamespace(x=10.0, y=20.0))
    with (
        patch(
            "squat_gui.pose_condition_actions.pose_from_angles",
            return_value=object(),
        ),
        patch(
            "squat_gui.pose_condition_actions.drag_updated_q",
            return_value=app.final_q,
        ),
    ):
        controller.on_pose_drag(SimpleNamespace(x=10.0, y=20.0))
    controller.on_pose_release(SimpleNamespace())

    assert app.pose_redraws == 0
    assert app.angle_syncs == 0
    assert app.recomputes == 0
