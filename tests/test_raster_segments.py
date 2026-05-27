import unittest

from squat_gui import raster_segments


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


if __name__ == "__main__":
    unittest.main()
