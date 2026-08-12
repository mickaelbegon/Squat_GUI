"""Didactic timing presets and progressive scientific reveal states."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .kinematics import PhaseDurations
from .rendering import RenderLayers


class RevealMode(str, Enum):
    FREE = "LIBRE"
    OBSERVATION = "OBSERVATION"
    KINEMATICS = "CINÉMATIQUE"
    DYNAMICS = "DYNAMIQUE"


@dataclass(frozen=True)
class TemporalPreset:
    name: str
    durations: PhaseDurations


CUSTOM_TEMPORAL_PRESET = "Personnalisé"
TEMPORAL_PRESETS = (
    TemporalPreset("Référence", PhaseDurations(4.0, 2.0, 4.0)),
    TemporalPreset("Lent", PhaseDurations(6.0, 2.0, 6.0)),
    TemporalPreset("Rapide", PhaseDurations(2.0, 0.5, 2.0)),
    TemporalPreset("Sans pause", PhaseDurations(4.0, 0.0, 4.0)),
    TemporalPreset(
        "Descente lente / remontée rapide",
        PhaseDurations(6.0, 1.0, 2.0),
    ),
    TemporalPreset(
        "Descente rapide / remontée lente",
        PhaseDurations(2.0, 1.0, 6.0),
    ),
)
TEMPORAL_PRESETS_BY_NAME = {preset.name: preset for preset in TEMPORAL_PRESETS}


def matching_temporal_preset(durations: PhaseDurations, tolerance: float = 1e-9) -> str:
    for preset in TEMPORAL_PRESETS:
        candidate = preset.durations
        if all(
            abs(actual - expected) <= tolerance
            for actual, expected in zip(
                (durations.excentrique, durations.isometrique, durations.concentrique),
                (candidate.excentrique, candidate.isometrique, candidate.concentrique),
            )
        ):
            return preset.name
    return CUSTOM_TEMPORAL_PRESET


def reveal_mode_for_step(step: int) -> RevealMode:
    """Map the guided path to a monotonic scientific reveal."""
    if step <= 5:
        return RevealMode.OBSERVATION
    if step == 6:
        return RevealMode.KINEMATICS
    return RevealMode.DYNAMICS


def layers_for_reveal(
    mode: RevealMode | str,
    *,
    refined_sprites: bool = True,
) -> RenderLayers:
    mode = RevealMode(mode)
    if mode is RevealMode.OBSERVATION:
        return RenderLayers(
            global_com=False,
            com_projection=False,
            segment_com=False,
            cop_zmp=False,
            grf=False,
            weight=False,
            geometric_base=False,
            functional_base=False,
            force_balance=False,
            joint_coordinates=False,
            segment_orientations=False,
            joint_angles=False,
            anthropometry=False,
            moment_arms=False,
            capacity_rings=False,
            joint_markers=False,
            alerts=False,
            time_label=False,
            refined_sprites=refined_sprites,
        )
    if mode is RevealMode.KINEMATICS:
        return RenderLayers(
            global_com=True,
            com_projection=True,
            segment_com=False,
            cop_zmp=False,
            grf=False,
            weight=False,
            geometric_base=False,
            functional_base=False,
            force_balance=False,
            joint_coordinates=True,
            segment_orientations=False,
            joint_angles=False,
            anthropometry=False,
            moment_arms=False,
            capacity_rings=False,
            joint_markers=True,
            alerts=False,
            time_label=True,
            refined_sprites=refined_sprites,
        )
    if mode is RevealMode.DYNAMICS:
        return RenderLayers(
            global_com=True,
            com_projection=True,
            segment_com=False,
            cop_zmp=True,
            grf=True,
            weight=True,
            geometric_base=True,
            functional_base=True,
            force_balance=False,
            joint_coordinates=True,
            segment_orientations=False,
            joint_angles=False,
            anthropometry=False,
            moment_arms=True,
            capacity_rings=True,
            joint_markers=True,
            alerts=True,
            time_label=True,
            refined_sprites=refined_sprites,
        )
    raise ValueError("Le mode LIBRE utilise les choix de couches de l'interface.")
