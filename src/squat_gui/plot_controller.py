"""Tk canvas controller for simulation plots.

The controller owns graph preparation and drawing orchestration while the main
application remains responsible for widget construction and scientific state.
It deliberately uses the application's public methods at integration seams so
legacy extensions and headless tests can still override those methods.
"""

from __future__ import annotations

import tkinter as tk
from math import degrees, isfinite
from typing import Any, cast

from .didactics import RevealMode
from .dynamics import GRAVITY, DynamicsResult
from .kinematics import (
    MotionState,
    PhaseDurations,
    joint_values_from_segment_values,
)
from .plot_data import (
    PlotDataset,
    PlotSample,
    sample_dataset_at_time as sample_plot_dataset_at_time,
    select_plot_datasets,
)
from .plot_rendering import (
    PhaseMarkerDataset,
    blend_color as blend_plot_color,
    component_color as torque_component_color,
    condition_color as comparison_condition_color,
    format_axis_value as formatted_axis_value,
    kinematic_unit as synchronized_kinematic_unit,
    linear_position,
    linear_ticks,
    padded_value_bounds,
    phase_marker_layout,
    plot_time_bounds as rendering_time_bounds,
    plot_unit as rendering_plot_unit,
    time_marker_layout,
    torque_component_styles as detailed_torque_component_styles,
    value_bounds_with_zero as rendering_value_bounds_with_zero,
)
from .session_persistence import SavedCondition, SettingsReader
from .timeline import TimeMode, nearest_time_index, time_axis_label, time_axis_unit


DETAILED_PLOT_CHOICE = "couples detailles"
SYNCHRONIZED_KINEMATICS_CHOICE = "cinematique synchronisee"
TORQUE_COMPONENT_KEYS = {
    "M(q) qddot": "mass_acceleration",
    "termes qdot": "velocity",
    "gravité": "gravity",
    "contact externe (signé)": "external_contact",
    "total ID": "total",
}
PLOT_CHOICES = [
    "cinematique articulaire",
    "centre de masse",
    SYNCHRONIZED_KINEMATICS_CHOICE,
    "force reaction sol",
    "couples articulaires",
    "couples normalises",
    DETAILED_PLOT_CHOICE,
    "puissances articulaires",
]
JOINT_COLORS = {
    "cheville": "#2e7d54",
    "genou": "#b46d22",
    "hanche": "#6d5ea8",
    "horizontal": "#2a8ca6",
    "vertical": "#8a5a22",
}


