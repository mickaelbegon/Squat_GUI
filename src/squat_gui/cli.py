"""Command-line exports for squat conditions."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable

from .anthropometry import ANTHROPOMETRY_MODES
from .torque_capacity import torque_presets
from .didactics import (
    DYNAMIC_PHASE_DURATION_OPTIONS,
    ISOMETRIC_PHASE_DURATION_OPTIONS,
    bounded_phase_durations,
)
from .export_io import write_csv
from .export_schema import write_xlsx
from .kinematics import (
    DEFAULT_SAMPLE_PERIOD_S,
    PhaseDurations,
    frame_count_for_duration,
    segment_values_from_joint_values,
)
from .simulation_service import (
    JOINTS,
    Condition,
    anthropometry,
    condition_from_settings,
    condition_summary,
    simulate_condition,
)

DEFAULT_SEGMENT_ANGLES_DEG = (22.0, -58.0, 20.0)
TORQUE_PRESET_ALIASES = {
    "anderson": "Anderson actif x2",
    "anderson-actif-x2": "Anderson actif x2",
    "sportifs": "Sportifs",
}

def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in ("1", "true", "yes", "y", "oui", "o"):
        return True
    if normalized in ("0", "false", "no", "n", "non"):
        return False
    raise argparse.ArgumentTypeError(f"Valeur booleenne invalide: {value}")


def preset_key(name: str) -> str:
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


def condition_from_args(args: argparse.Namespace) -> Condition:
    q_segment_deg = tuple(args.q_segment_deg)
    if args.joint_angles_deg is not None:
        q_segment_deg = segment_angles_from_joint_angles(*args.joint_angles_deg)

    preset_name = preset_key(args.torque_preset)
    max_torques = dict(torque_presets(70.0, 1.70)[preset_name].torques)
    overrides = {
        "cheville": args.max_cheville,
        "genou": args.max_genou,
        "hanche": args.max_hanche,
    }
    for joint, value in overrides.items():
        if value is not None:
            max_torques[joint] = value

    durations = PhaseDurations(
        args.duration_excentrique,
        args.duration_isometrique,
        args.duration_concentrique,
    )
    frames = max(2, args.frames) if args.frames else frame_count_for_duration(durations)
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
        max_torques=max_torques,
        angle_adapt=args.angle_adapt,
        velocity_adapt=args.velocity_adapt,
        frames=frames,
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


def condition_from_row(
    row: dict[str, str], index: int, defaults: argparse.Namespace
) -> Condition:
    preset_name = preset_key(row_str(row, "torque_preset", defaults.torque_preset))
    max_torques = dict(torque_presets(70.0, 1.70)[preset_name].torques)
    for joint, column in (
        ("cheville", "max_cheville"),
        ("genou", "max_genou"),
        ("hanche", "max_hanche"),
    ):
        if row.get(column, ""):
            max_torques[joint] = float(row[column])

    if all(
        row.get(column, "") for column in ("q_shank_deg", "q_thigh_deg", "q_trunk_deg")
    ):
        q_segment_deg = (
            float(row["q_shank_deg"]),
            float(row["q_thigh_deg"]),
            float(row["q_trunk_deg"]),
        )
    elif all(row.get(column, "") for column in ("ankle_deg", "knee_deg", "hip_deg")):
        q_segment_deg = segment_angles_from_joint_angles(
            float(row["ankle_deg"]),
            float(row["knee_deg"]),
            float(row["hip_deg"]),
        )
    else:
        q_segment_deg = tuple(defaults.q_segment_deg)

    legacy_load = row_float(row, "load_kg", 0.0)
    load_percent_bw = row_float(row, "load_percent_bw", 100.0 * legacy_load / 70.0)
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
    requested_frames = row_int(row, "frames", defaults.frames)
    frames = (
        max(2, requested_frames)
        if requested_frames
        else frame_count_for_duration(durations)
    )
    return Condition(
        condition_id=row_str(row, "condition_id", f"condition_{index:03d}"),
        load_percent_bw=load_percent_bw,
        subject_profile=row_str(row, "subject_profile", defaults.subject_profile),
        bar_position=row_str(row, "bar_position", defaults.bar_position),
        wedge_20_deg=parse_bool(row_str(row, "wedge_20_deg", str(defaults.wedge))),
        shank_percent=row_float(row, "shank_percent", defaults.shank),
        thigh_percent=row_float(row, "thigh_percent", defaults.thigh),
        trunk_percent=row_float(row, "trunk_percent", defaults.trunk),
        anthropometry_mode=row_str(
            row, "anthropometry_mode", defaults.anthropometry_mode
        ),
        duration_excentrique_s=duration_excentrique_s,
        duration_isometrique_s=duration_isometrique_s,
        duration_concentrique_s=duration_concentrique_s,
        q_segment_deg=q_segment_deg,
        torque_preset=preset_name,
        max_torques=max_torques,
        angle_adapt=parse_bool(row_str(row, "angle_adapt", str(defaults.angle_adapt))),
        velocity_adapt=parse_bool(
            row_str(row, "velocity_adapt", str(defaults.velocity_adapt))
        ),
        frames=frames,
        backend=row_str(row, "backend", defaults.backend),
        optimize_bar_path_experimental=parse_bool(
            row_str(
                row,
                "optimize_bar_path_experimental",
                str(defaults.optimize_bar_path),
            )
        ),
    )


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run_condition(args: argparse.Namespace) -> int:
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


def read_conditions_csv(
    path: Path, defaults: argparse.Namespace
) -> Iterable[Condition]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=1):
            yield condition_from_row(row, index, defaults)


def run_batch(args: argparse.Namespace) -> int:
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


def add_condition_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--condition-id", default="condition_001")
    parser.add_argument(
        "--load-percent-bw",
        type=float,
        default=0.0,
        help="Charge de barre en pourcentage du poids de corps (sujet 70 kg).",
    )
    parser.add_argument(
        "--load",
        type=float,
        help="Compatibilite: charge de barre en kg, prioritaire sur --load-percent-bw.",
    )
    parser.add_argument(
        "--subject-profile", choices=("homme", "femme enceinte"), default="homme"
    )
    parser.add_argument(
        "--bar-position", choices=("front", "back", "over-head"), default="back"
    )
    parser.add_argument(
        "--wedge", action="store_true", help="Ajouter une talonnette de 20 deg."
    )
    parser.add_argument(
        "--shank", type=float, default=0.0, help="Variation longueur tibia en pourcent."
    )
    parser.add_argument(
        "--thigh",
        type=float,
        default=0.0,
        help="Variation longueur cuisse en pourcent.",
    )
    parser.add_argument(
        "--trunk", type=float, default=0.0, help="Variation longueur tronc en pourcent."
    )
    parser.add_argument(
        "--anthropometry-mode",
        choices=ANTHROPOMETRY_MODES,
        default="longueur seule",
        help=(
            "longueur seule conserve masses/inerties; morphotype recalibre "
            "recalcule les masses avec l'hypothese didactique documentee."
        ),
    )
    parser.add_argument(
        "--duration-excentrique",
        type=float,
        choices=DYNAMIC_PHASE_DURATION_OPTIONS,
        default=4.0,
    )
    parser.add_argument(
        "--duration-isometrique",
        type=float,
        choices=ISOMETRIC_PHASE_DURATION_OPTIONS,
        default=2.0,
    )
    parser.add_argument(
        "--duration-concentrique",
        type=float,
        choices=DYNAMIC_PHASE_DURATION_OPTIONS,
        default=4.0,
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=0,
        help=f"Nombre de frames; 0 utilise automatiquement Δt={DEFAULT_SAMPLE_PERIOD_S:.2f} s.",
    )
    parser.add_argument(
        "--q-segment-deg",
        type=float,
        nargs=3,
        default=DEFAULT_SEGMENT_ANGLES_DEG,
        metavar=("SHANK", "THIGH", "TRUNK"),
    )
    parser.add_argument(
        "--joint-angles-deg",
        type=float,
        nargs=3,
        metavar=("ANKLE", "KNEE", "HIP"),
        help="Angles articulaires finaux en degres. Prioritaire sur --q-segment-deg.",
    )
    parser.add_argument(
        "--torque-preset", default="anderson", help="anderson ou sportifs."
    )
    parser.add_argument("--max-cheville", type=float)
    parser.add_argument("--max-genou", type=float)
    parser.add_argument("--max-hanche", type=float)
    parser.add_argument("--angle-adapt", type=parse_bool, default=True)
    parser.add_argument("--velocity-adapt", type=parse_bool, default=True)
    parser.add_argument(
        "--optimize-bar-path",
        action="store_true",
        help=(
            "Activer la stabilisation expérimentale SLSQP de la trajectoire "
            "horizontale de la barre (±5 deg, contraintes CoP)."
        ),
    )
    parser.add_argument(
        "--backend", choices=("auto", "analytical", "biorbd"), default="auto"
    )


def add_export_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--csv-mode",
        choices=("standard", "full"),
        default="standard",
        help=(
            "standard exporte les variables biomécaniques essentielles; "
            "full conserve toutes les colonnes diagnostiques."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Exporter rapidement des simulations de squat 2D."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Exporter une condition unique.")
    add_condition_arguments(run_parser)
    add_export_arguments(run_parser)
    run_parser.add_argument("--out", default="exports/squat_results.csv")
    run_parser.add_argument(
        "--summary",
        default="",
        help="Résumé JSON optionnel (les métriques étudiantes sont aussi dans Excel).",
    )
    run_parser.add_argument(
        "--xlsx", default="", help="Classeur Excel global optionnel."
    )
    run_parser.set_defaults(func=run_condition)

    batch_parser = subparsers.add_parser(
        "batch", help="Exporter un lot de conditions depuis un CSV."
    )
    add_condition_arguments(batch_parser)
    add_export_arguments(batch_parser)
    batch_parser.add_argument("conditions", help="CSV de conditions.")
    batch_parser.add_argument("--out", default="exports/squat_batch_results.csv")
    batch_parser.add_argument(
        "--summary",
        default="",
        help="Résumé JSON optionnel (les métriques étudiantes sont aussi dans Excel).",
    )
    batch_parser.add_argument(
        "--xlsx", default="", help="Classeur Excel global optionnel."
    )
    batch_parser.set_defaults(func=run_batch)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
