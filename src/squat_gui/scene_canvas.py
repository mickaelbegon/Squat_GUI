"""Tk canvas rendering and overlays for the squat application.

This controller owns the widget-facing scene renderer while the application
continues to expose its historical drawing methods as thin delegates. The
scientific geometry remains in :mod:`squat_gui.scene_model`, and raster
preparation remains in :mod:`squat_gui.raster_segments`.
"""

from __future__ import annotations

import tkinter as tk
from math import degrees
from typing import Any, cast

from .anthropometry import Anthropometry
from .didactics import RevealMode
from .dynamics import GRAVITY, DynamicsResult, force_balance
from .kinematics import (
    MotionState,
    clinical_joint_values_from_segment_values,
    joint_angles_from_pose,
    pose_from_angles,
    segment_orientations,
)
from .observables import (
    com_contributions,
    joint_coordinates,
    neighbor_samples,
    segment_anthropometry,
    support_margins,
)
from .plot_data import PlotSample
from .raster_segments import draw_sprite_segment
from .rendering import RenderLayers
from .scene_model import (
    SceneGeometry,
    ViewportTransform,
    build_scene_geometry,
    project_point_on_line,
    scene_bounds as common_scene_bounds,
)
from .segment_shapes import draw_segment, load_segments

FORCE_DRAW_SCALE = 3500.0 / 3.0
CANVAS_BG = "#fbfcf9"
ALERT_BG = "#ffe7e3"
OK_BORDER = "#587a5f"
ALERT_BORDER = "#c9332c"
POINT_LABELS = {
    "ankle": "cheville",
    "knee": "genou",
    "hip": "hanche",
    "shoulder": "épaule",
    "bar": "centre barre",
}
SEGMENT_LABELS = {
    "foot": "pied",
    "shank": "jambe",
    "thigh": "cuisse",
    "trunk": "tronc",
    "bar": "barre",
}


