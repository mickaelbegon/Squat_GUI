"""Canvas/world transforms and scene viewport fitting."""

from __future__ import annotations

import tkinter as tk

from .anthropometry import Anthropometry
from .dynamics import DynamicsResult
from .kinematics import MotionState
from .scene_model import ViewportTransform, scene_bounds as common_scene_bounds


class SceneTransformMixin:
    """Coordinate transforms shared by the pose and animation canvases."""

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
