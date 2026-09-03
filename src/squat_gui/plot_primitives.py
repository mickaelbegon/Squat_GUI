"""Reusable Tk Canvas primitives for plot controllers."""

from __future__ import annotations

import tkinter as tk
from math import isfinite
from typing import Any

from .didactics import RevealMode
from .kinematics import PhaseDurations
from .plot_rendering import (
    PhaseMarkerDataset,
    blend_color as blend_plot_color,
    component_color as torque_component_color,
    condition_color as comparison_condition_color,
    format_axis_value as formatted_axis_value,
    linear_position,
    linear_ticks,
    phase_marker_layout,
    plot_unit as rendering_plot_unit,
    time_marker_layout,
    torque_component_styles as detailed_torque_component_styles,
    value_bounds_with_zero as rendering_value_bounds_with_zero,
)
from .timeline import nearest_time_index, time_axis_label, time_axis_unit


class PlotPrimitivesMixin:
    """Draw axes, cursors, legends, lines, and point markers."""

    gui: Any

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

    def torque_component_styles(
        self,
    ) -> dict[str, tuple[int, tuple[int, ...] | None, str | None]]:
        return detailed_torque_component_styles()

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
            canvas.create_line(x0 - 4, tick.coordinate, x0, tick.coordinate, fill="#69746e")
            canvas.create_line(x0, tick.coordinate, grid_right, tick.coordinate, fill="#edf0ec")
            canvas.create_text(
                x0 - 8,
                tick.coordinate,
                text=self.gui.format_axis_value(tick.value),
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
            canvas.create_line(tick.coordinate, y0, tick.coordinate, y0 + 4, fill="#69746e")
            canvas.create_text(
                tick.coordinate,
                y0 + 16,
                text=self.gui.format_axis_value(tick.value),
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
            if isinstance(durations := dataset.get("durations"), PhaseDurations)
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
