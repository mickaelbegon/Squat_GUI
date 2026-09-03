"""Typed models and JSON codec for GUI sessions.

This module deliberately knows nothing about Tkinter.  It defines the stable
on-disk contract used by the GUI and keeps compatibility rules for older
settings in one place.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from .dynamics import DynamicsResult
from .kinematics import MotionState
from .timeline import TimeMode

JsonScalar = Union[None, bool, int, float, str]
JsonValue = Union[JsonScalar, list["JsonValue"], dict[str, "JsonValue"]]
SettingsMap = dict[str, object]


@dataclass(frozen=True)
class GuiSettings:
    """Complete snapshot of the settings currently exposed by the GUI."""

    subject_profile: str
    bar_position: str
    load_percent_bw: float
    load_kg: float
    shank_percent: float
    thigh_percent: float
    trunk_percent: float
    anthropometry_mode: str
    duration_excentrique_s: float
    duration_isometrique_s: float
    duration_concentrique_s: float
    temporal_preset: str
    wedge_20_deg: bool
    frame: int
    plot_choice: str
    quantity: str
    synchronized_source: str
    show_joints: dict[str, bool]
    show_com_components: dict[str, bool]
    show_torque_components: dict[str, bool]
    max_torques: dict[str, float]
    torque_preset: str
    show_torque_bounds: bool
    angle_adapt: bool
    velocity_adapt: bool
    optimize_bar_path_experimental: bool
    show_sprite_centers: bool
    show_segment_com: bool
    display_layers: dict[str, bool]
    low_quality_sprites: bool
    time_mode: str
    subplot_mode: bool
    show_phase_limits: bool
    show_phase_names: bool
    final_q_deg: list[float]
    frame_count: int

    def to_mapping(self) -> SettingsMap:
        """Return the historical JSON mapping, including compatibility keys."""
        return {
            "subject_profile": self.subject_profile,
            "bar_position": self.bar_position,
            "load_percent_bw": self.load_percent_bw,
            "load_kg": self.load_kg,
            "shank_percent": self.shank_percent,
            "thigh_percent": self.thigh_percent,
            "trunk_percent": self.trunk_percent,
            "anthropometry_mode": self.anthropometry_mode,
            "duration_excentrique_s": self.duration_excentrique_s,
            "duration_isometrique_s": self.duration_isometrique_s,
            "duration_concentrique_s": self.duration_concentrique_s,
            "temporal_preset": self.temporal_preset,
            "wedge_20_deg": self.wedge_20_deg,
            "frame": self.frame,
            "plot_choice": self.plot_choice,
            "quantity": self.quantity,
            "synchronized_source": self.synchronized_source,
            "show_joints": dict(self.show_joints),
            "show_com_components": dict(self.show_com_components),
            "show_torque_components": dict(self.show_torque_components),
            "max_torques": dict(self.max_torques),
            "torque_preset": self.torque_preset,
            "show_torque_bounds": self.show_torque_bounds,
            "angle_adapt": self.angle_adapt,
            "velocity_adapt": self.velocity_adapt,
            "optimize_bar_path_experimental": self.optimize_bar_path_experimental,
            "show_sprite_centers": self.show_sprite_centers,
            "show_segment_com": self.show_segment_com,
            "display_layers": dict(self.display_layers),
            "low_quality_sprites": self.low_quality_sprites,
            # Kept because version-1 readers used the positive formulation.
            "refined_sprites": not self.low_quality_sprites,
            "time_mode": self.time_mode,
            # Kept because version-1 readers used this boolean.
            "normalize_time": self.time_mode == TimeMode.NORMALIZED.value,
            "subplot_mode": self.subplot_mode,
            "show_phase_limits": self.show_phase_limits,
            "show_phase_names": self.show_phase_names,
            "final_q_deg": list(self.final_q_deg),
            "frame_count": self.frame_count,
        }


@dataclass(frozen=True)
class SettingsReader:
    """Typed access to a current or legacy settings mapping.

    Missing-value defaults stay under the caller's control because several GUI
    options intentionally retain their current value when loading a session.
    Cross-version aliases live here instead of being scattered through Tk code.
    """

    values: Mapping[str, object]

    @classmethod
    def from_object(cls, value: object) -> "SettingsReader":
        if not isinstance(value, Mapping):
            raise ValueError("les réglages doivent être un objet JSON")
        return cls(value)

    def has(self, key: str) -> bool:
        return key in self.values

    def raw(self, key: str, default: object = None) -> object:
        return self.values.get(key, default)

    def text(self, key: str, default: str = "") -> str:
        return str(self.values.get(key, default))

    def number(self, key: str, default: float) -> float:
        return float(self.values.get(key, default))

    def integer(self, key: str, default: int) -> int:
        return int(self.values.get(key, default))

    def flag(self, key: str, default: bool = False) -> bool:
        return bool(self.values.get(key, default))

    def mapping(self, key: str) -> Mapping[str, object]:
        value = self.values.get(key, {})
        if not isinstance(value, Mapping):
            raise ValueError(f"le réglage {key!r} doit être un objet JSON")
        return value

    def load_percent_bw(self, default: float) -> float:
        if self.has("load_percent_bw"):
            return self.number("load_percent_bw", default)
        if self.has("load_kg"):
            return 100.0 * self.number("load_kg", 0.0) / 70.0
        return default

    def phase_durations(self) -> tuple[float, float, float]:
        legacy = self.number("duration_phase_s", 4.0)
        return (
            self.number("duration_excentrique_s", legacy),
            self.number("duration_isometrique_s", 2.0),
            self.number("duration_concentrique_s", legacy),
        )

    def low_quality_sprites(self) -> bool:
        if self.has("low_quality_sprites"):
            return self.flag("low_quality_sprites")
        return not self.flag("refined_sprites", True)

    def time_mode(self) -> str:
        legacy = (
            TimeMode.NORMALIZED.value
            if self.flag("normalize_time", False)
            else TimeMode.CENTERED.value
        )
        requested = self.text("time_mode", legacy)
        if requested in {mode.value for mode in TimeMode}:
            return requested
        return TimeMode.CENTERED.value


@dataclass(frozen=True)
class ComparisonReference:
    label: str
    settings: SettingsMap
    final_q_deg: list[float]

    @classmethod
    def from_object(cls, value: object) -> Optional["ComparisonReference"]:
        if value is None:
            return None
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise ValueError("la référence de comparaison doit être un objet JSON")
        settings = SettingsReader.from_object(value.get("settings", {}))
        return cls(
            label=str(value.get("label", "")),
            settings=dict(settings.values),
            final_q_deg=_float_list(value.get("final_q_deg", [])),
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "label": self.label,
            "settings": dict(self.settings),
            "final_q_deg": list(self.final_q_deg),
        }


@dataclass
class SavedCondition(Mapping[str, object]):
    """A recorded simulation with typed runtime and persistence fields.

    Mapping compatibility is intentional: extensions and older tests that read
    condition records as dictionaries keep working during the refactor.
    """

    label: str
    settings: SettingsMap
    final_q_deg: list[float]
    states: list[MotionState]
    results: list[DynamicsResult]
    comparison_reference: Optional[ComparisonReference] = None
    difference_summary: str = "référence indépendante"

    _KEYS = (
        "label",
        "settings",
        "final_q_deg",
        "states",
        "results",
        "comparison_reference",
        "difference_summary",
    )

    def __getitem__(self, key: str) -> object:
        if key not in self._KEYS:
            raise KeyError(key)
        value = getattr(self, key)
        if key == "comparison_reference" and value is not None:
            return value.to_mapping()
        return value

    def __iter__(self) -> Iterator[str]:
        return iter(self._KEYS)

    def __len__(self) -> int:
        return len(self._KEYS)


@dataclass(frozen=True)
class StoredCondition:
    """Serializable subset of :class:`SavedCondition`."""

    iid: str
    label: str
    settings: SettingsMap
    final_q_deg: list[float]
    comparison_reference: Optional[ComparisonReference] = None

    @classmethod
    def from_mapping(cls, value: object) -> "StoredCondition":
        if not isinstance(value, Mapping):
            raise ValueError("chaque condition doit être un objet JSON")
        settings = SettingsReader.from_object(value.get("settings", {}))
        return cls(
            iid=str(value.get("iid", "")),
            label=str(value.get("label", "")),
            settings=dict(settings.values),
            final_q_deg=_float_list(value.get("final_q_deg", [])),
            comparison_reference=ComparisonReference.from_object(
                value.get("comparison_reference")
            ),
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "iid": self.iid,
            "label": self.label,
            "settings": dict(self.settings),
            "final_q_deg": list(self.final_q_deg),
            "comparison_reference": (
                self.comparison_reference.to_mapping()
                if self.comparison_reference is not None
                else None
            ),
        }


@dataclass(frozen=True)
class SessionDocument:
    settings: SettingsMap
    conditions: list[StoredCondition]
    version: int = 2

    @classmethod
    def from_mapping(cls, value: object) -> "SessionDocument":
        if not isinstance(value, Mapping):
            raise ValueError("la session doit être un objet JSON")
        settings = SettingsReader.from_object(value.get("settings", {}))
        raw_conditions = value.get("conditions", [])
        if not isinstance(raw_conditions, list):
            raise ValueError("le champ conditions doit être une liste JSON")
        return cls(
            version=int(value.get("version", 1)),
            settings=dict(settings.values),
            conditions=[
                StoredCondition.from_mapping(condition)
                for condition in raw_conditions
            ],
        )

    @classmethod
    def from_runtime(
        cls,
        settings: Mapping[str, object],
        conditions: Mapping[str, Mapping[str, object]],
    ) -> "SessionDocument":
        stored: list[StoredCondition] = []
        for iid, condition in conditions.items():
            stored.append(
                StoredCondition(
                    iid=iid,
                    label=str(condition["label"]),
                    settings=dict(_mapping_value(condition["settings"], "settings")),
                    final_q_deg=_float_list(condition["final_q_deg"]),
                    comparison_reference=ComparisonReference.from_object(
                        condition.get("comparison_reference")
                    ),
                )
            )
        return cls(settings=dict(settings), conditions=stored)

    def to_mapping(self) -> dict[str, object]:
        return {
            "version": self.version,
            "settings": dict(self.settings),
            "conditions": [condition.to_mapping() for condition in self.conditions],
        }


class SessionJsonCodec:
    """Read and write the stable version-2 session JSON format."""

    @staticmethod
    def dumps(document: SessionDocument) -> str:
        return json.dumps(document.to_mapping(), indent=2, ensure_ascii=False)

    @classmethod
    def write(cls, path: Union[str, Path], document: SessionDocument) -> None:
        Path(path).write_text(cls.dumps(document), encoding="utf-8")

    @staticmethod
    def loads(text: str) -> SessionDocument:
        return SessionDocument.from_mapping(json.loads(text))

    @classmethod
    def read(cls, path: Union[str, Path]) -> SessionDocument:
        return cls.loads(Path(path).read_text(encoding="utf-8"))


def _mapping_value(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"le champ {field_name} doit être un objet JSON")
    return value


def _float_list(value: object) -> list[float]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("les angles finaux doivent être une liste JSON")
    return [float(item) for item in value]
