"""Command-line exports for squat conditions."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from math import degrees, radians
from pathlib import Path
from typing import Iterable

from .anthropometry import ANTHROPOMETRY_MODES, Anthropometry, scale_from_percent
from .backend import BiorbdModelCache
from .bar_path_optimization import optimize_deep_squat_bar_path
from .dynamics import force_balance, simulate, torque_presets
from .didactics import (
    DYNAMIC_PHASE_DURATION_OPTIONS,
    ISOMETRIC_PHASE_DURATION_OPTIONS,
    bounded_phase_durations,
)
from .export_schema import SCHEMA_VERSION, csv_export_rows, write_xlsx
from .kinematics import (
    DEFAULT_SAMPLE_PERIOD_S,
    PhaseDurations,
    frame_count_for_duration,
    joint_values_from_segment_values,
    segment_orientations,
    segment_values_from_joint_values,
)
from .observables import (
    com_contributions,
    frame_info,
    joint_coordinates,
    segment_anthropometry,
    support_margins,
)

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
    anthropometry_mode: str
    duration_excentrique_s: float
    duration_isometrique_s: float
    duration_concentrique_s: float
    q_segment_deg: tuple[float, float, float]
    torque_preset: str
    max_torques: dict[str, float]
    angle_adapt: bool
    velocity_adapt: bool
    frames: int
    backend: str
    optimize_bar_path_experimental: bool = False

    @property
    def load_kg(self) -> float:
        return 70.0 * self.load_percent_bw / 100.0

    @property
    def phase_durations(self) -> PhaseDurations:
        return PhaseDurations(
            self.duration_excentrique_s,
            self.duration_isometrique_s,
            self.duration_concentrique_s,
        )

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


def anthropometry(condition: Condition) -> Anthropometry:
    return Anthropometry(
        bar_mass=condition.load_kg,
        shank_scale=scale_from_percent(condition.shank_percent),
        thigh_scale=scale_from_percent(condition.thigh_percent),
        trunk_scale=scale_from_percent(condition.trunk_percent),
        scaling_mode=condition.anthropometry_mode,
        subject_profile=condition.subject_profile,
        bar_position=condition.bar_position,
        wedge_angle_deg=20.0 if condition.wedge_20_deg else 0.0,
    )


def condition_from_settings(
    settings: dict[str, object],
    final_q_deg: Iterable[float],
    condition_id: str,
    *,
    frames: int | None = None,
    backend: str = "auto",
) -> Condition:
    """Build an export condition from GUI-compatible settings."""
    legacy_duration = float(settings.get("duration_phase_s", 4.0))
    load_percent_bw = float(
        settings.get(
            "load_percent_bw",
            100.0 * float(settings.get("load_kg", 0.0)) / 70.0,
        )
    )
    preset_name = str(settings.get("torque_preset", "Anderson actif x2"))
    default_torques = (
        torque_presets(70.0, 1.70)
        .get(
            preset_name,
            torque_presets(70.0, 1.70)["Anderson actif x2"],
        )
        .torques
    )
    max_torques = {
        joint: float(
            dict(settings.get("max_torques", {})).get(joint, default_torques[joint])
        )
        for joint in JOINTS
    }
    q_values = tuple(float(value) for value in final_q_deg)
    if len(q_values) != 3:
        raise ValueError("Trois orientations segmentaires finales sont requises.")
    durations = bounded_phase_durations(
        PhaseDurations(
            float(settings.get("duration_excentrique_s", legacy_duration)),
            float(settings.get("duration_isometrique_s", 2.0)),
            float(settings.get("duration_concentrique_s", legacy_duration)),
        )
    )
    frame_count = int(frames or 0)
    if frame_count <= 0:
        frame_count = frame_count_for_duration(durations)
    return Condition(
        condition_id=condition_id,
        load_percent_bw=load_percent_bw,
        subject_profile=str(settings.get("subject_profile", "homme")),
        bar_position=str(settings.get("bar_position", "back")),
        wedge_20_deg=bool(settings.get("wedge_20_deg", False)),
        shank_percent=float(settings.get("shank_percent", 0.0)),
        thigh_percent=float(settings.get("thigh_percent", 0.0)),
        trunk_percent=float(settings.get("trunk_percent", 0.0)),
        anthropometry_mode=str(settings.get("anthropometry_mode", "longueur seule")),
        duration_excentrique_s=durations.excentrique,
        duration_isometrique_s=durations.isometrique,
        duration_concentrique_s=durations.concentrique,
        q_segment_deg=(q_values[0], q_values[1], q_values[2]),
        torque_preset=preset_name,
        max_torques=max_torques,
        angle_adapt=bool(settings.get("angle_adapt", True)),
        velocity_adapt=bool(settings.get("velocity_adapt", True)),
        frames=max(2, frame_count),
        backend=backend,
        optimize_bar_path_experimental=bool(
            settings.get("optimize_bar_path_experimental", False)
        ),
    )


def simulate_condition(
    condition: Condition,
) -> tuple[list[dict[str, object]], dict[str, object]]:
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
        condition.velocity_adapt,
    )
    optimization = None
    if condition.optimize_bar_path_experimental:
        optimization = optimize_deep_squat_bar_path(
            anthro,
            final_q,
            condition.phase_durations,
            condition.frames,
            condition.max_torques,
            condition.angle_adapt,
            model_cache,
            condition.velocity_adapt,
            baseline=(states, results),
        )
        states = optimization.states
        results = optimization.dynamics
    actual_backend = results[0].backend if results else "none"
    if condition.backend == "biorbd" and actual_backend != "biorbd":
        raise RuntimeError(
            "Backend biorbd demande, mais le calcul est tombe sur le backend analytique."
        )

    anthropometry_table = segment_anthropometry(anthro)
    rows = []
    for frame, (state, result) in enumerate(zip(states, results)):
        info = frame_info(states, frame)
        point_support = support_margins(state.pose, result.cop_x)
        com_support = support_margins(state.pose, state.pose.com[0])
        balance = force_balance(anthro, result)
        coordinates = {
            "heel": state.pose.heel,
            "toe": state.pose.toe,
            **joint_coordinates(state.pose),
        }
        orientations = segment_orientations(state.pose)
        contributions = com_contributions(anthro, state.pose)
        joint_angles = {
            joint: degrees(value)
            for joint, value in joint_values_from_segment_values(state.q).items()
        }
        joint_velocities = {
            joint: degrees(value)
            for joint, value in joint_values_from_segment_values(state.qdot).items()
        }
        joint_accelerations = {
            joint: degrees(value)
            for joint, value in joint_values_from_segment_values(state.qddot).items()
        }
        row: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "condition_id": condition.condition_id,
            "frame": frame,
            "time_s": state.time,
            "delta_time_s": info.delta_time_s,
            "normalized_time_percent": info.normalized_time_percent,
            "phase": state.phase,
            "backend": result.backend,
            "contact_source": result.contact_source,
            "subject_profile": condition.subject_profile,
            "bar_position": condition.bar_position,
            "wedge_20_deg": condition.wedge_20_deg,
            "load_percent_bw": condition.load_percent_bw,
            "load_kg": condition.load_kg,
            "body_mass_kg": anthro.body_mass,
            "total_mass_kg": anthro.total_mass,
            "height_m": anthro.height,
            "shank_percent": condition.shank_percent,
            "thigh_percent": condition.thigh_percent,
            "trunk_percent": condition.trunk_percent,
            "anthropometry_mode": condition.anthropometry_mode,
            "anthropometry_scaling_rule": anthro.scaling_rule,
            "duration_excentrique_s": condition.duration_excentrique_s,
            "duration_isometrique_s": condition.duration_isometrique_s,
            "duration_concentrique_s": condition.duration_concentrique_s,
            "total_duration_s": condition.total_duration_s,
            "frames": condition.frames,
            "torque_preset": condition.torque_preset,
            "angle_adapt": condition.angle_adapt,
            "velocity_adapt": condition.velocity_adapt,
            "bar_path_optimization_requested": (
                condition.optimize_bar_path_experimental
            ),
            "bar_path_optimization_applied": (
                bool(optimization.applied) if optimization is not None else False
            ),
            "bar_path_optimization_message": (
                optimization.message if optimization is not None else "désactivée"
            ),
            "max_cheville_Nm": condition.max_torques["cheville"],
            "max_genou_Nm": condition.max_torques["genou"],
            "max_hanche_Nm": condition.max_torques["hanche"],
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
            "support_point_x_m": result.cop_x,
            "support_point_label": result.support_point_label,
            "support_point_source": result.support_point_source,
            "geometric_support_posterior_m": point_support.geometric_posterior_m,
            "geometric_support_anterior_m": point_support.geometric_anterior_m,
            "functional_support_posterior_m": point_support.functional_posterior_m,
            "functional_support_anterior_m": point_support.functional_anterior_m,
            "support_point_geometric_posterior_margin_m": point_support.geometric_posterior_margin_m,
            "support_point_geometric_anterior_margin_m": point_support.geometric_anterior_margin_m,
            "support_point_functional_posterior_margin_m": point_support.functional_posterior_margin_m,
            "support_point_functional_anterior_margin_m": point_support.functional_anterior_margin_m,
            "support_point_in_geometric_base": point_support.in_geometric_base,
            "support_point_in_functional_base": point_support.in_functional_base,
            "com_projection_geometric_posterior_margin_m": com_support.geometric_posterior_margin_m,
            "com_projection_geometric_anterior_margin_m": com_support.geometric_anterior_margin_m,
            "com_projection_in_geometric_base": com_support.in_geometric_base,
            "zmp_posterior_limit_m": point_support.functional_posterior_m,
            "zmp_anterior_limit_m": point_support.functional_anterior_m,
            "zmp_in_support": point_support.in_functional_base,
            "cop_in_foot": point_support.in_geometric_base,
            "grf_x_N": result.ground_reaction[0],
            "grf_y_N": result.ground_reaction[1],
            "weight_magnitude_N": balance.weight_magnitude_N,
            "weight_x_N": balance.weight_vector_N[0],
            "weight_y_N": balance.weight_vector_N[1],
            "force_balance_residual_x_N": balance.residual_N[0],
            "force_balance_residual_y_N": balance.residual_N[1],
            "dynamic_moment_z_Nm": result.dynamic_moment_z,
        }
        for point, (x, y) in coordinates.items():
            row[f"{point}_x_m"] = x
            row[f"{point}_y_m"] = y
        for segment, orientation in orientations.items():
            row[f"{segment}_orientation_deg"] = degrees(orientation)
        for segment, parameters in anthropometry_table.items():
            row[f"{segment}_mass_kg"] = parameters.mass_kg
            row[f"{segment}_mass_fraction_body"] = parameters.mass_fraction_body
            row[f"{segment}_length_m"] = parameters.length_m
            row[f"{segment}_com_fraction"] = parameters.com_fraction
            row[f"{segment}_com_transverse_offset_m"] = (
                parameters.com_transverse_offset_m
            )
            row[f"{segment}_radius_of_gyration_fraction"] = (
                parameters.radius_of_gyration_fraction
            )
            row[f"{segment}_inertia_kg_m2"] = parameters.inertia_kg_m2
            row[f"{segment}_scaling_mode"] = parameters.scaling_mode
            row[f"{segment}_scaling_rule"] = parameters.scaling_rule
            row[f"{segment}_attachment_anterior_offset_m"] = (
                parameters.attachment_anterior_offset_m
            )
            row[f"{segment}_attachment_longitudinal_offset_m"] = (
                parameters.attachment_longitudinal_offset_m
            )
            contribution = contributions[segment]
            row[f"{segment}_com_x_m"] = contribution.position_m[0]
            row[f"{segment}_com_y_m"] = contribution.position_m[1]
            row[f"{segment}_weighted_com_x_kg_m"] = contribution.weighted_position_kg_m[
                0
            ]
            row[f"{segment}_weighted_com_y_kg_m"] = contribution.weighted_position_kg_m[
                1
            ]
        for joint in JOINTS:
            capacity = result.torque_capacities[joint]
            utilization = result.effort_ratios[joint]
            row[f"{joint}_angle_deg"] = joint_angles[joint]
            row[f"{joint}_velocity_deg_s"] = joint_velocities[joint]
            row[f"{joint}_acceleration_deg_s2"] = joint_accelerations[joint]
            row[f"{joint}_torque_Nm"] = result.torques[joint]
            row[f"{joint}_torque_body_mass_normalized_Nm_kg"] = (
                result.torques[joint] / anthro.body_mass
            )
            row[f"{joint}_max_available_Nm"] = capacity.available_torque_Nm
            row[f"{joint}_capacity_base_torque_Nm"] = capacity.base_torque_Nm
            row[f"{joint}_capacity_angle_rad"] = capacity.angle_rad
            row[f"{joint}_capacity_angular_velocity_rad_s"] = (
                capacity.angular_velocity_rad_s
            )
            row[f"{joint}_capacity_angle_factor"] = capacity.angle_factor
            row[f"{joint}_capacity_velocity_factor"] = capacity.velocity_factor
            row[f"{joint}_capacity_regime"] = capacity.regime
            row[f"{joint}_capacity_regime_source"] = capacity.regime_source
            row[f"{joint}_capacity_angle_in_domain"] = capacity.angle_in_domain
            row[f"{joint}_capacity_model"] = capacity.model
            row[f"{joint}_capacity_source"] = capacity.source
            row[f"{joint}_capacity_defined"] = utilization is not None
            row[f"{joint}_utilization_ratio"] = utilization
            row[f"{joint}_utilization_percent"] = (
                None if utilization is None else 100.0 * utilization
            )
            row[f"{joint}_utilization_exceeds_capacity"] = (
                abs(result.torques[joint]) > 0.0
                if utilization is None
                else utilization > 1.0
            )
            # Compatibility alias retained for existing student notebooks.
            row[f"{joint}_effort_percent"] = row[f"{joint}_utilization_percent"]
            row[f"{joint}_power_W"] = result.powers[joint]
            row[f"{joint}_inverse_dynamics_total_Nm"] = result.torque_components[joint][
                "total"
            ]
            row[f"{joint}_mass_acceleration_Nm"] = result.torque_components[joint][
                "mass_acceleration"
            ]
            row[f"{joint}_velocity_dependent_Nm"] = result.torque_components[joint][
                "velocity"
            ]
            row[f"{joint}_gravity_Nm"] = result.torque_components[joint]["gravity"]
            row[f"{joint}_external_contact_effect_Nm"] = result.torque_components[
                joint
            ]["external_contact"]
            row[f"{joint}_inverse_dynamics_reconstruction_residual_Nm"] = (
                result.torque_components[joint]["reconstruction_residual"]
            )
            row[f"{joint}_contact_Nm"] = result.torque_components[joint]["contact"]
            row[f"{joint}_inertial_nonlinear_Nm"] = result.torque_components[joint][
                "inertiels_non_lineaires"
            ]
        rows.append(row)

    summary = condition_summary(condition, rows, actual_backend)
    return rows, summary


def condition_summary(
    condition: Condition, rows: list[dict[str, object]], actual_backend: str
) -> dict[str, object]:
    peaks = {}
    for joint in JOINTS:
        joint_utilizations = [
            float(row[f"{joint}_utilization_percent"])
            for row in rows
            if row[f"{joint}_utilization_percent"] is not None
        ]
        peaks[joint] = {
            "peak_abs_torque_Nm": max(
                abs(float(row[f"{joint}_torque_Nm"])) for row in rows
            ),
            "peak_effort_percent": max(joint_utilizations, default=None),
            "peak_abs_power_W": max(
                abs(float(row[f"{joint}_power_W"])) for row in rows
            ),
        }
    undefined_events = [
        (row, joint)
        for row in rows
        for joint in JOINTS
        if row[f"{joint}_utilization_ratio"] is None
        and abs(float(row[f"{joint}_torque_Nm"])) > 0.0
    ]
    defined_events = [
        (float(row[f"{joint}_utilization_ratio"]), row, joint)
        for row in rows
        for joint in JOINTS
        if row[f"{joint}_utilization_ratio"] is not None
    ]
    if undefined_events:
        limiting_row, limiting_joint = undefined_events[0]
        maximum_ratio = None
        maximum_status = "capacite_active_nulle_hors_domaine"
        exceeds_capacity = True
    elif defined_events:
        maximum_ratio, limiting_row, limiting_joint = max(
            defined_events, key=lambda item: item[0]
        )
        maximum_status = "defini"
        exceeds_capacity = maximum_ratio > 1.0
    else:
        limiting_row = None
        limiting_joint = None
        maximum_ratio = None
        maximum_status = "indisponible"
        exceeds_capacity = False
    mechanical_feasibility = {
        "interpretation": "faisabilite mecanique dans les hypotheses du modele",
        "maximum_utilization_ratio": maximum_ratio,
        "maximum_utilization_percent": (
            None if maximum_ratio is None else 100.0 * maximum_ratio
        ),
        "maximum_status": maximum_status,
        "limiting_joint": limiting_joint,
        "frame": None if limiting_row is None else limiting_row["frame"],
        "time_s": None if limiting_row is None else limiting_row["time_s"],
        "phase": None if limiting_row is None else limiting_row["phase"],
        "exceeds_capacity": exceeds_capacity,
        "undefined_capacity_events": len(undefined_events),
    }
    return {
        "condition": asdict(condition),
        "actual_backend": actual_backend,
        "frames": len(rows),
        "cop_outside_foot_frames": sum(
            1 for row in rows if not bool(row["cop_in_foot"])
        ),
        "zmp_outside_support_frames": sum(
            1 for row in rows if not bool(row["zmp_in_support"])
        ),
        "support_point_outside_functional_frames": sum(
            1 for row in rows if not bool(row["support_point_in_functional_base"])
        ),
        "over_limit_frames": sum(
            1
            for row in rows
            if any(
                bool(row[f"{joint}_utilization_exceeds_capacity"]) for joint in JOINTS
            )
        ),
        "peaks": peaks,
        "mechanical_feasibility": mechanical_feasibility,
    }


def write_csv(
    path: Path, rows: list[dict[str, object]], *, mode: str = "standard"
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exported_rows = csv_export_rows(rows, mode=mode)
    fieldnames = list(exported_rows[0]) if exported_rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(exported_rows)


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
