"""Experimental constrained optimization of the squat bar path.

This module is the stable public façade. Bounds and constraints, candidate
evaluation, and SLSQP execution live in focused internal modules so the
optimization workflow remains readable without changing its public API.
"""

from __future__ import annotations

from typing import Any, Callable

from .anthropometry import Anthropometry
from .bar_path_constraints import (
    ANATOMICAL_JOINT_LIMITS_RAD,
    ANGLE_PERTURBATION_RAD,
    COP_NUMERICAL_BUFFER_M,
    DEPTH_TOLERANCE_M,
    FEASIBILITY_TOLERANCE,
    FEASIBLE_START_LEVEL_ORDER,
    JOINT_ORDER,
    MIN_VERTICAL_GRF_N,
)
from .bar_path_models import (
    BarPathFailureCode,
    BarPathMetrics,
    BarPathOptimizationDiagnostic,
    BarPathOptimizationProgress,
    BarPathOptimizationResult,
    BarPathOptimizationStage,
    BarPathProgressCallback,
    OptimizationRejected as _OptimizationRejected,
    emit_progress as _emit_progress,
    fallback_result as _fallback_result,
    trajectory_metrics,
)
from .bar_path_problem import (
    ANCHOR_OBJECTIVE_WEIGHT,
    CORRECTION_OBJECTIVE_WEIGHT,
    BarPathOptimizationProblem as _BarPathOptimizationProblem,
)
from .bar_path_solver import (
    OBJECTIVE_IMPROVEMENT_TOLERANCE,
    SLSQP_FUNCTION_TOLERANCE,
    SLSQP_MAX_ITERATIONS,
    solve_slsqp as _solve_slsqp,
)
from .dynamics import DynamicsResult, simulate
from .kinematics import MotionState, PhaseDurations, phase_durations


__all__ = [
    "ANATOMICAL_JOINT_LIMITS_RAD",
    "ANCHOR_OBJECTIVE_WEIGHT",
    "ANGLE_PERTURBATION_RAD",
    "COP_NUMERICAL_BUFFER_M",
    "CORRECTION_OBJECTIVE_WEIGHT",
    "DEPTH_TOLERANCE_M",
    "FEASIBILITY_TOLERANCE",
    "FEASIBLE_START_LEVEL_ORDER",
    "JOINT_ORDER",
    "MIN_VERTICAL_GRF_N",
    "OBJECTIVE_IMPROVEMENT_TOLERANCE",
    "SLSQP_FUNCTION_TOLERANCE",
    "SLSQP_MAX_ITERATIONS",
    "BarPathFailureCode",
    "BarPathMetrics",
    "BarPathOptimizationDiagnostic",
    "BarPathOptimizationProgress",
    "BarPathOptimizationResult",
    "BarPathOptimizationStage",
    "BarPathProgressCallback",
    "optimize_deep_squat_bar_path",
    "trajectory_metrics",
]


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

    problem = _BarPathOptimizationProblem(
        anthro,
        requested_final_q,
        durations,
        frame_count,
        max_torques,
        adapt_max_by_angle,
        model_cache,
        adapt_max_by_velocity,
        baseline_states,
        baseline_dynamics,
        before,
        progress_callback,
    )
    try:
        solution = _solve_slsqp(problem, minimize_function)
    except _OptimizationRejected as error:
        _emit_progress(
            progress_callback,
            BarPathOptimizationStage.FALLBACK,
            problem.evaluated_candidates,
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
            problem.evaluated_candidates,
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
        solution.final_q,
        solution.states,
        solution.dynamics,
        before,
        solution.metrics,
        True,
        True,
        (
            "stabilisation expérimentale appliquée: excursion horizontale "
            f"{100.0 * before.horizontal_excursion_m:.1f} → "
            f"{100.0 * solution.metrics.horizontal_excursion_m:.1f} cm; "
            "énergie vₓ² "
            f"{before.horizontal_velocity_energy_m2_s:.4g} → "
            f"{solution.metrics.horizontal_velocity_energy_m2_s:.4g} m²/s"
        ),
    )
    _emit_progress(
        progress_callback,
        BarPathOptimizationStage.COMPLETED,
        problem.evaluated_candidates,
        result.message,
    )
    return result
