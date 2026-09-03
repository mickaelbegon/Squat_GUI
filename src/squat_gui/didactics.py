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


GuidePiece = tuple[str, str | None]


@dataclass(frozen=True)
class DidacticPathState:
    """Tk-independent state of the eleven-step guided exploration."""

    active: bool
    step: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "step", clamp_didactic_step(self.step))

    @property
    def reveal_mode(self) -> RevealMode:
        return reveal_mode_for_step(self.step)

    @property
    def can_go_back(self) -> bool:
        return self.active and self.step > 0

    @property
    def can_go_forward(self) -> bool:
        return not self.active or self.step < LAST_DIDACTIC_STEP

    def toggled(self) -> "DidacticPathState":
        """Toggle guidance; enabling always starts from the first step."""

        return (
            DidacticPathState(True, 0)
            if not self.active
            else DidacticPathState(False, self.step)
        )

    def advanced(self) -> "DidacticPathState":
        """Move forward, activating the guided path when it was inactive."""

        if not self.active:
            return DidacticPathState(True, 0)
        return DidacticPathState(True, self.step + 1)

    def retreated(self) -> "DidacticPathState":
        """Move backward only while the guided path is active."""

        if not self.active:
            return self
        return DidacticPathState(True, self.step - 1)


@dataclass(frozen=True)
class TemporalPreset:
    name: str
    durations: PhaseDurations


CUSTOM_TEMPORAL_PRESET = "Personnalisé"
# Discrete values exposed by the GUI and the CLI.  Keeping the options here
# avoids having two slightly different timing scales in the student workflow.
DYNAMIC_PHASE_DURATION_OPTIONS = (0.5, 1.0, 2.0, 4.0)
ISOMETRIC_PHASE_DURATION_OPTIONS = (0.0, 0.5, 1.0, 2.0)


DIDACTIC_STEPS: tuple[tuple[GuidePiece, ...], ...] = (
    (
        ("1. Choisir le ", None),
        ("sujet", "sujet"),
        (": profil, longueurs et mode anthropométrique.", None),
    ),
    (
        ("2. Selectionner la ", None),
        ("barre", "barre"),
        (": front, back ou over-head.", None),
    ),
    (
        ("3. Regler la ", None),
        ("charge", "charge"),
        ("; commencer a 0 %BW.", None),
    ),
    (
        ("4. Choisir un ", None),
        ("preset temporel", "phase"),
        (" ou régler les trois durées.", None),
    ),
    (
        ("5. Glisser les articulations pour la ", None),
        ("position basse", "pose"),
        (
            ". Pour un angle précis, faire un clic droit sur cheville, "
            "genou ou hanche, puis valider la valeur sous l'image.",
            None,
        ),
    ),
    (
        ("6. Observer l'", None),
        ("animation", "pose"),
        (" et formuler une hypothèse; les valeurs restent masquées.", None),
    ),
    (
        ("7. Révéler la ", None),
        ("cinématique", "phase"),
        (
            ": vue synchronisée, curseur, inspecteur, phases et repère temporel.",
            None,
        ),
    ),
    (
        ("8. Révéler la ", None),
        ("dynamique", "barre"),
        (
            ": forces, couples détaillés, capacités Anderson angle-vitesse et U demande/capacité.",
            None,
        ),
    ),
    (
        ("9. Cliquer sur ", None),
        ("Ajouter", "pose"),
        (" pour conserver l'essai.", None),
    ),
    (
        ("10. ", None),
        ("Dupliquer", "pose"),
        (" la référence, changer un seul ", None),
        ("paramètre", "charge"),
        (" puis ajouter.", None),
    ),
    (
        ("11. Sélectionner deux lignes et lire ", None),
        ("Variables contrôlées", "phase"),
        (" pour comparer.", None),
    ),
)
LAST_DIDACTIC_STEP = len(DIDACTIC_STEPS) - 1
INACTIVE_DIDACTIC_MESSAGE: tuple[GuidePiece, ...] = (
    ("Activer pour guider une exploration etape par etape.", None),
)

# Semantic target names are intentionally independent from Tk widget/style
# choices.  The GUI remains responsible for mapping them to visual emphasis.
DIDACTIC_FOCUS_KEYS: tuple[tuple[str, ...], ...] = (
    ("subject",),
    ("bar",),
    ("load",),
    ("phase",),
    ("deep_pose",),
    ("animation",),
    ("kinematics",),
    ("dynamics",),
    ("add",),
    ("duplicate",),
    ("comparison",),
)


def clamp_didactic_step(step: int) -> int:
    """Bound a possibly imported/navigation step to the eleven-step path."""

    return min(LAST_DIDACTIC_STEP, max(0, int(step)))


def didactic_step_pieces(step: int) -> tuple[GuidePiece, ...]:
    """Return the tagged French message for a guided step."""

    return DIDACTIC_STEPS[clamp_didactic_step(step)]


def didactic_message(active: bool, step: int) -> tuple[GuidePiece, ...]:
    """Return the current guide text, including its inactive prompt."""

    return didactic_step_pieces(step) if active else INACTIVE_DIDACTIC_MESSAGE


def didactic_focus_keys(step: int) -> tuple[str, ...]:
    """Return semantic UI targets to emphasize for a guided step."""

    return DIDACTIC_FOCUS_KEYS[clamp_didactic_step(step)]


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
