import json
import math
import tempfile
import unittest
from pathlib import Path

import imageio.v2 as imageio

from squat_gui.anthropometry import Anthropometry
from squat_gui.dynamics import simulate
from squat_gui.kinematics import PhaseDurations
from squat_gui.rendering import RenderLayers, render_animation_frame
from squat_gui.video_export import DEFAULT_VIDEO_FPS, export_mp4


class VideoExportTests(unittest.TestCase):
    @staticmethod
    def simulation():
        anthro = Anthropometry(bar_mass=20.0, wedge_angle_deg=20.0)
        states, results = simulate(
            anthro,
            (math.radians(22.0), math.radians(-58.0), math.radians(20.0)),
            PhaseDurations(0.05, 0.0, 0.05),
            3,
            {"cheville": 222.0, "genou": 380.0, "hanche": 376.0},
            True,
            None,
        )
        return anthro, states, results

    def test_offscreen_frame_has_requested_dimensions(self) -> None:
        anthro, states, results = self.simulation()
        image = render_animation_frame(
            anthro,
            states[1],
            results[1],
            RenderLayers(weight=True, geometric_base=True),
            width=640,
            height=480,
        )

        self.assertEqual(image.size, (640, 480))
        self.assertEqual(image.mode, "RGB")

    def test_mp4_and_reproducibility_metadata_use_twenty_fps(self) -> None:
        anthro, states, results = self.simulation()
        layers = RenderLayers(weight=True, moment_arms=False, capacity_rings=False)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "squat.mp4"
            report = export_mp4(
                output,
                anthro,
                states,
                results,
                layers,
                width=640,
                height=480,
            )
            metadata = json.loads(
                Path(report.metadata_path).read_text(encoding="utf-8")
            )

            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 1000)
            self.assertEqual(report.fps, DEFAULT_VIDEO_FPS)
            self.assertEqual(report.frame_count, 2)
            self.assertEqual(report.source_frame_count, 3)
            self.assertAlmostEqual(report.timeline_duration_s, states[-1].time)
            self.assertAlmostEqual(report.encoded_duration_s, states[-1].time)
            self.assertEqual(metadata["video"]["frame_count"], 2)
            self.assertEqual(metadata["video"]["source_frame_count"], 3)
            self.assertEqual(metadata["video"]["sample_period_s"], 0.05)
            self.assertFalse(metadata["layers"]["moment_arms"])
            self.assertFalse(metadata["layers"]["capacity_rings"])

            reader = imageio.get_reader(output)
            try:
                container = reader.get_meta_data()
                self.assertEqual(reader.count_frames(), report.frame_count)
            finally:
                reader.close()
            self.assertAlmostEqual(container["fps"], report.fps)
            self.assertAlmostEqual(
                container["duration"], report.timeline_duration_s, places=6
            )


if __name__ == "__main__":
    unittest.main()
