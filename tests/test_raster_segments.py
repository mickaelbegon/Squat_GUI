import unittest

from squat_gui import raster_segments
from squat_gui.bar_com_editor import calibration_images, calibration_payload, point_relative_to_shoulder
from squat_gui.bar_calibration import annotated_bar_offset_fractions, calibration_entries


@unittest.skipUnless(raster_segments.pillow_available(), "Pillow is required for raster sprite anchors")
class RasterSegmentAnchorTest(unittest.TestCase):
    def test_rotation_uses_pillow_screen_coordinate_direction(self):
        self.assertAlmostEqual(raster_segments.sprite_rotation_degrees((0.0, -1.0), (1.0, -1.0)), -45.0)
        self.assertAlmostEqual(raster_segments.sprite_rotation_degrees((0.0, -1.0), (-1.0, -1.0)), 45.0)

    def test_targets_define_long_bone_anchors(self):
        for name in ("shank", "thigh", "trunk"):
            with self.subTest(name=name):
                spec = raster_segments.sprite_spec(name)
                self.assertGreater(spec.distal_anchor[1], spec.proximal_anchor[1])
                self.assertGreater(abs(spec.distal_anchor[1] - spec.proximal_anchor[1]), 400)

    def test_refined_targets_define_long_bone_anchors(self):
        for name in ("shank", "thigh", "trunk"):
            with self.subTest(name=name):
                spec = raster_segments.sprite_spec(name, refined=True)
                self.assertGreater(spec.distal_anchor[1], spec.proximal_anchor[1])
                self.assertGreater(abs(spec.distal_anchor[1] - spec.proximal_anchor[1]), 600)

    def test_refined_trunks_are_available_for_each_subject_and_hold(self):
        for subject in ("homme", "femme enceinte"):
            for hold in ("front", "back", "over-head"):
                with self.subTest(subject=subject, hold=hold):
                    spec = raster_segments.sprite_spec("trunk", refined=True, trunk_variant=(subject, hold))
                    self.assertGreater(spec.distal_anchor[1], spec.proximal_anchor[1])

    def test_low_quality_trunks_are_available_for_each_subject_and_hold(self):
        for subject in ("homme", "femme enceinte"):
            for hold in ("front", "back", "over-head"):
                with self.subTest(subject=subject, hold=hold):
                    spec = raster_segments.sprite_spec("trunk", refined=False, trunk_variant=(subject, hold))
                    self.assertGreater(spec.distal_anchor[1], spec.proximal_anchor[1])

    def test_foot_uses_target_and_toe_tip(self):
        spec = raster_segments.sprite_spec("foot")
        self.assertAlmostEqual(spec.distal_anchor[0], 84.5, delta=1.0)
        self.assertAlmostEqual(spec.distal_anchor[1], 67.0, delta=1.0)
        self.assertGreater(spec.proximal_anchor[0], 280.0)
        self.assertGreater(spec.proximal_anchor[1] - spec.distal_anchor[1], 80.0)

    def test_refined_foot_uses_target_and_toe_tip(self):
        spec = raster_segments.sprite_spec("foot", refined=True)
        self.assertAlmostEqual(spec.distal_anchor[0], 118.4, delta=1.0)
        self.assertAlmostEqual(spec.distal_anchor[1], 75.4, delta=1.0)
        self.assertGreater(spec.proximal_anchor[0], 700.0)

    def test_bar_com_editor_includes_all_twelve_trunk_images(self):
        images = calibration_images()

        self.assertEqual(len(images), 12)
        self.assertEqual(len({item.key for item in images}), 12)
        self.assertTrue(all(item.path.exists() for item in images))

    def test_bar_com_local_coordinates_are_relative_to_shoulder(self):
        item = calibration_images()[0]
        spec = raster_segments.sprite_spec("trunk", item.refined, (item.subject_profile, item.bar_position))
        anterior, longitudinal = point_relative_to_shoulder(spec.proximal_anchor, spec)

        self.assertAlmostEqual(anterior, 0.0)
        self.assertAlmostEqual(longitudinal, 0.0)
        payload = calibration_payload({item.key: spec.proximal_anchor})
        self.assertEqual(payload["placed_count"], 1)
        self.assertEqual(payload["expected_count"], 12)

    def test_manual_bar_com_calibration_contains_all_rendered_variants(self):
        entries = calibration_entries()

        self.assertEqual(len(entries), 12)
        for item in calibration_images():
            with self.subTest(item=item.key):
                self.assertIn((item.quality, item.subject_profile, item.bar_position), entries)

    def test_refined_manual_point_is_the_physical_reference(self):
        anterior, longitudinal = annotated_bar_offset_fractions("homme", "front")

        self.assertAlmostEqual(anterior, 0.201445)
        self.assertAlmostEqual(longitudinal, 0.111125)

    def test_display_adjustments_make_lower_limb_silhouettes_more_readable(self):
        shank, _ = raster_segments.transformed_sprite_image(
            raster_segments.sprite_spec("shank", refined=True),
            (0.0, -161.0),
            refined=True,
        )
        thigh, _ = raster_segments.transformed_sprite_image(
            raster_segments.sprite_spec("thigh", refined=True),
            (0.0, -161.0),
            refined=True,
        )
        foot, _ = raster_segments.transformed_sprite_image(
            raster_segments.sprite_spec("foot", refined=True),
            (100.0, 0.0),
            refined=True,
        )

        self.assertGreaterEqual(shank.size[0], 55)
        self.assertGreater(thigh.size[0], 85)
        self.assertGreater(foot.size[0], 130)


if __name__ == "__main__":
    unittest.main()
