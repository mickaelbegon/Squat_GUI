"""Argument and CSV-row conversion for the command-line interface.

This module deliberately contains no file I/O or simulation calls. Keeping
the conversion boundary pure makes the CLI input contract easy to exercise.
"""

from __future__ import annotations

import argparse

from .didactics import bounded_phase_durations
from .kinematics import (
    PhaseDurations,
    frame_count_for_duration,
    segment_values_from_joint_values,
)
from .simulation_service import Condition
from .torque_capacity import torque_presets

DEFAULT_SEGMENT_ANGLES_DEG = (22.0, -58.0, 20.0)
TORQUE_PRESET_ALIASES = {
    "anderson": "Anderson actif x2",
    "anderson-actif-x2": "Anderson actif x2",
    "sportifs": "Sportifs",
}


def parse_bool(value: str | bool) -> bool:
    """Parse the documented French and English boolean spellings."""
    if isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in ("1", "true", "yes", "y", "oui", "o"):
        return True
    if normalized in ("0", "false", "no", "n", "non"):
        return False
    raise argparse.ArgumentTypeError(f"Valeur booleenne invalide: {value}")


def preset_key(name: str) -> str:
    """Resolve a user-facing torque preset spelling to its canonical name."""
    normalized = name.strip().lower().replace(" ", "-")
    if normalized not in TORQUE_PRESET_ALIASES:
        choices = ", ".join(TORQUE_PRESET_ALIASES)
        raise argparse.ArgumentTypeError(
            f"Preset couple inconnu: {name}. Choix: {choices}"
        )
    return TORQUE_PRESET_ALIASES[normalized]


def segment_angles_from_joint_angles(
    ankle_deg: float, knee_deg: float, hip_deg: float
) -> tuple[float, float, float]:
    """Compatibility wrapper for the canonical kinematic conversion."""
    return segment_values_from_joint_values(ankle_deg, knee_deg, hip_deg)


def _max_torques(preset_name: str, overrides: dict[str, float | None]) -> dict[str, float]:
    max_torques = dict(torque_presets(70.0, 1.70)[preset_name].torques)
    for joint, value in overrides.items():
        if value is not None:
            max_torques[joint] = value
    return max_torques


def _frames(durations: PhaseDurations, requested_frames: int) -> int:
    return (
        max(2, requested_frames)
        if requested_frames
        else frame_count_for_duration(durations)
    )


def condition_from_args(args: argparse.Namespace) -> Condition:
    """Convert the parsed ``run`` arguments to the simulation condition."""
    q_segment_deg = tuple(args.q_segment_deg)
    if args.joint_angles_deg is not None:
        q_segment_deg = segment_angles_from_joint_angles(*args.joint_angles_deg)
    preset_name = preset_key(args.torque_preset)
    durations = PhaseDurations(
        args.duration_excentrique,
        args.duration_isometrique,
        args.duration_concentrique,
    )
    return Condition(
        condition_id=args.condition_id,
        load_percent_bw=(
            100.0 * args.load / 70.0 if args.load is not None else args.load_percent_bw
        ),
        subject_profile=args.subject_profile,
        bar_position=args.bar_position,
        wedge_20_deg=args.wedge,
        shank_percent=args.shank,
        thigh_percent=args.thigh,
        trunk_percent=args.trunk,
        anthropometry_mode=args.anthropometry_mode,
        duration_excentrique_s=args.duration_excentrique,
        duration_isometrique_s=args.duration_isometrique,
        duration_concentrique_s=args.duration_concentrique,
        q_segment_deg=q_segment_deg,
        torque_preset=preset_name,
        max_torques=_max_torques(
            preset_name,
            {
                "cheville": args.max_cheville,
                "genou": args.max_genou,
                "hanche": args.max_hanche,
            },
        ),
        angle_adapt=args.angle_adapt,
        velocity_adapt=args.velocity_adapt,
        frames=_frames(durations, args.frames),
        backend=args.backend,
        optimize_bar_path_experimental=args.optimize_bar_path,
    )


