import csv
import unittest
from math import radians
from pathlib import Path

from squat_gui.anthropometry import Anthropometry
from squat_gui.app import SquatGui
from squat_gui.dynamics import simulate
from squat_gui.kinematics import (
    DEFAULT_SAMPLE_PERIOD_S,
    PhaseDurations,
    frame_count_for_duration,
)


class TemporalSamplingTests(unittest.TestCase):
    def test_default_ten_second_motion_uses_fifty_milliseconds(self) -> None:
        durations = PhaseDurations(4.0, 2.0, 4.0)
        frame_count = frame_count_for_duration(durations)

        self.assertEqual(frame_count, 201)
        self.assertAlmostEqual(
            durations.total / (frame_count - 1), DEFAULT_SAMPLE_PERIOD_S
        )

    def test_frame_count_tracks_phase_durations(self) -> None:
        durations = PhaseDurations(3.0, 1.0, 3.0)

        self.assertEqual(frame_count_for_duration(durations), 141)

    def test_invalid_sample_period_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            frame_count_for_duration(PhaseDurations(), 0.0)

    def test_public_lab_scenarios_preserve_fifty_milliseconds(self) -> None:
        path = Path(__file__).resolve().parents[1] / "Labo/scenarios/scenarios_labo_squat.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(condition_id=row["condition_id"]):
                durations = PhaseDurations(
                    float(row["duration_excentrique_s"]),
                    float(row["duration_isometrique_s"]),
                    float(row["duration_concentrique_s"]),
                )
                self.assertEqual(
                    int(row["frames"]), frame_count_for_duration(durations)
                )

    def test_centered_time_is_exactly_zero_at_squat_midpoint(self) -> None:
        durations = PhaseDurations(4.0, 2.0, 4.0)
        states, _results = simulate(
            Anthropometry(),
            (radians(22.0), radians(-58.0), radians(20.0)),
            durations,
            frame_count_for_duration(durations),
            {"cheville": 222.0, "genou": 380.0, "hanche": 376.0},
            True,
            None,
        )
        gui = object.__new__(SquatGui)
        centered = gui.centered_times(states)

        self.assertAlmostEqual(centered[100], 0.0)
        self.assertAlmostEqual(centered[0], -5.0)
        self.assertAlmostEqual(centered[-1], 5.0)


if __name__ == "__main__":
    unittest.main()
