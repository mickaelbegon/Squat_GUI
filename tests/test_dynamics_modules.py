"""Regression tests for the modular dynamics compatibility facade."""

from __future__ import annotations

import math

from squat_gui import dynamics
from squat_gui.anthropometry import Anthropometry
from squat_gui.biorbd_dynamics import (
    _biorbd_inverse_dynamics_decomposition,
    _biorbd_native_cop,
    _biorbd_native_cop_x,
)
from squat_gui.dynamics_diagnostics import force_balance
from squat_gui.dynamics_models import DynamicsResult, ForceBalance
from squat_gui.dynamics_solver import inverse_dynamics, simulate
from squat_gui.ground_reaction import ground_reaction_and_cop
from squat_gui.joint_dynamics import _contact_moments
from squat_gui.kinematics import PhaseDurations, motion_state


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
