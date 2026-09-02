import csv
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from squat_gui.cli import main
from squat_gui.export_schema import SCHEMA_VERSION, STANDARD_CSV_COLUMNS


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
                        "--csv-mode",
                        "full",
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
            self.assertEqual(rows[0]["schema_version"], SCHEMA_VERSION)
            self.assertIn("cheville_effort_percent", rows[0])
            self.assertIn("cheville_utilization_ratio", rows[0])
            self.assertIn("cheville_capacity_velocity_factor", rows[0])
            self.assertIn("cheville_capacity_base_torque_Nm", rows[0])
            self.assertIn("cheville_capacity_regime", rows[0])
            self.assertIn("genou_inverse_dynamics_total_Nm", rows[0])
            self.assertIn("genou_inertial_nonlinear_Nm", rows[0])
            self.assertIn("genou_mass_acceleration_Nm", rows[0])
            self.assertIn("genou_velocity_dependent_Nm", rows[0])
            self.assertIn("genou_gravity_Nm", rows[0])
            self.assertIn("genou_external_contact_effect_Nm", rows[0])
            self.assertEqual(
                rows[0]["contact_source"],
                "moment géométrique de la GRF",
            )
            self.assertAlmostEqual(
                float(rows[0]["genou_inverse_dynamics_reconstruction_residual_Nm"]),
                0.0,
                places=11,
            )
            self.assertIn("zmp_posterior_limit_m", rows[0])
            self.assertIn("zmp_in_support", rows[0])
            self.assertIn("delta_time_s", rows[0])
            self.assertIn("normalized_time_percent", rows[0])
            self.assertIn("ankle_x_m", rows[0])
            self.assertIn("bar_y_m", rows[0])
            self.assertIn("foot_orientation_deg", rows[0])
            self.assertIn("trunk_orientation_deg", rows[0])
            self.assertIn("total_mass_kg", rows[0])
            self.assertIn("shank_length_m", rows[0])
            self.assertIn("trunk_com_fraction", rows[0])
            self.assertIn("bar_attachment_anterior_offset_m", rows[0])
            self.assertIn("foot_com_x_m", rows[0])
            self.assertIn("bar_weighted_com_y_kg_m", rows[0])
            segments = ("foot", "shank", "thigh", "trunk", "bar")
            weighted_x = sum(
                float(rows[2][f"{segment}_weighted_com_x_kg_m"]) for segment in segments
            )
            weighted_y = sum(
                float(rows[2][f"{segment}_weighted_com_y_kg_m"]) for segment in segments
            )
            total_mass = float(rows[2]["total_mass_kg"])
            self.assertAlmostEqual(weighted_x / total_mass, float(rows[2]["com_x_m"]))
            self.assertAlmostEqual(weighted_y / total_mass, float(rows[2]["com_y_m"]))
            self.assertGreater(
                abs(float(rows[1]["com_vx_m_s"])) + abs(float(rows[1]["com_vy_m_s"])),
                1e-6,
            )
            self.assertEqual(rows[1]["support_point_label"], "CoP")
            self.assertEqual(
                rows[1]["support_point_source"], "bilan dynamique analytique"
            )
            feasibility = payload["mechanical_feasibility"]
            self.assertEqual(
                feasibility["interpretation"],
                "faisabilite mecanique dans les hypotheses du modele",
            )
            self.assertIn(
                feasibility["limiting_joint"], ("cheville", "genou", "hanche")
            )
            self.assertIn(
                feasibility["phase"], ("excentrique", "isometrique", "concentrique")
            )
            self.assertIsInstance(feasibility["exceeds_capacity"], bool)
            self.assertIn("geometric_support_posterior_m", rows[1])
            self.assertIn("functional_support_posterior_m", rows[1])
            self.assertIn("support_point_functional_posterior_margin_m", rows[1])
            self.assertIn("com_projection_in_geometric_base", rows[1])
            self.assertAlmostEqual(float(rows[1]["weight_magnitude_N"]), 70.0 * 9.80665)
            self.assertAlmostEqual(
                float(rows[1]["force_balance_residual_x_N"]), 0.0, places=11
            )
            self.assertAlmostEqual(
                float(rows[1]["force_balance_residual_y_N"]), 0.0, places=11
            )
            self.assertIn("zmp_outside_support_frames", payload)
            self.assertEqual(payload["condition"]["condition_id"], "demo")
            self.assertEqual(rows[0]["bar_position"], "back")
            self.assertEqual(rows[0]["load_percent_bw"], "0.0")

    def test_run_uses_stable_standard_csv_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "standard.csv"

            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "run",
                        "--backend",
                        "analytical",
                        "--frames",
                        "3",
                        "--out",
                        str(out),
                        "--summary",
                        "",
                    ]
                )

            self.assertEqual(code, 0)
            with out.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
            self.assertEqual(tuple(reader.fieldnames or ()), STANDARD_CSV_COLUMNS)
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]["frames"], "3")
            self.assertIn("cheville_torque_body_mass_normalized_Nm_kg", rows[0])
            self.assertIn("grf_y_N", rows[0])
            self.assertNotIn("cheville_mass_acceleration_Nm", rows[0])
            self.assertNotIn("foot_weighted_com_x_kg_m", rows[0])

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
                code = main(
                    ["batch", str(conditions), "--out", str(out), "--summary", ""]
                )

            self.assertEqual(code, 0)
            with out.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 6)
            self.assertEqual({row["condition_id"] for row in rows}, {"light", "loaded"})
            self.assertAlmostEqual(
                float(rows[3]["load_percent_bw"]), 100.0 * 40.0 / 70.0
            )


if __name__ == "__main__":
    unittest.main()
