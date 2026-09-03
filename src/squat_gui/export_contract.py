"""Static, versioned column contracts for Squat GUI exports.

This module deliberately contains no row processing or file writing.  Keeping
the public column lists together makes an export-format change easy to review.
"""

from __future__ import annotations

from dataclasses import dataclass


SCHEMA_VERSION = "2.0.0"
SEGMENTS = ("foot", "shank", "thigh", "trunk", "bar")
JOINTS = ("cheville", "genou", "hanche")
POINTS = ("heel", "toe", "ankle", "knee", "hip", "shoulder", "bar")
ROW_KEYS = ("schema_version", "condition_id", "frame", "time_s")


@dataclass(frozen=True)
class ColumnDefinition:
    """Human-readable metadata attached to an exported column."""

    unit: str
    definition: str
    sign_convention: str = "sans objet"
    status: str = "canonique"


CONDITION_COLUMNS = (
    "schema_version",
    "condition_id",
    "backend",
    "subject_profile",
    "bar_position",
    "wedge_20_deg",
    "load_percent_bw",
    "load_kg",
    "body_mass_kg",
    "total_mass_kg",
    "height_m",
    "shank_percent",
    "thigh_percent",
    "trunk_percent",
    "anthropometry_mode",
    "anthropometry_scaling_rule",
    "duration_excentrique_s",
    "duration_isometrique_s",
    "duration_concentrique_s",
    "total_duration_s",
    "frames",
    "torque_preset",
    "angle_adapt",
    "velocity_adapt",
    "max_cheville_Nm",
    "max_genou_Nm",
    "max_hanche_Nm",
)
TIME_COLUMNS = ROW_KEYS + (
    "delta_time_s",
    "normalized_time_percent",
    "phase",
    "backend",
)
COORDINATE_COLUMNS = ROW_KEYS + tuple(
    f"{point}_{axis}_m" for point in POINTS for axis in ("x", "y")
)
ORIENTATION_COLUMNS = ROW_KEYS + tuple(
    f"{segment}_orientation_deg" for segment in ("foot", "shank", "thigh", "trunk")
)
KINEMATIC_COLUMNS = (
    ROW_KEYS
    + ("q_shank_deg", "q_thigh_deg", "q_trunk_deg")
    + tuple(
        f"{joint}_{quantity}{unit}"
        for joint in JOINTS
        for quantity, unit in (
            ("angle", "_deg"),
            ("velocity", "_deg_s"),
            ("acceleration", "_deg_s2"),
        )
    )
)
ANTHROPOMETRY_COLUMNS = ("schema_version", "condition_id", "segment") + (
    "mass_kg",
    "mass_fraction_body",
    "length_m",
    "com_fraction",
    "com_transverse_offset_m",
    "radius_of_gyration_fraction",
    "inertia_kg_m2",
    "scaling_mode",
    "scaling_rule",
    "attachment_anterior_offset_m",
    "attachment_longitudinal_offset_m",
)
SEGMENT_COM_COLUMNS = ROW_KEYS + tuple(
    f"{segment}_{quantity}"
    for segment in SEGMENTS
    for quantity in ("com_x_m", "com_y_m", "weighted_com_x_kg_m", "weighted_com_y_kg_m")
)
GLOBAL_COM_COLUMNS = ROW_KEYS + (
    "total_mass_kg",
    "com_x_m",
    "com_y_m",
    "com_vx_m_s",
    "com_vy_m_s",
    "com_ax_m_s2",
    "com_ay_m_s2",
)
FORCE_COLUMNS = ROW_KEYS + (
    "grf_x_N",
    "grf_y_N",
    "weight_magnitude_N",
    "weight_x_N",
    "weight_y_N",
    "force_balance_residual_x_N",
    "force_balance_residual_y_N",
    "support_point_x_m",
    "support_point_label",
    "support_point_source",
    "geometric_support_posterior_m",
    "geometric_support_anterior_m",
    "functional_support_posterior_m",
    "functional_support_anterior_m",
    "support_point_geometric_posterior_margin_m",
    "support_point_geometric_anterior_margin_m",
    "support_point_functional_posterior_margin_m",
    "support_point_functional_anterior_margin_m",
    "support_point_in_geometric_base",
    "support_point_in_functional_base",
    "com_projection_geometric_posterior_margin_m",
    "com_projection_geometric_anterior_margin_m",
    "com_projection_in_geometric_base",
)
DYNAMIC_COLUMNS = (
    ROW_KEYS
    + ("dynamic_moment_z_Nm", "contact_source")
    + tuple(
        f"{joint}_{quantity}"
        for joint in JOINTS
        for quantity in (
            "torque_Nm",
            "torque_body_mass_normalized_Nm_kg",
            "max_available_Nm",
            "capacity_base_torque_Nm",
            "capacity_angle_rad",
            "capacity_angular_velocity_rad_s",
            "capacity_angle_factor",
            "capacity_velocity_factor",
            "capacity_regime",
            "capacity_regime_source",
            "capacity_angle_in_domain",
            "capacity_model",
            "capacity_source",
            "capacity_defined",
            "utilization_ratio",
            "utilization_percent",
            "utilization_exceeds_capacity",
            "effort_percent",
            "power_W",
            "inverse_dynamics_total_Nm",
            "mass_acceleration_Nm",
            "velocity_dependent_Nm",
            "gravity_Nm",
            "external_contact_effect_Nm",
            "inverse_dynamics_reconstruction_residual_Nm",
            "contact_Nm",
            "inertial_nonlinear_Nm",
        )
    )
)

