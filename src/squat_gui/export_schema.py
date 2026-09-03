"""Public façade for the versioned CSV and Excel export contract.

Static columns live in :mod:`export_contract`, their human-readable metadata in
:mod:`export_dictionary`, and row/table construction in :mod:`export_tables`.
This module keeps the established import surface and XLSX compatibility hooks.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Sequence

from .export_contract import (
    ANTHROPOMETRY_COLUMNS,
    CONDITION_COLUMNS,
    COORDINATE_COLUMNS,
    DYNAMIC_COLUMNS,
    FORCE_COLUMNS,
    GLOBAL_COM_COLUMNS,
    JOINTS,
    KINEMATIC_COLUMNS,
    ORIENTATION_COLUMNS,
    POINTS,
    ROW_KEYS,
    SCHEMA_VERSION,
    SEGMENT_COM_COLUMNS,
    SEGMENTS,
    STANDARD_CSV_COLUMNS,
    SUMMARY_COLUMNS,
    TIME_COLUMNS,
    ColumnDefinition,
)
from .export_dictionary import DESCRIPTION_OVERRIDES, LEGACY_COLUMNS, column_definition
from .export_tables import add_schema_version, csv_export_rows, workbook_tables
from .workbook_model import (
    COMBINED_SHEET,
    DEFINITIONS_SHEET,
    SUMMARY_SHEET,
    WorkbookTables,
    excel_number_format,
    missing_dictionary_columns,
)
from .xlsx_writers import write_xlsx_artifact, write_xlsx_openpyxl


def _write_xlsx_artifact(
    path: str | Path,
    rows: Sequence[Mapping[str, object]],
    *,
    preview_directory: str | Path | None = None,
) -> dict[str, object]:
    """Compatibility wrapper around the Artifact Tool writer."""
    return write_xlsx_artifact(
        path,
        workbook_tables(rows),
        schema_version=SCHEMA_VERSION,
        builder=Path(__file__).with_name("build_workbook.mjs"),
        preview_directory=preview_directory,
    )


def _excel_number_format(column: str) -> str | None:
    """Compatibility alias for the canonical workbook format selector."""
    return excel_number_format(column)


def _write_xlsx_openpyxl(
    path: str | Path,
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Compatibility wrapper around the autonomous openpyxl writer."""
    return write_xlsx_openpyxl(path, workbook_tables(rows))


def write_xlsx(
    path: str | Path,
    rows: Sequence[Mapping[str, object]],
    *,
    preview_directory: str | Path | None = None,
) -> dict[str, object]:
    """Write the canonical workbook, with an autonomous openpyxl fallback."""
    writer = os.environ.get("SQUAT_GUI_XLSX_WRITER", "auto").strip().lower()
    if writer not in {"auto", "artifact-tool", "openpyxl"}:
        raise ValueError(
            "SQUAT_GUI_XLSX_WRITER doit valoir auto, artifact-tool ou openpyxl."
        )
    if writer in {"auto", "artifact-tool"}:
        try:
            return _write_xlsx_artifact(path, rows, preview_directory=preview_directory)
        except RuntimeError:
            if writer == "artifact-tool":
                raise
    return _write_xlsx_openpyxl(path, rows)
