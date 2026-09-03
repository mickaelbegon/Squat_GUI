"""Shared domain model and orchestration for squat conditions."""

from __future__ import annotations

from dataclasses import dataclass
from math import radians
from typing import Iterable

from .anthropometry import Anthropometry, scale_from_percent
from .backend import BiorbdModelCache
from .bar_path_optimization import optimize_deep_squat_bar_path
from .didactics import bounded_phase_durations
from .dynamics import simulate, torque_presets
from .export_schema import JOINTS
from .kinematics import PhaseDurations, frame_count_for_duration
from .simulation_export_rows import build_export_rows, condition_summary


@dataclass(frozen=True)
class Condition:
    """Complete, immutable input required to run one squat simulation."""

    condition_id: str
    load_percent_bw: float
    subject_profile: str
    bar_position: str
    wedge_20_deg: bool
    shank_percent: float
    thigh_percent: float
    trunk_percent: float
    anthropometry_mode: str
    duration_excentrique_s: float
    duration_isometrique_s: float
    duration_concentrique_s: float
    q_segment_deg: tuple[float, float, float]
    torque_preset: str
    max_torques: dict[str, float]
    angle_adapt: bool
    velocity_adapt: bool
    frames: int
    backend: str
    optimize_bar_path_experimental: bool = False

    @property
    def load_kg(self) -> float:
        return 70.0 * self.load_percent_bw / 100.0

    @property
    def phase_durations(self) -> PhaseDurations:
        return PhaseDurations(self.duration_excentrique_s, self.duration_isometrique_s, self.duration_concentrique_s)

    @property
    def total_duration_s(self) -> float:
        return self.phase_durations.total


def anthropometry(condition: Condition) -> Anthropometry:
    """Build the anthropometric model associated with a condition."""
    return Anthropometry(
        bar_mass=condition.load_kg, shank_scale=scale_from_percent(condition.shank_percent),
        thigh_scale=scale_from_percent(condition.thigh_percent), trunk_scale=scale_from_percent(condition.trunk_percent),
        scaling_mode=condition.anthropometry_mode, subject_profile=condition.subject_profile,
        bar_position=condition.bar_position, wedge_angle_deg=20.0 if condition.wedge_20_deg else 0.0,
    )


def condition_from_settings(settings: dict[str, object], final_q_deg: Iterable[float], condition_id: str, *, frames: int | None = None, backend: str = "auto") -> Condition:
    """Build a simulation condition from GUI-compatible settings."""
    legacy_duration = float(settings.get("duration_phase_s", 4.0))
    load_percent_bw = float(settings.get("load_percent_bw", 100.0 * float(settings.get("load_kg", 0.0)) / 70.0))
    preset_name = str(settings.get("torque_preset", "Anderson actif x2"))
    presets = torque_presets(70.0, 1.70)
    default_torques = presets.get(preset_name, presets["Anderson actif x2"]).torques
    max_torques = {joint: float(dict(settings.get("max_torques", {})).get(joint, default_torques[joint])) for joint in JOINTS}
    q_values = tuple(float(value) for value in final_q_deg)
    if len(q_values) != 3:
        raise ValueError("Trois orientations segmentaires finales sont requises.")
    durations = bounded_phase_durations(PhaseDurations(
        float(settings.get("duration_excentrique_s", legacy_duration)), float(settings.get("duration_isometrique_s", 2.0)),
        float(settings.get("duration_concentrique_s", legacy_duration)),
    ))
    frame_count = int(frames or 0)
    if frame_count <= 0:
        frame_count = frame_count_for_duration(durations)
    return Condition(
        condition_id=condition_id, load_percent_bw=load_percent_bw, subject_profile=str(settings.get("subject_profile", "homme")),
        bar_position=str(settings.get("bar_position", "back")), wedge_20_deg=bool(settings.get("wedge_20_deg", False)),
        shank_percent=float(settings.get("shank_percent", 0.0)), thigh_percent=float(settings.get("thigh_percent", 0.0)),
        trunk_percent=float(settings.get("trunk_percent", 0.0)), anthropometry_mode=str(settings.get("anthropometry_mode", "longueur seule")),
        duration_excentrique_s=durations.excentrique, duration_isometrique_s=durations.isometrique,
        duration_concentrique_s=durations.concentrique, q_segment_deg=(q_values[0], q_values[1], q_values[2]),
        torque_preset=preset_name, max_torques=max_torques, angle_adapt=bool(settings.get("angle_adapt", True)),
        velocity_adapt=bool(settings.get("velocity_adapt", True)), frames=max(2, frame_count), backend=backend,
        optimize_bar_path_experimental=bool(settings.get("optimize_bar_path_experimental", False)),
    )


def simulate_condition(condition: Condition) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Run one condition and return detailed rows plus its summary."""
    anthro = anthropometry(condition)
    final_q = tuple(radians(value) for value in condition.q_segment_deg)
    model_cache = None if condition.backend == "analytical" else BiorbdModelCache()
    states, results = simulate(anthro, final_q, condition.phase_durations, condition.frames, condition.max_torques, condition.angle_adapt, model_cache, condition.velocity_adapt)
    optimization = None
    if condition.optimize_bar_path_experimental:
        optimization = optimize_deep_squat_bar_path(anthro, final_q, condition.phase_durations, condition.frames, condition.max_torques, condition.angle_adapt, model_cache, condition.velocity_adapt, baseline=(states, results))
        states, results = optimization.states, optimization.dynamics
    actual_backend = results[0].backend if results else "none"
    if condition.backend == "biorbd" and actual_backend != "biorbd":
        raise RuntimeError("Backend biorbd demande, mais le calcul est tombe sur le backend analytique.")
    rows = build_export_rows(condition, anthro, states, results, optimization)
    return rows, condition_summary(condition, rows, actual_backend)
