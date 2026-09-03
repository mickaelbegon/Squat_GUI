"""Tk-facing actions for pose editing, playback and saved conditions.

This module groups callbacks that operate on the active pose or on the
recorded-conditions workspace.  It keeps :class:`~squat_gui.app.SquatGui`
as the public callback surface expected by the layout and existing scripts,
while avoiding another collection of unrelated UI behaviour in ``app.py``.

The anatomical rules are delegated to :mod:`squat_gui.pose_editing`, precise
input widgets to :mod:`squat_gui.pose_angle_dialog`, and persistence/table
work to :mod:`squat_gui.conditions_controller`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from math import radians
from time import perf_counter
from typing import Any

import tkinter as tk

from .bar_path_optimization import optimize_deep_squat_bar_path
from .didactics import reveal_mode_for_step
from .dynamics import DynamicsResult, simulate
from .kinematics import (
    DEFAULT_SAMPLE_PERIOD_S,
    MotionState,
    frame_count_for_duration,
    pose_from_angles,
)
from .pose_editing import (
    apply_clinical_angle,
    clamp_segment_angles,
    clinical_joint_angles_deg,
    drag_updated_q,
    format_pose_angle,
    nearest_named_point,
)
from .session_persistence import ComparisonReference


class PoseConditionActionsController:
    """Coordinate the interactive actions of one ``SquatGui`` instance.

    The application is deliberately duck-typed.  This keeps this adapter
    independent of the concrete Tk root and lets callback mechanics be tested
    with a small fake application.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    @staticmethod
    def format_pose_angle(value: float) -> str:
        """Format a precise degree value without insignificant zeroes."""

        return format_pose_angle(value)

    def nearest_handle(self, x: float, y: float) -> str | None:
        anthro = self.app.anthro()
        pose = pose_from_angles(anthro, self.app.final_q)
        bounds = getattr(self.app, "_pose_editor_bounds", None) or self.app.scene_bounds()
        candidates = {"knee": pose.knee, "hip": pose.hip, "shoulder": pose.shoulder}
        canvas_candidates = {
            name: self.app.world_to_canvas(self.app.pose_canvas, point, bounds)
            for name, point in candidates.items()
        }
        return nearest_named_point(x, y, canvas_candidates)

    def nearest_joint_angle(self, x: float, y: float) -> str | None:
        """Return the clinical joint selected for a precise right-click edit."""

        pose = pose_from_angles(self.app.anthro(), self.app.final_q)
        bounds = getattr(self.app, "_pose_editor_bounds", None) or self.app.scene_bounds()
        candidates = {
            "cheville": pose.ankle,
            "genou": pose.knee,
            "hanche": pose.hip,
        }
        canvas_candidates = {
            joint: self.app.world_to_canvas(self.app.pose_canvas, point, bounds)
            for joint, point in candidates.items()
        }
        return nearest_named_point(x, y, canvas_candidates)

    def on_pose_context_menu(self, event: tk.Event) -> str | None:
        joint = self.nearest_joint_angle(event.x, event.y)
        if joint is None:
            return None
        self.app.open_pose_angle_editor(joint)
        return "break"

    def on_pose_press(self, event: tk.Event) -> None:
        self.app._pose_drag_bounds = (
            getattr(self.app, "_pose_editor_bounds", None) or self.app.scene_bounds()
        )
        self.app.drag_target = self.nearest_handle(event.x, event.y)

    def on_pose_drag(self, event: tk.Event) -> None:
        if not self.app.drag_target:
            return
        anthro = self.app.anthro()
        pose = pose_from_angles(anthro, self.app.final_q)
        point = self.app.canvas_to_world(
            self.app.pose_canvas,
            event.x,
            event.y,
            self.app._pose_drag_bounds
            or getattr(self.app, "_pose_editor_bounds", None)
            or self.app.scene_bounds(),
        )
        self.app.final_q = drag_updated_q(
            self.app.final_q, self.app.drag_target, point, pose
        )
        self.app.sync_pose_angle_fields_from_final_q()
        self.app.on_parameter_changed()

    def synchronize_pose_angle_fields(self) -> None:
        """Refresh an open precise editor after a drag without committing it."""

        self.app.pose_angle_controller.synchronize(self.app.final_q)

    def open_pose_angle_editor(self, joint: str) -> None:
        self.app.pose_angle_controller.open(joint, self.app.final_q)

    def confirm_pose_angle_editor(self, event: tk.Event | None = None) -> str | None:
        return self.app.pose_angle_controller.confirm(event)

    def close_pose_angle_editor(self) -> None:
        self.app.pose_angle_controller.close()

    def apply_clinical_joint_angle(self, joint: str, raw_value: str) -> bool:
        """Validate and commit one angle only after an explicit dialog action."""

        update = apply_clinical_angle(self.app.final_q, joint, raw_value)
        if not update.accepted:
            self.app.status_var.set(update.error_message or "angle invalide")
            return False
        if update.q is None or update.bounded_deg is None:
            raise RuntimeError("mise à jour clinique incomplète")
        self.app.final_q = update.q
        self.app.on_parameter_changed()
        if update.was_clamped:
            self.app.status_var.set(
                "limite anatomique appliquée : "
                f"{joint} {format_pose_angle(update.bounded_deg)}°"
            )
        return True

    @staticmethod
    def clamp_final_q(
        q: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        return clamp_segment_angles(q)

    def on_pose_release(self, _event: tk.Event) -> None:
        self.app.drag_target = None
        self.app._pose_drag_bounds = None

    def toggle_play(self, *, clock: Callable[[], float] = perf_counter) -> None:
        self.app.playing = not self.app.playing
        self.app.play_button.configure(text="⏸" if self.app.playing else "▶")
        if self.app.playing:
            self.app._play_started_at = clock()
            self.app._play_start_time_s = (
                self.app.frame_var.get() * DEFAULT_SAMPLE_PERIOD_S
            )
            self.step_animation(clock=clock)
        else:
            self.app._play_started_at = None

    def step_animation(self, *, clock: Callable[[], float] = perf_counter) -> None:
        if not self.app.playing:
            return
        duration_s = max(
            DEFAULT_SAMPLE_PERIOD_S,
            (self.app.frame_count - 1) * DEFAULT_SAMPLE_PERIOD_S,
        )
        started_at = (
            self.app._play_started_at
            if self.app._play_started_at is not None
            else clock()
        )
        elapsed_s = clock() - started_at
        target_time_s = (self.app._play_start_time_s + elapsed_s) % duration_s
        self.app.frame_var.set(round(target_time_s / DEFAULT_SAMPLE_PERIOD_S))
        self.app.redraw()
        self.app.after(
            round(1000 * DEFAULT_SAMPLE_PERIOD_S), self.app.step_animation
        )

    def record_condition(self) -> None:
        self.app._conditions().record()
        if self.app.didactic_mode_var.get() and self.app.didactic_step < 9:
            self.app.didactic_step = 9
            self.app.set_reveal_mode(reveal_mode_for_step(self.app.didactic_step))
            self.app.update_didactic_guide()

    def clear_conditions(self) -> None:
        self.app._conditions().clear()

    def duplicate_selected_condition(self) -> None:
        self.app._conditions().duplicate_selected()

    def add_saved_condition(
        self,
        settings: dict[str, object],
        final_q_deg: list[float],
        label: str | None = None,
        iid: str | None = None,
        states: list[MotionState] | None = None,
        results: list[DynamicsResult] | None = None,
        comparison_reference: ComparisonReference | Mapping[str, object] | None = None,
    ) -> str:
        return self.app._conditions().add_saved_condition(
            settings,
            final_q_deg,
            label=label,
            iid=iid,
            states=states,
            results=results,
            comparison_reference=comparison_reference,
        )

    def delete_selected_conditions(self) -> None:
        self.app._conditions().delete_selected()

    def simulate_from_condition(
        self,
        settings: dict[str, object],
        final_q_deg: list[float],
    ) -> tuple[list[MotionState], list[DynamicsResult]]:
        anthro = self.app.anthro_from_settings(settings)
        final_q = self.clamp_final_q(
            tuple(
                radians(value)
                for value in self.app.normalized_final_q_deg(final_q_deg)
            )
        )
        max_torques = {
            joint: float(
                dict(settings.get("max_torques", {})).get(
                    joint, self.app.max_torque_vars[joint].get()
                )
            )
            for joint in ("cheville", "genou", "hanche")
        }
        durations = self.app.phase_durations_from_settings(settings)
        baseline = simulate(
            anthro,
            final_q,
            durations,
            frame_count_for_duration(durations),
            max_torques,
            bool(settings.get("angle_adapt", self.app.angle_adapt_var.get())),
            self.app.model_cache,
            bool(settings.get("velocity_adapt", self.app.velocity_adapt_var.get())),
        )
        if not bool(settings.get("optimize_bar_path_experimental", False)):
            return baseline
        optimization = optimize_deep_squat_bar_path(
            anthro,
            final_q,
            durations,
            frame_count_for_duration(durations),
            max_torques,
            bool(settings.get("angle_adapt", self.app.angle_adapt_var.get())),
            self.app.model_cache,
            bool(settings.get("velocity_adapt", self.app.velocity_adapt_var.get())),
            baseline=baseline,
        )
        return optimization.states, optimization.dynamics

    @staticmethod
    def display_joint_angles(
        q: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        return clinical_joint_angles_deg(q)
