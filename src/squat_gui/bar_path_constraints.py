"""Bounds and biomechanical constraints for bar-path optimization."""

from __future__ import annotations

from itertools import product
from math import radians
from typing import Any, Callable

from .anthropometry import Anthropometry
from .dynamics import DynamicsResult
from .kinematics import MotionState, functional_support_limits, pose_from_angles


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


def anatomical_constraint_values(
    final_q: tuple[float, float, float],
) -> tuple[float, ...]:
    """Return lower- and upper-limit margins for the three joint angles."""

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


def candidate_bounds(
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


def trajectory_constraint_values(
    anthro: Anthropometry,
    candidate_final_q: tuple[float, float, float],
    states: list[MotionState],
    dynamics: list[DynamicsResult],
    requested_depth: float,
) -> tuple[float, ...]:
    """Return the complete SLSQP inequality vector (feasible values >= 0)."""

    values = list(anatomical_constraint_values(candidate_final_q))
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


def find_feasible_start(
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
