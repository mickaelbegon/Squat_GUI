"""Typed, Tk-independent operations for recorded squat conditions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Optional

from .comparison import ParameterDifference, difference_summary, parameter_differences
from .dynamics import DynamicsResult
from .kinematics import MotionState
from .session_persistence import ComparisonReference, SavedCondition, SettingsMap


@dataclass(frozen=True)
class ConditionComparison:
    """A resolved pair of conditions ready for the differences table."""

    reference_label: str
    reference_settings: SettingsMap
    reference_final_q_deg: list[float]
    compared_label: str
    compared_settings: SettingsMap
    compared_final_q_deg: list[float]

    @property
    def differences(self) -> tuple[ParameterDifference, ...]:
        return parameter_differences(
            self.reference_settings,
            self.reference_final_q_deg,
            self.compared_settings,
            self.compared_final_q_deg,
        )


def selected_conditions(
    conditions: Mapping[str, SavedCondition], selected_ids: Iterable[str]
) -> list[tuple[str, SavedCondition]]:
    """Return recorded conditions in the exact order exposed by the UI."""

    return [
        (iid, conditions[iid]) for iid in selected_ids if iid in conditions
    ]


def comparison_reference(condition: SavedCondition) -> ComparisonReference:
    """Create the stable snapshot used when duplicating a condition."""

    return ComparisonReference(
        label=condition.label,
        settings=deepcopy(condition.settings),
        final_q_deg=list(condition.final_q_deg),
    )


def resolve_condition_comparison(
    conditions: Mapping[str, SavedCondition],
    selected_ids: Iterable[str],
    *,
    pending_reference_iid: str | None = None,
    current_settings: Mapping[str, object] | None = None,
    current_final_q_deg: Sequence[float] | None = None,
) -> Optional[ConditionComparison]:
    """Resolve comparison priority without depending on a table widget.

    Two selected saved conditions take precedence.  One selected condition can
    compare itself with its persisted duplication reference.  With no selected
    row, a pending duplicate reference compares against the live editor.
    """

    selected = selected_conditions(conditions, selected_ids)
    if len(selected) >= 2:
        _reference_iid, reference = selected[0]
        _compared_iid, compared = selected[1]
        return ConditionComparison(
            reference.label,
            dict(reference.settings),
            list(reference.final_q_deg),
            compared.label,
            dict(compared.settings),
            list(compared.final_q_deg),
        )
    if len(selected) == 1:
        _iid, condition = selected[0]
        reference = condition.comparison_reference
        if reference is not None:
            return ConditionComparison(
                reference.label,
                dict(reference.settings),
                list(reference.final_q_deg),
                condition.label,
                dict(condition.settings),
                list(condition.final_q_deg),
            )
    if (
        not selected
        and pending_reference_iid is not None
        and pending_reference_iid in conditions
        and current_settings is not None
        and current_final_q_deg is not None
    ):
        reference = conditions[pending_reference_iid]
        return ConditionComparison(
            reference.label,
            dict(reference.settings),
            list(reference.final_q_deg),
            "courant",
            dict(current_settings),
            list(current_final_q_deg),
        )
    return None


def create_saved_condition(
    *,
    label: str,
    settings: Mapping[str, object],
    final_q_deg: Sequence[float],
    states: list[MotionState],
    results: list[DynamicsResult],
    reference: ComparisonReference | Mapping[str, object] | None = None,
) -> SavedCondition:
    """Build one runtime record and compute its immutable comparison summary."""

    typed_reference = ComparisonReference.from_object(reference)
    differences: tuple[ParameterDifference, ...] = ()
    if typed_reference is not None:
        differences = parameter_differences(
            typed_reference.settings,
            typed_reference.final_q_deg,
            settings,
            final_q_deg,
        )
    return SavedCondition(
        label=label,
        settings=dict(settings),
        final_q_deg=list(final_q_deg),
        states=states,
        results=results,
        comparison_reference=typed_reference,
        difference_summary=(
            difference_summary(differences)
            if typed_reference is not None
            else "référence indépendante"
        ),
    )


@dataclass(frozen=True)
class ConditionTableMetrics:
    """Computed scientific values displayed in one saved-condition row."""

    peak_torques: Mapping[str, float]
    utilization_label: str
    limiting_label: str


def condition_table_metrics(condition: SavedCondition) -> ConditionTableMetrics:
    """Compute peak torques and the limiting utilization from saved results."""

    if not condition.states or not condition.results:
        raise ValueError("La condition enregistrée ne contient aucun résultat.")
    peak_torques = {
        joint: max(abs(result.torques[joint]) for result in condition.results)
        for joint in ("cheville", "genou", "hanche")
    }
    utilization_events = [
        (result.effort_ratios[joint], index, joint)
        for index, result in enumerate(condition.results)
        for joint in ("cheville", "genou", "hanche")
    ]
    undefined_events = [event for event in utilization_events if event[0] is None]
    if undefined_events:
        limiting_ratio, limiting_index, limiting_joint = undefined_events[0]
        utilization_label = "n.d."
        exceeds_label = "oui"
    else:
        limiting_ratio, limiting_index, limiting_joint = max(
            utilization_events, key=lambda event: float(event[0] or 0.0)
        )
        utilization_label = f"{100.0 * float(limiting_ratio or 0.0):.0f}%"
        exceeds_label = "oui" if float(limiting_ratio or 0.0) > 1.0 else "non"
    limiting_state = condition.states[limiting_index]
    limiting_label = (
        f"{limiting_joint} · {limiting_state.time:.2f}s · "
        f"{limiting_state.phase} · {exceeds_label}"
    )
    return ConditionTableMetrics(peak_torques, utilization_label, limiting_label)
