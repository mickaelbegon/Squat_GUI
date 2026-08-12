import unittest

from squat_gui.kinematics import PhaseDurations
from squat_gui.timeline import (
    TimeMode,
    nearest_time_index,
    phase_windows,
    plot_time,
    time_axis_label,
)


class TimelineTests(unittest.TestCase):
    def test_phase_windows_use_exact_configured_boundaries(self) -> None:
        durations = PhaseDurations(4.0, 2.0, 3.0)

        windows = phase_windows(durations, mode=TimeMode.CENTERED)

        self.assertEqual(
            [(window.name, window.start, window.end) for window in windows],
            [
                ("excentrique", -5.0, -1.0),
                ("isometrique", -1.0, 1.0),
                ("concentrique", 1.0, 4.0),
            ],
        )

    def test_normalized_phase_windows_use_zero_to_one_hundred_percent(self) -> None:
        durations = PhaseDurations(6.0, 1.0, 2.0)

        windows = phase_windows(durations, mode=TimeMode.NORMALIZED)

        self.assertAlmostEqual(windows[0].start, 0.0)
        self.assertAlmostEqual(windows[0].end, 100.0 * 6.0 / 9.0)
        self.assertAlmostEqual(windows[1].end, 100.0 * 7.0 / 9.0)
        self.assertAlmostEqual(windows[2].end, 100.0)

    def test_plot_time_places_squat_reference_at_zero(self) -> None:
        durations = PhaseDurations(4.0, 2.0, 4.0)

        self.assertEqual(
            plot_time(
                durations.squat_reference_time, durations, mode=TimeMode.CENTERED
            ),
            0.0,
        )

    def test_absolute_time_starts_at_zero_and_keeps_duration(self) -> None:
        durations = PhaseDurations(6.0, 1.0, 2.0)

        self.assertEqual(plot_time(0.0, durations, mode=TimeMode.ABSOLUTE), 0.0)
        self.assertEqual(plot_time(9.0, durations, mode=TimeMode.ABSOLUTE), 9.0)
        self.assertIn("depuis le début", time_axis_label(TimeMode.ABSOLUTE))

    def test_nearest_index_is_deterministic_on_a_tie(self) -> None:
        self.assertEqual(nearest_time_index([0.0, 0.05, 0.10], 0.075), 1)

    def test_empty_timeline_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            nearest_time_index([], 0.0)


if __name__ == "__main__":
    unittest.main()
