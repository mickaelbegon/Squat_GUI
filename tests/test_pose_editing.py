import unittest
from math import atan2, radians

from squat_gui.anthropometry import Anthropometry
from squat_gui.kinematics import pose_from_angles
from squat_gui.pose_editing import (
    apply_clinical_angle,
    clamp_segment_angles,
    clinical_angle_editor_spec,
    clinical_joint_angles_deg,
    drag_updated_q,
    nearest_named_point,
)


class PoseEditingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.q = (radians(22.0), radians(-58.0), radians(20.0))

    def test_handle_selection_uses_strict_twenty_pixel_radius_and_order(self) -> None:
        candidates = {"knee": (100.0, 100.0), "hip": (112.0, 100.0)}

        self.assertEqual(nearest_named_point(105.0, 100.0, candidates), "knee")
        self.assertIsNone(nearest_named_point(120.0, 100.0, {"knee": (100.0, 100.0)}))

    def test_drag_updates_only_target_segment_before_clinical_clamp(self) -> None:
        pose = pose_from_angles(Anthropometry(), self.q)
        point = (pose.ankle[0] + 0.10, pose.ankle[1] + 0.30)

        updated = drag_updated_q(self.q, "knee", point, pose)

        self.assertAlmostEqual(updated[0], atan2(0.10, 0.30))
        self.assertNotEqual(updated, self.q)

    def test_clamp_preserves_the_clinical_angle_bounds(self) -> None:
        q = clamp_segment_angles((radians(80.0), radians(-180.0), radians(100.0)))
        ankle, knee, hip = clinical_joint_angles_deg(q)

        self.assertEqual(ankle, 40.0)
        self.assertGreaterEqual(knee, 0.0)
        self.assertLessEqual(knee, 140.0)
        self.assertGreaterEqual(hip, -15.0)
        self.assertLessEqual(hip, 120.0)

    def test_precise_angle_accepts_comma_decimal_and_preserves_other_joints(self) -> None:
        update = apply_clinical_angle(self.q, "genou", "110,5")

        self.assertTrue(update.accepted)
        assert update.q is not None
        ankle, knee, hip = clinical_joint_angles_deg(update.q)
        self.assertAlmostEqual(ankle, 22.0)
        self.assertAlmostEqual(knee, 110.5)
        self.assertAlmostEqual(hip, 78.0)
        self.assertFalse(update.was_clamped)

    def test_precise_angle_clamps_and_invalid_input_does_not_return_a_pose(self) -> None:
        clamped = apply_clinical_angle(self.q, "cheville", "50")
        invalid = apply_clinical_angle(self.q, "genou", "-")

        self.assertTrue(clamped.accepted)
        self.assertTrue(clamped.was_clamped)
        self.assertEqual(clamped.bounded_deg, 40.0)
        self.assertFalse(invalid.accepted)
        self.assertIsNone(invalid.q)
        self.assertIn("angle invalide (genou)", invalid.error_message or "")

    def test_editor_spec_matches_existing_french_text(self) -> None:
        spec = clinical_angle_editor_spec("genou", self.q)

        self.assertEqual(spec.label, "Genou (flexion)")
        self.assertEqual(spec.display_label, "Genou (flexion) — 0 à 140 deg")
        self.assertAlmostEqual(spec.value_deg, 80.0)


if __name__ == "__main__":
    unittest.main()
