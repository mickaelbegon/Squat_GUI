"""Experimental constrained optimization of the squat bar path.

The optimization deliberately changes only the three segment orientations at
the deep-squat posture.  The regular quintic motion law remains responsible
for every intermediate state, so the support constraints are evaluated on the
same complete movement that is displayed and exported by the application.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import product
from math import radians
from typing import Any, Callable

from .anthropometry import Anthropometry
from .dynamics import DynamicsResult, simulate
from .kinematics import (
    MotionState,
    PhaseDurations,
    functional_support_limits,
    joint_values_from_segment_values,
    phase_durations,
    pose_from_angles,
    segment_values_from_joint_values,
)


ANGLE_PERTURBATION_RAD = radians(5.0)
DEPTH_TOLERANCE_M = 0.01
COP_NUMERICAL_BUFFER_M = 1e-5
MIN_VERTICAL_GRF_N = 1.0
FEASIBILITY_TOLERANCE = 2e-6
JOINT_ORDER = ("cheville", "genou", "hanche")
ANATOMICAL_JOINT_LIMITS_RAD = (
    (radians(-30.0), radians(40.0)),
    (radians(-140.0), radians(0.0)),
    (radians(-15.0), radians(120.0)),
)
FEASIBLE_START_LEVEL_ORDER = (0.0, -0.5, 0.5, -1.0, 1.0)
ANCHOR_OBJECTIVE_WEIGHT = 0.10
CORRECTION_OBJECTIVE_WEIGHT = 0.01
OBJECTIVE_IMPROVEMENT_TOLERANCE = 1e-8
SLSQP_MAX_ITERATIONS = 160
SLSQP_FUNCTION_TOLERANCE = 1e-10


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


class _OptimizationRejected(RuntimeError):
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


def _emit_progress(
    callback: BarPathProgressCallback | None,
    stage: BarPathOptimizationStage,
    evaluated_candidates: int,
    message: str,
) -> None:
    """Notify an observer when requested, without choosing an output channel."""

    if callback is not None:
        callback(BarPathOptimizationProgress(stage, evaluated_candidates, message))


def _fallback_result(
    requested_final_q: tuple[float, float, float],
    baseline_states: list[MotionState],
    baseline_dynamics: list[DynamicsResult],
    before: BarPathMetrics,
    *,
    scipy_available: bool,
    code: BarPathFailureCode,
    detail: str,
) -> BarPathOptimizationResult:
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


def _anatomical_constraint_values(
    final_q: tuple[float, float, float],
) -> tuple[float, ...]:
    ankle = final_q[0]
    knee = final_q[1] - final_q[0]
    hip = final_q[2] - final_q[1]
    joint_angles = (ankle, knee, hip)
    return tuple(
        value
        for angle, (lower, upper) in zip(
            joint_angles, ANATOMICAL_JOINT_LIMITS_RAD
        )
        for value in (angle - lower, upper - angle)
    )


def _candidate_bounds(
    requested_joint_q: tuple[float, float, float],
) -> list[tuple[float, float]]:
    """Combine the anatomical limits with the experimental ±5° bounds."""

    return [
        (
            max(lower, requested_angle - ANGLE_PERTURBATION_RAD),
            min(upper, requested_angle + ANGLE_PERTURBATION_RAD),
        )
        for requested_angle, (lower, upper) in zip(
            requested_joint_q, ANATOMICAL_JOINT_LIMITS_RAD
        )
    ]


def _trajectory_constraint_values(
    anthro: Anthropometry,
    candidate_final_q: tuple[float, float, float],
    states: list[MotionState],
    dynamics: list[DynamicsResult],
    requested_depth: float,
) -> tuple[float, ...]:
    """Return the complete SLSQP inequality vector (feasible values >= 0)."""

    values = list(_anatomical_constraint_values(candidate_final_q))
    candidate_depth = pose_from_angles(anthro, candidate_final_q).hip[1]
    values.extend(
        (
            DEPTH_TOLERANCE_M - (candidate_depth - requested_depth),
            DEPTH_TOLERANCE_M + (candidate_depth - requested_depth),
        )
    )
    for state, result in zip(states, dynamics):
        posterior, anterior = functional_support_limits(state.pose)
        values.extend(
            (
                result.cop_x - posterior - COP_NUMERICAL_BUFFER_M,
                anterior - result.cop_x - COP_NUMERICAL_BUFFER_M,
                result.ground_reaction[1] - MIN_VERTICAL_GRF_N,
            )
        )
    return tuple(values)


def _find_feasible_start(
    requested_joint_q: tuple[float, float, float],
    bounds: list[tuple[float, float]],
    constraints: Callable[[Any], tuple[float, ...]],
) -> tuple[float, float, float] | None:
    """Find the deterministic feasible seed used before calling SLSQP."""

    if min(constraints(requested_joint_q)) >= -FEASIBILITY_TOLERANCE:
        return requested_joint_q
    for offsets in product(FEASIBLE_START_LEVEL_ORDER, repeat=3):
        candidate_start = tuple(
            min(
                upper,
                max(
                    lower,
                    requested + offset * ANGLE_PERTURBATION_RAD,
                ),
            )
            for requested, offset, (lower, upper) in zip(
                requested_joint_q, offsets, bounds
            )
        )
        if candidate_start == requested_joint_q:
            continue
        if min(constraints(candidate_start)) >= -FEASIBILITY_TOLERANCE:
            return candidate_start
    return None


def optimize_deep_squat_bar_path(
    anthro: Anthropometry,
    requested_final_q: tuple[float, float, float],
    duration: float | PhaseDurations,
    frame_count: int,
    max_torques: dict[str, float],
    adapt_max_by_angle: bool,
    model_cache: Any | None = None,
    adapt_max_by_velocity: bool = True,
    *,
    baseline: tuple[list[MotionState], list[DynamicsResult]] | None = None,
    minimize_function: Callable[..., Any] | None = None,
    progress_callback: BarPathProgressCallback | None = None,
) -> BarPathOptimizationResult:
    """Minimize horizontal bar motion with SLSQP under biomechanical bounds.

    The result falls back to the supplied baseline without mutating it when
    SciPy is missing, SLSQP fails, the solution is infeasible, or the objective
    does not improve.
    """

    durations = phase_durations(duration)
    if baseline is None:
        baseline = simulate(
            anthro,
            requested_final_q,
            durations,
            frame_count,
            max_torques,
            adapt_max_by_angle,
            model_cache,
            adapt_max_by_velocity,
        )
    baseline_states, baseline_dynamics = baseline
    before = trajectory_metrics(baseline_states, baseline_dynamics)
    _emit_progress(
        progress_callback,
        BarPathOptimizationStage.BASELINE_READY,
        1,
        "trajectoire de référence évaluée",
    )

    if minimize_function is None:
        try:
            from scipy.optimize import minimize as minimize_function
        except (ImportError, ModuleNotFoundError):
            detail = "SciPy n'est pas installé"
            _emit_progress(
                progress_callback,
                BarPathOptimizationStage.FALLBACK,
                1,
                detail,
            )
            return _fallback_result(
                requested_final_q,
                baseline_states,
                baseline_dynamics,
                before,
                scipy_available=False,
                code=BarPathFailureCode.SCIPY_UNAVAILABLE,
                detail=detail,
            )

    requested_depth = pose_from_angles(anthro, requested_final_q).hip[1]
    requested_joint_values = joint_values_from_segment_values(requested_final_q)
    requested_joint_q = tuple(
        requested_joint_values[joint] for joint in JOINT_ORDER
    )
    cache: dict[
        tuple[float, float, float],
        tuple[
            tuple[float, float, float],
            list[MotionState],
            list[DynamicsResult],
            BarPathMetrics,
        ],
    ] = {
        requested_joint_q: (
            requested_final_q,
            baseline_states,
            baseline_dynamics,
            before,
        ),
    }

    def evaluate(values: Any) -> tuple[
        tuple[float, float, float],
        list[MotionState],
        list[DynamicsResult],
        BarPathMetrics,
    ]:
        candidate = tuple(float(value) for value in values)
        if len(candidate) != 3:
            raise ValueError("SLSQP doit fournir exactement trois angles.")
        candidate_joint_q = (candidate[0], candidate[1], candidate[2])
        if candidate_joint_q not in cache:
            candidate_final_q = segment_values_from_joint_values(*candidate_joint_q)
            states, dynamics = simulate(
                anthro,
                candidate_final_q,
                durations,
                frame_count,
                max_torques,
                adapt_max_by_angle,
                model_cache,
                adapt_max_by_velocity,
            )
            cache[candidate_joint_q] = (
                candidate_final_q,
                states,
                dynamics,
                trajectory_metrics(states, dynamics),
            )
            _emit_progress(
                progress_callback,
                BarPathOptimizationStage.CANDIDATE_EVALUATED,
                len(cache),
                "posture candidate évaluée",
            )
        return cache[candidate_joint_q]

    velocity_scale = max(before.horizontal_velocity_energy_m2_s, 1e-8)
    anchor_scale = max(before.horizontal_rms_from_top_m**2, 1e-8)

    def objective(values: Any) -> float:
        _final_q, _states, _dynamics, metrics = evaluate(values)
        correction = sum(
            ((float(value) - reference) / ANGLE_PERTURBATION_RAD) ** 2
            for value, reference in zip(values, requested_joint_q)
        ) / 3.0
        return (
            metrics.horizontal_velocity_energy_m2_s / velocity_scale
            + ANCHOR_OBJECTIVE_WEIGHT
            * metrics.horizontal_rms_from_top_m**2
            / anchor_scale
            + CORRECTION_OBJECTIVE_WEIGHT * correction
        )

    def constraints(values: Any) -> tuple[float, ...]:
        candidate_final_q, states, dynamics, _metrics = evaluate(values)
        return _trajectory_constraint_values(
            anthro,
            candidate_final_q,
            states,
            dynamics,
            requested_depth,
        )

    bounds = _candidate_bounds(requested_joint_q)
    try:
        # SciPy 1.17.1 on Windows can terminate the interpreter inside its
        # native SLSQP feasibility pass when the problem has no feasible point.
        # Keep the validated constrained SLSQP solve below, but only call it
        # from a feasible point found by this bounded deterministic search.
        _emit_progress(
            progress_callback,
            BarPathOptimizationStage.FEASIBLE_START_SEARCH,
            len(cache),
            "recherche d'une posture initiale faisable",
        )
        feasible_start = _find_feasible_start(
            requested_joint_q, bounds, constraints
        )
        if feasible_start is None:
            raise _OptimizationRejected(
                BarPathFailureCode.NO_FEASIBLE_START,
                "aucune posture faisable dans les bornes ±5°",
            )
        _emit_progress(
            progress_callback,
            BarPathOptimizationStage.FEASIBLE_START_FOUND,
            len(cache),
            "posture initiale faisable trouvée",
        )
        _emit_progress(
            progress_callback,
            BarPathOptimizationStage.SOLVER_STARTED,
            len(cache),
            "optimisation SLSQP démarrée",
        )
        try:
            optimized = minimize_function(
                objective,
                feasible_start,
                method="SLSQP",
                bounds=bounds,
                constraints=({"type": "ineq", "fun": constraints},),
                options={
                    "maxiter": SLSQP_MAX_ITERATIONS,
                    "ftol": SLSQP_FUNCTION_TOLERANCE,
                    "disp": False,
                },
            )
        except (ArithmeticError, RuntimeError, TypeError, ValueError) as error:
            raise _OptimizationRejected(
                BarPathFailureCode.SOLVER_ERROR,
                str(error) or type(error).__name__,
            ) from error
        _emit_progress(
            progress_callback,
            BarPathOptimizationStage.SOLVER_FINISHED,
            len(cache),
            "optimisation SLSQP terminée; validation de la solution",
        )
        try:
            candidate_joint_q = tuple(float(value) for value in optimized.x)
            candidate, states, dynamics, after = evaluate(candidate_joint_q)
            minimum_constraint = min(constraints(candidate_joint_q))
        except (AttributeError, TypeError, ValueError) as error:
            raise _OptimizationRejected(
                BarPathFailureCode.SOLVER_ERROR,
                f"résultat SLSQP invalide: {error}",
            ) from error
        if not bool(optimized.success):
            raise _OptimizationRejected(
                BarPathFailureCode.SOLVER_REJECTED,
                str(getattr(optimized, "message", "échec SLSQP")),
            )
        if minimum_constraint < -FEASIBILITY_TOLERANCE:
            raise _OptimizationRejected(
                BarPathFailureCode.CONSTRAINT_VIOLATION,
                "solution SLSQP rejetée: contrainte violée",
            )
        if (
            objective(candidate_joint_q)
            >= objective(requested_joint_q) - OBJECTIVE_IMPROVEMENT_TOLERANCE
        ):
            raise _OptimizationRejected(
                BarPathFailureCode.NO_IMPROVEMENT,
                "aucune amélioration mesurable de la trajectoire",
            )
    except _OptimizationRejected as error:
        _emit_progress(
            progress_callback,
            BarPathOptimizationStage.FALLBACK,
            len(cache),
            str(error),
        )
        return _fallback_result(
            requested_final_q,
            baseline_states,
            baseline_dynamics,
            before,
            scipy_available=True,
            code=error.code,
            detail=str(error),
        )
    except (
        ArithmeticError,
        AttributeError,
        LookupError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        detail = str(error) or type(error).__name__
        _emit_progress(
            progress_callback,
            BarPathOptimizationStage.FALLBACK,
            len(cache),
            detail,
        )
        return _fallback_result(
            requested_final_q,
            baseline_states,
            baseline_dynamics,
            before,
            scipy_available=True,
            code=BarPathFailureCode.EVALUATION_ERROR,
            detail=detail,
        )

    result = BarPathOptimizationResult(
        requested_final_q,
        (candidate[0], candidate[1], candidate[2]),
        states,
        dynamics,
        before,
        after,
        True,
        True,
        (
            "stabilisation expérimentale appliquée: excursion horizontale "
            f"{100.0 * before.horizontal_excursion_m:.1f} → "
            f"{100.0 * after.horizontal_excursion_m:.1f} cm; énergie vₓ² "
            f"{before.horizontal_velocity_energy_m2_s:.4g} → "
            f"{after.horizontal_velocity_energy_m2_s:.4g} m²/s"
        ),
    )
    _emit_progress(
        progress_callback,
        BarPathOptimizationStage.COMPLETED,
        len(cache),
        result.message,
    )
    return result
