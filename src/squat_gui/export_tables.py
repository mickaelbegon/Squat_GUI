"""Row and table assembly for the export contract.

Summary metrics are calculated in :mod:`squat_gui.workbook_model`; this module
only binds that writer-independent computation to the public export schema.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

from .export_contract import (
    JOINTS,
    SCHEMA_VERSION,
    STANDARD_CSV_COLUMNS,
    SUMMARY_COLUMNS,
)
from .export_dictionary import column_definition
from .workbook_model import WorkbookContract, WorkbookTables, build_workbook_tables


def add_schema_version(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Copy rows while attaching the current export contract version."""
    versioned: list[dict[str, object]] = []
    for source in rows:
        row = {"schema_version": SCHEMA_VERSION}
        row.update(source)
        versioned.append(row)
    return versioned


def csv_export_rows(
    rows: Sequence[Mapping[str, object]], *, mode: str = "standard"
) -> list[dict[str, object]]:
    """Return rows for the concise student or complete diagnostic CSV contract."""
    if mode not in {"standard", "full"}:
        raise ValueError("Le mode CSV doit valoir standard ou full.")
    versioned = add_schema_version(rows)
    if mode == "full":
        return versioned
    return [
        {column: row.get(column) for column in STANDARD_CSV_COLUMNS}
        for row in versioned
    ]


def workbook_contract() -> WorkbookContract:
    """Build the dependencies required for normalized workbook tables."""
    return WorkbookContract(
        schema_version=SCHEMA_VERSION,
        joints=JOINTS,
        standard_csv_columns=STANDARD_CSV_COLUMNS,
        summary_columns=SUMMARY_COLUMNS,
        column_definition=column_definition,
    )


def workbook_tables(rows: Sequence[Mapping[str, object]]) -> WorkbookTables:
    """Build the writer-independent student workbook tables and summary metrics."""
    return build_workbook_tables(rows, workbook_contract())
