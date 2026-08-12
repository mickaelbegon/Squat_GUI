import math
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from zipfile import ZipFile

from squat_gui.cli import Condition, simulate_condition
from squat_gui.export_schema import (
    SCHEMA_VERSION,
    missing_dictionary_columns,
    workbook_tables,
    write_xlsx,
)


class ExportSchemaTests(unittest.TestCase):
    @staticmethod
    def rows() -> list[dict[str, object]]:
        condition = Condition(
            condition_id="contrat",
            load_percent_bw=20.0,
            subject_profile="homme",
            bar_position="front",
            wedge_20_deg=True,
            shank_percent=2.0,
            thigh_percent=-1.0,
            trunk_percent=3.0,
            anthropometry_mode="morphotype recalibre",
            duration_excentrique_s=2.0,
            duration_isometrique_s=0.5,
            duration_concentrique_s=2.0,
            q_segment_deg=(22.0, -58.0, 20.0),
            torque_preset="Anderson actif x2",
            max_torques={"cheville": 222.0, "genou": 380.0, "hanche": 376.0},
            angle_adapt=True,
            velocity_adapt=True,
            frames=3,
            backend="analytical",
        )
        rows, _summary = simulate_condition(condition)
        return rows

    def test_every_excel_column_has_definition_and_units(self) -> None:
        rows = self.rows()
        tables = workbook_tables(rows)
        self.assertEqual(
            set(tables),
            {
                "conditions",
                "temps",
                "coordonnees",
                "orientations",
                "cinematique_articulaire",
                "anthropometrie",
                "com_segmentaires",
                "com_global",
                "forces_equilibre",
                "dynamique",
                "definitions",
            },
        )
        self.assertEqual(missing_dictionary_columns(tables), set())
        self.assertEqual(len(tables["anthropometrie"]["rows"]), 5)
        self.assertTrue(
            all(row[0] == SCHEMA_VERSION for row in tables["temps"]["rows"])
        )
        csv_definitions = {
            row[2]: row
            for row in tables["definitions"]["rows"]
            if row[1] == "csv_large"
        }
        self.assertEqual(set(csv_definitions), set(rows[0]))
        self.assertEqual(csv_definitions["zmp_in_support"][6], "compatibilité legacy")
        self.assertEqual(
            csv_definitions["cheville_contact_Nm"][6],
            "compatibilité legacy",
        )
        self.assertEqual(
            csv_definitions["cheville_mass_acceleration_Nm"][6],
            "canonique",
        )

    def test_global_com_is_the_sum_of_exported_segment_contributions(self) -> None:
        segments = ("foot", "shank", "thigh", "trunk", "bar")
        for row in self.rows():
            total_mass = float(row["total_mass_kg"])
            weighted_x = sum(
                float(row[f"{segment}_weighted_com_x_kg_m"]) for segment in segments
            )
            weighted_y = sum(
                float(row[f"{segment}_weighted_com_y_kg_m"]) for segment in segments
            )
            self.assertTrue(
                math.isclose(
                    weighted_x / total_mass, float(row["com_x_m"]), abs_tol=1e-12
                )
            )
            self.assertTrue(
                math.isclose(
                    weighted_y / total_mass, float(row["com_y_m"]), abs_tol=1e-12
                )
            )

    def test_xlsx_contains_every_metric_family_and_no_formula_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "squat.xlsx"
            previews = Path(temporary) / "previews"
            report = write_xlsx(output, self.rows(), preview_directory=previews)
            self.assertEqual(report["writer"], "artifact-tool")
            self.assertEqual(report["formulaErrors"], [])
            self.assertEqual(len(report["sheets"]), 11)
            self.assertTrue(
                all((previews / f"{name}.png").exists() for name in report["sheets"])
            )
            with ZipFile(output) as archive:
                workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
            for name in report["sheets"]:
                self.assertIn(f'name="{name}"', workbook_xml)

    def test_openpyxl_fallback_is_autonomous_and_preserves_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "fallback.xlsx"
            with patch.dict(
                os.environ, {"SQUAT_GUI_XLSX_WRITER": "openpyxl"}, clear=False
            ):
                report = write_xlsx(output, self.rows())
            self.assertEqual(report["writer"], "openpyxl")
            self.assertEqual(report["formulaErrors"], [])
            self.assertEqual(len(report["sheets"]), 11)

            from openpyxl import load_workbook

            workbook = load_workbook(output, read_only=False, data_only=False)
            try:
                self.assertEqual(workbook.sheetnames, report["sheets"])
                self.assertEqual(workbook["temps"].freeze_panes, "C2")
                self.assertEqual(workbook["anthropometrie"].freeze_panes, "D2")
                self.assertEqual(
                    workbook["temps"]["E2"].value,
                    self.rows()[0]["delta_time_s"],
                )
                self.assertEqual(workbook["temps"]["E2"].number_format, "0.000")
                self.assertTrue(workbook["conditions"].tables)
                self.assertEqual(
                    workbook["conditions"]["A1"].fill.fgColor.rgb[-6:], "245B4A"
                )
            finally:
                workbook.close()

    def test_auto_falls_back_when_artifact_runtime_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "auto.xlsx"
            with (
                patch.dict(
                    os.environ, {"SQUAT_GUI_XLSX_WRITER": "auto"}, clear=False
                ),
                patch(
                    "squat_gui.export_schema._write_xlsx_artifact",
                    side_effect=RuntimeError("Node absent"),
                ),
            ):
                report = write_xlsx(output, self.rows())
            self.assertEqual(report["writer"], "openpyxl")
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
