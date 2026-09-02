#!/usr/bin/env python3
"""Summarize Squat_GUI CLI exports for the student lab without extra dependencies."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


JOINT_MAP = {
    "hip": "hanche",
    "knee": "genou",
    "ankle": "cheville",
}
CONDITION_COLUMNS = (
    "subject_profile",
    "bar_position",
    "load_percent_bw",
    "wedge_20_deg",
    "shank_percent",
    "thigh_percent",
    "trunk_percent",
    "anthropometry_mode",
    "duration_excentrique_s",
    "duration_isometrique_s",
    "duration_concentrique_s",
    "backend",
)


def read_results(path: Path) -> list[dict[str, str]]:
    files = [path] if path.is_file() else sorted(path.rglob("*.csv"))
    if not files:
        raise SystemExit(f"Aucun fichier CSV trouve dans {path}")
    rows: list[dict[str, str]] = []
    for file in files:
        with file.open(newline="", encoding="utf-8") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def number(row: dict[str, str], column: str) -> float:
    return float(row[column])


def peak_abs(rows: list[dict[str, str]], column: str) -> float:
    return max(abs(number(row, column)) for row in rows)


def parse_bool(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes", "oui")


def mean(rows: list[dict[str, str]], column: str) -> float:
    return sum(number(row, column) for row in rows) / len(rows)


def available_numbers(rows: list[dict[str, str]], column: str) -> list[float]:
    return [
        float(row[column])
        for row in rows
        if column in row and row[column] not in ("", "None", None)
    ]


def support_point_in_functional_base(row: dict[str, str]) -> bool:
    return parse_bool(row["support_point_in_functional_base"])


def summarize_condition(condition_id: str, rows: list[dict[str, str]]) -> dict[str, object]:
    cop_outside_frames = sum(
        1
        for frame in rows
        if not parse_bool(frame["support_point_in_geometric_base"])
    )
    zmp_outside_frames = sum(
        1 for frame in rows if not support_point_in_functional_base(frame)
    )
    summary: dict[str, object] = {
        "scenario": condition_id,
        "frames": len(rows),
        "cop_outside_foot_frames": cop_outside_frames,
        "cop_outside_foot_percent": 100.0 * cop_outside_frames / len(rows),
        "zmp_outside_support_frames": zmp_outside_frames,
        "zmp_outside_support_percent": 100.0 * zmp_outside_frames / len(rows),
    }
    for column in CONDITION_COLUMNS:
        if column in rows[0]:
            summary[column] = rows[0][column]

    squat_rows = [frame for frame in rows if frame["phase"] == "isometrique"]
    if not squat_rows:
        squat_rows = [min(rows, key=lambda frame: number(frame, "com_y_m"))]
    summary["squat_com_x_m"] = mean(squat_rows, "com_x_m")
    summary["squat_support_point_x_m"] = mean(squat_rows, "support_point_x_m")

    for english, french in JOINT_MAP.items():
        summary[f"peak_{english}_torque_Nm"] = peak_abs(rows, f"{french}_torque_Nm")
        utilizations = available_numbers(rows, f"{french}_utilization_ratio")
        summary[f"peak_{english}_effort"] = (
            max(utilizations) if utilizations else None
        )
        summary[f"peak_{english}_power_W"] = peak_abs(rows, f"{french}_power_W")
        for metric, suffix in (
            ("total", "inverse_dynamics_total_Nm"),
            ("mass_acceleration", "mass_acceleration_Nm"),
            ("velocity_dependent", "velocity_dependent_Nm"),
            ("gravity", "gravity_Nm"),
            ("external_contact_effect", "external_contact_effect_Nm"),
            ("inertial_nonlinear", "inertial_nonlinear_Nm"),
            ("reconstruction_residual", "inverse_dynamics_reconstruction_residual_Nm"),
        ):
            column = f"{french}_{suffix}"
            if column in rows[0]:
                summary[f"peak_{english}_{metric}_Nm"] = peak_abs(rows, column)

    peak_knee = float(summary["peak_knee_torque_Nm"])
    summary["peak_hip_to_knee_torque_ratio"] = (
        None if peak_knee == 0.0 else float(summary["peak_hip_torque_Nm"]) / peak_knee
    )
    summary["support_point_x_min_m"] = min(
        number(row, "support_point_x_m") for row in rows
    )
    summary["support_point_x_max_m"] = max(
        number(row, "support_point_x_m") for row in rows
    )
    summary["support_point_excursion_m"] = float(
        summary["support_point_x_max_m"]
    ) - float(summary["support_point_x_min_m"])
    summary["com_x_min_m"] = min(number(row, "com_x_m") for row in rows)
    summary["com_x_max_m"] = max(number(row, "com_x_m") for row in rows)
    summary["com_excursion_m"] = float(summary["com_x_max_m"]) - float(summary["com_x_min_m"])
    summary["peak_grf_y_N"] = peak_abs(rows, "grf_y_N")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    grouped: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_results(args.results):
        grouped[row["condition_id"]].append(row)
    summaries = [summarize_condition(condition_id, grouped[condition_id]) for condition_id in sorted(grouped)]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    print("Ecrit", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
