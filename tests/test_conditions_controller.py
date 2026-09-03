"""Behavior tests for recorded-condition Tk interactions without a Tk root."""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from math import radians

from squat_gui.conditions_controller import ConditionInteractionController
from squat_gui.session_persistence import SavedCondition


class FakeButton:
    def __init__(self) -> None:
        self.states: list[tuple[str, ...]] = []

    def state(self, values: list[str]) -> None:
        self.states.append(tuple(values))


class FakeTable:
    def __init__(self, selection: tuple[str, ...] = ()) -> None:
        self.selected = selection
        self.rows: dict[str, tuple[object, ...]] = {}
        self.inserted: list[tuple[object, ...]] = []

    def selection(self) -> tuple[str, ...]:
        return self.selected

    def selection_remove(self, values: tuple[str, ...] | str) -> None:
        removed = {values} if isinstance(values, str) else set(values)
        self.selected = tuple(iid for iid in self.selected if iid not in removed)

    def get_children(self) -> tuple[str, ...]:
        return tuple(self.rows)

    def delete(self, iid: str) -> None:
        self.rows.pop(iid, None)

    def exists(self, iid: str) -> bool:
        return iid in self.rows

    def insert(self, _parent: str, _position: str, *, iid=None, values=()) -> None:
        self.inserted.append(tuple(values))
        if iid is not None:
            self.rows[iid] = tuple(values)

    def identify_row(self, _y: int) -> str:
        return ""


class FakeVariable:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def set(self, value: str) -> None:
        self.value = value


class FakeNotebook:
    def __init__(self) -> None:
        self.selected = None

    def select(self, tab: object) -> None:
        self.selected = tab


@dataclass
class FakeApp:
    conditions_table: FakeTable = field(default_factory=FakeTable)
    differences_table: FakeTable = field(default_factory=FakeTable)
    delete_condition_button: FakeButton = field(default_factory=FakeButton)
    duplicate_condition_button: FakeButton = field(default_factory=FakeButton)
    table_notebook: FakeNotebook = field(default_factory=FakeNotebook)
    differences_tab: object = field(default_factory=object)
    saved_conditions: dict[str, SavedCondition] = field(default_factory=dict)
    saved_condition_count: int = 1
    _comparison_reference_iid: str | None = None
    final_q: tuple[float, float, float] = (radians(20), radians(-60), radians(25))
    status_var: FakeVariable = field(default_factory=FakeVariable)
    applied_settings: dict[str, object] | None = None
    redraw_count: int = 0
    plot_choices_count: int = 0
    table_tab_changed_count: int = 0

    def current_settings(self) -> dict[str, object]:
        return {"subject_profile": "homme", "load_percent_bw": 0.0}

    def update_plot_choices(self) -> None:
        self.plot_choices_count += 1

    def redraw(self) -> None:
        self.redraw_count += 1

    def apply_settings(self, settings: dict[str, object]) -> None:
        self.applied_settings = settings

    def on_table_tab_changed(self) -> None:
        self.table_tab_changed_count += 1


def saved_condition(label: str = "1") -> SavedCondition:
    return SavedCondition(
        label=label,
        settings={"subject_profile": "homme", "load_percent_bw": 25.0},
        final_q_deg=[20.0, -60.0, 25.0],
        states=[],
        results=[],
    )


class ConditionsControllerTests(unittest.TestCase):
    def test_selection_updates_actions_and_dependent_views(self) -> None:
        app = FakeApp(conditions_table=FakeTable(("one",)))
        controller = ConditionInteractionController(
            app, confirm_delete=lambda *_args, **_kw: True
        )

        controller.on_selection_changed()

        self.assertEqual(app.delete_condition_button.states[-1], ("!disabled",))
        self.assertEqual(app.duplicate_condition_button.states[-1], ("!disabled",))
        self.assertEqual(app.plot_choices_count, 1)
        self.assertEqual(app.redraw_count, 1)

    def test_duplicate_loads_snapshot_and_shows_comparison_tab(self) -> None:
        app = FakeApp(conditions_table=FakeTable(("one",)))
        app.saved_conditions = {"one": saved_condition("référence")}
        controller = ConditionInteractionController(
            app, confirm_delete=lambda *_args, **_kw: True
        )

        controller.duplicate_selected()

        self.assertEqual(app._comparison_reference_iid, "one")
        self.assertEqual(app.applied_settings["final_q_deg"], [20.0, -60.0, 25.0])
        self.assertEqual(app.table_notebook.selected, app.differences_tab)
        self.assertEqual(app.table_tab_changed_count, 1)
        self.assertIn("dupliquée", app.status_var.value)

    def test_delete_removes_selected_record_after_confirmation(self) -> None:
        app = FakeApp(conditions_table=FakeTable(("one",)))
        app.conditions_table.rows["one"] = ("référence",)
        app.saved_conditions = {"one": saved_condition("référence")}
        controller = ConditionInteractionController(
            app, confirm_delete=lambda *_args, **_kw: True
        )

        controller.delete_selected()

        self.assertNotIn("one", app.saved_conditions)
        self.assertFalse(app.conditions_table.exists("one"))
        self.assertEqual(app.status_var.value, "1 condition(s) supprimee(s)")


if __name__ == "__main__":
    unittest.main()
