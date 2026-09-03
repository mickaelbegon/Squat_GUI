"""Pure conversion of simulated states into the public export records.

The simulation service owns orchestration (model creation, optional biorbd and
optimization).  This module owns only the deterministic export projection so
CSV, JSON and XLSX consumers share one stable record shape.
"""

from __future__ import annotations

from dataclasses import asdict
from math import degrees
from typing import Protocol, Sequence

from .anthropometry import Anthropometry
from .dynamics import DynamicsResult, force_balance
from .export_schema import JOINTS, SCHEMA_VERSION
from .kinematics import MotionState, joint_values_from_segment_values, segment_orientations
from .observables import (
    com_contributions,
    frame_info,
    joint_coordinates,
    segment_anthropometry,
    support_margins,
)

ExportRow = dict[str, object]


class ExportCondition(Protocol):
    """Subset of a condition required to build stable export records."""

    condition_id: str
    subject_profile: str
    bar_position: str
    wedge_20_deg: bool
    load_percent_bw: float
    load_kg: float
    shank_percent: float
    thigh_percent: float
    trunk_percent: float
    anthropometry_mode: str
    duration_excentrique_s: float
    duration_isometrique_s: float
    duration_concentrique_s: float
    total_duration_s: float
    frames: int
    torque_preset: str
    max_torques: dict[str, float]
    angle_adapt: bool
    velocity_adapt: bool
    optimize_bar_path_experimental: bool


class ExportOptimization(Protocol):
    applied: bool
    message: str


def build_export_rows(
    condition: ExportCondition,
    anthro: Anthropometry,
    states: Sequence[MotionState],
    results: Sequence[DynamicsResult],
    optimization: ExportOptimization | None = None,
) -> list[ExportRow]:
    """Project one simulation into its unchanged, schema-versioned frame rows."""

    anthropometry_table = segment_anthropometry(anthro)
    rows: list[ExportRow] = []
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
        row: ExportRow = {
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
            "bar_path_optimization_requested": condition.optimize_bar_path_experimental,
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
    return rows


def condition_summary(
    condition: object,
    rows: Sequence[ExportRow],
    actual_backend: str,
) -> dict[str, object]:
    """Summarize the mechanical and numerical outcome of one condition."""

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
            1
            for row in rows
            if not bool(row["support_point_in_functional_base"])
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
