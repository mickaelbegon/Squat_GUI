"""Public compatibility facade for the squat command-line interface.

Parser assembly, input conversion and command handlers live in focused
modules. Names historically imported from ``cli`` remain available here.
"""

from __future__ import annotations

# Kept public because downstream code historically patched this module while
# characterising atomic CSV exports.
import csv

from .cli_conversion import (
    DEFAULT_SEGMENT_ANGLES_DEG,
    TORQUE_PRESET_ALIASES,
    condition_from_args,
    condition_from_row,
    parse_bool,
    preset_key,
    row_float,
    row_int,
    row_str,
    segment_angles_from_joint_angles,
)
from .cli_handlers import read_conditions_csv, run_batch, run_condition, write_json
from .cli_parser import add_condition_arguments, add_export_arguments, build_parser
from .export_io import write_csv
from .simulation_service import (
    JOINTS,
    Condition,
    anthropometry,
    condition_from_settings,
    condition_summary,
    simulate_condition,
)

__all__ = [
    "DEFAULT_SEGMENT_ANGLES_DEG",
    "JOINTS",
    "TORQUE_PRESET_ALIASES",
    "Condition",
    "add_condition_arguments",
    "add_export_arguments",
    "anthropometry",
    "build_parser",
    "condition_from_args",
    "condition_from_row",
    "condition_from_settings",
    "condition_summary",
    "main",
    "parse_bool",
    "preset_key",
    "read_conditions_csv",
    "row_float",
    "row_int",
    "row_str",
    "run_batch",
    "run_condition",
    "segment_angles_from_joint_angles",
    "simulate_condition",
    "write_csv",
    "write_json",
]


def main(argv: list[str] | None = None) -> int:
    """Run the selected sub-command and return its historical exit code."""
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
