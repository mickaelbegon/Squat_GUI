"""Public plot-controller facade and high-level layout orchestration.

The specialized modules inherited below own data adaptation, synchronized
kinematics, torque rendering, and low-level Canvas primitives.  This module
keeps the historical :class:`PlotCanvasController` API used by ``SquatGui`` and
extensions while making its orchestration role explicit.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any

from .didactics import RevealMode
from .plot_config import (
    DETAILED_PLOT_CHOICE,
    JOINT_COLORS,
    PLOT_CHOICES,
    SYNCHRONIZED_KINEMATICS_CHOICE,
    TORQUE_COMPONENT_KEYS,
)
from .plot_data_adapter import PlotDataAdapterMixin
from .plot_primitives import PlotPrimitivesMixin
from .plot_rendering import padded_value_bounds
from .plot_synchronized import SynchronizedPlotMixin
from .plot_torque import TorquePlotMixin

__all__ = [
    "DETAILED_PLOT_CHOICE",
    "JOINT_COLORS",
    "PLOT_CHOICES",
    "SYNCHRONIZED_KINEMATICS_CHOICE",
    "TORQUE_COMPONENT_KEYS",
    "PlotCanvasController",
]


class PlotCanvasController(
    PlotDataAdapterMixin,
    SynchronizedPlotMixin,
    TorquePlotMixin,
    PlotPrimitivesMixin,
):
    """Coordinate plot datasets and specialized Tk Canvas renderers."""

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
                    canvas,
                    plotted,
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
            else:
                self.gui.draw_panel_series(
                    canvas,
                    plotted,
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
                    canvas,
                    plotted,
                    panel,
                    x0,
                    x1,
                    y0,
                    y1,
                    ymin,
                    ymax,
                    tmin,
                    tmax,
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
            for dataset in plotted:
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
                canvas,
                panel_name,
                x0,
                x1,
                y0,
                y1,
                ymin,
                ymax,
                tmin=tmin,
                tmax=tmax,
            )