# Stable, student-facing CSV contract. The complete row remains available from
# the opt-in ``full`` mode for diagnostics and backwards compatibility.
STANDARD_CSV_COLUMNS = (
    (
        "schema_version",
        "condition_id",
        "subject_profile",
        "bar_position",
        "load_percent_bw",
        "wedge_20_deg",
        "shank_percent",
        "thigh_percent",
        "trunk_percent",
        "duration_excentrique_s",
        "duration_isometrique_s",
        "duration_concentrique_s",
        "frames",
        "backend",
        "torque_preset",
        "angle_adapt",
        "velocity_adapt",
        "anthropometry_mode",
        "frame",
        "time_s",
        "delta_time_s",
        "normalized_time_percent",
        "phase",
        "q_shank_deg",
        "q_thigh_deg",
        "q_trunk_deg",
    )
    + tuple(
        f"{joint}_{quantity}"
        for joint in JOINTS
        for quantity in (
            "angle_deg",
            "velocity_deg_s",
            "acceleration_deg_s2",
            "torque_Nm",
            "torque_body_mass_normalized_Nm_kg",
            "inverse_dynamics_total_Nm",
            "external_contact_effect_Nm",
            "inertial_nonlinear_Nm",
            "power_W",
            "utilization_ratio",
            "utilization_percent",
        )
    )
    + (
        "com_x_m",
        "com_y_m",
        "support_point_x_m",
        "support_point_label",
        "support_point_source",
        "functional_support_posterior_m",
        "functional_support_anterior_m",
        "support_point_in_geometric_base",
        "support_point_in_functional_base",
        "grf_y_N",
    )
)

SUMMARY_COLUMNS = (
    (
        "schema_version",
        "condition_id",
        "subject_profile",
        "bar_position",
        "load_percent_bw",
        "wedge_20_deg",
        "shank_percent",
        "thigh_percent",
        "trunk_percent",
        "duration_excentrique_s",
        "duration_isometrique_s",
        "duration_concentrique_s",
        "frames",
        "backend",
        "torque_preset",
        "angle_adapt",
        "velocity_adapt",
        "anthropometry_mode",
        "squat_com_x_m",
        "squat_cop_x_m",
        "support_point_label",
        "zmp_x_min_m",
        "zmp_x_max_m",
        "zmp_excursion_m",
        "zmp_outside_support_frames",
        "zmp_outside_support_percent",
        "cop_outside_foot_frames",
        "cop_outside_foot_percent",
        "over_limit_frames",
        "peak_grf_y_N",
    )
    + tuple(
        f"{joint}_{quantity}"
        for joint in JOINTS
        for quantity in (
            "peak_abs_torque_Nm",
            "peak_abs_torque_body_mass_normalized_Nm_kg",
            "peak_abs_power_W",
            "peak_utilization_ratio",
            "peak_utilization_percent",
        )
    )
    + (
        "maximum_utilization_ratio",
        "maximum_utilization_percent",
        "limiting_joint",
        "limiting_frame",
        "limiting_time_s",
        "limiting_phase",
        "exceeds_capacity",
        "undefined_capacity_events",
    )
)