def row_float(row: dict[str, str], key: str, default: float) -> float:
    value = row.get(key, "")
    return default if value == "" else float(value)


def row_int(row: dict[str, str], key: str, default: int) -> int:
    value = row.get(key, "")
    return default if value == "" else int(value)


def row_str(row: dict[str, str], key: str, default: str) -> str:
    value = row.get(key, "")
    return default if value == "" else value


def _row_segment_angles(
    row: dict[str, str], defaults: argparse.Namespace
) -> tuple[float, float, float]:
    segment_columns = ("q_shank_deg", "q_thigh_deg", "q_trunk_deg")
    if all(row.get(column, "") for column in segment_columns):
        return tuple(float(row[column]) for column in segment_columns)  # type: ignore[return-value]
    joint_columns = ("ankle_deg", "knee_deg", "hip_deg")
    if all(row.get(column, "") for column in joint_columns):
        return segment_angles_from_joint_angles(
            *(float(row[column]) for column in joint_columns)
        )
    return tuple(defaults.q_segment_deg)


def condition_from_row(
    row: dict[str, str], index: int, defaults: argparse.Namespace
) -> Condition:
    """Convert one legacy-compatible batch CSV row to a condition."""
    preset_name = preset_key(row_str(row, "torque_preset", defaults.torque_preset))
    overrides = {
        joint: float(row[column]) if row.get(column, "") else None
        for joint, column in (
            ("cheville", "max_cheville"),
            ("genou", "max_genou"),
            ("hanche", "max_hanche"),
        )
    }
    legacy_duration = row_float(row, "duration_phase_s", defaults.duration_excentrique)
    duration_excentrique_s = row_float(row, "duration_excentrique_s", legacy_duration)
    duration_isometrique_s = row_float(
        row, "duration_isometrique_s", defaults.duration_isometrique
    )
    duration_concentrique_s = row_float(row, "duration_concentrique_s", legacy_duration)
    durations = bounded_phase_durations(
        PhaseDurations(
            duration_excentrique_s,
            duration_isometrique_s,
            duration_concentrique_s,
        )
    )
    return Condition(
        condition_id=row_str(row, "condition_id", f"condition_{index:03d}"),
        load_percent_bw=row_float(
            row, "load_percent_bw", 100.0 * row_float(row, "load_kg", 0.0) / 70.0
        ),
        subject_profile=row_str(row, "subject_profile", defaults.subject_profile),
        bar_position=row_str(row, "bar_position", defaults.bar_position),
        wedge_20_deg=parse_bool(row_str(row, "wedge_20_deg", str(defaults.wedge))),
        shank_percent=row_float(row, "shank_percent", defaults.shank),
        thigh_percent=row_float(row, "thigh_percent", defaults.thigh),
        trunk_percent=row_float(row, "trunk_percent", defaults.trunk),
        anthropometry_mode=row_str(row, "anthropometry_mode", defaults.anthropometry_mode),
        duration_excentrique_s=duration_excentrique_s,
        duration_isometrique_s=duration_isometrique_s,
        duration_concentrique_s=duration_concentrique_s,
        q_segment_deg=_row_segment_angles(row, defaults),
        torque_preset=preset_name,
        max_torques=_max_torques(preset_name, overrides),
        angle_adapt=parse_bool(row_str(row, "angle_adapt", str(defaults.angle_adapt))),
        velocity_adapt=parse_bool(
            row_str(row, "velocity_adapt", str(defaults.velocity_adapt))
        ),
        frames=_frames(durations, row_int(row, "frames", defaults.frames)),
        backend=row_str(row, "backend", defaults.backend),
        optimize_bar_path_experimental=parse_bool(
            row_str(
                row, "optimize_bar_path_experimental", str(defaults.optimize_bar_path)
            )
        ),
    )
