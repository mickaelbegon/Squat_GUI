"""Versioned, shared export schema for CSV and Excel outputs."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .workbook_model import (
    COMBINED_SHEET,
    DEFINITIONS_SHEET,
    SUMMARY_SHEET,
    WorkbookContract,
    WorkbookTables,
    build_workbook_tables,
    excel_number_format,
    missing_dictionary_columns,
)
from .xlsx_writers import write_xlsx_artifact, write_xlsx_openpyxl

SCHEMA_VERSION = "2.0.0"
SEGMENTS = ("foot", "shank", "thigh", "trunk", "bar")
JOINTS = ("cheville", "genou", "hanche")
POINTS = ("heel", "toe", "ankle", "knee", "hip", "shoulder", "bar")
ROW_KEYS = ("schema_version", "condition_id", "frame", "time_s")


@dataclass(frozen=True)
class ColumnDefinition:
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
    + (
        "q_shank_deg",
        "q_thigh_deg",
        "q_trunk_deg",
    )
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
    for quantity in (
        "com_x_m",
        "com_y_m",
        "weighted_com_x_kg_m",
        "weighted_com_y_kg_m",
    )
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

# Stable, student-facing CSV contract.  The complete in-memory row remains the
# source for the diagnostic Excel sheets and for the opt-in ``full`` CSV mode.
STANDARD_CSV_COLUMNS = (
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
) + tuple(
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
) + (
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

SUMMARY_COLUMNS = (
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
) + tuple(
    f"{joint}_{quantity}"
    for joint in JOINTS
    for quantity in (
        "peak_abs_torque_Nm",
        "peak_abs_torque_body_mass_normalized_Nm_kg",
        "peak_abs_power_W",
        "peak_utilization_ratio",
        "peak_utilization_percent",
    )
) + (
    "maximum_utilization_ratio",
    "maximum_utilization_percent",
    "limiting_joint",
    "limiting_frame",
    "limiting_time_s",
    "limiting_phase",
    "exceeds_capacity",
    "undefined_capacity_events",
)

DESCRIPTION_OVERRIDES = {
    "schema_version": "Version du contrat d'export Squat GUI.",
    "condition_id": "Identifiant stable de la condition simulée.",
    "frame": "Indice entier de l'échantillon, à partir de zéro.",
    "time_s": "Temps physique écoulé depuis le début de la simulation.",
    "delta_time_s": "Pas de temps local entre échantillons adjacents.",
    "normalized_time_percent": "Temps normalisé sur la durée totale du mouvement.",
    "phase": "Phase du mouvement: excentrique, isométrique ou concentrique.",
    "backend": "Backend ayant effectivement produit les résultats.",
    "frames": "Nombre total d'échantillons de la condition.",
    "support_point_label": "Nature du point d'appui exporté: CoP ou ZMP.",
    "support_point_source": "Méthode exacte utilisée pour calculer le point d'appui.",
    "contact_source": "Méthode effectivement utilisée pour calculer le diagnostic de contact externe.",
    "support_point_x_m": "Abscisse du CoP ou ZMP sur le plan du sol.",
    "torque_body_mass_normalized_Nm_kg": (
        "Moment articulaire divisé par la masse corporelle du sujet."
    ),
    "squat_com_x_m": (
        "Abscisse moyenne du CoM pendant la phase isométrique; à défaut, "
        "valeur à la hauteur minimale du CoM."
    ),
    "squat_cop_x_m": (
        "Abscisse moyenne du point d'appui CoP/ZMP pendant la phase "
        "isométrique; à défaut, valeur à la hauteur minimale du CoM."
    ),
    "zmp_x_min_m": "Abscisse minimale du point d'appui CoP/ZMP sur la trajectoire.",
    "zmp_x_max_m": "Abscisse maximale du point d'appui CoP/ZMP sur la trajectoire.",
    "zmp_excursion_m": "Étendue max-min du point d'appui CoP/ZMP sur la trajectoire.",
    "zmp_outside_support_frames": (
        "Nombre de frames où le point d'appui sort de la base fonctionnelle."
    ),
    "zmp_outside_support_percent": (
        "Pourcentage de frames où le point d'appui sort de la base fonctionnelle."
    ),
    "cop_outside_foot_frames": (
        "Nombre de frames où le point d'appui sort de la base géométrique du pied."
    ),
    "cop_outside_foot_percent": (
        "Pourcentage de frames où le point d'appui sort de la base géométrique du pied."
    ),
    "over_limit_frames": (
        "Nombre de frames où au moins une demande articulaire dépasse la capacité active."
    ),
    "peak_grf_y_N": "Valeur absolue maximale de la force de réaction verticale.",
    "peak_abs_torque_Nm": "Valeur absolue maximale du moment articulaire.",
    "peak_abs_torque_body_mass_normalized_Nm_kg": (
        "Valeur absolue maximale du moment articulaire normalisé par la masse corporelle."
    ),
    "peak_abs_power_W": "Valeur absolue maximale de la puissance articulaire.",
    "peak_utilization_ratio": "Valeur maximale du ratio demande/capacité U.",
    "peak_utilization_percent": "Valeur maximale de U exprimée en pourcentage.",
    "maximum_utilization_ratio": "Maximum de U parmi toutes les articulations et frames.",
    "maximum_utilization_percent": "Maximum de U exprimé en pourcentage.",
    "limiting_joint": "Articulation associée au maximum de U.",
    "limiting_frame": "Frame associée au maximum de U.",
    "limiting_time_s": "Temps associé au maximum de U.",
    "limiting_phase": "Phase associée au maximum de U.",
    "exceeds_capacity": "Vrai si une demande articulaire dépasse la capacité active.",
    "undefined_capacity_events": (
        "Nombre de demandes non nulles pour lesquelles la capacité active est nulle ou indéfinie."
    ),
    "weight_magnitude_N": "Norme du poids total, calculée comme masse totale multipliée par g.",
    "dynamic_moment_z_Nm": "Dérivée du moment cinétique autour de l'axe z global.",
    "max_available_Nm": (
        "Capacité de couple actif selon les facteurs angle et vitesse sélectionnés; "
        "elle n'inclut pas le couple passif."
    ),
    "capacity_base_torque_Nm": (
        "Amplitude de couple de base avant facteurs angle-vitesse; sa provenance "
        "est donnée par torque_preset et les colonnes max_*_Nm de la condition."
    ),
    "capacity_angle_rad": (
        "Angle fourni à Anderson: dorsiflexion/flexion positive; la flexion du "
        "genou Squat_GUI est donc inversée."
    ),
    "capacity_angular_velocity_rad_s": (
        "Vitesse dans la direction d'action du groupe testé; positive concentrique, "
        "négative excentrique."
    ),
    "capacity_angle_factor": "Multiplicateur couple-angle actif d'Anderson.",
    "capacity_velocity_factor": "Multiplicateur couple-vitesse actif d'Anderson.",
    "capacity_regime": "Régime déduit de la vitesse de capacité: concentrique, excentrique ou isométrique.",
    "capacity_regime_source": "Règle utilisée pour relier vitesse, couple, puissance et régime de capacité.",
    "capacity_angle_in_domain": "Vrai si l'angle appartient au lobe positif de la relation active d'Anderson.",
    "capacity_model": "Nom du modèle de capacité effectivement appliqué.",
    "capacity_source": "Référence primaire des paramètres de capacité.",
    "capacity_defined": "Vrai si la capacité active est strictement positive et U calculable.",
    "utilization_ratio": "U = valeur absolue du couple requis divisée par la capacité active disponible.",
    "utilization_percent": "Utilisation demande/capacité U exprimée en pourcentage.",
    "utilization_exceeds_capacity": (
        "Vrai si U > 1, ou si un couple non nul est requis alors que la capacité active est nulle."
    ),
    "effort_percent": "Alias de compatibilité de utilization_percent.",
    "inverse_dynamics_total_Nm": (
        "Couple de dynamique inverse du modèle à pied fixé, reconstruit par "
        "M(q)qddot + termes dépendant de qdot + gravité."
    ),
    "mass_acceleration_Nm": "Terme M(q)qddot projeté dans la convention des moments articulaires.",
    "velocity_dependent_Nm": "Termes de dynamique inverse dépendant de qdot, isolés à qddot nul.",
    "gravity_Nm": "Terme gravitaire de dynamique inverse, évalué à qdot=qddot=0.",
    "external_contact_effect_Nm": (
        "Effet signé du moment de GRF: opposé de la colonne legacy contact_Nm; "
        "hors reconstruction du modèle contraint à pied fixé."
    ),
    "inverse_dynamics_reconstruction_residual_Nm": (
        "Résidu total - [M(q)qddot + vitesse + gravité]; attendu nul à la tolérance numérique."
    ),
    "segment": "Nom canonique du segment ou de la barre.",
    "mass_kg": "Masse effectivement utilisée pour le segment.",
    "mass_fraction_body": "Fraction de la masse corporelle effectivement attribuée au segment; sans objet pour la barre.",
    "length_m": "Longueur effectivement utilisée pour le segment.",
    "com_fraction": "Position longitudinale du CoM en fraction de longueur segmentaire.",
    "com_transverse_offset_m": "Décalage transverse du CoM dans le repère segmentaire.",
    "radius_of_gyration_fraction": "Rayon de giration en fraction de longueur segmentaire.",
    "inertia_kg_m2": "Moment d'inertie planaire effectivement utilisé.",
    "anthropometry_mode": "Mode de sensibilité anthropométrique sélectionné pour la condition.",
    "anthropometry_scaling_rule": "Règle exacte reliant variations de longueur, masses et inerties.",
    "scaling_mode": "Mode anthropométrique appliqué à cette ligne segmentaire.",
    "scaling_rule": "Règle de recalibrage effectivement appliquée à cette ligne segmentaire.",
    "attachment_anterior_offset_m": "Décalage antérieur de l'attache de barre relativement à l'épaule.",
    "attachment_longitudinal_offset_m": "Décalage longitudinal de l'attache de barre relativement à l'épaule.",
}

LEGACY_COLUMNS = {
    "cop_x_m",
    "zmp_posterior_limit_m",
    "zmp_anterior_limit_m",
    "zmp_in_support",
    "cop_in_foot",
    "contact_Nm",
    "inertial_nonlinear_Nm",
    "effort_percent",
}


def _unit(column: str) -> str:
    suffixes = (
        ("_kg_m2", "kg·m²"),
        ("_kg_m", "kg·m"),
        ("_Nm_kg", "N·m/kg"),
        ("_deg_s2", "deg/s²"),
        ("_rad_s", "rad/s"),
        ("_rad", "rad"),
        ("_m_s2", "m/s²"),
        ("_deg_s", "deg/s"),
        ("_m_s", "m/s"),
        ("_Nm", "N·m"),
        ("_N", "N"),
        ("_kg", "kg"),
        ("_deg", "deg"),
        ("_m", "m"),
        ("_W", "W"),
        ("_percent", "%"),
        ("_fraction", "1"),
    )
    for suffix, unit in suffixes:
        if column.endswith(suffix):
            return unit
    return "1"


def _sign_convention(column: str) -> str:
    if "orientation_deg" in column:
        return "positif antihoraire depuis l'axe global +x"
    if any(
        token in column for token in ("_x_", "_vx_", "_ax_", "anterior", "posterior")
    ):
        return "+x vers l'avant; une marge positive indique l'intérieur de la limite"
    if any(token in column for token in ("_y_", "_vy_", "_ay_")):
        return "+y vers le haut"
    if any(
        token in column
        for token in (
            "torque",
            "moment",
            "contact",
            "mass_acceleration",
            "velocity_dependent",
            "gravity_Nm",
            "inverse_dynamics",
        )
    ):
        return "positif selon la convention de dynamique inverse documentée; axe +z hors du plan"
    if "power" in column:
        return "positive pour une puissance articulaire génératrice, négative pour absorbante"
    if "capacity_angular_velocity" in column:
        return "positive concentrique, négative excentrique pour le groupe musculaire modélisé"
    if any(
        token in column for token in ("angle_deg", "velocity_deg", "acceleration_deg")
    ):
        return "angles articulaires relatifs selon la convention cinématique documentée"
    return "sans objet"


def column_definition(column: str) -> ColumnDefinition:
    description = DESCRIPTION_OVERRIDES.get(column)
    if description is None:
        for joint in JOINTS:
            prefix = f"{joint}_"
            if column.startswith(prefix):
                description = DESCRIPTION_OVERRIDES.get(column[len(prefix) :])
                if description is not None:
                    description = f"{joint.capitalize()}: {description}"
                break
    if description is None:
        description = (
            column.replace("_", " ")
            .replace("com", "CoM")
            .replace("grf", "GRF")
            .capitalize()
            + "."
        )
    return ColumnDefinition(
        unit=_unit(column),
        definition=description,
        sign_convention=_sign_convention(column),
        status=(
            "compatibilité legacy"
            if column in LEGACY_COLUMNS
            or any(column.endswith(f"_{legacy}") for legacy in LEGACY_COLUMNS)
            else "canonique"
        ),
    )


def add_schema_version(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    versioned = []
    for source in rows:
        row = {"schema_version": SCHEMA_VERSION}
        row.update(source)
        versioned.append(row)
    return versioned


def csv_export_rows(
    rows: Sequence[Mapping[str, object]], *, mode: str = "standard"
) -> list[dict[str, object]]:
    """Return rows following the stable CSV contract selected by ``mode``.

    ``standard`` is the concise student-facing contract. ``full`` preserves the
    complete diagnostic row, including legacy compatibility columns.
    """
    if mode not in {"standard", "full"}:
        raise ValueError("Le mode CSV doit valoir standard ou full.")
    versioned = add_schema_version(rows)
    if mode == "full":
        return versioned
    return [
        {column: row.get(column) for column in STANDARD_CSV_COLUMNS}
        for row in versioned
    ]


def _workbook_contract() -> WorkbookContract:
    return WorkbookContract(
        schema_version=SCHEMA_VERSION,
        joints=JOINTS,
        standard_csv_columns=STANDARD_CSV_COLUMNS,
        summary_columns=SUMMARY_COLUMNS,
        column_definition=column_definition,
    )


def workbook_tables(
    rows: Sequence[Mapping[str, object]],
) -> WorkbookTables:
    """Build the student workbook through the writer-independent model."""
    return build_workbook_tables(rows, _workbook_contract())


def _write_xlsx_artifact(
    path: str | Path,
    rows: Sequence[Mapping[str, object]],
    *,
    preview_directory: str | Path | None = None,
) -> dict[str, object]:
    """Compatibility wrapper around the Artifact Tool writer."""
    return write_xlsx_artifact(
        path,
        workbook_tables(rows),
        schema_version=SCHEMA_VERSION,
        builder=Path(__file__).with_name("build_workbook.mjs"),
        preview_directory=preview_directory,
    )


def _excel_number_format(column: str) -> str | None:
    """Compatibility alias for the canonical workbook format selector."""
    return excel_number_format(column)


def _write_xlsx_openpyxl(
    path: str | Path,
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Compatibility wrapper around the autonomous openpyxl writer."""
    return write_xlsx_openpyxl(path, workbook_tables(rows))


def write_xlsx(
    path: str | Path,
    rows: Sequence[Mapping[str, object]],
    *,
    preview_directory: str | Path | None = None,
) -> dict[str, object]:
    """Write the canonical workbook, with an autonomous openpyxl fallback."""
    writer = os.environ.get("SQUAT_GUI_XLSX_WRITER", "auto").strip().lower()
    if writer not in {"auto", "artifact-tool", "openpyxl"}:
        raise ValueError(
            "SQUAT_GUI_XLSX_WRITER doit valoir auto, artifact-tool ou openpyxl."
        )
    if writer in {"auto", "artifact-tool"}:
        try:
            return _write_xlsx_artifact(
                path, rows, preview_directory=preview_directory
            )
        except RuntimeError:
            if writer == "artifact-tool":
                raise
    return _write_xlsx_openpyxl(path, rows)
