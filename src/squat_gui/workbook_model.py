"""Canonical, writer-independent model for student Excel workbooks."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import re
from typing import Callable, Mapping, Protocol, Sequence, TypedDict


SUMMARY_SHEET = "Synthèse"
COMBINED_SHEET = "Données combinées"
DEFINITIONS_SHEET = "Définitions"

LONG_TEXT_COLUMNS = frozenset(
    {
        "anthropometry_scaling_rule",
        "scaling_rule",
        "contact_source",
        "support_point_source",
        "capacity_model",
        "capacity_source",
        "definition",
        "sign_convention",
    }
)


class ColumnDescription(Protocol):
    """Subset of a schema column definition needed by the workbook model."""

    unit: str
    definition: str
    sign_convention: str
    status: str


@dataclass(frozen=True)
class WorkbookContract:
    """Export-schema dependencies used to build a canonical workbook."""

    schema_version: str
    joints: tuple[str, ...]
    standard_csv_columns: tuple[str, ...]
    summary_columns: tuple[str, ...]
    column_definition: Callable[[str], ColumnDescription]


class WorkbookTable(TypedDict):
    """One normalized worksheet, independent of the physical XLSX writer."""

    columns: list[str]
    rows: list[list[object | None]]


WorkbookTables = OrderedDict[str, WorkbookTable]


def _add_schema_version(
    rows: Sequence[Mapping[str, object]], schema_version: str
) -> list[dict[str, object]]:
    versioned: list[dict[str, object]] = []
    for source in rows:
        row = {"schema_version": schema_version}
        row.update(source)
        versioned.append(row)
    return versioned


def _number(row: Mapping[str, object], column: str) -> float:
    value = row.get(column)
    if value is None:
        raise ValueError(f"Valeur numérique absente: {column}")
    return float(value)


def _mean(rows: Sequence[Mapping[str, object]], column: str) -> float:
    return sum(_number(row, column) for row in rows) / len(rows)


def _frame_restarts(previous: object, current: object) -> bool:
    """Return whether two adjacent frames reveal a repeated simulation ID."""
    if previous is None or current is None:
        return False
    try:
        return float(current) <= float(previous)
    except (TypeError, ValueError):
        return False


def _simulation_groups(
    rows: Sequence[Mapping[str, object]],
) -> list[tuple[object, list[Mapping[str, object]]]]:
    """Keep contiguous simulations distinct, even when their IDs are repeated."""
    groups: list[tuple[object, list[Mapping[str, object]]]] = []
    current_id: object = None
    current_rows: list[Mapping[str, object]] = []
    previous_frame: object = None
    for row in rows:
        condition_id = row.get("condition_id")
        frame = row.get("frame")
        starts_new = bool(current_rows) and (
            condition_id != current_id or _frame_restarts(previous_frame, frame)
        )
        if starts_new:
            groups.append((current_id, current_rows))
            current_rows = []
        if not current_rows:
            current_id = condition_id
        current_rows.append(row)
        previous_frame = frame
    if current_rows:
        groups.append((current_id, current_rows))
    return groups


def _condition_summary_rows(
    rows: Sequence[Mapping[str, object]], contract: WorkbookContract
) -> list[dict[str, object]]:
    """Build one Excel-ready summary row per simulated condition."""
    summaries: list[dict[str, object]] = []
    for _condition_id, condition_rows in _simulation_groups(rows):
        first = condition_rows[0]
        frame_count = len(condition_rows)
        squat_rows = [row for row in condition_rows if row.get("phase") == "isometrique"]
        if not squat_rows:
            squat_rows = [min(condition_rows, key=lambda row: _number(row, "com_y_m"))]

        support_values = [
            _number(row, "support_point_x_m") for row in condition_rows
        ]
        outside_functional = sum(
            1
            for row in condition_rows
            if not bool(row.get("support_point_in_functional_base"))
        )
        outside_geometric = sum(
            1
            for row in condition_rows
            if not bool(row.get("support_point_in_geometric_base"))
        )
        over_limit = sum(
            1
            for row in condition_rows
            if any(
                bool(row.get(f"{joint}_utilization_exceeds_capacity"))
                for joint in contract.joints
            )
        )

        summary: dict[str, object] = {
            column: first.get(column) for column in contract.summary_columns[:18]
        }
        summary.update(
            {
                "schema_version": contract.schema_version,
                "frames": frame_count,
                "squat_com_x_m": _mean(squat_rows, "com_x_m"),
                "squat_cop_x_m": _mean(squat_rows, "support_point_x_m"),
                "support_point_label": first.get("support_point_label"),
                "zmp_x_min_m": min(support_values),
                "zmp_x_max_m": max(support_values),
                "zmp_excursion_m": max(support_values) - min(support_values),
                "zmp_outside_support_frames": outside_functional,
                "zmp_outside_support_percent": 100.0
                * outside_functional
                / frame_count,
                "cop_outside_foot_frames": outside_geometric,
                "cop_outside_foot_percent": 100.0 * outside_geometric / frame_count,
                "over_limit_frames": over_limit,
                "peak_grf_y_N": max(
                    abs(_number(row, "grf_y_N")) for row in condition_rows
                ),
            }
        )

        undefined_events: list[tuple[Mapping[str, object], str]] = []
        defined_events: list[tuple[float, Mapping[str, object], str]] = []
        for joint in contract.joints:
            utilizations = [
                float(row[f"{joint}_utilization_ratio"])
                for row in condition_rows
                if row.get(f"{joint}_utilization_ratio") is not None
            ]
            for row in condition_rows:
                ratio = row.get(f"{joint}_utilization_ratio")
                torque = _number(row, f"{joint}_torque_Nm")
                if ratio is None and abs(torque) > 0.0:
                    undefined_events.append((row, joint))
                elif ratio is not None:
                    defined_events.append((float(ratio), row, joint))
            summary.update(
                {
                    f"{joint}_peak_abs_torque_Nm": max(
                        abs(_number(row, f"{joint}_torque_Nm"))
                        for row in condition_rows
                    ),
                    f"{joint}_peak_abs_torque_body_mass_normalized_Nm_kg": max(
                        abs(
                            _number(
                                row,
                                f"{joint}_torque_body_mass_normalized_Nm_kg",
                            )
                        )
                        for row in condition_rows
                    ),
                    f"{joint}_peak_abs_power_W": max(
                        abs(_number(row, f"{joint}_power_W"))
                        for row in condition_rows
                    ),
                    f"{joint}_peak_utilization_ratio": (
                        max(utilizations) if utilizations else None
                    ),
                    f"{joint}_peak_utilization_percent": (
                        100.0 * max(utilizations) if utilizations else None
                    ),
                }
            )

        if undefined_events:
            limiting_row, limiting_joint = undefined_events[0]
            maximum_ratio: float | None = None
            exceeds_capacity = True
        elif defined_events:
            maximum_ratio, limiting_row, limiting_joint = max(
                defined_events, key=lambda item: item[0]
            )
            exceeds_capacity = maximum_ratio > 1.0
        else:
            maximum_ratio = None
            limiting_row = None
            limiting_joint = None
            exceeds_capacity = False
        summary.update(
            {
                "maximum_utilization_ratio": maximum_ratio,
                "maximum_utilization_percent": (
                    None if maximum_ratio is None else 100.0 * maximum_ratio
                ),
                "limiting_joint": limiting_joint,
                "limiting_frame": (
                    None if limiting_row is None else limiting_row.get("frame")
                ),
                "limiting_time_s": (
                    None if limiting_row is None else limiting_row.get("time_s")
                ),
                "limiting_phase": (
                    None if limiting_row is None else limiting_row.get("phase")
                ),
                "exceeds_capacity": exceeds_capacity,
                "undefined_capacity_events": len(undefined_events),
            }
        )
        summaries.append(summary)
    return summaries


def _project(
    rows: Sequence[Mapping[str, object]], columns: Sequence[str]
) -> list[list[object | None]]:
    return [[row.get(column) for column in columns] for row in rows]


_INVALID_WORKSHEET_CHARACTERS = re.compile(r'[\\/*?:\[\]<>|"\x00-\x1f]')
_WINDOWS_RESERVED_NAMES = re.compile(
    r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])$", re.IGNORECASE
)


def _worksheet_name(
    condition_id: object,
    used_names: set[str],
    simulation_index: int,
) -> str:
    """Build a safe, unique Excel sheet name of at most 31 characters."""
    raw_name = "" if condition_id is None else str(condition_id)
    base = _INVALID_WORKSHEET_CHARACTERS.sub("_", raw_name)
    base = re.sub(r"\s+", " ", base).strip(" .'_")
    if not base:
        base = f"Simulation {simulation_index}"
    if _WINDOWS_RESERVED_NAMES.fullmatch(base):
        base = f"_{base}"
    base = base[:31].rstrip(" .'") or f"Simulation {simulation_index}"

    candidate = base
    suffix_index = 2
    while candidate.casefold() in used_names:
        suffix = f" ({suffix_index})"
        stem = base[: 31 - len(suffix)].rstrip(" .'")
        candidate = f"{stem}{suffix}"
        suffix_index += 1
    used_names.add(candidate.casefold())
    return candidate


def _ordered_row_columns(
    rows: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    """Return the complete row schema in stable first-seen order."""
    return tuple(dict.fromkeys(column for row in rows for column in row))


def build_workbook_tables(
    rows: Sequence[Mapping[str, object]], contract: WorkbookContract
) -> WorkbookTables:
    """Normalize result rows into the canonical, writer-independent tables."""
    if not rows:
        raise ValueError("L'export requiert au moins une ligne de résultats.")
    versioned = _add_schema_version(rows, contract.schema_version)
    frame_columns = _ordered_row_columns(versioned)
    simulations = _simulation_groups(versioned)
    tables: WorkbookTables = OrderedDict()
    tables[SUMMARY_SHEET] = {
        "columns": list(contract.summary_columns),
        "rows": _project(
            _condition_summary_rows(versioned, contract), contract.summary_columns
        ),
    }
    tables[COMBINED_SHEET] = {
        "columns": list(frame_columns),
        "rows": _project(versioned, frame_columns),
    }

    used_names = {
        SUMMARY_SHEET.casefold(),
        COMBINED_SHEET.casefold(),
        DEFINITIONS_SHEET.casefold(),
    }
    for simulation_index, (condition_id, simulation_rows) in enumerate(
        simulations, start=1
    ):
        sheet_name = _worksheet_name(condition_id, used_names, simulation_index)
        tables[sheet_name] = {
            "columns": list(frame_columns),
            "rows": _project(simulation_rows, frame_columns),
        }

    definitions = []
    for csv_name, columns in (
        ("csv_standard", contract.standard_csv_columns),
        ("csv_full", frame_columns),
    ):
        for column in columns:
            definition = contract.column_definition(column)
            definitions.append(
                [
                    contract.schema_version,
                    csv_name,
                    column,
                    definition.unit,
                    definition.definition,
                    definition.sign_convention,
                    definition.status,
                ]
            )
    for table_name, columns in (
        (SUMMARY_SHEET, contract.summary_columns),
        (COMBINED_SHEET, frame_columns),
        ("Simulation", frame_columns),
    ):
        for column in columns:
            definition = contract.column_definition(column)
            definitions.append(
                [
                    contract.schema_version,
                    table_name,
                    column,
                    definition.unit,
                    definition.definition,
                    definition.sign_convention,
                    definition.status,
                ]
            )
    tables[DEFINITIONS_SHEET] = {
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


def missing_dictionary_columns(tables: Mapping[str, WorkbookTable]) -> set[str]:
    """Return data columns that do not have an entry in the definitions table."""
    defined = {
        row[2] for row in tables[DEFINITIONS_SHEET]["rows"]
    }
    exported = {
        column
        for name, table in tables.items()
        if name != DEFINITIONS_SHEET
        for column in table["columns"]
    }
    return exported - defined


def excel_number_format(column: str) -> str | None:
    """Return the common Excel number format for an exported column."""
    if re.search(r"(^|_)(time|delta_time|duration).*_s$", column):
        return "0.000"
    if re.search(r"(_m|_m_s|_m_s2|_kg_m|_kg_m2|_N|_Nm|_W)$", column):
        return "0.000000"
    if re.search(r"(_deg|_deg_s|_deg_s2|_percent)$", column):
        return "0.000"
    return None
