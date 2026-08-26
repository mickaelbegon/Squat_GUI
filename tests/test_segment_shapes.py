import unittest

from squat_gui.segment_shapes import draw_segment


class RecordingCanvas:
    def __init__(self):
        self.polygons = []

    def create_polygon(self, points, **_kwargs):
        self.polygons.append(points)


class SegmentShapeTests(unittest.TestCase):
    def test_minimum_world_y_keeps_vector_silhouette_above_floor(self):
        canvas = RecordingCanvas()
        segment = {
            "paths": [
                {
                    "closed": True,
                    "vertices": [[0.0, 0.1], [1.0, -0.2], [1.0, 0.1]],
                }
            ]
        }

        draw_segment(
            canvas,
            segment,
            origin=(0.0, 0.0),
            angle=0.0,
            scale=1.0,
            world_to_canvas=lambda point: point,
            minimum_world_y=0.0,
        )

        self.assertEqual(canvas.polygons[0][3], 0.0)


if __name__ == "__main__":
    unittest.main()
