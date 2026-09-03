"""Torque-specific plot overlays and detailed-component rendering."""

from __future__ import annotations

import tkinter as tk
from typing import Any

from .dynamics import GRAVITY
from .plot_config import JOINT_COLORS, TORQUE_COMPONENT_KEYS


class TorquePlotMixin:
    """Draw joint-torque limits, components, and related references."""

    gui: Any

    def visible_torque_components(self) -> tuple[str, ...]:
        variables = self.gui.__dict__.get("torque_component_vars")
        if variables is None:
            return tuple(TORQUE_COMPONENT_KEYS)
        return tuple(
            component
            for component in TORQUE_COMPONENT_KEYS
            if component in variables and variables[component].get()
        )

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
                canvas,
                joint,
                x0,
                x1,
                y0,
                y1,
                ymin,
                ymax,
                values,
                tmin=tmin,
                tmax=tmax,
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
                        canvas,
                        values,
                        x0,
                        x1,
                        y0,
                        y1,
                        ymin,
                        ymax,
                        component_color,
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
