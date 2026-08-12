import unittest

from squat_gui.didactics import (
    CUSTOM_TEMPORAL_PRESET,
    TEMPORAL_PRESETS,
    RevealMode,
    layers_for_reveal,
    matching_temporal_preset,
    reveal_mode_for_step,
)
from squat_gui.kinematics import PhaseDurations
from squat_gui.kinematics import DEFAULT_SAMPLE_PERIOD_S, frame_count_for_duration


class TemporalPresetTests(unittest.TestCase):
    def test_six_named_presets_are_distinct(self) -> None:
        self.assertEqual(len(TEMPORAL_PRESETS), 6)
        self.assertEqual(len({preset.name for preset in TEMPORAL_PRESETS}), 6)
        self.assertEqual(len({preset.durations for preset in TEMPORAL_PRESETS}), 6)

    def test_reference_preserves_the_validated_default(self) -> None:
        reference = TEMPORAL_PRESETS[0]

        self.assertEqual(reference.name, "Référence")
        self.assertEqual(reference.durations, PhaseDurations(4.0, 2.0, 4.0))

    def test_custom_durations_are_identified(self) -> None:
        self.assertEqual(
            matching_temporal_preset(PhaseDurations(3.0, 1.0, 4.0)),
            CUSTOM_TEMPORAL_PRESET,
        )

    def test_every_preset_keeps_the_validated_sample_period(self) -> None:
        for preset in TEMPORAL_PRESETS:
            with self.subTest(preset=preset.name):
                count = frame_count_for_duration(preset.durations)
                self.assertAlmostEqual(
                    preset.durations.total / (count - 1),
                    DEFAULT_SAMPLE_PERIOD_S,
                )


class ProgressiveRevealTests(unittest.TestCase):
    def test_guided_steps_reveal_observation_then_kinematics_then_dynamics(
        self,
    ) -> None:
        self.assertEqual(reveal_mode_for_step(0), RevealMode.OBSERVATION)
        self.assertEqual(reveal_mode_for_step(5), RevealMode.OBSERVATION)
        self.assertEqual(reveal_mode_for_step(6), RevealMode.KINEMATICS)
        self.assertEqual(reveal_mode_for_step(7), RevealMode.DYNAMICS)
        self.assertEqual(reveal_mode_for_step(10), RevealMode.DYNAMICS)

    def test_observation_reveals_only_the_subject_and_bar(self) -> None:
        layers = layers_for_reveal(RevealMode.OBSERVATION)

        visible_scientific_layers = [
            value for name, value in vars(layers).items() if name != "refined_sprites"
        ]
        self.assertFalse(any(visible_scientific_layers))

    def test_kinematics_excludes_dynamic_outputs(self) -> None:
        layers = layers_for_reveal(RevealMode.KINEMATICS)

        self.assertTrue(layers.global_com)
        self.assertTrue(layers.joint_coordinates)
        self.assertFalse(layers.joint_angles)
        self.assertFalse(layers.cop_zmp)
        self.assertFalse(layers.grf)
        self.assertFalse(layers.alerts)

    def test_dynamics_adds_forces_support_and_capacity(self) -> None:
        layers = layers_for_reveal(RevealMode.DYNAMICS)

        self.assertTrue(layers.grf)
        self.assertTrue(layers.weight)
        self.assertTrue(layers.cop_zmp)
        self.assertTrue(layers.capacity_rings)
        self.assertTrue(layers.alerts)


if __name__ == "__main__":
    unittest.main()
