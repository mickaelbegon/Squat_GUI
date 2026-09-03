"""Pure layout and styling rules used by the Tk plot renderer.

This module deliberately knows nothing about Tk widgets.  It turns scientific
plot metadata into small immutable layout objects so the GUI only has to issue
the corresponding canvas drawing commands.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import isfinite

from .kinematics import PhaseDurations
from .timeline import TimeMode, phase_windows


DEFAULT_CONDITION_COLOR = "#2e7d54"
DEFAULT_PHASE_COLOR = "#6d5ea8"


@dataclass(frozen=True)
class AxisTick:
    """One value and its pixel coordinate on a linear axis."""

    value: float
    coordinate: float


@dataclass(frozen=True)
class TimeMarkerLayout:
    """Horizontal positions of temporal cursor lines."""

    squat_reference_x: float | None
    current_time_x: float


@dataclass(frozen=True)
class PhaseMarkerDataset:
    """The metadata required to lay out phase annotations for one condition."""

    label: str
    durations: PhaseDurations
    color: str | None = None
    row: int | None = None


@dataclass(frozen=True)
class PhaseBoundaryMarker:
    """A vertical phase boundary in canvas coordinates."""

    x: float
    color: str


@dataclass(frozen=True)
class PhaseLabelMarker:
    """A phase name centered over its visible time window."""

    x: float
    text: str
    color: str
    row: int


@dataclass(frozen=True)
class PhaseMarkerLayout:
    """All phase annotations to draw for the visible datasets."""

    boundaries: tuple[PhaseBoundaryMarker, ...]
    labels: tuple[PhaseLabelMarker, ...]


def plot_time_bounds(
    time_groups: Iterable[Iterable[float]],
    mode: TimeMode | str,
    fallback_durations: PhaseDurations,
) -> tuple[float, float]:
    """Return the visible time extent, including the historical fallbacks."""

    mode = TimeMode(mode)
    if mode is TimeMode.NORMALIZED:
        return (0.0, 100.0)
    times = [time for group in time_groups for time in group]
    if not times:
        if mode is TimeMode.ABSOLUTE:
            return (0.0, fallback_durations.total)
        return (
            -fallback_durations.squat_reference_time,
            fallback_durations.total - fallback_durations.squat_reference_time,
        )
    minimum = min(times)
    maximum = max(times)
    if abs(maximum - minimum) < 1e-9:
        return (minimum - 1.0, maximum + 1.0)
    return minimum, maximum


def linear_position(
    value: float,
    pixel_start: float,
    pixel_end: float,
    value_min: float,
    value_max: float,
) -> float:
    """Map a value linearly from data coordinates to canvas coordinates."""

    return pixel_start + (pixel_end - pixel_start) * (value - value_min) / (
        value_max - value_min
    )


def linear_ticks(
    value_min: float,
    value_max: float,
    pixel_start: float,
    pixel_end: float,
    count: int = 5,
) -> tuple[AxisTick, ...]:
    """Return evenly spaced tick values and coordinates for a linear axis."""

    if count < 2:
        raise ValueError("Un axe linéaire requiert au moins deux graduations.")
    return tuple(
        AxisTick(
            value=value_min + index / (count - 1) * (value_max - value_min),
            coordinate=pixel_start + index / (count - 1) * (pixel_end - pixel_start),
        )
        for index in range(count)
    )


def condition_color(index: int, total: int) -> str:
    """Interpolate the comparison palette from red through green to blue."""

    if total <= 1:
        return DEFAULT_CONDITION_COLOR
    fraction = index / max(1, total - 1)
    if fraction <= 0.5:
        local = fraction / 0.5
        start = (198, 51, 44)
        end = (46, 125, 84)
    else:
        local = (fraction - 0.5) / 0.5
        start = (46, 125, 84)
        end = (42, 140, 166)
    rgb = tuple(
        round(start[channel] + local * (end[channel] - start[channel]))
        for channel in range(3)
    )
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def blend_color(color: str, target: str, fraction: float) -> str:
    """Linearly blend two hexadecimal RGB colors."""

    source_hex = color.lstrip("#")
    target_hex = target.lstrip("#")
    source_rgb = tuple(int(source_hex[index : index + 2], 16) for index in (0, 2, 4))
    target_rgb = tuple(int(target_hex[index : index + 2], 16) for index in (0, 2, 4))
    mixed = tuple(
        round(source_rgb[index] + fraction * (target_rgb[index] - source_rgb[index]))
        for index in range(3)
    )
    return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"


def component_color(base_color: str, component: str) -> str:
    """Derive a distinguishable detailed-torque color from the joint color."""

    targets = {
        "termes qdot": ("#111111", 0.18),
        "gravité": ("#ffffff", 0.20),
        "total ID": ("#ffffff", 0.28),
        "contact externe (signé)": ("#ffffff", 0.48),
    }
    if component not in targets:
        return base_color
    target, fraction = targets[component]
    return blend_color(base_color, target, fraction)


def torque_component_styles() -> dict[
    str, tuple[int, tuple[int, ...] | None, str | None]
]:
    """Return canvas width, dash pattern and marker for each torque component."""

    return {
        "M(q) qddot": (2, None, None),
        "termes qdot": (1, (2, 3), None),
        "gravité": (1, (7, 4), None),
        "contact externe (signé)": (1, (7, 3, 2, 3), "triangle"),
        "total ID": (3, None, None),
    }


def value_bounds_with_zero(values: Iterable[float]) -> tuple[float, float]:
    """Return padded finite bounds guaranteed to contain zero."""

    finite_values = [value for value in values if isfinite(value)]
    if not finite_values:
        return (-1.0, 1.0)
    minimum = min(0.0, min(finite_values))
    maximum = max(0.0, max(finite_values))
    if abs(maximum - minimum) < 1e-12:
        return (-1.0, 1.0)
    margin = 0.05 * (maximum - minimum)
    return minimum - margin, maximum + margin


def padded_value_bounds(
    values: Iterable[float],
    additional_values: Iterable[float] = (),
    *,
    include_hundred: bool = False,
) -> tuple[float, float]:
    """Return finite value bounds with the established five-percent padding."""

    finite_values = [
        value for value in (*values, *additional_values) if isfinite(value)
    ]
    if include_hundred:
        finite_values.append(100.0)
    if not finite_values:
        return (-1.0, 1.0)
    minimum = min(finite_values)
    maximum = max(finite_values)
    if abs(maximum - minimum) < 1e-9:
        minimum -= 1.0
        maximum += 1.0
    margin = 0.05 * (maximum - minimum)
    return minimum - margin, maximum + margin


def time_marker_layout(
    *,
    mode: TimeMode | str,
    show_phase_limits: bool,
    current_time: float,
    x0: float,
    x1: float,
    tmin: float,
    tmax: float,
) -> TimeMarkerLayout:
    """Lay out the optional squat reference and clamped animation cursor."""

    mode = TimeMode(mode)
    squat_reference_x = None
    if show_phase_limits and mode is TimeMode.CENTERED and tmin <= 0.0 <= tmax:
        squat_reference_x = linear_position(0.0, x0, x1, tmin, tmax)
    bounded_time = min(tmax, max(tmin, current_time))
    return TimeMarkerLayout(
        squat_reference_x=squat_reference_x,
        current_time_x=linear_position(bounded_time, x0, x1, tmin, tmax),
    )


def phase_marker_layout(
    datasets: Sequence[PhaseMarkerDataset],
    *,
    mode: TimeMode | str,
    show_limits: bool,
    show_names: bool,
    x0: float,
    x1: float,
    tmin: float,
    tmax: float,
    comparison_count: int | None = None,
) -> PhaseMarkerLayout:
    """Lay out visible phase boundaries and names for all conditions."""

    boundaries: list[PhaseBoundaryMarker] = []
    labels: list[PhaseLabelMarker] = []
    multiple_conditions = (comparison_count or len(datasets)) > 1
    for dataset_index, dataset in enumerate(datasets):
        row = dataset.row if dataset.row is not None else dataset_index
        windows = phase_windows(dataset.durations, mode=TimeMode(mode))
        color = dataset.color or DEFAULT_PHASE_COLOR
        if show_limits:
            for boundary in (windows[0].end, windows[1].end):
                if tmin <= boundary <= tmax:
                    boundaries.append(
                        PhaseBoundaryMarker(
                            linear_position(boundary, x0, x1, tmin, tmax),
                            color,
                        )
                    )
        if show_names:
            for window in windows:
                start = max(tmin, window.start)
                end = min(tmax, window.end)
                if end - start <= 1e-9:
                    continue
                text = window.name
                if multiple_conditions:
                    text = f"{dataset.label}: {text}"
                labels.append(
                    PhaseLabelMarker(
                        linear_position((start + end) / 2.0, x0, x1, tmin, tmax),
                        text,
                        color,
                        row,
                    )
                )
    return PhaseMarkerLayout(tuple(boundaries), tuple(labels))


def format_axis_value(value: float) -> str:
    """Format an axis value with magnitude-sensitive precision."""

    absolute_value = abs(value)
    if absolute_value >= 100:
        return f"{value:.0f}"
    if absolute_value >= 10:
        return f"{value:.1f}"
    if absolute_value >= 1:
        return f"{value:.2f}"
    return f"{value:.3f}".rstrip("0").rstrip(".")


def kinematic_unit(source: str, quantity: str) -> str:
    """Return the unit used by one synchronized kinematic panel."""

    if source == "centre de masse":
        return {"position": "m", "vitesse": "m/s", "acceleration": "m/s²"}[quantity]
    return {"position": "deg", "vitesse": "deg/s", "acceleration": "deg/s²"}[quantity]


def plot_unit(choice: str, quantity: str) -> str:
    """Return the unit associated with a main plot choice."""

    if choice == "cinematique articulaire":
        return {"position": "deg", "vitesse": "deg/s", "acceleration": "deg/s2"}[
            quantity
        ]
    if choice == "centre de masse":
        return {"position": "m", "vitesse": "m/s", "acceleration": "m/s2"}[quantity]
    if choice == "force reaction sol":
        return "N"
    if choice in ("couples articulaires", "couples detailles"):
        return "Nm"
    if choice == "couples normalises":
        return "% max"
    return "W"
