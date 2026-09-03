from __future__ import annotations

from types import SimpleNamespace

from squat_gui.app import SquatGui
from squat_gui.didactics import RevealMode
from squat_gui.plot_controller import PlotCanvasController


class FakeVariable:
    def __init__(self, value: object = "") -> None:
        self.value = value

    def get(self) -> object:
        return self.value

    def set(self, value: object) -> None:
        self.value = value


class RecordingCanvas:
    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.texts: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def delete(self, tag: str) -> None:
        self.deleted.append(tag)

    def winfo_width(self) -> int:
        return 420

    def winfo_height(self) -> int:
        return 240

    def create_text(self, *args: object, **kwargs: object) -> int:
        self.texts.append((args, kwargs))
        return len(self.texts)


def test_observation_plot_is_rendered_without_preparing_series() -> None:
    canvas = RecordingCanvas()
    cursor_updates: list[object] = []
    notice_updates: list[object] = []
    app = SimpleNamespace(
        plot_canvas=canvas,
        plot_title_var=FakeVariable(),
        _plot_hit_regions=[("stale",)],
        plot_datasets=lambda: [],
        update_time_mode_notice=notice_updates.append,
        reveal_mode=lambda: RevealMode.OBSERVATION,
        update_cursor_table=cursor_updates.append,
    )

    PlotCanvasController(app).draw_plot()

    assert canvas.deleted == ["all"]
    assert app._plot_hit_regions == []
    assert notice_updates == [[]]
    assert cursor_updates == [[]]
    assert app.plot_title_var.get() == "OBSERVATION — courbes masquées"
    assert "formulez une hypothèse" in str(canvas.texts[0][1]["text"])


def test_squat_gui_keeps_plot_series_as_a_compatibility_delegate() -> None:
    calls: list[tuple[str, object, object]] = []

    class StubController:
        def plot_series_for(self, choice: str, states: object, results: object):
            calls.append((choice, states, results))
            return {"cheville": [1.0]}

    app = object.__new__(SquatGui)
    app.__dict__["_plot_controller"] = StubController()
    states = [object()]
    results = [object()]

    series = app.plot_series_for("couples articulaires", states, results)

    assert series == {"cheville": [1.0]}
    assert calls == [("couples articulaires", states, results)]


def test_lazy_controller_and_missing_cursor_table_work_without_tcl() -> None:
    app = object.__new__(SquatGui)

    app.clear_cursor_table()

    assert isinstance(app.__dict__["_plot_controller"], PlotCanvasController)
