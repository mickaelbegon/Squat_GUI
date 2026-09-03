"""Settings, session, and export orchestration for the Tk application.

The controller is deliberately independent from Tk widgets.  It receives the
existing application as a small duck-typed view and centralizes the workflow
that turns UI values into simulations, session documents, and student files.
``SquatGui`` remains the public façade for callbacks and dialogs.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import degrees, radians
from pathlib import Path
from typing import Any

from .didactics import (
    TEMPORAL_PRESETS,
    TEMPORAL_PRESETS_BY_NAME,
    temporal_preset_display,
)
from .bar_path_optimization import optimize_deep_squat_bar_path
from .dynamics import simulate
from .export_io import write_csv
from .export_schema import write_xlsx
from .kinematics import frame_count_for_duration
from .session_persistence import GuiSettings, SessionDocument, SessionJsonCodec, SettingsReader
from .simulation_service import Condition, condition_from_settings, simulate_condition
from .torque_capacity import torque_presets
from .video_export import VideoExportReport, export_mp4


@dataclass(frozen=True)
class CsvExportResult:
    """Facts needed by the GUI to report a combined CSV export."""

    path: Path
    condition_count: int
    frame_count: int
    replaced_existing: bool


class SessionWorkflowController:
    """Coordinate mutable GUI settings with persistence and output services.

    ``app`` intentionally remains duck-typed.  It supplies observable Tk
    variables and narrow presentation hooks (redraw/status/condition table),
    while scientific simulation and serialization stay in their dedicated
    modules.  This avoids a circular dependency from service code to ``app``.
    """

    def __init__(
        self,
        app: Any,
        *,
        simulate_condition_fn: Callable[[Condition], tuple[list[dict[str, object]], dict[str, object]]] = simulate_condition,
    ) -> None:
        self.app = app
        self._simulate_condition = simulate_condition_fn

    def apply_torque_preset(self) -> None:
        preset = torque_presets(70.0, 1.70)[self.app.torque_preset_var.get()]
        for joint, torque in preset.torques.items():
            self.app.max_torque_vars[joint].set(round(torque))
        self.app.on_parameter_changed()

    def apply_temporal_preset(self) -> None:
        selected = self.app.temporal_preset_display_var.get()
        if not selected:
            self.app.temporal_preset_var.set("")
            return
        preset = next(
            (
                candidate
                for candidate in TEMPORAL_PRESETS
                if temporal_preset_display(candidate) == selected
            ),
            TEMPORAL_PRESETS_BY_NAME.get(self.app.temporal_preset_var.get()),
        )
        if preset is None:
            return
        self.app.temporal_preset_var.set(preset.name)
        self.app.temporal_preset_display_var.set(temporal_preset_display(preset))
        durations = preset.durations
        self.app.eccentric_duration_var.set(durations.excentrique)
        self.app.isometric_duration_var.set(durations.isometrique)
        self.app.concentric_duration_var.set(durations.concentrique)
        self.app.on_parameter_changed()

    def on_duration_changed(self) -> None:
        self.app.temporal_preset_var.set("")
        self.app.temporal_preset_display_var.set("")
        self.app.on_parameter_changed()

    def on_parameter_changed(self) -> None:
        if not self.app._suspend_selection_clear:
            self.app.clear_condition_selection()
        self.app.recompute()

    def recompute(self) -> None:
        old_count = self.app.frame_count
        old_fraction = self.app.frame_var.get() / max(1, old_count - 1)
        durations = self.app.phase_durations()
        self.app.frame_count = frame_count_for_duration(durations)
        if hasattr(self.app, "frame_scale"):
            self.app.frame_scale.configure(to=self.app.frame_count - 1)
        self.app.frame_var.set(round(old_fraction * (self.app.frame_count - 1)))
        anthro = self.app.anthro()
        self.app.states, self.app.results = simulate(
            anthro,
            self.app.final_q,
            durations,
            self.app.frame_count,
            self.app.max_torques(),
            self.app.angle_adapt_var.get(),
            self.app.model_cache,
            self.app.velocity_adapt_var.get(),
        )
        self.app.bar_path_optimization = None
        if self.app.optimize_bar_path_var.get():
            optimization = optimize_deep_squat_bar_path(
                anthro,
                self.app.final_q,
                durations,
                self.app.frame_count,
                self.app.max_torques(),
                self.app.angle_adapt_var.get(),
                self.app.model_cache,
                self.app.velocity_adapt_var.get(),
                baseline=(self.app.states, self.app.results),
            )
            self.app.bar_path_optimization = optimization
            self.app.states = optimization.states
            self.app.results = optimization.dynamics
        self._set_backend_status(anthro)
        if self.app.bar_path_optimization is not None:
            self.app.status_var.set(
                f"{self.app.status_var.get()} · {self.app.bar_path_optimization.message}"
            )
        self.app.update_condition_differences()
        self.app.redraw()

    def _set_backend_status(self, anthro: object) -> None:
        results = self.app.results
        if (
            results
            and results[0].backend == "biorbd"
            and self.app.model_cache is not None
        ):
            point = results[0]
            self.app.status_var.set(
                f"biorbd actif ({point.support_point_label}: {point.support_point_source}; "
                f"contact: {point.contact_source}): "
                f"{self.app.model_cache.cached_path_for(anthro)}"
            )
        elif results:
            self.app.status_var.set(
                f"backend analytique actif (contact: {results[0].contact_source}): "
                "biorbd indisponible ou modèle non chargé"
            )

    def current_settings(self) -> dict[str, object]:
        app = self.app
        return GuiSettings(
            subject_profile=app.subject_profile_var.get(),
            bar_position=app.bar_position_var.get(),
            load_percent_bw=app.load_var.get(),
            load_kg=app.anthro().bar_mass,
            shank_percent=app.shank_var.get(),
            thigh_percent=app.thigh_var.get(),
            trunk_percent=app.trunk_var.get(),
            anthropometry_mode=app.anthropometry_mode_var.get(),
            duration_excentrique_s=app.eccentric_duration_var.get(),
            duration_isometrique_s=app.isometric_duration_var.get(),
            duration_concentrique_s=app.concentric_duration_var.get(),
            temporal_preset=app.temporal_preset_var.get(),
            wedge_20_deg=app.wedge_var.get(),
            frame=app.frame_var.get(),
            plot_choice=app.plot_choice.get(),
            quantity=app.quantity_var.get(),
            synchronized_source=app.synchronized_source_var.get(),
            show_joints={name: var.get() for name, var in app.show_vars.items()},
            show_com_components={
                name: var.get() for name, var in app.com_component_vars.items()
            },
            show_torque_components={
                name: var.get() for name, var in app.torque_component_vars.items()
            },
            max_torques={joint: var.get() for joint, var in app.max_torque_vars.items()},
            torque_preset=app.torque_preset_var.get(),
            show_torque_bounds=app.show_torque_bounds_var.get(),
            angle_adapt=app.angle_adapt_var.get(),
            velocity_adapt=app.velocity_adapt_var.get(),
            optimize_bar_path_experimental=app.optimize_bar_path_var.get(),
            show_sprite_centers=app.show_sprite_centers_var.get(),
            show_segment_com=app.show_segment_com_var.get(),
            display_layers=self._display_layers(),
            low_quality_sprites=app.low_quality_sprites_var.get(),
            time_mode=app.time_mode().value,
            subplot_mode=app.subplot_mode_var.get(),
            show_phase_limits=app.show_phase_limits_var.get(),
            show_phase_names=app.show_phase_names_var.get(),
            final_q_deg=[degrees(value) for value in app.final_q],
            frame_count=app.frame_count,
        ).to_mapping()

    def _display_layers(self) -> dict[str, bool]:
        app = self.app
        return {
            "global_com": app.show_global_com_var.get(),
            "com_projection": app.show_com_projection_var.get(),
            "segment_com": app.show_segment_com_var.get(),
            "cop_zmp": app.show_cop_var.get(),
            "grf": app.show_grf_var.get(),
            "weight": app.show_weight_var.get(),
            "geometric_base": app.show_geometric_base_var.get(),
            "support_limits": app.show_support_limits_var.get(),
            "force_balance": app.show_force_balance_var.get(),
            "animation_torques": app.show_animation_torques_var.get(),
            "joint_coordinates": app.show_joint_coordinates_var.get(),
            "segment_orientations": app.show_segment_orientations_var.get(),
            "joint_angles": app.show_joint_angles_var.get(),
            "anthropometry": app.show_anthropometry_var.get(),
            "neighbor_samples": app.show_neighbor_samples_var.get(),
            "bar_trajectory": app.show_bar_trajectory_var.get(),
            "moment_arms": app.show_moment_arms_var.get(),
            "capacity_rings": app.show_capacity_rings_var.get(),
            "joint_markers": app.show_joint_markers_var.get(),
        }

    def apply_settings(self, settings: dict[str, object]) -> None:
        app = self.app
        reader = SettingsReader.from_object(settings)
        app._suspend_selection_clear = True
        try:
            app.subject_profile_var.set(reader.text("subject_profile", app.subject_profile_var.get()))
            app.bar_position_var.set(reader.text("bar_position", app.bar_position_var.get()))
            if reader.has("load_percent_bw") or reader.has("load_kg"):
                app.load_var.set(reader.load_percent_bw(app.load_var.get()))
            app.shank_var.set(reader.number("shank_percent", app.shank_var.get()))
            app.thigh_var.set(reader.number("thigh_percent", app.thigh_var.get()))
            app.trunk_var.set(reader.number("trunk_percent", app.trunk_var.get()))
            app.anthropometry_mode_var.set(reader.text("anthropometry_mode", app.anthropometry_mode_var.get()))
            eccentric, isometric, concentric = reader.phase_durations()
            app.eccentric_duration_var.set(eccentric)
            app.isometric_duration_var.set(isometric)
            app.concentric_duration_var.set(concentric)
            self._apply_temporal_preset(reader)
            app.wedge_var.set(reader.flag("wedge_20_deg"))
            app.torque_preset_var.set(reader.text("torque_preset", app.torque_preset_var.get()))
            self._apply_mapping(reader.mapping("max_torques"), app.max_torque_vars, float)
            self._apply_mapping(reader.mapping("show_joints"), app.show_vars, bool)
            component_aliases = {"x": "horizontal", "y": "vertical"}
            for name, value in reader.mapping("show_com_components").items():
                variable = app.com_component_vars.get(component_aliases.get(str(name), str(name)))
                if variable is not None:
                    variable.set(bool(value))
            self._apply_mapping(reader.mapping("show_torque_components"), app.torque_component_vars, bool)
            app.show_torque_bounds_var.set(reader.flag("show_torque_bounds", app.show_torque_bounds_var.get()))
            app.angle_adapt_var.set(reader.flag("angle_adapt", app.angle_adapt_var.get()))
            app.velocity_adapt_var.set(reader.flag("velocity_adapt", app.velocity_adapt_var.get()))
            app.optimize_bar_path_var.set(reader.flag("optimize_bar_path_experimental", app.optimize_bar_path_var.get()))
            app.show_sprite_centers_var.set(reader.flag("show_sprite_centers", app.show_sprite_centers_var.get()))
            app.show_segment_com_var.set(reader.flag("show_segment_com", app.show_segment_com_var.get()))
            self._apply_display_layers(reader.mapping("display_layers"))
            app.low_quality_sprites_var.set(reader.low_quality_sprites())
            app.time_mode_var.set(reader.time_mode())
            app.subplot_mode_var.set(reader.flag("subplot_mode", app.subplot_mode_var.get()))
            app.final_q = app.clamp_final_q(
                tuple(radians(value) for value in app.normalized_final_q_deg(reader.raw("final_q_deg")))
            )
            app.sync_pose_angle_fields_from_final_q()
            app.quantity_var.set(reader.text("quantity", app.quantity_var.get()))
            app.synchronized_source_var.set(reader.text("synchronized_source", app.synchronized_source_var.get()))
            app.show_phase_limits_var.set(reader.flag("show_phase_limits", app.show_phase_limits_var.get()))
            app.show_phase_names_var.set(reader.flag("show_phase_names", app.show_phase_names_var.get()))
            plot_choice = reader.text("plot_choice", app.plot_choice.get())
            app.update_plot_choices()
            if plot_choice in app.available_plot_choices():
                app.plot_choice.set(plot_choice)
            app.frame_var.set(reader.integer("frame", app.frame_var.get()))
            app.on_plot_choice_changed()
        finally:
            app._suspend_selection_clear = False
        self.app.recompute()

    @staticmethod
    def _apply_mapping(values: Mapping[str, object], variables: Mapping[str, Any], convert: Callable[[object], object]) -> None:
        for name, value in values.items():
            variable = variables.get(str(name))
            if variable is not None:
                variable.set(convert(value))

    def _apply_temporal_preset(self, reader: SettingsReader) -> None:
        loaded_preset = reader.text("temporal_preset")
        preset = TEMPORAL_PRESETS_BY_NAME.get(loaded_preset)
        self.app.temporal_preset_var.set(preset.name if preset is not None else "")
        self.app.temporal_preset_display_var.set(
            temporal_preset_display(preset) if preset is not None else ""
        )

    def _apply_display_layers(self, display_layers: Mapping[str, object]) -> None:
        app = self.app
        variables = {
            "global_com": app.show_global_com_var,
            "com_projection": app.show_com_projection_var,
            "segment_com": app.show_segment_com_var,
            "cop_zmp": app.show_cop_var,
            "grf": app.show_grf_var,
            "weight": app.show_weight_var,
            "geometric_base": app.show_geometric_base_var,
            "support_limits": app.show_support_limits_var,
            "force_balance": app.show_force_balance_var,
            "animation_torques": app.show_animation_torques_var,
            "joint_coordinates": app.show_joint_coordinates_var,
            "segment_orientations": app.show_segment_orientations_var,
            "joint_angles": app.show_joint_angles_var,
            "anthropometry": app.show_anthropometry_var,
            "neighbor_samples": app.show_neighbor_samples_var,
            "bar_trajectory": app.show_bar_trajectory_var,
            "moment_arms": app.show_moment_arms_var,
            "capacity_rings": app.show_capacity_rings_var,
            "joint_markers": app.show_joint_markers_var,
        }
        self._apply_mapping(display_layers, variables, bool)

    def save_session(self, path: str | Path, *, include_conditions: bool) -> Path:
        output = Path(path)
        document = SessionDocument.from_runtime(
            self.current_settings(),
            self.app.saved_conditions if include_conditions else {},
        )
        SessionJsonCodec.write(output, document)
        return output

    def load_session(self, path: str | Path) -> Path:
        source = Path(path)
        document = SessionJsonCodec.read(source)
        self.app.clear_conditions()
        self.apply_settings(document.settings)
        for condition in document.conditions:
            self.app.add_saved_condition(
                settings=dict(condition.settings),
                final_q_deg=list(condition.final_q_deg),
                label=condition.label or None,
                iid=condition.iid or None,
                comparison_reference=condition.comparison_reference,
            )
        return source

    @staticmethod
    def _condition_export_signature(condition: Condition) -> str:
        def canonical(value: object) -> object:
            if isinstance(value, float):
                return round(value, 9)
            if isinstance(value, dict):
                return {str(key): canonical(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
            if isinstance(value, (list, tuple)):
                return [canonical(item) for item in value]
            return value

        payload = {key: canonical(value) for key, value in condition.__dict__.items() if key != "condition_id"}
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _normalized_export_id(raw_id: object, fallback: str) -> str:
        identifier = "".join(character if character.isalnum() else "_" for character in str(raw_id).strip())
        while "__" in identifier:
            identifier = identifier.replace("__", "_")
        return identifier.strip("_") or fallback

    @staticmethod
    def _unique_export_id(candidate: str, used_ids: set[str]) -> str:
        if candidate not in used_ids:
            used_ids.add(candidate)
            return candidate
        suffix = 2
        while f"{candidate}_{suffix}" in used_ids:
            suffix += 1
        unique = f"{candidate}_{suffix}"
        used_ids.add(unique)
        return unique

    def session_export_conditions(self) -> list[Condition]:
        conditions: list[Condition] = []
        saved_signatures: set[str] = set()
        used_ids: set[str] = set()
        for index, (iid, saved) in enumerate(self.app.saved_conditions.items(), start=1):
            results = list(saved.get("results", []))
            backend = results[0].backend if results else "analytical"
            condition_id = self._unique_export_id(self._normalized_export_id(iid, f"condition_{index}"), used_ids)
            condition = condition_from_settings(dict(saved["settings"]), list(saved["final_q_deg"]), condition_id, backend=backend)
            conditions.append(condition)
            saved_signatures.add(self._condition_export_signature(condition))
        current_backend = self.app.results[0].backend if self.app.results else "analytical"
        current = condition_from_settings(
            self.app.current_settings(),
            [degrees(value) for value in self.app.final_q],
            "condition_courante",
            backend=current_backend,
        )
        if self._condition_export_signature(current) not in saved_signatures:
            current_id = self._unique_export_id("condition_courante", used_ids)
            if current_id != current.condition_id:
                current = condition_from_settings(
                    self.app.current_settings(),
                    [degrees(value) for value in self.app.final_q],
                    current_id,
                    backend=current_backend,
                )
            conditions.append(current)
        return conditions

    def export_excel(self, path: str | Path) -> Path:
        exports = [
            (
                "condition_courante",
                self.app.current_settings(),
                [degrees(value) for value in self.app.final_q],
                self.app.results[0].backend if self.app.results else "analytical",
            )
        ]
        exports.extend(
            (
                f"condition_{condition['label']}",
                dict(condition["settings"]),
                list(condition["final_q_deg"]),
                condition["results"][0].backend if condition["results"] else "analytical",
            )
            for condition in self.app.saved_conditions.values()
        )
        rows: list[dict[str, object]] = []
        for condition_id, settings, final_q_deg, backend in exports:
            condition = condition_from_settings(settings, final_q_deg, condition_id, backend=backend)
            condition_rows, _summary = self._simulate_condition(condition)
            rows.extend(condition_rows)
        output = Path(path)
        write_xlsx(output, rows)
        return output

    def export_csv(self, path: str | Path) -> CsvExportResult:
        output = Path(path)
        replaced_existing = output.exists()
        conditions = self.session_export_conditions()
        rows: list[dict[str, object]] = []
        for condition in conditions:
            condition_rows, _summary = self._simulate_condition(condition)
            rows.extend(condition_rows)
        write_csv(output, rows, mode="standard")
        return CsvExportResult(output, len(conditions), len(rows), replaced_existing)

    def export_video(self, path: str | Path) -> VideoExportReport:
        return export_mp4(
            path,
            self.app.anthro(),
            self.app.states,
            self.app.results,
            self.app.render_layers(),
        )
