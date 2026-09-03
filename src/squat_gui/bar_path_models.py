"""Results, diagnostics, and progress events for bar-path optimization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .dynamics import DynamicsResult
from .kinematics import MotionState, functional_support_limits


class BarPathOptimizationStage(str, Enum):
    """Stable milestones exposed to optional GUI and CLI observers."""

    BASELINE_READY = "baseline_ready"
    FEASIBLE_START_SEARCH = "feasible_start_search"
    FEASIBLE_START_FOUND = "feasible_start_found"
    SOLVER_STARTED = "solver_started"
    CANDIDATE_EVALUATED = "candidate_evaluated"
    SOLVER_FINISHED = "solver_finished"
    COMPLETED = "completed"
    FALLBACK = "fallback"


class BarPathFailureCode(str, Enum):
    """Machine-readable reasons for keeping the safe baseline trajectory."""

    SCIPY_UNAVAILABLE = "scipy_unavailable"
    NO_FEASIBLE_START = "no_feasible_start"
    SOLVER_ERROR = "solver_error"
    SOLVER_REJECTED = "solver_rejected"
    CONSTRAINT_VIOLATION = "constraint_violation"
    NO_IMPROVEMENT = "no_improvement"
    EVALUATION_ERROR = "evaluation_error"


@dataclass(frozen=True)
class BarPathOptimizationProgress:
    """One optional progress event; emitting it never writes to a stream."""

    stage: BarPathOptimizationStage
    evaluated_candidates: int
    message: str


BarPathProgressCallback = Callable[[BarPathOptimizationProgress], None]


@dataclass(frozen=True)
class BarPathOptimizationDiagnostic:
    """Structured diagnostic attached to a non-applied optimization."""

    code: BarPathFailureCode
    detail: str


class OptimizationRejected(RuntimeError):
    """Controlled internal rejection converted to a safe public result."""

    def __init__(self, code: BarPathFailureCode, detail: str) -> None:
        super().__init__(detail)
        self.code = code


@dataclass(frozen=True)
class BarPathMetrics:
    """Quantities used to compare the requested and optimized trajectories."""

    horizontal_velocity_energy_m2_s: float
    horizontal_excursion_m: float
    horizontal_rms_from_top_m: float
    minimum_cop_margin_m: float
    minimum_vertical_grf_N: float
    deep_hip_height_m: float


@dataclass(frozen=True)
class BarPathOptimizationResult:
    """Outcome of one optional optimization attempt.

    ``states`` and ``dynamics`` always contain a safe trajectory.  They are the
    exact baseline objects when optimization cannot be applied.
    """

    requested_final_q: tuple[float, float, float]
    final_q: tuple[float, float, float]
    states: list[MotionState]
    dynamics: list[DynamicsResult]
    before: BarPathMetrics
    after: BarPathMetrics
    applied: bool
    scipy_available: bool
    message: str
    diagnostic: BarPathOptimizationDiagnostic | None = None


def emit_progress(
    callback: BarPathProgressCallback | None,
    stage: BarPathOptimizationStage,
    evaluated_candidates: int,
    message: str,
) -> None:
    """Notify an observer when requested, without choosing an output channel."""

    if callback is not None:
        callback(BarPathOptimizationProgress(stage, evaluated_candidates, message))


def fallback_result(
    requested_final_q: tuple[float, float, float],
    baseline_states: list[MotionState],
    baseline_dynamics: list[DynamicsResult],
    before: BarPathMetrics,
    *,
    scipy_available: bool,
    code: BarPathFailureCode,
    detail: str,
) -> BarPathOptimizationResult:
    """Build a failed result while preserving the exact baseline objects."""

    return BarPathOptimizationResult(
        requested_final_q,
        requested_final_q,
        baseline_states,
        baseline_dynamics,
        before,
        before,
        False,
        scipy_available,
        (
            "stabilisation expérimentale non appliquée: " + detail
            if scipy_available
            else "stabilisation expérimentale indisponible: " + detail
        ),
        BarPathOptimizationDiagnostic(code, detail),
    )


def trajectory_metrics(
    states: list[MotionState],
    dynamics: list[DynamicsResult],
) -> BarPathMetrics:
    """Return bar-path and support metrics for an endpoint-inclusive motion."""

    if not states or len(states) != len(dynamics):
        raise ValueError("Une trajectoire et sa dynamique de même taille sont requises.")
    bar_x = [state.pose.bar[0] for state in states]
    top_x = bar_x[0]
    velocity_energy = 0.0
    for previous, current, previous_x, current_x in zip(
        states, states[1:], bar_x, bar_x[1:]
    ):
        delta_time = current.time - previous.time
        if delta_time > 0.0:
            horizontal_velocity = (current_x - previous_x) / delta_time
            velocity_energy += horizontal_velocity**2 * delta_time

    support_margins = []
    for state, result in zip(states, dynamics):
        posterior, anterior = functional_support_limits(state.pose)
        support_margins.append(
            min(result.cop_x - posterior, anterior - result.cop_x)
        )
    deepest_state = min(states, key=lambda state: state.pose.hip[1])
    return BarPathMetrics(
        horizontal_velocity_energy_m2_s=velocity_energy,
        horizontal_excursion_m=max(bar_x) - min(bar_x),
        horizontal_rms_from_top_m=(
            sum((value - top_x) ** 2 for value in bar_x) / len(bar_x)
        )
        ** 0.5,
        minimum_cop_margin_m=min(support_margins),
        minimum_vertical_grf_N=min(
            result.ground_reaction[1] for result in dynamics
        ),
        deep_hip_height_m=deepest_state.pose.hip[1],
    )
