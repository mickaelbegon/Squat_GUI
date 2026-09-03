import unittest

from squat_gui.didactics import (
    CUSTOM_TEMPORAL_PRESET,
    DYNAMIC_PHASE_DURATION_OPTIONS,
    DIDACTIC_STEPS,
    DidacticPathState,
    ISOMETRIC_PHASE_DURATION_OPTIONS,
    TEMPORAL_PRESETS,
    RevealMode,
    bounded_phase_durations,
    clamp_didactic_step,
    didactic_focus_keys,
    didactic_message,
    didactic_step_pieces,
    layers_for_reveal,
    matching_temporal_preset,
    phase_duration_triplet,
    reveal_mode_for_step,
    temporal_preset_display,
)
from squat_gui.kinematics import PhaseDurations
from squat_gui.kinematics import DEFAULT_SAMPLE_PERIOD_S, frame_count_for_duration


class TemporalPresetTests(unittest.TestCase):
    def test_five_named_presets_are_distinct(self) -> None:
        self.assertEqual(len(TEMPORAL_PRESETS), 5)
        self.assertEqual(len({preset.name for preset in TEMPORAL_PRESETS}), 5)
        self.assertEqual(len({preset.durations for preset in TEMPORAL_PRESETS}), 5)

    def test_reference_preserves_the_validated_default(self) -> None:
        reference = TEMPORAL_PRESETS[0]

        self.assertEqual(reference.name, "Ref")
        self.assertEqual(reference.durations, PhaseDurations(2.0, 1.0, 2.0))
        self.assertEqual(phase_duration_triplet(reference.durations), "2 | 1 | 2")
        self.assertEqual(temporal_preset_display(reference), "Ref — 2 | 1 | 2 s")

    def test_presets_match_the_validated_triplets(self) -> None:
        self.assertEqual(
            [(preset.name, preset.durations) for preset in TEMPORAL_PRESETS],
            [
                ("Ref", PhaseDurations(2.0, 1.0, 2.0)),
                ("Lent", PhaseDurations(4.0, 2.0, 4.0)),
                ("Rapide", PhaseDurations(1.0, 0.5, 1.0)),
                ("Lent/Rapide", PhaseDurations(4.0, 1.0, 1.0)),
                ("Rapide/Lent", PhaseDurations(1.0, 1.0, 4.0)),
            ],
        )

    def test_presets_use_the_revised_discrete_duration_scale(self) -> None:
        for preset in TEMPORAL_PRESETS:
            with self.subTest(preset=preset.name):
                self.assertIn(
                    preset.durations.excentrique, DYNAMIC_PHASE_DURATION_OPTIONS
                )
                self.assertIn(
                    preset.durations.concentrique, DYNAMIC_PHASE_DURATION_OPTIONS
                )
                self.assertIn(
                    preset.durations.isometrique, ISOMETRIC_PHASE_DURATION_OPTIONS
                )
        self.assertNotIn(1.5, ISOMETRIC_PHASE_DURATION_OPTIONS)

    def test_legacy_values_are_migrated_to_the_nearest_exposed_option(self) -> None:
        self.assertEqual(
            bounded_phase_durations(PhaseDurations(6.0, 1.5, 3.0)),
            PhaseDurations(4.0, 2.0, 4.0),
        )

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
    def test_guided_path_has_eleven_tagged_messages(self) -> None:
        self.assertEqual(len(DIDACTIC_STEPS), 11)
        self.assertEqual(
            didactic_step_pieces(0)[1], ("sujet", "sujet")
        )
        self.assertIn(
            "clic droit",
            "".join(text for text, _tag in didactic_step_pieces(4)),
        )
        self.assertEqual(
            didactic_step_pieces(10)[1], ("Variables contrôlées", "phase")
        )

    def test_guided_step_and_semantic_focus_are_clamped(self) -> None:
        self.assertEqual(clamp_didactic_step(-5), 0)
        self.assertEqual(clamp_didactic_step(99), 10)
        self.assertEqual(didactic_focus_keys(-1), ("subject",))
        self.assertEqual(didactic_focus_keys(99), ("comparison",))

    def test_guided_path_navigation_preserves_transition_rules(self) -> None:
        inactive = DidacticPathState(False, 8)

        self.assertEqual(inactive.advanced(), DidacticPathState(True, 0))
        self.assertEqual(inactive.retreated(), inactive)
        self.assertEqual(DidacticPathState(True, 0).retreated(), DidacticPathState(True, 0))
        self.assertEqual(DidacticPathState(True, 10).advanced(), DidacticPathState(True, 10))
        self.assertEqual(DidacticPathState(True, 6).reveal_mode, RevealMode.KINEMATICS)
        self.assertFalse(DidacticPathState(True, 10).can_go_forward)

    def test_inactive_message_stays_outside_the_guided_step_content(self) -> None:
        self.assertEqual(
            didactic_message(False, 4),
            (("Activer pour guider une exploration etape par etape.", None),),
        )
        self.assertEqual(didactic_message(True, 8), didactic_step_pieces(8))

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
