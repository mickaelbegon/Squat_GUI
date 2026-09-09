"""Regression tests for the single-pose viewport framing."""

from math import radians

from squat_gui.anthropometry import Anthropometry
from squat_gui.app import SquatGui
from squat_gui.dynamics import DynamicsResult
from squat_gui.kinematics import MotionState, pose_from_angles
from squat_gui.kinematics import PhaseDurations
from squat_gui.rendering import RenderLayers
from squat_gui.scene_canvas import SceneCanvasController


class _Canvas:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

    def winfo_width(self) -> int:
        return self.width

    def winfo_height(self) -> int:
        return self.height


class _RecordingDragCanvas:
    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.texts: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def delete(self, tag: str) -> None:
        self.deleted.append(tag)

    def create_text(self, *args: object, **kwargs: object) -> None:
        self.texts.append((args, kwargs))


class _Var:
    def __init__(self, value: object) -> None:
        self.value = value

    def get(self) -> object:
        return self.value


class _ViewportOwner:
    @staticmethod
    def scene_bounds(**_kwargs) -> tuple[float, float, float, float]:
        return (-0.36, 1.46, -0.08, 1.92)


def test_pose_editor_viewport_centres_crouched_subject_and_reduces_dead_space():
    anthro = Anthropometry(bar_mass=20.0)
    q = (radians(22.0), radians(-58.0), radians(20.0))
    pose = pose_from_angles(anthro, q)
    state = MotionState(0.0, q, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), pose, "isometrique")
    result = DynamicsResult((0.0, 900.0), 0.12, {}, {}, {}, {}, {})
    canvas = _Canvas(360, 500)
    owner = _ViewportOwner()

    bounds = SquatGui.pose_editor_bounds(owner, canvas, state, result, anthro)
    points = (
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
    xmin = min(point[0] for point in points)
    xmax = max(point[0] for point in points)
    scale = min(
        (canvas.winfo_width() - 84) / (bounds[1] - bounds[0]),
        (canvas.winfo_height() - 84) / (bounds[3] - bounds[2]),
    )
    projected_middle = 42 + ((xmin + xmax) / 2.0 - bounds[0]) * scale

    assert abs(projected_middle - canvas.winfo_width() / 2.0) <= 1e-9
    assert bounds[0] < xmin < xmax < bounds[1]
    assert bounds[2] <= -0.16
    assert bounds[1] - bounds[0] < 1.46 - (-0.36)


def test_drag_preview_keeps_refined_raster_sprites_enabled():
    anthro = Anthropometry()
    q = (radians(22.0), radians(-58.0), radians(20.0))
    canvas = _RecordingDragCanvas()
    skeleton_calls: list[dict[str, object]] = []

    class _DragPreviewApp:
        pose_canvas = canvas
        final_q = q
        low_quality_sprites_var = _Var(False)
        _pose_drag_bounds = (-0.5, 1.5, -0.2, 2.0)
        _pose_editor_bounds = None

        @staticmethod
        def anthro() -> Anthropometry:
            return anthro

        @staticmethod
        def phase_durations() -> PhaseDurations:
            return PhaseDurations()

        @staticmethod
        def render_layers(*, refined_sprites: bool | None = None) -> RenderLayers:
            return RenderLayers(refined_sprites=bool(refined_sprites))

        @staticmethod
        def configure_alert_canvas(_canvas: object, _alerts: list[object]) -> None:
            pass

        @staticmethod
        def draw_skeleton(*_args: object, **kwargs: object) -> None:
            skeleton_calls.append(kwargs)

        @staticmethod
        def draw_squat_angle_labels(*_args: object) -> None:
            pass

        @staticmethod
        def scene_bounds() -> tuple[float, float, float, float]:
            return (-0.5, 1.5, -0.2, 2.0)

    SceneCanvasController(_DragPreviewApp()).draw_pose_drag_preview()

    assert canvas.deleted == ["all"]
    assert len(skeleton_calls) == 1
    assert skeleton_calls[0]["refined_sprites"] is True
    assert skeleton_calls[0]["use_raster_sprites"] is True
    layers = skeleton_calls[0]["layers"]
    assert isinstance(layers, RenderLayers)
    assert layers.refined_sprites is True
