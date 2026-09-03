"""Diagnostics derived from inverse-dynamics results."""

from __future__ import annotations

from .anthropometry import Anthropometry
from .dynamics_models import DynamicsResult, ForceBalance
from .torque_capacity import GRAVITY


def force_balance(anthro: Anthropometry, result: DynamicsResult) -> ForceBalance:
    """Return GRF + weight = mass * CoM acceleration in the global frame."""

    weight = anthro.total_mass * GRAVITY
    weight_vector = (0.0, -weight)
    inertial_resultant = (
        anthro.total_mass * result.com_acceleration[0],
        anthro.total_mass * result.com_acceleration[1],
    )
    external_resultant = (
        result.ground_reaction[0] + weight_vector[0],
        result.ground_reaction[1] + weight_vector[1],
    )
    residual = (
        external_resultant[0] - inertial_resultant[0],
        external_resultant[1] - inertial_resultant[1],
    )
    return ForceBalance(
        weight_magnitude_N=weight,
        weight_vector_N=weight_vector,
        inertial_resultant_N=inertial_resultant,
        external_resultant_N=external_resultant,
        residual_N=residual,
    )