class PlotCanvasController:
    """Coordinate plot datasets, cursor tables, and Tk canvas rendering."""

    def __init__(self, gui: Any) -> None:
        self.gui = gui

    def draw_plot(self) -> None:
        canvas = self.gui.plot_canvas
        canvas.delete("all")
        self.gui._plot_hit_regions = []
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        datasets = self.gui.plot_datasets()
        self.gui.update_time_mode_notice(datasets)
        if self.gui.reveal_mode() is RevealMode.OBSERVATION:
            self.gui.update_cursor_table([])
            self.gui.plot_title_var.set("OBSERVATION — courbes masquées")
            canvas.create_text(
                width / 2,
                height / 2,
                text="Observez le mouvement et formulez une hypothèse.\n"
                "Passez à CINÉMATIQUE pour révéler position, vitesse et accélération.",
                width=max(240, width - 100),
                justify="center",
                fill="#506158",
                font=("Helvetica", 12, "bold"),
            )
            return
        choice = self.gui.plot_choice.get()
        if choice == SYNCHRONIZED_KINEMATICS_CHOICE:
            source = self.gui.synchronized_source_var.get()
            self.gui.plot_title_var.set(f"cinématique synchronisée — {source}")
            self.gui.draw_synchronized_kinematics(canvas, datasets, width, height)
            return
        self.gui.plot_title_var.set(f"{choice} ({self.gui.plot_unit(choice)})")
        plotted = [
            {
                **dataset,
                "series": self.gui.plot_series_for(
                    choice, dataset.states, dataset.results
                ),
                "times": self.gui.plot_times(dataset.states),
            }
            for dataset in datasets
        ]
        plotted = [dataset for dataset in plotted if dataset["series"]]
        self.gui.update_cursor_table(plotted, choice)
        if not plotted:
            return
        if self.gui.subplot_mode_var.get():
            self.gui.draw_subplot_plot(canvas, plotted, choice, width, height)
        else:
            self.gui.draw_single_axis_plot(canvas, plotted, choice, width, height)

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

    def kinematic_unit(self, source: str, quantity: str) -> str:
        return synchronized_kinematic_unit(source, quantity)

    def draw_synchronized_kinematics(
        self,
        canvas: tk.Canvas,
        datasets: list[PlotDataset],
        width: int,
        height: int,
    ) -> None:
        source = self.gui.synchronized_source_var.get()
        quantities = ("position", "vitesse", "acceleration")
        plotted = []
        for dataset in datasets:
            plotted.append(
                {
                    **dataset,
                    "times": self.gui.plot_times(dataset.states),
                    "orders": {
                        quantity: self.gui.synchronized_series_for(
                            source,
                            quantity,
                            dataset.states,
                            dataset.results,
                        )
                        for quantity in quantities
                    },
                }
            )
        self.gui.update_synchronized_cursor_table(plotted, source)
        if not plotted:
            return
        pad_left, pad_top, pad_right, pad_bottom = 62, 22, 18, 34
        gap = 12
        panel_height = (height - pad_top - pad_bottom - 2 * gap) / 3.0
        tmin, tmax = self.gui.plot_time_bounds(plotted)
        for panel_index, quantity in enumerate(quantities):
            y1 = pad_top + panel_index * (panel_height + gap)
            y0 = y1 + panel_height
            x0, x1 = pad_left, width - pad_right
            values = [
                value
                for dataset in plotted
                for series in dataset["orders"][quantity].values()  # type: ignore[index,union-attr]
                for value in series
            ]
            if not values:
                continue
            ymin, ymax = self.gui.value_bounds_with_zero(values)
            unit = self.gui.kinematic_unit(source, quantity)
            self.gui.draw_panel_axes(
                canvas,
                x0,
                x1,
                y0,
                y1,
                ymin,
                ymax,
                unit,
                quantity,
                tmin,
                tmax,
                show_x_axis=panel_index == 2,
            )
            self.gui.draw_zero_line(canvas, x0, x1, y0, y1, ymin, ymax)
            self.gui.draw_phase_markers(canvas, plotted, x0, x1, y0, y1, tmin, tmax)
            for dataset in plotted:
                series_map = dataset["orders"][quantity]  # type: ignore[index]
                for series_index, (name, series) in enumerate(series_map.items()):  # type: ignore[union-attr]
                    if len(plotted) > 1:
                        color = str(dataset["color"])
                        dash = (None, (6, 4), (2, 3))[series_index % 3]
                    else:
                        color = JOINT_COLORS.get(str(name), "#2e7d54")
                        dash = None
                    self.gui.draw_series_line(
                        canvas,
                        series,
                        x0,
                        x1,
                        y0,
                        y1,
                        ymin,
                        ymax,
                        color,
                        width=2,
                        dash=dash,
                        times=dataset["times"],  # type: ignore[arg-type]
                        tmin=tmin,
                        tmax=tmax,
                    )
        self.gui.draw_synchronized_legend(canvas, plotted, source, width)
        self.gui.draw_condition_legend(canvas, plotted, width, height)

    def value_bounds_with_zero(self, values: list[float]) -> tuple[float, float]:
        return rendering_value_bounds_with_zero(values)

    def draw_zero_line(
        self,
        canvas: tk.Canvas,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
    ) -> None:
        if not ymin <= 0.0 <= ymax:
            return
        y = y0 - (y0 - y1) * (0.0 - ymin) / (ymax - ymin)
        canvas.create_line(x0, y, x1, y, fill="#7f8f83", width=1, dash=(3, 4))
        canvas.create_text(
            x1 - 3,
            y - 2,
            text="0",
            anchor="se",
            fill="#506158",
            font=("Helvetica", 8, "bold"),
        )

    def draw_synchronized_legend(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        source: str,
        width: int,
    ) -> None:
        if len(plotted) > 1:
            return
        names = (
            ("horizontal", "vertical")
            if source == "centre de masse"
            else ("cheville", "genou", "hanche")
        )
        x = width - 18
        for name in reversed(names):
            if source == "centre de masse":
                visible = self.gui.com_component_vars[name].get()
            else:
                visible = self.gui.show_vars[name].get()
            if not visible:
                continue
            canvas.create_text(
                x,
                10,
                text=name,
                anchor="ne",
                fill=JOINT_COLORS[name],
                font=("Helvetica", 8, "bold"),
            )
            x -= 9 * len(name) + 12

    def clear_cursor_table(self) -> None:
        if self.gui.__dict__.get("cursor_table") is None:
            return
        for iid in self.gui.cursor_table.get_children():
            self.gui.cursor_table.delete(iid)

    def insert_cursor_value(
        self,
        condition: str,
        variable: str,
        value: float,
        unit: str,
        sample_time: float,
        phase: str,
    ) -> None:
        time_unit = time_axis_unit(self.gui.time_mode())
        phase_label = phase if self.gui.show_phase_names_var.get() else "masquée"
        self.gui.cursor_table.insert(
            "",
            "end",
            values=(
                condition,
                variable,
                f"{value:.6f}",
                unit,
                f"{sample_time:.3f} {time_unit}",
                phase_label,
            ),
        )

    def update_cursor_table(
        self,
        plotted: list[dict[str, object]],
        choice: str | None = None,
    ) -> None:
        if self.gui.__dict__.get("cursor_table") is None:
            return
        self.gui.clear_cursor_table()
        if self.gui.reveal_mode() is RevealMode.OBSERVATION:
            self.gui.cursor_table.insert(
                "",
                "end",
                values=("", "Valeurs masquées", "", "", "", ""),
            )
            return
        if choice is None:
            return
        cursor_time = self.gui.current_plot_time()
        unit = self.gui.plot_unit(choice)
        for dataset in plotted:
            times = dataset["times"]  # type: ignore[assignment]
            if not times:
                continue
            index = nearest_time_index(times, cursor_time)  # type: ignore[arg-type]
            states = dataset["states"]  # type: ignore[assignment]
            for name, values in dataset["series"].items():  # type: ignore[union-attr]
                if index >= len(values):
                    continue
                self.gui.insert_cursor_value(
                    str(dataset["label"]),
                    str(name),
                    float(values[index]),
                    unit,
                    float(times[index]),
                    str(states[index].phase),
                )

    def update_synchronized_cursor_table(
        self,
        plotted: list[dict[str, object]],
        source: str,
    ) -> None:
        if self.gui.__dict__.get("cursor_table") is None:
            return
        self.gui.clear_cursor_table()
        cursor_time = self.gui.current_plot_time()
        for dataset in plotted:
            times = dataset["times"]  # type: ignore[assignment]
            if not times:
                continue
            index = nearest_time_index(times, cursor_time)  # type: ignore[arg-type]
            states = dataset["states"]  # type: ignore[assignment]
            for quantity in ("position", "vitesse", "acceleration"):
                unit = self.gui.kinematic_unit(source, quantity)
                for name, values in dataset["orders"][quantity].items():  # type: ignore[index,union-attr]
                    if index >= len(values):
                        continue
                    self.gui.insert_cursor_value(
                        str(dataset["label"]),
                        f"{quantity} · {name}",
                        float(values[index]),
                        unit,
                        float(times[index]),
                        str(states[index].phase),
                    )

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
        return rendering_time_bounds(
            time_groups,
            mode,
            fallback_durations,
        )

    def x_from_time(
        self, time: float, x0: float, x1: float, tmin: float, tmax: float
    ) -> float:
        return linear_position(time, x0, x1, tmin, tmax)

    def condition_color(self, index: int, total: int) -> str:
        return comparison_condition_color(index, total)

    def blend_color(self, color: str, target: str, fraction: float) -> str:
        return blend_plot_color(color, target, fraction)

    def component_color(self, base_color: str, component: str) -> str:
        return torque_component_color(base_color, component)

    def visible_torque_components(self) -> tuple[str, ...]:
        variables = self.gui.__dict__.get("torque_component_vars")
        if variables is None:
            return tuple(TORQUE_COMPONENT_KEYS)
        return tuple(
            component
            for component in TORQUE_COMPONENT_KEYS
            if component in variables and variables[component].get()
        )

    def torque_component_styles(
        self,
    ) -> dict[str, tuple[int, tuple[int, ...] | None, str | None]]:
        return detailed_torque_component_styles()

    def selected_panel_names(
        self, plotted: list[dict[str, object]], choice: str
    ) -> list[str]:
        if choice == DETAILED_PLOT_CHOICE:
            return [
                joint
                for joint in ("cheville", "genou", "hanche")
                if self.gui.show_vars[joint].get()
            ]
        names: list[str] = []
        for dataset in plotted:
            for name in dataset["series"]:  # type: ignore[union-attr]
                if name not in names:
                    names.append(str(name))
        return names

    def draw_subplot_plot(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        choice: str,
        width: int,
        height: int,
    ) -> None:
        panels = self.gui.selected_panel_names(plotted, choice)
        if not panels:
            return
        pad_left = 54
        pad_top = 82 if choice == DETAILED_PLOT_CHOICE else 32
        pad_right, pad_bottom = 18, 44
        gap = 44 if choice == DETAILED_PLOT_CHOICE else 22
        panel_width = (width - pad_left - pad_right - gap * (len(panels) - 1)) / len(
            panels
        )
        unit = self.gui.plot_unit(choice)
        tmin, tmax = self.gui.plot_time_bounds(plotted)
        for panel_index, panel_name in enumerate(panels):
            x0 = pad_left + panel_index * (panel_width + gap)
            x1 = x0 + panel_width
            y0 = height - pad_bottom
            y1 = pad_top
            values = self.gui.panel_values(plotted, choice, panel_name)
            if not values:
                continue
            ymin, ymax = self.gui.value_bounds(values, choice, panel_name)
            self.gui.draw_panel_axes(
                canvas, x0, x1, y0, y1, ymin, ymax, unit, panel_name, tmin, tmax
            )
            self.gui.draw_phase_markers(canvas, plotted, x0, x1, y0, y1, tmin, tmax)
            if choice == DETAILED_PLOT_CHOICE:
                self.gui.draw_detailed_panel(
                    canvas, plotted, panel_name, x0, x1, y0, y1, ymin, ymax, tmin, tmax
                )
            else:
                self.gui.draw_panel_series(
                    canvas, plotted, panel_name, x0, x1, y0, y1, ymin, ymax, tmin, tmax
                )
            self.gui.draw_panel_limits(
                canvas,
                plotted,
                choice,
                panel_name,
                x0,
                x1,
                y0,
                y1,
                ymin,
                ymax,
                tmin,
                tmax,
            )
        self.gui.draw_condition_legend(canvas, plotted, width, height)
        if choice == DETAILED_PLOT_CHOICE:
            self.gui.draw_detailed_component_legend(
                canvas,
                pad_left,
                24,
                horizontal=True,
            )

    def draw_single_axis_plot(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        choice: str,
        width: int,
        height: int,
    ) -> None:
        pad_left = 54
        pad_top = 66 if choice == DETAILED_PLOT_CHOICE else 24
        pad_right, pad_bottom = 18, 36
        x0, y0 = pad_left, height - pad_bottom
        x1, y1 = width - pad_right, pad_top
        tmin, tmax = self.gui.plot_time_bounds(plotted)
        all_values = [
            value
            for dataset in plotted
            for values in dataset["series"].values()  # type: ignore[union-attr]
            for value in values
        ]
        panels = self.gui.selected_panel_names(plotted, choice)
        for panel in panels:
            all_values.extend(self.gui.limit_values_for_plot(choice, panel))
        if choice == "couples normalises":
            all_values.append(100.0)
        ymin, ymax = self.gui.value_bounds(all_values, choice, None)
        unit = self.gui.plot_unit(choice)
        self.gui.draw_panel_axes(
            canvas, x0, x1, y0, y1, ymin, ymax, unit, choice, tmin, tmax
        )
        self.gui.draw_phase_markers(canvas, plotted, x0, x1, y0, y1, tmin, tmax)
        if choice == DETAILED_PLOT_CHOICE:
            for panel in panels:
                self.gui.draw_detailed_panel(
                    canvas, plotted, panel, x0, x1, y0, y1, ymin, ymax, tmin, tmax
                )
            self.gui.draw_detailed_component_legend(
                canvas,
                x0,
                20,
                horizontal=True,
            )
        else:
            palette = [
                "#2e7d54",
                "#b46d22",
                "#6d5ea8",
                "#2a8ca6",
                "#9b3d3d",
                "#4c6f3d",
                "#8a5a22",
            ]
            for dataset_index, dataset in enumerate(plotted):
                multi_condition = len(plotted) > 1
                for series_index, (name, values) in enumerate(
                    dataset["series"].items()
                ):  # type: ignore[union-attr]
                    color = (
                        str(dataset["color"])
                        if multi_condition
                        else JOINT_COLORS.get(
                            name, palette[series_index % len(palette)]
                        )
                    )
                    dash = (
                        None
                        if not multi_condition
                        else (None, (6, 4), (2, 3))[series_index % 3]
                    )
                    self.gui.draw_series_line(
                        canvas,
                        values,
                        x0,
                        x1,
                        y0,
                        y1,
                        ymin,
                        ymax,
                        color,
                        width=2,
                        dash=dash,
                        times=dataset["times"],
                        tmin=tmin,
                        tmax=tmax,
                    )  # type: ignore[arg-type]
        self.gui.draw_torque_bounds(canvas, x0, x1, y0, y1, ymin, ymax, tmin, tmax)
        self.gui.draw_normalized_torque_limit(canvas, x0, x1, y0, y1, ymin, ymax)
        if choice == "force reaction sol" and "vertical" in panels:
            self.gui.draw_body_weight_line(canvas, plotted, x0, x1, y0, y1, ymin, ymax)
        self.gui.draw_condition_legend(canvas, plotted, width, height)

    def panel_values(
        self, plotted: list[dict[str, object]], choice: str, panel_name: str
    ) -> list[float]:
        if choice == DETAILED_PLOT_CHOICE:
            return [
                value
                for dataset in plotted
                for component in self.gui.visible_torque_components()
                for value in dataset["series"].get(f"{panel_name} {component}", [])  # type: ignore[union-attr]
            ]
        return [
            value
            for dataset in plotted
            for value in dataset["series"].get(panel_name, [])  # type: ignore[union-attr]
        ]

    def value_bounds(
        self, values: list[float], choice: str, panel_name: str | None
    ) -> tuple[float, float]:
        additional_values = (
            self.gui.limit_values_for_plot(choice, panel_name)
            if panel_name is not None
            else ()
        )
        return padded_value_bounds(
            values,
            additional_values,
            include_hundred=choice == "couples normalises",
        )

    def limit_values_for_plot(self, choice: str, panel_name: str) -> list[float]:
        if (
            choice not in ("couples articulaires", DETAILED_PLOT_CHOICE)
            or not self.gui.show_torque_bounds_var.get()
        ):
            return []
        if (
            panel_name not in self.gui.show_vars
            or not self.gui.show_vars[panel_name].get()
        ):
            return []
        values = self.gui.torque_bound_series().get(panel_name, [])
        return values + [-value for value in values]

    def draw_panel_axes(
        self,
        canvas: tk.Canvas,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        unit: str,
        title: str,
        tmin: float,
        tmax: float,
        show_x_axis: bool = True,
    ) -> None:
        self.gui._plot_hit_regions.append((x0, x1, y1, y0, tmin, tmax))
        canvas.create_line(x0, y0, x1, y0, fill="#69746e")
        canvas.create_line(x0, y0, x0, y1, fill="#69746e")
        self.gui.draw_y_ticks(canvas, x0, y0, y1, ymin, ymax, x1)
        if show_x_axis:
            self.gui.draw_x_ticks(canvas, x0, x1, y0, tmin, tmax)
        self.gui.draw_time_markers(canvas, x0, x1, y0, y1, tmin, tmax)
        canvas.create_text(
            x0 + 4,
            y1 - 14,
            text=f"{title} ({unit})",
            anchor="w",
            fill="#22312a",
            font=("Helvetica", 10, "bold"),
        )
        if show_x_axis:
            xlabel = time_axis_label(self.gui.time_mode())
            canvas.create_text(
                x1 - 44,
                y0 + 24,
                text=xlabel,
                anchor="e",
                fill="#506158",
                font=("Helvetica", 9),
            )

    def draw_panel_series(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        panel_name: str,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        tmin: float,
        tmax: float,
    ) -> None:
        multi_condition = len(plotted) > 1
        for dataset in plotted:
            values = dataset["series"].get(panel_name, [])  # type: ignore[union-attr]
            color = (
                str(dataset["color"])
                if multi_condition
                else JOINT_COLORS.get(panel_name, "#2e7d54")
            )
            self.gui.draw_series_line(
                canvas,
                values,
                x0,
                x1,
                y0,
                y1,
                ymin,
                ymax,
                color,
                width=2,
                times=dataset["times"],
                tmin=tmin,
                tmax=tmax,
            )  # type: ignore[arg-type]

    def draw_panel_limits(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        choice: str,
        panel_name: str,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        tmin: float,
        tmax: float,
    ) -> None:
        if choice == "couples normalises":
            self.gui.draw_normalized_torque_limit(canvas, x0, x1, y0, y1, ymin, ymax)
        if choice == "force reaction sol" and panel_name == "vertical":
            self.gui.draw_body_weight_line(canvas, plotted, x0, x1, y0, y1, ymin, ymax)
        if choice in ("couples articulaires", DETAILED_PLOT_CHOICE):
            self.gui.draw_torque_bound_for_joint(
                canvas, panel_name, x0, x1, y0, y1, ymin, ymax, tmin=tmin, tmax=tmax
            )

    def draw_condition_legend(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        width: int,
        height: int,
    ) -> None:
        if len(plotted) <= 1:
            return
        legend_x = 62
        y = height - 14
        for dataset in plotted:
            color = str(dataset["color"])
            label = str(dataset["label"])
            canvas.create_line(legend_x, y, legend_x + 18, y, fill=color, width=3)
            canvas.create_text(legend_x + 24, y, text=label, anchor="w", fill="#22312a")
            legend_x += max(86, 9 * len(label))

    def draw_y_ticks(
        self,
        canvas: tk.Canvas,
        x0: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        grid_right: float | None = None,
    ) -> None:
        grid_right = grid_right if grid_right is not None else canvas.winfo_width() - 18
        for tick in linear_ticks(ymin, ymax, y0, y1):
            value = tick.value
            y = tick.coordinate
            canvas.create_line(x0 - 4, y, x0, y, fill="#69746e")
            canvas.create_line(x0, y, grid_right, y, fill="#edf0ec")
            canvas.create_text(
                x0 - 8,
                y,
                text=self.gui.format_axis_value(value),
                anchor="e",
                fill="#506158",
                font=("Helvetica", 9),
            )

    def draw_x_ticks(
        self,
        canvas: tk.Canvas,
        x0: float,
        x1: float,
        y0: float,
        tmin: float,
        tmax: float,
    ) -> None:
        for tick in linear_ticks(tmin, tmax, x0, x1):
            value = tick.value
            x = tick.coordinate
            canvas.create_line(x, y0, x, y0 + 4, fill="#69746e")
            canvas.create_text(
                x,
                y0 + 16,
                text=self.gui.format_axis_value(value),
                anchor="n",
                fill="#506158",
                font=("Helvetica", 9),
            )

    def draw_time_markers(
        self,
        canvas: tk.Canvas,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        tmin: float,
        tmax: float,
    ) -> None:
        markers = time_marker_layout(
            mode=self.gui.time_mode(),
            show_phase_limits=self.gui.show_phase_limits_var.get(),
            current_time=self.gui.current_plot_time(),
            x0=x0,
            x1=x1,
            tmin=tmin,
            tmax=tmax,
        )
        if markers.squat_reference_x is not None:
            canvas.create_line(
                markers.squat_reference_x,
                y0,
                markers.squat_reference_x,
                y1,
                fill="#59645e",
                width=1,
                dash=(6, 5),
            )
        canvas.create_line(
            markers.current_time_x,
            y0,
            markers.current_time_x,
            y1,
            fill="#c9332c",
            width=2,
        )

    def draw_phase_markers(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        tmin: float,
        tmax: float,
    ) -> None:
        if (
            not self.gui.show_phase_limits_var.get()
            and not self.gui.show_phase_names_var.get()
        ):
            return
        marker_datasets = [
            PhaseMarkerDataset(
                label=str(dataset.get("label", "")),
                durations=durations,
                color=(str(dataset["color"]) if dataset.get("color") else None),
                row=dataset_index,
            )
            for dataset_index, dataset in enumerate(plotted)
            if isinstance(
                durations := dataset.get("durations"),
                PhaseDurations,
            )
        ]
        markers = phase_marker_layout(
            marker_datasets,
            mode=self.gui.time_mode(),
            show_limits=self.gui.show_phase_limits_var.get(),
            show_names=self.gui.show_phase_names_var.get(),
            x0=x0,
            x1=x1,
            tmin=tmin,
            tmax=tmax,
            comparison_count=len(plotted),
        )
        for marker in markers.boundaries:
            canvas.create_line(
                marker.x,
                y0,
                marker.x,
                y1,
                fill=marker.color,
                width=1,
                dash=(3, 3),
            )
        for marker in markers.labels:
            canvas.create_text(
                marker.x,
                y1 + 3 + 10 * marker.row,
                text=marker.text,
                anchor="n",
                fill=marker.color,
                font=("Helvetica", 7, "bold"),
            )

    def on_plot_cursor_event(self, event: tk.Event) -> None:
        if (
            self.gui.reveal_mode() is RevealMode.OBSERVATION
            or not self.gui._plot_hit_regions
        ):
            return
        candidates = [
            region
            for region in self.gui._plot_hit_regions
            if region[0] <= event.x <= region[1] and region[2] <= event.y <= region[3]
        ]
        region = candidates[0] if candidates else self.gui._plot_hit_regions[0]
        x0, x1, _y1, _y0, tmin, tmax = region
        fraction = min(1.0, max(0.0, (event.x - x0) / max(1e-9, x1 - x0)))
        selected_time = tmin + fraction * (tmax - tmin)
        frame_fraction = (selected_time - tmin) / max(1e-9, tmax - tmin)
        self.gui.frame_var.set(round(frame_fraction * (self.gui.frame_count - 1)))
        self.gui.redraw()

    def format_axis_value(self, value: float) -> str:
        return formatted_axis_value(value)

    def plot_unit(self, choice: str) -> str:
        return rendering_plot_unit(choice, self.gui.quantity_var.get())

    def draw_torque_bounds(
        self,
        canvas: tk.Canvas,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        tmin: float | None = None,
        tmax: float | None = None,
    ) -> None:
        if (
            self.gui.plot_choice.get()
            not in ("couples articulaires", "couples detailles")
            or not self.gui.show_torque_bounds_var.get()
        ):
            return
        if tmin is None or tmax is None:
            tmin, tmax = self.gui.plot_time_bounds([{"times": self.gui.plot_times()}])
        for joint, values in self.gui.torque_bound_series().items():
            self.gui.draw_torque_bound_for_joint(
                canvas, joint, x0, x1, y0, y1, ymin, ymax, values, tmin=tmin, tmax=tmax
            )

    def draw_torque_bound_for_joint(
        self,
        canvas: tk.Canvas,
        joint: str,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        values: list[float] | None = None,
        tmin: float | None = None,
        tmax: float | None = None,
    ) -> None:
        if (
            joint not in self.gui.show_vars
            or not self.gui.show_vars[joint].get()
            or not self.gui.show_torque_bounds_var.get()
        ):
            return
        values = values or self.gui.torque_bound_series().get(joint, [])
        if tmin is None or tmax is None:
            tmin, tmax = self.gui.plot_time_bounds([{"times": self.gui.plot_times()}])
        times = self.gui.plot_times()
        color = JOINT_COLORS[joint]
        for sign in (1.0, -1.0):
            points = []
            for index, value in enumerate(values):
                x = (
                    self.gui.x_from_time(times[index], x0, x1, tmin, tmax)
                    if index < len(times)
                    else x0
                )
                y = y0 - (y0 - y1) * (sign * value - ymin) / (ymax - ymin)
                points.extend([x, y])
            if len(points) >= 4:
                canvas.create_line(*points, fill=color, width=1, dash=(6, 5))

    def draw_normalized_torque_limit(
        self,
        canvas: tk.Canvas,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
    ) -> None:
        if self.gui.plot_choice.get() != "couples normalises":
            return
        y = y0 - (y0 - y1) * (100.0 - ymin) / (ymax - ymin)
        canvas.create_line(x0, y, x1, y, fill="#c9332c", width=1, dash=(6, 5))
        canvas.create_text(
            x1 - 4,
            y - 4,
            text="100%",
            anchor="se",
            fill="#8a1f17",
            font=("Helvetica", 9, "bold"),
        )

    def draw_body_weight_line(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
    ) -> None:
        weights = []
        for dataset in plotted:
            anthro = dataset["anthro"]  # type: ignore[assignment]
            weight = float(anthro.total_mass * GRAVITY)
            if all(abs(weight - existing) > 1e-6 for existing in weights):
                weights.append(weight)
        for weight in weights:
            if not ymin <= weight <= ymax:
                continue
            y = y0 - (y0 - y1) * (weight - ymin) / (ymax - ymin)
            canvas.create_line(x0, y, x1, y, fill="#59645e", width=1, dash=(6, 5))
            canvas.create_text(
                x1 - 4,
                y - 4,
                text=f"m·g {weight:.0f} N",
                anchor="se",
                fill="#59645e",
                font=("Helvetica", 9),
            )

    def draw_detailed_torque_plot(
        self,
        canvas: tk.Canvas,
        series: dict[str, list[float]],
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
    ) -> None:
        legend_x = x0
        component_styles = self.gui.torque_component_styles()
        for joint in ("cheville", "genou", "hanche"):
            if joint not in self.gui.show_vars or not self.gui.show_vars[joint].get():
                continue
            color = JOINT_COLORS[joint]
            for component in self.gui.visible_torque_components():
                width, dash, marker = component_styles[component]
                values = series.get(f"{joint} {component}", [])
                component_color = self.gui.component_color(color, component)
                self.gui.draw_series_line(
                    canvas,
                    values,
                    x0,
                    x1,
                    y0,
                    y1,
                    ymin,
                    ymax,
                    component_color,
                    width=width,
                    dash=dash,
                )
                if marker == "triangle":
                    self.gui.draw_triangle_markers(
                        canvas, values, x0, x1, y0, y1, ymin, ymax, component_color
                    )
            canvas.create_line(
                legend_x,
                canvas.winfo_height() - 14,
                legend_x + 18,
                canvas.winfo_height() - 14,
                fill=color,
                width=3,
            )
            canvas.create_text(
                legend_x + 24,
                canvas.winfo_height() - 14,
                text=joint,
                anchor="w",
                fill="#22312a",
            )
            legend_x += 95
        self.gui.draw_detailed_component_legend(canvas, x1 - 270, y1 + 4)

    def draw_detailed_panel(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        joint: str,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        tmin: float,
        tmax: float,
    ) -> None:
        multi_condition = len(plotted) > 1
        component_styles = self.gui.torque_component_styles()
        for dataset in plotted:
            color = str(dataset["color"]) if multi_condition else JOINT_COLORS[joint]
            series = dataset["series"]  # type: ignore[assignment]
            times = dataset["times"]  # type: ignore[assignment]
            for component in self.gui.visible_torque_components():
                width, dash, marker = component_styles[component]
                values = series.get(f"{joint} {component}", [])
                component_color = self.gui.component_color(color, component)
                self.gui.draw_series_line(
                    canvas,
                    values,
                    x0,
                    x1,
                    y0,
                    y1,
                    ymin,
                    ymax,
                    component_color,
                    width=width,
                    dash=dash,
                    times=times,
                    tmin=tmin,
                    tmax=tmax,
                )
                if marker == "triangle":
                    self.gui.draw_triangle_markers(
                        canvas,
                        values,
                        x0,
                        x1,
                        y0,
                        y1,
                        ymin,
                        ymax,
                        component_color,
                        times=times,
                        tmin=tmin,
                        tmax=tmax,
                    )

    def draw_detailed_component_legend(
        self,
        canvas: tk.Canvas,
        x: float,
        y: float,
        *,
        horizontal: bool = False,
    ) -> None:
        styles = self.gui.torque_component_styles()
        cursor_x = x
        for index, label in enumerate(self.gui.visible_torque_components()):
            width, dash, marker = styles[label]
            xx = cursor_x if horizontal else x
            yy = y if horizontal else y + 16 * index
            canvas.create_line(
                xx,
                yy,
                xx + 28,
                yy,
                fill="#334139",
                width=width,
                dash=dash,
            )
            if marker == "triangle":
                canvas.create_polygon(
                    xx + 14,
                    yy - 4,
                    xx + 10,
                    yy + 4,
                    xx + 18,
                    yy + 4,
                    fill="#334139",
                    outline="#334139",
                )
            canvas.create_text(
                xx + 34,
                yy,
                text=label,
                anchor="w",
                fill="#334139",
                font=("Helvetica", 9),
            )
            if horizontal:
                cursor_x += 70 + 6.4 * len(label)

    def draw_series_line(
        self,
        canvas: tk.Canvas,
        values: list[float],
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        color: str,
        width: int,
        dash: tuple[int, ...] | None = None,
        times: list[float] | None = None,
        tmin: float | None = None,
        tmax: float | None = None,
    ) -> None:
        points: list[float] = []
        for index, value in enumerate(values):
            if not isfinite(value):
                if len(points) >= 4:
                    canvas.create_line(*points, fill=color, width=width, dash=dash)
                points = []
                continue
            if (
                times is not None
                and tmin is not None
                and tmax is not None
                and index < len(times)
            ):
                x = self.gui.x_from_time(times[index], x0, x1, tmin, tmax)
            else:
                x = x0 + (x1 - x0) * index / max(1, len(values) - 1)
            y = y0 - (y0 - y1) * (value - ymin) / (ymax - ymin)
            points.extend([x, y])
        if len(points) >= 4:
            canvas.create_line(*points, fill=color, width=width, dash=dash)

    def draw_triangle_markers(
        self,
        canvas: tk.Canvas,
        values: list[float],
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        color: str,
        times: list[float] | None = None,
        tmin: float | None = None,
        tmax: float | None = None,
    ) -> None:
        step = max(1, len(values) // 18)
        for index, value in enumerate(values):
            if index % step != 0 and index != len(values) - 1:
                continue
            if (
                times is not None
                and tmin is not None
                and tmax is not None
                and index < len(times)
            ):
                x = self.gui.x_from_time(times[index], x0, x1, tmin, tmax)
            else:
                x = x0 + (x1 - x0) * index / max(1, len(values) - 1)
            y = y0 - (y0 - y1) * (value - ymin) / (ymax - ymin)
            canvas.create_polygon(
                x, y - 5, x - 5, y + 5, x + 5, y + 5, fill=color, outline=color
            )

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
