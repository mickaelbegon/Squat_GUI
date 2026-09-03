from __future__ import annotations

import json
import unittest

from squat_gui.session_persistence import (
    ComparisonReference,
    GuiSettings,
    SavedCondition,
    SessionDocument,
    SessionJsonCodec,
    SettingsReader,
)
from squat_gui.timeline import TimeMode


class SessionPersistenceTests(unittest.TestCase):
    def test_gui_snapshot_keeps_current_and_legacy_compatibility_keys(self) -> None:
        settings = GuiSettings(
            subject_profile="femme",
            bar_position="front",
            load_percent_bw=50.0,
            load_kg=35.0,
            shank_percent=1.0,
            thigh_percent=2.0,
            trunk_percent=3.0,
            anthropometry_mode="longueur seule",
            duration_excentrique_s=3.0,
            duration_isometrique_s=1.0,
            duration_concentrique_s=2.0,
            temporal_preset="",
            wedge_20_deg=True,
            frame=4,
            plot_choice="centre de masse",
            quantity="position",
            synchronized_source="angles articulaires",
            show_joints={"cheville": True},
            show_com_components={"horizontal": False},
            show_torque_components={"total ID": True},
            max_torques={"cheville": 100.0},
            torque_preset="manuel",
            show_torque_bounds=True,
            angle_adapt=False,
            velocity_adapt=True,
            optimize_bar_path_experimental=False,
            show_sprite_centers=False,
            show_segment_com=True,
            display_layers={"global_com": True},
            low_quality_sprites=False,
            time_mode=TimeMode.NORMALIZED.value,
            subplot_mode=True,
            show_phase_limits=True,
            show_phase_names=False,
            final_q_deg=[22.0, -58.0, 20.0],
            frame_count=101,
        ).to_mapping()

        self.assertFalse(settings["low_quality_sprites"])
        self.assertTrue(settings["refined_sprites"])
        self.assertTrue(settings["normalize_time"])
        self.assertEqual(settings["final_q_deg"], [22.0, -58.0, 20.0])

    def test_reader_centralizes_legacy_aliases(self) -> None:
        reader = SettingsReader.from_object(
            {
                "load_kg": 14.0,
                "duration_phase_s": 3.0,
                "refined_sprites": False,
                "normalize_time": True,
            }
        )

        self.assertEqual(reader.load_percent_bw(0.0), 20.0)
        self.assertEqual(reader.phase_durations(), (3.0, 2.0, 3.0))
        self.assertTrue(reader.low_quality_sprites())
        self.assertEqual(reader.time_mode(), TimeMode.NORMALIZED.value)

    def test_version_2_document_round_trip_preserves_existing_shape(self) -> None:
        payload = {
            "version": 2,
            "settings": {"subject_profile": "homme", "load_percent_bw": 25.0},
            "conditions": [
                {
                    "iid": "condition-1",
                    "label": "1",
                    "settings": {"bar_position": "back"},
                    "final_q_deg": [22.0, -58.0, 20.0],
                    "comparison_reference": {
                        "label": "référence",
                        "settings": {"bar_position": "front"},
                        "final_q_deg": [20.0, -60.0, 18.0],
                    },
                }
            ],
        }

        document = SessionJsonCodec.loads(json.dumps(payload))

        self.assertEqual(document.to_mapping(), payload)
        self.assertEqual(json.loads(SessionJsonCodec.dumps(document)), payload)

    def test_runtime_saved_condition_serializes_without_runtime_results(self) -> None:
        condition = SavedCondition(
            label="1",
            settings={"subject_profile": "homme"},
            final_q_deg=[22.0, -58.0, 20.0],
            states=[],
            results=[],
            comparison_reference=ComparisonReference(
                label="0",
                settings={"subject_profile": "femme"},
                final_q_deg=[20.0, -60.0, 18.0],
            ),
            difference_summary="profil modifié",
        )

        document = SessionDocument.from_runtime(
            {"subject_profile": "homme"}, {"condition-1": condition}
        )
        persisted = document.to_mapping()["conditions"][0]

        self.assertNotIn("states", persisted)
        self.assertNotIn("results", persisted)
        self.assertNotIn("difference_summary", persisted)
        self.assertEqual(persisted["comparison_reference"]["label"], "0")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
