#!/usr/bin/env python3
"""Summarize Squat_GUI CLI exports for the student lab."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


JOINT_MAP = {
    "hip": "hanche",
    "knee": "genou",
    "ankle": "cheville",
}


def read_results(path: Path) -> pd.DataFrame:
    if path.is_file():
        return pd.read_csv(path)
    files = sorted(path.rglob("*.csv"))
    if not files:
        raise SystemExit(f"Aucun fichier CSV trouve dans {path}")
    return pd.concat([pd.read_csv(file) for file in files], ignore_index=True)


def peak_abs(series: pd.Series) -> float:
    return float(pd.to_numeric(series, errors="coerce").abs().max())


def summarize_condition(condition_id: str, df: pd.DataFrame) -> dict[str, float | str | int]:
    row: dict[str, float | str | int] = {
        "scenario": condition_id,
        "frames": int(len(df)),
        "cop_outside_foot_frames": int((~df["cop_in_foot"].astype(bool)).sum()),
    }
    for english, french in JOINT_MAP.items():
        row[f"peak_{english}_torque_Nm"] = peak_abs(df[f"{french}_torque_Nm"])
        row[f"peak_{english}_effort"] = float(pd.to_numeric(df[f"{french}_effort_percent"], errors="coerce").max() / 100.0)
        row[f"peak_{english}_power_W"] = peak_abs(df[f"{french}_power_W"])
    row["peak_hip_to_knee_torque_ratio"] = row["peak_hip_torque_Nm"] / row["peak_knee_torque_Nm"]
    row["cop_x_min_m"] = float(pd.to_numeric(df["cop_x_m"], errors="coerce").min())
    row["cop_x_max_m"] = float(pd.to_numeric(df["cop_x_m"], errors="coerce").max())
    row["com_x_min_m"] = float(pd.to_numeric(df["com_x_m"], errors="coerce").min())
    row["com_x_max_m"] = float(pd.to_numeric(df["com_x_m"], errors="coerce").max())
    row["peak_grf_y_N"] = peak_abs(df["grf_y_N"])
    row["peak_mqddot_knee_Nm"] = peak_abs(df["genou_Mqddot_Nm"])
    row["peak_contact_knee_Nm"] = peak_abs(df["genou_contact_Nm"])
    row["peak_nleffects_knee_Nm"] = peak_abs(df["genou_NLeffects_Nm"])
    row["knee_inertial_share_pct"] = 100.0 * row["peak_mqddot_knee_Nm"] / row["peak_knee_torque_Nm"]
    row["knee_contact_share_pct"] = 100.0 * row["peak_contact_knee_Nm"] / row["peak_knee_torque_Nm"]
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    df = read_results(args.results)
    rows = [
        summarize_condition(str(condition_id), group)
        for condition_id, group in df.groupby("condition_id", sort=True)
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.out, index=False)
    print("Ecrit", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
