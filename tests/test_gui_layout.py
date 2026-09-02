"""Geometry regression tests for the Tkinter layout.

These tests are skipped when the test runner has no display. On a desktop/CI
runner with Tk available they exercise the real widget positions after layout.
"""

import os
import tkinter as tk
import unittest
from types import SimpleNamespace
from tkinter import ttk

from squat_gui.app import SquatGui


def _rect(widget: tk.Misc) -> tuple[int, int, int, int]:
    return (
        widget.winfo_rootx(),
        widget.winfo_rooty(),
        widget.winfo_width(),
        widget.winfo_height(),
    )


def _inside(child: tk.Misc, parent: tk.Misc, tolerance: int = 2) -> bool:
    child_x, child_y, child_width, child_height = _rect(child)
    parent_x, parent_y, parent_width, parent_height = _rect(parent)
    return (
        child_x >= parent_x - tolerance
        and child_y >= parent_y - tolerance
        and child_x + child_width <= parent_x + parent_width + tolerance
        and child_y + child_height <= parent_y + parent_height + tolerance
    )


class GuiLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Sur macOS, Tk peut interrompre le processus avant de lever TclError
        # lorsqu'aucune session graphique n'est disponible.
        if not os.environ.get("DISPLAY") and os.name != "nt":
            raise unittest.SkipTest("aucune session graphique disponible")
        try:
            cls.app = SquatGui()
            cls.app.update()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"Tkinter sans affichage: {exc}") from exc

    @classmethod
    def tearDownClass(cls) -> None:
        cls.app.destroy()

    def assert_inside(self, child: tk.Misc, parent: tk.Misc) -> None:
        self.assertTrue(
            _inside(child, parent),
            msg=(
                f"{child} sort de {parent}: child={_rect(child)}, "
                f"parent={_rect(parent)}"
            ),
        )

    def test_results_and_conditions_keep_distinct_vertical_slots(self):
        self.assertIs(self.app.plot_box.master, self.app.left_panel)
        self.assertIs(self.app.table_box.master, self.app.left_panel)
        torque_bottom = (
            self.app.torque_box.winfo_rooty() + self.app.torque_box.winfo_height()
        )
        self.assertLessEqual(torque_bottom, self.app.plot_box.winfo_rooty())
        plot_bottom = self.app.plot_box.winfo_rooty() + self.app.plot_box.winfo_height()
        conditions_top = self.app.table_box.winfo_rooty()
        self.assertLessEqual(plot_bottom, conditions_top)

        plot_right = self.app.plot_box.winfo_rootx() + self.app.plot_box.winfo_width()
        table_right = self.app.table_box.winfo_rootx() + self.app.table_box.winfo_width()
        pose_left = self.app.pose_canvas.winfo_rootx()
        self.assertLessEqual(plot_right, pose_left)
        self.assertLessEqual(table_right, pose_left)

    def test_plot_controls_fit_inside_the_results_frame(self):
        self.assertGreater(self.app.plot_box.winfo_width(), 0)
        self.assertGreater(self.app.plot_box.winfo_height(), 0)
        for widget in self.app.plot_box.winfo_children():
            if widget.winfo_ismapped():
                self.assert_inside(widget, self.app.plot_box)

    def test_display_menu_is_overlaid_on_the_animation_panel(self):
        self.assertIs(
            self.app.display_menu_upper_button.master, self.app.animation_panel
        )
        self.assertIs(self.app.display_menu_lower_button.master, self.app.plot_panel)
        for button in (
            self.app.display_menu_upper_button,
            self.app.display_menu_lower_button,
        ):
            self.assertEqual(button.place_info().get("anchor"), "ne")
            self.assertEqual(float(button.place_info().get("relx", 0.0)), 1.0)

    def test_playback_is_compact_below_the_pose_with_a_wide_slider(self):
        self.assertEqual(self.app.playback_panel.grid_info()["column"], 1)
        self.assertEqual(self.app.playback_panel.grid_info()["columnspan"], 2)
        self.assertEqual(self.app.reveal_mode_menu.grid_info()["column"], 0)
        self.assertEqual(self.app.frame_scale.grid_info()["column"], 2)
        self.assertLess(
            self.app.reveal_mode_menu.winfo_rootx(),
            self.app.frame_scale.winfo_rootx(),
        )
        self.assertGreater(
            self.app.frame_scale.winfo_width(), self.app.reveal_mode_menu.winfo_width()
        )
        playback_bottom = (
            self.app.playback_panel.winfo_rooty()
            + self.app.playback_panel.winfo_height()
        )
        self.assertLessEqual(playback_bottom, self.app.plot_panel.winfo_rooty())

    def test_temporal_preset_starts_empty(self):
        self.assertEqual(self.app.temporal_preset_var.get(), "")
        self.assertEqual(self.app.temporal_preset_display_var.get(), "")

    def test_bar_stabilization_is_explicit_and_disabled_by_default(self):
        self.assertFalse(self.app.optimize_bar_path_var.get())
        controls = self.app.parameter_options.winfo_children()
        experimental = [
            control
            for control in controls
            if "expérimental" in str(control.cget("text"))
        ]
        self.assertEqual(len(experimental), 1)
        self.assertTrue(experimental[0].winfo_ismapped())

    def test_torque_preset_and_checks_use_the_compact_grid(self):
        self.assertIs(self.app.torque_preset_menu.master, self.app.torque_box)
        self.assertEqual(self.app.torque_preset_menu.grid_info()["rowspan"], 2)
        torque_checks = next(
            child
            for child in self.app.torque_box.winfo_children()
            if isinstance(child, ttk.Frame)
        )
        check_rows = {
            child.grid_info().get("row")
            for child in torque_checks.winfo_children()
            if child.winfo_manager() == "grid"
        }
        self.assertEqual(check_rows, {0})

    def test_file_actions_share_one_icon_row(self):
        buttons = (
            self.app.save_conditions_button,
            self.app.load_conditions_button,
            self.app.export_excel_button,
            self.app.export_mp4_button,
        )
        self.assertEqual({button.grid_info().get("row") for button in buttons}, {0})
        self.assertEqual(
            {button.grid_info().get("column") for button in buttons}, {0, 1, 2, 3}
        )
        self.assertEqual(self.app.export_csv_button.grid_info().get("row"), 1)
        self.assertEqual(self.app.export_csv_button.grid_info().get("columnspan"), 4)
        self.assertTrue(all(button.cget("text")[0] in "💾📂▦▶" for button in buttons))

    def test_parameter_columns_share_the_same_grid_lines(self):
        self.assertEqual(
            self.app.duration_box.grid_info()["row"],
            self.app.lengths_box.grid_info()["row"],
        )
        self.assertEqual(
            self.app.duration_box.winfo_rooty(), self.app.lengths_box.winfo_rooty()
        )
        self.assertEqual(
            self.app.duration_box.winfo_height(), self.app.lengths_box.winfo_height()
        )
        self.assertIs(self.app.temporal_preset_menu.master, self.app.duration_box)
        self.assertEqual(
            self.app.temporal_preset_label.grid_info()["row"],
            self.app.anthropometry_mode_label.grid_info()["row"],
        )

    def test_charge_starts_on_the_lengths_column(self):
        self.assertEqual(self.app.profile_menu.grid_info()["column"], 0)
        self.assertEqual(self.app.bar_menu.grid_info()["column"], 1)
        self.assertIs(self.app.charge_box.master, self.app.parameter_box)
        self.assertEqual(self.app.charge_box.grid_info()["column"], 1)
        self.assertAlmostEqual(
            self.app.charge_box.winfo_rootx(),
            self.app.lengths_box.winfo_rootx(),
            delta=2,
        )

    def test_precise_pose_angle_editor_uses_context_click_not_spinboxes(self):
        self.assertIs(self.app.pose_canvas.master, self.app.pose_panel)
        self.assertFalse(hasattr(self.app, "pose_angle_box"))
        self.assertFalse(hasattr(self.app, "pose_angle_spinboxes"))
        self.assertTrue(self.app.pose_canvas.bind("<ButtonPress-3>"))

    def test_angle_dialog_is_precise_and_does_not_apply_on_open(self):
        before = self.app.final_q
        self.app.open_pose_angle_dialog("genou")
        dialog = self.app.pose_angle_dialog
        try:
            self.assertIsNotNone(dialog)
            self.assertEqual(self.app.final_q, before)
            self.assertIn("Genou", dialog.title())

            descendants = [dialog]
            for widget in descendants:
                descendants.extend(widget.winfo_children())
            self.assertFalse(any(isinstance(widget, ttk.Spinbox) for widget in descendants))
        finally:
            if dialog is not None:
                self.app.close_pose_angle_dialog(dialog)

    def test_drag_uses_the_same_bounds_as_the_visible_pose_handles(self):
        bounds = self.app._pose_editor_bounds
        self.assertIsNotNone(bounds)
        pose = self.app.states[-1].pose
        handles = {
            "knee": pose.knee,
            "hip": pose.hip,
            "shoulder": pose.shoulder,
        }
        for handle, point in handles.items():
            with self.subTest(handle=handle):
                x, y = self.app.world_to_canvas(self.app.pose_canvas, point, bounds)
                self.assertEqual(self.app.nearest_handle(x, y), handle)

        before = self.app.final_q
        knee_x, knee_y = self.app.world_to_canvas(
            self.app.pose_canvas, pose.knee, bounds
        )
        self.app.on_pose_press(SimpleNamespace(x=knee_x, y=knee_y))
        target_x, target_y = self.app.world_to_canvas(
            self.app.pose_canvas,
            (pose.ankle[0] + 0.06, pose.ankle[1] + 0.26),
            bounds,
        )
        self.app.on_pose_drag(SimpleNamespace(x=target_x, y=target_y))
        self.app.on_pose_release(SimpleNamespace())

        self.assertNotEqual(self.app.final_q, before)
        self.assertIsNone(self.app.drag_target)
        self.assertIsNone(self.app._pose_drag_bounds)

    def test_pose_viewport_centres_the_subject_and_keeps_foot_label_space(self):
        state = self.app.states[-1]
        result = self.app.results[-1]
        bounds = self.app.pose_editor_bounds(
            self.app.pose_canvas, state, result, self.app.anthro()
        )
        points = (
            state.pose.heel,
            state.pose.toe,
            state.pose.ankle,
            state.pose.knee,
            state.pose.hip,
            state.pose.shoulder,
            state.pose.bar,
            state.pose.com,
            *state.pose.segment_coms.values(),
            (result.cop_x, 0.0),
        )
        screen_x = [
            self.app.world_to_canvas(self.app.pose_canvas, point, bounds)[0]
            for point in points
        ]
        subject_middle = (min(screen_x) + max(screen_x)) / 2.0
        self.assertAlmostEqual(
            subject_middle,
            self.app.pose_canvas.winfo_width() / 2.0,
            delta=2.0,
        )
        self.assertLess(bounds[0], min(point[0] for point in points))
        self.assertGreater(bounds[1], max(point[0] for point in points))
        self.assertLessEqual(bounds[2], -0.16)

    def test_parameter_controls_fit_inside_the_left_panel(self):
        self.assertGreater(self.app.left_panel.winfo_height(), 0)
        for widget in self.app.left_panel.winfo_children():
            if widget.winfo_ismapped():
                self.assert_inside(widget, self.app.left_panel)

    def test_left_controls_are_scrollable_on_a_small_screen(self):
        try:
            self.app.geometry("1024x700")
            self.app.update()
            scroll_region = tuple(
                int(float(value))
                for value in self.app.left_scroll_canvas.cget("scrollregion").split()
            )
            self.assertEqual(len(scroll_region), 4)
            self.assertGreater(
                scroll_region[3] - scroll_region[1],
                self.app.left_scroll_canvas.winfo_height(),
            )
            self.assertTrue(self.app.left_scrollbar.winfo_ismapped())
            self.assertGreater(int(self.app.status_label.cget("wraplength")), 0)
        finally:
            self.app.geometry("1480x920")
            self.app.update()

    def test_conditions_controls_fit_inside_the_conditions_frame(self):
        self.assertGreaterEqual(self.app.table_box.winfo_width(), 420)
        self.assertGreaterEqual(self.app.table_box.winfo_height(), 250)
        for widget in (
            self.app.table_buttons,
            self.app.table_notebook,
            self.app.file_box,
        ):
            self.assert_inside(widget, self.app.table_box)

    def test_condition_actions_stay_visible_on_every_tab(self):
        for tab in (
            self.app.conditions_tab,
            self.app.cursor_tab,
            self.app.differences_tab,
        ):
            with self.subTest(tab=str(tab)):
                self.app.table_notebook.select(tab)
                self.app.on_table_tab_changed()
                self.app.update_idletasks()
                self.assertTrue(self.app.table_buttons.winfo_ismapped())
                self.assertTrue(self.app.file_box.winfo_ismapped())

    def test_layout_remains_non_overlapping_after_window_resize(self):
        try:
            self.app.geometry("1200x800")
            self.app.update_idletasks()
            self.test_results_and_conditions_keep_distinct_vertical_slots()
            self.test_plot_controls_fit_inside_the_results_frame()
            self.test_parameter_controls_fit_inside_the_left_panel()
            self.test_conditions_controls_fit_inside_the_conditions_frame()
        finally:
            self.app.geometry("1480x920")
            self.app.update_idletasks()


if __name__ == "__main__":
    unittest.main()
