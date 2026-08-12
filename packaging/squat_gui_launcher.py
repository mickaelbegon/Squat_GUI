"""Frozen-app launcher for the Squat GUI."""

from __future__ import annotations

import importlib
import os
import tempfile
from pathlib import Path

from squat_gui.app import main


if __name__ == "__main__":
    if os.environ.get("SQUAT_GUI_SMOKE_TEST") == "1":
        import math

        import imageio.v2 as imageio
        import imageio_ffmpeg
        import numpy

        from squat_gui.anthropometry import Anthropometry
        from squat_gui.backend import BiorbdModelCache
        from squat_gui.cli import condition_from_settings, simulate_condition
        from squat_gui.dynamics import simulate
        import squat_gui.export_schema as export_schema
        from squat_gui.kinematics import PhaseDurations
        from squat_gui.rendering import RenderLayers
        from squat_gui.resources import asset_path
        from squat_gui.video_export import export_mp4

        assert (asset_path("raster_segments") / "pied.png").exists()
        assert Path(export_schema.__file__).with_name(
            "build_workbook.mjs"
        ).exists()
        assert imageio_ffmpeg.get_ffmpeg_exe()
        assert numpy.__version__

        anthropometry = Anthropometry()
        states, results = simulate(
            anthropometry,
            (math.radians(22.0), math.radians(-58.0), math.radians(20.0)),
            PhaseDurations(0.05, 0.0, 0.05),
            3,
            {"cheville": 222.0, "genou": 380.0, "hanche": 376.0},
            True,
            None,
        )
        with tempfile.TemporaryDirectory(prefix="squat-gui-frozen-smoke-") as work:
            video_path = Path(work) / "smoke.mp4"
            report = export_mp4(
                video_path,
                anthropometry,
                states,
                results,
                RenderLayers(),
                width=320,
                height=240,
            )
            reader = imageio.get_reader(video_path)
            try:
                assert reader.count_frames() == report.frame_count == 2
            finally:
                reader.close()
            condition = condition_from_settings(
                {},
                (22.0, -58.0, 20.0),
                "frozen_excel",
                frames=3,
                backend="analytical",
            )
            export_rows, _summary = simulate_condition(condition)
            excel_path = Path(work) / "smoke.xlsx"
            previous_writer = os.environ.get("SQUAT_GUI_XLSX_WRITER")
            os.environ["SQUAT_GUI_XLSX_WRITER"] = "openpyxl"
            try:
                excel_report = export_schema.write_xlsx(excel_path, export_rows)
            finally:
                if previous_writer is None:
                    os.environ.pop("SQUAT_GUI_XLSX_WRITER", None)
                else:
                    os.environ["SQUAT_GUI_XLSX_WRITER"] = previous_writer
            assert excel_report["writer"] == "openpyxl"
            assert len(excel_report["sheets"]) == 11
            assert excel_path.stat().st_size > 10000

        if os.environ.get("SQUAT_GUI_INCLUDE_OPTIONAL_BACKENDS") == "1":
            biorbd = importlib.import_module("biorbd")
            assert biorbd.__version__
            with tempfile.TemporaryDirectory(
                prefix="squat-gui-frozen-biorbd-"
            ) as work:
                _states, biorbd_results = simulate(
                    anthropometry,
                    (math.radians(22.0), math.radians(-58.0), math.radians(20.0)),
                    PhaseDurations(0.05, 0.0, 0.05),
                    3,
                    {"cheville": 222.0, "genou": 380.0, "hanche": 376.0},
                    True,
                    BiorbdModelCache(Path(work) / "cache"),
                )
                assert all(result.backend == "biorbd" for result in biorbd_results)
        print("Squat GUI frozen smoke test OK: assets, video, Excel builder, biorbd")
        raise SystemExit(0)
    main()
