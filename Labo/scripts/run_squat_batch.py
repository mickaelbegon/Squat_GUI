#!/usr/bin/env python3
"""Run the public lab scenarios with the Squat_GUI command line interface."""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def filter_conditions(source: Path, selected: list[str] | None) -> Path:
    if not selected:
        return source
    keep = set(selected)
    handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
    with source.open(newline="", encoding="utf-8") as source_handle, handle:
        reader = csv.DictReader(source_handle)
        writer = csv.DictWriter(handle, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            if row.get("condition_id") in keep:
                writer.writerow(row)
    return Path(handle.name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conditions", type=Path, default=Path("scenarios/scenarios_labo_squat.csv"))
    parser.add_argument("--out", type=Path, default=Path("results_labo_squat"))
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conditions = filter_conditions(args.conditions, args.only)
    result_csv = args.out / "results.csv"
    summary_json = args.out / "summary.json"
    command = [
        sys.executable,
        "-m",
        "squat_gui",
        "batch",
        str(conditions),
        "--out",
        str(result_csv),
        "--summary",
        str(summary_json),
    ]
    print(" ".join(command))
    if args.dry_run:
        return 0
    project_src = Path(__file__).resolve().parents[2] / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{project_src}{os.pathsep}{env.get('PYTHONPATH', '')}"
    completed = subprocess.run(command, text=True, env=env)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
