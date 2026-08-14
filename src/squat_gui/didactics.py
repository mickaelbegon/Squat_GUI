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
# Discrete values exposed by the GUI and the CLI.  Keeping the options here
# avoids having two slightly different timing scales in the student workflow.
DYNAMIC_PHASE_DURATION_OPTIONS = (0.5, 1.0, 2.0, 4.0)
ISOMETRIC_PHASE_DURATION_OPTIONS = (0.0, 0.5, 1.0, 2.0)


def phase_duration_triplet(durations: PhaseDurations) -> str:
    """Format descente | isométrique | montée for the GUI and documents."""
    return " | ".join(
        f"{value:g}"
        for value in (
            durations.excentrique,
            durations.isometrique,
            durations.concentrique,
        )
    )


def temporal_preset_display(preset: TemporalPreset) -> str:
    """Return a human-readable preset label with its three durations."""
    return f"{preset.name} — {phase_duration_triplet(preset.durations)} s"


def _nearest_duration_option(value: float, options: tuple[float, ...]) -> float:
    """Map legacy/imported values to the nearest currently exposed option."""
    return min(options, key=lambda option: (abs(option - value), -option))


def bounded_phase_durations(durations: PhaseDurations) -> PhaseDurations:
    """Keep imported GUI/CLI settings within the current discrete duration scale."""
    return PhaseDurations(
        _nearest_duration_option(
            durations.excentrique, DYNAMIC_PHASE_DURATION_OPTIONS
        ),
        _nearest_duration_option(
            durations.isometrique, ISOMETRIC_PHASE_DURATION_OPTIONS
        ),
        _nearest_duration_option(
            durations.concentrique, DYNAMIC_PHASE_DURATION_OPTIONS
        ),
    )

TEMPORAL_PRESETS = (
    TemporalPreset("Ref", PhaseDurations(2.0, 1.0, 2.0)),
    TemporalPreset("Lent", PhaseDurations(4.0, 2.0, 4.0)),
    TemporalPreset("Rapide", PhaseDurations(1.0, 0.5, 1.0)),
    TemporalPreset("Lent/Rapide", PhaseDurations(4.0, 1.0, 1.0)),
    TemporalPreset("Rapide/Lent", PhaseDurations(1.0, 1.0, 4.0)),
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
