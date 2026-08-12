"""Canonical inspectable values derived from simulation states."""

from __future__ import annotations

from dataclasses import dataclass

from .anthropometry import Anthropometry
from .kinematics import (
    MotionState,
    Pose,
    Vector,
    functional_support_limits,
    geometric_support_limits,
    joint_angles_from_pose,
)


@dataclass(frozen=True)
class FrameInfo:
    frame: int
    frame_count: int
    time_s: float
    delta_time_s: float
    normalized_time_percent: float
    phase: str


@dataclass(frozen=True)
class SegmentAnthropometry:
    key: str
    label: str
    mass_kg: float
    mass_fraction_body: float | None
    length_m: float
    com_fraction: float | None
    com_transverse_offset_m: float
    radius_of_gyration_fraction: float | None
    inertia_kg_m2: float
    scaling_mode: str
    scaling_rule: str
    attachment_anterior_offset_m: float | None = None
    attachment_longitudinal_offset_m: float | None = None


@dataclass(frozen=True)
class ComContribution:
    key: str
    label: str
    mass_kg: float
    position_m: Vector
    weighted_position_kg_m: Vector


@dataclass(frozen=True)
class NeighborSample:
    offset: int
    frame: int
    time_s: float
    delta_from_center_s: float
    phase: str
    com_m: Vector
    joint_angles_rad: tuple[float, float, float]


@dataclass(frozen=True)
class SupportMargins:
    point_x_m: float
    geometric_posterior_m: float
    geometric_anterior_m: float
    functional_posterior_m: float
    functional_anterior_m: float
    geometric_posterior_margin_m: float
    geometric_anterior_margin_m: float
    functional_posterior_margin_m: float
    functional_anterior_margin_m: float
    in_geometric_base: bool
    in_functional_base: bool


def frame_info(states: list[MotionState], frame: int) -> FrameInfo:
    if not states:
        raise ValueError("states must contain at least one motion state")
    index = min(len(states) - 1, max(0, int(frame)))
    state = states[index]
    if len(states) == 1:
        delta_time = 0.0
        normalized_time = 0.0
    else:
        neighbor = index + 1 if index < len(states) - 1 else index - 1
        delta_time = abs(states[neighbor].time - state.time)
        duration = states[-1].time - states[0].time
        normalized_time = (
            0.0
            if abs(duration) < 1e-12
            else 100.0 * (state.time - states[0].time) / duration
        )
    return FrameInfo(
        frame=index,
        frame_count=len(states),
        time_s=state.time,
        delta_time_s=delta_time,
        normalized_time_percent=normalized_time,
        phase=state.phase,
    )


def neighbor_samples(
    states: list[MotionState],
    frame: int,
) -> tuple[NeighborSample | None, NeighborSample | None, NeighborSample | None]:
    """Return the available i-1, i and i+1 samples without boundary duplication."""

    if not states:
        raise ValueError("states must contain at least one motion state")
    center_index = min(len(states) - 1, max(0, int(frame)))
    center_time = states[center_index].time
    samples: list[NeighborSample | None] = []
    for offset in (-1, 0, 1):
        index = center_index + offset
        if index < 0 or index >= len(states):
            samples.append(None)
            continue
        state = states[index]
        angles = joint_angles_from_pose(state.pose)
        samples.append(
            NeighborSample(
                offset=offset,
                frame=index,
                time_s=state.time,
                delta_from_center_s=state.time - center_time,
                phase=state.phase,
                com_m=state.pose.com,
                joint_angles_rad=tuple(
                    angles[joint] for joint in ("cheville", "genou", "hanche")
                ),
            )
        )
    return (samples[0], samples[1], samples[2])


def support_margins(pose: Pose, point_x_m: float) -> SupportMargins:
    geometric_posterior, geometric_anterior = geometric_support_limits(pose)
    functional_posterior, functional_anterior = functional_support_limits(pose)
    return SupportMargins(
        point_x_m=point_x_m,
        geometric_posterior_m=geometric_posterior,
        geometric_anterior_m=geometric_anterior,
        functional_posterior_m=functional_posterior,
        functional_anterior_m=functional_anterior,
        geometric_posterior_margin_m=point_x_m - geometric_posterior,
        geometric_anterior_margin_m=geometric_anterior - point_x_m,
        functional_posterior_margin_m=point_x_m - functional_posterior,
        functional_anterior_margin_m=functional_anterior - point_x_m,
        in_geometric_base=geometric_posterior <= point_x_m <= geometric_anterior,
        in_functional_base=functional_posterior <= point_x_m <= functional_anterior,
    )


def joint_coordinates(pose: Pose) -> dict[str, Vector]:
    """Return the points required by F02, in global metres."""

    return {
        "ankle": pose.ankle,
        "knee": pose.knee,
        "hip": pose.hip,
        "shoulder": pose.shoulder,
        "bar": pose.bar,
    }


def segment_anthropometry(anthro: Anthropometry) -> dict[str, SegmentAnthropometry]:
    """Return the effective anthropometric table used by the model."""

    specs = {
        "foot": anthro.foot,
        "shank": anthro.shank,
        "thigh": anthro.thigh,
        "trunk": anthro.trunk,
    }
    rows = {
        key: SegmentAnthropometry(
            key=key,
            label=spec.name,
            mass_kg=spec.mass,
            mass_fraction_body=spec.mass / anthro.body_mass,
            length_m=spec.length,
            com_fraction=spec.com_fraction,
            com_transverse_offset_m=(
                anthro.foot_com_transverse_offset
                if key == "foot"
                else spec.com_anterior_offset
            ),
            radius_of_gyration_fraction=spec.radius_of_gyration,
            inertia_kg_m2=spec.inertia,
            scaling_mode=anthro.scaling_mode,
            scaling_rule=anthro.scaling_rule,
        )
        for key, spec in specs.items()
    }
    rows["bar"] = SegmentAnthropometry(
        key="bar",
        label="barre",
        mass_kg=anthro.bar_mass,
        mass_fraction_body=None,
        length_m=0.0,
        com_fraction=None,
        com_transverse_offset_m=0.0,
        radius_of_gyration_fraction=None,
        inertia_kg_m2=0.0,
        scaling_mode=anthro.scaling_mode,
        scaling_rule=anthro.scaling_rule,
        attachment_anterior_offset_m=anthro.bar_anterior_offset,
        attachment_longitudinal_offset_m=anthro.bar_longitudinal_offset,
    )
    return rows


def com_contributions(anthro: Anthropometry, pose: Pose) -> dict[str, ComContribution]:
    """Return each mass-weighted segment contribution to the global CoM."""

    table = segment_anthropometry(anthro)
    return {
        key: ComContribution(
            key=key,
            label=row.label,
            mass_kg=row.mass_kg,
            position_m=pose.segment_coms[key],
            weighted_position_kg_m=(
                row.mass_kg * pose.segment_coms[key][0],
                row.mass_kg * pose.segment_coms[key][1],
            ),
        )
        for key, row in table.items()
    }


def reconstruct_global_com(contributions: dict[str, ComContribution]) -> Vector:
    total_mass = sum(item.mass_kg for item in contributions.values())
    if total_mass <= 0.0:
        raise ValueError("total mass must be positive")
    return (
        sum(item.weighted_position_kg_m[0] for item in contributions.values())
        / total_mass,
        sum(item.weighted_position_kg_m[1] for item in contributions.values())
        / total_mass,
    )
