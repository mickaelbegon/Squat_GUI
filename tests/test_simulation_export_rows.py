import math
import unittest

from squat_gui.dynamics import simulate
from squat_gui.simulation_export_rows import build_export_rows, condition_summary
from squat_gui.simulation_service import anthropometry, condition_from_settings, simulate_condition


class SimulationExportRowsTests(unittest.TestCase):
    def test_service_records_equal_the_pure_export_projection(self):
        condition = condition_from_settings(
            {"duration_phase_s": 0.2}, (20.0, -55.0, -15.0), "equivalence",
            frames=3, backend="analytical",
        )
        rows, summary = simulate_condition(condition)
        anthro = anthropometry(condition)
        states, results = simulate(
            anthro, tuple(math.radians(value) for value in condition.q_segment_deg),
            condition.phase_durations, condition.frames, condition.max_torques,
            condition.angle_adapt, None, condition.velocity_adapt,
        )
        projected = build_export_rows(condition, anthro, states, results)

        self.assertEqual(rows, projected)
        self.assertEqual(summary, condition_summary(condition, projected, "analytical"))


if __name__ == "__main__":
    unittest.main()
