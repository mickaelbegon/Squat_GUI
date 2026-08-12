"""Versioned, shared export schema for CSV and Excel outputs."""

from __future__ import annotations

from collections import OrderedDict
from copy import copy
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Iterable, Mapping, Sequence

SCHEMA_VERSION = "1.4.0"
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

TABLE_COLUMNS = OrderedDict(
    (
        ("conditions", CONDITION_COLUMNS),
        ("temps", TIME_COLUMNS),
        ("coordonnees", COORDINATE_COLUMNS),
        ("orientations", ORIENTATION_COLUMNS),
        ("cinematique_articulaire", KINEMATIC_COLUMNS),
        ("anthropometrie", ANTHROPOMETRY_COLUMNS),
        ("com_segmentaires", SEGMENT_COM_COLUMNS),
        ("com_global", GLOBAL_COM_COLUMNS),
        ("forces_equilibre", FORCE_COLUMNS),
        ("dynamique", DYNAMIC_COLUMNS),
    )
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
    "support_point_label": "Nature du point d'appui exporté: CoP ou ZMP.",
    "support_point_source": "Méthode exacte utilisée pour calculer le point d'appui.",
    "contact_source": "Méthode effectivement utilisée pour calculer le diagnostic de contact externe.",
    "support_point_x_m": "Abscisse du CoP ou ZMP sur le plan du sol.",
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


def _project(
    rows: Sequence[Mapping[str, object]], columns: Sequence[str]
) -> list[list[object | None]]:
    return [[row.get(column) for column in columns] for row in rows]


def _unique_conditions(
    rows: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    unique: OrderedDict[object, Mapping[str, object]] = OrderedDict()
    for row in rows:
        unique.setdefault(row.get("condition_id"), row)
    return list(unique.values())


def _anthropometry_rows(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    result = []
    for row in _unique_conditions(rows):
        for segment in SEGMENTS:
            result.append(
                {
                    "schema_version": row.get("schema_version"),
                    "condition_id": row.get("condition_id"),
                    "segment": segment,
                    **{
                        column: row.get(f"{segment}_{column}")
                        for column in ANTHROPOMETRY_COLUMNS[3:]
                    },
                }
            )
    return result


def workbook_tables(
    rows: Sequence[Mapping[str, object]],
) -> OrderedDict[str, dict[str, object]]:
    """Split canonical wide rows into machine-readable metric families."""
    if not rows:
        raise ValueError("L'export requiert au moins une ligne de résultats.")
    versioned = add_schema_version(rows)
    tables: OrderedDict[str, dict[str, object]] = OrderedDict()
    for name, columns in TABLE_COLUMNS.items():
        source_rows: Sequence[Mapping[str, object]]
        if name == "conditions":
            source_rows = _unique_conditions(versioned)
        elif name == "anthropometrie":
            source_rows = _anthropometry_rows(versioned)
        else:
            source_rows = versioned
        tables[name] = {
            "columns": list(columns),
            "rows": _project(source_rows, columns),
        }

    definitions = []
    for column in versioned[0]:
        definition = column_definition(column)
        definitions.append(
            [
                SCHEMA_VERSION,
                "csv_large",
                column,
                definition.unit,
                definition.definition,
                definition.sign_convention,
                definition.status,
            ]
        )
    for table_name, columns in TABLE_COLUMNS.items():
        for column in columns:
            definition = column_definition(column)
            definitions.append(
                [
                    SCHEMA_VERSION,
                    table_name,
                    column,
                    definition.unit,
                    definition.definition,
                    definition.sign_convention,
                    definition.status,
                ]
            )
    tables["definitions"] = {
        "columns": [
            "schema_version",
            "table",
            "column",
            "unit",
            "definition",
            "sign_convention",
            "status",
        ],
        "rows": definitions,
    }
    return tables


def missing_dictionary_columns(tables: Mapping[str, Mapping[str, object]]) -> set[str]:
    """Return data columns that do not have an entry in the definitions table."""
    defined = {row[2] for row in tables["definitions"]["rows"]}  # type: ignore[index]
    exported = {
        column
        for name, table in tables.items()
        if name != "definitions"
        for column in table["columns"]  # type: ignore[index]
    }
    return exported - defined


def _artifact_runtime() -> tuple[Path, Path]:
    """Locate Node and the artifact-tool modules without hard-coding a workstation."""
    node_candidates = [
        Path(value)
        for value in (os.environ.get("SQUAT_GUI_NODE"), shutil.which("node"))
        if value
    ]
    codex_dependencies = (
        Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node"
    )
    node_candidates.append(codex_dependencies / "bin/node")
    module_candidates = [
        Path(value) for value in (os.environ.get("SQUAT_GUI_NODE_MODULES"),) if value
    ]
    module_candidates.extend(
        (
            Path.cwd() / "node_modules",
            codex_dependencies / "node_modules",
        )
    )
    node = next(
        (candidate for candidate in node_candidates if candidate.is_file()), None
    )
    modules = next(
        (
            candidate
            for candidate in module_candidates
            if (candidate / "@oai/artifact-tool").exists()
        ),
        None,
    )
    if node is None or modules is None:
        raise RuntimeError(
            "Export Excel indisponible: Node.js et @oai/artifact-tool sont requis. "
            "Définir SQUAT_GUI_NODE et SQUAT_GUI_NODE_MODULES si nécessaire."
        )
    return node, modules


def _write_xlsx_artifact(
    path: str | Path,
    rows: Sequence[Mapping[str, object]],
    *,
    preview_directory: str | Path | None = None,
) -> dict[str, object]:
    """Write the canonical tables with Artifact Tool when its runtime exists."""
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    node, modules = _artifact_runtime()
    payload = {"schema_version": SCHEMA_VERSION, "tables": workbook_tables(rows)}
    builder = Path(__file__).with_name("build_workbook.mjs")
    if not builder.exists():
        raise RuntimeError(f"Constructeur de classeur introuvable: {builder}")

    with tempfile.TemporaryDirectory(prefix="squat-gui-xlsx-") as temporary:
        work = Path(temporary)
        local_builder = work / builder.name
        shutil.copy2(builder, local_builder)
        (work / "node_modules").symlink_to(modules, target_is_directory=True)
        payload_path = work / "payload.json"
        payload_path.write_text(
            json.dumps(payload, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
        report_path = work / "report.json"
        command = [
            str(node),
            str(local_builder),
            str(payload_path),
            str(output),
            str(report_path),
        ]
        if preview_directory is not None:
            command.append(str(Path(preview_directory).expanduser().resolve()))
        completed = subprocess.run(
            command,
            cwd=work,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"Échec de l'export Excel: {detail}")
        if not report_path.exists():
            raise RuntimeError("Échec de l'export Excel: rapport de validation absent.")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["writer"] = "artifact-tool"
        return report


def _excel_number_format(column: str) -> str | None:
    if re.search(r"(^|_)(time|delta_time|duration).*_s$", column):
        return "0.000"
    if re.search(r"(_m|_m_s|_m_s2|_kg_m|_kg_m2|_N|_Nm|_W)$", column):
        return "0.000000"
    if re.search(r"(_deg|_deg_s|_deg_s2|_percent)$", column):
        return "0.000"
    return None


def _write_xlsx_openpyxl(
    path: str | Path,
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Write the canonical workbook without an external Node.js runtime."""
    try:
        from openpyxl import Workbook, load_workbook
        from openpyxl.styles import Alignment, Font, PatternFill, Side
        from openpyxl.worksheet.table import Table, TableStyleInfo
        from openpyxl.utils import get_column_letter
    except ImportError as error:
        raise RuntimeError(
            "Export Excel indisponible: installer openpyxl>=3.1 ou fournir "
            "Node.js avec @oai/artifact-tool."
        ) from error

    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    tables = workbook_tables(rows)
    workbook = Workbook()
    workbook.remove(workbook.active)
    header_fill = PatternFill("solid", fgColor="245B4A")
    alternate_fill = PatternFill("solid", fgColor="EAF2EE")
    header_font = Font(color="FFFFFF", bold=True)
    subtle_border = Side(style="thin", color="D8E1DD")
    long_text_columns = {
        "anthropometry_scaling_rule",
        "scaling_rule",
        "capacity_model",
        "capacity_source",
        "definition",
        "sign_convention",
    }

    for sheet_index, (name, table) in enumerate(tables.items(), start=1):
        sheet = workbook.create_sheet(name)
        sheet.sheet_view.showGridLines = False
        columns = list(table["columns"])
        table_rows = list(table["rows"])
        sheet.append(columns)
        for values in table_rows:
            sheet.append(list(values))

        sheet.row_dimensions[1].height = 34
        for cell in sheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(
                horizontal="left", vertical="center", wrap_text=True
            )

        for row_index in range(2, sheet.max_row + 1):
            for cell in sheet[row_index]:
                border = copy(cell.border)
                border.bottom = subtle_border
                cell.border = border
                if row_index % 2 == 0:
                    cell.fill = alternate_fill

        for column_index, column in enumerate(columns, start=1):
            letter = get_column_letter(column_index)
            number_format = _excel_number_format(column)
            is_long_text = column in long_text_columns
            maximum_width = 48 if name == "definitions" or is_long_text else 24
            measured_width = max(
                len(str(sheet.cell(row=row_index, column=column_index).value or ""))
                for row_index in range(1, sheet.max_row + 1)
            )
            sheet.column_dimensions[letter].width = min(
                max(measured_width + 2, 11), maximum_width
            )
            for row_index in range(2, sheet.max_row + 1):
                cell = sheet.cell(row=row_index, column=column_index)
                if number_format and isinstance(cell.value, (int, float)):
                    cell.number_format = number_format
                if is_long_text:
                    cell.alignment = Alignment(vertical="top", wrap_text=True)

        sheet.freeze_panes = "D2" if name == "anthropometrie" else "C2"
        if sheet.max_row >= 2:
            reference = f"A1:{get_column_letter(sheet.max_column)}{sheet.max_row}"
            excel_table = Table(
                displayName=f"SquatTable{sheet_index}", ref=reference
            )
            excel_table.tableStyleInfo = TableStyleInfo(
                name="TableStyleMedium2",
                showFirstColumn=False,
                showLastColumn=False,
                showRowStripes=True,
                showColumnStripes=False,
            )
            sheet.add_table(excel_table)

    workbook.save(output)
    check = load_workbook(output, read_only=False, data_only=False)
    try:
        formula_errors = [
            cell.value
            for sheet in check.worksheets
            for row in sheet.iter_rows()
            for cell in row
            if isinstance(cell.value, str)
            and cell.value in {"#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A"}
        ]
        sheets = check.sheetnames
    finally:
        check.close()
    return {
        "sheets": sheets,
        "formulaErrors": formula_errors,
        "writer": "openpyxl",
    }


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
