"""Geometry regression tests for the Tkinter layout.

These tests are skipped when the test runner has no display. On a desktop/CI
runner with Tk available they exercise the real widget positions after layout.
"""

import os
import tkinter as tk
import unittest

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
            cls.app.update_idletasks()
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

    def test_parameter_controls_fit_inside_the_left_panel(self):
        self.assertGreater(self.app.left_panel.winfo_height(), 0)
        for widget in self.app.left_panel.winfo_children():
            if widget.winfo_ismapped():
                self.assert_inside(widget, self.app.left_panel)

    def test_conditions_controls_fit_inside_the_conditions_frame(self):
        self.assertGreaterEqual(self.app.table_box.winfo_width(), 420)
        self.assertGreaterEqual(self.app.table_box.winfo_height(), 250)
        for widget in (
            self.app.table_buttons,
            self.app.table_notebook,
            self.app.file_box,
        ):
            self.assert_inside(widget, self.app.table_box)

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
