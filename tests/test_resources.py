from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from squat_gui.resources import asset_path, project_root


class ResourcePathTest(unittest.TestCase):
    def test_assets_resolve_from_repository(self):
        self.assertTrue((asset_path("raster_segments") / "pied.png").exists())
        self.assertTrue((project_root() / "pyproject.toml").exists())

    def test_assets_resolve_from_frozen_root(self):
        with patch.object(sys, "_MEIPASS", "/tmp/squat-gui-frozen", create=True):
            self.assertEqual(project_root(), Path("/tmp/squat-gui-frozen"))
            self.assertEqual(asset_path("raster_segments"), Path("/tmp/squat-gui-frozen/assets/raster_segments"))


if __name__ == "__main__":
    unittest.main()
