"""Tkinter GUI for the 2D squat model."""

from __future__ import annotations

import os
from time import perf_counter

os.environ.setdefault("LANG", "en_US.UTF-8")
os.environ.setdefault("LC_ALL", "en_US.UTF-8")

import tkinter as tk
from collections.abc import Mapping
from math import degrees, radians
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .anthropometry import (
    Anthropometry,
    scale_from_percent,
)
from .backend import BiorbdModelCache, detect_optional_backends
from .bar_path_optimization import (
    BarPathOptimizationResult,
    optimize_deep_squat_bar_path,
)
from .simulation_service import Condition, simulate_condition
from .conditions_controller import ConditionInteractionController
from .dynamics import (
    DynamicsResult,
)
from .didactics import (
    RevealMode,
    bounded_phase_durations,
)
from .kinematics import (
    MotionState,
    PhaseDurations,
    frame_count_for_duration,
)
from .layout_builder import build_layout
from .plot_controller import (
    JOINT_COLORS as JOINT_COLORS,
    PLOT_CHOICES,
    SYNCHRONIZED_KINEMATICS_CHOICE,
    TORQUE_COMPONENT_KEYS,
    PlotCanvasController,
)
from .plot_data import (
    PlotDataset,
    PlotSample,
    centered_times as centered_plot_times,
    current_plot_time as frame_plot_time,
    plot_times as times_for_plot,
)
from .pose_condition_actions import PoseConditionActionsController
from .raster_segments import draw_sprite_segment
from .rendering import RenderLayers
from .scene_canvas import CANVAS_BG, SceneCanvasController
from .scene_model import (
    SceneGeometry,
    project_point_on_line,
)
from .session_persistence import ComparisonReference, SavedCondition
from .session_workflow import SessionWorkflowController
from .timeline import (
    TimeMode,
    time_axis_label,
)
from .torque_capacity import torque_presets
from .ui_state_controller import UiStateController

# La charge est volontairement discrète dans le GUI : cinq niveaux couvrent
# l'absence de barre, une progression intermédiaire et la charge maximale.
# Le modèle accepte encore un flottant côté CLI pour les protocoles avancés.
LOAD_PERCENT_OPTIONS = (0.0, 25.0, 50.0, 75.0, 100.0)


class SquatGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Squat 2D - dynamique inverse")
        self.geometry("1480x920")
        self.minsize(1024, 700)
        self.configure(bg="#f2f4f1")

        self.final_q = (radians(22.0), radians(-58.0), radians(20.0))
        # A single non-modal angle window is reused so a second right click can
        # immediately select another articulation without blocking the canvas.
        self._pose_editor_bounds: tuple[float, float, float, float] | None = None
        self._pose_drag_bounds: tuple[float, float, float, float] | None = None
        self.frame_count = frame_count_for_duration(PhaseDurations())
        self.playing = False
        self._play_started_at: float | None = None
        self._play_start_time_s = 0.0
        self.drag_target: str | None = None
        self._redraw_pending = False
        self._suspend_selection_clear = False
        self.states: list[MotionState] = []
        self.results: list[DynamicsResult] = []
        self.saved_condition_count = 0
        self.saved_conditions: dict[str, SavedCondition] = {}
        self._comparison_reference_iid: str | None = None
        self.backend_status = detect_optional_backends()
        self.model_cache = (
            BiorbdModelCache() if self.backend_status.biorbd_available else None
        )

        self.subject_profile_var = tk.StringVar(value="homme")
        self.bar_position_var = tk.StringVar(value="back")
        self.load_var = tk.DoubleVar(value=0.0)
        self.load_display_var = tk.StringVar(value="0 %BW")
        self.load_var.trace_add("write", self._sync_load_display)
        self.shank_var = tk.DoubleVar(value=0.0)
        self.thigh_var = tk.DoubleVar(value=0.0)
        self.trunk_var = tk.DoubleVar(value=0.0)
        self.anthropometry_mode_var = tk.StringVar(value="longueur seule")
        self.eccentric_duration_var = tk.DoubleVar(value=4.0)
        self.isometric_duration_var = tk.DoubleVar(value=2.0)
        self.concentric_duration_var = tk.DoubleVar(value=4.0)
        # Un preset est une action explicite : les trois durées choisies à la
        # main ne doivent pas être étiquetées automatiquement.
        self.temporal_preset_var = tk.StringVar(value="")
        self.temporal_preset_display_var = tk.StringVar(value="")
        self.wedge_var = tk.BooleanVar(value=False)
        self.frame_var = tk.IntVar(value=self.frame_count // 2)
        self.plot_choice = tk.StringVar(value=PLOT_CHOICES[0])
        self.quantity_var = tk.StringVar(value="position")
        self.synchronized_source_var = tk.StringVar(value="angles articulaires")
        self.show_vars = {
            "cheville": tk.BooleanVar(value=True),
            "genou": tk.BooleanVar(value=True),
            "hanche": tk.BooleanVar(value=True),
        }
        self.show_checkbuttons: dict[str, ttk.Checkbutton] = {}
        self.com_component_vars = {
            "horizontal": tk.BooleanVar(value=True),
            "vertical": tk.BooleanVar(value=True),
        }
        self.torque_component_vars = {
            name: tk.BooleanVar(value=True) for name in TORQUE_COMPONENT_KEYS
        }
        self.quantity_controls: list[tk.Widget] = []
        self.com_controls: list[tk.Widget] = []
        self.torque_preset_var = tk.StringVar(value="Anderson actif x2")
        reference_torques = torque_presets(70.0, 1.70)[
            self.torque_preset_var.get()
        ].torques
        self.max_torque_vars = {
            "cheville": tk.DoubleVar(value=round(reference_torques["cheville"])),
            "genou": tk.DoubleVar(value=round(reference_torques["genou"])),
            "hanche": tk.DoubleVar(value=round(reference_torques["hanche"])),
        }
        self.show_torque_bounds_var = tk.BooleanVar(value=False)
        self.show_sprite_centers_var = tk.BooleanVar(value=False)
        self.show_segment_com_var = tk.BooleanVar(value=False)
        self.show_global_com_var = tk.BooleanVar(value=True)
        self.show_com_projection_var = tk.BooleanVar(value=True)
        self.show_cop_var = tk.BooleanVar(value=True)
        self.show_grf_var = tk.BooleanVar(value=True)
        self.show_weight_var = tk.BooleanVar(value=False)
        self.show_geometric_base_var = tk.BooleanVar(value=False)
        self.show_support_limits_var = tk.BooleanVar(value=True)
        self.show_force_balance_var = tk.BooleanVar(value=False)
        self.show_joint_coordinates_var = tk.BooleanVar(value=False)
        self.show_segment_orientations_var = tk.BooleanVar(value=False)
        self.show_joint_angles_var = tk.BooleanVar(value=False)
        self.show_animation_torques_var = tk.BooleanVar(value=True)
        self.show_anthropometry_var = tk.BooleanVar(value=False)
        self.show_neighbor_samples_var = tk.BooleanVar(value=False)
        self.show_bar_trajectory_var = tk.BooleanVar(value=False)
        self.optimize_bar_path_var = tk.BooleanVar(value=False)
        self.show_moment_arms_var = tk.BooleanVar(value=True)
        self.show_capacity_rings_var = tk.BooleanVar(value=True)
        self.show_joint_markers_var = tk.BooleanVar(value=True)
        self.show_phase_limits_var = tk.BooleanVar(value=True)
        self.show_phase_names_var = tk.BooleanVar(value=True)
        self.low_quality_sprites_var = tk.BooleanVar(value=False)
        self.angle_adapt_var = tk.BooleanVar(value=True)
        self.velocity_adapt_var = tk.BooleanVar(value=True)
        self.subplot_mode_var = tk.BooleanVar(value=True)
        self.time_mode_var = tk.StringVar(value=TimeMode.CENTERED.value)
        self.time_mode_notice_var = tk.StringVar(
            value=time_axis_label(TimeMode.CENTERED)
        )
        self.plot_title_var = tk.StringVar(value="")
        self.frame_info_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value=self.backend_status.message)
        self.bar_path_optimization: BarPathOptimizationResult | None = None
        self.didactic_mode_var = tk.BooleanVar(value=False)
        self.reveal_mode_var = tk.StringVar(value=RevealMode.FREE.value)
        self.didactic_step = 0
        self._reveal_mode_before_didactic = RevealMode.FREE.value
        self._last_reveal_mode = RevealMode.FREE
        self._plot_choice_before_reveal: str | None = None
        self._didactic_canvas_colors: dict[tk.Canvas, str] = {}
        self._animation_hover_targets: list[dict[str, object]] = []
        self._plot_hit_regions: list[
            tuple[float, float, float, float, float, float]
        ] = []

        self._ui_state_controller = UiStateController(
            self, load_percent_options=LOAD_PERCENT_OPTIONS
        )
        self._build_layout()
        self._plot_controller = PlotCanvasController(self)
        self._condition_controller = ConditionInteractionController(
            self, confirm_delete=messagebox.askyesno
        )
        self.recompute()

    def _build_display_menu(self, parent: tk.Misc, *, scope: str) -> ttk.Menubutton:
        return self._ui_state().build_display_menu(parent, scope=scope)

    def on_display_changed(self) -> None:
        self._ui_state().on_display_changed()

    def reveal_mode(self) -> RevealMode:
        return self._ui_state().reveal_mode()

    def set_reveal_mode(self, mode: RevealMode | str) -> None:
        self._ui_state().set_reveal_mode(mode)

    def on_reveal_mode_changed(self) -> None:
        self._ui_state().on_reveal_mode_changed()

    def render_layers(self, *, refined_sprites: bool | None = None) -> RenderLayers:
        return self._ui_state().render_layers(refined_sprites=refined_sprites)

    @staticmethod
    def _configure_didactic_styles(style: ttk.Style) -> None:
        UiStateController.configure_didactic_styles(style)

    def _build_layout(self) -> None:
        """Create the widgets through the dedicated view builder."""

        build_layout(
            self,
            canvas_background=CANVAS_BG,
            plot_choices=tuple(PLOT_CHOICES),
            load_percent_options=LOAD_PERCENT_OPTIONS,
        )

    def _ui_state(self) -> UiStateController:
        """Return the UI-state controller, including for headless callbacks."""

        controller = self.__dict__.get("_ui_state_controller")
        if controller is None:
            controller = UiStateController(
                self, load_percent_options=LOAD_PERCENT_OPTIONS
            )
            self._ui_state_controller = controller
        return controller

    def _update_left_scroll_region(self, _event: tk.Event | None = None) -> None:
        self._ui_state().update_left_scroll_region(_event)

    def _resize_left_contents(self, event: tk.Event) -> None:
        self._ui_state().resize_left_contents(event)

    def _scroll_left_panel(self, event: tk.Event) -> str:
        return self._ui_state().scroll_left_panel(event)

    def _resize_status_text(self, event: tk.Event) -> None:
        self._ui_state().resize_status_text(event)

    def _add_scale(
        self,
        parent: ttk.Frame,
        label: str,
        var: tk.DoubleVar,
        start: float,
        end: float,
        resolution: float,
        row: int,
        columnspan: int = 1,
    ) -> ttk.LabelFrame:
        return self._ui_state().add_scale(
            parent, label, var, start, end, resolution, row, columnspan
        )

    def _sync_load_display(self, *_args: object) -> None:
        self._ui_state().sync_load_display(*_args)

    def on_load_menu_changed(self) -> None:
        self._ui_state().on_load_menu_changed()

    def update_didactic_focus(self) -> None:
        self._ui_state().update_didactic_focus()

    def update_didactic_guide(self) -> None:
        self._ui_state().update_didactic_guide()

    def draw_didactic_switch(self) -> None:
        self._ui_state().draw_didactic_switch()

    def update_didactic_navigation(self) -> None:
        self._ui_state().update_didactic_navigation()

    def toggle_didactic_mode(self) -> None:
        self._ui_state().toggle_didactic_mode()

    def advance_didactic_guide(self) -> None:
        self._ui_state().advance_didactic_guide()

    def retreat_didactic_guide(self) -> None:
        self._ui_state().retreat_didactic_guide()

    def anthro(self) -> Anthropometry:
        return self.anthro_from_settings(
            {
                "load_percent_bw": self.load_var.get(),
                "shank_percent": self.shank_var.get(),
                "thigh_percent": self.thigh_var.get(),
                "trunk_percent": self.trunk_var.get(),
                "anthropometry_mode": self.anthropometry_mode_var.get(),
                "subject_profile": self.subject_profile_var.get(),
                "bar_position": self.bar_position_var.get(),
                "wedge_20_deg": self.wedge_var.get(),
            }
        )

    def anthro_from_settings(self, settings: dict[str, object]) -> Anthropometry:
        load_kg = float(
            settings.get(
                "load_kg", 70.0 * float(settings.get("load_percent_bw", 0.0)) / 100.0
            )
        )
        return Anthropometry(
            bar_mass=load_kg,
            shank_scale=scale_from_percent(float(settings.get("shank_percent", 0.0))),
            thigh_scale=scale_from_percent(float(settings.get("thigh_percent", 0.0))),
            trunk_scale=scale_from_percent(float(settings.get("trunk_percent", 0.0))),
            scaling_mode=str(settings.get("anthropometry_mode", "longueur seule")),
            subject_profile=str(settings.get("subject_profile", "homme")),
            bar_position=str(settings.get("bar_position", "back")),
            wedge_angle_deg=20.0 if bool(settings.get("wedge_20_deg", False)) else 0.0,
        )

    def refined_sprites_from_settings(self, settings: dict[str, object]) -> bool:
        if "low_quality_sprites" in settings:
            return not bool(settings["low_quality_sprites"])
        return bool(settings.get("refined_sprites", True))

    def available_plot_choices(self) -> list[str]:
        mode = self.reveal_mode()
        if mode is RevealMode.OBSERVATION:
            return []
        if mode is RevealMode.KINEMATICS:
            return [
                SYNCHRONIZED_KINEMATICS_CHOICE,
                "cinematique articulaire",
                "centre de masse",
            ]
        return PLOT_CHOICES

    def update_plot_choices(self) -> None:
        choices = self.available_plot_choices()
        self.plot_menu.configure(values=choices)
        self.plot_menu.state(["disabled"] if not choices else ["!disabled", "readonly"])
        if choices and self.plot_choice.get() not in choices:
            self.plot_choice.set(choices[0])
        self.on_plot_choice_changed()

    def max_torques(self) -> dict[str, float]:
        return {
            joint: max(1.0, var.get()) for joint, var in self.max_torque_vars.items()
        }

    def phase_durations(self) -> PhaseDurations:
        return bounded_phase_durations(
            PhaseDurations(
                self.eccentric_duration_var.get(),
                self.isometric_duration_var.get(),
                self.concentric_duration_var.get(),
            )
        )

    @staticmethod
    def phase_durations_from_settings(settings: dict[str, object]) -> PhaseDurations:
        legacy_duration = float(settings.get("duration_phase_s", 4.0))
        return bounded_phase_durations(
            PhaseDurations(
                float(settings.get("duration_excentrique_s", legacy_duration)),
                float(settings.get("duration_isometrique_s", 2.0)),
                float(settings.get("duration_concentrique_s", legacy_duration)),
            )
        )

    def total_motion_duration(self) -> float:
        return self.phase_durations().total

    def centered_times(self, states: list[MotionState] | None = None) -> list[float]:
        states = states or self.states
        return centered_plot_times(states)

    def time_mode(self) -> TimeMode:
        variable = self.__dict__.get("time_mode_var")
        if variable is None:
            return TimeMode.CENTERED
        try:
            return TimeMode(variable.get())
        except ValueError:
            return TimeMode.CENTERED

    def plot_times(self, states: list[MotionState] | None = None) -> list[float]:
        states = states or self.states
        return times_for_plot(states, self.time_mode())

    def current_plot_time(self) -> float:
        datasets = self.plot_datasets()
        frame = min(self.frame_count - 1, max(0, int(self.frame_var.get())))
        return frame_plot_time(
            datasets,
            self.time_mode(),
            frame,
            self.frame_count,
        )

    def on_time_mode_changed(self) -> None:
        self.update_time_mode_notice(self.plot_datasets())
        self.redraw()

    def time_mode_notice(
        self, datasets: list[PlotDataset] | list[dict[str, object]]
    ) -> str:
        mode = self.time_mode()
        base = time_axis_label(mode)
        if mode is not TimeMode.NORMALIZED:
            return base
        durations = {
            round(float(dataset["durations"].total), 9)
            for dataset in datasets
            if isinstance(dataset.get("durations"), PhaseDurations)
        }
        if len(durations) > 1:
            return f"Attention — {base}; les différences de durée sont masquées."
        return f"{base}; la durée réelle est masquée."

    def update_time_mode_notice(self, datasets: list[PlotDataset]) -> None:
        if hasattr(self, "time_mode_notice_var"):
            self.time_mode_notice_var.set(self.time_mode_notice(datasets))

    def _workflow(self) -> SessionWorkflowController:
        """Return the lazily-created settings/session workflow controller."""

        # ``tk.Tk.__getattr__`` assumes a live Tcl interpreter.  Headless
        # tests construct this façade without one, so consult instance state.
        controller = self.__dict__.get("_session_workflow")
        if controller is None:
            # The lambda intentionally resolves this module's public service
            # at call time, preserving extensions which replace it in tests.
            controller = SessionWorkflowController(
                self,
                simulate_condition_fn=lambda condition: simulate_condition(condition),
            )
            self._session_workflow = controller
        return controller

    def apply_torque_preset(self) -> None:
        self._workflow().apply_torque_preset()

    def apply_temporal_preset(self) -> None:
        self._workflow().apply_temporal_preset()

    def on_duration_changed(self) -> None:
        self._workflow().on_duration_changed()

    def on_parameter_changed(self) -> None:
        self._workflow().on_parameter_changed()

    def verticalize_bar(self) -> None:
        """Apply one constrained bar-path optimization to the current pose.

        The optimized segment orientations become the current pose. The button
        is deliberately an action, not a persistent checkbox: pressing it again
        runs a new optimization from those updated orientations.
        """
        if not self._suspend_selection_clear:
            self.clear_condition_selection()
        self.optimize_bar_path_var.set(False)
        button = getattr(self, "optimize_bar_path_button", None)
        if button is not None:
            button.configure(text="Calcul…", state="disabled")
            self.update_idletasks()
        try:
            anthro = self.anthro()
            requested_degrees = tuple(
                round(degrees(value), 2) for value in self.final_q
            )
            print(
                "[Verticalisation] Début SLSQP — angles segmentaires "
                f"(tibia, cuisse, tronc)={requested_degrees}°, "
                f"frames={self.frame_count}, bornes=±5°, contraintes CoP/GRF.",
                flush=True,
            )
            optimization = optimize_deep_squat_bar_path(
                anthro,
                self.final_q,
                self.phase_durations(),
                self.frame_count,
                self.max_torques(),
                self.angle_adapt_var.get(),
                self.model_cache,
                self.velocity_adapt_var.get(),
                baseline=(self.states, self.results),
            )
            self.bar_path_optimization = optimization
            self.states = optimization.states
            self.results = optimization.dynamics
            if optimization.applied:
                self.final_q = optimization.final_q
                self.sync_pose_angle_fields_from_final_q()
                optimized_degrees = tuple(
                    round(degrees(value), 2) for value in optimization.final_q
                )
                print(
                    "[Verticalisation] Convergence appliquée — angles "
                    f"optimisés={optimized_degrees}°; excursion horizontale "
                    f"{100 * optimization.before.horizontal_excursion_m:.1f} → "
                    f"{100 * optimization.after.horizontal_excursion_m:.1f} cm; "
                    f"énergie vₓ² {optimization.before.horizontal_velocity_energy_m2_s:.4g} → "
                    f"{optimization.after.horizontal_velocity_energy_m2_s:.4g} m²/s; "
                    f"marge CoP minimale={100 * optimization.after.minimum_cop_margin_m:.1f} cm.",
                    flush=True,
                )
            else:
                print(
                    f"[Verticalisation] Aucun angle modifié — {optimization.message}",
                    flush=True,
                )
            self.status_var.set(f"{self.status_var.get()} · {optimization.message}")
            self.update_condition_differences()
            self.redraw()
        finally:
            if button is not None:
                button.configure(text="Verticaliser la barre", state="normal")

    def clear_condition_selection(self) -> None:
        self._conditions().clear_selection()

    def recompute(self) -> None:
        self._workflow().recompute()

    def current_settings(self) -> dict[str, object]:
        return self._workflow().current_settings()

    def apply_settings(self, settings: dict[str, object]) -> None:
        self._workflow().apply_settings(settings)

    def save_json(self, path: str | Path | None = None) -> None:
        if path is None:
            selected = filedialog.asksaveasfilename(
                title="Sauver la condition",
                defaultextension=".json",
                filetypes=(("JSON", "*.json"), ("Tous les fichiers", "*.*")),
            )
            if not selected:
                return
            path = selected
        include_conditions = True
        if self.saved_conditions:
            answer = messagebox.askyesnocancel(
                "Sauver les conditions",
                "Inclure aussi les conditions enregistrees dans le tableau ?",
                parent=self,
            )
            if answer is None:
                return
            include_conditions = bool(answer)
        output = self._workflow().save_session(
            path, include_conditions=include_conditions
        )
        self.status_var.set(f"configuration ecrite: {output}")

    def load_json(self, path: str | Path | None = None) -> None:
        if path is None:
            selected = filedialog.askopenfilename(
                title="Charger une condition",
                filetypes=(("JSON", "*.json"), ("Tous les fichiers", "*.*")),
            )
            if not selected:
                return
            path = selected
        source = self._workflow().load_session(path)
        self.status_var.set(f"configuration chargee: {source}")
        self.redraw()

    @staticmethod
    def _condition_export_signature(condition: Condition) -> str:
        """Compatibility delegate for the session-export identity."""

        return SessionWorkflowController._condition_export_signature(condition)

    @staticmethod
    def _normalized_export_id(raw_id: object, fallback: str) -> str:
        """Compatibility delegate for stable export identifiers."""

        return SessionWorkflowController._normalized_export_id(raw_id, fallback)

    @staticmethod
    def _unique_export_id(candidate: str, used_ids: set[str]) -> str:
        """Compatibility delegate for stable export identifiers."""

        return SessionWorkflowController._unique_export_id(candidate, used_ids)

    def session_export_conditions(self) -> list[Condition]:
        """Collect saved conditions and a distinct active editor condition."""

        return self._workflow().session_export_conditions()

    def export_excel(self, path: str | Path | None = None) -> Path | None:
        interactive = path is None
        if path is None:
            selected = filedialog.asksaveasfilename(
                title="Exporter les métriques",
                defaultextension=".xlsx",
                filetypes=(("Classeur Excel", "*.xlsx"), ("Tous les fichiers", "*.*")),
            )
            if not selected:
                return None
            path = selected

        try:
            output = self._workflow().export_excel(path)
        except (OSError, RuntimeError, ValueError) as error:
            self.status_var.set(f"échec export Excel: {error}")
            if interactive:
                messagebox.showerror("Export Excel", str(error), parent=self)
            return None
        self.status_var.set(f"classeur Excel écrit: {output}")
        return output

    def export_csv_results(self, path: str | Path | None = None) -> Path | None:
        """Replace one student CSV with every distinct condition in the session."""
        interactive = path is None
        if path is None:
            selected = filedialog.asksaveasfilename(
                title="Exporter toutes les conditions",
                defaultextension=".csv",
                confirmoverwrite=True,
                filetypes=(
                    ("Données CSV", "*.csv"),
                    ("Tous les fichiers", "*.*"),
                ),
            )
            if not selected:
                return None
            path = selected

        try:
            exported = self._workflow().export_csv(path)
        except (OSError, RuntimeError, ValueError) as error:
            self.status_var.set(f"échec export CSV: {error}")
            if interactive:
                messagebox.showerror("Export CSV", str(error), parent=self)
            return None

        replacement = (
            "Le fichier existant a été remplacé."
            if exported.replaced_existing
            else "Un nouveau fichier a été créé."
        )
        condition_word = "condition" if exported.condition_count == 1 else "conditions"
        exported_word = "exportée" if exported.condition_count == 1 else "exportées"
        message = (
            f"{exported.condition_count} {condition_word} ({exported.frame_count} frames) {exported_word} "
            f"dans {exported.path.name}. {replacement} Aucun ajout automatique."
        )
        self.status_var.set(message)
        if interactive:
            messagebox.showinfo("Export CSV combiné", message, parent=self)
        return exported.path

    def export_video(self, path: str | Path | None = None) -> Path | None:
        interactive = path is None
        if path is None:
            selected = filedialog.asksaveasfilename(
                title="Exporter l'animation",
                defaultextension=".mp4",
                filetypes=(("Vidéo MP4", "*.mp4"), ("Tous les fichiers", "*.*")),
            )
            if not selected:
                return None
            path = selected
        try:
            report = self._workflow().export_video(path)
        except (OSError, RuntimeError, ValueError) as error:
            self.status_var.set(f"échec export MP4: {error}")
            if interactive:
                messagebox.showerror("Export MP4", str(error), parent=self)
            return None
        output = Path(report.path)
        self.status_var.set(
            f"vidéo écrite: {output} · {report.frame_count} frames · {report.fps} fps"
        )
        return output

    def normalized_final_q_deg(self, values: object | None) -> list[float]:
        if isinstance(values, list) and len(values) == 3:
            return [float(value) for value in values]
        return [degrees(value) for value in self.final_q]

    def canvases_ready(self) -> bool:
        return all(
            canvas.winfo_width() > 80 and canvas.winfo_height() > 80
            for canvas in (self.pose_canvas, self.animation_canvas, self.plot_canvas)
        )

    def schedule_redraw(self, _event: tk.Event | None = None) -> None:
        self._ui_state().schedule_redraw(_event)

    def flush_scheduled_redraw(self) -> None:
        self._ui_state().flush_scheduled_redraw()

    def redraw(self) -> None:
        self._ui_state().redraw()

    def on_table_selection_changed(self, _event: tk.Event | None = None) -> None:
        self._conditions().on_selection_changed()

    def _conditions(self) -> ConditionInteractionController:
        """Return the saved-condition controller, including for headless tests."""

        controller = getattr(self, "_condition_controller", None)
        if controller is None:
            controller = ConditionInteractionController(
                self, confirm_delete=messagebox.askyesno
            )
            self._condition_controller = controller
        return controller

    def _plots(self) -> PlotCanvasController:
        """Return the graph controller, including for headless tests."""

        # Avoid ``tk.Tk.__getattr__`` when lightweight tests instantiate the
        # application without creating a Tcl interpreter.
        controller = self.__dict__.get("_plot_controller")
        if controller is None:
            controller = PlotCanvasController(self)
            self._plot_controller = controller
        return controller

    def on_table_tab_changed(self, _event: tk.Event | None = None) -> None:
        """Keep condition actions in a stable position across all tabs."""
        if hasattr(self, "table_buttons"):
            self.table_buttons.grid()
        if hasattr(self, "file_box"):
            self.file_box.grid()

    def update_condition_buttons(self) -> None:
        self._conditions().update_buttons()

    def clear_condition_differences(self) -> None:
        self._conditions().clear_differences()

    def show_condition_differences(
        self,
        reference_settings: dict[str, object],
        reference_final_q_deg: list[float],
        compared_settings: dict[str, object],
        compared_final_q_deg: list[float],
    ) -> None:
        self._conditions().show_differences(
            reference_settings,
            reference_final_q_deg,
            compared_settings,
            compared_final_q_deg,
        )

    def update_condition_differences(self) -> None:
        self._conditions().update_differences()

    def on_table_click(self, event: tk.Event) -> None:
        self._conditions().on_table_click(event)

    def on_plot_choice_changed(self) -> None:
        choice = self.plot_choice.get()
        plots_visible = bool(self.available_plot_choices())
        synchronized = choice == SYNCHRONIZED_KINEMATICS_CHOICE
        synchronized_com = (
            synchronized and self.synchronized_source_var.get() == "centre de masse"
        )
        quantity_plot = choice in ("cinematique articulaire", "centre de masse")
        component_plot = (
            choice in ("centre de masse", "force reaction sol") or synchronized_com
        )
        if synchronized:
            self.quantity_menu.grid_remove()
            self.synchronized_source_menu.grid()
        else:
            self.synchronized_source_menu.grid_remove()
            self.quantity_menu.grid()
        for checkbutton in self.show_checkbuttons.values():
            checkbutton.state(
                ["disabled"] if not plots_visible or component_plot else ["!disabled"]
            )
        for control in self.quantity_controls:
            control.state(
                ["!disabled"] if plots_visible and quantity_plot else ["disabled"]
            )
        for control in self.com_controls:
            control.state(
                ["!disabled"] if plots_visible and component_plot else ["disabled"]
            )
        if synchronized and hasattr(self, "table_notebook"):
            self.table_notebook.select(self.cursor_tab)
            self.on_table_tab_changed()
        self.redraw()

    def _scene_canvas(self) -> SceneCanvasController:
        """Return the canvas renderer, including for headless tests."""

        # ``Tk.__getattr__`` expects an initialized Tcl interpreter. Tests and
        # callers that construct the application with ``object.__new__`` do
        # not have one, so controller lookup must stay in the Python dict.
        controller = self.__dict__.get("_scene_canvas_controller")
        if controller is None:
            controller = SceneCanvasController(self)
            self._scene_canvas_controller = controller
        return controller

    def world_to_canvas(
        self,
        canvas: tk.Canvas,
        point: tuple[float, float],
        bounds: tuple[float, float, float, float],
    ) -> tuple[float, float]:
        return self._scene_canvas().world_to_canvas(canvas, point, bounds)

    def canvas_to_world(
        self,
        canvas: tk.Canvas,
        x: float,
        y: float,
        bounds: tuple[float, float, float, float],
    ) -> tuple[float, float]:
        return self._scene_canvas().canvas_to_world(canvas, x, y, bounds)

    def scene_bounds(
        self,
        extra_x: float = 0.0,
        anthropometries: list[Anthropometry] | None = None,
    ) -> tuple[float, float, float, float]:
        return self._scene_canvas().scene_bounds(extra_x, anthropometries)

    def pose_editor_bounds(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        result: DynamicsResult,
        anthro: Anthropometry,
    ) -> tuple[float, float, float, float]:
        # Keep the historical unbound-call seam used by viewport consumers:
        # their duck-typed owner need not implement ``_scene_canvas``.
        return SceneCanvasController(self).pose_editor_bounds(
            canvas, state, result, anthro
        )

    def cop_in_foot(self, state: MotionState, result: DynamicsResult) -> bool:
        return self._scene_canvas().cop_in_foot(state, result)

    def support_point_in_functional_base(
        self, state: MotionState, result: DynamicsResult
    ) -> bool:
        return self._scene_canvas().support_point_in_functional_base(state, result)

    def com_projection_in_foot(self, state: MotionState) -> bool:
        return self._scene_canvas().com_projection_in_foot(state)

    def over_limit_joints(self, result: DynamicsResult) -> list[str]:
        return self._scene_canvas().over_limit_joints(result)

    def biomechanical_alerts(
        self, state: MotionState, result: DynamicsResult, include_com: bool
    ) -> list[str]:
        return self._scene_canvas().biomechanical_alerts(state, result, include_com)

    def configure_alert_canvas(self, canvas: tk.Canvas, alerts: list[str]) -> None:
        self._scene_canvas().configure_alert_canvas(canvas, alerts)

    def draw_alert_banner(self, canvas: tk.Canvas, alerts: list[str], y: int) -> None:
        self._scene_canvas().draw_alert_banner(canvas, alerts, y)

    def draw_skeleton(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        result: DynamicsResult,
        with_handles: bool,
        bounds: tuple[float, float, float, float] | None = None,
        x_offset: float = 0.0,
        render_anthro: Anthropometry | None = None,
        refined_sprites: bool | None = None,
        layers: RenderLayers | None = None,
    ) -> None:
        self._scene_canvas().draw_skeleton(
            canvas,
            state,
            result,
            with_handles,
            bounds,
            x_offset,
            render_anthro,
            refined_sprites,
            layers,
        )

    def draw_raster_segments(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        mapper,
        render_anthro: Anthropometry | None = None,
        refined_sprites: bool | None = None,
        *,
        scene: SceneGeometry | None = None,
    ) -> bool:
        return self._scene_canvas().draw_raster_segments(
            canvas,
            state,
            mapper,
            render_anthro,
            refined_sprites,
            scene=scene,
            sprite_drawer=draw_sprite_segment,
        )

    def draw_pose_editor(self) -> None:
        self._scene_canvas().draw_pose_editor()

    def draw_squat_angle_labels(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        bounds: tuple[float, float, float, float] | None = None,
    ) -> None:
        self._scene_canvas().draw_squat_angle_labels(canvas, state, bounds)

    def draw_animation(self, frame: int) -> None:
        self._scene_canvas().draw_animation(frame)

    def draw_bar_trajectory(
        self,
        canvas: tk.Canvas,
        states: list[MotionState],
        bounds: tuple[float, float, float, float],
        x_offset: float,
        color: str | None,
    ) -> None:
        self._scene_canvas().draw_bar_trajectory(
            canvas, states, bounds, x_offset, color
        )

    def register_animation_hover_targets(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        bounds: tuple[float, float, float, float],
        x_offset: float,
        condition_label: str,
        include_condition: bool,
        layers: RenderLayers,
    ) -> None:
        self._scene_canvas().register_animation_hover_targets(
            canvas,
            state,
            bounds,
            x_offset,
            condition_label,
            include_condition,
            layers,
        )

    def register_segment_com_hover_targets(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        anthro: Anthropometry,
        bounds: tuple[float, float, float, float],
        x_offset: float,
        condition_label: str,
        include_condition: bool,
        layers: RenderLayers,
    ) -> None:
        self._scene_canvas().register_segment_com_hover_targets(
            canvas,
            state,
            anthro,
            bounds,
            x_offset,
            condition_label,
            include_condition,
            layers,
        )

    def draw_anthropometry_overlay(
        self,
        canvas: tk.Canvas,
        anthro: Anthropometry,
        condition_label: str,
        top_y: int,
    ) -> int:
        return self._scene_canvas().draw_anthropometry_overlay(
            canvas, anthro, condition_label, top_y
        )

    def draw_force_balance_overlay(
        self,
        canvas: tk.Canvas,
        anthro: Anthropometry,
        state: MotionState,
        result: DynamicsResult,
        top_y: int,
    ) -> int:
        return self._scene_canvas().draw_force_balance_overlay(
            canvas, anthro, state, result, top_y
        )

    def draw_neighbor_samples_overlay(
        self,
        canvas: tk.Canvas,
        states: list[MotionState],
        frame: int,
    ) -> None:
        self._scene_canvas().draw_neighbor_samples_overlay(canvas, states, frame)

    def draw_animation_scientific_labels(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        bounds: tuple[float, float, float, float],
        x_offset: float,
        layers: RenderLayers,
    ) -> None:
        self._scene_canvas().draw_animation_scientific_labels(
            canvas, state, bounds, x_offset, layers
        )

    def clear_animation_tooltip(self, event: tk.Event | None = None) -> None:
        self._scene_canvas().clear_animation_tooltip(event)

    def on_animation_motion(self, event: tk.Event) -> None:
        self._scene_canvas().on_animation_motion(event)

    def draw_animation_values(
        self,
        canvas: tk.Canvas,
        sampled: list[PlotSample] | list[dict[str, object]],
    ) -> None:
        self._scene_canvas().draw_animation_values(canvas, sampled)

    def draw_plot(self) -> None:
        return self._plots().draw_plot()

    def synchronized_series_for(
        self,
        source: str,
        quantity: str,
        states: list[MotionState],
        results: list[DynamicsResult],
    ) -> dict[str, list[float]]:
        return self._plots().synchronized_series_for(source, quantity, states, results)

    def kinematic_unit(self, source: str, quantity: str) -> str:
        return self._plots().kinematic_unit(source, quantity)

    def draw_synchronized_kinematics(
        self,
        canvas: tk.Canvas,
        datasets: list[PlotDataset],
        width: int,
        height: int,
    ) -> None:
        return self._plots().draw_synchronized_kinematics(
            canvas, datasets, width, height
        )

    def value_bounds_with_zero(self, values: list[float]) -> tuple[float, float]:
        return self._plots().value_bounds_with_zero(values)

    def draw_zero_line(
        self,
        canvas: tk.Canvas,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
    ) -> None:
        return self._plots().draw_zero_line(canvas, x0, x1, y0, y1, ymin, ymax)

    def draw_synchronized_legend(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        source: str,
        width: int,
    ) -> None:
        return self._plots().draw_synchronized_legend(canvas, plotted, source, width)

    def clear_cursor_table(self) -> None:
        return self._plots().clear_cursor_table()

    def insert_cursor_value(
        self,
        condition: str,
        variable: str,
        value: float,
        unit: str,
        sample_time: float,
        phase: str,
    ) -> None:
        return self._plots().insert_cursor_value(
            condition, variable, value, unit, sample_time, phase
        )

    def update_cursor_table(
        self,
        plotted: list[dict[str, object]],
        choice: str | None = None,
    ) -> None:
        return self._plots().update_cursor_table(plotted, choice)

    def update_synchronized_cursor_table(
        self,
        plotted: list[dict[str, object]],
        source: str,
    ) -> None:
        return self._plots().update_synchronized_cursor_table(plotted, source)

    def plot_datasets(self) -> list[PlotDataset]:
        return self._plots().plot_datasets()

    def sample_dataset_at_time(
        self, dataset: PlotDataset, plot_time: float
    ) -> PlotSample:
        return self._plots().sample_dataset_at_time(dataset, plot_time)

    def animation_time_label(self, plot_time: float) -> str:
        return self._plots().animation_time_label(plot_time)

    def plot_time_bounds(self, plotted: list[dict[str, object]]) -> tuple[float, float]:
        return self._plots().plot_time_bounds(plotted)

    def x_from_time(
        self, time: float, x0: float, x1: float, tmin: float, tmax: float
    ) -> float:
        return self._plots().x_from_time(time, x0, x1, tmin, tmax)

    def condition_color(self, index: int, total: int) -> str:
        return self._plots().condition_color(index, total)

    def blend_color(self, color: str, target: str, fraction: float) -> str:
        return self._plots().blend_color(color, target, fraction)

    def component_color(self, base_color: str, component: str) -> str:
        return self._plots().component_color(base_color, component)

    def visible_torque_components(self) -> tuple[str, ...]:
        return self._plots().visible_torque_components()

    def torque_component_styles(
        self,
    ) -> dict[str, tuple[int, tuple[int, ...] | None, str | None]]:
        return self._plots().torque_component_styles()

    def selected_panel_names(
        self, plotted: list[dict[str, object]], choice: str
    ) -> list[str]:
        return self._plots().selected_panel_names(plotted, choice)

    def draw_subplot_plot(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        choice: str,
        width: int,
        height: int,
    ) -> None:
        return self._plots().draw_subplot_plot(canvas, plotted, choice, width, height)

    def draw_single_axis_plot(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        choice: str,
        width: int,
        height: int,
    ) -> None:
        return self._plots().draw_single_axis_plot(
            canvas, plotted, choice, width, height
        )

    def panel_values(
        self, plotted: list[dict[str, object]], choice: str, panel_name: str
    ) -> list[float]:
        return self._plots().panel_values(plotted, choice, panel_name)

    def value_bounds(
        self, values: list[float], choice: str, panel_name: str | None
    ) -> tuple[float, float]:
        return self._plots().value_bounds(values, choice, panel_name)

    def limit_values_for_plot(self, choice: str, panel_name: str) -> list[float]:
        return self._plots().limit_values_for_plot(choice, panel_name)

    def draw_panel_axes(
        self,
        canvas: tk.Canvas,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        unit: str,
        title: str,
        tmin: float,
        tmax: float,
        show_x_axis: bool = True,
    ) -> None:
        return self._plots().draw_panel_axes(
            canvas, x0, x1, y0, y1, ymin, ymax, unit, title, tmin, tmax, show_x_axis
        )

    def draw_panel_series(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        panel_name: str,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        tmin: float,
        tmax: float,
    ) -> None:
        return self._plots().draw_panel_series(
            canvas, plotted, panel_name, x0, x1, y0, y1, ymin, ymax, tmin, tmax
        )

    def draw_panel_limits(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        choice: str,
        panel_name: str,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        tmin: float,
        tmax: float,
    ) -> None:
        return self._plots().draw_panel_limits(
            canvas, plotted, choice, panel_name, x0, x1, y0, y1, ymin, ymax, tmin, tmax
        )

    def draw_condition_legend(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        width: int,
        height: int,
    ) -> None:
        return self._plots().draw_condition_legend(canvas, plotted, width, height)

    def draw_y_ticks(
        self,
        canvas: tk.Canvas,
        x0: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        grid_right: float | None = None,
    ) -> None:
        return self._plots().draw_y_ticks(canvas, x0, y0, y1, ymin, ymax, grid_right)

    def draw_x_ticks(
        self,
        canvas: tk.Canvas,
        x0: float,
        x1: float,
        y0: float,
        tmin: float,
        tmax: float,
    ) -> None:
        return self._plots().draw_x_ticks(canvas, x0, x1, y0, tmin, tmax)

    def draw_time_markers(
        self,
        canvas: tk.Canvas,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        tmin: float,
        tmax: float,
    ) -> None:
        return self._plots().draw_time_markers(canvas, x0, x1, y0, y1, tmin, tmax)

    def draw_phase_markers(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        tmin: float,
        tmax: float,
    ) -> None:
        return self._plots().draw_phase_markers(
            canvas, plotted, x0, x1, y0, y1, tmin, tmax
        )

    def on_plot_cursor_event(self, event: tk.Event) -> None:
        return self._plots().on_plot_cursor_event(event)

    def format_axis_value(self, value: float) -> str:
        return self._plots().format_axis_value(value)

    def plot_unit(self, choice: str) -> str:
        return self._plots().plot_unit(choice)

    def draw_torque_bounds(
        self,
        canvas: tk.Canvas,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        tmin: float | None = None,
        tmax: float | None = None,
    ) -> None:
        return self._plots().draw_torque_bounds(
            canvas, x0, x1, y0, y1, ymin, ymax, tmin, tmax
        )

    def draw_torque_bound_for_joint(
        self,
        canvas: tk.Canvas,
        joint: str,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        values: list[float] | None = None,
        tmin: float | None = None,
        tmax: float | None = None,
    ) -> None:
        return self._plots().draw_torque_bound_for_joint(
            canvas, joint, x0, x1, y0, y1, ymin, ymax, values, tmin, tmax
        )

    def draw_normalized_torque_limit(
        self,
        canvas: tk.Canvas,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
    ) -> None:
        return self._plots().draw_normalized_torque_limit(
            canvas, x0, x1, y0, y1, ymin, ymax
        )

    def draw_body_weight_line(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
    ) -> None:
        return self._plots().draw_body_weight_line(
            canvas, plotted, x0, x1, y0, y1, ymin, ymax
        )

    def draw_detailed_torque_plot(
        self,
        canvas: tk.Canvas,
        series: dict[str, list[float]],
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
    ) -> None:
        return self._plots().draw_detailed_torque_plot(
            canvas, series, x0, x1, y0, y1, ymin, ymax
        )

    def draw_detailed_panel(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        joint: str,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        tmin: float,
        tmax: float,
    ) -> None:
        return self._plots().draw_detailed_panel(
            canvas, plotted, joint, x0, x1, y0, y1, ymin, ymax, tmin, tmax
        )

    def draw_detailed_component_legend(
        self,
        canvas: tk.Canvas,
        x: float,
        y: float,
        *,
        horizontal: bool = False,
    ) -> None:
        return self._plots().draw_detailed_component_legend(
            canvas, x, y, horizontal=horizontal
        )

    def draw_series_line(
        self,
        canvas: tk.Canvas,
        values: list[float],
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        color: str,
        width: int,
        dash: tuple[int, ...] | None = None,
        times: list[float] | None = None,
        tmin: float | None = None,
        tmax: float | None = None,
    ) -> None:
        return self._plots().draw_series_line(
            canvas,
            values,
            x0,
            x1,
            y0,
            y1,
            ymin,
            ymax,
            color,
            width,
            dash,
            times,
            tmin,
            tmax,
        )

    def draw_triangle_markers(
        self,
        canvas: tk.Canvas,
        values: list[float],
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        ymin: float,
        ymax: float,
        color: str,
        times: list[float] | None = None,
        tmin: float | None = None,
        tmax: float | None = None,
    ) -> None:
        return self._plots().draw_triangle_markers(
            canvas, values, x0, x1, y0, y1, ymin, ymax, color, times, tmin, tmax
        )

    def plot_series(self, choice: str) -> dict[str, list[float]]:
        return self._plots().plot_series(choice)

    def plot_series_for(
        self,
        choice: str,
        states: list[MotionState],
        results: list[DynamicsResult],
    ) -> dict[str, list[float]]:
        return self._plots().plot_series_for(choice, states, results)

    def joint_kinematic_series(
        self, states: list[MotionState] | None = None
    ) -> dict[str, list[float]]:
        return self._plots().joint_kinematic_series(states)

    def joint_kinematic_series_for_quantity(
        self,
        states: list[MotionState],
        quantity: str,
    ) -> dict[str, list[float]]:
        return self._plots().joint_kinematic_series_for_quantity(states, quantity)

    def com_plot_series(
        self, results: list[DynamicsResult] | None = None
    ) -> dict[str, list[float]]:
        return self._plots().com_plot_series(results)

    def com_plot_series_for_quantity(
        self,
        results: list[DynamicsResult],
        quantity: str,
    ) -> dict[str, list[float]]:
        return self._plots().com_plot_series_for_quantity(results, quantity)

    def ground_reaction_plot_series(
        self, results: list[DynamicsResult] | None = None
    ) -> dict[str, list[float]]:
        return self._plots().ground_reaction_plot_series(results)

    def horizontal_vertical_series(
        self, source: list[tuple[float, float]]
    ) -> dict[str, list[float]]:
        return self._plots().horizontal_vertical_series(source)

    def torque_bound_series(self) -> dict[str, list[float]]:
        return self._plots().torque_bound_series()

    def _pose_actions(self) -> PoseConditionActionsController:
        """Return the controller for pose, playback and condition callbacks."""

        controller = self.__dict__.get("_pose_condition_actions")
        if controller is None:
            controller = PoseConditionActionsController(self)
            self._pose_condition_actions = controller
        return controller

    def nearest_handle(self, x: float, y: float) -> str | None:
        return self._pose_actions().nearest_handle(x, y)

    def nearest_joint_angle(self, x: float, y: float) -> str | None:
        """Return the clinical joint selected for a precise right-click edit."""
        return self._pose_actions().nearest_joint_angle(x, y)

    @property
    def _active_pose_angle_joint(self) -> str | None:
        """Compatibility view of the precise-editor selection state."""

        return self.pose_angle_controller.active_joint

    def on_pose_context_menu(self, event: tk.Event) -> str | None:
        return self._pose_actions().on_pose_context_menu(event)

    def on_pose_press(self, event: tk.Event) -> None:
        self._pose_actions().on_pose_press(event)

    def on_pose_drag(self, event: tk.Event) -> None:
        self._pose_actions().on_pose_drag(event)

    @staticmethod
    def format_pose_angle(value: float) -> str:
        """Format a precise degree value without insignificant zeroes."""
        return PoseConditionActionsController.format_pose_angle(value)

    def sync_pose_angle_fields_from_final_q(self) -> None:
        """Refresh the visible editor after a drag without committing input."""
        self._pose_actions().synchronize_pose_angle_fields()

    def open_pose_angle_editor(self, joint: str) -> None:
        """Show the precise-angle editor for ``joint``."""
        self._pose_actions().open_pose_angle_editor(joint)

    def confirm_pose_angle_editor(self, _event: tk.Event | None = None) -> str | None:
        """Delegate explicit validation to the precise-angle controller."""

        return self._pose_actions().confirm_pose_angle_editor(_event)

    def close_pose_angle_editor(self) -> None:
        """Discard the pending value and hide the angle window."""
        self._pose_actions().close_pose_angle_editor()

    # Compatibility entry point for callers that use the former dialog name.
    def open_pose_angle_dialog(self, joint: str) -> None:
        self.open_pose_angle_editor(joint)

    def close_pose_angle_dialog(self, _dialog: tk.Misc | None = None) -> None:
        """Compatibility entry point for the non-modal angle window."""
        self.close_pose_angle_editor()

    def apply_clinical_joint_angle(self, joint: str, raw_value: str) -> bool:
        """Validate and commit one angle only after an explicit dialog action."""
        return self._pose_actions().apply_clinical_joint_angle(joint, raw_value)

    def clamp_final_q(
        self, q: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        return self._pose_actions().clamp_final_q(q)

    def project_on_force_line(
        self,
        joint: tuple[float, float],
        force_origin: tuple[float, float],
        force_vector: tuple[float, float],
    ) -> tuple[float, float]:
        """Compatibility wrapper around the renderer-independent geometry."""

        return project_point_on_line(joint, force_origin, force_vector)

    def on_pose_release(self, _event: tk.Event) -> None:
        self._pose_actions().on_pose_release(_event)

    def toggle_play(self) -> None:
        self._pose_actions().toggle_play(clock=perf_counter)

    def step_animation(self) -> None:
        self._pose_actions().step_animation(clock=perf_counter)

    def record_condition(self) -> None:
        self._pose_actions().record_condition()

    def clear_conditions(self) -> None:
        self._pose_actions().clear_conditions()

    def duplicate_selected_condition(self) -> None:
        self._pose_actions().duplicate_selected_condition()

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
        return self._pose_actions().add_saved_condition(
            settings,
            final_q_deg,
            label=label,
            iid=iid,
            states=states,
            results=results,
            comparison_reference=comparison_reference,
        )

    def delete_selected_conditions(self) -> None:
        self._pose_actions().delete_selected_conditions()

    def simulate_from_condition(
        self,
        settings: dict[str, object],
        final_q_deg: list[float],
    ) -> tuple[list[MotionState], list[DynamicsResult]]:
        return self._pose_actions().simulate_from_condition(settings, final_q_deg)

    def display_joint_angles(
        self, q: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        return self._pose_actions().display_joint_angles(q)


def main() -> None:
    app = SquatGui()
    app.mainloop()
