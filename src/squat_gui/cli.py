"""Command-line exports for squat conditions."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from math import degrees, radians
from pathlib import Path
from typing import Iterable

from .anthropometry import Anthropometry, scale_from_percent
from .backend import BiorbdModelCache
from .dynamics import (
    available_joint_torque_limits,
    simulate,
    torque_presets,
)
from .kinematics import PhaseDurations, zmp_in_support, zmp_support_limits


JOINTS = ("cheville", "genou", "hanche")
DEFAULT_SEGMENT_ANGLES_DEG = (22.0, -58.0, 20.0)
TORQUE_PRESET_ALIASES = {
    "anderson": "Anderson actif x2",
    "anderson-actif-x2": "Anderson actif x2",
    "sportifs": "Sportifs",
}


@dataclass(frozen=True)
class Condition:
    condition_id: str
    load_percent_bw: float
    subject_profile: str
    bar_position: str
    wedge_20_deg: bool
    shank_percent: float
    thigh_percent: float
    trunk_percent: float
    duration_excentrique_s: float
    duration_isometrique_s: float
    duration_concentrique_s: float
    q_segment_deg: tuple[float, float, float]
    torque_preset: str
    max_torques: dict[str, float]
    angle_adapt: bool
    frames: int
    backend: str

    @property
    def load_kg(self) -> float:
        return 70.0 * self.load_percent_bw / 100.0

    @property
    def phase_durations(self) -> PhaseDurations:
        return PhaseDurations(self.duration_excentrique_s, self.duration_isometrique_s, self.duration_concentrique_s)

    @property
    def total_duration_s(self) -> float:
        return self.phase_durations.total


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
        raise argparse.ArgumentTypeError(f"Preset couple inconnu: {name}. Choix: {choices}")
    return TORQUE_PRESET_ALIASES[normalized]


def segment_angles_from_joint_angles(ankle_deg: float, knee_deg: float, hip_deg: float) -> tuple[float, float, float]:
    shank = ankle_deg
    thigh = shank + knee_deg
    trunk = thigh + hip_deg
    return (shank, thigh, trunk)


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

    return Condition(
        condition_id=args.condition_id,
        load_percent_bw=100.0 * args.load / 70.0 if args.load is not None else args.load_percent_bw,
        subject_profile=args.subject_profile,
        bar_position=args.bar_position,
        wedge_20_deg=args.wedge,
        shank_percent=args.shank,
        thigh_percent=args.thigh,
        trunk_percent=args.trunk,
        duration_excentrique_s=args.duration_excentrique,
        duration_isometrique_s=args.duration_isometrique,
        duration_concentrique_s=args.duration_concentrique,
        q_segment_deg=q_segment_deg,
        torque_preset=preset_name,
        max_torques=max_torques,
        angle_adapt=args.angle_adapt,
        frames=max(2, args.frames),
        backend=args.backend,
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


def condition_from_row(row: dict[str, str], index: int, defaults: argparse.Namespace) -> Condition:
    preset_name = preset_key(row_str(row, "torque_preset", defaults.torque_preset))
    max_torques = dict(torque_presets(70.0, 1.70)[preset_name].torques)
    for joint, column in (("cheville", "max_cheville"), ("genou", "max_genou"), ("hanche", "max_hanche")):
        if row.get(column, ""):
            max_torques[joint] = float(row[column])

    if all(row.get(column, "") for column in ("q_shank_deg", "q_thigh_deg", "q_trunk_deg")):
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
    return Condition(
        condition_id=row_str(row, "condition_id", f"condition_{index:03d}"),
        load_percent_bw=load_percent_bw,
        subject_profile=row_str(row, "subject_profile", defaults.subject_profile),
        bar_position=row_str(row, "bar_position", defaults.bar_position),
        wedge_20_deg=parse_bool(row_str(row, "wedge_20_deg", str(defaults.wedge))),
        shank_percent=row_float(row, "shank_percent", defaults.shank),
        thigh_percent=row_float(row, "thigh_percent", defaults.thigh),
        trunk_percent=row_float(row, "trunk_percent", defaults.trunk),
        duration_excentrique_s=row_float(row, "duration_excentrique_s", legacy_duration),
        duration_isometrique_s=row_float(row, "duration_isometrique_s", defaults.duration_isometrique),
        duration_concentrique_s=row_float(row, "duration_concentrique_s", legacy_duration),
        q_segment_deg=q_segment_deg,
        torque_preset=preset_name,
        max_torques=max_torques,
        angle_adapt=parse_bool(row_str(row, "angle_adapt", str(defaults.angle_adapt))),
        frames=max(2, row_int(row, "frames", defaults.frames)),
        backend=row_str(row, "backend", defaults.backend),
    )


def anthropometry(condition: Condition) -> Anthropometry:
    return Anthropometry(
        bar_mass=condition.load_kg,
        shank_scale=scale_from_percent(condition.shank_percent),
        thigh_scale=scale_from_percent(condition.thigh_percent),
        trunk_scale=scale_from_percent(condition.trunk_percent),
        subject_profile=condition.subject_profile,
        bar_position=condition.bar_position,
        wedge_angle_deg=20.0 if condition.wedge_20_deg else 0.0,
    )


def simulate_condition(condition: Condition) -> tuple[list[dict[str, object]], dict[str, object]]:
    anthro = anthropometry(condition)
    final_q = tuple(radians(value) for value in condition.q_segment_deg)
    model_cache = None if condition.backend == "analytical" else BiorbdModelCache()
    states, results = simulate(
        anthro,
        final_q,
        condition.phase_durations,
        condition.frames,
        condition.max_torques,
        condition.angle_adapt,
        model_cache,
    )
    actual_backend = results[0].backend if results else "none"
    if condition.backend == "biorbd" and actual_backend != "biorbd":
        raise RuntimeError("Backend biorbd demande, mais le calcul est tombe sur le backend analytique.")

    rows = []
    for frame, (state, result) in enumerate(zip(states, results)):
        limits = available_joint_torque_limits(state, condition.max_torques, condition.angle_adapt)
        zmp_posterior_limit, zmp_anterior_limit = zmp_support_limits(state.pose)
        zmp_supported = zmp_in_support(state.pose, result.cop_x)
        joint_angles = {
            "cheville": degrees(state.q[0]),
            "genou": degrees(state.q[1] - state.q[0]),
            "hanche": degrees(state.q[2] - state.q[1]),
        }
        joint_velocities = {
            "cheville": degrees(state.qdot[0]),
            "genou": degrees(state.qdot[1] - state.qdot[0]),
            "hanche": degrees(state.qdot[2] - state.qdot[1]),
        }
        joint_accelerations = {
            "cheville": degrees(state.qddot[0]),
            "genou": degrees(state.qddot[1] - state.qddot[0]),
            "hanche": degrees(state.qddot[2] - state.qddot[1]),
        }
        row: dict[str, object] = {
            "condition_id": condition.condition_id,
            "frame": frame,
            "time_s": state.time,
            "phase": state.phase,
            "backend": result.backend,
            "subject_profile": condition.subject_profile,
            "bar_position": condition.bar_position,
            "wedge_20_deg": condition.wedge_20_deg,
            "load_percent_bw": condition.load_percent_bw,
            "load_kg": condition.load_kg,
            "shank_percent": condition.shank_percent,
            "thigh_percent": condition.thigh_percent,
            "trunk_percent": condition.trunk_percent,
            "duration_excentrique_s": condition.duration_excentrique_s,
            "duration_isometrique_s": condition.duration_isometrique_s,
            "duration_concentrique_s": condition.duration_concentrique_s,
            "total_duration_s": condition.total_duration_s,
            "q_shank_deg": degrees(state.q[0]),
            "q_thigh_deg": degrees(state.q[1]),
            "q_trunk_deg": degrees(state.q[2]),
            "com_x_m": result.com[0],
            "com_y_m": result.com[1],
            "com_vx_m_s": result.com_velocity[0],
            "com_vy_m_s": result.com_velocity[1],
            "com_ax_m_s2": result.com_acceleration[0],
            "com_ay_m_s2": result.com_acceleration[1],
            "cop_x_m": result.cop_x,
            "zmp_posterior_limit_m": zmp_posterior_limit,
            "zmp_anterior_limit_m": zmp_anterior_limit,
            "zmp_in_support": zmp_supported,
            "cop_in_foot": zmp_supported,
            "grf_x_N": result.ground_reaction[0],
            "grf_y_N": result.ground_reaction[1],
            "dynamic_moment_z_Nm": result.dynamic_moment_z,
        }
        for joint in JOINTS:
            row[f"{joint}_angle_deg"] = joint_angles[joint]
            row[f"{joint}_velocity_deg_s"] = joint_velocities[joint]
            row[f"{joint}_acceleration_deg_s2"] = joint_accelerations[joint]
            row[f"{joint}_torque_Nm"] = result.torques[joint]
            row[f"{joint}_max_available_Nm"] = limits[joint]
            row[f"{joint}_effort_percent"] = 100.0 * result.effort_ratios[joint]
            row[f"{joint}_power_W"] = result.powers[joint]
            row[f"{joint}_inverse_dynamics_total_Nm"] = result.torque_components[joint]["total"]
            row[f"{joint}_contact_Nm"] = result.torque_components[joint]["contact"]
            row[f"{joint}_inertial_nonlinear_Nm"] = result.torque_components[joint][
                "inertiels_non_lineaires"
            ]
        rows.append(row)

    summary = condition_summary(condition, rows, actual_backend)
    return rows, summary


def condition_summary(condition: Condition, rows: list[dict[str, object]], actual_backend: str) -> dict[str, object]:
    peaks = {}
    for joint in JOINTS:
        peaks[joint] = {
            "peak_abs_torque_Nm": max(abs(float(row[f"{joint}_torque_Nm"])) for row in rows),
            "peak_effort_percent": max(float(row[f"{joint}_effort_percent"]) for row in rows),
            "peak_abs_power_W": max(abs(float(row[f"{joint}_power_W"])) for row in rows),
        }
    return {
        "condition": asdict(condition),
        "actual_backend": actual_backend,
        "frames": len(rows),
        "cop_outside_foot_frames": sum(1 for row in rows if not bool(row["cop_in_foot"])),
        "zmp_outside_support_frames": sum(1 for row in rows if not bool(row["zmp_in_support"])),
        "over_limit_frames": sum(
            1
            for row in rows
            if any(float(row[f"{joint}_effort_percent"]) > 100.0 for joint in JOINTS)
        ),
        "peaks": peaks,
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run_condition(args: argparse.Namespace) -> int:
    condition = condition_from_args(args)
    rows, summary = simulate_condition(condition)
    write_csv(Path(args.out), rows)
    if args.summary:
        write_json(Path(args.summary), summary)
    print(f"{condition.condition_id}: {len(rows)} frames exportees vers {args.out}")
    print(f"backend={summary['actual_backend']} over_limit_frames={summary['over_limit_frames']} cop_outside_foot_frames={summary['cop_outside_foot_frames']}")
    return 0


def read_conditions_csv(path: Path, defaults: argparse.Namespace) -> Iterable[Condition]:
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
    write_csv(Path(args.out), all_rows)
    if args.summary:
        write_json(Path(args.summary), {"conditions": summaries})
    print(f"{len(summaries)} conditions exportees vers {args.out}")
    return 0


def add_condition_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--condition-id", default="condition_001")
    parser.add_argument("--load-percent-bw", type=float, default=0.0, help="Charge de barre en pourcentage du poids de corps (sujet 70 kg).")
    parser.add_argument("--load", type=float, help="Compatibilite: charge de barre en kg, prioritaire sur --load-percent-bw.")
    parser.add_argument("--subject-profile", choices=("homme", "femme enceinte"), default="homme")
    parser.add_argument("--bar-position", choices=("front", "back", "over-head"), default="back")
    parser.add_argument("--wedge", action="store_true", help="Ajouter une talonnette de 20 deg.")
    parser.add_argument("--shank", type=float, default=0.0, help="Variation longueur tibia en pourcent.")
    parser.add_argument("--thigh", type=float, default=0.0, help="Variation longueur cuisse en pourcent.")
    parser.add_argument("--trunk", type=float, default=0.0, help="Variation longueur tronc en pourcent.")
    parser.add_argument("--duration-excentrique", type=float, choices=(2.0, 2.5, 3.0, 3.5, 4.0), default=4.0)
    parser.add_argument("--duration-isometrique", type=float, choices=(0.0, 0.5, 1.0, 1.5, 2.0), default=2.0)
    parser.add_argument("--duration-concentrique", type=float, choices=(2.0, 2.5, 3.0, 3.5, 4.0), default=4.0)
    parser.add_argument("--frames", type=int, default=81)
    parser.add_argument("--q-segment-deg", type=float, nargs=3, default=DEFAULT_SEGMENT_ANGLES_DEG, metavar=("SHANK", "THIGH", "TRUNK"))
    parser.add_argument("--joint-angles-deg", type=float, nargs=3, metavar=("ANKLE", "KNEE", "HIP"), help="Angles articulaires finaux en degres. Prioritaire sur --q-segment-deg.")
    parser.add_argument("--torque-preset", default="anderson", help="anderson ou sportifs.")
    parser.add_argument("--max-cheville", type=float)
    parser.add_argument("--max-genou", type=float)
    parser.add_argument("--max-hanche", type=float)
    parser.add_argument("--angle-adapt", type=parse_bool, default=True)
    parser.add_argument("--backend", choices=("auto", "analytical", "biorbd"), default="auto")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Exporter rapidement des simulations de squat 2D.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Exporter une condition unique.")
    add_condition_arguments(run_parser)
    run_parser.add_argument("--out", default="exports/squat_results.csv")
    run_parser.add_argument("--summary", default="exports/squat_summary.json")
    run_parser.set_defaults(func=run_condition)

    batch_parser = subparsers.add_parser("batch", help="Exporter un lot de conditions depuis un CSV.")
    add_condition_arguments(batch_parser)
    batch_parser.add_argument("conditions", help="CSV de conditions.")
    batch_parser.add_argument("--out", default="exports/squat_batch_results.csv")
    batch_parser.add_argument("--summary", default="exports/squat_batch_summary.json")
    batch_parser.set_defaults(func=run_batch)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