class SceneCanvasController:
    """Render both squat canvases for a duck-typed GUI application."""

    def __init__(self, app: Any) -> None:
        self.app = app

    def __getattr__(self, name: str) -> Any:
        """Forward application state and non-rendering services."""

        return getattr(self.app, name)

    def world_to_canvas(
        self,
        canvas: tk.Canvas,
        point: tuple[float, float],
        bounds: tuple[float, float, float, float],
    ) -> tuple[float, float]:
        viewport = ViewportTransform(
            max(1, canvas.winfo_width()),
            max(1, canvas.winfo_height()),
            bounds,
            42,
        )
        return viewport.world_to_pixel(point)

    def canvas_to_world(
        self,
        canvas: tk.Canvas,
        x: float,
        y: float,
        bounds: tuple[float, float, float, float],
    ) -> tuple[float, float]:
        viewport = ViewportTransform(
            max(1, canvas.winfo_width()),
            max(1, canvas.winfo_height()),
            bounds,
            42,
        )
        return viewport.pixel_to_world((x, y))

    def scene_bounds(
        self,
        extra_x: float = 0.0,
        anthropometries: list[Anthropometry] | None = None,
    ) -> tuple[float, float, float, float]:
        return common_scene_bounds(anthropometries or [self.anthro()], extra_x=extra_x)

    def pose_editor_bounds(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        result: DynamicsResult,
        anthro: Anthropometry,
    ) -> tuple[float, float, float, float]:
        """Fit the single-pose viewport to the displayed subject.

        ``scene_bounds`` intentionally reserves space to the right for every
        possible animation and for side-by-side conditions.  Reusing it for
        the pose editor left a crouched subject at the far left of its own
        canvas.  Here the vertical reference is kept stable (so force and
        support annotations remain comparable), while the horizontal extent is
        centred on the actual subject and expanded only as much as the canvas
        aspect ratio requires.
        """
        pose = state.pose
        subject_points = (
            pose.heel,
            pose.toe,
            pose.ankle,
            pose.knee,
            pose.hip,
            pose.shoulder,
            pose.bar,
            pose.com,
            *pose.segment_coms.values(),
            (result.cop_x, 0.0),
        )
        subject_xmin = min(point[0] for point in subject_points) - 0.18
        subject_xmax = max(point[0] for point in subject_points) + 0.18

        # Keep room below the foot for the geometric/functional-base labels.
        _, _, _, ymax = self.app.scene_bounds(anthropometries=[anthro])
        ymin = -0.16
        pad = 42
        drawable_width = max(1, canvas.winfo_width() - 2 * pad)
        drawable_height = max(1, canvas.winfo_height() - 2 * pad)
        aspect_width = (ymax - ymin) * drawable_width / drawable_height
        required_width = max(subject_xmax - subject_xmin, aspect_width)
        centre_x = (subject_xmin + subject_xmax) / 2.0
        return (
            centre_x - required_width / 2.0,
            centre_x + required_width / 2.0,
            ymin,
            ymax,
        )

    def cop_in_foot(self, state: MotionState, result: DynamicsResult) -> bool:
        return support_margins(state.pose, result.cop_x).in_geometric_base

    def support_point_in_functional_base(
        self, state: MotionState, result: DynamicsResult
    ) -> bool:
        return support_margins(state.pose, result.cop_x).in_functional_base

    def com_projection_in_foot(self, state: MotionState) -> bool:
        return support_margins(state.pose, state.pose.com[0]).in_geometric_base

    def over_limit_joints(self, result: DynamicsResult) -> list[str]:
        return [
            joint
            for joint in ("cheville", "genou", "hanche")
            if result.effort_ratios[joint] is None or result.effort_ratios[joint] > 1.0
        ]

    def biomechanical_alerts(
        self, state: MotionState, result: DynamicsResult, include_com: bool
    ) -> list[str]:
        alerts = []
        if not self.app.support_point_in_functional_base(state, result):
            alerts.append(
                f"{result.support_point_label} hors zone fonctionnelle d'appui"
            )
        if include_com and not self.app.com_projection_in_foot(state):
            alerts.append("CoM hors pied")
        over_limit = self.app.over_limit_joints(result)
        if over_limit:
            alerts.append(
                "faisabilité mécanique U > 1 sous les hypothèses du modèle: "
                + ", ".join(over_limit)
            )
        return alerts

    def configure_alert_canvas(self, canvas: tk.Canvas, alerts: list[str]) -> None:
        focus_color = self._didactic_canvas_colors.get(canvas)
        if alerts:
            canvas.configure(
                bg=ALERT_BG, highlightbackground=ALERT_BORDER, highlightthickness=4
            )
        else:
            canvas.configure(
                bg=CANVAS_BG,
                highlightbackground=focus_color or OK_BORDER,
                highlightthickness=4 if focus_color else 2,
            )

    def draw_alert_banner(self, canvas: tk.Canvas, alerts: list[str], y: int) -> None:
        if not alerts:
            return
        text = "Problèmes biomécaniques :\n" + "\n".join(
            f"• {alert}" for alert in alerts
        )
        item = canvas.create_text(
            16,
            y,
            text=text,
            anchor="nw",
            fill="#8a1f17",
            font=("Helvetica", 10, "bold"),
            width=max(120, canvas.winfo_width() - 32),
        )
        bbox = canvas.bbox(item)
        if bbox is not None:
            background = canvas.create_rectangle(
                bbox[0] - 5,
                bbox[1] - 3,
                bbox[2] + 5,
                bbox[3] + 3,
                fill="#ffd2cb",
                outline=ALERT_BORDER,
            )
            canvas.tag_lower(background, item)

    def draw_skeleton(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        result: DynamicsResult,
        with_handles: bool,
        bounds: tuple[float, float, float, float] | None = None,
        x_offset: float = 0.0,
        render_anthro: Anthropometry | None = None,
        refined_sprites: bool | None = None,
        layers: RenderLayers | None = None,
    ) -> None:
        render_anthro = render_anthro or self.anthro()
        refined_sprites = (
            not self.low_quality_sprites_var.get()
            if refined_sprites is None
            else refined_sprites
        )
        layers = layers or self.render_layers(refined_sprites=refined_sprites)
        bounds = bounds or self.app.scene_bounds()
        scene = build_scene_geometry(
            render_anthro, state, result.cop_x, x_offset=x_offset
        )
        points = {
            name: self.app.world_to_canvas(canvas, scene.point(name), bounds)
            for name in ("heel", "toe", "ankle", "knee", "hip", "shoulder")
        }
        if not hasattr(canvas, "_sprite_images"):
            canvas._sprite_images = []

        def mapper(point: tuple[float, float]) -> tuple[float, float]:
            return self.app.world_to_canvas(canvas, point, bounds)

        raster_drawn = self.app.draw_raster_segments(
            canvas,
            state,
            mapper,
            render_anthro,
            refined_sprites,
            scene=scene,
        )
        if not raster_drawn:
            segments = load_segments()
            foot_scale = render_anthro.foot.length / 1.07
            draw_segment(
                canvas,
                segments["foot"],
                scene.point("ankle"),
                -render_anthro.wedge_angle,
                foot_scale,
                mapper,
                minimum_world_y=0.0,
            )
            draw_segment(
                canvas,
                segments["shank"],
                scene.point("ankle"),
                -state.q[0],
                render_anthro.shank.length,
                mapper,
            )
            draw_segment(
                canvas,
                segments["thigh"],
                scene.point("knee"),
                -state.q[1],
                render_anthro.thigh.length,
                mapper,
            )
            draw_segment(
                canvas,
                segments["trunk_bar"],
                scene.point("hip"),
                -state.q[2],
                render_anthro.trunk.length,
                mapper,
            )
        canvas.create_line(*points["heel"], *points["toe"], width=3, fill="#333333")

        def draw_support_interval(
            limits: tuple[float, float],
            vertical_offset: int,
            color: str,
            label: str,
        ) -> None:
            posterior_px = self.app.world_to_canvas(canvas, (limits[0], 0.0), bounds)
            anterior_px = self.app.world_to_canvas(canvas, (limits[1], 0.0), bounds)
            y = posterior_px[1] + vertical_offset
            canvas.create_line(
                posterior_px[0], y, anterior_px[0], y, fill=color, width=3
            )
            for x in (posterior_px[0], anterior_px[0]):
                canvas.create_line(x, y - 5, x, y + 5, fill=color, width=2)
            canvas.create_text(
                (posterior_px[0] + anterior_px[0]) / 2.0,
                y + 6,
                text=label,
                anchor="n",
                fill=color,
                font=("Helvetica", 7, "bold"),
            )

        if layers.geometric_base:
            draw_support_interval(
                scene.geometric_support.limits, 8, "#506158", "base géométrique"
            )
        if layers.functional_base:
            functional_offset = 24 if layers.geometric_base else 10
            draw_support_interval(
                scene.functional_support.limits,
                functional_offset,
                "#9a5b16",
                "zone fonctionnelle",
            )
        if scene.wedge_polygon is not None:
            heel, toe, floor_heel = tuple(
                self.app.world_to_canvas(canvas, point, bounds)
                for point in scene.wedge_polygon
            )
            wedge_item = canvas.create_polygon(
                heel[0],
                heel[1],
                toe[0],
                toe[1],
                floor_heel[0],
                floor_heel[1],
                fill="#d9c39b",
                outline="#7d6542",
            )
            canvas.tag_lower(wedge_item)

        com = self.app.world_to_canvas(canvas, scene.point("com"), bounds)
        projection = self.app.world_to_canvas(canvas, scene.com_projection, bounds)
        if layers.global_com and layers.com_projection:
            canvas.create_line(
                com[0],
                com[1],
                projection[0],
                projection[1],
                fill="#3d7580",
                dash=(4, 4),
                width=1,
            )
        if layers.global_com:
            canvas.create_oval(
                com[0] - 7,
                com[1] - 7,
                com[0] + 7,
                com[1] + 7,
                fill="#2c9ab7",
                outline="",
            )
        if layers.com_projection:
            canvas.create_oval(
                projection[0] - 5,
                projection[1] - 5,
                projection[0] + 5,
                projection[1] + 5,
                fill="#2c9ab7",
                outline="",
            )
        if layers.segment_com:
            for segment_com in scene.segment_coms:
                px = self.app.world_to_canvas(canvas, segment_com.position, bounds)
                canvas.create_oval(
                    px[0] - 4,
                    px[1] - 4,
                    px[0] + 4,
                    px[1] + 4,
                    fill="#e64357",
                    outline="#ffffff",
                )
                canvas.create_text(
                    px[0] + 6,
                    px[1] - 6,
                    text=SEGMENT_LABELS[segment_com.name],
                    anchor="sw",
                    fill="#8a1f32",
                    font=("Helvetica", 8, "bold"),
                )

        cop = self.app.world_to_canvas(canvas, scene.support_point, bounds)
        if layers.cop_zmp:
            canvas.create_oval(
                cop[0] - 5,
                cop[1] - 5,
                cop[0] + 5,
                cop[1] + 5,
                fill="#c15a2b",
                outline="#ffffff",
            )
            canvas.create_text(
                cop[0] + 7,
                cop[1] - 7,
                text=result.support_point_label,
                anchor="sw",
                fill="#8a3f1f",
                font=("Helvetica", 8, "bold"),
            )
        if layers.grf:
            force_end = self.app.world_to_canvas(
                canvas,
                (
                    scene.support_point[0]
                    + result.ground_reaction[0] / FORCE_DRAW_SCALE,
                    result.ground_reaction[1] / FORCE_DRAW_SCALE,
                ),
                bounds,
            )
            canvas.create_line(
                cop[0],
                cop[1],
                force_end[0],
                force_end[1],
                arrow=tk.LAST,
                width=3,
                fill="#c15a2b",
            )
            canvas.create_text(
                force_end[0] + 5,
                force_end[1],
                text="GRF",
                anchor="w",
                fill="#8a3f1f",
                font=("Helvetica", 8, "bold"),
            )
        if layers.weight:
            weight = render_anthro.total_mass * GRAVITY
            weight_end = self.app.world_to_canvas(
                canvas,
                (
                    scene.point("com")[0],
                    scene.point("com")[1] - weight / FORCE_DRAW_SCALE,
                ),
                bounds,
            )
            canvas.create_line(
                com[0],
                com[1],
                weight_end[0],
                weight_end[1],
                arrow=tk.LAST,
                width=3,
                fill="#315f8a",
            )
            canvas.create_text(
                weight_end[0] + 5,
                weight_end[1],
                text=f"P={weight:.0f} N",
                anchor="w",
                fill="#315f8a",
                font=("Helvetica", 8, "bold"),
            )
        if layers.moment_arms:
            for joint in (scene.point("knee"), scene.point("hip")):
                projected = project_point_on_line(
                    joint, scene.support_point, result.ground_reaction
                )
                joint_px = self.app.world_to_canvas(canvas, joint, bounds)
                projected_px = self.app.world_to_canvas(canvas, projected, bounds)
                canvas.create_line(
                    joint_px[0],
                    joint_px[1],
                    projected_px[0],
                    projected_px[1],
                    fill="#1f77b4",
                    dash=(4, 4),
                    width=2,
                )
                canvas.create_oval(
                    projected_px[0] - 3,
                    projected_px[1] - 3,
                    projected_px[0] + 3,
                    projected_px[1] + 3,
                    fill="#1f77b4",
                    outline="",
                )

        if layers.capacity_rings:
            for name in ("cheville", "genou", "hanche"):
                utilization = result.effort_ratios[name]
                ratio = 1.0 if utilization is None else min(1.0, utilization)
                red = int(40 + 190 * ratio)
                green = int(170 * max(0.0, 1.0 - max(0.0, ratio - 0.5) * 2.0))
                color = f"#{red:02x}{green:02x}35"
                point = {
                    "cheville": scene.point("ankle"),
                    "genou": scene.point("knee"),
                    "hanche": scene.point("hip"),
                }[name]
                px = self.app.world_to_canvas(canvas, point, bounds)
                canvas.create_oval(
                    px[0] - 12,
                    px[1] - 12,
                    px[0] + 12,
                    px[1] + 12,
                    outline=color,
                    width=4,
                )
        if layers.joint_markers:
            for name in ("ankle", "knee", "hip", "shoulder"):
                x, y = points[name]
                canvas.create_oval(
                    x - 6,
                    y - 6,
                    x + 6,
                    y + 6,
                    fill="#ffffff",
                    outline="#1f1f1f",
                    width=2,
                )
        if self.reveal_mode() is RevealMode.FREE and self.show_sprite_centers_var.get():
            for name in ("ankle", "knee", "hip", "shoulder", "toe"):
                x, y = points[name]
                canvas.create_line(x - 12, y, x + 12, y, fill="#26a69a", width=2)
                canvas.create_line(x, y - 12, x, y + 12, fill="#26a69a", width=2)

        if with_handles:
            for name in ("knee", "hip", "shoulder"):
                x, y = points[name]
                canvas.create_oval(
                    x - 9,
                    y - 9,
                    x + 9,
                    y + 9,
                    fill="#f7f7f2",
                    outline="#1d3d35",
                    width=2,
                    tags=name,
                )

    def draw_raster_segments(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        mapper,
        render_anthro: Anthropometry | None = None,
        refined_sprites: bool | None = None,
        *,
        scene: SceneGeometry | None = None,
        sprite_drawer=draw_sprite_segment,
    ) -> bool:
        try:
            render_anthro = render_anthro or self.anthro()
            refined = (
                not self.low_quality_sprites_var.get()
                if refined_sprites is None
                else refined_sprites
            )
            scene = scene or build_scene_geometry(render_anthro, state, 0.0)
            return all(
                sprite_drawer(
                    canvas,
                    segment.name,
                    segment.distal,
                    segment.proximal,
                    mapper,
                    refined,
                    segment.variant,
                    0.0 if segment.name == "foot" else None,
                )
                for segment in scene.segments
            )
        except Exception:
            return False

    def draw_pose_editor(self) -> None:
        canvas = self.pose_canvas
        canvas.delete("all")
        canvas._sprite_images = []
        anthro = self.anthro()
        pose = pose_from_angles(anthro, self.final_q)
        state = MotionState(
            self.phase_durations().squat_reference_time,
            self.final_q,
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            pose,
            "isometrique",
        )
        result = min(
            self.results,
            key=lambda item: (
                abs(item.com[0] - state.pose.com[0])
                + abs(item.com[1] - state.pose.com[1])
            ),
        )
        layers = self.render_layers(
            refined_sprites=not self.low_quality_sprites_var.get()
        )
        alerts = (
            self.app.biomechanical_alerts(state, result, include_com=True)
            if layers.alerts
            else []
        )
        bounds = self.app.pose_editor_bounds(canvas, state, result, anthro)
        self.app._pose_editor_bounds = bounds
        self.app.configure_alert_canvas(canvas, alerts)
        self.app.draw_skeleton(
            canvas,
            state,
            result,
            with_handles=True,
            bounds=bounds,
            render_anthro=anthro,
            refined_sprites=not self.low_quality_sprites_var.get(),
            layers=layers,
        )
        if layers.joint_angles:
            self.app.draw_squat_angle_labels(canvas, state, bounds)
        canvas.create_text(
            16,
            16,
            text="Position de squat",
            anchor="nw",
            fill="#22312a",
            font=("Helvetica", 13, "bold"),
        )
        canvas.create_text(
            16, 38, text="Glisser genou, hanche ou epaules", anchor="nw", fill="#506158"
        )
        canvas.create_text(
            16,
            54,
            text="Clic droit : angle précis sous l'image (Entrée ou Valider)",
            anchor="nw",
            fill="#506158",
            font=("Helvetica", 8),
        )
        if layers.alerts:
            self.app.draw_alert_banner(canvas, alerts, 74)

    def draw_squat_angle_labels(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        bounds: tuple[float, float, float, float] | None = None,
    ) -> None:
        pose = state.pose
        bounds = bounds or self.app.scene_bounds()
        joint_angles = clinical_joint_values_from_segment_values(state.q)
        width = max(1, canvas.winfo_width())
        canvas_height = max(1, getattr(canvas, "winfo_height", lambda: 480)())
        if canvas_height <= 1:
            canvas_height = 480
        # Keep the values in left/right lanes, but line each one up with its
        # actual joint.  A small vertical separation is applied only when two
        # labels would otherwise overlap in a compact viewport.
        joint_points = {
            "cheville": pose.ankle,
            "hanche": pose.hip,
            "genou": pose.knee,
        }
        desired_y = {
            name: max(
                74,
                min(
                    canvas_height - 18,
                    self.app.world_to_canvas(canvas, point, bounds)[1],
                ),
            )
            for name, point in joint_points.items()
        }

        def separated_lane(names: tuple[str, ...]) -> dict[str, float]:
            gap = 24
            floor = 74
            ceiling = canvas_height - 18
            placed: dict[str, float] = {}
            previous = floor - gap
            for name in sorted(names, key=desired_y.__getitem__):
                placed[name] = max(desired_y[name], previous + gap, floor)
                previous = placed[name]
            overflow = max(0.0, max(placed.values()) - ceiling)
            if overflow:
                placed = {name: max(floor, y - overflow) for name, y in placed.items()}
            return placed

        left_y = separated_lane(("cheville", "hanche"))
        labels = (
            (
                "cheville",
                degrees(joint_angles["cheville"]),
                14,
                left_y["cheville"],
                "nw",
            ),
            ("hanche", degrees(joint_angles["hanche"]), 14, left_y["hanche"], "nw"),
            (
                "genou",
                degrees(joint_angles["genou"]),
                width - 14,
                desired_y["genou"],
                "ne",
            ),
        )
        for name, value, x, y, anchor in labels:
            item = canvas.create_text(
                x,
                y,
                text=f"{name}: {value:.0f} deg",
                anchor=anchor,
                fill="#22312a",
                font=("Helvetica", 9, "bold"),
            )
            bbox = canvas.bbox(item)
            if bbox is not None:
                background = canvas.create_rectangle(
                    bbox[0] - 3,
                    bbox[1] - 2,
                    bbox[2] + 3,
                    bbox[3] + 2,
                    fill=CANVAS_BG,
                    outline="#c9d1c7",
                )
                canvas.tag_lower(background, item)

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

    def draw_anthropometry_overlay(
        self,
        canvas: tk.Canvas,
        anthro: Anthropometry,
        condition_label: str,
        top_y: int,
    ) -> int:
        table = segment_anthropometry(anthro)
        title = "Anthropométrie utilisée"
        if condition_label:
            title += f" · {condition_label}"
        lines = [title]
        lines.append(f"mode: {anthro.scaling_mode}")
        for key in ("foot", "shank", "thigh", "trunk"):
            row = table[key]
            lines.append(
                f"{row.label}: L={row.length_m:.3f} m · m={row.mass_kg:.2f} kg · f={row.com_fraction:.3f}"
            )
        lines.append(f"barre ponctuelle: m={anthro.bar_mass:.2f} kg")
        lines.append(f"masse totale: {anthro.total_mass:.2f} kg")
        text_item = canvas.create_text(
            max(10, canvas.winfo_width() - 12),
            top_y,
            text="\n".join(lines),
            anchor="ne",
            justify="left",
            fill="#17364a",
            font=("Helvetica", 8, "bold"),
            tags="anthropometry-overlay",
        )
        bbox = canvas.bbox(text_item)
        if bbox is not None:
            background = canvas.create_rectangle(
                bbox[0] - 7,
                bbox[1] - 6,
                bbox[2] + 7,
                bbox[3] + 6,
                fill="#f4faf7",
                outline="#587a5f",
                tags="anthropometry-overlay",
            )
            canvas.tag_lower(background, text_item)
            return bbox[3] + 12
        return top_y

    def draw_force_balance_overlay(
        self,
        canvas: tk.Canvas,
        anthro: Anthropometry,
        state: MotionState,
        result: DynamicsResult,
        top_y: int,
    ) -> int:
        balance = force_balance(anthro, result)
        point = support_margins(state.pose, result.cop_x)
        com_projection = support_margins(state.pose, state.pose.com[0])
        lines = [
            "Bilan forces et équilibre",
            "repère: +x avant · +y haut",
            f"P=(0, {balance.weight_vector_N[1]:.1f}) N",
            f"GRF=({result.ground_reaction[0]:.1f}, {result.ground_reaction[1]:.1f}) N",
            f"GRF + P − m·a=({balance.residual_N[0]:.2e}, {balance.residual_N[1]:.2e}) N",
            f"{result.support_point_label}: x={result.cop_x:.4f} m · {result.support_point_source}",
            (
                f"base géom.=[{point.geometric_posterior_m:.4f}, "
                f"{point.geometric_anterior_m:.4f}] m"
            ),
            (
                f"zone fonct.=[{point.functional_posterior_m:.4f}, "
                f"{point.functional_anterior_m:.4f}] m"
            ),
            (
                f"marges {result.support_point_label} fonct.: "
                f"post.={point.functional_posterior_margin_m:.4f} · "
                f"ant.={point.functional_anterior_margin_m:.4f} m"
            ),
            (
                f"projection CoM: x={state.pose.com[0]:.4f} m · "
                f"géom.={'oui' if com_projection.in_geometric_base else 'non'}"
            ),
        ]
        text_item = canvas.create_text(
            max(10, canvas.winfo_width() - 12),
            top_y,
            text="\n".join(lines),
            width=330,
            anchor="ne",
            justify="left",
            fill="#4f3518",
            font=("Helvetica", 9, "bold"),
            tags="force-balance-overlay",
        )
        bbox = canvas.bbox(text_item)
        if bbox is not None:
            background = canvas.create_rectangle(
                bbox[0] - 7,
                bbox[1] - 6,
                bbox[2] + 7,
                bbox[3] + 6,
                fill="#fff8e8",
                outline="#9a5b16",
                tags="force-balance-overlay",
            )
            canvas.tag_lower(background, text_item)
            return bbox[3] + 12
        return top_y

    def draw_neighbor_samples_overlay(
        self,
        canvas: tk.Canvas,
        states: list[MotionState],
        frame: int,
    ) -> None:
        samples = neighbor_samples(states, frame)
        labels = ("i−1", "i", "i+1")
        lines = ["Échantillons pour dérivation manuelle"]
        for label, sample in zip(labels, samples):
            if sample is None:
                lines.append(f"{label}: indisponible")
                continue
            angles = tuple(degrees(value) for value in sample.joint_angles_rad)
            lines.append(
                f"{label} · F{sample.frame} · t={sample.time_s:.3f} s · {sample.phase}"
            )
            lines.append(
                f"  CoM=({sample.com_m[0]:.4f}, {sample.com_m[1]:.4f}) m · "
                f"θ=({angles[0]:.1f}, {angles[1]:.1f}, {angles[2]:.1f})°"
            )
        previous, current, following = samples
        dt_previous = (
            "—"
            if previous is None or current is None
            else f"{current.time_s - previous.time_s:.3f} s"
        )
        dt_following = (
            "—"
            if following is None or current is None
            else f"{following.time_s - current.time_s:.3f} s"
        )
        lines.append(f"Δt−={dt_previous} · Δt+={dt_following}")
        text_item = canvas.create_text(
            max(10, canvas.winfo_width() - 12),
            max(10, canvas.winfo_height() - 12),
            text="\n".join(lines),
            width=330,
            anchor="se",
            justify="left",
            fill="#3d315f",
            font=("Helvetica", 9, "bold"),
            tags="neighbor-samples-overlay",
        )
        bbox = canvas.bbox(text_item)
        if bbox is not None:
            background = canvas.create_rectangle(
                bbox[0] - 7,
                bbox[1] - 6,
                bbox[2] + 7,
                bbox[3] + 6,
                fill="#f6f2fb",
                outline="#6d5ea8",
                tags="neighbor-samples-overlay",
            )
            canvas.tag_lower(background, text_item)

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
