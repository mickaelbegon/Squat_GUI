import unittest
from math import atan2, cos, degrees, hypot, radians, sin
from pathlib import Path
from unittest.mock import patch

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

    def test_refined_calibration_targets_are_not_drawn_on_the_silhouette(self):
        """Joint targets locate the sprite but must not appear in the GUI."""
        from PIL import Image

        for filename in ("pied.png", "jambe.png", "cuisse.png", "trunk_homme_back.png"):
            with self.subTest(filename=filename):
                source = Image.open(raster_segments._asset_path(filename, refined=True))
                targets = raster_segments._component_centers(
                    raster_segments._rgb_on_white(source)
                )
                cleaned = raster_segments._load_transparent_sprite(filename, refined=True)
                for x, y in targets:
                    self.assertEqual(cleaned.getpixel((round(x), round(y)))[3], 0)

    def test_unknown_segment_reports_the_requested_name(self):
        with self.assertRaisesRegex(
            raster_segments.SpriteDefinitionError,
            "Unknown sprite segment 'forearm'",
        ):
            raster_segments.sprite_spec("forearm")

    def test_unknown_trunk_variant_reports_the_requested_variant(self):
        with self.assertRaisesRegex(
            raster_segments.SpriteDefinitionError,
            "Unknown trunk sprite variant",
        ):
            raster_segments.sprite_spec("trunk", trunk_variant=("homme", "side"))

    def test_missing_asset_reports_its_path(self):
        with patch.object(raster_segments, "_asset_path", return_value=Path("missing.png")):
            with self.assertRaisesRegex(raster_segments.SpriteAssetError, "missing.png"):
                raster_segments._load_source_image("missing.png", refined=False, mode="RGBA")

    def test_invalid_calibration_reports_target_count(self):
        raster_segments.sprite_spec.cache_clear()
        try:
            with patch.object(raster_segments, "_component_centers", return_value=[]):
                with self.assertRaisesRegex(
                    raster_segments.SpriteCalibrationError,
                    "pied.png.*one rotation target.*found 0",
                ):
                    raster_segments.sprite_spec("foot")
        finally:
            raster_segments.sprite_spec.cache_clear()

    def test_blank_foot_reports_that_its_silhouette_is_missing(self):
        from PIL import Image

        blank = Image.new("RGB", (10, 10), (255, 255, 255))
        with self.assertRaisesRegex(
            raster_segments.SpriteCalibrationError,
            "blank.png cannot locate the foot silhouette",
        ):
            raster_segments._sprite_spec_from_targets(
                "foot", "blank.png", blank, [(4.0, 4.0)]
            )

    def test_display_cleanup_opens_each_sprite_once(self):
        raster_segments._load_transparent_sprite.cache_clear()
        try:
            with patch.object(
                raster_segments,
                "_load_source_image",
                wraps=raster_segments._load_source_image,
            ) as load_source:
                raster_segments._load_transparent_sprite("pied.png", refined=True)
            load_source.assert_called_once_with("pied.png", True, "RGBA")
        finally:
            raster_segments._load_transparent_sprite.cache_clear()

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

    def test_refined_transform_cache_reuses_pil_result(self):
        from PIL import Image

        raster_segments.transformed_sprite_cache_clear()
        try:
            spec = raster_segments.sprite_spec("shank", refined=True)
            target = (23.0, -160.0)
            with patch.object(
                raster_segments,
                "_render_transformed_sprite",
                wraps=raster_segments._render_transformed_sprite,
            ) as render:
                first_image, first_anchor = raster_segments.transformed_sprite_image(
                    spec, target, refined=True
                )
                second_image, second_anchor = raster_segments.transformed_sprite_image(
                    spec, target, refined=True
                )

            self.assertIsInstance(first_image, Image.Image)
            self.assertIs(first_image, second_image)
            self.assertEqual(first_anchor, second_anchor)
            self.assertEqual(render.call_count, 1)
            info = raster_segments.transformed_sprite_cache_info()
            self.assertEqual((info.hits, info.misses, info.curr_entries), (1, 1, 1))
        finally:
            raster_segments.transformed_sprite_cache_clear()

    def test_transform_cache_canonicalization_stays_below_one_pixel(self):
        length = 160.0
        angle = -80.0
        target = (length * cos(radians(angle)), length * sin(radians(angle)))
        canonical, length_step, angle_step = (
            raster_segments._canonical_target_vector(target)
        )

        self.assertLess(hypot(canonical[0] - target[0], canonical[1] - target[1]), 0.2)
        self.assertEqual(
            length_step,
            round(length / raster_segments.TRANSFORMED_SPRITE_LENGTH_STEP_PX),
        )
        self.assertEqual(
            angle_step,
            round(angle / raster_segments.TRANSFORMED_SPRITE_ANGLE_STEP_DEGREES),
        )

    def test_rotation_workspace_encloses_sprite_with_less_transparent_area(self):
        image_size = (180, 300)
        anchor = (72.5, 245.25)

        workspace, pivot = raster_segments._rotation_workspace(image_size, anchor)
        radius = pivot[0]
        corner_distances = (
            hypot(x - anchor[0], y - anchor[1])
            for x in (0.0, float(image_size[0]))
            for y in (0.0, float(image_size[1]))
        )
        legacy_margin = int(max(image_size) * 1.5)
        legacy_area = (image_size[0] + 2 * legacy_margin) * (
            image_size[1] + 2 * legacy_margin
        )

        self.assertEqual(workspace, (2 * radius + 1, 2 * radius + 1))
        self.assertGreaterEqual(radius - 2, max(corner_distances))
        self.assertLess(workspace[0] * workspace[1], legacy_area * 0.6)

    def test_cached_transform_preserves_pixels_and_distal_alignment(self):
        raster_segments.transformed_sprite_cache_clear()
        try:
            spec = raster_segments.sprite_spec("thigh", refined=True)
            target = (0.0, -160.0)
            expected_image, expected_anchor = (
                raster_segments._render_transformed_sprite(spec, target, True)
            )
            image, anchor = raster_segments.transformed_sprite_image(
                spec, target, refined=True
            )

            self.assertEqual(image.size, expected_image.size)
            self.assertEqual(image.tobytes(), expected_image.tobytes())
            self.assertEqual(anchor, expected_anchor)
            distal = (123.25, 456.75)
            image_origin = (distal[0] - anchor[0], distal[1] - anchor[1])
            self.assertEqual(
                (image_origin[0] + anchor[0], image_origin[1] + anchor[1]),
                distal,
            )
        finally:
            raster_segments.transformed_sprite_cache_clear()

    def test_refined_cache_separates_asset_variants(self):
        raster_segments.transformed_sprite_cache_clear()
        try:
            front = raster_segments.sprite_spec(
                "trunk", refined=True, trunk_variant=("homme", "front")
            )
            back = raster_segments.sprite_spec(
                "trunk", refined=True, trunk_variant=("homme", "back")
            )
            target = (0.0, -180.0)
            with patch.object(
                raster_segments,
                "_render_transformed_sprite",
                wraps=raster_segments._render_transformed_sprite,
            ) as render:
                raster_segments.transformed_sprite_image(front, target, refined=True)
                raster_segments.transformed_sprite_image(back, target, refined=True)

            self.assertEqual(render.call_count, 2)
            self.assertEqual(
                raster_segments.transformed_sprite_cache_info().curr_entries,
                2,
            )
        finally:
            raster_segments.transformed_sprite_cache_clear()

    def test_low_quality_transform_bypasses_refined_cache(self):
        raster_segments.transformed_sprite_cache_clear()
        spec = raster_segments.sprite_spec("foot", refined=False)
        with patch.object(
            raster_segments,
            "_render_transformed_sprite",
            wraps=raster_segments._render_transformed_sprite,
        ) as render:
            raster_segments.transformed_sprite_image(spec, (100.0, 0.0))
            raster_segments.transformed_sprite_image(spec, (100.0, 0.0))

        self.assertEqual(render.call_count, 2)
        self.assertEqual(
            raster_segments.transformed_sprite_cache_info().curr_entries,
            0,
        )

    def test_transform_cache_is_lru_and_bounded_by_count_and_bytes(self):
        from PIL import Image

        image = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
        value = (image, (0.0, 0.0))
        cache = raster_segments._TransformedSpriteCache(
            max_entries=2,
            max_bytes=32,
        )
        cache.put("first", value)
        cache.put("second", value)
        self.assertIsNotNone(cache.get("first"))
        cache.put("third", value)

        self.assertIsNone(cache.get("second"))
        self.assertEqual(cache.info().curr_entries, 2)
        self.assertEqual(cache.info().curr_bytes, 32)
        self.assertEqual(cache.info().evictions, 1)

        byte_bounded = raster_segments._TransformedSpriteCache(
            max_entries=10,
            max_bytes=20,
        )
        byte_bounded.put("first", value)
        byte_bounded.put("second", value)
        self.assertEqual(byte_bounded.info().curr_entries, 1)
        self.assertEqual(byte_bounded.info().curr_bytes, 16)
        self.assertEqual(byte_bounded.info().evictions, 1)

    def test_foot_sprite_is_clipped_at_floor_without_moving_ankle_anchor(self):
        for refined in (False, True):
            with self.subTest(refined=refined):
                image, anchor = raster_segments.transformed_sprite_image(
                    raster_segments.sprite_spec("foot", refined=refined),
                    (100.0, 30.0),
                    refined=refined,
                )
                distal_px = (50.0, 70.0)
                floor_y = 100.0

                clipped, clipped_anchor = raster_segments.clip_sprite_at_canvas_floor(
                    image, anchor, distal_px, floor_y
                )

                self.assertEqual(clipped_anchor, anchor)
                self.assertLessEqual(
                    distal_px[1] - clipped_anchor[1] + clipped.getbbox()[3],
                    floor_y + 1.0,
                )

    def test_ground_condition_rotates_only_the_foot_display_vector_backward(self):
        target = (100.0, 30.0)

        flat = raster_segments.display_target_vector("foot", target, 0.0)
        wedge = raster_segments.display_target_vector("foot", target, 20.0)
        shank = raster_segments.display_target_vector("shank", target, 20.0)

        self.assertEqual(shank, target)
        self.assertAlmostEqual(hypot(*flat), hypot(*target))
        self.assertAlmostEqual(hypot(*wedge), hypot(*target))
        self.assertAlmostEqual(
            degrees(atan2(flat[1], flat[0])),
            degrees(atan2(target[1], target[0])) - 3.0,
        )
        self.assertAlmostEqual(
            degrees(atan2(wedge[1], wedge[0])),
            degrees(atan2(target[1], target[0])) - 10.0,
        )


if __name__ == "__main__":
    unittest.main()
