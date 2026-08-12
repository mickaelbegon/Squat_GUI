import unittest

from squat_gui.anthropometry import Anthropometry
from squat_gui.backend import biomod_cache_key, biomod_text
from squat_gui.cli import condition_from_settings, simulate_condition
from squat_gui.comparison import parameter_differences


class AnthropometryModeTests(unittest.TestCase):
    def test_modes_are_identical_at_reference_lengths(self) -> None:
        length_only = Anthropometry(scaling_mode="longueur seule")
        recalibrated = Anthropometry(scaling_mode="morphotype recalibre")

        for name in ("foot", "shank", "thigh", "trunk"):
            reference = getattr(length_only, name)
            candidate = getattr(recalibrated, name)
            self.assertAlmostEqual(candidate.mass, reference.mass)
            self.assertAlmostEqual(candidate.inertia, reference.inertia)

    def test_length_only_changes_geometry_but_preserves_mass_and_inertia(self) -> None:
        reference = Anthropometry()
        scaled = Anthropometry(
            shank_scale=1.05,
            thigh_scale=0.95,
            trunk_scale=1.025,
            scaling_mode="longueur seule",
        )

        for name in ("foot", "shank", "thigh", "trunk"):
            baseline = getattr(reference, name)
            candidate = getattr(scaled, name)
            self.assertAlmostEqual(candidate.mass, baseline.mass)
            self.assertAlmostEqual(candidate.inertia, baseline.inertia)
        self.assertAlmostEqual(scaled.shank.length / reference.shank.length, 1.05)
        self.assertAlmostEqual(scaled.thigh.length / reference.thigh.length, 0.95)
        self.assertAlmostEqual(scaled.trunk.length / reference.trunk.length, 1.025)

    def test_recalibrated_morphotype_preserves_total_mass_and_recomputes_inertia(
        self,
    ) -> None:
        reference = Anthropometry()
        scaled = Anthropometry(
            shank_scale=1.05,
            thigh_scale=0.95,
            trunk_scale=1.025,
            scaling_mode="morphotype recalibre",
        )

        self.assertAlmostEqual(sum(segment.mass for segment in scaled.segments), 70.0)
        self.assertNotAlmostEqual(scaled.shank.mass, reference.shank.mass)
        self.assertNotAlmostEqual(scaled.thigh.inertia, reference.thigh.inertia)
        self.assertIn("densite lineique constante", scaled.scaling_rule)

    def test_unknown_mode_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Anthropometry(scaling_mode="boite noire")


class BarPositionPropagationTests(unittest.TestCase):
    def test_biomod_cache_key_does_not_merge_distinct_cli_values(self) -> None:
        first = Anthropometry(bar_mass=10.001, thigh_scale=1.0001)
        second = Anthropometry(bar_mass=10.049, thigh_scale=1.0004)
        self.assertNotEqual(biomod_cache_key(first), biomod_cache_key(second))

    def test_all_bar_positions_propagate_through_geometry_dynamics_and_export(
        self,
    ) -> None:
        positions = ("front", "back", "over-head")
        rows_by_position = {}
        keys = set()
        biomods = set()
        for position in positions:
            settings = {
                "subject_profile": "homme",
                "bar_position": position,
                "load_percent_bw": 40.0,
                "anthropometry_mode": "morphotype recalibre",
                "shank_percent": 5.0,
                "thigh_percent": -5.0,
                "trunk_percent": 2.5,
            }
            condition = condition_from_settings(
                settings,
                [22.0, -58.0, 20.0],
                position,
                frames=5,
                backend="analytical",
            )
            rows, _summary = simulate_condition(condition)
            rows_by_position[position] = rows[2]
            anthro = Anthropometry(
                bar_mass=28.0,
                shank_scale=1.05,
                thigh_scale=0.95,
                trunk_scale=1.025,
                scaling_mode="morphotype recalibre",
                bar_position=position,
            )
            keys.add(biomod_cache_key(anthro))
            biomods.add(biomod_text(anthro))

        self.assertEqual(len(keys), 3)
        self.assertEqual(len(biomods), 3)
        self.assertEqual(
            {row["bar_position"] for row in rows_by_position.values()}, set(positions)
        )
        self.assertEqual(
            {row["anthropometry_mode"] for row in rows_by_position.values()},
            {"morphotype recalibre"},
        )
        self.assertEqual(
            len(
                {
                    (round(float(row["bar_x_m"]), 9), round(float(row["bar_y_m"]), 9))
                    for row in rows_by_position.values()
                }
            ),
            3,
        )
        self.assertEqual(
            len(
                {
                    tuple(
                        round(float(row[f"{joint}_torque_Nm"]), 9)
                        for joint in ("cheville", "genou", "hanche")
                    )
                    for row in rows_by_position.values()
                }
            ),
            3,
        )
        self.assertEqual(
            {
                round(float(row["trunk_mass_kg"]), 12)
                for row in rows_by_position.values()
            },
            {round(float(rows_by_position["back"]["trunk_mass_kg"]), 12)},
        )
        self.assertEqual(
            {
                round(float(row["trunk_inertia_kg_m2"]), 12)
                for row in rows_by_position.values()
            },
            {round(float(rows_by_position["back"]["trunk_inertia_kg_m2"]), 12)},
        )

    def test_bar_position_is_a_controlled_variable(self) -> None:
        differences = parameter_differences(
            {"bar_position": "back"},
            [22.0, -58.0, 20.0],
            {"bar_position": "front"},
            [22.0, -58.0, 20.0],
        )

        self.assertEqual(len(differences), 1)
        self.assertEqual(differences[0].label, "Position de barre")


if __name__ == "__main__":
    unittest.main()
