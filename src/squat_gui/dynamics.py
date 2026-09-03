"""Compatibility facade for the squat inverse-dynamics subsystem.

Consumers may keep importing the historical symbols from this module. The
implementation lives in focused modules so ground reactions, joint moments,
biorbd adaptation, data models and diagnostics can evolve independently.
"""

from __future__ import annotations

from .anthropometry import Anthropometry as Anthropometry
from .backend import resolve_biorbd_model as resolve_biorbd_model
from .biorbd_dynamics import (
    _array_from_biorbd as _array_from_biorbd,
    _biorbd_angular_momentum_derivative_z as _biorbd_angular_momentum_derivative_z,
    _biorbd_contact_torques as _biorbd_contact_torques,
    _biorbd_coordinates as _biorbd_coordinates,
    _biorbd_ground_reaction_and_cop as _biorbd_ground_reaction_and_cop,
    _biorbd_inverse_dynamics_decomposition as _biorbd_inverse_dynamics_decomposition,
    _biorbd_inverse_dynamics_torques as _biorbd_inverse_dynamics_torques,
    _biorbd_motion_state_with_com as _biorbd_motion_state_with_com,
    _biorbd_native_cop as _biorbd_native_cop,
    _biorbd_native_cop_x as _biorbd_native_cop_x,
    _biorbd_tau_from_coordinates as _biorbd_tau_from_coordinates,
    _joint_dict_from_biorbd_tau as _joint_dict_from_biorbd_tau,
    _numpy_biorbd_coordinates as _numpy_biorbd_coordinates,
)
from .dynamics_diagnostics import force_balance as force_balance
from .dynamics_models import DynamicsResult as DynamicsResult
from .dynamics_models import ForceBalance as ForceBalance
from .dynamics_solver import inverse_dynamics as inverse_dynamics
from .dynamics_solver import simulate as simulate
from .ground_reaction import (
    _mass_weighted_segment_vector as _mass_weighted_segment_vector,
    ground_reaction_and_cop as ground_reaction_and_cop,
    total_com_acceleration as total_com_acceleration,
    total_com_velocity as total_com_velocity,
)
from .joint_dynamics import (
    _absolute_generalized_torque as _absolute_generalized_torque,
    _analytical_inverse_dynamics_decomposition as _analytical_inverse_dynamics_decomposition,
    _contact_moments as _contact_moments,
    _jacobians as _jacobians,
    _joint_from_absolute as _joint_from_absolute,
    _segment_forces as _segment_forces,
    _subtract_joint_terms as _subtract_joint_terms,
    _sum_joint_terms as _sum_joint_terms,
)
from .kinematics import MotionState as MotionState
from .kinematics import PhaseDurations as PhaseDurations
from .kinematics import Pose as Pose
from .kinematics import Vector as Vector
from .kinematics import angle_derivative_vector as angle_derivative_vector
from .kinematics import com_accelerations as com_accelerations
from .kinematics import com_velocities as com_velocities
from .kinematics import cross_z as cross_z
from .kinematics import dot as dot
from .kinematics import local_angle_derivative_vector as local_angle_derivative_vector
from .kinematics import motion_state as motion_state
from .kinematics import phase_durations as phase_durations
from .kinematics import sub as sub
from .torque_capacity import GRAVITY as GRAVITY
from .torque_capacity import TorqueCapacity as TorqueCapacity
from .torque_capacity import joint_torque_capacities as joint_torque_capacities


__all__ = [
    "GRAVITY",
    "DynamicsResult",
    "ForceBalance",
    "force_balance",
    "ground_reaction_and_cop",
    "inverse_dynamics",
    "simulate",
    "total_com_acceleration",
    "total_com_velocity",
]
