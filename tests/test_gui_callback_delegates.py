"""Headless contracts for the public Tk callback surface.

The layout binds methods on :class:`SquatGui`, while the implementation is
owned by focused controllers.  These tests keep that public surface safe to
use without a Tcl interpreter and catch accidental self-recursion in a facade.
"""

from __future__ import annotations

from types import SimpleNamespace

from squat_gui.app import SquatGui


class RecordingController:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def __getattr__(self, name: str):
        def callback(*args: object) -> str:
            self.calls.append((name, args))
            return f"{name}-result"

        return callback


def test_pose_event_facade_delegates_each_event_once_without_tcl() -> None:
    app = object.__new__(SquatGui)
    controller = RecordingController()
    app.__dict__["_pose_condition_actions"] = controller
    event = SimpleNamespace(x=120, y=240)

    assert app.on_pose_context_menu(event) == "on_pose_context_menu-result"
    assert app.on_pose_press(event) is None
    assert app.on_pose_drag(event) is None
    assert app.on_pose_release(event) is None

    assert controller.calls == [
        ("on_pose_context_menu", (event,)),
        ("on_pose_press", (event,)),
        ("on_pose_drag", (event,)),
        ("on_pose_release", (event,)),
    ]


def test_condition_event_facade_delegates_each_event_once_without_tcl() -> None:
    app = object.__new__(SquatGui)
    controller = RecordingController()
    app.__dict__["_condition_controller"] = controller
    event = SimpleNamespace(y=42)

    assert app.on_table_selection_changed(event) is None
    assert app.on_table_click(event) is None
    assert app.update_condition_buttons() is None
    assert app.update_condition_differences() is None

    assert controller.calls == [
        ("on_selection_changed", ()),
        ("on_table_click", (event,)),
        ("update_buttons", ()),
        ("update_differences", ()),
    ]


def test_plot_and_scene_facades_delegate_once_without_tcl() -> None:
    app = object.__new__(SquatGui)
    plot_controller = RecordingController()
    scene_controller = RecordingController()
    app.__dict__["_plot_controller"] = plot_controller
    app.__dict__["_scene_canvas_controller"] = scene_controller
    event = SimpleNamespace(x=30, y=50)
    canvas = object()
    bounds = (-1.0, 1.0, -1.0, 1.0)

    assert app.draw_plot() == "draw_plot-result"
    assert app.on_plot_cursor_event(event) == "on_plot_cursor_event-result"
    assert app.world_to_canvas(canvas, (0.2, 0.4), bounds) == "world_to_canvas-result"
    assert app.draw_pose_editor() is None

    assert plot_controller.calls == [
        ("draw_plot", ()),
        ("on_plot_cursor_event", (event,)),
    ]
    assert scene_controller.calls == [
        ("world_to_canvas", (canvas, (0.2, 0.4), bounds)),
        ("draw_pose_editor", ()),
    ]
