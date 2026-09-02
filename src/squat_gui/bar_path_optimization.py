"""Experimental constrained optimization of the squat bar path.

The optimization deliberately changes only the three segment orientations at
the deep-squat posture.  The regular quintic motion law remains responsible
for every intermediate state, so the support constraints are evaluated on the
same complete movement that is displayed and exported by the application.
"""

from __future__ import annotations

from dataclasses import dataclass
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
_FEASIBILITY_TOLERANCE = 2e-6


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
    limits = (
        (radians(-30.0), radians(40.0)),
        (radians(-140.0), radians(0.0)),
        (radians(-15.0), radians(120.0)),
    )
    return tuple(
        value
        for angle, (lower, upper) in zip(joint_angles, limits)
        for value in (angle - lower, upper - angle)
    )


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

    if minimize_function is None:
        try:
            from scipy.optimize import minimize as minimize_function
        except (ImportError, ModuleNotFoundError):
            return BarPathOptimizationResult(
                requested_final_q,
                requested_final_q,
                baseline_states,
                baseline_dynamics,
                before,
                before,
                False,
                False,
                "stabilisation expérimentale indisponible: SciPy n'est pas installé",
            )

    requested_depth = pose_from_angles(anthro, requested_final_q).hip[1]
    requested_joint_values = joint_values_from_segment_values(requested_final_q)
    requested_joint_q = tuple(
        requested_joint_values[joint] for joint in ("cheville", "genou", "hanche")
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
            + 0.10 * metrics.horizontal_rms_from_top_m**2 / anchor_scale
            + 0.01 * correction
        )

    def constraints(values: Any) -> tuple[float, ...]:
        candidate_final_q, states, dynamics, _metrics = evaluate(values)
        constraint_values = list(_anatomical_constraint_values(candidate_final_q))
        candidate_depth = pose_from_angles(anthro, candidate_final_q).hip[1]
        constraint_values.extend(
            (
                DEPTH_TOLERANCE_M - (candidate_depth - requested_depth),
                DEPTH_TOLERANCE_M + (candidate_depth - requested_depth),
            )
        )
        for state, result in zip(states, dynamics):
            posterior, anterior = functional_support_limits(state.pose)
            constraint_values.extend(
                (
                    result.cop_x - posterior - COP_NUMERICAL_BUFFER_M,
                    anterior - result.cop_x - COP_NUMERICAL_BUFFER_M,
                    result.ground_reaction[1] - MIN_VERTICAL_GRF_N,
                )
            )
        return tuple(constraint_values)

    anatomical_limits = (
        (radians(-30.0), radians(40.0)),
        (radians(-140.0), radians(0.0)),
        (radians(-15.0), radians(120.0)),
    )
    bounds = [
        (
            max(lower, requested_angle - ANGLE_PERTURBATION_RAD),
            min(upper, requested_angle + ANGLE_PERTURBATION_RAD),
        )
        for requested_angle, (lower, upper) in zip(
            requested_joint_q, anatomical_limits
        )
    ]
    try:
        # SciPy 1.17.1 on Windows can terminate the interpreter inside its
        # native SLSQP feasibility pass when the problem has no feasible point.
        # Keep the validated constrained SLSQP solve below, but only call it
        # from a feasible point found by this bounded deterministic search.
        feasible_start: tuple[float, float, float] | None = None
        if min(constraints(requested_joint_q)) >= -_FEASIBILITY_TOLERANCE:
            feasible_start = requested_joint_q
        else:
            level_order = (0.0, -0.5, 0.5, -1.0, 1.0)
            for offsets in product(level_order, repeat=3):
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
                if min(constraints(candidate_start)) >= -_FEASIBILITY_TOLERANCE:
                    feasible_start = candidate_start
                    break
        if feasible_start is None:
            raise RuntimeError("aucune posture faisable dans les bornes ±5°")
        optimized = minimize_function(
            objective,
            feasible_start,
            method="SLSQP",
            bounds=bounds,
            constraints=({"type": "ineq", "fun": constraints},),
            options={"maxiter": 160, "ftol": 1e-10, "disp": False},
        )
        candidate_joint_q = tuple(float(value) for value in optimized.x)
        candidate, states, dynamics, after = evaluate(candidate_joint_q)
        minimum_constraint = min(constraints(candidate_joint_q))
        if not bool(optimized.success):
            raise RuntimeError(str(getattr(optimized, "message", "échec SLSQP")))
        if minimum_constraint < -_FEASIBILITY_TOLERANCE:
            raise RuntimeError("solution SLSQP rejetée: contrainte violée")
        if objective(candidate_joint_q) >= objective(requested_joint_q) - 1e-8:
            raise RuntimeError("aucune amélioration mesurable de la trajectoire")
    except Exception as error:
        return BarPathOptimizationResult(
            requested_final_q,
            requested_final_q,
            baseline_states,
            baseline_dynamics,
            before,
            before,
            False,
            True,
            f"stabilisation expérimentale non appliquée: {error}",
        )

    return BarPathOptimizationResult(
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
