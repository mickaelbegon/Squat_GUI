"""Public facade for Tk canvas rendering in the squat application.

Rendering responsibilities live in focused mixins while this controller keeps
the historical API consumed by squat_gui.app and external callers.
"""

from __future__ import annotations

from typing import Any

from .scene_animation import SceneAnimationRendererMixin
from .scene_hover import SceneHoverMixin
from .scene_overlays import SceneOverlayMixin
from .scene_pose import ScenePoseRendererMixin
from .scene_styles import (
    ALERT_BG,
    ALERT_BORDER,
    CANVAS_BG,
    FORCE_DRAW_SCALE,
    OK_BORDER,
    POINT_LABELS,
    SEGMENT_LABELS,
)
from .scene_transforms import SceneTransformMixin

__all__ = [
    "ALERT_BG",
    "ALERT_BORDER",
    "CANVAS_BG",
    "FORCE_DRAW_SCALE",
    "OK_BORDER",
    "POINT_LABELS",
    "SEGMENT_LABELS",
    "SceneCanvasController",
]


class SceneCanvasController(
    SceneTransformMixin,
    SceneOverlayMixin,
    ScenePoseRendererMixin,
    SceneAnimationRendererMixin,
    SceneHoverMixin,
):
    """Render both squat canvases for a duck-typed GUI application."""

    def __init__(self, app: Any) -> None:
        self.app = app

    def __getattr__(self, name: str) -> Any:
        """Forward application state and non-rendering services."""

        return getattr(self.app, name)
