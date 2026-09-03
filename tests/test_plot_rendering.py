import unittest
from math import inf, nan

from squat_gui.kinematics import PhaseDurations
from squat_gui.plot_rendering import (
    PhaseMarkerDataset,
    blend_color,
    component_color,
    condition_color,
    format_axis_value,
    kinematic_unit,
    linear_position,
    linear_ticks,
    padded_value_bounds,
    phase_marker_layout,
    plot_time_bounds,
    plot_unit,
    time_marker_layout,
    torque_component_styles,
    value_bounds_with_zero,
)
from squat_gui.timeline import TimeMode


class PlotRenderingTests(unittest.TestCase):
    def test_time_bounds_cover_modes_fallbacks_and_constant_series(self) -> None:
        durations = PhaseDurations(2.0, 1.0, 3.0)

        self.assertEqual(
            plot_time_bounds([], TimeMode.NORMALIZED, durations),
            (0.0, 100.0),
        )
        self.assertEqual(
            plot_time_bounds([], TimeMode.ABSOLUTE, durations),
            (0.0, 6.0),
        )
        self.assertEqual(
            plot_time_bounds([], TimeMode.CENTERED, durations),
            (-2.5, 3.5),
        )
        self.assertEqual(
            plot_time_bounds([[4.0], []], TimeMode.ABSOLUTE, durations),
            (3.0, 5.0),
        )
        self.assertEqual(
            plot_time_bounds([[1.0, 3.0], [-2.0]], TimeMode.CENTERED, durations),
            (-2.0, 3.0),
        )

    def test_linear_layout_produces_ticks_and_positions(self) -> None:
        self.assertEqual(linear_position(5.0, 20.0, 120.0, 0.0, 10.0), 70.0)
        ticks = linear_ticks(-10.0, 10.0, 100.0, 0.0)

        self.assertEqual([tick.value for tick in ticks], [-10.0, -5.0, 0.0, 5.0, 10.0])
        self.assertEqual(
            [tick.coordinate for tick in ticks],
            [100.0, 75.0, 50.0, 25.0, 0.0],
        )
        with self.assertRaisesRegex(ValueError, "au moins deux"):
            linear_ticks(0.0, 1.0, 0.0, 100.0, count=1)

    def test_plot_palette_and_torque_styles_are_stable(self) -> None:
        self.assertEqual(condition_color(0, 1), "#2e7d54")
        self.assertEqual(condition_color(0, 3), "#c6332c")
        self.assertEqual(condition_color(1, 3), "#2e7d54")
        self.assertEqual(condition_color(2, 3), "#2a8ca6")
        self.assertEqual(blend_color("#000000", "#ffffff", 0.5), "#808080")
        self.assertEqual(component_color("#204060", "M(q) qddot"), "#204060")
        self.assertNotEqual(
            component_color("#204060", "contact externe (signé)"),
            "#204060",
        )
        self.assertEqual(torque_component_styles()["total ID"], (3, None, None))

    def test_value_bounds_ignore_non_finite_values_and_keep_references(self) -> None:
        self.assertEqual(value_bounds_with_zero([nan, inf]), (-1.0, 1.0))
        self.assertEqual(value_bounds_with_zero([10.0]), (-0.5, 10.5))
        self.assertEqual(padded_value_bounds([10.0, 20.0]), (9.5, 20.5))
        self.assertEqual(
            padded_value_bounds([10.0], [-20.0], include_hundred=True),
            (-26.0, 106.0),
        )

    def test_time_markers_are_clamped_and_center_reference_is_optional(self) -> None:
        centered = time_marker_layout(
            mode=TimeMode.CENTERED,
            show_phase_limits=True,
            current_time=50.0,
            x0=0.0,
            x1=200.0,
            tmin=-1.0,
            tmax=1.0,
        )
        absolute = time_marker_layout(
            mode=TimeMode.ABSOLUTE,
            show_phase_limits=True,
            current_time=0.5,
            x0=0.0,
            x1=200.0,
            tmin=0.0,
            tmax=1.0,
        )

        self.assertEqual(centered.squat_reference_x, 100.0)
        self.assertEqual(centered.current_time_x, 200.0)
        self.assertIsNone(absolute.squat_reference_x)
        self.assertEqual(absolute.current_time_x, 100.0)

    def test_phase_layout_centers_labels_and_prefixes_comparisons(self) -> None:
        durations = PhaseDurations(1.0, 1.0, 1.0)
        layout = phase_marker_layout(
            [
                PhaseMarkerDataset("A", durations, "#111111"),
                PhaseMarkerDataset("B", durations, "#222222"),
            ],
            mode=TimeMode.CENTERED,
            show_limits=True,
            show_names=True,
            x0=0.0,
            x1=300.0,
            tmin=-1.5,
            tmax=1.5,
        )

        self.assertEqual([marker.x for marker in layout.boundaries], [100.0, 200.0] * 2)
        self.assertEqual(
            [marker.x for marker in layout.labels],
            [50.0, 150.0, 250.0] * 2,
        )
        self.assertEqual(layout.labels[0].text, "A: excentrique")
        self.assertEqual(layout.labels[-1].text, "B: concentrique")
        self.assertEqual(layout.labels[-1].row, 1)

    def test_units_and_axis_formatting_remain_presentation_rules(self) -> None:
        self.assertEqual(kinematic_unit("centre de masse", "acceleration"), "m/s²")
        self.assertEqual(kinematic_unit("angles articulaires", "vitesse"), "deg/s")
        self.assertEqual(plot_unit("cinematique articulaire", "acceleration"), "deg/s2")
        self.assertEqual(plot_unit("couples articulaires", "position"), "Nm")
        self.assertEqual(format_axis_value(123.4), "123")
        self.assertEqual(format_axis_value(12.34), "12.3")
        self.assertEqual(format_axis_value(1.234), "1.23")
        self.assertEqual(format_axis_value(0.125), "0.125")


if __name__ == "__main__":
    unittest.main()
