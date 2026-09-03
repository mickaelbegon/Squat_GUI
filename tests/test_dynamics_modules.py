"""Regression tests for the modular dynamics compatibility facade."""

from __future__ import annotations

import math

from squat_gui import dynamics
from squat_gui import kinematics
from squat_gui import torque_capacity
from squat_gui.anthropometry import Anthropometry
from squat_gui.biorbd_dynamics import (
    _biorbd_inverse_dynamics_decomposition,
    _biorbd_native_cop,
    _biorbd_native_cop_x,
)
from squat_gui.dynamics_diagnostics import force_balance
from squat_gui.dynamics_models import DynamicsResult, ForceBalance
from squat_gui.dynamics_solver import inverse_dynamics, simulate
from squat_gui.ground_reaction import (
    ground_reaction_and_cop,
    total_com_acceleration,
    total_com_velocity,
)
from squat_gui.joint_dynamics import _contact_moments
from squat_gui.kinematics import PhaseDurations, motion_state


def test_historical_dynamics_public_api_contract():
    """Every domain symbol importable from the pre-split module stays public."""

    expected = {
        "ANDERSON_2007_YOUNG_MALE": torque_capacity.ANDERSON_2007_YOUNG_MALE,
        "ATHLETE_REFERENCE_TORQUES_PER_KG": (
            torque_capacity.ATHLETE_REFERENCE_TORQUES_PER_KG
        ),
        "AndersonTorqueParameters": torque_capacity.AndersonTorqueParameters,
        "Anthropometry": Anthropometry,
        "DynamicsResult": DynamicsResult,
        "ForceBalance": ForceBalance,
        "GRAVITY": torque_capacity.GRAVITY,
        "MotionState": kinematics.MotionState,
        "PhaseDurations": kinematics.PhaseDurations,
        "Pose": kinematics.Pose,
        "TorqueCapacity": torque_capacity.TorqueCapacity,
        "TorquePreset": torque_capacity.TorquePreset,
        "Vector": kinematics.Vector,
        "anderson_angle_domain": torque_capacity.anderson_angle_domain,
        "anderson_angle_factor": torque_capacity.anderson_angle_factor,
        "anderson_reference_max_torques": (
            torque_capacity.anderson_reference_max_torques
        ),
        "anderson_velocity_factor": torque_capacity.anderson_velocity_factor,
        "angle_adapted_max": torque_capacity.angle_adapted_max,
        "angle_derivative_vector": kinematics.angle_derivative_vector,
        "athlete_reference_max_torques": (
            torque_capacity.athlete_reference_max_torques
        ),
        "available_joint_torque_limits": (
            torque_capacity.available_joint_torque_limits
        ),
        "com_accelerations": kinematics.com_accelerations,
        "com_velocities": kinematics.com_velocities,
        "cross_z": kinematics.cross_z,
        "dot": kinematics.dot,
        "force_balance": force_balance,
        "ground_reaction_and_cop": ground_reaction_and_cop,
        "inverse_dynamics": inverse_dynamics,
        "joint_angles_for_limits": torque_capacity.joint_angles_for_limits,
        "joint_angles_from_pose": kinematics.joint_angles_from_pose,
        "joint_torque_capacities": torque_capacity.joint_torque_capacities,
        "joint_values_from_segment_values": (
            kinematics.joint_values_from_segment_values
        ),
        "joint_velocities_for_limits": torque_capacity.joint_velocities_for_limits,
        "local_angle_derivative_vector": kinematics.local_angle_derivative_vector,
        "motion_state": kinematics.motion_state,
        "phase_durations": kinematics.phase_durations,
        "simulate": simulate,
        "sub": kinematics.sub,
        "torque_presets": torque_capacity.torque_presets,
        "total_com_acceleration": total_com_acceleration,
        "total_com_velocity": total_com_velocity,
    }

    assert set(dynamics.__all__) == set(expected)
    for name, implementation in expected.items():
        assert getattr(dynamics, name) is implementation


def test_historical_dynamics_module_reexports_extracted_contracts():
    assert dynamics.DynamicsResult is DynamicsResult
    assert dynamics.ForceBalance is ForceBalance
    assert dynamics.force_balance is force_balance
    assert dynamics.ground_reaction_and_cop is ground_reaction_and_cop
    assert dynamics.inverse_dynamics is inverse_dynamics
    assert dynamics.simulate is simulate
    assert dynamics._contact_moments is _contact_moments
    assert (
        dynamics._biorbd_inverse_dynamics_decomposition
        is _biorbd_inverse_dynamics_decomposition
    )
    assert dynamics._biorbd_native_cop is _biorbd_native_cop
    assert dynamics._biorbd_native_cop_x is _biorbd_native_cop_x


def test_extracted_ground_reaction_closes_force_balance():
    anthro = Anthropometry(bar_mass=35.0, bar_position="front")
    state = motion_state(
        anthro,
        (math.radians(22.0), math.radians(-58.0), math.radians(20.0)),
        PhaseDurations(2.0, 1.0, 2.0),
        1.0,
    )
    result = inverse_dynamics(
        anthro,
        state,
        {"cheville": 222.0, "genou": 380.0, "hanche": 376.0},
        adapt_max_by_angle=True,
    )
    reaction, cop_x, com_acceleration, dynamic_moment_z = ground_reaction_and_cop(
        anthro, state
    )

    assert result.ground_reaction == reaction
    assert result.cop_x == cop_x
    assert result.com_acceleration == com_acceleration
    assert result.dynamic_moment_z == dynamic_moment_z
    residual = force_balance(anthro, result).residual_N
    assert math.isclose(residual[0], 0.0, abs_tol=1e-12)
    assert math.isclose(residual[1], 0.0, abs_tol=1e-12)
