"""Adapt simulation and saved-condition data for plotting.

This module contains no Canvas layout.  It is the translation boundary between
the application's scientific objects and the named series consumed by the plot
renderers.
"""

from __future__ import annotations

from math import degrees
from typing import Any, cast

from .dynamics import DynamicsResult
from .kinematics import MotionState, PhaseDurations, joint_values_from_segment_values
from .plot_config import TORQUE_COMPONENT_KEYS
from .plot_data import (
    PlotDataset,
    PlotSample,
    sample_dataset_at_time as sample_plot_dataset_at_time,
    select_plot_datasets,
)
from .plot_rendering import plot_time_bounds as rendering_time_bounds
from .session_persistence import SavedCondition, SettingsReader
from .timeline import TimeMode


class PlotDataAdapterMixin:
    """Provide plot datasets, time metadata, and scientific series."""

    gui: Any

    def plot_datasets(self) -> list[PlotDataset]:
        selected = [
            iid
            for iid in self.gui.conditions_table.selection()
            if iid in self.gui.saved_conditions
        ]
        if not selected:
            settings = self.gui.current_settings()
            current = PlotDataset(
                label="courant",
                states=self.gui.states,
                results=self.gui.results,
                color=None,
                anthro=self.gui.anthro(),
                refined_sprites=self.gui.refined_sprites_from_settings(settings),
                durations=self.gui.phase_durations(),
            )
            return select_plot_datasets(current, {}, selected)
        total = len(selected)
        saved_datasets: dict[str, PlotDataset] = {}
        for index, iid in enumerate(selected):
            condition = self.gui.saved_conditions[iid]
            if isinstance(condition, SavedCondition):
                label = condition.label
                states = condition.states
                results = condition.results
                condition_settings = condition.settings
            else:
                # Transitional compatibility for extensions that still provide
                # the historical mapping representation.
                label = str(condition["label"])
                states = cast(list[MotionState], condition["states"])
                results = cast(list[DynamicsResult], condition["results"])
                condition_settings = dict(
                    SettingsReader.from_object(condition["settings"]).values
                )
            saved_datasets[iid] = PlotDataset(
                label=label,
                states=states,
                results=results,
                color=self.gui.condition_color(index, total),
                anthro=self.gui.anthro_from_settings(condition_settings),
                refined_sprites=self.gui.refined_sprites_from_settings(
                    condition_settings
                ),
                durations=self.gui.phase_durations_from_settings(condition_settings),
            )
        return select_plot_datasets(None, saved_datasets, selected)

    def sample_dataset_at_time(
        self, dataset: PlotDataset, plot_time: float
    ) -> PlotSample:
        return sample_plot_dataset_at_time(dataset, plot_time, self.gui.time_mode())

    def animation_time_label(self, plot_time: float) -> str:
        mode = self.gui.time_mode()
        if mode is TimeMode.NORMALIZED:
            return f"temps normalisé={plot_time:.0f}%"
        if mode is TimeMode.ABSOLUTE:
            return f"temps absolu={plot_time:.2f}s"
        return f"temps centré={plot_time:.2f}s"

    def plot_time_bounds(self, plotted: list[dict[str, object]]) -> tuple[float, float]:
        time_groups = [
            cast(list[float], dataset.get("times", [])) for dataset in plotted
        ]
        mode = self.gui.time_mode()
        fallback_durations = (
            self.gui.phase_durations()
            if mode is not TimeMode.NORMALIZED and not any(time_groups)
            else PhaseDurations()
        )
        return rendering_time_bounds(time_groups, mode, fallback_durations)

    def synchronized_series_for(
        self,
        source: str,
        quantity: str,
        states: list[MotionState],
        results: list[DynamicsResult],
    ) -> dict[str, list[float]]:
        if source == "centre de masse":
            return self.gui.com_plot_series_for_quantity(results, quantity)
        series = self.gui.joint_kinematic_series_for_quantity(states, quantity)
        return {
            name: values
            for name, values in series.items()
            if self.gui.show_vars[name].get()
        }

    def plot_series(self, choice: str) -> dict[str, list[float]]:
        return self.gui.plot_series_for(choice, self.gui.states, self.gui.results)

    def plot_series_for(
        self,
        choice: str,
        states: list[MotionState],
        results: list[DynamicsResult],
    ) -> dict[str, list[float]]:
        selected = [name for name, var in self.gui.show_vars.items() if var.get()]
        data: dict[str, list[float]] = {}
        if choice == "cinematique articulaire":
            values = self.gui.joint_kinematic_series(states)
        elif choice == "centre de masse":
            return self.gui.com_plot_series(results)
        elif choice == "force reaction sol":
            return self.gui.ground_reaction_plot_series(results)
        elif choice == "couples articulaires":
            values = {
                joint: [result.torques[joint] for result in results]
                for joint in ("cheville", "genou", "hanche")
            }
        elif choice == "couples normalises":
            values = {
                joint: [
                    (
                        float("nan")
                        if result.effort_ratios[joint] is None
                        else 100.0 * result.effort_ratios[joint]
                    )
                    for result in results
                ]
                for joint in ("cheville", "genou", "hanche")
            }
        elif choice == "couples detailles":
            values = {}
            for joint in ("cheville", "genou", "hanche"):
                if joint in selected:
                    for label in self.gui.visible_torque_components():
                        key = TORQUE_COMPONENT_KEYS[label]
                        values[f"{joint} {label}"] = [
                            result.torque_components[joint][key] for result in results
                        ]
            return values
        else:
            values = {
                joint: [result.powers[joint] for result in results]
                for joint in ("cheville", "genou", "hanche")
            }
        for name in selected:
            if name in values:
                data[name] = values[name]
        return data

    def joint_kinematic_series(
        self, states: list[MotionState] | None = None
    ) -> dict[str, list[float]]:
        states = states or self.gui.states
        return self.gui.joint_kinematic_series_for_quantity(
            states, self.gui.quantity_var.get()
        )

    def joint_kinematic_series_for_quantity(
        self,
        states: list[MotionState],
        quantity: str,
    ) -> dict[str, list[float]]:
        attribute = {"position": "q", "vitesse": "qdot", "acceleration": "qddot"}[
            quantity
        ]
        series = {joint: [] for joint in ("cheville", "genou", "hanche")}
        for state in states:
            values = joint_values_from_segment_values(getattr(state, attribute))
            for joint, value in values.items():
                series[joint].append(degrees(value))
        return series

    def com_plot_series(
        self, results: list[DynamicsResult] | None = None
    ) -> dict[str, list[float]]:
        results = results or self.gui.results
        return self.gui.com_plot_series_for_quantity(
            results, self.gui.quantity_var.get()
        )

    def com_plot_series_for_quantity(
        self,
        results: list[DynamicsResult],
        quantity: str,
    ) -> dict[str, list[float]]:
        source = {
            "position": [result.com for result in results],
            "vitesse": [result.com_velocity for result in results],
            "acceleration": [result.com_acceleration for result in results],
        }[quantity]
        return self.gui.horizontal_vertical_series(source)

    def ground_reaction_plot_series(
        self, results: list[DynamicsResult] | None = None
    ) -> dict[str, list[float]]:
        results = results or self.gui.results
        return self.gui.horizontal_vertical_series(
            [result.ground_reaction for result in results]
        )

    def horizontal_vertical_series(
        self, source: list[tuple[float, float]]
    ) -> dict[str, list[float]]:
        data: dict[str, list[float]] = {}
        if self.gui.com_component_vars["horizontal"].get():
            data["horizontal"] = [value[0] for value in source]
        if self.gui.com_component_vars["vertical"].get():
            data["vertical"] = [value[1] for value in source]
        return data

    def torque_bound_series(self) -> dict[str, list[float]]:
        return {
            joint: [
                result.torque_capacities[joint].available_torque_Nm
                for result in self.gui.results
            ]
            for joint in ("cheville", "genou", "hanche")
        }
