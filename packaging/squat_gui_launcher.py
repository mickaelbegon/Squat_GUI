"""Frozen-app launcher for the Squat GUI."""

from __future__ import annotations

import os

from squat_gui.app import main


if __name__ == "__main__":
    if os.environ.get("SQUAT_GUI_SMOKE_TEST") == "1":
        from squat_gui.resources import asset_path

        assert (asset_path("raster_segments") / "pied.png").exists()
        print("Squat GUI frozen smoke test OK")
        raise SystemExit(0)
    main()
