import unittest

from squat_gui.comparison import difference_summary, parameter_differences


class ControlledVariableTests(unittest.TestCase):
    def test_display_only_settings_are_excluded(self) -> None:
        reference = {
            "load_percent_bw": 20.0,
            "display_layers": {"grf": True},
            "plot_choice": "centre de masse",
        }
        compared = {
            **reference,
            "display_layers": {"grf": False},
            "plot_choice": "couples articulaires",
        }

        self.assertEqual(
            parameter_differences(reference, [1, 2, 3], compared, [1, 2, 3]), ()
        )

    def test_semantic_diff_reports_scientific_changes_with_units(self) -> None:
        reference = {
            "load_percent_bw": 20.0,
            "duration_excentrique_s": 4.0,
            "max_torques": {"cheville": 100.0, "genou": 200.0, "hanche": 250.0},
        }
        compared = {
            **reference,
            "load_percent_bw": 40.0,
            "duration_excentrique_s": 6.0,
        }

        differences = parameter_differences(reference, [1, 2, 3], compared, [1, 2, 5])

        self.assertEqual(
            [difference.label for difference in differences],
            ["Charge", "Durée excentrique", "Orientation tronc basse"],
        )
        self.assertEqual(differences[0].reference, "20.00 % BW")
        self.assertEqual(differences[0].compared, "40.00 % BW")
        self.assertEqual(
            difference_summary(differences),
            "Charge, Durée excentrique, Orientation tronc basse",
        )

    def test_bar_stabilization_is_a_scientific_condition_parameter(self) -> None:
        reference = {"optimize_bar_path_experimental": False}
        compared = {"optimize_bar_path_experimental": True}

        differences = parameter_differences(
            reference, [1, 2, 3], compared, [1, 2, 3]
        )

        self.assertEqual(len(differences), 1)
        self.assertEqual(
            differences[0].label, "Stabilisation expérimentale de la barre"
        )
        self.assertEqual(differences[0].reference, "non")
        self.assertEqual(differences[0].compared, "oui")


if __name__ == "__main__":
    unittest.main()
