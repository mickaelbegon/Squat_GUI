"""Single-pose and shared skeleton canvas rendering."""

from __future__ import annotations

import tkinter as tk
from math import degrees

from .anthropometry import Anthropometry
from .didactics import RevealMode
from .dynamics import GRAVITY, DynamicsResult
from .kinematics import MotionState, clinical_joint_values_from_segment_values, pose_from_angles
from .raster_segments import draw_sprite_segment
from .rendering import RenderLayers
from .scene_model import SceneGeometry, build_scene_geometry, project_point_on_line
from .scene_styles import CANVAS_BG, FORCE_DRAW_SCALE, SEGMENT_LABELS
from .segment_shapes import draw_segment, load_segments


class ScenePoseRendererMixin:
    """Render the skeleton and the interactive deep-squat pose."""

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
