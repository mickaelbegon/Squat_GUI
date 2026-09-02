import csv
import unittest
from dataclasses import replace
from math import radians
from pathlib import Path

from squat_gui.anthropometry import Anthropometry
from squat_gui.app import SquatGui
from squat_gui.cli import build_parser, read_conditions_csv, simulate_condition
from squat_gui.dynamics import simulate
from squat_gui.kinematics import (
    DEFAULT_SAMPLE_PERIOD_S,
    PhaseDurations,
    frame_count_for_duration,
    joint_values_from_segment_values,
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

    def test_reference_and_stability_lab_presets_are_plausible_and_supported(self) -> None:
        path = Path(__file__).resolve().parents[1] / "Labo/scenarios/scenarios_labo_squat.csv"
        defaults = build_parser().parse_args(["batch", str(path)])
        conditions = {
            condition.condition_id: condition
            for condition in read_conditions_csv(path, defaults)
        }
        expected_joint_angles = {
            "baseline": (25.0, -90.0, 120.0),
            "stability_forward": (30.0, -95.0, 115.0),
            "stability_backward": (25.0, -85.0, 105.0),
        }
        for condition_id, expected in expected_joint_angles.items():
            condition = conditions[condition_id]
            joint_values = joint_values_from_segment_values(
                tuple(radians(value) for value in condition.q_segment_deg)
            )
            actual = tuple(
                round(joint_values[joint] * 180.0 / 3.141592653589793, 6)
                for joint in ("cheville", "genou", "hanche")
            )
            with self.subTest(condition_id=condition_id):
                self.assertEqual(actual, expected)
                rows, _summary = simulate_condition(
                    replace(condition, backend="analytical")
                )
                self.assertTrue(
                    all(row["support_point_in_functional_base"] for row in rows)
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
