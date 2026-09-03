"""Animation canvas and bar-trajectory rendering."""

from __future__ import annotations

import tkinter as tk
from math import degrees
from typing import cast

from .didactics import RevealMode
from .dynamics import DynamicsResult
from .kinematics import MotionState, joint_angles_from_pose, segment_orientations
from .plot_data import PlotSample
from .rendering import RenderLayers
from .scene_styles import ALERT_BORDER, CANVAS_BG, SEGMENT_LABELS


class SceneAnimationRendererMixin:
    """Render animated conditions, trajectories, labels, and values."""

    def draw_animation(self, frame: int) -> None:
        canvas = self.animation_canvas
        canvas.delete("all")
        canvas._sprite_images = []
        self.app._animation_hover_targets = []
        layers = self.render_layers()
        datasets = self.plot_datasets()
        current_plot_time = self.current_plot_time()
        sampled = [
            self.sample_dataset_at_time(dataset, current_plot_time)
            for dataset in datasets
        ]
        alerts: list[str] = []
        if layers.alerts:
            for item in sampled:
                condition_alerts = self.app.biomechanical_alerts(
                    item.state, item.result, include_com=False
                )
                alerts.extend(f"{item.label} : {alert}" for alert in condition_alerts)
        self.app.configure_alert_canvas(canvas, alerts)
        bounds = self.app.scene_bounds(
            extra_x=max(0, len(sampled) - 1),
            anthropometries=[item.anthro for item in sampled],
        )
        for index, item in enumerate(sampled):
            state = item.state
            condition_alerts = (
                self.app.biomechanical_alerts(state, item.result, include_com=False)
                if layers.alerts
                else []
            )
            self.app.draw_skeleton(
                canvas,
                state,
                item.result,
                with_handles=False,
                bounds=bounds,
                x_offset=float(index),
                render_anthro=item.anthro,
                refined_sprites=item.refined_sprites,
                layers=layers,
            )
            if (
                self.reveal_mode() is RevealMode.FREE
                and self.show_bar_trajectory_var.get()
            ):
                self.app.draw_bar_trajectory(
                    canvas,
                    item.states,
                    bounds,
                    float(index),
                    item.color or "#2e7d54",
                )
            self.app.register_animation_hover_targets(
                canvas,
                state,
                bounds,
                float(index),
                item.label,
                len(sampled) > 1,
                layers,
            )
            self.app.register_segment_com_hover_targets(
                canvas,
                state,
                item.anthro,
                bounds,
                float(index),
                item.label,
                len(sampled) > 1,
                layers,
            )
            self.app.draw_animation_scientific_labels(
                canvas, state, bounds, float(index), layers
            )
            if len(sampled) > 1:
                label_point = self.app.world_to_canvas(
                    canvas, (float(index), -0.045), bounds
                )
                color = item.color or "#2e7d54"
                canvas.create_text(
                    label_point[0],
                    label_point[1],
                    text=item.label,
                    anchor="n",
                    fill=color,
                    font=("Helvetica", 10, "bold"),
                )
                if condition_alerts:
                    canvas.create_text(
                        label_point[0] + 36,
                        label_point[1],
                        text="⚠",
                        anchor="n",
                        fill=ALERT_BORDER,
                        font=("Helvetica", 12, "bold"),
                    )
        state = sampled[0].state
        result = sampled[0].result
        title = (
            f"Animation {state.phase} {self.animation_time_label(current_plot_time)}"
            if layers.time_label
            else "Animation — OBSERVATION"
        )
        canvas.create_text(
            16,
            16,
            text=title,
            anchor="nw",
            fill="#22312a",
            font=("Helvetica", 13, "bold"),
        )
        if self.reveal_mode() in (RevealMode.FREE, RevealMode.DYNAMICS):
            self.app.draw_animation_values(canvas, sampled)
        overlay_top = 16
        if layers.anthropometry:
            overlay_top = self.app.draw_anthropometry_overlay(
                canvas,
                sampled[0].anthro,
                sampled[0].label if len(sampled) > 1 else "",
                overlay_top,
            )
        if layers.force_balance:
            self.app.draw_force_balance_overlay(
                canvas,
                sampled[0].anthro,
                state,
                result,
                overlay_top,
            )
        if (
            self.reveal_mode() is RevealMode.FREE
            and self.show_neighbor_samples_var.get()
        ):
            self.app.draw_neighbor_samples_overlay(canvas, self.states, frame)
        if layers.alerts:
            self.app.draw_alert_banner(canvas, alerts, 126)

    def draw_bar_trajectory(
        self,
        canvas: tk.Canvas,
        states: list[MotionState],
        bounds: tuple[float, float, float, float],
        x_offset: float,
        color: str | None,
    ) -> None:
        """Draw the full actual bar path, from descent through the return."""
        if len(states) < 2:
            return
        color = color or "#2e7d54"
        bottom_index = min(
            range(len(states)), key=lambda index: states[index].pose.bar[1]
        )
        points = [
            self.app.world_to_canvas(
                canvas,
                (state.pose.bar[0] + x_offset, state.pose.bar[1]),
                bounds,
            )
            for state in states
        ]
        coordinates = [coordinate for point in points for coordinate in point]
        canvas.create_line(
            *coordinates,
            fill=color,
            width=3,
            dash=(7, 4),
            smooth=True,
        )
        markers = (
            (points[0], "départ", -8),
            (points[bottom_index], "bas", 0),
            (points[-1], "retour", 8),
        )
        for point, label, label_y_offset in markers:
            x, y = point
            canvas.create_oval(
                x - 5,
                y - 5,
                x + 5,
                y + 5,
                fill=CANVAS_BG,
                outline=color,
                width=2,
            )
            canvas.create_text(
                x + 8,
                y + label_y_offset,
                text=label,
                anchor="w",
                fill=color,
                font=("Helvetica", 9, "bold"),
            )

    def draw_animation_scientific_labels(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        bounds: tuple[float, float, float, float],
        x_offset: float,
        layers: RenderLayers,
    ) -> None:
        pose = state.pose
        if layers.segment_orientations:
            orientations = segment_orientations(pose)
            endpoints = {
                "foot": (pose.heel, pose.toe),
                "shank": (pose.ankle, pose.knee),
                "thigh": (pose.knee, pose.hip),
                "trunk": (pose.hip, pose.shoulder),
            }
            orientation_offsets = {
                "foot": (8, 24, "nw"),
                "shank": (8, -4, "sw"),
                "thigh": (8, -10, "sw"),
                "trunk": (8, -10, "sw"),
            }
            for name, (start, end) in endpoints.items():
                midpoint = (
                    (start[0] + end[0]) / 2.0 + x_offset,
                    (start[1] + end[1]) / 2.0,
                )
                x, y = self.app.world_to_canvas(canvas, midpoint, bounds)
                dx, dy, anchor = orientation_offsets[name]
                canvas.create_text(
                    x + dx,
                    y + dy,
                    text=f"{SEGMENT_LABELS[name]}: {degrees(orientations[name]):.1f}°",
                    anchor=anchor,
                    fill="#276c92",
                    font=("Helvetica", 8, "bold"),
                )
        if layers.joint_angles:
            angles = joint_angles_from_pose(pose)
            points = {"cheville": pose.ankle, "genou": pose.knee, "hanche": pose.hip}
            angle_offsets = {
                "cheville": (12, -12, "sw"),
                "genou": (12, 16, "nw"),
                "hanche": (12, 16, "nw"),
            }
            for name, point in points.items():
                x, y = self.app.world_to_canvas(
                    canvas, (point[0] + x_offset, point[1]), bounds
                )
                dx, dy, anchor = angle_offsets[name]
                canvas.create_text(
                    x + dx,
                    y + dy,
                    text=f"{name}: {degrees(angles[name]):.1f}°",
                    anchor=anchor,
                    fill="#6d5ea8",
                    font=("Helvetica", 8, "bold"),
                )

    def draw_animation_values(
        self,
        canvas: tk.Canvas,
        sampled: list[PlotSample] | list[dict[str, object]],
    ) -> None:
        column_width = 155
        for index, item in enumerate(sampled):
            x = 16 + index * column_width
            y = 42
            if isinstance(item, PlotSample):
                label = item.label
                color = item.color or "#22312a"
                result = item.result
            else:
                label = str(item["label"])
                color = str(item["color"] or "#22312a")
                result = cast(DynamicsResult, item["result"])
            canvas.create_text(
                x,
                y,
                text=label,
                anchor="nw",
                fill=color,
                font=("Helvetica", 10, "bold"),
            )
            y += 18
            if self.show_animation_torques_var.get():
                for joint in ("cheville", "genou", "hanche"):
                    torque = result.torques[joint]
                    ratio = result.effort_ratios[joint]
                    text_color = "#8a1f17" if ratio is None or ratio > 1.0 else color
                    utilization_text = (
                        "n.d." if ratio is None else f"{100 * ratio: .0f}%"
                    )
                    canvas.create_text(
                        x,
                        y,
                        text=f"{joint}: {torque: .1f} Nm (U={utilization_text})",
                        anchor="nw",
                        fill=text_color,
                        font=("Helvetica", 9),
                    )
                    y += 18
