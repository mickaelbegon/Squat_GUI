"""Hover-target registration and scientific tooltips."""

from __future__ import annotations

import tkinter as tk

from .anthropometry import Anthropometry
from .kinematics import MotionState
from .observables import com_contributions, joint_coordinates, segment_anthropometry
from .rendering import RenderLayers
from .scene_styles import POINT_LABELS


class SceneHoverMixin:
    """Register canvas targets and display their scientific tooltips."""

    def register_animation_hover_targets(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        bounds: tuple[float, float, float, float],
        x_offset: float,
        condition_label: str,
        include_condition: bool,
        layers: RenderLayers,
    ) -> None:
        if not layers.joint_coordinates:
            return
        for name, point in joint_coordinates(state.pose).items():
            shifted = (point[0] + x_offset, point[1])
            x, y = self.app.world_to_canvas(canvas, shifted, bounds)
            self._animation_hover_targets.append(
                {
                    "x": x,
                    "y": y,
                    "name": name,
                    "point": point,
                    "condition": condition_label if include_condition else "",
                    "tooltip_text": "",
                }
            )
            canvas.create_oval(x - 8, y - 8, x + 8, y + 8, outline="#276c92", width=2)

    def register_segment_com_hover_targets(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        anthro: Anthropometry,
        bounds: tuple[float, float, float, float],
        x_offset: float,
        condition_label: str,
        include_condition: bool,
        layers: RenderLayers,
    ) -> None:
        if not layers.segment_com:
            return
        table = segment_anthropometry(anthro)
        contributions = com_contributions(anthro, state.pose)
        condition = f"{condition_label} · " if include_condition else ""
        for name, contribution in contributions.items():
            point = contribution.position_m
            x, y = self.app.world_to_canvas(
                canvas, (point[0] + x_offset, point[1]), bounds
            )
            row = table[name]
            if row.com_fraction is None:
                geometry = (
                    f"ponctuelle · attache a={row.attachment_anterior_offset_m:.3f} m, "
                    f"l={row.attachment_longitudinal_offset_m:.3f} m"
                )
            else:
                geometry = (
                    f"L={row.length_m:.3f} m · f={row.com_fraction:.3f} · "
                    f"d⊥={row.com_transverse_offset_m:.3f} m"
                )
            tooltip_text = (
                f"{condition}CoM {row.label}\n"
                f"x={point[0]:.4f} m   y={point[1]:.4f} m\n"
                f"m={row.mass_kg:.3f} kg · I={row.inertia_kg_m2:.4f} kg·m²\n"
                f"mode={row.scaling_mode}\n"
                f"{geometry}\n"
                f"m·x={contribution.weighted_position_kg_m[0]:.4f} kg·m   "
                f"m·y={contribution.weighted_position_kg_m[1]:.4f} kg·m"
            )
            self._animation_hover_targets.append(
                {
                    "x": x,
                    "y": y,
                    "name": name,
                    "point": point,
                    "condition": condition_label if include_condition else "",
                    "tooltip_text": tooltip_text,
                }
            )

    def clear_animation_tooltip(self, _event: tk.Event | None = None) -> None:
        if hasattr(self, "animation_canvas"):
            self.animation_canvas.delete("scientific-tooltip")

    def on_animation_motion(self, event: tk.Event) -> None:
        self.app.clear_animation_tooltip()
        if not self._animation_hover_targets:
            return
        target = min(
            self._animation_hover_targets,
            key=lambda item: (
                (float(item["x"]) - event.x) ** 2 + (float(item["y"]) - event.y) ** 2,
                0 if item["tooltip_text"] else 1,
            ),
        )
        distance_squared = (float(target["x"]) - event.x) ** 2 + (
            float(target["y"]) - event.y
        ) ** 2
        if distance_squared > 18.0**2:
            return
        tooltip_text = str(target["tooltip_text"])
        if not tooltip_text:
            point = target["point"]
            condition = f"{target['condition']} · " if target["condition"] else ""
            label = POINT_LABELS[str(target["name"])]
            tooltip_text = (
                f"{condition}{label}\nx={point[0]:.4f} m   y={point[1]:.4f} m"
            )
        x = min(max(8, event.x + 14), max(8, self.animation_canvas.winfo_width() - 340))
        y = max(8, event.y - 12)
        text_item = self.animation_canvas.create_text(
            x,
            y,
            text=tooltip_text,
            width=320,
            anchor="sw",
            fill="#17364a",
            font=("Helvetica", 9, "bold"),
            tags="scientific-tooltip",
        )
        bbox = self.animation_canvas.bbox(text_item)
        if bbox is not None:
            background = self.animation_canvas.create_rectangle(
                bbox[0] - 5,
                bbox[1] - 4,
                bbox[2] + 5,
                bbox[3] + 4,
                fill="#eef7fb",
                outline="#276c92",
                tags="scientific-tooltip",
            )
            self.animation_canvas.tag_lower(background, text_item)
