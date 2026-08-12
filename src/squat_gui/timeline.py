"""Canonical timeline helpers shared by plots, phases and cursor inspection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .kinematics import PhaseDurations


@dataclass(frozen=True)
class PhaseWindow:
    name: str
    start: float
    end: float


class TimeMode(str, Enum):
    ABSOLUTE = "absolu"
    CENTERED = "centré"
    NORMALIZED = "normalisé"


def centered_time(absolute_time: float, durations: PhaseDurations) -> float:
    return absolute_time - durations.squat_reference_time


def plot_time(
    absolute_time: float,
    durations: PhaseDurations,
    *,
    normalized: bool | None = None,
    mode: TimeMode | str | None = None,
) -> float:
    if mode is None:
        mode = TimeMode.NORMALIZED if normalized else TimeMode.CENTERED
    mode = TimeMode(mode)
    if mode is TimeMode.ABSOLUTE:
        return absolute_time
    if mode is TimeMode.CENTERED:
        return centered_time(absolute_time, durations)
    return 0.0 if durations.total <= 0.0 else 100.0 * absolute_time / durations.total


def phase_windows(
    durations: PhaseDurations,
    *,
    normalized: bool | None = None,
    mode: TimeMode | str | None = None,
) -> tuple[PhaseWindow, PhaseWindow, PhaseWindow]:
    boundaries = (
        0.0,
        durations.excentrique,
        durations.excentrique + durations.isometrique,
        durations.total,
    )
    values = tuple(
        plot_time(value, durations, normalized=normalized, mode=mode)
        for value in boundaries
    )
    return (
        PhaseWindow("excentrique", values[0], values[1]),
        PhaseWindow("isometrique", values[1], values[2]),
        PhaseWindow("concentrique", values[2], values[3]),
    )


def nearest_time_index(times: list[float], selected_time: float) -> int:
    if not times:
        raise ValueError("La série temporelle ne peut pas être vide.")
    return min(range(len(times)), key=lambda index: abs(times[index] - selected_time))


def time_axis_label(mode: TimeMode | str) -> str:
    mode = TimeMode(mode)
    return {
        TimeMode.ABSOLUTE: "temps absolu depuis le début (s)",
        TimeMode.CENTERED: "temps centré sur le milieu de la pause (s)",
        TimeMode.NORMALIZED: "temps normalisé du mouvement (%)",
    }[mode]


def time_axis_unit(mode: TimeMode | str) -> str:
    return "%" if TimeMode(mode) is TimeMode.NORMALIZED else "s"
