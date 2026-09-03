from __future__ import annotations

import unittest

from squat_gui import cli
from squat_gui.export_io import write_csv
from squat_gui.simulation_service import (
    Condition,
    anthropometry,
    condition_from_settings,
    condition_summary,
    simulate_condition,
)


class SimulationServiceTests(unittest.TestCase):
    def test_cli_keeps_legacy_service_exports(self) -> None:
        self.assertIs(cli.Condition, Condition)
        self.assertIs(cli.anthropometry, anthropometry)
        self.assertIs(cli.condition_from_settings, condition_from_settings)
        self.assertIs(cli.simulate_condition, simulate_condition)
        self.assertIs(cli.condition_summary, condition_summary)
        self.assertIs(cli.write_csv, write_csv)

    def test_condition_computed_properties_are_preserved(self) -> None:
        condition = Condition(
            condition_id="test",
            load_percent_bw=50.0,
            subject_profile="homme",
            bar_position="back",
            wedge_20_deg=False,
            shank_percent=0.0,
            thigh_percent=0.0,
            trunk_percent=0.0,
            anthropometry_mode="longueur seule",
            duration_excentrique_s=4.0,
            duration_isometrique_s=2.0,
            duration_concentrique_s=4.0,
            q_segment_deg=(22.0, -58.0, 20.0),
            torque_preset="Anderson actif x2",
            max_torques={"cheville": 1.0, "genou": 2.0, "hanche": 3.0},
            angle_adapt=True,
            velocity_adapt=True,
            frames=101,
            backend="analytical",
        )

        self.assertEqual(condition.load_kg, 35.0)
        self.assertEqual(condition.total_duration_s, 10.0)
        self.assertEqual(condition.phase_durations.excentrique, 4.0)


if __name__ == "__main__":
    unittest.main()
