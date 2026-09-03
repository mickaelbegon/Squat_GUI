"""Presentation-state callbacks for the Tk application.

This module owns the UI-only state transitions shared by the layout: display
layers, the progressive didactic guide, scrolling, discrete load selection and
deferred canvas redraws.  Scientific settings and rendering implementations
remain services of the application; this adapter merely coordinates widgets
and preserves the long-standing ``SquatGui`` callback surface.
"""

from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk

from .didactics import (
    DidacticPathState,
    RevealMode,
    didactic_focus_keys,
    didactic_message,
    layers_for_reveal,
)
from .observables import frame_info
from .plot_controller import PLOT_CHOICES, SYNCHRONIZED_KINEMATICS_CHOICE
from .rendering import RenderLayers


class UiStateController:
    """Coordinate UI state for one application without owning its domain data.

    ``app`` is intentionally duck-typed so these callbacks can be tested with
    lightweight fakes and so the controller does not import :mod:`app`.
    """

    def __init__(self, app: Any, *, load_percent_options: tuple[float, ...]) -> None:
        self.app = app
        self.load_percent_options = load_percent_options

    def build_display_menu(
        self, parent: tk.Misc, *, scope: str
    ) -> ttk.Menubutton:
        """Build a display menu scoped to the upper or lower figures."""

        if scope not in {"upper", "lower"}:
            raise ValueError(f"Portée d'affichage inconnue: {scope}")
        label = "Affichage haut" if scope == "upper" else "Affichage bas"
        button = ttk.Menubutton(parent, text=label)
        display_menu = tk.Menu(button, tearoff=False)

        def add_section(title: str) -> None:
            display_menu.add_command(label=title, state="disabled")

        def add_check(label: str, variable: tk.Variable) -> None:
            display_menu.add_checkbutton(
                label=label, variable=variable, command=self.on_display_changed
            )

        if scope == "lower":
            add_section("COURBES")
            for name, variable in self.app.show_vars.items():
                add_check(f"Courbe — {name}", variable)
            for name, variable in self.app.com_component_vars.items():
                add_check(f"Composante — {name}", variable)
            display_menu.add_separator()
            add_section("DÉCOMPOSITION DYNAMIQUE")
            for name, variable in self.app.torque_component_vars.items():
                add_check(name, variable)
            add_check("Courbes sur 3 axes", self.app.subplot_mode_var)
            add_check("Limites de couple", self.app.show_torque_bounds_var)
            display_menu.add_separator()
            add_section("PHASES")
            add_check("Limites des phases", self.app.show_phase_limits_var)
            add_check("Noms des phases", self.app.show_phase_names_var)
        else:
            add_section("ANIMATION ET REPÈRES")
            add_check(
                "Coordonnées articulaires (survol)",
                self.app.show_joint_coordinates_var,
            )
            add_check("Orientations segmentaires", self.app.show_segment_orientations_var)
            add_check("Angles articulaires", self.app.show_joint_angles_var)
            add_check("Informations sur les couples", self.app.show_animation_torques_var)
            add_check("Anthropométrie utilisée", self.app.show_anthropometry_var)
            add_check("Échantillons i−1 / i / i+1", self.app.show_neighbor_samples_var)
            add_check("Trajectoire de la barre", self.app.show_bar_trajectory_var)
            display_menu.add_separator()
            add_section("CoM ET APPUI")
            add_check("CoM global", self.app.show_global_com_var)
            add_check("Projection du CoM", self.app.show_com_projection_var)
            add_check("CoM segmentaires + barre", self.app.show_segment_com_var)
            add_check("Point d'appui (CoP ou ZMP)", self.app.show_cop_var)
            add_check("GRF", self.app.show_grf_var)
            add_check("Poids", self.app.show_weight_var)
            add_check("Base géométrique projetée", self.app.show_geometric_base_var)
            add_check("Zone fonctionnelle d'appui", self.app.show_support_limits_var)
            add_check("Bilan forces et équilibre", self.app.show_force_balance_var)
            display_menu.add_separator()
            add_section("ANNOTATIONS DYNAMIQUES")
            add_check("Bras de levier GRF", self.app.show_moment_arms_var)
            add_check("Anneaux demande/capacité", self.app.show_capacity_rings_var)
            add_check("Marqueurs articulaires", self.app.show_joint_markers_var)
            add_check("Centres des sprites", self.app.show_sprite_centers_var)
            add_check("Sprites basse qualité", self.app.low_quality_sprites_var)

        button.configure(menu=display_menu)
        if scope == "upper":
            self.app.display_menu_upper = display_menu
        else:
            self.app.display_menu_lower = display_menu
        return button

    def on_display_changed(self) -> None:
        """Refresh visual selections without recomputing scientific results."""

        self.app.update_plot_choices()

    def reveal_mode(self) -> RevealMode:
        variable = self.app.__dict__.get("reveal_mode_var")
        if variable is None:
            return RevealMode.FREE
        try:
            return RevealMode(variable.get())
        except ValueError:
            return RevealMode.FREE

    def set_reveal_mode(self, mode: RevealMode | str) -> None:
        target = RevealMode(mode)
        previous = getattr(self.app, "_last_reveal_mode", RevealMode.FREE)
        if previous is RevealMode.FREE and target is not RevealMode.FREE:
            self.app._plot_choice_before_reveal = self.app.plot_choice.get()
        self.app.reveal_mode_var.set(target.value)
        if target is RevealMode.KINEMATICS and previous is RevealMode.OBSERVATION:
            self.app.plot_choice.set(SYNCHRONIZED_KINEMATICS_CHOICE)
        elif target is RevealMode.KINEMATICS and self.app.plot_choice.get() not in (
            "cinematique articulaire",
            "centre de masse",
            SYNCHRONIZED_KINEMATICS_CHOICE,
        ):
            self.app.plot_choice.set(SYNCHRONIZED_KINEMATICS_CHOICE)
        elif target is RevealMode.DYNAMICS and previous in (
            RevealMode.OBSERVATION,
            RevealMode.KINEMATICS,
        ):
            self.app.plot_choice.set("force reaction sol")
        elif (
            target is RevealMode.FREE
            and self.app._plot_choice_before_reveal in PLOT_CHOICES
        ):
            self.app.plot_choice.set(self.app._plot_choice_before_reveal)
            self.app._plot_choice_before_reveal = None
        self.app._last_reveal_mode = target
        if hasattr(self.app, "plot_menu"):
            self.app.update_plot_choices()
            state = ["!disabled"] if target is RevealMode.FREE else ["disabled"]
            self.app.display_menu_upper_button.state(state)
            self.app.display_menu_lower_button.state(state)

    def on_reveal_mode_changed(self) -> None:
        self.set_reveal_mode(self.app.reveal_mode_var.get())

    def render_layers(self, *, refined_sprites: bool | None = None) -> RenderLayers:
        refined = (
            not self.app.low_quality_sprites_var.get()
            if refined_sprites is None
            else refined_sprites
        )
        mode = self.reveal_mode()
        if mode is not RevealMode.FREE:
            return layers_for_reveal(mode, refined_sprites=refined)
        return RenderLayers(
            global_com=self.app.show_global_com_var.get(),
            com_projection=self.app.show_com_projection_var.get(),
            segment_com=self.app.show_segment_com_var.get(),
            cop_zmp=self.app.show_cop_var.get(),
            grf=self.app.show_grf_var.get(),
            weight=self.app.show_weight_var.get(),
            geometric_base=self.app.show_geometric_base_var.get(),
            functional_base=self.app.show_support_limits_var.get(),
            force_balance=self.app.show_force_balance_var.get(),
            joint_coordinates=self.app.show_joint_coordinates_var.get(),
            segment_orientations=self.app.show_segment_orientations_var.get(),
            joint_angles=self.app.show_joint_angles_var.get(),
            anthropometry=self.app.show_anthropometry_var.get(),
            moment_arms=self.app.show_moment_arms_var.get(),
            capacity_rings=self.app.show_capacity_rings_var.get(),
            joint_markers=self.app.show_joint_markers_var.get(),
            refined_sprites=refined,
        )

    @staticmethod
    def configure_didactic_styles(style: ttk.Style) -> None:
        focus_styles = {
            "Sujet": ("#d9f0eb", "#16756d"),
            "Barre": ("#f7e7d5", "#b05e16"),
            "Charge": ("#dceff4", "#237f9f"),
            "Phase": ("#ebe7f6", "#6d5ea8"),
            "Pose": ("#e0f0e2", "#2e7d54"),
            "Results": ("#e6eff7", "#276c92"),
        }
        for name, (background, border) in focus_styles.items():
            style.configure(
                f"Guide{name}.TLabelframe",
                background=background,
                foreground=border,
                bordercolor=border,
                lightcolor=border,
                darkcolor=border,
            )
            style.configure(
                f"Guide{name}.TLabelframe.Label",
                background=background,
                foreground=border,
            )
        for name, (background, border) in focus_styles.items():
            style.configure(
                f"Guide{name}.TCombobox",
                fieldbackground=background,
                background=background,
                bordercolor=border,
                lightcolor=border,
                darkcolor=border,
                arrowcolor=border,
            )
            style.map(
                f"Guide{name}.TCombobox", fieldbackground=[("readonly", background)]
            )
        style.configure(
            "GuidePose.TButton",
            background="#e0f0e2",
            foreground="#2e7d54",
            bordercolor="#2e7d54",
            font=("Helvetica", 10, "bold"),
        )
        style.map("GuidePose.TButton", background=[("active", "#d1e8d5")])
        style.configure(
            "GuidePhase.Treeview",
            fieldbackground="#ebe7f6",
            background="#ebe7f6",
            bordercolor="#6d5ea8",
        )
        style.configure(
            "GuidePhase.Treeview.Heading",
            foreground="#6d5ea8",
            font=("Helvetica", 9, "bold"),
        )

    def update_left_scroll_region(self, _event: tk.Event | None = None) -> None:
        self.app.left_scroll_canvas.configure(
            scrollregion=self.app.left_scroll_canvas.bbox("all")
        )

    def resize_left_contents(self, event: tk.Event) -> None:
        required_height = self.app.left_panel.winfo_reqheight()
        self.app.left_scroll_canvas.itemconfigure(
            self.app.left_scroll_window,
            width=max(1, event.width),
            height=max(1, event.height, required_height),
        )
        self.update_left_scroll_region()

    def scroll_left_panel(self, event: tk.Event) -> str:
        delta = -1 if event.delta > 0 else 1
        self.app.left_scroll_canvas.yview_scroll(delta, "units")
        return "break"

    def resize_status_text(self, event: tk.Event) -> None:
        self.app.status_label.configure(wraplength=max(300, event.width - 20))

    def add_scale(
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
        box = ttk.LabelFrame(parent, text=label)
        box.grid(row=row, column=0, columnspan=columnspan, sticky="ew", padx=4, pady=2)
        box.columnconfigure(0, weight=1)
        scale = ttk.Scale(
            box,
            variable=var,
            from_=start,
            to=end,
            orient="horizontal",
            command=lambda _value: self.app.on_parameter_changed(),
        )
        scale.grid(row=0, column=0, sticky="ew", padx=4)
        value_label = ttk.Label(box, width=7)
        value_label.grid(row=0, column=1, padx=(4, 2))

        def sync_label(*_args: object) -> None:
            snapped = round((var.get() - start) / resolution) * resolution + start
            snapped = min(end, max(start, snapped))
            if abs(snapped - var.get()) > 1e-6:
                var.set(snapped)
            value_label.configure(text=f"{snapped:g}")

        var.trace_add("write", sync_label)
        sync_label()
        return box

    def sync_load_display(self, *_args: object) -> None:
        """Keep the readable popup value aligned with the numeric setting."""

        if hasattr(self.app, "load_display_var"):
            value = self.app.load_var.get()
            snapped = min(
                self.load_percent_options, key=lambda option: abs(option - value)
            )
            if abs(snapped - value) > 1e-6:
                self.app.load_var.set(float(snapped))
            self.app.load_display_var.set(f"{snapped:g} %BW")

    def on_load_menu_changed(self) -> None:
        """Apply a discrete popup selection without changing the data model."""

        text = self.app.load_display_var.get().split()[0]
        try:
            self.app.load_var.set(float(text))
        except (TypeError, ValueError):
            self.sync_load_display()
            return
        self.app.on_parameter_changed()

    def update_didactic_focus(self) -> None:
        if not hasattr(self.app, "profile_menu"):
            return
        self.app.profile_menu.configure(style="TCombobox")
        self.app.bar_menu.configure(style="TCombobox")
        self.app.temporal_preset_menu.configure(style="TCombobox")
        for frame in (
            self.app.parameter_box,
            self.app.charge_box,
            self.app.duration_box,
            self.app.lengths_box,
            self.app.torque_box,
            self.app.plot_box,
            self.app.table_box,
        ):
            frame.configure(style="TLabelframe")
        self.app.add_condition_button.configure(style="TButton")
        self.app.play_button.configure(style="TButton")
        self.app.conditions_table.configure(style="Treeview")
        self.app._didactic_canvas_colors.clear()
        self.app.plot_canvas.configure(
            highlightthickness=1, highlightbackground="#c9d1c7"
        )

        if self.app.didactic_mode_var.get():
            focus_targets = {
                "subject": (("widget", self.app.profile_menu, "GuideSujet.TCombobox"),),
                "bar": (("widget", self.app.bar_menu, "GuideBarre.TCombobox"),),
                "load": (("widget", self.app.charge_box, "GuideCharge.TLabelframe"),),
                "phase": (
                    ("widget", self.app.duration_box, "GuidePhase.TLabelframe"),
                    (
                        "widget",
                        self.app.temporal_preset_menu,
                        "GuidePhase.TCombobox",
                    ),
                ),
                "deep_pose": (("canvas", self.app.pose_canvas, "#2e7d54"),),
                "animation": (
                    ("canvas", self.app.animation_canvas, "#2e7d54"),
                    ("widget", self.app.play_button, "GuidePose.TButton"),
                ),
                "kinematics": (
                    ("widget", self.app.plot_box, "GuideResults.TLabelframe"),
                    ("widget", self.app.table_box, "GuideResults.TLabelframe"),
                    ("plot_canvas", self.app.plot_canvas, "#276c92"),
                ),
                "dynamics": (
                    ("canvas", self.app.animation_canvas, "#b05e16"),
                    ("widget", self.app.plot_box, "GuideResults.TLabelframe"),
                ),
                "add": (("widget", self.app.add_condition_button, "GuidePose.TButton"),),
                "duplicate": (
                    (
                        "widget",
                        self.app.duplicate_condition_button,
                        "GuidePose.TButton",
                    ),
                    ("widget", self.app.parameter_box, "GuideCharge.TLabelframe"),
                    ("widget", self.app.add_condition_button, "GuidePose.TButton"),
                ),
                "comparison": (
                    ("widget", self.app.table_box, "GuidePhase.TLabelframe"),
                    ("widget", self.app.conditions_table, "GuidePhase.Treeview"),
                    ("widget", self.app.differences_table, "GuidePhase.Treeview"),
                ),
            }
            for focus_key in didactic_focus_keys(self.app.didactic_step):
                for target_type, widget, style_or_color in focus_targets[focus_key]:
                    if target_type == "widget":
                        widget.configure(style=style_or_color)
                    elif target_type == "canvas":
                        self.app._didactic_canvas_colors[widget] = style_or_color
                    else:
                        widget.configure(
                            highlightthickness=4, highlightbackground=style_or_color
                        )
        if self.app.states:
            self.app.redraw()

    def update_didactic_guide(self) -> None:
        self.app.didactic_label.configure(state="normal")
        self.app.didactic_label.delete("1.0", "end")
        if self.app.didactic_mode_var.get():
            self.app.didactic_label.configure(bg="#e5f1e8", fg="#154a34")
            pieces = didactic_message(True, self.app.didactic_step)
        else:
            self.app.didactic_label.configure(bg="#f2f4f1", fg="#506158")
            pieces = didactic_message(False, self.app.didactic_step)
        for text, tag in pieces:
            self.app.didactic_label.insert("end", text, () if tag is None else (tag,))
        self.app.didactic_label.configure(state="disabled")
        self.update_didactic_focus()
        self.update_didactic_navigation()

    def draw_didactic_switch(self) -> None:
        enabled = self.app.didactic_mode_var.get()
        background = "#2e7d54" if enabled else "#bcc4bd"
        knob_x = 28 if enabled else 10
        switch = self.app.didactic_switch
        switch.delete("all")
        switch.create_oval(2, 2, 20, 18, fill=background, outline=background)
        switch.create_oval(18, 2, 36, 18, fill=background, outline=background)
        switch.create_rectangle(10, 2, 28, 18, fill=background, outline=background)
        switch.create_oval(
            knob_x - 7,
            4,
            knob_x + 7,
            16,
            fill="#ffffff",
            outline="#ffffff",
        )

    def update_didactic_navigation(self) -> None:
        self.draw_didactic_switch()
        state = DidacticPathState(
            self.app.didactic_mode_var.get(), self.app.didactic_step
        )
        self.app.reveal_mode_menu.state(
            ["disabled"] if state.active else ["!disabled", "readonly"]
        )
        self.app.didactic_previous_button.state(
            ["!disabled"] if state.can_go_back else ["disabled"]
        )
        self.app.didactic_next_button.state(
            ["!disabled"] if state.can_go_forward else ["disabled"]
        )

    def toggle_didactic_mode(self) -> None:
        current = DidacticPathState(
            self.app.didactic_mode_var.get(), self.app.didactic_step
        )
        updated = current.toggled()
        self.app.didactic_mode_var.set(updated.active)
        self.app.didactic_step = updated.step
        if updated.active:
            self.app._reveal_mode_before_didactic = self.app.reveal_mode_var.get()
            self.set_reveal_mode(updated.reveal_mode)
        else:
            self.set_reveal_mode(self.app._reveal_mode_before_didactic)
        self.update_didactic_guide()

    def advance_didactic_guide(self) -> None:
        updated = DidacticPathState(
            self.app.didactic_mode_var.get(), self.app.didactic_step
        ).advanced()
        self.app.didactic_mode_var.set(updated.active)
        self.app.didactic_step = updated.step
        self.set_reveal_mode(updated.reveal_mode)
        self.update_didactic_guide()

    def retreat_didactic_guide(self) -> None:
        current = DidacticPathState(
            self.app.didactic_mode_var.get(), self.app.didactic_step
        )
        if not current.active:
            return
        updated = current.retreated()
        self.app.didactic_step = updated.step
        self.set_reveal_mode(updated.reveal_mode)
        self.update_didactic_guide()

    def schedule_redraw(self, _event: tk.Event | None = None) -> None:
        if self.app._redraw_pending:
            return
        self.app._redraw_pending = True
        self.app.after(40, self.flush_scheduled_redraw)

    def flush_scheduled_redraw(self) -> None:
        self.app._redraw_pending = False
        self.redraw()

    def redraw(self) -> None:
        if not self.app.states:
            return
        if not self.app.canvases_ready():
            self.schedule_redraw()
            return
        frame = min(
            self.app.frame_count - 1, max(0, int(self.app.frame_var.get()))
        )
        info = frame_info(self.app.states, frame)
        if self.reveal_mode() is RevealMode.OBSERVATION:
            self.app.frame_info_var.set(
                "OBSERVATION · temps, phase et grandeurs masqués"
            )
        else:
            self.app.frame_info_var.set(
                f"Frame {info.frame}/{info.frame_count - 1}  ·  "
                f"t={info.time_s:.3f} s  ·  Δt={info.delta_time_s:.3f} s  ·  "
                f"{info.normalized_time_percent:.1f} %  ·  {info.phase}"
            )
        self.app.draw_pose_editor()
        self.app.draw_plot()
        self.app.draw_animation(frame)
