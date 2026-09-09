import csv
import unittest
from dataclasses import replace
from math import degrees, radians
from pathlib import Path

from squat_gui.anthropometry import Anthropometry
from squat_gui.app import SquatGui
from squat_gui.cli import (
    build_parser,
    condition_from_row,
    read_conditions_csv,
    simulate_condition,
)
from squat_gui.dynamics import simulate
from squat_gui.kinematics import (
    DEFAULT_SAMPLE_PERIOD_S,
    PhaseDurations,
    clinical_joint_values_from_segment_values,
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

    def test_public_lab_scenarios_use_the_gui_joint_angle_convention(self) -> None:
        path = Path(__file__).resolve().parents[1] / "Labo/scenarios/scenarios_labo_squat.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        self.assertEqual(
            [row["condition_id"] for row in rows],
            [
                "baseline",
                "limited_ankle_flexion",
                "wedge_20_deg",
                "posture_knee_dominant",
                "posture_hip_dominant",
                "balance_long_thigh_back",
                "balance_long_thigh_front",
                "balance_pregnant_back",
                "balance_pregnant_front",
                "load_100bw",
                "duration_fast",
            ],
        )
        self.assertTrue(
            {"ankle_deg", "knee_flexion_deg", "hip_flexion_deg"}.issubset(
                reader.fieldnames or ()
            )
        )
        self.assertTrue(
            {"q_shank_deg", "q_thigh_deg", "q_trunk_deg"}.isdisjoint(
                reader.fieldnames or ()
            )
        )

        defaults = build_parser().parse_args(["batch", str(path)])
        conditions = {
            condition.condition_id: condition
            for condition in read_conditions_csv(path, defaults)
        }
        expected_gui_angles = {
            "baseline": (25.0, 90.0, 120.0),
            "limited_ankle_flexion": (10.0, 90.0, 120.0),
            "wedge_20_deg": (10.0, 90.0, 120.0),
            "posture_knee_dominant": (35.0, 105.0, 80.0),
            "posture_hip_dominant": (15.0, 80.0, 100.0),
            "balance_long_thigh_back": (22.0, 80.0, 78.0),
            "balance_long_thigh_front": (22.0, 80.0, 78.0),
            "balance_pregnant_back": (22.0, 80.0, 78.0),
            "balance_pregnant_front": (22.0, 80.0, 78.0),
            "load_100bw": (22.0, 80.0, 78.0),
            "duration_fast": (22.0, 80.0, 78.0),
        }
        for condition_id, expected in expected_gui_angles.items():
            condition = conditions[condition_id]
            joint_values = clinical_joint_values_from_segment_values(
                tuple(radians(value) for value in condition.q_segment_deg)
            )
            actual = tuple(
                round(degrees(joint_values[joint]), 6)
                for joint in ("cheville", "genou", "hanche")
            )
            with self.subTest(condition_id=condition_id):
                self.assertEqual(actual, expected)

    def test_batch_parser_preserves_legacy_signed_joint_angle_compatibility(self) -> None:
        defaults = build_parser().parse_args(["batch", "legacy.csv"])
        clinical = condition_from_row(
            {
                "ankle_deg": "20",
                "knee_flexion_deg": "70",
                "hip_flexion_deg": "60",
            },
            1,
            defaults,
        )
        legacy = condition_from_row(
            {"ankle_deg": "20", "knee_deg": "-70", "hip_deg": "60"},
            1,
            defaults,
        )

        self.assertEqual(clinical.q_segment_deg, legacy.q_segment_deg)

    def test_lab_ankle_sequence_has_intended_analytical_support_contrast(self) -> None:
        path = Path(__file__).resolve().parents[1] / "Labo/scenarios/scenarios_labo_squat.csv"
        defaults = build_parser().parse_args(["batch", str(path)])
        conditions = {
            condition.condition_id: condition
            for condition in read_conditions_csv(path, defaults)
        }
        baseline = conditions["baseline"]
        limited = conditions["limited_ankle_flexion"]
        wedge = conditions["wedge_20_deg"]

        self.assertEqual(limited.q_segment_deg, wedge.q_segment_deg)
        self.assertFalse(limited.wedge_20_deg)
        self.assertTrue(wedge.wedge_20_deg)

        support_by_condition = {}
        for condition in (baseline, limited, wedge):
            rows, _summary = simulate_condition(
                replace(condition, backend="analytical")
            )
            support_by_condition[condition.condition_id] = [
                bool(row["support_point_in_functional_base"]) for row in rows
            ]

        self.assertTrue(all(support_by_condition["baseline"]))
        self.assertTrue(all(support_by_condition["wedge_20_deg"]))
        self.assertTrue(
            any(not in_support for in_support in support_by_condition["limited_ankle_flexion"])
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
