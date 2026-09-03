"""Headless checks for Tk bindings and button commands created by the layout."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from squat_gui.layout_builder import LayoutBuilder


class RecordingWidget:
    def __init__(self, *_args: object, **options: object) -> None:
        self.options = options
        self.bindings: dict[str, object] = {}

    def bind(self, sequence: str, callback: object) -> None:
        self.bindings[sequence] = callback

    def grid(self, **_options: object) -> None:
        pass

    def place(self, **_options: object) -> None:
        pass

    def configure(self, **options: object) -> None:
        self.options.update(options)

    def state(self, _values: list[str]) -> None:
        pass

    def rowconfigure(self, *_args: object, **_options: object) -> None:
        pass

    def columnconfigure(self, *_args: object, **_options: object) -> None:
        pass

    def grid_propagate(self, _enabled: bool) -> None:
        pass


class FakeAngleDialog:
    def __init__(self, *_args: object, **_options: object) -> None:
        self.dialog = RecordingWidget()
        self.editor = RecordingWidget()
        self.joint_var = object()
        self.value_var = object()
        self.feedback_var = object()
        self.joint_label = RecordingWidget()
        self.entry = RecordingWidget()
        self.cancel_button = RecordingWidget()
        self.apply_button = RecordingWidget()
        self.feedback_label = RecordingWidget()


def _builder(gui: object) -> LayoutBuilder:
    return LayoutBuilder(
        gui,
        canvas_background="#edf2ec",
        plot_choices=("centre de masse",),
        load_percent_options=(0.0,),
    )


def test_pose_canvas_bindings_and_verticalize_command_are_preserved() -> None:
    gui = SimpleNamespace(
        schedule_redraw=lambda _event=None: None,
        on_pose_press=lambda _event: None,
        on_pose_drag=lambda _event: None,
        on_pose_release=lambda _event: None,
        on_pose_context_menu=lambda _event: "break",
        verticalize_bar=lambda: None,
        apply_clinical_joint_angle=lambda _joint, _value: True,
        status_var=SimpleNamespace(get=lambda: ""),
    )
    root = RecordingWidget()

    with (
        patch("squat_gui.layout_builder.ttk.Frame", RecordingWidget),
        patch("squat_gui.layout_builder.ttk.Button", RecordingWidget),
        patch("squat_gui.layout_builder.tk.Canvas", RecordingWidget),
        patch("squat_gui.layout_builder.PrecisePoseAngleDialog", FakeAngleDialog),
    ):
        _builder(gui)._build_pose_panel(root)

    assert set(gui.pose_canvas.bindings) == {
        "<Configure>",
        "<ButtonPress-1>",
        "<B1-Motion>",
        "<ButtonRelease-1>",
        "<ButtonPress-3>",
    }
    assert gui.pose_canvas.bindings["<ButtonPress-1>"] == gui.on_pose_press
    assert gui.pose_canvas.bindings["<B1-Motion>"] == gui.on_pose_drag
    assert gui.pose_canvas.bindings["<ButtonRelease-1>"] == gui.on_pose_release
    assert gui.pose_canvas.bindings["<ButtonPress-3>"] == gui.on_pose_context_menu
    assert gui.optimize_bar_path_button.options["command"] == gui.verticalize_bar


def test_plot_and_conditions_callbacks_keep_their_public_commands() -> None:
    gui = SimpleNamespace(
        schedule_redraw=lambda _event=None: None,
        on_plot_cursor_event=lambda _event: None,
        on_table_tab_changed=lambda _event=None: None,
        record_condition=lambda: None,
        duplicate_selected_condition=lambda: None,
        delete_selected_conditions=lambda: None,
        save_json=lambda: None,
        load_json=lambda: None,
        export_excel=lambda: None,
        export_video=lambda: None,
        export_csv_results=lambda: None,
        _build_display_menu=lambda _parent, **_options: RecordingWidget(),
    )
    root = RecordingWidget()

    with (
        patch("squat_gui.layout_builder.ttk.Frame", RecordingWidget),
        patch("squat_gui.layout_builder.ttk.LabelFrame", RecordingWidget),
        patch("squat_gui.layout_builder.ttk.Button", RecordingWidget),
        patch("squat_gui.layout_builder.tk.Canvas", RecordingWidget),
    ):
        builder = _builder(gui)
        builder._build_plot_panel(root)
        builder._build_condition_notebook = lambda: setattr(
            gui, "table_notebook", RecordingWidget()
        )
        builder._build_conditions_panel(RecordingWidget())

    assert gui.plot_canvas.bindings["<Button-1>"] == gui.on_plot_cursor_event
    assert gui.plot_canvas.bindings["<B1-Motion>"] == gui.on_plot_cursor_event
    assert gui.table_notebook.bindings["<<NotebookTabChanged>>"] == gui.on_table_tab_changed
    assert gui.add_condition_button.options["command"] == gui.record_condition
    assert gui.duplicate_condition_button.options["command"] == gui.duplicate_selected_condition
    assert gui.delete_condition_button.options["command"] == gui.delete_selected_conditions
    assert gui.save_conditions_button.options["command"] == gui.save_json
    assert gui.load_conditions_button.options["command"] == gui.load_json
    assert gui.export_excel_button.options["command"] == gui.export_excel
    assert gui.export_mp4_button.options["command"] == gui.export_video
    assert gui.export_csv_button.options["command"] == gui.export_csv_results
