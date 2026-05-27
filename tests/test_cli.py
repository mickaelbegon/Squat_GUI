import csv
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from squat_gui.cli import main


class CliExportTests(unittest.TestCase):
    def test_run_exports_results_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "results.csv"
            summary = Path(tmp) / "summary.json"

            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "run",
                        "--condition-id",
                        "demo",
                        "--backend",
                        "analytical",
                        "--frames",
                        "5",
                        "--out",
                        str(out),
                        "--summary",
                        str(summary),
                    ]
                )

            self.assertEqual(code, 0)
            with out.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            payload = json.loads(summary.read_text(encoding="utf-8"))

            self.assertEqual(len(rows), 5)
            self.assertEqual(rows[0]["condition_id"], "demo")
            self.assertIn("cheville_effort_percent", rows[0])
            self.assertIn("genou_inverse_dynamics_total_Nm", rows[0])
            self.assertIn("genou_inertial_nonlinear_Nm", rows[0])
            self.assertIn("zmp_posterior_limit_m", rows[0])
            self.assertIn("zmp_in_support", rows[0])
            self.assertIn("zmp_outside_support_frames", payload)
            self.assertEqual(payload["condition"]["condition_id"], "demo")
            self.assertEqual(rows[0]["bar_position"], "back")
            self.assertEqual(rows[0]["load_percent_bw"], "0.0")

    def test_batch_exports_multiple_conditions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conditions = Path(tmp) / "conditions.csv"
            out = Path(tmp) / "batch.csv"
            conditions.write_text(
                "condition_id,load_kg,duration_phase_s,frames,backend,ankle_deg,knee_deg,hip_deg\n"
                "light,0,0.4,3,analytical,20,-70,60\n"
                "loaded,40,0.4,3,analytical,22,-80,78\n",
                encoding="utf-8",
            )

            with redirect_stdout(StringIO()):
                code = main(["batch", str(conditions), "--out", str(out), "--summary", ""])

            self.assertEqual(code, 0)
            with out.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 6)
            self.assertEqual({row["condition_id"] for row in rows}, {"light", "loaded"})
            self.assertAlmostEqual(float(rows[3]["load_percent_bw"]), 100.0 * 40.0 / 70.0)


if __name__ == "__main__":
    unittest.main()
