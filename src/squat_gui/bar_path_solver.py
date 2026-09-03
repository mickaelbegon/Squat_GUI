"""SLSQP execution and validation for bar-path optimization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .bar_path_constraints import FEASIBILITY_TOLERANCE, find_feasible_start
from .bar_path_models import (
    BarPathFailureCode,
    BarPathMetrics,
    BarPathOptimizationStage,
    OptimizationRejected,
    emit_progress,
)
from .bar_path_problem import BarPathOptimizationProblem
from .dynamics import DynamicsResult
from .kinematics import MotionState


OBJECTIVE_IMPROVEMENT_TOLERANCE = 1e-8
SLSQP_MAX_ITERATIONS = 160
SLSQP_FUNCTION_TOLERANCE = 1e-10


@dataclass(frozen=True)
class SlsqpSolution:
    """Validated values returned by a successful SLSQP solve."""

    final_q: tuple[float, float, float]
    states: list[MotionState]
    dynamics: list[DynamicsResult]
    metrics: BarPathMetrics


def solve_slsqp(
    problem: BarPathOptimizationProblem,
    minimize_function: Callable[..., Any],
) -> SlsqpSolution:
    """Find, solve, and validate one constrained SLSQP problem."""

    # SciPy 1.17.1 on Windows can terminate the interpreter inside its native
    # SLSQP feasibility pass when the problem has no feasible point. Keep the
    # constrained solve, but only call it from a deterministically validated seed.
    emit_progress(
        problem.progress_callback,
        BarPathOptimizationStage.FEASIBLE_START_SEARCH,
        problem.evaluated_candidates,
        "recherche d'une posture initiale faisable",
    )
    feasible_start = find_feasible_start(
        problem.requested_joint_q,
        problem.bounds,
        problem.constraints,
    )
    if feasible_start is None:
        raise OptimizationRejected(
            BarPathFailureCode.NO_FEASIBLE_START,
            "aucune posture faisable dans les bornes ±5°",
        )
    emit_progress(
        problem.progress_callback,
        BarPathOptimizationStage.FEASIBLE_START_FOUND,
        problem.evaluated_candidates,
        "posture initiale faisable trouvée",
    )
    emit_progress(
        problem.progress_callback,
        BarPathOptimizationStage.SOLVER_STARTED,
        problem.evaluated_candidates,
        "optimisation SLSQP démarrée",
    )
    try:
        optimized = minimize_function(
            problem.objective,
            feasible_start,
            method="SLSQP",
            bounds=problem.bounds,
            constraints=({"type": "ineq", "fun": problem.constraints},),
            options={
                "maxiter": SLSQP_MAX_ITERATIONS,
                "ftol": SLSQP_FUNCTION_TOLERANCE,
                "disp": False,
            },
        )
    except (ArithmeticError, RuntimeError, TypeError, ValueError) as error:
        raise OptimizationRejected(
            BarPathFailureCode.SOLVER_ERROR,
            str(error) or type(error).__name__,
        ) from error
    emit_progress(
        problem.progress_callback,
        BarPathOptimizationStage.SOLVER_FINISHED,
        problem.evaluated_candidates,
        "optimisation SLSQP terminée; validation de la solution",
    )
    try:
        candidate_joint_q = tuple(float(value) for value in optimized.x)
        candidate, states, dynamics, after = problem.evaluate(candidate_joint_q)
        minimum_constraint = min(problem.constraints(candidate_joint_q))
    except (AttributeError, TypeError, ValueError) as error:
        raise OptimizationRejected(
            BarPathFailureCode.SOLVER_ERROR,
            f"résultat SLSQP invalide: {error}",
        ) from error
    if not bool(optimized.success):
        raise OptimizationRejected(
            BarPathFailureCode.SOLVER_REJECTED,
            str(getattr(optimized, "message", "échec SLSQP")),
        )
    if minimum_constraint < -FEASIBILITY_TOLERANCE:
        raise OptimizationRejected(
            BarPathFailureCode.CONSTRAINT_VIOLATION,
            "solution SLSQP rejetée: contrainte violée",
        )
    if (
        problem.objective(candidate_joint_q)
        >= problem.objective(problem.requested_joint_q)
        - OBJECTIVE_IMPROVEMENT_TOLERANCE
    ):
        raise OptimizationRejected(
            BarPathFailureCode.NO_IMPROVEMENT,
            "aucune amélioration mesurable de la trajectoire",
        )
    return SlsqpSolution(
        (candidate[0], candidate[1], candidate[2]),
        states,
        dynamics,
        after,
    )
