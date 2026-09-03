"""Typed, Tk-independent preparation of plot and animation data."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from .anthropometry import Anthropometry
from .dynamics import DynamicsResult
from .kinematics import MotionState, PhaseDurations
from .timeline import TimeMode, nearest_time_index


@dataclass(frozen=True)
class PlotDataset(Mapping[str, object]):
    """One simulation ready to be consumed by the GUI renderers.

    Mapping compatibility keeps the transitional public surface used by a few
    extensions and tests while application code can rely on typed attributes.
    """

    label: str
    states: list[MotionState]
    results: list[DynamicsResult]
    color: str | None
    anthro: Anthropometry
    refined_sprites: bool
    durations: PhaseDurations

    _KEYS = (
        "label",
        "states",
        "results",
        "color",
        "anthro",
        "refined_sprites",
        "durations",
    )

    def __getitem__(self, key: str) -> object:
        if key not in self._KEYS:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter(self._KEYS)

    def __len__(self) -> int:
        return len(self._KEYS)


@dataclass(frozen=True)
class PlotSample:
    """A dataset paired with the state nearest to the displayed time."""

    dataset: PlotDataset
    state: MotionState
    result: DynamicsResult

    @property
    def label(self) -> str:
        return self.dataset.label

    @property
    def color(self) -> str | None:
        return self.dataset.color

    @property
    def states(self) -> list[MotionState]:
        return self.dataset.states

    @property
    def anthro(self) -> Anthropometry:
        return self.dataset.anthro

    @property
    def refined_sprites(self) -> bool:
        return self.dataset.refined_sprites


def select_plot_datasets(
    current: PlotDataset | None,
    saved_by_id: Mapping[str, PlotDataset],
    selected_ids: Iterable[str],
) -> list[PlotDataset]:
    """Return selected saved datasets in UI order, or the current one."""

    selected = [saved_by_id[iid] for iid in selected_ids if iid in saved_by_id]
    if selected:
        return selected
    if current is None:
        raise ValueError("La simulation courante est requise sans sélection.")
    return [current]


def centered_times(states: Sequence[MotionState]) -> list[float]:
    """Express state times relative to the middle of the deep-squat pause."""

    if not states:
        return []
    eccentric_times = [
        state.time for state in states if state.phase == "excentrique"
    ]
    isometric_times = [
        state.time for state in states if state.phase == "isometrique"
    ]
    squat_start = eccentric_times[-1] if eccentric_times else states[0].time
    squat_time = (
        (squat_start + isometric_times[-1]) / 2.0
        if isometric_times
        else squat_start
    )
    return [state.time - squat_time for state in states]


def plot_times(states: Sequence[MotionState], mode: TimeMode | str) -> list[float]:
    """Return the plot abscissa for every state in the requested time mode."""

    if not states:
        return []
    mode = TimeMode(mode)
    if mode is TimeMode.ABSOLUTE:
        return [state.time for state in states]
    if mode is TimeMode.CENTERED:
        return centered_times(states)
    duration = states[-1].time - states[0].time
    if duration <= 1e-9:
        return [0.0 for _state in states]
    return [100.0 * (state.time - states[0].time) / duration for state in states]


def sample_dataset_at_time(
    dataset: PlotDataset,
    selected_time: float,
    mode: TimeMode | str,
) -> PlotSample:
    """Select the closest synchronized state/result pair from a dataset."""

    times = plot_times(dataset.states, mode)
    if not times:
        raise ValueError("La simulation ne contient aucun échantillon.")
    if len(dataset.results) < len(dataset.states):
        raise ValueError("Les états et résultats de la simulation sont désynchronisés.")
    index = nearest_time_index(times, selected_time)
    return PlotSample(dataset, dataset.states[index], dataset.results[index])


def current_plot_time(
    datasets: Sequence[PlotDataset],
    mode: TimeMode | str,
    frame: int,
    frame_count: int,
) -> float:
    """Map the shared animation frame to the full visible plot time span."""

    all_times = [
        time
        for dataset in datasets
        for time in plot_times(dataset.states, mode)
    ]
    if not all_times:
        return 0.0
    tmin, tmax = min(all_times), max(all_times)
    bounded_frame = min(frame_count - 1, max(0, int(frame)))
    fraction = bounded_frame / max(1, frame_count - 1)
    return tmin + fraction * (tmax - tmin)
