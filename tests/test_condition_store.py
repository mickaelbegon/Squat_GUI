import unittest
from math import radians

from squat_gui.anthropometry import Anthropometry
from squat_gui.condition_store import (
    comparison_reference,
    condition_table_metrics,
    create_saved_condition,
    resolve_condition_comparison,
    selected_conditions,
)
from squat_gui.dynamics import inverse_dynamics
from squat_gui.kinematics import PhaseDurations, motion_state


class ConditionStoreTests(unittest.TestCase):
    def condition(self, label: str, *, reference=None, load: float = 20.0):
        anthro = Anthropometry()
        durations = PhaseDurations(1.0, 0.0, 1.0)
        states = [
            motion_state(
                anthro,
                (radians(20.0), radians(-60.0), radians(25.0)),
                durations,
                time,
            )
            for time in (0.0, 1.0, 2.0)
        ]
        results = [
            inverse_dynamics(
                anthro,
                state,
                {"cheville": 180.0, "genou": 220.0, "hanche": 260.0},
                True,
            )
            for state in states
        ]
        return create_saved_condition(
            label=label,
            settings={"subject_profile": "homme", "load_percent_bw": load},
            final_q_deg=[20.0, -60.0, 25.0],
            states=states,
            results=results,
            reference=reference,
        )

    def test_selection_keeps_table_order_and_ignores_unknown_rows(self) -> None:
        first = self.condition("première")
        second = self.condition("deuxième")

        selected = selected_conditions(
            {"a": first, "b": second}, ("b", "inconnue", "a")
        )

        self.assertEqual([iid for iid, _condition in selected], ["b", "a"])

    def test_two_selected_conditions_take_priority_over_saved_reference(self) -> None:
        reference = self.condition("référence", load=10.0)
        first = self.condition("première", reference=comparison_reference(reference))
        second = self.condition("deuxième", load=40.0)

        comparison = resolve_condition_comparison(
            {"one": first, "two": second}, ("one", "two")
        )

        self.assertIsNotNone(comparison)
        assert comparison is not None
        self.assertEqual(comparison.reference_label, "première")
        self.assertEqual(comparison.compared_label, "deuxième")
        self.assertEqual([item.label for item in comparison.differences], ["Charge"])

    def test_one_selected_condition_uses_its_persisted_reference(self) -> None:
        reference = self.condition("référence", load=10.0)
        condition = self.condition("copie", reference=comparison_reference(reference), load=30.0)

        comparison = resolve_condition_comparison({"copy": condition}, ("copy",))

        self.assertIsNotNone(comparison)
        assert comparison is not None
        self.assertEqual(comparison.reference_label, "référence")
        self.assertEqual(comparison.compared_label, "copie")
        self.assertEqual([item.label for item in comparison.differences], ["Charge"])

    def test_pending_duplicate_reference_compares_against_live_editor(self) -> None:
        reference = self.condition("référence", load=10.0)

        comparison = resolve_condition_comparison(
            {"reference": reference},
            (),
            pending_reference_iid="reference",
            current_settings={"subject_profile": "homme", "load_percent_bw": 50.0},
            current_final_q_deg=[20.0, -60.0, 25.0],
        )

        self.assertIsNotNone(comparison)
        assert comparison is not None
        self.assertEqual(comparison.compared_label, "courant")
        self.assertEqual([item.label for item in comparison.differences], ["Charge"])

    def test_created_condition_keeps_reference_snapshot_and_metrics(self) -> None:
        reference = self.condition("référence", load=10.0)
        snapshot = comparison_reference(reference)
        condition = self.condition("copie", reference=snapshot, load=40.0)

        metrics = condition_table_metrics(condition)

        self.assertEqual(condition.difference_summary, "Charge")
        self.assertGreater(metrics.peak_torques["genou"], 0.0)
        self.assertIn("·", metrics.limiting_label)
        self.assertTrue(metrics.utilization_label.endswith("%") or metrics.utilization_label == "n.d.")


if __name__ == "__main__":
    unittest.main()
