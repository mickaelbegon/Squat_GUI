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

    def test_foot_uses_target_and_toe_tip(self):
        spec = raster_segments.sprite_spec("foot")
        self.assertAlmostEqual(spec.distal_anchor[0], 84.5, delta=1.0)
        self.assertAlmostEqual(spec.distal_anchor[1], 67.0, delta=1.0)
        self.assertGreater(spec.proximal_anchor[0], 280.0)
        self.assertGreater(spec.proximal_anchor[1] - spec.distal_anchor[1], 80.0)


if __name__ == "__main__":
    unittest.main()
