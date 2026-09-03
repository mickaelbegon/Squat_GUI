"""Typed results produced by inverse-dynamics calculations."""

from __future__ import annotations

from dataclasses import dataclass

from .kinematics import Vector
from .torque_capacity import TorqueCapacity


@dataclass(frozen=True)
class DynamicsResult:
    """Complete dynamics result for one sampled motion state."""

    ground_reaction: Vector
    cop_x: float
    torques: dict[str, float]
    torque_components: dict[str, dict[str, float]]
    powers: dict[str, float]
    effort_ratios: dict[str, float | None]
    torque_capacities: dict[str, TorqueCapacity]
    backend: str = "analytical"
    com: Vector = (0.0, 0.0)
    com_velocity: Vector = (0.0, 0.0)
    com_acceleration: Vector = (0.0, 0.0)
    dynamic_moment_z: float = 0.0
    support_point_label: str = "CoP"
    support_point_source: str = "bilan dynamique analytique"
    contact_source: str = "moment géométrique de la GRF"
    backend_diagnostic: str = "Backend analytique sélectionné."


@dataclass(frozen=True)
class ForceBalance:
    """Terms of the translational force-balance diagnostic."""

    weight_magnitude_N: float
    weight_vector_N: Vector
    inertial_resultant_N: Vector
    external_resultant_N: Vector
    residual_N: Vector
