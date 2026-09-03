"""Side-effecting command handlers for the squat command-line interface."""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Iterable
from pathlib import Path

from .cli_conversion import condition_from_args, condition_from_row
from .export_io import write_csv
from .export_schema import write_xlsx
from .simulation_service import Condition, simulate_condition


def write_json(path: Path, payload: object) -> None:
    """Write a UTF-8 JSON export, creating its parent directory when needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def read_conditions_csv(
    path: Path, defaults: argparse.Namespace
) -> Iterable[Condition]:
    """Yield conditions from the legacy-compatible batch CSV format."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=1):
            yield condition_from_row(row, index, defaults)


def run_condition(args: argparse.Namespace) -> int:
    """Simulate and export one command-line condition."""
    condition = condition_from_args(args)
    rows, summary = simulate_condition(condition)
    write_csv(Path(args.out), rows, mode=args.csv_mode)
    if args.summary:
        write_json(Path(args.summary), summary)
    if args.xlsx:
        write_xlsx(Path(args.xlsx), rows)
    print(f"{condition.condition_id}: {len(rows)} frames exportees vers {args.out}")
    print(
        f"backend={summary['actual_backend']} over_limit_frames={summary['over_limit_frames']} cop_outside_foot_frames={summary['cop_outside_foot_frames']}"
    )
    return 0


def run_batch(args: argparse.Namespace) -> int:
    """Simulate and export every condition from a batch CSV."""
    all_rows: list[dict[str, object]] = []
    summaries = []
    for condition in read_conditions_csv(Path(args.conditions), args):
        rows, summary = simulate_condition(condition)
        all_rows.extend(rows)
        summaries.append(summary)
    write_csv(Path(args.out), all_rows, mode=args.csv_mode)
    if args.summary:
        write_json(Path(args.summary), {"conditions": summaries})
    if args.xlsx:
        write_xlsx(Path(args.xlsx), all_rows)
    print(f"{len(summaries)} conditions exportees vers {args.out}")
    return 0
