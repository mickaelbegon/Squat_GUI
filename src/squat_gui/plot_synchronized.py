"""Rendering for the synchronized position/velocity/acceleration view."""

from __future__ import annotations

import tkinter as tk
from typing import Any

from .plot_config import JOINT_COLORS
from .plot_data import PlotDataset
from .plot_rendering import kinematic_unit as synchronized_kinematic_unit
from .timeline import nearest_time_index


class SynchronizedPlotMixin:
    """Draw and update the three aligned kinematic panels."""

    gui: Any

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
