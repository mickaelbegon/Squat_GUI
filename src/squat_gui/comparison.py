"""Semantic comparison of controlled squat-condition parameters."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ParameterDifference:
    key: str
    label: str
    reference: str
    compared: str


PARAMETERS = (
    ("subject_profile", "Sujet", "text"),
    ("bar_position", "Position de barre", "text"),
    ("load_percent_bw", "Charge", "% BW"),
    ("shank_percent", "Longueur tibia", "%"),
    ("thigh_percent", "Longueur cuisse", "%"),
    ("trunk_percent", "Longueur tronc", "%"),
    ("anthropometry_mode", "Mode anthropométrique", "text"),
    ("duration_excentrique_s", "Durée excentrique", "s"),
    ("duration_isometrique_s", "Durée isométrique", "s"),
    ("duration_concentrique_s", "Durée concentrique", "s"),
    ("wedge_20_deg", "Wedge 20°", "bool"),
    ("angle_adapt", "Capacité adaptée à l'angle", "bool"),
    ("velocity_adapt", "Capacité adaptée à la vitesse", "bool"),
    (
        "optimize_bar_path_experimental",
        "Stabilisation expérimentale de la barre",
        "bool",
    ),
)


def _format(value: object, unit: str) -> str:
    if unit == "bool":
        return "oui" if bool(value) else "non"
    if unit == "text":
        return str(value)
    number = float(value)
    suffix = f" {unit}" if unit else ""
    return f"{number:.2f}{suffix}"


def _different(reference: object, compared: object) -> bool:
    if isinstance(reference, (int, float)) and isinstance(compared, (int, float)):
        return not isclose(float(reference), float(compared), rel_tol=0.0, abs_tol=1e-9)
    return reference != compared


def semantic_parameter_values(
    settings: Mapping[str, object],
    final_q_deg: Sequence[float],
) -> tuple[tuple[str, str, object, str], ...]:
    values: list[tuple[str, str, object, str]] = []
    defaults: dict[str, object] = {
        "subject_profile": "homme",
        "bar_position": "back",
        "load_percent_bw": 0.0,
        "shank_percent": 0.0,
        "thigh_percent": 0.0,
        "trunk_percent": 0.0,
        "anthropometry_mode": "longueur seule",
        "duration_excentrique_s": settings.get("duration_phase_s", 4.0),
        "duration_isometrique_s": 2.0,
        "duration_concentrique_s": settings.get("duration_phase_s", 4.0),
        "wedge_20_deg": False,
        "angle_adapt": True,
        "velocity_adapt": True,
        "optimize_bar_path_experimental": False,
    }
    for key, label, unit in PARAMETERS:
        values.append((key, label, settings.get(key, defaults[key]), unit))

    torques = dict(settings.get("max_torques", {}))
    for joint in ("cheville", "genou", "hanche"):
        values.append(
            (
                f"max_torques.{joint}",
                f"Couple maximal — {joint}",
                float(torques.get(joint, 0.0)),
                "Nm",
            )
        )

    pose = list(final_q_deg)
    for index, label in enumerate(
        (
            "Orientation jambe basse",
            "Orientation cuisse basse",
            "Orientation tronc basse",
        )
    ):
        values.append(
            (
                f"final_q_deg.{index}",
                label,
                float(pose[index]) if index < len(pose) else 0.0,
                "deg",
            )
        )
    return tuple(values)


def parameter_differences(
    reference_settings: Mapping[str, object],
    reference_final_q_deg: Sequence[float],
    compared_settings: Mapping[str, object],
    compared_final_q_deg: Sequence[float],
) -> tuple[ParameterDifference, ...]:
    reference = semantic_parameter_values(reference_settings, reference_final_q_deg)
    compared = semantic_parameter_values(compared_settings, compared_final_q_deg)
    compared_by_key = {
        key: (label, value, unit) for key, label, value, unit in compared
    }
    differences = []
    for key, label, value, unit in reference:
        _compared_label, compared_value, compared_unit = compared_by_key[key]
        if _different(value, compared_value):
            differences.append(
                ParameterDifference(
                    key=key,
                    label=label,
                    reference=_format(value, unit),
                    compared=_format(compared_value, compared_unit),
                )
            )
    return tuple(differences)


def difference_summary(differences: Sequence[ParameterDifference]) -> str:
    if not differences:
        return "aucun paramètre scientifique modifié"
    labels = [difference.label for difference in differences]
    if len(labels) <= 3:
        return ", ".join(labels)
    return f"{', '.join(labels[:3])} +{len(labels) - 3}"
