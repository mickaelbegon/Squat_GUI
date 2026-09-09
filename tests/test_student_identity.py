from __future__ import annotations

import unittest
import unicodedata

from squat_gui.export_schema import SUMMARY_SHEET, workbook_tables
from squat_gui.simulation_service import condition_from_settings, simulate_condition
from squat_gui.student_identity import StudentIdentity, normalize_identity_text


class StudentIdentityTests(unittest.TestCase):
    def test_normalization_preserves_spelling_while_making_one_line(self) -> None:
        decomposed_name = unicodedata.normalize("NFD", "  Aurélie\n  Côté  ")

        identity = StudentIdentity.normalized(decomposed_name, "  2026  001  ")

        self.assertEqual(identity.name, "Aurélie Côté")
        self.assertEqual(identity.student_id, "2026 001")
        self.assertEqual(normalize_identity_text("  Ab-C.  "), "Ab-C.")
        self.assertEqual(
            identity.display_label(), "Étudiant : Aurélie Côté · matricule 2026 001"
        )

    def test_identity_is_optional_and_propagates_to_all_export_formats(self) -> None:
        condition = condition_from_settings(
            {
                "student_name": "  Aurélie Côté ",
                "student_id": "  A-123 ",
                "load_percent_bw": 0.0,
            },
            (22.0, -58.0, 20.0),
            "identite",
            frames=3,
            backend="analytical",
        )

        rows, summary = simulate_condition(condition)

        self.assertTrue(
            all(
                row["student_name"] == "Aurélie Côté"
                and row["student_id"] == "A-123"
                for row in rows
            )
        )
        self.assertEqual(summary["student_name"], "Aurélie Côté")
        self.assertEqual(summary["student_id"], "A-123")
        self.assertEqual(summary["condition"]["student_name"], "Aurélie Côté")

        summary_table = workbook_tables(rows)[SUMMARY_SHEET]
        xlsx_summary = dict(
            zip(summary_table["columns"], summary_table["rows"][0])
        )
        self.assertEqual(xlsx_summary["student_name"], "Aurélie Côté")
        self.assertEqual(xlsx_summary["student_id"], "A-123")

        anonymous = condition_from_settings(
            {}, (22.0, -58.0, 20.0), "anonymous", frames=2
        )
        self.assertEqual(anonymous.student_name, "")
        self.assertEqual(anonymous.student_id, "")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
