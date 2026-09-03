"""Objective and candidate evaluation for bar-path optimization."""

from __future__ import annotations

from typing import Any

from .anthropometry import Anthropometry
from .bar_path_constraints import (
    ANGLE_PERTURBATION_RAD,
    JOINT_ORDER,
    candidate_bounds,
    trajectory_constraint_values,
)
from .bar_path_models import (
    BarPathMetrics,
    BarPathOptimizationStage,
    BarPathProgressCallback,
    emit_progress,
    trajectory_metrics,
)
from .dynamics import DynamicsResult, simulate
from .kinematics import (
    MotionState,
    PhaseDurations,
    joint_values_from_segment_values,
    pose_from_angles,
    segment_values_from_joint_values,
)


ANCHOR_OBJECTIVE_WEIGHT = 0.10
CORRECTION_OBJECTIVE_WEIGHT = 0.01

CandidateEvaluation = tuple[
    tuple[float, float, float],
    list[MotionState],
    list[DynamicsResult],
    BarPathMetrics,
]


class BarPathOptimizationProblem:
    """Own one SLSQP problem and cache its expensive trajectory evaluations."""

    def __init__(
        self,
        anthro: Anthropometry,
        requested_final_q: tuple[float, float, float],
        durations: PhaseDurations,
        frame_count: int,
        max_torques: dict[str, float],
        adapt_max_by_angle: bool,
        model_cache: Any | None,
        adapt_max_by_velocity: bool,
        baseline_states: list[MotionState],
        baseline_dynamics: list[DynamicsResult],
        before: BarPathMetrics,
        progress_callback: BarPathProgressCallback | None,
    ) -> None:
        self.anthro = anthro
        self.requested_final_q = requested_final_q
        self.durations = durations
        self.frame_count = frame_count
        self.max_torques = max_torques
        self.adapt_max_by_angle = adapt_max_by_angle
        self.model_cache = model_cache
        self.adapt_max_by_velocity = adapt_max_by_velocity
        self.progress_callback = progress_callback
        self.requested_depth = pose_from_angles(anthro, requested_final_q).hip[1]
        requested_joint_values = joint_values_from_segment_values(requested_final_q)
        self.requested_joint_q = tuple(
            requested_joint_values[joint] for joint in JOINT_ORDER
        )
        self.bounds = candidate_bounds(self.requested_joint_q)
        self.velocity_scale = max(before.horizontal_velocity_energy_m2_s, 1e-8)
        self.anchor_scale = max(before.horizontal_rms_from_top_m**2, 1e-8)
        self._cache: dict[
            tuple[float, float, float], CandidateEvaluation
        ] = {
            self.requested_joint_q: (
                requested_final_q,
                baseline_states,
                baseline_dynamics,
                before,
            ),
        }

    @property
    def evaluated_candidates(self) -> int:
        """Number of unique joint configurations evaluated so far."""

        return len(self._cache)

    def evaluate(self, values: Any) -> CandidateEvaluation:
        """Simulate one candidate, reusing an identical prior evaluation."""

        candidate = tuple(float(value) for value in values)
        if len(candidate) != 3:
            raise ValueError("SLSQP doit fournir exactement trois angles.")
        candidate_joint_q = (candidate[0], candidate[1], candidate[2])
        if candidate_joint_q not in self._cache:
            candidate_final_q = segment_values_from_joint_values(*candidate_joint_q)
            states, dynamics = simulate(
                self.anthro,
                candidate_final_q,
                self.durations,
                self.frame_count,
                self.max_torques,
                self.adapt_max_by_angle,
                self.model_cache,
                self.adapt_max_by_velocity,
            )
            self._cache[candidate_joint_q] = (
                candidate_final_q,
                states,
                dynamics,
                trajectory_metrics(states, dynamics),
            )
            emit_progress(
                self.progress_callback,
                BarPathOptimizationStage.CANDIDATE_EVALUATED,
                self.evaluated_candidates,
                "posture candidate évaluée",
            )
        return self._cache[candidate_joint_q]

    def objective(self, values: Any) -> float:
        """Return the normalized horizontal-motion objective for SLSQP."""

        _final_q, _states, _dynamics, metrics = self.evaluate(values)
        correction = sum(
            ((float(value) - reference) / ANGLE_PERTURBATION_RAD) ** 2
            for value, reference in zip(values, self.requested_joint_q)
        ) / 3.0
        return (
            metrics.horizontal_velocity_energy_m2_s / self.velocity_scale
            + ANCHOR_OBJECTIVE_WEIGHT
            * metrics.horizontal_rms_from_top_m**2
            / self.anchor_scale
            + CORRECTION_OBJECTIVE_WEIGHT * correction
        )

    def constraints(self, values: Any) -> tuple[float, ...]:
        """Return every biomechanical inequality margin for one candidate."""

        candidate_final_q, states, dynamics, _metrics = self.evaluate(values)
        return trajectory_constraint_values(
            self.anthro,
            candidate_final_q,
            states,
            dynamics,
            self.requested_depth,
        )
