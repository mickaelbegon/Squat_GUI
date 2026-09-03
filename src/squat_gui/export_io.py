"""File-writing helpers shared by the GUI and command-line interface."""

from __future__ import annotations

import csv
from pathlib import Path
from tempfile import NamedTemporaryFile

from .export_schema import csv_export_rows


def write_csv(
    path: Path, rows: list[dict[str, object]], *, mode: str = "standard"
) -> None:
    """Atomically replace a CSV so a failed export preserves the previous file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    exported_rows = csv_export_rows(rows, mode=mode)
    fieldnames = list(exported_rows[0]) if exported_rows else []
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            newline="",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(exported_rows)
        temporary_path.replace(path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
