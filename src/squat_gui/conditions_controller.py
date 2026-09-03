"""Tk-facing interactions for the recorded-conditions workspace.

The scientific representation of a recorded condition lives in
``condition_store``.  This controller deliberately owns only the small amount
of presentation state that connects that representation to a ``Treeview`` and
the active editor.  Keeping it here prevents :mod:`squat_gui.app` from mixing
widget callbacks, comparison rules, and saved-condition construction.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from math import degrees, radians
from typing import Any

from .condition_store import (
    ConditionComparison,
    comparison_reference,
    condition_table_metrics,
    create_saved_condition,
    resolve_condition_comparison,
    selected_conditions,
)
from .dynamics import DynamicsResult
from .kinematics import MotionState
from .session_persistence import ComparisonReference


class ConditionInteractionController:
    """Coordinate saved-condition controls for one GUI application instance.

    ``app`` is intentionally duck-typed: it is the existing Tk application and
    supplies domain-specific services (current settings, simulation, pose
    formatting, redraw).  The controller has no import dependency on the app,
    which keeps the presentation logic unit-testable without a Tk root.
    """

    def __init__(
        self,
        app: Any,
        *,
        confirm_delete: Callable[..., bool],
    ) -> None:
        self.app = app
        self.confirm_delete = confirm_delete

    def on_selection_changed(self) -> None:
        """Refresh widgets and dependent views after table selection changes."""

        self.update_buttons()
        self.update_differences()
        self.app.update_plot_choices()
        self.app.redraw()

    def update_buttons(self) -> None:
        selected = self.app.conditions_table.selection()
        self.app.delete_condition_button.state(
            ["!disabled"] if selected else ["disabled"]
        )
        self.app.duplicate_condition_button.state(
            ["!disabled"] if len(selected) == 1 else ["disabled"]
        )

    def clear_differences(self) -> None:
        table = getattr(self.app, "differences_table", None)
        if table is None:
            return
        for iid in table.get_children():
            table.delete(iid)

    def show_differences(
        self,
        reference_settings: Mapping[str, object],
        reference_final_q_deg: list[float],
        compared_settings: Mapping[str, object],
        compared_final_q_deg: list[float],
    ) -> None:
        """Render the resolved scientific differences in the comparison tab."""

        self.clear_differences()
        comparison = ConditionComparison(
            "référence",
            dict(reference_settings),
            reference_final_q_deg,
            "comparée",
            dict(compared_settings),
            compared_final_q_deg,
        )
        if not comparison.differences:
            self.app.differences_table.insert(
                "",
                "end",
                values=("Aucun paramètre scientifique modifié", "—", "—"),
            )
            return
        for difference in comparison.differences:
            self.app.differences_table.insert(
                "",
                "end",
                values=(difference.label, difference.reference, difference.compared),
            )

    def update_differences(self) -> None:
        """Resolve and display the comparison selected by the table."""

        if not hasattr(self.app, "differences_table"):
            return
        selected_ids = self.app.conditions_table.selection()
        current_settings = None
        current_final_q_deg = None
        if not selected_ids:
            current_settings = self.app.current_settings()
            current_final_q_deg = [degrees(value) for value in self.app.final_q]
        comparison = resolve_condition_comparison(
            self.app.saved_conditions,
            selected_ids,
            pending_reference_iid=self.app._comparison_reference_iid,
            current_settings=current_settings,
            current_final_q_deg=current_final_q_deg,
        )
        if comparison is not None:
            self.show_differences(
                comparison.reference_settings,
                comparison.reference_final_q_deg,
                comparison.compared_settings,
                comparison.compared_final_q_deg,
            )
            return
        self.clear_differences()
        self.app.differences_table.insert(
            "",
            "end",
            values=("Sélectionnez deux conditions ou utilisez Dupliquer", "", ""),
        )

    def clear_selection(self) -> None:
        selected = self.app.conditions_table.selection()
        if selected:
            self.app.conditions_table.selection_remove(selected)
            self.update_buttons()
            self.update_differences()
            self.app.update_plot_choices()

    def on_table_click(self, event: Any) -> None:
        """Clear selection when clicking the empty part of the table."""

        if not self.app.conditions_table.identify_row(event.y):
            selected = self.app.conditions_table.selection()
            if selected:
                self.app.conditions_table.selection_remove(selected)
                self.on_selection_changed()

    def record(self) -> str:
        """Record the active editor state and preserve duplicate provenance."""

        reference_snapshot = None
        reference_iid = self.app._comparison_reference_iid
        if reference_iid in self.app.saved_conditions:
            reference_snapshot = comparison_reference(
                self.app.saved_conditions[reference_iid]
            )
        condition_iid = self.add_saved_condition(
            self.app.current_settings(),
            [degrees(value) for value in self.app.final_q],
            states=list(self.app.states),
            results=list(self.app.results),
            comparison_reference=reference_snapshot,
        )
        summary = self.app.saved_conditions[condition_iid].difference_summary
        self.app.status_var.set(
            f"condition {self.app.saved_condition_count} enregistrée · {summary}"
        )
        self.app._comparison_reference_iid = None
        return condition_iid

    def clear(self) -> None:
        """Remove all records without changing the active editor."""

        self.app.saved_conditions.clear()
        self.app.saved_condition_count = 0
        self.app._comparison_reference_iid = None
        for iid in self.app.conditions_table.get_children():
            self.app.conditions_table.delete(iid)
        self.update_differences()

    def duplicate_selected(self) -> None:
        """Load exactly one saved condition into the active editor."""

        selected = selected_conditions(
            self.app.saved_conditions, self.app.conditions_table.selection()
        )
        if len(selected) != 1:
            return
        reference_iid, reference = selected[0]
        snapshot = comparison_reference(reference)
        settings = dict(snapshot.settings)
        settings["final_q_deg"] = list(snapshot.final_q_deg)
        self.app._comparison_reference_iid = reference_iid
        self.app.apply_settings(settings)
        self.app.conditions_table.selection_remove(reference_iid)
        self.update_buttons()
        self.app.table_notebook.select(self.app.differences_tab)
        self.app.on_table_tab_changed()
        self.update_differences()
        self.app.status_var.set(
            f"condition {reference.label} dupliquée vers l'éditeur · "
            "modifiez un paramètre puis cliquez sur Ajouter"
        )

    def add_saved_condition(
        self,
        settings: Mapping[str, object],
        final_q_deg: list[float],
        label: str | None = None,
        iid: str | None = None,
        states: list[MotionState] | None = None,
        results: list[DynamicsResult] | None = None,
        comparison_reference: ComparisonReference | Mapping[str, object] | None = None,
    ) -> str:
        """Simulate as needed, save a condition, and add its table row."""

        self.app.saved_condition_count += 1
        condition_iid = iid or f"condition-{self.app.saved_condition_count}"
        if condition_iid in self.app.saved_conditions:
            condition_iid = f"condition-{self.app.saved_condition_count}"
        if not final_q_deg:
            final_q_deg = [degrees(value) for value in self.app.final_q]
        condition_label = label or str(self.app.saved_condition_count)
        if states is None or results is None:
            states, results = self.app.simulate_from_condition(
                dict(settings), final_q_deg
            )
        squat_angles = self.app.display_joint_angles(
            tuple(radians(value) for value in final_q_deg)
        )
        condition = create_saved_condition(
            label=condition_label,
            settings=settings,
            final_q_deg=final_q_deg,
            states=states,
            results=results,
            reference=comparison_reference,
        )
        metrics = condition_table_metrics(condition)
        self.app.saved_conditions[condition_iid] = condition
        self.app.conditions_table.insert(
            "",
            "end",
            iid=condition_iid,
            values=self._table_values(settings, squat_angles, condition, metrics),
        )
        return condition_iid

    @staticmethod
    def _table_values(
        settings: Mapping[str, object],
        squat_angles: tuple[float, float, float],
        condition: Any,
        metrics: Any,
    ) -> tuple[object, ...]:
        """Build the stable presentation values for one saved-condition row."""

        return (
            condition.label,
            str(settings.get("subject_profile", "homme")),
            str(settings.get("bar_position", "back")),
            f"{squat_angles[0]:.0f}/{squat_angles[1]:.0f}/{squat_angles[2]:.0f}",
            f"{float(settings.get('load_percent_bw', 100.0 * float(settings.get('load_kg', 0.0)) / 70.0)):.0f}",
            (
                f"{float(settings.get('duration_excentrique_s', settings.get('duration_phase_s', 4.0))):.1f}/"
                f"{float(settings.get('duration_isometrique_s', 2.0)):.1f}/"
                f"{float(settings.get('duration_concentrique_s', settings.get('duration_phase_s', 4.0))):.1f}"
            ),
            "20" if bool(settings.get("wedge_20_deg", False)) else "0",
            f"{float(settings.get('shank_percent', 0.0)):+.1f}",
            f"{float(settings.get('thigh_percent', 0.0)):+.1f}",
            f"{float(settings.get('trunk_percent', 0.0)):+.1f}",
            f"{metrics.peak_torques['cheville']:.1f}",
            f"{metrics.peak_torques['genou']:.1f}",
            f"{metrics.peak_torques['hanche']:.1f}",
            metrics.utilization_label,
            metrics.limiting_label,
            condition.difference_summary,
        )

    def delete_selected(self) -> None:
        """Ask for confirmation, then delete the selected saved conditions."""

        selected = list(self.app.conditions_table.selection())
        if not selected:
            return
        if not self.confirm_delete(
            "Supprimer",
            f"Supprimer {len(selected)} condition(s) selectionnee(s) ?",
            parent=self.app,
        ):
            return
        for iid in selected:
            self.app.saved_conditions.pop(iid, None)
            if self.app.conditions_table.exists(iid):
                self.app.conditions_table.delete(iid)
            if iid == self.app._comparison_reference_iid:
                self.app._comparison_reference_iid = None
        self.on_selection_changed()
        self.app.status_var.set(f"{len(selected)} condition(s) supprimee(s)")
