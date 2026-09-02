"""Tkinter GUI for the 2D squat model."""

from __future__ import annotations

import os
from time import perf_counter

os.environ.setdefault("LANG", "en_US.UTF-8")
os.environ.setdefault("LC_ALL", "en_US.UTF-8")

import json
import tkinter as tk
from copy import deepcopy
from math import atan2, degrees, isfinite, radians
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .anthropometry import (
    ANTHROPOMETRY_MODES,
    BAR_POSITIONS,
    SUBJECT_PROFILES,
    Anthropometry,
    scale_from_percent,
)
from .backend import BiorbdModelCache, detect_optional_backends
from .bar_path_optimization import (
    BarPathOptimizationResult,
    optimize_deep_squat_bar_path,
)
from .cli import Condition, condition_from_settings, simulate_condition, write_csv
from .comparison import difference_summary, parameter_differences
from .dynamics import (
    GRAVITY,
    DynamicsResult,
    force_balance,
    simulate,
    torque_presets,
)
from .didactics import (
    DYNAMIC_PHASE_DURATION_OPTIONS,
    ISOMETRIC_PHASE_DURATION_OPTIONS,
    TEMPORAL_PRESETS,
    TEMPORAL_PRESETS_BY_NAME,
    RevealMode,
    bounded_phase_durations,
    layers_for_reveal,
    reveal_mode_for_step,
    temporal_preset_display,
)
from .kinematics import (
    CLINICAL_JOINT_LIMITS_DEG,
    DEFAULT_SAMPLE_PERIOD_S,
    MotionState,
    PhaseDurations,
    clinical_joint_values_from_segment_values,
    functional_support_limits,
    frame_count_for_duration,
    geometric_support_limits,
    joint_angles_from_pose,
    joint_values_from_segment_values,
    pose_from_angles,
    segment_orientations,
    segment_values_from_clinical_joint_values,
)
from .observables import (
    com_contributions,
    frame_info,
    joint_coordinates,
    neighbor_samples,
    segment_anthropometry,
    support_margins,
)
from .export_schema import write_xlsx
from .raster_segments import draw_sprite_segment
from .rendering import RenderLayers
from .segment_shapes import draw_segment, load_segments
from .timeline import (
    TimeMode,
    nearest_time_index,
    phase_windows,
    time_axis_label,
    time_axis_unit,
)
from .video_export import export_mp4

DETAILED_PLOT_CHOICE = "couples detailles"
SYNCHRONIZED_KINEMATICS_CHOICE = "cinematique synchronisee"
TORQUE_COMPONENT_KEYS = {
    "M(q) qddot": "mass_acceleration",
    "termes qdot": "velocity",
    "gravité": "gravity",
    "contact externe (signé)": "external_contact",
    "total ID": "total",
}
PLOT_CHOICES = [
    "cinematique articulaire",
    "centre de masse",
    SYNCHRONIZED_KINEMATICS_CHOICE,
    "force reaction sol",
    "couples articulaires",
    "couples normalises",
    DETAILED_PLOT_CHOICE,
    "puissances articulaires",
]
# La charge est volontairement discrète dans le GUI : cinq niveaux couvrent
# l'absence de barre, une progression intermédiaire et la charge maximale.
# Le modèle accepte encore un flottant côté CLI pour les protocoles avancés.
LOAD_PERCENT_OPTIONS = (0.0, 25.0, 50.0, 75.0, 100.0)

JOINT_COLORS = {
    "cheville": "#2e7d54",
    "genou": "#b46d22",
    "hanche": "#6d5ea8",
    "horizontal": "#2a8ca6",
    "vertical": "#8a5a22",
}
FORCE_DRAW_SCALE = 3500.0 / 3.0
CANVAS_BG = "#fbfcf9"
ALERT_BG = "#ffe7e3"
OK_BORDER = "#587a5f"
ALERT_BORDER = "#c9332c"
POINT_LABELS = {
    "ankle": "cheville",
    "knee": "genou",
    "hip": "hanche",
    "shoulder": "épaule",
    "bar": "centre barre",
}
SEGMENT_LABELS = {
    "foot": "pied",
    "shank": "jambe",
    "thigh": "cuisse",
    "trunk": "tronc",
    "bar": "barre",
}


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
        self._active_pose_angle_joint: str | None = None
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
        self.saved_conditions: dict[str, dict[str, object]] = {}
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

        self._build_layout()
        self.recompute()

    def _build_display_menu(
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
            for name, variable in self.show_vars.items():
                add_check(f"Courbe — {name}", variable)
            for name, variable in self.com_component_vars.items():
                add_check(f"Composante — {name}", variable)
            display_menu.add_separator()
            add_section("DÉCOMPOSITION DYNAMIQUE")
            for name, variable in self.torque_component_vars.items():
                add_check(name, variable)
            add_check("Courbes sur 3 axes", self.subplot_mode_var)
            add_check("Limites de couple", self.show_torque_bounds_var)
            display_menu.add_separator()
            add_section("PHASES")
            add_check("Limites des phases", self.show_phase_limits_var)
            add_check("Noms des phases", self.show_phase_names_var)
        else:
            add_section("ANIMATION ET REPÈRES")
            add_check("Coordonnées articulaires (survol)", self.show_joint_coordinates_var)
            add_check("Orientations segmentaires", self.show_segment_orientations_var)
            add_check("Angles articulaires", self.show_joint_angles_var)
            add_check("Anthropométrie utilisée", self.show_anthropometry_var)
            add_check("Échantillons i−1 / i / i+1", self.show_neighbor_samples_var)
            add_check("Trajectoire de la barre", self.show_bar_trajectory_var)
            display_menu.add_separator()
            add_section("CoM ET APPUI")
            add_check("CoM global", self.show_global_com_var)
            add_check("Projection du CoM", self.show_com_projection_var)
            add_check("CoM segmentaires + barre", self.show_segment_com_var)
            add_check("Point d'appui (CoP ou ZMP)", self.show_cop_var)
            add_check("GRF", self.show_grf_var)
            add_check("Poids", self.show_weight_var)
            add_check("Base géométrique projetée", self.show_geometric_base_var)
            add_check("Zone fonctionnelle d'appui", self.show_support_limits_var)
            add_check("Bilan forces et équilibre", self.show_force_balance_var)
            display_menu.add_separator()
            add_section("ANNOTATIONS DYNAMIQUES")
            add_check("Bras de levier GRF", self.show_moment_arms_var)
            add_check("Anneaux demande/capacité", self.show_capacity_rings_var)
            add_check("Marqueurs articulaires", self.show_joint_markers_var)
            add_check("Centres des sprites", self.show_sprite_centers_var)
            add_check("Sprites basse qualité", self.low_quality_sprites_var)

        button.configure(menu=display_menu)
        if scope == "upper":
            self.display_menu_upper = display_menu
        else:
            self.display_menu_lower = display_menu
        return button

    def on_display_changed(self) -> None:
        """Refresh visual selections without recomputing scientific results."""
        self.update_plot_choices()

    def reveal_mode(self) -> RevealMode:
        variable = self.__dict__.get("reveal_mode_var")
        if variable is None:
            return RevealMode.FREE
        try:
            return RevealMode(variable.get())
        except ValueError:
            return RevealMode.FREE

    def set_reveal_mode(self, mode: RevealMode | str) -> None:
        target = RevealMode(mode)
        previous = getattr(self, "_last_reveal_mode", RevealMode.FREE)
        if previous is RevealMode.FREE and target is not RevealMode.FREE:
            self._plot_choice_before_reveal = self.plot_choice.get()
        self.reveal_mode_var.set(target.value)
        if target is RevealMode.KINEMATICS and previous is RevealMode.OBSERVATION:
            self.plot_choice.set(SYNCHRONIZED_KINEMATICS_CHOICE)
        elif target is RevealMode.KINEMATICS and self.plot_choice.get() not in (
            "cinematique articulaire",
            "centre de masse",
            SYNCHRONIZED_KINEMATICS_CHOICE,
        ):
            self.plot_choice.set(SYNCHRONIZED_KINEMATICS_CHOICE)
        elif target is RevealMode.DYNAMICS and previous in (
            RevealMode.OBSERVATION,
            RevealMode.KINEMATICS,
        ):
            self.plot_choice.set("force reaction sol")
        elif (
            target is RevealMode.FREE
            and self._plot_choice_before_reveal in PLOT_CHOICES
        ):
            self.plot_choice.set(self._plot_choice_before_reveal)
            self._plot_choice_before_reveal = None
        self._last_reveal_mode = target
        if hasattr(self, "plot_menu"):
            self.update_plot_choices()
            state = ["!disabled"] if target is RevealMode.FREE else ["disabled"]
            self.display_menu_upper_button.state(state)
            self.display_menu_lower_button.state(state)

    def on_reveal_mode_changed(self) -> None:
        self.set_reveal_mode(self.reveal_mode_var.get())

    def render_layers(self, *, refined_sprites: bool | None = None) -> RenderLayers:
        refined = (
            not self.low_quality_sprites_var.get()
            if refined_sprites is None
            else refined_sprites
        )
        mode = self.reveal_mode()
        if mode is not RevealMode.FREE:
            return layers_for_reveal(mode, refined_sprites=refined)
        return RenderLayers(
            global_com=self.show_global_com_var.get(),
            com_projection=self.show_com_projection_var.get(),
            segment_com=self.show_segment_com_var.get(),
            cop_zmp=self.show_cop_var.get(),
            grf=self.show_grf_var.get(),
            weight=self.show_weight_var.get(),
            geometric_base=self.show_geometric_base_var.get(),
            functional_base=self.show_support_limits_var.get(),
            force_balance=self.show_force_balance_var.get(),
            joint_coordinates=self.show_joint_coordinates_var.get(),
            segment_orientations=self.show_segment_orientations_var.get(),
            joint_angles=self.show_joint_angles_var.get(),
            anthropometry=self.show_anthropometry_var.get(),
            moment_arms=self.show_moment_arms_var.get(),
            capacity_rings=self.show_capacity_rings_var.get(),
            joint_markers=self.show_joint_markers_var.get(),
            refined_sprites=refined,
        )

    @staticmethod
    def _configure_didactic_styles(style: ttk.Style) -> None:
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

    def _build_layout(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f2f4f1")
        style.configure("TLabelframe", background="#f2f4f1")
        style.configure("TLabel", background="#f2f4f1", foreground="#22312a")
        style.configure("TCheckbutton", background="#f2f4f1")
        style.configure("TButton", padding=6)
        style.configure("Invalid.TSpinbox", fieldbackground="#ffe3df")
        style.configure(
            "GuideNav.TButton", padding=(3, 2), font=("Helvetica", 11, "bold")
        )
        self._configure_didactic_styles(style)

        root = ttk.Frame(self, padding=10)
        self.root_layout = root
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=0, minsize=360)
        # Le poseur sert a regler une seule posture, alors que le panneau droit
        # affiche toute l'animation.  Garder une largeur minimale au poseur
        # preserve le glisser-deposer, puis donner deux fois plus de largeur a
        # l'animation libere un espace appreciable sans masquer les controles
        # dans les petites fenetres.
        root.columnconfigure(1, weight=1, minsize=260)
        root.columnconfigure(2, weight=2, minsize=280)
        root.rowconfigure(0, weight=1, minsize=420)
        root.rowconfigure(2, weight=3, minsize=250)

        self.left_scroll_host = ttk.Frame(root)
        self.left_scroll_host.grid(
            row=0, column=0, rowspan=3, sticky="nsew", padx=(0, 8)
        )
        self.left_scroll_host.rowconfigure(0, weight=1)
        self.left_scroll_host.columnconfigure(0, weight=1)
        self.left_scroll_canvas = tk.Canvas(
            self.left_scroll_host,
            width=420,
            bg="#f2f4f1",
            highlightthickness=0,
        )
        self.left_scroll_canvas.grid(row=0, column=0, sticky="nsew")
        self.left_scrollbar = ttk.Scrollbar(
            self.left_scroll_host,
            orient="vertical",
            command=self.left_scroll_canvas.yview,
        )
        self.left_scrollbar.grid(row=0, column=1, sticky="ns")
        self.left_scroll_canvas.configure(yscrollcommand=self.left_scrollbar.set)

        left = ttk.Frame(self.left_scroll_canvas)
        self.left_panel = left
        self.left_scroll_window = self.left_scroll_canvas.create_window(
            0, 0, anchor="nw", window=left
        )
        left.bind("<Configure>", self._update_left_scroll_region)
        self.left_scroll_canvas.bind("<Configure>", self._resize_left_contents)
        self.left_scroll_canvas.bind("<MouseWheel>", self._scroll_left_panel)
        left.columnconfigure(0, weight=1)
        guide_box = ttk.LabelFrame(left, text="Parcours didactique")
        guide_box.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        guide_box.columnconfigure(1, weight=1)
        self.didactic_switch = tk.Canvas(
            guide_box,
            width=38,
            height=20,
            bg="#f2f4f1",
            highlightthickness=0,
            cursor="hand2",
        )
        self.didactic_switch.grid(row=0, column=0, sticky="w", padx=(6, 4), pady=4)
        self.didactic_switch.bind(
            "<Button-1>", lambda _event: self.toggle_didactic_mode()
        )
        self.didactic_label = tk.Text(
            guide_box,
            height=1,
            width=34,
            wrap="none",
            relief="flat",
            borderwidth=0,
            bg="#f2f4f1",
            fg="#22312a",
            font=("Helvetica", 9),
            padx=4,
            pady=4,
        )
        self.didactic_label.grid(row=0, column=1, sticky="ew", padx=2)
        self.didactic_label.tag_configure(
            "sujet", foreground="#16756d", font=("Helvetica", 9, "bold")
        )
        self.didactic_label.tag_configure(
            "barre", foreground="#b05e16", font=("Helvetica", 9, "bold")
        )
        self.didactic_label.tag_configure(
            "charge", foreground="#237f9f", font=("Helvetica", 9, "bold")
        )
        self.didactic_label.tag_configure(
            "phase", foreground="#6d5ea8", font=("Helvetica", 9, "bold")
        )
        self.didactic_label.tag_configure(
            "pose", foreground="#2e7d54", font=("Helvetica", 9, "bold")
        )
        self.didactic_label.tag_configure(
            "alerte", foreground="#c9332c", font=("Helvetica", 9, "bold")
        )
        self.didactic_previous_button = ttk.Button(
            guide_box,
            text="\u25c0",
            command=self.retreat_didactic_guide,
            width=2,
            style="GuideNav.TButton",
        )
        self.didactic_previous_button.grid(row=0, column=2, padx=(3, 1), pady=3)
        self.didactic_next_button = ttk.Button(
            guide_box,
            text="\u25b6",
            command=self.advance_didactic_guide,
            width=2,
            style="GuideNav.TButton",
        )
        self.didactic_next_button.grid(row=0, column=3, padx=(1, 4), pady=3)
        self.parameter_box = ttk.LabelFrame(left, text="Parametres")
        self.parameter_box.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.parameter_box.columnconfigure(0, weight=1)
        self.parameter_box.columnconfigure(1, weight=1)
        self.identity_box = ttk.Frame(self.parameter_box)
        self.identity_box.grid(
            row=0, column=0, sticky="nsew", padx=(4, 2), pady=3
        )
        for column in range(2):
            self.identity_box.columnconfigure(column, weight=1)
        ttk.Label(self.identity_box, text="Sujet").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(self.identity_box, text="Prise barre").grid(
            row=0, column=1, sticky="w"
        )
        self.profile_menu = ttk.Combobox(
            self.identity_box,
            textvariable=self.subject_profile_var,
            values=SUBJECT_PROFILES,
            state="readonly",
            width=9,
        )
        self.profile_menu.grid(row=1, column=0, sticky="ew", padx=(0, 3))
        self.profile_menu.bind(
            "<<ComboboxSelected>>", lambda _event: self.on_parameter_changed()
        )
        self.bar_menu = ttk.Combobox(
            self.identity_box,
            textvariable=self.bar_position_var,
            values=BAR_POSITIONS,
            state="readonly",
            width=9,
        )
        self.bar_menu.grid(row=1, column=1, sticky="ew", padx=(3, 0))
        self.bar_menu.bind(
            "<<ComboboxSelected>>", lambda _event: self.on_parameter_changed()
        )
        self.charge_box = ttk.LabelFrame(
            self.parameter_box, text="Charge %BW (sujet 70 kg)"
        )
        self.charge_box.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(2, 4),
            pady=3,
        )
        self.charge_box.columnconfigure(0, weight=1)
        self.load_menu = ttk.Combobox(
            self.charge_box,
            textvariable=self.load_display_var,
            values=tuple(f"{value:g} %BW" for value in LOAD_PERCENT_OPTIONS),
            state="readonly",
            width=10,
        )
        self.load_menu.grid(row=0, column=0, sticky="ew", padx=4, pady=3)
        self.load_menu.bind(
            "<<ComboboxSelected>>", lambda _event: self.on_load_menu_changed()
        )
        self.duration_box = ttk.LabelFrame(
            self.parameter_box, text="Durée des phases (s)"
        )
        self.duration_box.grid(
            row=1, column=0, sticky="nsew", padx=(4, 2), pady=3
        )
        for column, (label, variable, values) in enumerate(
            (
                (
                    "excent.",
                    self.eccentric_duration_var,
                    DYNAMIC_PHASE_DURATION_OPTIONS,
                ),
                (
                    "isomet.",
                    self.isometric_duration_var,
                    ISOMETRIC_PHASE_DURATION_OPTIONS,
                ),
                (
                    "concent.",
                    self.concentric_duration_var,
                    DYNAMIC_PHASE_DURATION_OPTIONS,
                ),
            )
        ):
            self.duration_box.columnconfigure(column, weight=1)
            ttk.Label(self.duration_box, text=label).grid(row=0, column=column)
            duration = ttk.Combobox(
                self.duration_box,
                textvariable=variable,
                values=values,
                state="readonly",
                width=4,
            )
            duration.grid(row=1, column=column, sticky="ew", padx=2, pady=(0, 3))
            duration.bind(
                "<<ComboboxSelected>>", lambda _event: self.on_duration_changed()
            )
        self.temporal_preset_label = ttk.Label(
            self.duration_box,
            text="Preset temporel (Descente | Iso | Montée)",
        )
        self.temporal_preset_label.grid(
            row=2, column=0, columnspan=3, sticky="w", padx=2
        )
        self.temporal_preset_menu = ttk.Combobox(
            self.duration_box,
            textvariable=self.temporal_preset_display_var,
            values=(
                "",
                *(temporal_preset_display(preset) for preset in TEMPORAL_PRESETS),
            ),
            state="readonly",
            width=30,
        )
        self.temporal_preset_menu.grid(
            row=3,
            column=0,
            columnspan=3,
            sticky="ew",
            padx=2,
            pady=(0, 3),
        )
        self.temporal_preset_menu.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.apply_temporal_preset(),
        )
        self.lengths_box = ttk.LabelFrame(self.parameter_box, text="Longueurs (%)")
        self.lengths_box.grid(
            row=1, column=1, sticky="nsew", padx=(2, 4), pady=3
        )
        for column, (label, variable) in enumerate(
            (
                ("tibia", self.shank_var),
                ("cuisse", self.thigh_var),
                ("tronc", self.trunk_var),
            )
        ):
            self.lengths_box.columnconfigure(column, weight=1)
            ttk.Label(self.lengths_box, text=label).grid(row=0, column=column)
            length_menu = ttk.Combobox(
                self.lengths_box,
                textvariable=variable,
                values=(-5.0, -2.5, 0.0, 2.5, 5.0),
                state="readonly",
                width=4,
            )
            length_menu.grid(row=1, column=column, sticky="ew", padx=2, pady=(0, 3))
            length_menu.bind(
                "<<ComboboxSelected>>", lambda _event: self.on_parameter_changed()
            )
        self.anthropometry_mode_label = ttk.Label(self.lengths_box, text="mode")
        self.anthropometry_mode_label.grid(
            row=2, column=0, columnspan=3, sticky="w", padx=2
        )
        self.anthropometry_mode_menu = ttk.Combobox(
            self.lengths_box,
            textvariable=self.anthropometry_mode_var,
            values=ANTHROPOMETRY_MODES,
            state="readonly",
            width=22,
        )
        self.anthropometry_mode_menu.grid(
            row=3, column=0, columnspan=3, sticky="ew", padx=2, pady=(0, 3)
        )
        self.anthropometry_mode_menu.bind(
            "<<ComboboxSelected>>", lambda _event: self.on_parameter_changed()
        )
        self.parameter_options = ttk.Frame(self.parameter_box)
        self.parameter_options.grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(3, 4)
        )
        ttk.Checkbutton(
            self.parameter_options,
            text="wedge 20 deg",
            variable=self.wedge_var,
            command=self.on_parameter_changed,
        ).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(
            self.parameter_options,
            text="CoM segments + barre",
            variable=self.show_segment_com_var,
            command=self.redraw,
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.torque_box = ttk.LabelFrame(left, text="Couples max")
        self.torque_box.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        for col in range(4):
            self.torque_box.columnconfigure(col, weight=1)
        self.torque_box.columnconfigure(0, weight=0)
        self.torque_preset_menu = ttk.OptionMenu(
            self.torque_box,
            self.torque_preset_var,
            self.torque_preset_var.get(),
            *torque_presets(70.0, 1.70),
            command=lambda _value: self.apply_torque_preset(),
        )
        self.torque_preset_menu.grid(
            row=0, column=0, rowspan=2, sticky="nsew", padx=4, pady=(3, 0)
        )
        for col, joint in enumerate(("cheville", "genou", "hanche")):
            ttk.Label(self.torque_box, text=joint).grid(row=0, column=col + 1, padx=4)
            entry = ttk.Entry(
                self.torque_box, textvariable=self.max_torque_vars[joint], width=7
            )
            entry.grid(row=1, column=col + 1, sticky="ew", padx=4)
            entry.bind("<FocusOut>", lambda _event: self.on_parameter_changed())
            entry.bind("<Return>", lambda _event: self.on_parameter_changed())
        torque_checks = ttk.Frame(self.torque_box)
        torque_checks.grid(
            row=2, column=0, columnspan=4, sticky="ew", padx=4, pady=(4, 0)
        )
        for col in range(3):
            torque_checks.columnconfigure(col, weight=1)
        ttk.Checkbutton(
            torque_checks,
            text="max-angle (Anderson)",
            variable=self.angle_adapt_var,
            command=self.on_parameter_changed,
        ).grid(row=0, column=0, sticky="w", padx=(0, 4))
        ttk.Checkbutton(
            torque_checks,
            text="max-vitesse (Anderson)",
            variable=self.velocity_adapt_var,
            command=self.on_parameter_changed,
        ).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Checkbutton(
            torque_checks,
            text="afficher les limites",
            variable=self.show_torque_bounds_var,
            command=self.redraw,
        ).grid(row=0, column=2, sticky="w", padx=(4, 0))

        # Les controles de resultat occupent la ligne dediee a l'en-tete des
        # courbes. Ils ne doivent pas etre enfermes dans le panneau vertical
        # des parametres, dont la hauteur est contrainte par la fenetre.
        self.plot_box = ttk.LabelFrame(left, text="Resultats")
        self.plot_box.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        for col in range(4):
            self.plot_box.columnconfigure(col, weight=1)
        self.plot_menu = ttk.Combobox(
            self.plot_box,
            textvariable=self.plot_choice,
            values=PLOT_CHOICES,
            state="readonly",
        )
        self.plot_menu.grid(
            row=0, column=0, columnspan=4, sticky="ew", padx=4, pady=(2, 4)
        )
        self.plot_menu.bind(
            "<<ComboboxSelected>>", lambda _event: self.on_plot_choice_changed()
        )
        for index, name in enumerate(self.show_vars):
            checkbutton = ttk.Checkbutton(
                self.plot_box,
                text=name,
                variable=self.show_vars[name],
                command=self.redraw,
            )
            checkbutton.grid(row=1, column=index, sticky="w", padx=4)
            self.show_checkbuttons[name] = checkbutton
        self.quantity_menu = ttk.OptionMenu(
            self.plot_box,
            self.quantity_var,
            self.quantity_var.get(),
            "position",
            "vitesse",
            "acceleration",
            command=lambda _value: self.redraw(),
        )
        self.quantity_menu.grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(6, 2)
        )
        self.quantity_controls.append(self.quantity_menu)
        self.synchronized_source_menu = ttk.OptionMenu(
            self.plot_box,
            self.synchronized_source_var,
            self.synchronized_source_var.get(),
            "angles articulaires",
            "centre de masse",
            command=lambda _value: self.on_plot_choice_changed(),
        )
        self.synchronized_source_menu.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=(6, 2),
        )
        self.synchronized_source_menu.grid_remove()
        for index, name in enumerate(self.com_component_vars):
            checkbutton = ttk.Checkbutton(
                self.plot_box,
                text=name,
                variable=self.com_component_vars[name],
                command=self.redraw,
            )
            checkbutton.grid(row=2, column=index + 2, sticky="w", padx=4, pady=(6, 2))
            self.com_controls.append(checkbutton)
        for control in self.com_controls:
            control.state(["disabled"])
        self.phase_menu_button = ttk.Menubutton(self.plot_box, text="Phases")
        phase_menu = tk.Menu(self.phase_menu_button, tearoff=False)
        phase_menu.add_checkbutton(
            label="Afficher les limites",
            variable=self.show_phase_limits_var,
            command=self.redraw,
        )
        phase_menu.add_checkbutton(
            label="Afficher les noms",
            variable=self.show_phase_names_var,
            command=self.redraw,
        )
        self.phase_menu_button.configure(menu=phase_menu)
        self.phase_menu_button.grid(row=1, column=3, sticky="ew", padx=4)
        self.table_box = ttk.LabelFrame(
            left, text="Conditions enregistrees", width=420, height=250
        )
        self.table_box.grid(row=4, column=0, sticky="nsew")
        self.table_box.grid_propagate(False)
        self.table_box.rowconfigure(1, weight=1)
        self.table_box.columnconfigure(0, weight=1)
        self.table_buttons = ttk.Frame(self.table_box)
        self.table_buttons.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        self.table_buttons.columnconfigure(0, weight=1)
        self.table_buttons.columnconfigure(1, weight=1)
        self.table_buttons.columnconfigure(2, weight=1)
        self.add_condition_button = ttk.Button(
            self.table_buttons, text="Ajouter", command=self.record_condition
        )
        self.add_condition_button.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self.duplicate_condition_button = ttk.Button(
            self.table_buttons,
            text="Dupliquer",
            command=self.duplicate_selected_condition,
        )
        self.duplicate_condition_button.grid(row=0, column=1, sticky="ew", padx=3)
        self.duplicate_condition_button.state(["disabled"])
        self.delete_condition_button = ttk.Button(
            self.table_buttons,
            text="Supprimer",
            command=self.delete_selected_conditions,
        )
        self.delete_condition_button.grid(row=0, column=2, sticky="ew", padx=(3, 0))
        self.delete_condition_button.state(["disabled"])
        columns = (
            "numero",
            "profil",
            "prise",
            "squat",
            "charge",
            "phases",
            "wedge",
            "tibia",
            "cuisse",
            "tronc",
            "cheville",
            "genou",
            "hanche",
            "u_max",
            "limitant",
            "modifications",
        )
        self.table_notebook = ttk.Notebook(self.table_box)
        self.table_notebook.grid(row=1, column=0, sticky="nsew", padx=4, pady=(4, 0))
        self.conditions_tab = ttk.Frame(self.table_notebook)
        self.cursor_tab = ttk.Frame(self.table_notebook)
        self.differences_tab = ttk.Frame(self.table_notebook)
        self.table_notebook.add(self.conditions_tab, text="Conditions")
        self.table_notebook.add(self.cursor_tab, text="Valeurs au curseur")
        self.table_notebook.add(self.differences_tab, text="Variables contrôlées")
        self.conditions_tab.rowconfigure(0, weight=1)
        self.conditions_tab.columnconfigure(0, weight=1)
        self.cursor_tab.rowconfigure(0, weight=1)
        self.cursor_tab.columnconfigure(0, weight=1)
        self.differences_tab.rowconfigure(0, weight=1)
        self.differences_tab.columnconfigure(0, weight=1)
        self.conditions_table = ttk.Treeview(
            self.conditions_tab,
            columns=columns,
            show="headings",
            height=7,
            selectmode="extended",
        )
        headings = {
            "numero": "#",
            "profil": "sujet",
            "prise": "barre",
            "squat": "squat deg",
            "charge": "%BW",
            "phases": "ecc/iso/con s",
            "wedge": "wedge",
            "tibia": "tibia %",
            "cuisse": "cuisse %",
            "tronc": "tronc %",
            "cheville": "pic chev Nm",
            "genou": "pic gen Nm",
            "hanche": "pic han Nm",
            "u_max": "U max",
            "limitant": "limitant · temps · phase · U>1",
            "modifications": "modifications contrôlées",
        }
        widths = {
            "numero": 34,
            "profil": 80,
            "prise": 64,
            "squat": 78,
            "charge": 48,
            "phases": 90,
            "wedge": 46,
            "tibia": 56,
            "cuisse": 60,
            "tronc": 56,
            "cheville": 76,
            "genou": 74,
            "hanche": 74,
            "u_max": 58,
            "limitant": 190,
            "modifications": 190,
        }
        for column in columns:
            self.conditions_table.heading(column, text=headings[column])
            self.conditions_table.column(
                column, width=widths[column], anchor="center", stretch=True
            )
        self.conditions_table.grid(row=0, column=0, sticky="nsew")
        table_scroll = ttk.Scrollbar(
            self.conditions_tab,
            orient="horizontal",
            command=self.conditions_table.xview,
        )
        table_scroll.grid(row=1, column=0, sticky="ew")
        self.conditions_table.configure(xscrollcommand=table_scroll.set)
        self.conditions_table.bind(
            "<<TreeviewSelect>>", self.on_table_selection_changed
        )
        self.conditions_table.bind("<Button-1>", self.on_table_click)
        cursor_columns = ("condition", "variable", "value", "unit", "time", "phase")
        self.cursor_table = ttk.Treeview(
            self.cursor_tab,
            columns=cursor_columns,
            show="headings",
            height=7,
        )
        cursor_headings = {
            "condition": "condition",
            "variable": "courbe visible",
            "value": "valeur",
            "unit": "unité",
            "time": "t courbe",
            "phase": "phase",
        }
        cursor_widths = {
            "condition": 70,
            "variable": 155,
            "value": 78,
            "unit": 58,
            "time": 72,
            "phase": 82,
        }
        for column in cursor_columns:
            self.cursor_table.heading(column, text=cursor_headings[column])
            self.cursor_table.column(
                column,
                width=cursor_widths[column],
                anchor="center",
                stretch=True,
            )
        self.cursor_table.grid(row=0, column=0, sticky="nsew")
        cursor_scroll = ttk.Scrollbar(
            self.cursor_tab,
            orient="vertical",
            command=self.cursor_table.yview,
        )
        cursor_scroll.grid(row=0, column=1, sticky="ns")
        cursor_xscroll = ttk.Scrollbar(
            self.cursor_tab,
            orient="horizontal",
            command=self.cursor_table.xview,
        )
        cursor_xscroll.grid(row=1, column=0, sticky="ew")
        self.cursor_table.configure(
            yscrollcommand=cursor_scroll.set,
            xscrollcommand=cursor_xscroll.set,
        )
        difference_columns = ("variable", "reference", "compared")
        self.differences_table = ttk.Treeview(
            self.differences_tab,
            columns=difference_columns,
            show="headings",
            height=7,
        )
        for column, heading, width in (
            ("variable", "paramètre modifié", 180),
            ("reference", "référence", 105),
            ("compared", "comparée", 105),
        ):
            self.differences_table.heading(column, text=heading)
            self.differences_table.column(
                column, width=width, anchor="center", stretch=True
            )
        self.differences_table.grid(row=0, column=0, sticky="nsew")
        difference_scroll = ttk.Scrollbar(
            self.differences_tab,
            orient="vertical",
            command=self.differences_table.yview,
        )
        difference_scroll.grid(row=0, column=1, sticky="ns")
        self.differences_table.configure(yscrollcommand=difference_scroll.set)
        self.file_box = ttk.Frame(self.table_box)
        self.file_box.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 4))
        for col in range(4):
            self.file_box.columnconfigure(col, weight=1)
        self.save_conditions_button = ttk.Button(
            self.file_box, text="💾 Sauver", command=self.save_json
        )
        self.save_conditions_button.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self.load_conditions_button = ttk.Button(
            self.file_box, text="📂 Charger", command=self.load_json
        )
        self.load_conditions_button.grid(row=0, column=1, sticky="ew", padx=3)
        self.export_excel_button = ttk.Button(
            self.file_box, text="▦ Excel", command=self.export_excel
        )
        self.export_excel_button.grid(row=0, column=2, sticky="ew", padx=3)
        self.export_mp4_button = ttk.Button(
            self.file_box, text="▶ MP4", command=self.export_video
        )
        self.export_mp4_button.grid(row=0, column=3, sticky="ew", padx=(3, 0))
        self.export_csv_button = ttk.Button(
            self.file_box,
            text="⇩ CSV combiné",
            command=self.export_csv_results,
        )
        self.export_csv_button.grid(
            row=1, column=0, columnspan=4, sticky="ew", pady=(4, 0)
        )
        self.table_notebook.bind("<<NotebookTabChanged>>", self.on_table_tab_changed)

        self.pose_panel = ttk.Frame(root)
        self.pose_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        self.pose_panel.rowconfigure(0, weight=1)
        self.pose_panel.columnconfigure(0, weight=1)
        self.pose_canvas = tk.Canvas(
            self.pose_panel,
            bg=CANVAS_BG,
            highlightthickness=2,
            highlightbackground="#7f8f83",
        )
        self.pose_canvas.grid(row=0, column=0, sticky="nsew")
        self.pose_canvas.bind("<Configure>", self.schedule_redraw)
        self.pose_canvas.bind("<ButtonPress-1>", self.on_pose_press)
        self.pose_canvas.bind("<B1-Motion>", self.on_pose_drag)
        self.pose_canvas.bind("<ButtonRelease-1>", self.on_pose_release)
        self.pose_canvas.bind("<ButtonPress-3>", self.on_pose_context_menu)
        self.optimize_bar_path_toggle = ttk.Checkbutton(
            self.pose_canvas,
            text="Stabiliser barre (expérimental)",
            variable=self.optimize_bar_path_var,
            command=self.on_parameter_changed,
        )
        self.optimize_bar_path_toggle.place(
            relx=1.0, rely=1.0, x=-10, y=-10, anchor="se"
        )

        self.pose_angle_dialog = tk.Toplevel(self)
        self.pose_angle_dialog.withdraw()
        self.pose_angle_dialog.transient(self)
        self.pose_angle_dialog.resizable(False, False)
        self.pose_angle_dialog.protocol("WM_DELETE_WINDOW", self.close_pose_angle_editor)
        self.pose_angle_editor = ttk.LabelFrame(
            self.pose_angle_dialog, text="Angle articulaire", padding=(8, 5)
        )
        self.pose_angle_editor.grid(row=0, column=0, sticky="nsew")
        self.pose_angle_editor.columnconfigure(1, weight=1)
        self.pose_angle_joint_var = tk.StringVar(value="")
        self.pose_angle_value_var = tk.StringVar(value="")
        self.pose_angle_feedback_var = tk.StringVar(value="")
        self.pose_angle_joint_label = ttk.Label(
            self.pose_angle_editor,
            textvariable=self.pose_angle_joint_var,
            font=("Helvetica", 10, "bold"),
        )
        self.pose_angle_joint_label.grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(self.pose_angle_editor, text="Valeur précise (deg) :").grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )
        self.pose_angle_entry = ttk.Entry(
            self.pose_angle_editor,
            textvariable=self.pose_angle_value_var,
            width=12,
            justify="right",
        )
        self.pose_angle_entry.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(4, 0))
        self.pose_angle_entry.bind("<Return>", self.confirm_pose_angle_editor)
        self.pose_angle_entry.bind("<KP_Enter>", self.confirm_pose_angle_editor)
        self.pose_angle_entry.bind(
            "<Escape>", lambda _event: self.close_pose_angle_editor()
        )
        self.pose_angle_cancel_button = ttk.Button(
            self.pose_angle_editor, text="Annuler", command=self.close_pose_angle_editor
        )
        self.pose_angle_cancel_button.grid(row=1, column=2, padx=(6, 0), pady=(4, 0))
        self.pose_angle_apply_button = ttk.Button(
            self.pose_angle_editor, text="Valider", command=self.confirm_pose_angle_editor
        )
        self.pose_angle_apply_button.grid(row=1, column=3, padx=(6, 0), pady=(4, 0))
        self.pose_angle_feedback_label = ttk.Label(
            self.pose_angle_editor,
            textvariable=self.pose_angle_feedback_var,
            foreground=ALERT_BORDER,
        )
        self.pose_angle_feedback_label.grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(3, 0)
        )
        self.pose_angle_dialog.bind("<Return>", self.confirm_pose_angle_editor)
        self.pose_angle_dialog.bind("<KP_Enter>", self.confirm_pose_angle_editor)
        self.pose_angle_dialog.bind(
            "<Escape>", lambda _event: self.close_pose_angle_editor()
        )

        right = ttk.Frame(root)
        self.animation_panel = right
        right.grid(row=0, column=2, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.animation_canvas = tk.Canvas(
            right, bg=CANVAS_BG, highlightthickness=2, highlightbackground="#c9d1c7"
        )
        self.animation_canvas.grid(row=0, column=0, sticky="nsew")
        self.animation_canvas.bind("<Configure>", self.schedule_redraw)
        self.animation_canvas.bind("<Motion>", self.on_animation_motion)
        self.animation_canvas.bind("<Leave>", self.clear_animation_tooltip)
        self.display_menu_upper_button = self._build_display_menu(
            right, scope="upper"
        )
        self.display_menu_upper_button.place(relx=1.0, x=-8, y=8, anchor="ne")

        playback = ttk.Frame(root)
        self.playback_panel = playback
        playback.grid(
            row=1, column=1, columnspan=2, sticky="ew", pady=(2, 0)
        )
        playback.columnconfigure(2, weight=1)
        self.reveal_mode_menu = ttk.Combobox(
            playback,
            textvariable=self.reveal_mode_var,
            values=[mode.value for mode in RevealMode],
            state="readonly",
            width=13,
        )
        self.reveal_mode_menu.grid(row=0, column=0, padx=(0, 8))
        self.reveal_mode_menu.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.on_reveal_mode_changed(),
        )
        self.play_button = ttk.Button(
            playback, text="▶", command=self.toggle_play, width=4
        )
        self.play_button.grid(row=0, column=1, padx=(0, 8))
        self.frame_scale = ttk.Scale(
            playback,
            variable=self.frame_var,
            from_=0,
            to=self.frame_count - 1,
            orient="horizontal",
            command=lambda _value: self.redraw(),
        )
        self.frame_scale.grid(row=0, column=2, sticky="ew")
        self.time_mode_menu = ttk.Combobox(
            playback,
            textvariable=self.time_mode_var,
            values=[mode.value for mode in TimeMode],
            state="readonly",
            width=10,
        )
        self.time_mode_menu.grid(row=0, column=3, padx=(8, 0))
        self.time_mode_menu.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.on_time_mode_changed(),
        )
        plot_panel = ttk.Frame(root)
        self.plot_panel = plot_panel
        plot_panel.grid(row=2, column=1, columnspan=2, sticky="nsew", pady=(2, 0))
        plot_panel.rowconfigure(0, weight=1)
        plot_panel.columnconfigure(0, weight=1)
        self.plot_canvas = tk.Canvas(
            plot_panel,
            bg="#ffffff",
            highlightthickness=1,
            highlightbackground="#c9d1c7",
        )
        self.plot_canvas.grid(row=0, column=0, sticky="nsew")
        self.plot_canvas.bind("<Configure>", self.schedule_redraw)
        self.plot_canvas.bind("<Button-1>", self.on_plot_cursor_event)
        self.plot_canvas.bind("<B1-Motion>", self.on_plot_cursor_event)
        self.display_menu_lower_button = self._build_display_menu(
            plot_panel, scope="lower"
        )
        self.display_menu_lower_button.place(relx=1.0, x=-8, y=8, anchor="ne")

        self.status_label = ttk.Label(
            root,
            textvariable=self.status_var,
            justify="left",
            anchor="w",
        )
        self.status_label.grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=(8, 0)
        )
        root.bind("<Configure>", self._resize_status_text)
        self.update_didactic_guide()

    def _update_left_scroll_region(self, _event: tk.Event | None = None) -> None:
        self.left_scroll_canvas.configure(
            scrollregion=self.left_scroll_canvas.bbox("all")
        )

    def _resize_left_contents(self, event: tk.Event) -> None:
        self.left_scroll_canvas.itemconfigure(
            self.left_scroll_window, width=max(1, event.width)
        )
        self._update_left_scroll_region()

    def _scroll_left_panel(self, event: tk.Event) -> str:
        delta = -1 if event.delta > 0 else 1
        self.left_scroll_canvas.yview_scroll(delta, "units")
        return "break"

    def _resize_status_text(self, event: tk.Event) -> None:
        self.status_label.configure(wraplength=max(300, event.width - 20))

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
        box = ttk.LabelFrame(parent, text=label)
        box.grid(row=row, column=0, columnspan=columnspan, sticky="ew", padx=4, pady=2)
        box.columnconfigure(0, weight=1)
        scale = ttk.Scale(
            box,
            variable=var,
            from_=start,
            to=end,
            orient="horizontal",
            command=lambda _value: self.on_parameter_changed(),
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

    def _sync_load_display(self, *_args: object) -> None:
        """Keep the readable popup value aligned with the numeric setting."""
        if hasattr(self, "load_display_var"):
            value = self.load_var.get()
            snapped = min(LOAD_PERCENT_OPTIONS, key=lambda option: abs(option - value))
            if abs(snapped - value) > 1e-6:
                self.load_var.set(float(snapped))
            self.load_display_var.set(f"{snapped:g} %BW")

    def on_load_menu_changed(self) -> None:
        """Apply a discrete popup selection without changing the data model."""
        text = self.load_display_var.get().split()[0]
        try:
            self.load_var.set(float(text))
        except (TypeError, ValueError):
            self._sync_load_display()
            return
        self.on_parameter_changed()

    def update_didactic_focus(self) -> None:
        if not hasattr(self, "profile_menu"):
            return
        self.profile_menu.configure(style="TCombobox")
        self.bar_menu.configure(style="TCombobox")
        self.temporal_preset_menu.configure(style="TCombobox")
        for frame in (
            self.parameter_box,
            self.charge_box,
            self.duration_box,
            self.lengths_box,
            self.torque_box,
            self.plot_box,
            self.table_box,
        ):
            frame.configure(style="TLabelframe")
        self.add_condition_button.configure(style="TButton")
        self.play_button.configure(style="TButton")
        self.conditions_table.configure(style="Treeview")
        self._didactic_canvas_colors.clear()
        self.plot_canvas.configure(highlightthickness=1, highlightbackground="#c9d1c7")

        if self.didactic_mode_var.get():
            focus_steps = {
                0: (("widget", self.profile_menu, "GuideSujet.TCombobox"),),
                1: (("widget", self.bar_menu, "GuideBarre.TCombobox"),),
                2: (("widget", self.charge_box, "GuideCharge.TLabelframe"),),
                3: (
                    ("widget", self.duration_box, "GuidePhase.TLabelframe"),
                    ("widget", self.temporal_preset_menu, "GuidePhase.TCombobox"),
                ),
                4: (("canvas", self.pose_canvas, "#2e7d54"),),
                5: (
                    ("canvas", self.animation_canvas, "#2e7d54"),
                    ("widget", self.play_button, "GuidePose.TButton"),
                ),
                6: (
                    ("widget", self.plot_box, "GuideResults.TLabelframe"),
                    ("widget", self.table_box, "GuideResults.TLabelframe"),
                    ("plot_canvas", self.plot_canvas, "#276c92"),
                ),
                7: (
                    ("canvas", self.animation_canvas, "#b05e16"),
                    ("widget", self.plot_box, "GuideResults.TLabelframe"),
                ),
                8: (("widget", self.add_condition_button, "GuidePose.TButton"),),
                9: (
                    ("widget", self.duplicate_condition_button, "GuidePose.TButton"),
                    ("widget", self.parameter_box, "GuideCharge.TLabelframe"),
                    ("widget", self.add_condition_button, "GuidePose.TButton"),
                ),
                10: (
                    ("widget", self.table_box, "GuidePhase.TLabelframe"),
                    ("widget", self.conditions_table, "GuidePhase.Treeview"),
                    ("widget", self.differences_table, "GuidePhase.Treeview"),
                ),
            }
            for target_type, widget, style_or_color in focus_steps[self.didactic_step]:
                if target_type == "widget":
                    widget.configure(style=style_or_color)
                elif target_type == "canvas":
                    self._didactic_canvas_colors[widget] = style_or_color
                else:
                    widget.configure(
                        highlightthickness=4, highlightbackground=style_or_color
                    )
        if self.states:
            self.redraw()

    def update_didactic_guide(self) -> None:
        steps = (
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
        self.didactic_label.configure(state="normal")
        self.didactic_label.delete("1.0", "end")
        if self.didactic_mode_var.get():
            self.didactic_label.configure(bg="#e5f1e8", fg="#154a34")
            pieces = steps[self.didactic_step]
        else:
            self.didactic_label.configure(bg="#f2f4f1", fg="#506158")
            pieces = (("Activer pour guider une exploration etape par etape.", None),)
        for text, tag in pieces:
            self.didactic_label.insert("end", text, () if tag is None else (tag,))
        self.didactic_label.configure(state="disabled")
        self.update_didactic_focus()
        self.update_didactic_navigation()

    def draw_didactic_switch(self) -> None:
        enabled = self.didactic_mode_var.get()
        background = "#2e7d54" if enabled else "#bcc4bd"
        knob_x = 28 if enabled else 10
        self.didactic_switch.delete("all")
        self.didactic_switch.create_oval(
            2, 2, 20, 18, fill=background, outline=background
        )
        self.didactic_switch.create_oval(
            18, 2, 36, 18, fill=background, outline=background
        )
        self.didactic_switch.create_rectangle(
            10, 2, 28, 18, fill=background, outline=background
        )
        self.didactic_switch.create_oval(
            knob_x - 7,
            4,
            knob_x + 7,
            16,
            fill="#ffffff",
            outline="#ffffff",
        )

    def update_didactic_navigation(self) -> None:
        self.draw_didactic_switch()
        active = self.didactic_mode_var.get()
        self.reveal_mode_menu.state(
            ["disabled"] if active else ["!disabled", "readonly"]
        )
        self.didactic_previous_button.state(
            ["!disabled"] if active and self.didactic_step > 0 else ["disabled"]
        )
        self.didactic_next_button.state(
            ["!disabled"] if not active or self.didactic_step < 10 else ["disabled"]
        )

    def toggle_didactic_mode(self) -> None:
        enabling = not self.didactic_mode_var.get()
        self.didactic_mode_var.set(enabling)
        if enabling:
            self._reveal_mode_before_didactic = self.reveal_mode_var.get()
            self.didactic_step = 0
            self.set_reveal_mode(reveal_mode_for_step(self.didactic_step))
        else:
            self.set_reveal_mode(self._reveal_mode_before_didactic)
        self.update_didactic_guide()

    def advance_didactic_guide(self) -> None:
        if not self.didactic_mode_var.get():
            self.didactic_mode_var.set(True)
            self.didactic_step = 0
        else:
            self.didactic_step = min(10, self.didactic_step + 1)
        self.set_reveal_mode(reveal_mode_for_step(self.didactic_step))
        self.update_didactic_guide()

    def retreat_didactic_guide(self) -> None:
        if not self.didactic_mode_var.get():
            return
        self.didactic_step = max(0, self.didactic_step - 1)
        self.set_reveal_mode(reveal_mode_for_step(self.didactic_step))
        self.update_didactic_guide()

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
        if not states:
            return []
        eccentric_times = [
            state.time for state in states if state.phase == "excentrique"
        ]
        isometric_times = [
            state.time for state in states if state.phase == "isometrique"
        ]
        squat_start = eccentric_times[-1] if eccentric_times else states[0].time
        squat_time = (
            (squat_start + isometric_times[-1]) / 2.0
            if isometric_times
            else squat_start
        )
        return [state.time - squat_time for state in states]

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
        if not states:
            return []
        mode = self.time_mode()
        if mode is TimeMode.ABSOLUTE:
            return [state.time for state in states]
        if mode is TimeMode.CENTERED:
            return self.centered_times(states)
        duration = states[-1].time - states[0].time
        if duration <= 1e-9:
            return [0.0 for _state in states]
        return [100.0 * (state.time - states[0].time) / duration for state in states]

    def current_plot_time(self) -> float:
        datasets = self.plot_datasets()
        times = [
            time
            for dataset in datasets
            for time in self.plot_times(dataset["states"])  # type: ignore[arg-type]
        ]
        if not times:
            return 0.0
        tmin, tmax = min(times), max(times)
        frame = min(self.frame_count - 1, max(0, int(self.frame_var.get())))
        fraction = frame / max(1, self.frame_count - 1)
        return tmin + fraction * (tmax - tmin)

    def on_time_mode_changed(self) -> None:
        self.update_time_mode_notice(self.plot_datasets())
        self.redraw()

    def time_mode_notice(self, datasets: list[dict[str, object]]) -> str:
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

    def update_time_mode_notice(self, datasets: list[dict[str, object]]) -> None:
        if hasattr(self, "time_mode_notice_var"):
            self.time_mode_notice_var.set(self.time_mode_notice(datasets))

    def apply_torque_preset(self) -> None:
        preset = torque_presets(70.0, 1.70)[self.torque_preset_var.get()]
        for joint, torque in preset.torques.items():
            self.max_torque_vars[joint].set(round(torque))
        self.on_parameter_changed()

    def apply_temporal_preset(self) -> None:
        selected = self.temporal_preset_display_var.get()
        if not selected:
            self.temporal_preset_var.set("")
            return
        preset = next(
            (
                candidate
                for candidate in TEMPORAL_PRESETS
                if temporal_preset_display(candidate) == selected
            ),
            TEMPORAL_PRESETS_BY_NAME.get(self.temporal_preset_var.get()),
        )
        if preset is None:
            return
        self.temporal_preset_var.set(preset.name)
        self.temporal_preset_display_var.set(temporal_preset_display(preset))
        durations = preset.durations
        self.eccentric_duration_var.set(durations.excentrique)
        self.isometric_duration_var.set(durations.isometrique)
        self.concentric_duration_var.set(durations.concentrique)
        self.on_parameter_changed()

    def on_duration_changed(self) -> None:
        self.temporal_preset_var.set("")
        self.temporal_preset_display_var.set("")
        self.on_parameter_changed()

    def on_parameter_changed(self) -> None:
        if not self._suspend_selection_clear:
            self.clear_condition_selection()
        self.recompute()

    def clear_condition_selection(self) -> None:
        selected = self.conditions_table.selection()
        if selected:
            self.conditions_table.selection_remove(selected)
            self.update_condition_buttons()
            self.update_condition_differences()
            self.update_plot_choices()

    def recompute(self) -> None:
        old_count = self.frame_count
        old_fraction = self.frame_var.get() / max(1, old_count - 1)
        self.frame_count = frame_count_for_duration(self.phase_durations())
        if hasattr(self, "frame_scale"):
            self.frame_scale.configure(to=self.frame_count - 1)
        self.frame_var.set(round(old_fraction * (self.frame_count - 1)))
        anthro = self.anthro()
        self.states, self.results = simulate(
            anthro,
            self.final_q,
            self.phase_durations(),
            self.frame_count,
            self.max_torques(),
            self.angle_adapt_var.get(),
            self.model_cache,
            self.velocity_adapt_var.get(),
        )
        self.bar_path_optimization = None
        if self.optimize_bar_path_var.get():
            self.bar_path_optimization = optimize_deep_squat_bar_path(
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
            self.states = self.bar_path_optimization.states
            self.results = self.bar_path_optimization.dynamics
        if (
            self.results
            and self.results[0].backend == "biorbd"
            and self.model_cache is not None
        ):
            point = self.results[0]
            self.status_var.set(
                f"biorbd actif ({point.support_point_label}: {point.support_point_source}; "
                f"contact: {point.contact_source}): "
                f"{self.model_cache.cached_path_for(anthro)}"
            )
        elif self.results:
            self.status_var.set(
                f"backend analytique actif (contact: {self.results[0].contact_source}): "
                "biorbd indisponible ou modèle non chargé"
            )
        if self.bar_path_optimization is not None:
            self.status_var.set(
                f"{self.status_var.get()} · {self.bar_path_optimization.message}"
            )
        self.update_condition_differences()
        self.redraw()

    def current_settings(self) -> dict[str, object]:
        return {
            "subject_profile": self.subject_profile_var.get(),
            "bar_position": self.bar_position_var.get(),
            "load_percent_bw": self.load_var.get(),
            "load_kg": self.anthro().bar_mass,
            "shank_percent": self.shank_var.get(),
            "thigh_percent": self.thigh_var.get(),
            "trunk_percent": self.trunk_var.get(),
            "anthropometry_mode": self.anthropometry_mode_var.get(),
            "duration_excentrique_s": self.eccentric_duration_var.get(),
            "duration_isometrique_s": self.isometric_duration_var.get(),
            "duration_concentrique_s": self.concentric_duration_var.get(),
            "temporal_preset": self.temporal_preset_var.get(),
            "wedge_20_deg": self.wedge_var.get(),
            "frame": self.frame_var.get(),
            "plot_choice": self.plot_choice.get(),
            "quantity": self.quantity_var.get(),
            "synchronized_source": self.synchronized_source_var.get(),
            "show_joints": {name: var.get() for name, var in self.show_vars.items()},
            "show_com_components": {
                name: var.get() for name, var in self.com_component_vars.items()
            },
            "show_torque_components": {
                name: var.get() for name, var in self.torque_component_vars.items()
            },
            "max_torques": {
                joint: var.get() for joint, var in self.max_torque_vars.items()
            },
            "torque_preset": self.torque_preset_var.get(),
            "show_torque_bounds": self.show_torque_bounds_var.get(),
            "angle_adapt": self.angle_adapt_var.get(),
            "velocity_adapt": self.velocity_adapt_var.get(),
            "optimize_bar_path_experimental": self.optimize_bar_path_var.get(),
            "show_sprite_centers": self.show_sprite_centers_var.get(),
            "show_segment_com": self.show_segment_com_var.get(),
            "display_layers": {
                "global_com": self.show_global_com_var.get(),
                "com_projection": self.show_com_projection_var.get(),
                "segment_com": self.show_segment_com_var.get(),
                "cop_zmp": self.show_cop_var.get(),
                "grf": self.show_grf_var.get(),
                "weight": self.show_weight_var.get(),
                "geometric_base": self.show_geometric_base_var.get(),
                "support_limits": self.show_support_limits_var.get(),
                "force_balance": self.show_force_balance_var.get(),
                "joint_coordinates": self.show_joint_coordinates_var.get(),
                "segment_orientations": self.show_segment_orientations_var.get(),
                "joint_angles": self.show_joint_angles_var.get(),
                "anthropometry": self.show_anthropometry_var.get(),
                "neighbor_samples": self.show_neighbor_samples_var.get(),
                "bar_trajectory": self.show_bar_trajectory_var.get(),
                "moment_arms": self.show_moment_arms_var.get(),
                "capacity_rings": self.show_capacity_rings_var.get(),
                "joint_markers": self.show_joint_markers_var.get(),
            },
            "low_quality_sprites": self.low_quality_sprites_var.get(),
            "refined_sprites": not self.low_quality_sprites_var.get(),
            "time_mode": self.time_mode().value,
            "normalize_time": self.time_mode() is TimeMode.NORMALIZED,
            "subplot_mode": self.subplot_mode_var.get(),
            "show_phase_limits": self.show_phase_limits_var.get(),
            "show_phase_names": self.show_phase_names_var.get(),
            "final_q_deg": [degrees(value) for value in self.final_q],
            "frame_count": self.frame_count,
        }

    def apply_settings(self, settings: dict[str, object]) -> None:
        self._suspend_selection_clear = True
        try:
            self.subject_profile_var.set(
                str(settings.get("subject_profile", self.subject_profile_var.get()))
            )
            self.bar_position_var.set(
                str(settings.get("bar_position", self.bar_position_var.get()))
            )
            if "load_percent_bw" in settings:
                self.load_var.set(float(settings["load_percent_bw"]))
            elif "load_kg" in settings:
                self.load_var.set(100.0 * float(settings["load_kg"]) / 70.0)
            self.shank_var.set(
                float(settings.get("shank_percent", self.shank_var.get()))
            )
            self.thigh_var.set(
                float(settings.get("thigh_percent", self.thigh_var.get()))
            )
            self.trunk_var.set(
                float(settings.get("trunk_percent", self.trunk_var.get()))
            )
            self.anthropometry_mode_var.set(
                str(
                    settings.get(
                        "anthropometry_mode", self.anthropometry_mode_var.get()
                    )
                )
            )
            legacy_duration = float(settings.get("duration_phase_s", 4.0))
            self.eccentric_duration_var.set(
                float(settings.get("duration_excentrique_s", legacy_duration))
            )
            self.isometric_duration_var.set(
                float(settings.get("duration_isometrique_s", 2.0))
            )
            self.concentric_duration_var.set(
                float(settings.get("duration_concentrique_s", legacy_duration))
            )
            loaded_preset = str(settings.get("temporal_preset", ""))
            preset = TEMPORAL_PRESETS_BY_NAME.get(loaded_preset)
            self.temporal_preset_var.set(preset.name if preset is not None else "")
            self.temporal_preset_display_var.set(
                temporal_preset_display(preset) if preset is not None else ""
            )
            self.wedge_var.set(bool(settings.get("wedge_20_deg", False)))
            self.torque_preset_var.set(
                str(settings.get("torque_preset", self.torque_preset_var.get()))
            )
            for joint, value in dict(settings.get("max_torques", {})).items():
                if joint in self.max_torque_vars:
                    self.max_torque_vars[joint].set(float(value))
            for name, value in dict(settings.get("show_joints", {})).items():
                if name in self.show_vars:
                    self.show_vars[name].set(bool(value))
            component_aliases = {"x": "horizontal", "y": "vertical"}
            for name, value in dict(settings.get("show_com_components", {})).items():
                name = component_aliases.get(str(name), str(name))
                if name in self.com_component_vars:
                    self.com_component_vars[name].set(bool(value))
            for name, value in dict(settings.get("show_torque_components", {})).items():
                if name in self.torque_component_vars:
                    self.torque_component_vars[name].set(bool(value))
            self.show_torque_bounds_var.set(
                bool(
                    settings.get(
                        "show_torque_bounds", self.show_torque_bounds_var.get()
                    )
                )
            )
            self.angle_adapt_var.set(
                bool(settings.get("angle_adapt", self.angle_adapt_var.get()))
            )
            self.velocity_adapt_var.set(
                bool(settings.get("velocity_adapt", self.velocity_adapt_var.get()))
            )
            self.optimize_bar_path_var.set(
                bool(
                    settings.get(
                        "optimize_bar_path_experimental",
                        self.optimize_bar_path_var.get(),
                    )
                )
            )
            self.show_sprite_centers_var.set(
                bool(
                    settings.get(
                        "show_sprite_centers", self.show_sprite_centers_var.get()
                    )
                )
            )
            self.show_segment_com_var.set(
                bool(settings.get("show_segment_com", self.show_segment_com_var.get()))
            )
            display_layers = dict(settings.get("display_layers", {}))
            layer_vars = {
                "global_com": self.show_global_com_var,
                "com_projection": self.show_com_projection_var,
                "segment_com": self.show_segment_com_var,
                "cop_zmp": self.show_cop_var,
                "grf": self.show_grf_var,
                "weight": self.show_weight_var,
                "geometric_base": self.show_geometric_base_var,
                "support_limits": self.show_support_limits_var,
                "force_balance": self.show_force_balance_var,
                "joint_coordinates": self.show_joint_coordinates_var,
                "segment_orientations": self.show_segment_orientations_var,
                "joint_angles": self.show_joint_angles_var,
                "anthropometry": self.show_anthropometry_var,
                "neighbor_samples": self.show_neighbor_samples_var,
                "bar_trajectory": self.show_bar_trajectory_var,
                "moment_arms": self.show_moment_arms_var,
                "capacity_rings": self.show_capacity_rings_var,
                "joint_markers": self.show_joint_markers_var,
            }
            for name, variable in layer_vars.items():
                if name in display_layers:
                    variable.set(bool(display_layers[name]))
            if "low_quality_sprites" in settings:
                self.low_quality_sprites_var.set(bool(settings["low_quality_sprites"]))
            else:
                self.low_quality_sprites_var.set(
                    not bool(settings.get("refined_sprites", True))
                )
            legacy_normalized = bool(settings.get("normalize_time", False))
            legacy_mode = (
                TimeMode.NORMALIZED.value
                if legacy_normalized
                else TimeMode.CENTERED.value
            )
            requested_mode = str(settings.get("time_mode", legacy_mode))
            self.time_mode_var.set(
                requested_mode
                if requested_mode in {mode.value for mode in TimeMode}
                else TimeMode.CENTERED.value
            )
            self.subplot_mode_var.set(
                bool(settings.get("subplot_mode", self.subplot_mode_var.get()))
            )
            self.final_q = self.clamp_final_q(
                tuple(
                    radians(value)
                    for value in self.normalized_final_q_deg(
                        settings.get("final_q_deg")
                    )
                )
            )
            self.sync_pose_angle_fields_from_final_q()
            self.quantity_var.set(
                str(settings.get("quantity", self.quantity_var.get()))
            )
            self.synchronized_source_var.set(
                str(
                    settings.get(
                        "synchronized_source", self.synchronized_source_var.get()
                    )
                )
            )
            self.show_phase_limits_var.set(
                bool(
                    settings.get("show_phase_limits", self.show_phase_limits_var.get())
                )
            )
            self.show_phase_names_var.set(
                bool(settings.get("show_phase_names", self.show_phase_names_var.get()))
            )
            plot_choice = str(settings.get("plot_choice", self.plot_choice.get()))
            self.update_plot_choices()
            if plot_choice in self.available_plot_choices():
                self.plot_choice.set(plot_choice)
            self.frame_var.set(int(settings.get("frame", self.frame_var.get())))
            self.on_plot_choice_changed()
        finally:
            self._suspend_selection_clear = False
        self.recompute()

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
        payload = {
            "version": 2,
            "settings": self.current_settings(),
            "conditions": (
                [
                    {
                        "iid": iid,
                        "label": condition["label"],
                        "settings": condition["settings"],
                        "final_q_deg": condition["final_q_deg"],
                        "comparison_reference": condition.get("comparison_reference"),
                    }
                    for iid, condition in self.saved_conditions.items()
                ]
                if include_conditions
                else []
            ),
        }
        Path(path).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self.status_var.set(f"configuration ecrite: {path}")

    def load_json(self, path: str | Path | None = None) -> None:
        if path is None:
            selected = filedialog.askopenfilename(
                title="Charger une condition",
                filetypes=(("JSON", "*.json"), ("Tous les fichiers", "*.*")),
            )
            if not selected:
                return
            path = selected
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        self.clear_conditions()
        self.apply_settings(payload.get("settings", {}))
        for condition in payload.get("conditions", []):
            self.add_saved_condition(
                settings=dict(condition.get("settings", {})),
                final_q_deg=[
                    float(value) for value in condition.get("final_q_deg", [])
                ],
                label=str(condition.get("label", "")) or None,
                iid=str(condition.get("iid", "")) or None,
                comparison_reference=condition.get("comparison_reference"),
            )
        self.status_var.set(f"configuration chargee: {path}")
        self.redraw()

    @staticmethod
    def _condition_export_signature(condition: Condition) -> str:
        """Return the simulation identity, independently from its export label."""

        def canonical(value: object) -> object:
            if isinstance(value, float):
                # Degree/radian round-trips in the editor can differ below the
                # numerical precision of every exported quantity.
                return round(value, 9)
            if isinstance(value, dict):
                return {
                    str(key): canonical(item)
                    for key, item in sorted(
                        value.items(), key=lambda pair: str(pair[0])
                    )
                }
            if isinstance(value, (list, tuple)):
                return [canonical(item) for item in value]
            return value

        payload = {
            key: canonical(value)
            for key, value in condition.__dict__.items()
            if key != "condition_id"
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _normalized_export_id(raw_id: object, fallback: str) -> str:
        """Build an Excel-friendly stable identifier from a session iid."""
        identifier = "".join(
            character if character.isalnum() else "_"
            for character in str(raw_id).strip()
        )
        while "__" in identifier:
            identifier = identifier.replace("__", "_")
        return identifier.strip("_") or fallback

    @staticmethod
    def _unique_export_id(candidate: str, used_ids: set[str]) -> str:
        """Keep condition identifiers unique without changing their stable prefix."""
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
        """Collect saved conditions and a distinct active editor condition.

        A condition that has just been added remains visible in the editor.  Its
        simulation must not therefore appear twice in the student dataset.
        """
        conditions: list[Condition] = []
        saved_signatures: set[str] = set()
        used_ids: set[str] = set()
        for index, (iid, saved) in enumerate(self.saved_conditions.items(), start=1):
            results = list(saved.get("results", []))
            backend = results[0].backend if results else "analytical"
            candidate = self._normalized_export_id(iid, f"condition_{index}")
            condition_id = self._unique_export_id(candidate, used_ids)
            condition = condition_from_settings(
                dict(saved["settings"]),
                list(saved["final_q_deg"]),
                condition_id,
                backend=backend,
            )
            conditions.append(condition)
            saved_signatures.add(self._condition_export_signature(condition))

        current_backend = self.results[0].backend if self.results else "analytical"
        current = condition_from_settings(
            self.current_settings(),
            [degrees(value) for value in self.final_q],
            "condition_courante",
            backend=current_backend,
        )
        if self._condition_export_signature(current) not in saved_signatures:
            current_id = self._unique_export_id("condition_courante", used_ids)
            if current_id != current.condition_id:
                current = condition_from_settings(
                    self.current_settings(),
                    [degrees(value) for value in self.final_q],
                    current_id,
                    backend=current_backend,
                )
            conditions.append(current)
        return conditions

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

        exports = [
            (
                "condition_courante",
                self.current_settings(),
                [degrees(value) for value in self.final_q],
                self.results[0].backend if self.results else "analytical",
            )
        ]
        exports.extend(
            (
                f"condition_{condition['label']}",
                dict(condition["settings"]),
                list(condition["final_q_deg"]),
                (
                    condition["results"][0].backend
                    if condition["results"]
                    else "analytical"
                ),
            )
            for condition in self.saved_conditions.values()
        )
        rows: list[dict[str, object]] = []
        try:
            for condition_id, settings, final_q_deg, backend in exports:
                condition = condition_from_settings(
                    settings,
                    final_q_deg,
                    condition_id,
                    backend=backend,
                )
                condition_rows, _summary = simulate_condition(condition)
                rows.extend(condition_rows)
            output = Path(path)
            write_xlsx(output, rows)
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

        rows: list[dict[str, object]] = []
        output = Path(path)
        replaced_existing = output.exists()
        try:
            conditions = self.session_export_conditions()
            for condition in conditions:
                condition_rows, _summary = simulate_condition(condition)
                rows.extend(condition_rows)
            write_csv(output, rows, mode="standard")
        except (OSError, RuntimeError, ValueError) as error:
            self.status_var.set(f"échec export CSV: {error}")
            if interactive:
                messagebox.showerror("Export CSV", str(error), parent=self)
            return None

        condition_count = len(conditions)
        replacement = (
            "Le fichier existant a été remplacé."
            if replaced_existing
            else "Un nouveau fichier a été créé."
        )
        condition_word = "condition" if condition_count == 1 else "conditions"
        exported_word = "exportée" if condition_count == 1 else "exportées"
        message = (
            f"{condition_count} {condition_word} ({len(rows)} frames) {exported_word} "
            f"dans {output.name}. {replacement} Aucun ajout automatique."
        )
        self.status_var.set(message)
        if interactive:
            messagebox.showinfo("Export CSV combiné", message, parent=self)
        return output

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
            report = export_mp4(
                path,
                self.anthro(),
                self.states,
                self.results,
                self.render_layers(),
            )
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
        if self._redraw_pending:
            return
        self._redraw_pending = True
        self.after(40, self.flush_scheduled_redraw)

    def flush_scheduled_redraw(self) -> None:
        self._redraw_pending = False
        self.redraw()

    def redraw(self) -> None:
        if not self.states:
            return
        if not self.canvases_ready():
            self.schedule_redraw()
            return
        frame = min(self.frame_count - 1, max(0, int(self.frame_var.get())))
        info = frame_info(self.states, frame)
        if self.reveal_mode() is RevealMode.OBSERVATION:
            self.frame_info_var.set("OBSERVATION · temps, phase et grandeurs masqués")
        else:
            self.frame_info_var.set(
                f"Frame {info.frame}/{info.frame_count - 1}  ·  "
                f"t={info.time_s:.3f} s  ·  Δt={info.delta_time_s:.3f} s  ·  "
                f"{info.normalized_time_percent:.1f} %  ·  {info.phase}"
            )
        self.draw_pose_editor()
        self.draw_plot()
        self.draw_animation(frame)

    def on_table_selection_changed(self, _event: tk.Event | None = None) -> None:
        self.update_condition_buttons()
        self.update_condition_differences()
        self.update_plot_choices()
        self.redraw()

    def on_table_tab_changed(self, _event: tk.Event | None = None) -> None:
        """Keep condition actions in a stable position across all tabs."""
        if hasattr(self, "table_buttons"):
            self.table_buttons.grid()
        if hasattr(self, "file_box"):
            self.file_box.grid()

    def update_condition_buttons(self) -> None:
        selected = self.conditions_table.selection()
        if selected:
            self.delete_condition_button.state(["!disabled"])
        else:
            self.delete_condition_button.state(["disabled"])
        self.duplicate_condition_button.state(
            ["!disabled"] if len(selected) == 1 else ["disabled"]
        )

    def clear_condition_differences(self) -> None:
        if not hasattr(self, "differences_table"):
            return
        for iid in self.differences_table.get_children():
            self.differences_table.delete(iid)

    def show_condition_differences(
        self,
        reference_settings: dict[str, object],
        reference_final_q_deg: list[float],
        compared_settings: dict[str, object],
        compared_final_q_deg: list[float],
    ) -> None:
        self.clear_condition_differences()
        differences = parameter_differences(
            reference_settings,
            reference_final_q_deg,
            compared_settings,
            compared_final_q_deg,
        )
        if not differences:
            self.differences_table.insert(
                "",
                "end",
                values=("Aucun paramètre scientifique modifié", "—", "—"),
            )
            return
        for difference in differences:
            self.differences_table.insert(
                "",
                "end",
                values=(difference.label, difference.reference, difference.compared),
            )

    def update_condition_differences(self) -> None:
        if not hasattr(self, "differences_table"):
            return
        selected = [
            iid
            for iid in self.conditions_table.selection()
            if iid in self.saved_conditions
        ]
        if len(selected) >= 2:
            reference = self.saved_conditions[selected[0]]
            compared = self.saved_conditions[selected[1]]
            self.show_condition_differences(
                dict(reference["settings"]),
                list(reference["final_q_deg"]),
                dict(compared["settings"]),
                list(compared["final_q_deg"]),
            )
            return
        if len(selected) == 1:
            condition = self.saved_conditions[selected[0]]
            comparison_reference = condition.get("comparison_reference")
            if isinstance(comparison_reference, dict):
                self.show_condition_differences(
                    dict(comparison_reference.get("settings", {})),
                    list(comparison_reference.get("final_q_deg", [])),
                    dict(condition["settings"]),
                    list(condition["final_q_deg"]),
                )
                return
        if not selected and self._comparison_reference_iid in self.saved_conditions:
            reference = self.saved_conditions[self._comparison_reference_iid]
            self.show_condition_differences(
                dict(reference["settings"]),
                list(reference["final_q_deg"]),
                self.current_settings(),
                [degrees(value) for value in self.final_q],
            )
            return
        self.clear_condition_differences()
        self.differences_table.insert(
            "",
            "end",
            values=("Sélectionnez deux conditions ou utilisez Dupliquer", "", ""),
        )

    def on_table_click(self, event: tk.Event) -> None:
        if not self.conditions_table.identify_row(event.y):
            selected = self.conditions_table.selection()
            if selected:
                self.conditions_table.selection_remove(selected)
                self.on_table_selection_changed()

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

    def world_to_canvas(
        self,
        canvas: tk.Canvas,
        point: tuple[float, float],
        bounds: tuple[float, float, float, float],
    ) -> tuple[float, float]:
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        xmin, xmax, ymin, ymax = bounds
        pad = 42
        scale = min(
            (width - 2 * pad) / (xmax - xmin), (height - 2 * pad) / (ymax - ymin)
        )
        x = pad + (point[0] - xmin) * scale
        y = height - pad - (point[1] - ymin) * scale
        return x, y

    def canvas_to_world(
        self,
        canvas: tk.Canvas,
        x: float,
        y: float,
        bounds: tuple[float, float, float, float],
    ) -> tuple[float, float]:
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        xmin, xmax, ymin, ymax = bounds
        pad = 42
        scale = min(
            (width - 2 * pad) / (xmax - xmin), (height - 2 * pad) / (ymax - ymin)
        )
        return (xmin + (x - pad) / scale, ymin + (height - pad - y) / scale)

    def scene_bounds(
        self,
        extra_x: float = 0.0,
        anthropometries: list[Anthropometry] | None = None,
    ) -> tuple[float, float, float, float]:
        anthropometries = anthropometries or [self.anthro()]
        ymax = max(
            2.22 if anthro.bar_position == "over-head" else 1.92
            for anthro in anthropometries
        )
        xmax = max(
            anthro.foot.length + anthro.shank.length + 0.78
            for anthro in anthropometries
        )
        return (-0.36, xmax + extra_x, -0.08, ymax)

    def pose_editor_bounds(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        result: DynamicsResult,
        anthro: Anthropometry,
    ) -> tuple[float, float, float, float]:
        """Fit the single-pose viewport to the displayed subject.

        ``scene_bounds`` intentionally reserves space to the right for every
        possible animation and for side-by-side conditions.  Reusing it for
        the pose editor left a crouched subject at the far left of its own
        canvas.  Here the vertical reference is kept stable (so force and
        support annotations remain comparable), while the horizontal extent is
        centred on the actual subject and expanded only as much as the canvas
        aspect ratio requires.
        """
        pose = state.pose
        subject_points = (
            pose.heel,
            pose.toe,
            pose.ankle,
            pose.knee,
            pose.hip,
            pose.shoulder,
            pose.bar,
            pose.com,
            *pose.segment_coms.values(),
            (result.cop_x, 0.0),
        )
        subject_xmin = min(point[0] for point in subject_points) - 0.18
        subject_xmax = max(point[0] for point in subject_points) + 0.18

        # Keep room below the foot for the geometric/functional-base labels.
        _, _, _, ymax = self.scene_bounds(anthropometries=[anthro])
        ymin = -0.16
        pad = 42
        drawable_width = max(1, canvas.winfo_width() - 2 * pad)
        drawable_height = max(1, canvas.winfo_height() - 2 * pad)
        aspect_width = (ymax - ymin) * drawable_width / drawable_height
        required_width = max(subject_xmax - subject_xmin, aspect_width)
        centre_x = (subject_xmin + subject_xmax) / 2.0
        return (
            centre_x - required_width / 2.0,
            centre_x + required_width / 2.0,
            ymin,
            ymax,
        )

    def cop_in_foot(self, state: MotionState, result: DynamicsResult) -> bool:
        return support_margins(state.pose, result.cop_x).in_geometric_base

    def support_point_in_functional_base(
        self, state: MotionState, result: DynamicsResult
    ) -> bool:
        return support_margins(state.pose, result.cop_x).in_functional_base

    def com_projection_in_foot(self, state: MotionState) -> bool:
        return support_margins(state.pose, state.pose.com[0]).in_geometric_base

    def over_limit_joints(self, result: DynamicsResult) -> list[str]:
        return [
            joint
            for joint in ("cheville", "genou", "hanche")
            if result.effort_ratios[joint] is None or result.effort_ratios[joint] > 1.0
        ]

    def biomechanical_alerts(
        self, state: MotionState, result: DynamicsResult, include_com: bool
    ) -> list[str]:
        alerts = []
        if not self.support_point_in_functional_base(state, result):
            alerts.append(
                f"{result.support_point_label} hors zone fonctionnelle d'appui"
            )
        if include_com and not self.com_projection_in_foot(state):
            alerts.append("CoM hors pied")
        over_limit = self.over_limit_joints(result)
        if over_limit:
            alerts.append(
                "faisabilité mécanique U > 1 sous les hypothèses du modèle: "
                + ", ".join(over_limit)
            )
        return alerts

    def configure_alert_canvas(self, canvas: tk.Canvas, alerts: list[str]) -> None:
        focus_color = self._didactic_canvas_colors.get(canvas)
        if alerts:
            canvas.configure(
                bg=ALERT_BG, highlightbackground=ALERT_BORDER, highlightthickness=4
            )
        else:
            canvas.configure(
                bg=CANVAS_BG,
                highlightbackground=focus_color or OK_BORDER,
                highlightthickness=4 if focus_color else 2,
            )

    def draw_alert_banner(self, canvas: tk.Canvas, alerts: list[str], y: int) -> None:
        if not alerts:
            return
        text = "Problèmes biomécaniques :\n" + "\n".join(f"• {alert}" for alert in alerts)
        item = canvas.create_text(
            16,
            y,
            text=text,
            anchor="nw",
            fill="#8a1f17",
            font=("Helvetica", 10, "bold"),
            width=max(120, canvas.winfo_width() - 32),
        )
        bbox = canvas.bbox(item)
        if bbox is not None:
            background = canvas.create_rectangle(
                bbox[0] - 5,
                bbox[1] - 3,
                bbox[2] + 5,
                bbox[3] + 3,
                fill="#ffd2cb",
                outline=ALERT_BORDER,
            )
            canvas.tag_lower(background, item)

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
        render_anthro = render_anthro or self.anthro()
        refined_sprites = (
            not self.low_quality_sprites_var.get()
            if refined_sprites is None
            else refined_sprites
        )
        layers = layers or self.render_layers(refined_sprites=refined_sprites)
        bounds = bounds or self.scene_bounds()
        pose = state.pose
        joints = [pose.heel, pose.toe, pose.ankle, pose.knee, pose.hip, pose.shoulder]
        names = ["heel", "toe", "ankle", "knee", "hip", "shoulder"]

        def shifted(point: tuple[float, float]) -> tuple[float, float]:
            return (point[0] + x_offset, point[1])

        points = {
            name: self.world_to_canvas(canvas, shifted(point), bounds)
            for name, point in zip(names, joints)
        }
        if not hasattr(canvas, "_sprite_images"):
            canvas._sprite_images = []

        def mapper(point: tuple[float, float]) -> tuple[float, float]:
            return self.world_to_canvas(canvas, shifted(point), bounds)

        raster_drawn = self.draw_raster_segments(
            canvas, state, mapper, render_anthro, refined_sprites
        )
        if not raster_drawn:
            segments = load_segments()
            foot_scale = render_anthro.foot.length / 1.07
            draw_segment(
                canvas,
                segments["foot"],
                pose.ankle,
                -render_anthro.wedge_angle,
                foot_scale,
                mapper,
                minimum_world_y=0.0,
            )
            draw_segment(
                canvas,
                segments["shank"],
                pose.ankle,
                -state.q[0],
                render_anthro.shank.length,
                mapper,
            )
            draw_segment(
                canvas,
                segments["thigh"],
                pose.knee,
                -state.q[1],
                render_anthro.thigh.length,
                mapper,
            )
            draw_segment(
                canvas,
                segments["trunk_bar"],
                pose.hip,
                -state.q[2],
                render_anthro.trunk.length,
                mapper,
            )
        canvas.create_line(*points["heel"], *points["toe"], width=3, fill="#333333")

        def draw_support_interval(
            limits: tuple[float, float],
            vertical_offset: int,
            color: str,
            label: str,
        ) -> None:
            posterior_px = self.world_to_canvas(
                canvas, shifted((limits[0], 0.0)), bounds
            )
            anterior_px = self.world_to_canvas(
                canvas, shifted((limits[1], 0.0)), bounds
            )
            y = posterior_px[1] + vertical_offset
            canvas.create_line(
                posterior_px[0], y, anterior_px[0], y, fill=color, width=3
            )
            for x in (posterior_px[0], anterior_px[0]):
                canvas.create_line(x, y - 5, x, y + 5, fill=color, width=2)
            canvas.create_text(
                (posterior_px[0] + anterior_px[0]) / 2.0,
                y + 6,
                text=label,
                anchor="n",
                fill=color,
                font=("Helvetica", 7, "bold"),
            )

        if layers.geometric_base:
            draw_support_interval(
                geometric_support_limits(pose), 8, "#506158", "base géométrique"
            )
        if layers.functional_base:
            functional_offset = 24 if layers.geometric_base else 10
            draw_support_interval(
                functional_support_limits(pose),
                functional_offset,
                "#9a5b16",
                "zone fonctionnelle",
            )
        if render_anthro.wedge_angle_deg:
            heel = self.world_to_canvas(canvas, shifted(pose.heel), bounds)
            toe = self.world_to_canvas(canvas, shifted(pose.toe), bounds)
            floor_heel = self.world_to_canvas(
                canvas, shifted((pose.heel[0], 0.0)), bounds
            )
            wedge_item = canvas.create_polygon(
                heel[0],
                heel[1],
                toe[0],
                toe[1],
                floor_heel[0],
                floor_heel[1],
                fill="#d9c39b",
                outline="#7d6542",
            )
            canvas.tag_lower(wedge_item)

        com = self.world_to_canvas(canvas, shifted(pose.com), bounds)
        projection = self.world_to_canvas(canvas, shifted((pose.com[0], 0.0)), bounds)
        if layers.global_com and layers.com_projection:
            canvas.create_line(
                com[0],
                com[1],
                projection[0],
                projection[1],
                fill="#3d7580",
                dash=(4, 4),
                width=1,
            )
        if layers.global_com:
            canvas.create_oval(
                com[0] - 7,
                com[1] - 7,
                com[0] + 7,
                com[1] + 7,
                fill="#2c9ab7",
                outline="",
            )
        if layers.com_projection:
            canvas.create_oval(
                projection[0] - 5,
                projection[1] - 5,
                projection[0] + 5,
                projection[1] + 5,
                fill="#2c9ab7",
                outline="",
            )
        if layers.segment_com:
            for label, point in state.pose.segment_coms.items():
                px = self.world_to_canvas(canvas, shifted(point), bounds)
                canvas.create_oval(
                    px[0] - 4,
                    px[1] - 4,
                    px[0] + 4,
                    px[1] + 4,
                    fill="#e64357",
                    outline="#ffffff",
                )
                canvas.create_text(
                    px[0] + 6,
                    px[1] - 6,
                    text=SEGMENT_LABELS[label],
                    anchor="sw",
                    fill="#8a1f32",
                    font=("Helvetica", 8, "bold"),
                )

        cop = self.world_to_canvas(canvas, (result.cop_x + x_offset, 0.0), bounds)
        if layers.cop_zmp:
            canvas.create_oval(
                cop[0] - 5,
                cop[1] - 5,
                cop[0] + 5,
                cop[1] + 5,
                fill="#c15a2b",
                outline="#ffffff",
            )
            canvas.create_text(
                cop[0] + 7,
                cop[1] - 7,
                text=result.support_point_label,
                anchor="sw",
                fill="#8a3f1f",
                font=("Helvetica", 8, "bold"),
            )
        if layers.grf:
            force_end = self.world_to_canvas(
                canvas,
                (
                    result.cop_x
                    + x_offset
                    + result.ground_reaction[0] / FORCE_DRAW_SCALE,
                    result.ground_reaction[1] / FORCE_DRAW_SCALE,
                ),
                bounds,
            )
            canvas.create_line(
                cop[0],
                cop[1],
                force_end[0],
                force_end[1],
                arrow=tk.LAST,
                width=3,
                fill="#c15a2b",
            )
            canvas.create_text(
                force_end[0] + 5,
                force_end[1],
                text="GRF",
                anchor="w",
                fill="#8a3f1f",
                font=("Helvetica", 8, "bold"),
            )
        if layers.weight:
            weight = render_anthro.total_mass * GRAVITY
            weight_end = self.world_to_canvas(
                canvas,
                shifted((pose.com[0], pose.com[1] - weight / FORCE_DRAW_SCALE)),
                bounds,
            )
            canvas.create_line(
                com[0],
                com[1],
                weight_end[0],
                weight_end[1],
                arrow=tk.LAST,
                width=3,
                fill="#315f8a",
            )
            canvas.create_text(
                weight_end[0] + 5,
                weight_end[1],
                text=f"P={weight:.0f} N",
                anchor="w",
                fill="#315f8a",
                font=("Helvetica", 8, "bold"),
            )
        if layers.moment_arms:
            for joint in (pose.knee, pose.hip):
                projected = self.project_on_force_line(
                    joint, (result.cop_x, 0.0), result.ground_reaction
                )
                joint_px = self.world_to_canvas(canvas, shifted(joint), bounds)
                projected_px = self.world_to_canvas(canvas, shifted(projected), bounds)
                canvas.create_line(
                    joint_px[0],
                    joint_px[1],
                    projected_px[0],
                    projected_px[1],
                    fill="#1f77b4",
                    dash=(4, 4),
                    width=2,
                )
                canvas.create_oval(
                    projected_px[0] - 3,
                    projected_px[1] - 3,
                    projected_px[0] + 3,
                    projected_px[1] + 3,
                    fill="#1f77b4",
                    outline="",
                )

        if layers.capacity_rings:
            for name in ("cheville", "genou", "hanche"):
                utilization = result.effort_ratios[name]
                ratio = 1.0 if utilization is None else min(1.0, utilization)
                red = int(40 + 190 * ratio)
                green = int(170 * max(0.0, 1.0 - max(0.0, ratio - 0.5) * 2.0))
                color = f"#{red:02x}{green:02x}35"
                point = {
                    "cheville": pose.ankle,
                    "genou": pose.knee,
                    "hanche": pose.hip,
                }[name]
                px = self.world_to_canvas(canvas, shifted(point), bounds)
                canvas.create_oval(
                    px[0] - 12,
                    px[1] - 12,
                    px[0] + 12,
                    px[1] + 12,
                    outline=color,
                    width=4,
                )
        if layers.joint_markers:
            for name in ("ankle", "knee", "hip", "shoulder"):
                x, y = points[name]
                canvas.create_oval(
                    x - 6,
                    y - 6,
                    x + 6,
                    y + 6,
                    fill="#ffffff",
                    outline="#1f1f1f",
                    width=2,
                )
        if self.reveal_mode() is RevealMode.FREE and self.show_sprite_centers_var.get():
            for name in ("ankle", "knee", "hip", "shoulder", "toe"):
                x, y = points[name]
                canvas.create_line(x - 12, y, x + 12, y, fill="#26a69a", width=2)
                canvas.create_line(x, y - 12, x, y + 12, fill="#26a69a", width=2)

        if with_handles:
            for name in ("knee", "hip", "shoulder"):
                x, y = points[name]
                canvas.create_oval(
                    x - 9,
                    y - 9,
                    x + 9,
                    y + 9,
                    fill="#f7f7f2",
                    outline="#1d3d35",
                    width=2,
                    tags=name,
                )

    def draw_raster_segments(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        mapper,
        render_anthro: Anthropometry | None = None,
        refined_sprites: bool | None = None,
    ) -> bool:
        try:
            pose = state.pose
            render_anthro = render_anthro or self.anthro()
            refined = (
                not self.low_quality_sprites_var.get()
                if refined_sprites is None
                else refined_sprites
            )
            trunk_variant = (render_anthro.subject_profile, render_anthro.bar_position)
            return all(
                (
                    draw_sprite_segment(
                        canvas,
                        "foot",
                        pose.ankle,
                        pose.toe,
                        mapper,
                        refined,
                        None,
                        0.0,
                    ),
                    draw_sprite_segment(
                        canvas,
                        "shank",
                        pose.ankle,
                        pose.knee,
                        mapper,
                        refined,
                    ),
                    draw_sprite_segment(
                        canvas,
                        "thigh",
                        pose.knee,
                        pose.hip,
                        mapper,
                        refined,
                    ),
                    draw_sprite_segment(
                        canvas,
                        "trunk",
                        pose.hip,
                        pose.shoulder,
                        mapper,
                        refined,
                        trunk_variant,
                    ),
                )
            )
        except Exception:
            return False

    def draw_pose_editor(self) -> None:
        canvas = self.pose_canvas
        canvas.delete("all")
        canvas._sprite_images = []
        anthro = self.anthro()
        pose = pose_from_angles(anthro, self.final_q)
        state = MotionState(
            self.phase_durations().squat_reference_time,
            self.final_q,
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            pose,
            "isometrique",
        )
        result = min(
            self.results,
            key=lambda item: abs(item.com[0] - state.pose.com[0])
            + abs(item.com[1] - state.pose.com[1]),
        )
        layers = self.render_layers(
            refined_sprites=not self.low_quality_sprites_var.get()
        )
        alerts = (
            self.biomechanical_alerts(state, result, include_com=True)
            if layers.alerts
            else []
        )
        bounds = self.pose_editor_bounds(canvas, state, result, anthro)
        self._pose_editor_bounds = bounds
        self.configure_alert_canvas(canvas, alerts)
        self.draw_skeleton(
            canvas,
            state,
            result,
            with_handles=True,
            bounds=bounds,
            render_anthro=anthro,
            refined_sprites=not self.low_quality_sprites_var.get(),
            layers=layers,
        )
        if layers.joint_angles:
            self.draw_squat_angle_labels(canvas, state, bounds)
        canvas.create_text(
            16,
            16,
            text="Position de squat",
            anchor="nw",
            fill="#22312a",
            font=("Helvetica", 13, "bold"),
        )
        canvas.create_text(
            16, 38, text="Glisser genou, hanche ou epaules", anchor="nw", fill="#506158"
        )
        canvas.create_text(
            16,
            54,
            text="Clic droit : angle précis sous l'image (Entrée ou Valider)",
            anchor="nw",
            fill="#506158",
            font=("Helvetica", 8),
        )
        if layers.alerts:
            self.draw_alert_banner(canvas, alerts, 74)

    def draw_squat_angle_labels(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        bounds: tuple[float, float, float, float] | None = None,
    ) -> None:
        pose = state.pose
        bounds = bounds or self.scene_bounds()
        joint_angles = clinical_joint_values_from_segment_values(state.q)
        width = max(1, canvas.winfo_width())
        canvas_height = max(
            1, getattr(canvas, "winfo_height", lambda: 480)()
        )
        if canvas_height <= 1:
            canvas_height = 480
        # Keep the values in left/right lanes, but line each one up with its
        # actual joint.  A small vertical separation is applied only when two
        # labels would otherwise overlap in a compact viewport.
        joint_points = {
            "cheville": pose.ankle,
            "hanche": pose.hip,
            "genou": pose.knee,
        }
        desired_y = {
            name: max(
                74,
                min(
                    canvas_height - 18,
                    self.world_to_canvas(canvas, point, bounds)[1],
                ),
            )
            for name, point in joint_points.items()
        }

        def separated_lane(names: tuple[str, ...]) -> dict[str, float]:
            gap = 24
            floor = 74
            ceiling = canvas_height - 18
            placed: dict[str, float] = {}
            previous = floor - gap
            for name in sorted(names, key=desired_y.__getitem__):
                placed[name] = max(desired_y[name], previous + gap, floor)
                previous = placed[name]
            overflow = max(0.0, max(placed.values()) - ceiling)
            if overflow:
                placed = {
                    name: max(floor, y - overflow) for name, y in placed.items()
                }
            return placed

        left_y = separated_lane(("cheville", "hanche"))
        labels = (
            ("cheville", degrees(joint_angles["cheville"]), 14, left_y["cheville"], "nw"),
            ("hanche", degrees(joint_angles["hanche"]), 14, left_y["hanche"], "nw"),
            ("genou", degrees(joint_angles["genou"]), width - 14, desired_y["genou"], "ne"),
        )
        for name, value, x, y, anchor in labels:
            item = canvas.create_text(
                x,
                y,
                text=f"{name}: {value:.0f} deg",
                anchor=anchor,
                fill="#22312a",
                font=("Helvetica", 9, "bold"),
            )
            bbox = canvas.bbox(item)
            if bbox is not None:
                background = canvas.create_rectangle(
                    bbox[0] - 3,
                    bbox[1] - 2,
                    bbox[2] + 3,
                    bbox[3] + 2,
                    fill=CANVAS_BG,
                    outline="#c9d1c7",
                )
                canvas.tag_lower(background, item)

    def draw_animation(self, frame: int) -> None:
        canvas = self.animation_canvas
        canvas.delete("all")
        canvas._sprite_images = []
        self._animation_hover_targets = []
        layers = self.render_layers()
        datasets = self.plot_datasets()
        current_plot_time = self.current_plot_time()
        sampled = [
            {
                **dataset,
                **self.sample_dataset_at_time(dataset, current_plot_time),
            }
            for dataset in datasets
        ]
        alerts: list[str] = []
        if layers.alerts:
            for item in sampled:
                condition_alerts = self.biomechanical_alerts(
                    item["state"], item["result"], include_com=False  # type: ignore[arg-type]
                )
                alerts.extend(f"{item['label']} : {alert}" for alert in condition_alerts)
        self.configure_alert_canvas(canvas, alerts)
        bounds = self.scene_bounds(
            extra_x=max(0, len(sampled) - 1),
            anthropometries=[item["anthro"] for item in sampled],  # type: ignore[list-item]
        )
        for index, item in enumerate(sampled):
            state = item["state"]  # type: ignore[assignment]
            condition_alerts = (
                self.biomechanical_alerts(
                    state, item["result"], include_com=False  # type: ignore[arg-type]
                )
                if layers.alerts
                else []
            )
            self.draw_skeleton(
                canvas,
                state,  # type: ignore[arg-type]
                item["result"],  # type: ignore[arg-type]
                with_handles=False,
                bounds=bounds,
                x_offset=float(index),
                render_anthro=item["anthro"],  # type: ignore[arg-type]
                refined_sprites=bool(item["refined_sprites"]),
                layers=layers,
            )
            if (
                self.reveal_mode() is RevealMode.FREE
                and self.show_bar_trajectory_var.get()
            ):
                self.draw_bar_trajectory(
                    canvas,
                    item["states"],  # type: ignore[arg-type]
                    bounds,
                    float(index),
                    str(item["color"] or "#2e7d54"),
                )
            self.register_animation_hover_targets(
                canvas,
                state,
                bounds,
                float(index),
                str(item["label"]),
                len(sampled) > 1,
                layers,
            )
            self.register_segment_com_hover_targets(
                canvas,
                state,
                item["anthro"],  # type: ignore[arg-type]
                bounds,
                float(index),
                str(item["label"]),
                len(sampled) > 1,
                layers,
            )
            self.draw_animation_scientific_labels(
                canvas, state, bounds, float(index), layers
            )
            if len(sampled) > 1:
                label_point = self.world_to_canvas(
                    canvas, (float(index), -0.045), bounds
                )
                color = str(item["color"])
                canvas.create_text(
                    label_point[0],
                    label_point[1],
                    text=str(item["label"]),
                    anchor="n",
                    fill=color,
                    font=("Helvetica", 10, "bold"),
                )
                if condition_alerts:
                    canvas.create_text(
                        label_point[0] + 36,
                        label_point[1],
                        text="⚠",
                        anchor="n",
                        fill=ALERT_BORDER,
                        font=("Helvetica", 12, "bold"),
                    )
        state = sampled[0]["state"]  # type: ignore[assignment]
        result = sampled[0]["result"]  # type: ignore[assignment]
        title = (
            f"Animation {state.phase} {self.animation_time_label(current_plot_time)}"
            if layers.time_label
            else "Animation — OBSERVATION"
        )
        canvas.create_text(
            16,
            16,
            text=title,
            anchor="nw",
            fill="#22312a",
            font=("Helvetica", 13, "bold"),
        )
        if self.reveal_mode() in (RevealMode.FREE, RevealMode.DYNAMICS):
            self.draw_animation_values(canvas, sampled)
        overlay_top = 16
        if layers.anthropometry:
            overlay_top = self.draw_anthropometry_overlay(
                canvas,
                sampled[0]["anthro"],  # type: ignore[arg-type]
                str(sampled[0]["label"]) if len(sampled) > 1 else "",
                overlay_top,
            )
        if layers.force_balance:
            self.draw_force_balance_overlay(
                canvas,
                sampled[0]["anthro"],  # type: ignore[arg-type]
                state,
                result,
                overlay_top,
            )
        if (
            self.reveal_mode() is RevealMode.FREE
            and self.show_neighbor_samples_var.get()
        ):
            self.draw_neighbor_samples_overlay(canvas, self.states, frame)
        if layers.alerts:
            self.draw_alert_banner(canvas, alerts, 126)

    def draw_bar_trajectory(
        self,
        canvas: tk.Canvas,
        states: list[MotionState],
        bounds: tuple[float, float, float, float],
        x_offset: float,
        color: str | None,
    ) -> None:
        """Draw the full actual bar path, from descent through the return."""
        if len(states) < 2:
            return
        color = color or "#2e7d54"
        bottom_index = min(range(len(states)), key=lambda index: states[index].pose.bar[1])
        points = [
            self.world_to_canvas(
                canvas,
                (state.pose.bar[0] + x_offset, state.pose.bar[1]),
                bounds,
            )
            for state in states
        ]
        coordinates = [coordinate for point in points for coordinate in point]
        canvas.create_line(
            *coordinates,
            fill=color,
            width=3,
            dash=(7, 4),
            smooth=True,
        )
        markers = (
            (points[0], "départ", -8),
            (points[bottom_index], "bas", 0),
            (points[-1], "retour", 8),
        )
        for point, label, label_y_offset in markers:
            x, y = point
            canvas.create_oval(
                x - 5,
                y - 5,
                x + 5,
                y + 5,
                fill=CANVAS_BG,
                outline=color,
                width=2,
            )
            canvas.create_text(
                x + 8,
                y + label_y_offset,
                text=label,
                anchor="w",
                fill=color,
                font=("Helvetica", 9, "bold"),
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
        if not layers.joint_coordinates:
            return
        for name, point in joint_coordinates(state.pose).items():
            shifted = (point[0] + x_offset, point[1])
            x, y = self.world_to_canvas(canvas, shifted, bounds)
            self._animation_hover_targets.append(
                {
                    "x": x,
                    "y": y,
                    "name": name,
                    "point": point,
                    "condition": condition_label if include_condition else "",
                    "tooltip_text": "",
                }
            )
            canvas.create_oval(x - 8, y - 8, x + 8, y + 8, outline="#276c92", width=2)

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
        if not layers.segment_com:
            return
        table = segment_anthropometry(anthro)
        contributions = com_contributions(anthro, state.pose)
        condition = f"{condition_label} · " if include_condition else ""
        for name, contribution in contributions.items():
            point = contribution.position_m
            x, y = self.world_to_canvas(canvas, (point[0] + x_offset, point[1]), bounds)
            row = table[name]
            if row.com_fraction is None:
                geometry = (
                    f"ponctuelle · attache a={row.attachment_anterior_offset_m:.3f} m, "
                    f"l={row.attachment_longitudinal_offset_m:.3f} m"
                )
            else:
                geometry = (
                    f"L={row.length_m:.3f} m · f={row.com_fraction:.3f} · "
                    f"d⊥={row.com_transverse_offset_m:.3f} m"
                )
            tooltip_text = (
                f"{condition}CoM {row.label}\n"
                f"x={point[0]:.4f} m   y={point[1]:.4f} m\n"
                f"m={row.mass_kg:.3f} kg · I={row.inertia_kg_m2:.4f} kg·m²\n"
                f"mode={row.scaling_mode}\n"
                f"{geometry}\n"
                f"m·x={contribution.weighted_position_kg_m[0]:.4f} kg·m   "
                f"m·y={contribution.weighted_position_kg_m[1]:.4f} kg·m"
            )
            self._animation_hover_targets.append(
                {
                    "x": x,
                    "y": y,
                    "name": name,
                    "point": point,
                    "condition": condition_label if include_condition else "",
                    "tooltip_text": tooltip_text,
                }
            )

    def draw_anthropometry_overlay(
        self,
        canvas: tk.Canvas,
        anthro: Anthropometry,
        condition_label: str,
        top_y: int,
    ) -> int:
        table = segment_anthropometry(anthro)
        title = "Anthropométrie utilisée"
        if condition_label:
            title += f" · {condition_label}"
        lines = [title]
        lines.append(f"mode: {anthro.scaling_mode}")
        for key in ("foot", "shank", "thigh", "trunk"):
            row = table[key]
            lines.append(
                f"{row.label}: L={row.length_m:.3f} m · m={row.mass_kg:.2f} kg · f={row.com_fraction:.3f}"
            )
        lines.append(f"barre ponctuelle: m={anthro.bar_mass:.2f} kg")
        lines.append(f"masse totale: {anthro.total_mass:.2f} kg")
        text_item = canvas.create_text(
            max(10, canvas.winfo_width() - 12),
            top_y,
            text="\n".join(lines),
            anchor="ne",
            justify="left",
            fill="#17364a",
            font=("Helvetica", 8, "bold"),
            tags="anthropometry-overlay",
        )
        bbox = canvas.bbox(text_item)
        if bbox is not None:
            background = canvas.create_rectangle(
                bbox[0] - 7,
                bbox[1] - 6,
                bbox[2] + 7,
                bbox[3] + 6,
                fill="#f4faf7",
                outline="#587a5f",
                tags="anthropometry-overlay",
            )
            canvas.tag_lower(background, text_item)
            return bbox[3] + 12
        return top_y

    def draw_force_balance_overlay(
        self,
        canvas: tk.Canvas,
        anthro: Anthropometry,
        state: MotionState,
        result: DynamicsResult,
        top_y: int,
    ) -> int:
        balance = force_balance(anthro, result)
        point = support_margins(state.pose, result.cop_x)
        com_projection = support_margins(state.pose, state.pose.com[0])
        lines = [
            "Bilan forces et équilibre",
            "repère: +x avant · +y haut",
            f"P=(0, {balance.weight_vector_N[1]:.1f}) N",
            f"GRF=({result.ground_reaction[0]:.1f}, {result.ground_reaction[1]:.1f}) N",
            f"GRF + P − m·a=({balance.residual_N[0]:.2e}, {balance.residual_N[1]:.2e}) N",
            f"{result.support_point_label}: x={result.cop_x:.4f} m · {result.support_point_source}",
            (
                f"base géom.=[{point.geometric_posterior_m:.4f}, "
                f"{point.geometric_anterior_m:.4f}] m"
            ),
            (
                f"zone fonct.=[{point.functional_posterior_m:.4f}, "
                f"{point.functional_anterior_m:.4f}] m"
            ),
            (
                f"marges {result.support_point_label} fonct.: "
                f"post.={point.functional_posterior_margin_m:.4f} · "
                f"ant.={point.functional_anterior_margin_m:.4f} m"
            ),
            (
                f"projection CoM: x={state.pose.com[0]:.4f} m · "
                f"géom.={'oui' if com_projection.in_geometric_base else 'non'}"
            ),
        ]
        text_item = canvas.create_text(
            max(10, canvas.winfo_width() - 12),
            top_y,
            text="\n".join(lines),
            width=330,
            anchor="ne",
            justify="left",
            fill="#4f3518",
            font=("Helvetica", 9, "bold"),
            tags="force-balance-overlay",
        )
        bbox = canvas.bbox(text_item)
        if bbox is not None:
            background = canvas.create_rectangle(
                bbox[0] - 7,
                bbox[1] - 6,
                bbox[2] + 7,
                bbox[3] + 6,
                fill="#fff8e8",
                outline="#9a5b16",
                tags="force-balance-overlay",
            )
            canvas.tag_lower(background, text_item)
            return bbox[3] + 12
        return top_y

    def draw_neighbor_samples_overlay(
        self,
        canvas: tk.Canvas,
        states: list[MotionState],
        frame: int,
    ) -> None:
        samples = neighbor_samples(states, frame)
        labels = ("i−1", "i", "i+1")
        lines = ["Échantillons pour dérivation manuelle"]
        for label, sample in zip(labels, samples):
            if sample is None:
                lines.append(f"{label}: indisponible")
                continue
            angles = tuple(degrees(value) for value in sample.joint_angles_rad)
            lines.append(
                f"{label} · F{sample.frame} · t={sample.time_s:.3f} s · {sample.phase}"
            )
            lines.append(
                f"  CoM=({sample.com_m[0]:.4f}, {sample.com_m[1]:.4f}) m · "
                f"θ=({angles[0]:.1f}, {angles[1]:.1f}, {angles[2]:.1f})°"
            )
        previous, current, following = samples
        dt_previous = (
            "—"
            if previous is None or current is None
            else f"{current.time_s - previous.time_s:.3f} s"
        )
        dt_following = (
            "—"
            if following is None or current is None
            else f"{following.time_s - current.time_s:.3f} s"
        )
        lines.append(f"Δt−={dt_previous} · Δt+={dt_following}")
        text_item = canvas.create_text(
            max(10, canvas.winfo_width() - 12),
            max(10, canvas.winfo_height() - 12),
            text="\n".join(lines),
            width=330,
            anchor="se",
            justify="left",
            fill="#3d315f",
            font=("Helvetica", 9, "bold"),
            tags="neighbor-samples-overlay",
        )
        bbox = canvas.bbox(text_item)
        if bbox is not None:
            background = canvas.create_rectangle(
                bbox[0] - 7,
                bbox[1] - 6,
                bbox[2] + 7,
                bbox[3] + 6,
                fill="#f6f2fb",
                outline="#6d5ea8",
                tags="neighbor-samples-overlay",
            )
            canvas.tag_lower(background, text_item)

    def draw_animation_scientific_labels(
        self,
        canvas: tk.Canvas,
        state: MotionState,
        bounds: tuple[float, float, float, float],
        x_offset: float,
        layers: RenderLayers,
    ) -> None:
        pose = state.pose
        if layers.segment_orientations:
            orientations = segment_orientations(pose)
            endpoints = {
                "foot": (pose.heel, pose.toe),
                "shank": (pose.ankle, pose.knee),
                "thigh": (pose.knee, pose.hip),
                "trunk": (pose.hip, pose.shoulder),
            }
            orientation_offsets = {
                "foot": (8, 24, "nw"),
                "shank": (8, -4, "sw"),
                "thigh": (8, -10, "sw"),
                "trunk": (8, -10, "sw"),
            }
            for name, (start, end) in endpoints.items():
                midpoint = (
                    (start[0] + end[0]) / 2.0 + x_offset,
                    (start[1] + end[1]) / 2.0,
                )
                x, y = self.world_to_canvas(canvas, midpoint, bounds)
                dx, dy, anchor = orientation_offsets[name]
                canvas.create_text(
                    x + dx,
                    y + dy,
                    text=f"{SEGMENT_LABELS[name]}: {degrees(orientations[name]):.1f}°",
                    anchor=anchor,
                    fill="#276c92",
                    font=("Helvetica", 8, "bold"),
                )
        if layers.joint_angles:
            angles = joint_angles_from_pose(pose)
            points = {"cheville": pose.ankle, "genou": pose.knee, "hanche": pose.hip}
            angle_offsets = {
                "cheville": (12, -12, "sw"),
                "genou": (12, 16, "nw"),
                "hanche": (12, 16, "nw"),
            }
            for name, point in points.items():
                x, y = self.world_to_canvas(
                    canvas, (point[0] + x_offset, point[1]), bounds
                )
                dx, dy, anchor = angle_offsets[name]
                canvas.create_text(
                    x + dx,
                    y + dy,
                    text=f"{name}: {degrees(angles[name]):.1f}°",
                    anchor=anchor,
                    fill="#6d5ea8",
                    font=("Helvetica", 8, "bold"),
                )

    def clear_animation_tooltip(self, _event: tk.Event | None = None) -> None:
        if hasattr(self, "animation_canvas"):
            self.animation_canvas.delete("scientific-tooltip")

    def on_animation_motion(self, event: tk.Event) -> None:
        self.clear_animation_tooltip()
        if not self._animation_hover_targets:
            return
        target = min(
            self._animation_hover_targets,
            key=lambda item: (
                (float(item["x"]) - event.x) ** 2 + (float(item["y"]) - event.y) ** 2,
                0 if item["tooltip_text"] else 1,
            ),
        )
        distance_squared = (float(target["x"]) - event.x) ** 2 + (
            float(target["y"]) - event.y
        ) ** 2
        if distance_squared > 18.0**2:
            return
        tooltip_text = str(target["tooltip_text"])
        if not tooltip_text:
            point = target["point"]
            condition = f"{target['condition']} · " if target["condition"] else ""
            label = POINT_LABELS[str(target["name"])]
            tooltip_text = (
                f"{condition}{label}\nx={point[0]:.4f} m   y={point[1]:.4f} m"
            )
        x = min(max(8, event.x + 14), max(8, self.animation_canvas.winfo_width() - 340))
        y = max(8, event.y - 12)
        text_item = self.animation_canvas.create_text(
            x,
            y,
            text=tooltip_text,
            width=320,
            anchor="sw",
            fill="#17364a",
            font=("Helvetica", 9, "bold"),
            tags="scientific-tooltip",
        )
        bbox = self.animation_canvas.bbox(text_item)
        if bbox is not None:
            background = self.animation_canvas.create_rectangle(
                bbox[0] - 5,
                bbox[1] - 4,
                bbox[2] + 5,
                bbox[3] + 4,
                fill="#eef7fb",
                outline="#276c92",
                tags="scientific-tooltip",
            )
            self.animation_canvas.tag_lower(background, text_item)

    def draw_animation_values(
        self, canvas: tk.Canvas, sampled: list[dict[str, object]]
    ) -> None:
        column_width = 155
        for index, item in enumerate(sampled):
            x = 16 + index * column_width
            y = 42
            color = str(item["color"] or "#22312a")
            result = item["result"]  # type: ignore[assignment]
            canvas.create_text(
                x,
                y,
                text=str(item["label"]),
                anchor="nw",
                fill=color,
                font=("Helvetica", 10, "bold"),
            )
            y += 18
            for joint in ("cheville", "genou", "hanche"):
                torque = result.torques[joint]
                ratio = result.effort_ratios[joint]
                text_color = "#8a1f17" if ratio is None or ratio > 1.0 else color
                utilization_text = "n.d." if ratio is None else f"{100 * ratio: .0f}%"
                canvas.create_text(
                    x,
                    y,
                    text=f"{joint}: {torque: .1f} Nm (U={utilization_text})",
                    anchor="nw",
                    fill=text_color,
                    font=("Helvetica", 9),
                )
                y += 18

    def draw_plot(self) -> None:
        canvas = self.plot_canvas
        canvas.delete("all")
        self._plot_hit_regions = []
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        datasets = self.plot_datasets()
        self.update_time_mode_notice(datasets)
        if self.reveal_mode() is RevealMode.OBSERVATION:
            self.update_cursor_table([])
            self.plot_title_var.set("OBSERVATION — courbes masquées")
            canvas.create_text(
                width / 2,
                height / 2,
                text="Observez le mouvement et formulez une hypothèse.\n"
                "Passez à CINÉMATIQUE pour révéler position, vitesse et accélération.",
                width=max(240, width - 100),
                justify="center",
                fill="#506158",
                font=("Helvetica", 12, "bold"),
            )
            return
        choice = self.plot_choice.get()
        if choice == SYNCHRONIZED_KINEMATICS_CHOICE:
            source = self.synchronized_source_var.get()
            self.plot_title_var.set(f"cinématique synchronisée — {source}")
            self.draw_synchronized_kinematics(canvas, datasets, width, height)
            return
        self.plot_title_var.set(f"{choice} ({self.plot_unit(choice)})")
        plotted = [
            {
                **dataset,
                "series": self.plot_series_for(choice, dataset["states"], dataset["results"]),  # type: ignore[arg-type]
                "times": self.plot_times(dataset["states"]),  # type: ignore[arg-type]
            }
            for dataset in datasets
        ]
        plotted = [dataset for dataset in plotted if dataset["series"]]
        self.update_cursor_table(plotted, choice)
        if not plotted:
            return
        if self.subplot_mode_var.get():
            self.draw_subplot_plot(canvas, plotted, choice, width, height)
        else:
            self.draw_single_axis_plot(canvas, plotted, choice, width, height)

    def synchronized_series_for(
        self,
        source: str,
        quantity: str,
        states: list[MotionState],
        results: list[DynamicsResult],
    ) -> dict[str, list[float]]:
        if source == "centre de masse":
            return self.com_plot_series_for_quantity(results, quantity)
        series = self.joint_kinematic_series_for_quantity(states, quantity)
        return {
            name: values
            for name, values in series.items()
            if self.show_vars[name].get()
        }

    def kinematic_unit(self, source: str, quantity: str) -> str:
        if source == "centre de masse":
            return {"position": "m", "vitesse": "m/s", "acceleration": "m/s²"}[quantity]
        return {"position": "deg", "vitesse": "deg/s", "acceleration": "deg/s²"}[
            quantity
        ]

    def draw_synchronized_kinematics(
        self,
        canvas: tk.Canvas,
        datasets: list[dict[str, object]],
        width: int,
        height: int,
    ) -> None:
        source = self.synchronized_source_var.get()
        quantities = ("position", "vitesse", "acceleration")
        plotted = []
        for dataset in datasets:
            states = dataset["states"]  # type: ignore[assignment]
            results = dataset["results"]  # type: ignore[assignment]
            plotted.append(
                {
                    **dataset,
                    "times": self.plot_times(states),
                    "orders": {
                        quantity: self.synchronized_series_for(
                            source,
                            quantity,
                            states,  # type: ignore[arg-type]
                            results,  # type: ignore[arg-type]
                        )
                        for quantity in quantities
                    },
                }
            )
        self.update_synchronized_cursor_table(plotted, source)
        if not plotted:
            return
        pad_left, pad_top, pad_right, pad_bottom = 62, 22, 18, 34
        gap = 12
        panel_height = (height - pad_top - pad_bottom - 2 * gap) / 3.0
        tmin, tmax = self.plot_time_bounds(plotted)
        for panel_index, quantity in enumerate(quantities):
            y1 = pad_top + panel_index * (panel_height + gap)
            y0 = y1 + panel_height
            x0, x1 = pad_left, width - pad_right
            values = [
                value
                for dataset in plotted
                for series in dataset["orders"][quantity].values()  # type: ignore[index,union-attr]
                for value in series
            ]
            if not values:
                continue
            ymin, ymax = self.value_bounds_with_zero(values)
            unit = self.kinematic_unit(source, quantity)
            self.draw_panel_axes(
                canvas,
                x0,
                x1,
                y0,
                y1,
                ymin,
                ymax,
                unit,
                quantity,
                tmin,
                tmax,
                show_x_axis=panel_index == 2,
            )
            self.draw_zero_line(canvas, x0, x1, y0, y1, ymin, ymax)
            self.draw_phase_markers(canvas, plotted, x0, x1, y0, y1, tmin, tmax)
            for dataset in plotted:
                series_map = dataset["orders"][quantity]  # type: ignore[index]
                for series_index, (name, series) in enumerate(series_map.items()):  # type: ignore[union-attr]
                    if len(plotted) > 1:
                        color = str(dataset["color"])
                        dash = (None, (6, 4), (2, 3))[series_index % 3]
                    else:
                        color = JOINT_COLORS.get(str(name), "#2e7d54")
                        dash = None
                    self.draw_series_line(
                        canvas,
                        series,
                        x0,
                        x1,
                        y0,
                        y1,
                        ymin,
                        ymax,
                        color,
                        width=2,
                        dash=dash,
                        times=dataset["times"],  # type: ignore[arg-type]
                        tmin=tmin,
                        tmax=tmax,
                    )
        self.draw_synchronized_legend(canvas, plotted, source, width)
        self.draw_condition_legend(canvas, plotted, width, height)

    def value_bounds_with_zero(self, values: list[float]) -> tuple[float, float]:
        finite_values = [value for value in values if isfinite(value)]
        if not finite_values:
            return (-1.0, 1.0)
        ymin = min(0.0, min(finite_values))
        ymax = max(0.0, max(finite_values))
        if abs(ymax - ymin) < 1e-12:
            return (-1.0, 1.0)
        margin = 0.05 * (ymax - ymin)
        return ymin - margin, ymax + margin

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
        if not ymin <= 0.0 <= ymax:
            return
        y = y0 - (y0 - y1) * (0.0 - ymin) / (ymax - ymin)
        canvas.create_line(x0, y, x1, y, fill="#7f8f83", width=1, dash=(3, 4))
        canvas.create_text(
            x1 - 3,
            y - 2,
            text="0",
            anchor="se",
            fill="#506158",
            font=("Helvetica", 8, "bold"),
        )

    def draw_synchronized_legend(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        source: str,
        width: int,
    ) -> None:
        if len(plotted) > 1:
            return
        names = (
            ("horizontal", "vertical")
            if source == "centre de masse"
            else ("cheville", "genou", "hanche")
        )
        x = width - 18
        for name in reversed(names):
            if source == "centre de masse":
                visible = self.com_component_vars[name].get()
            else:
                visible = self.show_vars[name].get()
            if not visible:
                continue
            canvas.create_text(
                x,
                10,
                text=name,
                anchor="ne",
                fill=JOINT_COLORS[name],
                font=("Helvetica", 8, "bold"),
            )
            x -= 9 * len(name) + 12

    def clear_cursor_table(self) -> None:
        if not hasattr(self, "cursor_table"):
            return
        for iid in self.cursor_table.get_children():
            self.cursor_table.delete(iid)

    def insert_cursor_value(
        self,
        condition: str,
        variable: str,
        value: float,
        unit: str,
        sample_time: float,
        phase: str,
    ) -> None:
        time_unit = time_axis_unit(self.time_mode())
        phase_label = phase if self.show_phase_names_var.get() else "masquée"
        self.cursor_table.insert(
            "",
            "end",
            values=(
                condition,
                variable,
                f"{value:.6f}",
                unit,
                f"{sample_time:.3f} {time_unit}",
                phase_label,
            ),
        )

    def update_cursor_table(
        self,
        plotted: list[dict[str, object]],
        choice: str | None = None,
    ) -> None:
        if not hasattr(self, "cursor_table"):
            return
        self.clear_cursor_table()
        if self.reveal_mode() is RevealMode.OBSERVATION:
            self.cursor_table.insert(
                "",
                "end",
                values=("", "Valeurs masquées", "", "", "", ""),
            )
            return
        if choice is None:
            return
        cursor_time = self.current_plot_time()
        unit = self.plot_unit(choice)
        for dataset in plotted:
            times = dataset["times"]  # type: ignore[assignment]
            if not times:
                continue
            index = nearest_time_index(times, cursor_time)  # type: ignore[arg-type]
            states = dataset["states"]  # type: ignore[assignment]
            for name, values in dataset["series"].items():  # type: ignore[union-attr]
                if index >= len(values):
                    continue
                self.insert_cursor_value(
                    str(dataset["label"]),
                    str(name),
                    float(values[index]),
                    unit,
                    float(times[index]),
                    str(states[index].phase),
                )

    def update_synchronized_cursor_table(
        self,
        plotted: list[dict[str, object]],
        source: str,
    ) -> None:
        if not hasattr(self, "cursor_table"):
            return
        self.clear_cursor_table()
        cursor_time = self.current_plot_time()
        for dataset in plotted:
            times = dataset["times"]  # type: ignore[assignment]
            if not times:
                continue
            index = nearest_time_index(times, cursor_time)  # type: ignore[arg-type]
            states = dataset["states"]  # type: ignore[assignment]
            for quantity in ("position", "vitesse", "acceleration"):
                unit = self.kinematic_unit(source, quantity)
                for name, values in dataset["orders"][quantity].items():  # type: ignore[index,union-attr]
                    if index >= len(values):
                        continue
                    self.insert_cursor_value(
                        str(dataset["label"]),
                        f"{quantity} · {name}",
                        float(values[index]),
                        unit,
                        float(times[index]),
                        str(states[index].phase),
                    )

    def plot_datasets(self) -> list[dict[str, object]]:
        selected = [
            iid
            for iid in self.conditions_table.selection()
            if iid in self.saved_conditions
        ]
        if not selected:
            settings = self.current_settings()
            return [
                {
                    "label": "courant",
                    "states": self.states,
                    "results": self.results,
                    "color": None,
                    "anthro": self.anthro(),
                    "refined_sprites": self.refined_sprites_from_settings(settings),
                    "durations": self.phase_durations(),
                }
            ]
        total = len(selected)
        datasets: list[dict[str, object]] = []
        for index, iid in enumerate(selected):
            condition = self.saved_conditions[iid]
            settings = condition["settings"]  # type: ignore[assignment]
            datasets.append(
                {
                    "label": condition["label"],
                    "states": condition["states"],
                    "results": condition["results"],
                    "color": self.condition_color(index, total),
                    "anthro": self.anthro_from_settings(settings),  # type: ignore[arg-type]
                    "refined_sprites": self.refined_sprites_from_settings(settings),  # type: ignore[arg-type]
                    "durations": self.phase_durations_from_settings(settings),  # type: ignore[arg-type]
                }
            )
        return datasets

    def sample_dataset_at_time(
        self, dataset: dict[str, object], plot_time: float
    ) -> dict[str, object]:
        states = dataset["states"]  # type: ignore[assignment]
        results = dataset["results"]  # type: ignore[assignment]
        times = self.plot_times(states)
        if not times:
            return {"state": self.states[0], "result": self.results[0]}
        if plot_time <= times[0]:
            return {"state": states[0], "result": results[0]}
        if plot_time >= times[-1]:
            return {"state": states[-1], "result": results[-1]}
        index = min(
            range(len(times)), key=lambda candidate: abs(times[candidate] - plot_time)
        )
        return {"state": states[index], "result": results[index]}

    def animation_time_label(self, plot_time: float) -> str:
        mode = self.time_mode()
        if mode is TimeMode.NORMALIZED:
            return f"temps normalisé={plot_time:.0f}%"
        if mode is TimeMode.ABSOLUTE:
            return f"temps absolu={plot_time:.2f}s"
        return f"temps centré={plot_time:.2f}s"

    def plot_time_bounds(self, plotted: list[dict[str, object]]) -> tuple[float, float]:
        if self.time_mode() is TimeMode.NORMALIZED:
            return (0.0, 100.0)
        times = [
            time
            for dataset in plotted
            for time in dataset.get("times", [])  # type: ignore[union-attr]
        ]
        if not times:
            durations = self.phase_durations()
            if self.time_mode() is TimeMode.ABSOLUTE:
                return (0.0, durations.total)
            return (
                -durations.squat_reference_time,
                durations.total - durations.squat_reference_time,
            )
        xmin = min(times)
        xmax = max(times)
        if abs(xmax - xmin) < 1e-9:
            return (xmin - 1.0, xmax + 1.0)
        return xmin, xmax

    def x_from_time(
        self, time: float, x0: float, x1: float, tmin: float, tmax: float
    ) -> float:
        return x0 + (x1 - x0) * (time - tmin) / (tmax - tmin)

    def condition_color(self, index: int, total: int) -> str:
        if total <= 1:
            return "#2e7d54"
        fraction = index / max(1, total - 1)
        if fraction <= 0.5:
            local = fraction / 0.5
            start = (198, 51, 44)
            end = (46, 125, 84)
        else:
            local = (fraction - 0.5) / 0.5
            start = (46, 125, 84)
            end = (42, 140, 166)
        rgb = tuple(
            round(start[channel] + local * (end[channel] - start[channel]))
            for channel in range(3)
        )
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

    def blend_color(self, color: str, target: str, fraction: float) -> str:
        color = color.lstrip("#")
        target = target.lstrip("#")
        rgb = tuple(int(color[index : index + 2], 16) for index in (0, 2, 4))
        target_rgb = tuple(int(target[index : index + 2], 16) for index in (0, 2, 4))
        mixed = tuple(
            round(rgb[index] + fraction * (target_rgb[index] - rgb[index]))
            for index in range(3)
        )
        return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"

    def component_color(self, base_color: str, component: str) -> str:
        if component == "M(q) qddot":
            return base_color
        if component == "termes qdot":
            return self.blend_color(base_color, "#111111", 0.18)
        if component == "gravité":
            return self.blend_color(base_color, "#ffffff", 0.20)
        if component == "total ID":
            return self.blend_color(base_color, "#ffffff", 0.28)
        if component == "contact externe (signé)":
            return self.blend_color(base_color, "#ffffff", 0.48)
        return base_color

    def visible_torque_components(self) -> tuple[str, ...]:
        variables = self.__dict__.get("torque_component_vars")
        if variables is None:
            return tuple(TORQUE_COMPONENT_KEYS)
        return tuple(
            component
            for component in TORQUE_COMPONENT_KEYS
            if component in variables and variables[component].get()
        )

    def torque_component_styles(
        self,
    ) -> dict[str, tuple[int, tuple[int, ...] | None, str | None]]:
        return {
            "M(q) qddot": (2, None, None),
            "termes qdot": (1, (2, 3), None),
            "gravité": (1, (7, 4), None),
            "contact externe (signé)": (1, (7, 3, 2, 3), "triangle"),
            "total ID": (3, None, None),
        }

    def selected_panel_names(
        self, plotted: list[dict[str, object]], choice: str
    ) -> list[str]:
        if choice == DETAILED_PLOT_CHOICE:
            return [
                joint
                for joint in ("cheville", "genou", "hanche")
                if self.show_vars[joint].get()
            ]
        names: list[str] = []
        for dataset in plotted:
            for name in dataset["series"]:  # type: ignore[union-attr]
                if name not in names:
                    names.append(str(name))
        return names

    def draw_subplot_plot(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        choice: str,
        width: int,
        height: int,
    ) -> None:
        panels = self.selected_panel_names(plotted, choice)
        if not panels:
            return
        pad_left = 54
        pad_top = 82 if choice == DETAILED_PLOT_CHOICE else 32
        pad_right, pad_bottom = 18, 44
        gap = 44 if choice == DETAILED_PLOT_CHOICE else 22
        panel_width = (width - pad_left - pad_right - gap * (len(panels) - 1)) / len(
            panels
        )
        unit = self.plot_unit(choice)
        tmin, tmax = self.plot_time_bounds(plotted)
        for panel_index, panel_name in enumerate(panels):
            x0 = pad_left + panel_index * (panel_width + gap)
            x1 = x0 + panel_width
            y0 = height - pad_bottom
            y1 = pad_top
            values = self.panel_values(plotted, choice, panel_name)
            if not values:
                continue
            ymin, ymax = self.value_bounds(values, choice, panel_name)
            self.draw_panel_axes(
                canvas, x0, x1, y0, y1, ymin, ymax, unit, panel_name, tmin, tmax
            )
            self.draw_phase_markers(canvas, plotted, x0, x1, y0, y1, tmin, tmax)
            if choice == DETAILED_PLOT_CHOICE:
                self.draw_detailed_panel(
                    canvas, plotted, panel_name, x0, x1, y0, y1, ymin, ymax, tmin, tmax
                )
            else:
                self.draw_panel_series(
                    canvas, plotted, panel_name, x0, x1, y0, y1, ymin, ymax, tmin, tmax
                )
            self.draw_panel_limits(
                canvas,
                plotted,
                choice,
                panel_name,
                x0,
                x1,
                y0,
                y1,
                ymin,
                ymax,
                tmin,
                tmax,
            )
        self.draw_condition_legend(canvas, plotted, width, height)
        if choice == DETAILED_PLOT_CHOICE:
            self.draw_detailed_component_legend(
                canvas,
                pad_left,
                24,
                horizontal=True,
            )

    def draw_single_axis_plot(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        choice: str,
        width: int,
        height: int,
    ) -> None:
        pad_left = 54
        pad_top = 66 if choice == DETAILED_PLOT_CHOICE else 24
        pad_right, pad_bottom = 18, 36
        x0, y0 = pad_left, height - pad_bottom
        x1, y1 = width - pad_right, pad_top
        tmin, tmax = self.plot_time_bounds(plotted)
        all_values = [
            value
            for dataset in plotted
            for values in dataset["series"].values()  # type: ignore[union-attr]
            for value in values
        ]
        panels = self.selected_panel_names(plotted, choice)
        for panel in panels:
            all_values.extend(self.limit_values_for_plot(choice, panel))
        if choice == "couples normalises":
            all_values.append(100.0)
        ymin, ymax = self.value_bounds(all_values, choice, None)
        unit = self.plot_unit(choice)
        self.draw_panel_axes(
            canvas, x0, x1, y0, y1, ymin, ymax, unit, choice, tmin, tmax
        )
        self.draw_phase_markers(canvas, plotted, x0, x1, y0, y1, tmin, tmax)
        if choice == DETAILED_PLOT_CHOICE:
            for panel in panels:
                self.draw_detailed_panel(
                    canvas, plotted, panel, x0, x1, y0, y1, ymin, ymax, tmin, tmax
                )
            self.draw_detailed_component_legend(
                canvas,
                x0,
                20,
                horizontal=True,
            )
        else:
            palette = [
                "#2e7d54",
                "#b46d22",
                "#6d5ea8",
                "#2a8ca6",
                "#9b3d3d",
                "#4c6f3d",
                "#8a5a22",
            ]
            for dataset_index, dataset in enumerate(plotted):
                multi_condition = len(plotted) > 1
                for series_index, (name, values) in enumerate(dataset["series"].items()):  # type: ignore[union-attr]
                    color = (
                        str(dataset["color"])
                        if multi_condition
                        else JOINT_COLORS.get(
                            name, palette[series_index % len(palette)]
                        )
                    )
                    dash = (
                        None
                        if not multi_condition
                        else (None, (6, 4), (2, 3))[series_index % 3]
                    )
                    self.draw_series_line(canvas, values, x0, x1, y0, y1, ymin, ymax, color, width=2, dash=dash, times=dataset["times"], tmin=tmin, tmax=tmax)  # type: ignore[arg-type]
        self.draw_torque_bounds(canvas, x0, x1, y0, y1, ymin, ymax, tmin, tmax)
        self.draw_normalized_torque_limit(canvas, x0, x1, y0, y1, ymin, ymax)
        if choice == "force reaction sol" and "vertical" in panels:
            self.draw_body_weight_line(canvas, plotted, x0, x1, y0, y1, ymin, ymax)
        self.draw_condition_legend(canvas, plotted, width, height)

    def panel_values(
        self, plotted: list[dict[str, object]], choice: str, panel_name: str
    ) -> list[float]:
        if choice == DETAILED_PLOT_CHOICE:
            return [
                value
                for dataset in plotted
                for component in self.visible_torque_components()
                for value in dataset["series"].get(f"{panel_name} {component}", [])  # type: ignore[union-attr]
            ]
        return [
            value
            for dataset in plotted
            for value in dataset["series"].get(panel_name, [])  # type: ignore[union-attr]
        ]

    def value_bounds(
        self, values: list[float], choice: str, panel_name: str | None
    ) -> tuple[float, float]:
        all_values = [value for value in values if isfinite(value)]
        if panel_name is not None:
            all_values.extend(
                value
                for value in self.limit_values_for_plot(choice, panel_name)
                if isfinite(value)
            )
        if choice == "couples normalises":
            all_values.append(100.0)
        if not all_values:
            return (-1.0, 1.0)
        ymin = min(all_values)
        ymax = max(all_values)
        if abs(ymax - ymin) < 1e-9:
            ymin -= 1.0
            ymax += 1.0
        margin = 0.05 * (ymax - ymin)
        return ymin - margin, ymax + margin

    def limit_values_for_plot(self, choice: str, panel_name: str) -> list[float]:
        if (
            choice not in ("couples articulaires", DETAILED_PLOT_CHOICE)
            or not self.show_torque_bounds_var.get()
        ):
            return []
        if panel_name not in self.show_vars or not self.show_vars[panel_name].get():
            return []
        values = self.torque_bound_series().get(panel_name, [])
        return values + [-value for value in values]

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
        self._plot_hit_regions.append((x0, x1, y1, y0, tmin, tmax))
        canvas.create_line(x0, y0, x1, y0, fill="#69746e")
        canvas.create_line(x0, y0, x0, y1, fill="#69746e")
        self.draw_y_ticks(canvas, x0, y0, y1, ymin, ymax, x1)
        if show_x_axis:
            self.draw_x_ticks(canvas, x0, x1, y0, tmin, tmax)
        self.draw_time_markers(canvas, x0, x1, y0, y1, tmin, tmax)
        canvas.create_text(
            x0 + 4,
            y1 - 14,
            text=f"{title} ({unit})",
            anchor="w",
            fill="#22312a",
            font=("Helvetica", 10, "bold"),
        )
        if show_x_axis:
            xlabel = time_axis_label(self.time_mode())
            canvas.create_text(
                x1 - 44,
                y0 + 24,
                text=xlabel,
                anchor="e",
                fill="#506158",
                font=("Helvetica", 9),
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
        multi_condition = len(plotted) > 1
        for dataset in plotted:
            values = dataset["series"].get(panel_name, [])  # type: ignore[union-attr]
            color = (
                str(dataset["color"])
                if multi_condition
                else JOINT_COLORS.get(panel_name, "#2e7d54")
            )
            self.draw_series_line(canvas, values, x0, x1, y0, y1, ymin, ymax, color, width=2, times=dataset["times"], tmin=tmin, tmax=tmax)  # type: ignore[arg-type]

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
        if choice == "couples normalises":
            self.draw_normalized_torque_limit(canvas, x0, x1, y0, y1, ymin, ymax)
        if choice == "force reaction sol" and panel_name == "vertical":
            self.draw_body_weight_line(canvas, plotted, x0, x1, y0, y1, ymin, ymax)
        if choice in ("couples articulaires", DETAILED_PLOT_CHOICE):
            self.draw_torque_bound_for_joint(
                canvas, panel_name, x0, x1, y0, y1, ymin, ymax, tmin=tmin, tmax=tmax
            )

    def draw_condition_legend(
        self,
        canvas: tk.Canvas,
        plotted: list[dict[str, object]],
        width: int,
        height: int,
    ) -> None:
        if len(plotted) <= 1:
            return
        legend_x = 62
        y = height - 14
        for dataset in plotted:
            color = str(dataset["color"])
            label = str(dataset["label"])
            canvas.create_line(legend_x, y, legend_x + 18, y, fill=color, width=3)
            canvas.create_text(legend_x + 24, y, text=label, anchor="w", fill="#22312a")
            legend_x += max(86, 9 * len(label))

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
        grid_right = grid_right if grid_right is not None else canvas.winfo_width() - 18
        for index in range(5):
            fraction = index / 4
            value = ymin + fraction * (ymax - ymin)
            y = y0 - (y0 - y1) * fraction
            canvas.create_line(x0 - 4, y, x0, y, fill="#69746e")
            canvas.create_line(x0, y, grid_right, y, fill="#edf0ec")
            canvas.create_text(
                x0 - 8,
                y,
                text=self.format_axis_value(value),
                anchor="e",
                fill="#506158",
                font=("Helvetica", 9),
            )

    def draw_x_ticks(
        self,
        canvas: tk.Canvas,
        x0: float,
        x1: float,
        y0: float,
        tmin: float,
        tmax: float,
    ) -> None:
        for index in range(5):
            fraction = index / 4
            x = x0 + (x1 - x0) * fraction
            value = tmin + (tmax - tmin) * fraction
            canvas.create_line(x, y0, x, y0 + 4, fill="#69746e")
            canvas.create_text(
                x,
                y0 + 16,
                text=self.format_axis_value(value),
                anchor="n",
                fill="#506158",
                font=("Helvetica", 9),
            )

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
        if (
            self.show_phase_limits_var.get()
            and self.time_mode() is TimeMode.CENTERED
            and tmin <= 0.0 <= tmax
        ):
            squat_x = self.x_from_time(0.0, x0, x1, tmin, tmax)
            canvas.create_line(
                squat_x, y0, squat_x, y1, fill="#59645e", width=1, dash=(6, 5)
            )

        current_time = min(tmax, max(tmin, self.current_plot_time()))
        animation_x = self.x_from_time(current_time, x0, x1, tmin, tmax)
        canvas.create_line(animation_x, y0, animation_x, y1, fill="#c9332c", width=2)

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
        if not self.show_phase_limits_var.get() and not self.show_phase_names_var.get():
            return
        for dataset_index, dataset in enumerate(plotted):
            durations = dataset.get("durations")
            if not isinstance(durations, PhaseDurations):
                continue
            windows = phase_windows(
                durations,
                mode=self.time_mode(),
            )
            color = str(dataset.get("color") or "#6d5ea8")
            if self.show_phase_limits_var.get():
                for boundary in (windows[0].end, windows[1].end):
                    if not tmin <= boundary <= tmax:
                        continue
                    x = self.x_from_time(boundary, x0, x1, tmin, tmax)
                    canvas.create_line(
                        x,
                        y0,
                        x,
                        y1,
                        fill=color,
                        width=1,
                        dash=(3, 3),
                    )
            if self.show_phase_names_var.get():
                for window in windows:
                    start = max(tmin, window.start)
                    end = min(tmax, window.end)
                    if end - start <= 1e-9:
                        continue
                    x = self.x_from_time((start + end) / 2.0, x0, x1, tmin, tmax)
                    label = window.name
                    if len(plotted) > 1:
                        label = f"{dataset['label']}: {label}"
                    canvas.create_text(
                        x,
                        y1 + 3 + 10 * dataset_index,
                        text=label,
                        anchor="n",
                        fill=color,
                        font=("Helvetica", 7, "bold"),
                    )

    def on_plot_cursor_event(self, event: tk.Event) -> None:
        if self.reveal_mode() is RevealMode.OBSERVATION or not self._plot_hit_regions:
            return
        candidates = [
            region
            for region in self._plot_hit_regions
            if region[0] <= event.x <= region[1] and region[2] <= event.y <= region[3]
        ]
        region = candidates[0] if candidates else self._plot_hit_regions[0]
        x0, x1, _y1, _y0, tmin, tmax = region
        fraction = min(1.0, max(0.0, (event.x - x0) / max(1e-9, x1 - x0)))
        selected_time = tmin + fraction * (tmax - tmin)
        frame_fraction = (selected_time - tmin) / max(1e-9, tmax - tmin)
        self.frame_var.set(round(frame_fraction * (self.frame_count - 1)))
        self.redraw()

    def format_axis_value(self, value: float) -> str:
        abs_value = abs(value)
        if abs_value >= 100:
            return f"{value:.0f}"
        if abs_value >= 10:
            return f"{value:.1f}"
        if abs_value >= 1:
            return f"{value:.2f}"
        return f"{value:.3f}".rstrip("0").rstrip(".")

    def plot_unit(self, choice: str) -> str:
        if choice == "cinematique articulaire":
            return {"position": "deg", "vitesse": "deg/s", "acceleration": "deg/s2"}[
                self.quantity_var.get()
            ]
        if choice == "centre de masse":
            return {"position": "m", "vitesse": "m/s", "acceleration": "m/s2"}[
                self.quantity_var.get()
            ]
        if choice == "force reaction sol":
            return "N"
        if choice in ("couples articulaires", "couples detailles"):
            return "Nm"
        if choice == "couples normalises":
            return "% max"
        return "W"

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
        if (
            self.plot_choice.get() not in ("couples articulaires", "couples detailles")
            or not self.show_torque_bounds_var.get()
        ):
            return
        if tmin is None or tmax is None:
            tmin, tmax = self.plot_time_bounds([{"times": self.plot_times()}])
        for joint, values in self.torque_bound_series().items():
            self.draw_torque_bound_for_joint(
                canvas, joint, x0, x1, y0, y1, ymin, ymax, values, tmin=tmin, tmax=tmax
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
        if (
            joint not in self.show_vars
            or not self.show_vars[joint].get()
            or not self.show_torque_bounds_var.get()
        ):
            return
        values = values or self.torque_bound_series().get(joint, [])
        if tmin is None or tmax is None:
            tmin, tmax = self.plot_time_bounds([{"times": self.plot_times()}])
        times = self.plot_times()
        color = JOINT_COLORS[joint]
        for sign in (1.0, -1.0):
            points = []
            for index, value in enumerate(values):
                x = (
                    self.x_from_time(times[index], x0, x1, tmin, tmax)
                    if index < len(times)
                    else x0
                )
                y = y0 - (y0 - y1) * (sign * value - ymin) / (ymax - ymin)
                points.extend([x, y])
            if len(points) >= 4:
                canvas.create_line(*points, fill=color, width=1, dash=(6, 5))

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
        if self.plot_choice.get() != "couples normalises":
            return
        y = y0 - (y0 - y1) * (100.0 - ymin) / (ymax - ymin)
        canvas.create_line(x0, y, x1, y, fill="#c9332c", width=1, dash=(6, 5))
        canvas.create_text(
            x1 - 4,
            y - 4,
            text="100%",
            anchor="se",
            fill="#8a1f17",
            font=("Helvetica", 9, "bold"),
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
        weights = []
        for dataset in plotted:
            anthro = dataset["anthro"]  # type: ignore[assignment]
            weight = float(anthro.total_mass * GRAVITY)
            if all(abs(weight - existing) > 1e-6 for existing in weights):
                weights.append(weight)
        for weight in weights:
            if not ymin <= weight <= ymax:
                continue
            y = y0 - (y0 - y1) * (weight - ymin) / (ymax - ymin)
            canvas.create_line(x0, y, x1, y, fill="#59645e", width=1, dash=(6, 5))
            canvas.create_text(
                x1 - 4,
                y - 4,
                text=f"m·g {weight:.0f} N",
                anchor="se",
                fill="#59645e",
                font=("Helvetica", 9),
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
        legend_x = x0
        component_styles = self.torque_component_styles()
        for joint in ("cheville", "genou", "hanche"):
            if joint not in self.show_vars or not self.show_vars[joint].get():
                continue
            color = JOINT_COLORS[joint]
            for component in self.visible_torque_components():
                width, dash, marker = component_styles[component]
                values = series.get(f"{joint} {component}", [])
                component_color = self.component_color(color, component)
                self.draw_series_line(
                    canvas,
                    values,
                    x0,
                    x1,
                    y0,
                    y1,
                    ymin,
                    ymax,
                    component_color,
                    width=width,
                    dash=dash,
                )
                if marker == "triangle":
                    self.draw_triangle_markers(
                        canvas, values, x0, x1, y0, y1, ymin, ymax, component_color
                    )
            canvas.create_line(
                legend_x,
                canvas.winfo_height() - 14,
                legend_x + 18,
                canvas.winfo_height() - 14,
                fill=color,
                width=3,
            )
            canvas.create_text(
                legend_x + 24,
                canvas.winfo_height() - 14,
                text=joint,
                anchor="w",
                fill="#22312a",
            )
            legend_x += 95
        self.draw_detailed_component_legend(canvas, x1 - 270, y1 + 4)

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
        multi_condition = len(plotted) > 1
        component_styles = self.torque_component_styles()
        for dataset in plotted:
            color = str(dataset["color"]) if multi_condition else JOINT_COLORS[joint]
            series = dataset["series"]  # type: ignore[assignment]
            times = dataset["times"]  # type: ignore[assignment]
            for component in self.visible_torque_components():
                width, dash, marker = component_styles[component]
                values = series.get(f"{joint} {component}", [])
                component_color = self.component_color(color, component)
                self.draw_series_line(
                    canvas,
                    values,
                    x0,
                    x1,
                    y0,
                    y1,
                    ymin,
                    ymax,
                    component_color,
                    width=width,
                    dash=dash,
                    times=times,
                    tmin=tmin,
                    tmax=tmax,
                )
                if marker == "triangle":
                    self.draw_triangle_markers(
                        canvas,
                        values,
                        x0,
                        x1,
                        y0,
                        y1,
                        ymin,
                        ymax,
                        component_color,
                        times=times,
                        tmin=tmin,
                        tmax=tmax,
                    )

    def draw_detailed_component_legend(
        self,
        canvas: tk.Canvas,
        x: float,
        y: float,
        *,
        horizontal: bool = False,
    ) -> None:
        styles = self.torque_component_styles()
        cursor_x = x
        for index, label in enumerate(self.visible_torque_components()):
            width, dash, marker = styles[label]
            xx = cursor_x if horizontal else x
            yy = y if horizontal else y + 16 * index
            canvas.create_line(
                xx,
                yy,
                xx + 28,
                yy,
                fill="#334139",
                width=width,
                dash=dash,
            )
            if marker == "triangle":
                canvas.create_polygon(
                    xx + 14,
                    yy - 4,
                    xx + 10,
                    yy + 4,
                    xx + 18,
                    yy + 4,
                    fill="#334139",
                    outline="#334139",
                )
            canvas.create_text(
                xx + 34,
                yy,
                text=label,
                anchor="w",
                fill="#334139",
                font=("Helvetica", 9),
            )
            if horizontal:
                cursor_x += 70 + 6.4 * len(label)

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
        points: list[float] = []
        for index, value in enumerate(values):
            if not isfinite(value):
                if len(points) >= 4:
                    canvas.create_line(*points, fill=color, width=width, dash=dash)
                points = []
                continue
            if (
                times is not None
                and tmin is not None
                and tmax is not None
                and index < len(times)
            ):
                x = self.x_from_time(times[index], x0, x1, tmin, tmax)
            else:
                x = x0 + (x1 - x0) * index / max(1, len(values) - 1)
            y = y0 - (y0 - y1) * (value - ymin) / (ymax - ymin)
            points.extend([x, y])
        if len(points) >= 4:
            canvas.create_line(*points, fill=color, width=width, dash=dash)

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
        step = max(1, len(values) // 18)
        for index, value in enumerate(values):
            if index % step != 0 and index != len(values) - 1:
                continue
            if (
                times is not None
                and tmin is not None
                and tmax is not None
                and index < len(times)
            ):
                x = self.x_from_time(times[index], x0, x1, tmin, tmax)
            else:
                x = x0 + (x1 - x0) * index / max(1, len(values) - 1)
            y = y0 - (y0 - y1) * (value - ymin) / (ymax - ymin)
            canvas.create_polygon(
                x, y - 5, x - 5, y + 5, x + 5, y + 5, fill=color, outline=color
            )

    def plot_series(self, choice: str) -> dict[str, list[float]]:
        return self.plot_series_for(choice, self.states, self.results)

    def plot_series_for(
        self,
        choice: str,
        states: list[MotionState],
        results: list[DynamicsResult],
    ) -> dict[str, list[float]]:
        selected = [name for name, var in self.show_vars.items() if var.get()]
        data: dict[str, list[float]] = {}
        if choice == "cinematique articulaire":
            values = self.joint_kinematic_series(states)
        elif choice == "centre de masse":
            return self.com_plot_series(results)
        elif choice == "force reaction sol":
            return self.ground_reaction_plot_series(results)
        elif choice == "couples articulaires":
            values = {
                joint: [result.torques[joint] for result in results]
                for joint in ("cheville", "genou", "hanche")
            }
        elif choice == "couples normalises":
            values = {
                joint: [
                    (
                        float("nan")
                        if result.effort_ratios[joint] is None
                        else 100.0 * result.effort_ratios[joint]
                    )
                    for result in results
                ]
                for joint in ("cheville", "genou", "hanche")
            }
        elif choice == "couples detailles":
            values = {}
            for joint in ("cheville", "genou", "hanche"):
                if joint in selected:
                    for label in self.visible_torque_components():
                        key = TORQUE_COMPONENT_KEYS[label]
                        values[f"{joint} {label}"] = [
                            result.torque_components[joint][key] for result in results
                        ]
            return values
        else:
            values = {
                joint: [result.powers[joint] for result in results]
                for joint in ("cheville", "genou", "hanche")
            }
        for name in selected:
            if name in values:
                data[name] = values[name]
        return data

    def joint_kinematic_series(
        self, states: list[MotionState] | None = None
    ) -> dict[str, list[float]]:
        states = states or self.states
        return self.joint_kinematic_series_for_quantity(states, self.quantity_var.get())

    def joint_kinematic_series_for_quantity(
        self,
        states: list[MotionState],
        quantity: str,
    ) -> dict[str, list[float]]:
        attribute = {"position": "q", "vitesse": "qdot", "acceleration": "qddot"}[
            quantity
        ]
        series = {joint: [] for joint in ("cheville", "genou", "hanche")}
        for state in states:
            values = joint_values_from_segment_values(getattr(state, attribute))
            for joint, value in values.items():
                series[joint].append(degrees(value))
        return series

    def com_plot_series(
        self, results: list[DynamicsResult] | None = None
    ) -> dict[str, list[float]]:
        results = results or self.results
        return self.com_plot_series_for_quantity(results, self.quantity_var.get())

    def com_plot_series_for_quantity(
        self,
        results: list[DynamicsResult],
        quantity: str,
    ) -> dict[str, list[float]]:
        source = {
            "position": [result.com for result in results],
            "vitesse": [result.com_velocity for result in results],
            "acceleration": [result.com_acceleration for result in results],
        }[quantity]
        return self.horizontal_vertical_series(source)

    def ground_reaction_plot_series(
        self, results: list[DynamicsResult] | None = None
    ) -> dict[str, list[float]]:
        results = results or self.results
        return self.horizontal_vertical_series(
            [result.ground_reaction for result in results]
        )

    def horizontal_vertical_series(
        self, source: list[tuple[float, float]]
    ) -> dict[str, list[float]]:
        data: dict[str, list[float]] = {}
        if self.com_component_vars["horizontal"].get():
            data["horizontal"] = [value[0] for value in source]
        if self.com_component_vars["vertical"].get():
            data["vertical"] = [value[1] for value in source]
        return data

    def torque_bound_series(self) -> dict[str, list[float]]:
        return {
            joint: [
                result.torque_capacities[joint].available_torque_Nm
                for result in self.results
            ]
            for joint in ("cheville", "genou", "hanche")
        }

    def nearest_handle(self, x: float, y: float) -> str | None:
        anthro = self.anthro()
        pose = pose_from_angles(anthro, self.final_q)
        bounds = getattr(self, "_pose_editor_bounds", None) or self.scene_bounds()
        candidates = {"knee": pose.knee, "hip": pose.hip, "shoulder": pose.shoulder}
        for name, point in candidates.items():
            px, py = self.world_to_canvas(self.pose_canvas, point, bounds)
            if (px - x) ** 2 + (py - y) ** 2 < 20**2:
                return name
        return None

    def nearest_joint_angle(self, x: float, y: float) -> str | None:
        """Return the clinical joint selected for a precise right-click edit."""
        pose = pose_from_angles(self.anthro(), self.final_q)
        bounds = getattr(self, "_pose_editor_bounds", None) or self.scene_bounds()
        candidates = {
            "cheville": pose.ankle,
            "genou": pose.knee,
            "hanche": pose.hip,
        }
        for joint, point in candidates.items():
            px, py = self.world_to_canvas(self.pose_canvas, point, bounds)
            if (px - x) ** 2 + (py - y) ** 2 < 20**2:
                return joint
        return None

    def on_pose_context_menu(self, event: tk.Event) -> str | None:
        joint = self.nearest_joint_angle(event.x, event.y)
        if joint is None:
            return None
        self.open_pose_angle_editor(joint)
        return "break"

    def on_pose_press(self, event: tk.Event) -> None:
        self._pose_drag_bounds = (
            getattr(self, "_pose_editor_bounds", None) or self.scene_bounds()
        )
        self.drag_target = self.nearest_handle(event.x, event.y)

    def on_pose_drag(self, event: tk.Event) -> None:
        if not self.drag_target:
            return
        anthro = self.anthro()
        pose = pose_from_angles(anthro, self.final_q)
        point = self.canvas_to_world(
            self.pose_canvas,
            event.x,
            event.y,
            self._pose_drag_bounds
            or getattr(self, "_pose_editor_bounds", None)
            or self.scene_bounds(),
        )
        shank, thigh, trunk = self.final_q
        if self.drag_target == "knee":
            dx = point[0] - pose.ankle[0]
            dy = point[1] - pose.ankle[1]
            shank = atan2(dx, dy)
        elif self.drag_target == "hip":
            dx = point[0] - pose.knee[0]
            dy = point[1] - pose.knee[1]
            thigh = atan2(dx, dy)
        elif self.drag_target == "shoulder":
            dx = point[0] - pose.hip[0]
            dy = point[1] - pose.hip[1]
            trunk = atan2(dx, dy)
        self.final_q = self.clamp_final_q((shank, thigh, trunk))
        self.sync_pose_angle_fields_from_final_q()
        self.on_parameter_changed()

    @staticmethod
    def format_pose_angle(value: float) -> str:
        """Format a precise degree value without insignificant zeroes."""
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def sync_pose_angle_fields_from_final_q(self) -> None:
        """Refresh the visible editor after a drag without committing input."""
        joint = getattr(self, "_active_pose_angle_joint", None)
        if joint is not None and hasattr(self, "pose_angle_value_var"):
            values = clinical_joint_values_from_segment_values(self.final_q)
            self.pose_angle_value_var.set(
                self.format_pose_angle(degrees(values[joint]))
            )

    def open_pose_angle_editor(self, joint: str) -> None:
        """Show one non-modal editor above the GUI for ``joint``.

        Selecting a new articulation always replaces the pending value.  No
        posture is changed until the user explicitly validates this editor.
        """
        values = clinical_joint_values_from_segment_values(self.final_q)
        lower, upper = CLINICAL_JOINT_LIMITS_DEG[joint]
        labels = {
            "cheville": "Cheville (dorsiflexion)",
            "genou": "Genou (flexion)",
            "hanche": "Hanche (flexion)",
        }
        self._active_pose_angle_joint = joint
        self.pose_angle_joint_var.set(
            f"{labels[joint]} — {lower:g} à {upper:g} deg"
        )
        self.pose_angle_value_var.set(
            self.format_pose_angle(degrees(values[joint]))
        )
        self.pose_angle_feedback_var.set("")
        self.pose_angle_dialog.title(f"Angle — {labels[joint]}")
        self.pose_angle_dialog.deiconify()
        self.pose_angle_dialog.lift(self)
        self.pose_angle_dialog.update_idletasks()
        x = self.pose_canvas.winfo_rootx() + 16
        y = self.pose_canvas.winfo_rooty() + 72
        self.pose_angle_dialog.geometry(f"+{x}+{y}")

        def focus_editor() -> None:
            if (
                self._active_pose_angle_joint == joint
                and self.pose_angle_dialog.winfo_viewable()
            ):
                self.pose_angle_dialog.focus_force()
                self.pose_angle_entry.focus_force()
                self.pose_angle_entry.selection_range(0, tk.END)

        self.after_idle(focus_editor)

    def confirm_pose_angle_editor(
        self, _event: tk.Event | None = None
    ) -> str | None:
        """Commit the currently selected joint only on Valider or Enter."""
        joint = self._active_pose_angle_joint
        if joint is None:
            return "break"
        if self.apply_clinical_joint_angle(joint, self.pose_angle_value_var.get()):
            self.close_pose_angle_editor()
            return "break"
        self.pose_angle_feedback_var.set(self.status_var.get())
        self.pose_angle_entry.focus_set()
        self.pose_angle_entry.selection_range(0, tk.END)
        return "break"

    def close_pose_angle_editor(self) -> None:
        """Discard the pending value and hide the angle window."""
        self._active_pose_angle_joint = None
        self.pose_angle_feedback_var.set("")
        self.pose_angle_dialog.withdraw()

    # Compatibility entry point for callers that use the former dialog name.
    def open_pose_angle_dialog(self, joint: str) -> None:
        self.open_pose_angle_editor(joint)

    def close_pose_angle_dialog(self, _dialog: tk.Misc | None = None) -> None:
        """Compatibility entry point for the non-modal angle window."""
        self.close_pose_angle_editor()

    def apply_clinical_joint_angle(self, joint: str, raw_value: str) -> bool:
        """Validate and commit one angle only after an explicit dialog action."""
        try:
            value = float(raw_value.strip().replace(",", "."))
        except (AttributeError, TypeError, ValueError):
            self.status_var.set(
                f"angle invalide ({joint}) : entrez une valeur numérique en degrés"
            )
            return False
        if not isfinite(value):
            self.status_var.set(
                f"angle invalide ({joint}) : entrez une valeur numérique en degrés"
            )
            return False

        lower, upper = CLINICAL_JOINT_LIMITS_DEG[joint]
        bounded = max(lower, min(upper, value))
        values = clinical_joint_values_from_segment_values(self.final_q)
        values[joint] = radians(bounded)
        self.final_q = self.clamp_final_q(
            segment_values_from_clinical_joint_values(
                values["cheville"], values["genou"], values["hanche"]
            )
        )
        self.on_parameter_changed()
        if bounded != value:
            self.status_var.set(
                "limite anatomique appliquée : "
                f"{joint} {self.format_pose_angle(bounded)}°"
            )
        return True

    def clamp_final_q(
        self, q: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        ankle = max(radians(-30.0), min(radians(40.0), q[0]))
        knee = max(radians(-140.0), min(radians(0.0), q[1] - ankle))
        thigh = ankle + knee
        hip = max(radians(-15.0), min(radians(120.0), q[2] - thigh))
        return (ankle, thigh, thigh + hip)

    def project_on_force_line(
        self,
        joint: tuple[float, float],
        force_origin: tuple[float, float],
        force_vector: tuple[float, float],
    ) -> tuple[float, float]:
        norm_squared = force_vector[0] ** 2 + force_vector[1] ** 2
        if norm_squared < 1e-12:
            return force_origin
        relative = (joint[0] - force_origin[0], joint[1] - force_origin[1])
        factor = (
            relative[0] * force_vector[0] + relative[1] * force_vector[1]
        ) / norm_squared
        return (
            force_origin[0] + factor * force_vector[0],
            force_origin[1] + factor * force_vector[1],
        )

    def on_pose_release(self, _event: tk.Event) -> None:
        self.drag_target = None
        self._pose_drag_bounds = None

    def toggle_play(self) -> None:
        self.playing = not self.playing
        self.play_button.configure(text="⏸" if self.playing else "▶")
        if self.playing:
            self._play_started_at = perf_counter()
            self._play_start_time_s = self.frame_var.get() * DEFAULT_SAMPLE_PERIOD_S
            self.step_animation()
        else:
            self._play_started_at = None

    def step_animation(self) -> None:
        if not self.playing:
            return
        duration_s = max(
            DEFAULT_SAMPLE_PERIOD_S,
            (self.frame_count - 1) * DEFAULT_SAMPLE_PERIOD_S,
        )
        started_at = (
            self._play_started_at
            if self._play_started_at is not None
            else perf_counter()
        )
        elapsed_s = perf_counter() - started_at
        target_time_s = (self._play_start_time_s + elapsed_s) % duration_s
        self.frame_var.set(round(target_time_s / DEFAULT_SAMPLE_PERIOD_S))
        self.redraw()
        self.after(round(1000 * DEFAULT_SAMPLE_PERIOD_S), self.step_animation)

    def record_condition(self) -> None:
        comparison_reference = None
        if self._comparison_reference_iid in self.saved_conditions:
            reference = self.saved_conditions[self._comparison_reference_iid]
            comparison_reference = {
                "label": reference["label"],
                "settings": deepcopy(reference["settings"]),
                "final_q_deg": list(reference["final_q_deg"]),
            }
        condition_iid = self.add_saved_condition(
            self.current_settings(),
            [degrees(value) for value in self.final_q],
            states=list(self.states),
            results=list(self.results),
            comparison_reference=comparison_reference,
        )
        summary = str(self.saved_conditions[condition_iid]["difference_summary"])
        self.status_var.set(
            f"condition {self.saved_condition_count} enregistrée · {summary}"
        )
        self._comparison_reference_iid = None
        if self.didactic_mode_var.get() and self.didactic_step < 9:
            self.didactic_step = 9
            self.set_reveal_mode(reveal_mode_for_step(self.didactic_step))
            self.update_didactic_guide()

    def clear_conditions(self) -> None:
        self.saved_conditions.clear()
        self.saved_condition_count = 0
        self._comparison_reference_iid = None
        for iid in self.conditions_table.get_children():
            self.conditions_table.delete(iid)
        self.update_condition_differences()

    def duplicate_selected_condition(self) -> None:
        selected = [
            iid
            for iid in self.conditions_table.selection()
            if iid in self.saved_conditions
        ]
        if len(selected) != 1:
            return
        reference_iid = selected[0]
        reference = self.saved_conditions[reference_iid]
        settings = deepcopy(reference["settings"])
        settings["final_q_deg"] = list(reference["final_q_deg"])
        self._comparison_reference_iid = reference_iid
        self.apply_settings(settings)
        self.conditions_table.selection_remove(reference_iid)
        self.update_condition_buttons()
        self.table_notebook.select(self.differences_tab)
        self.on_table_tab_changed()
        self.update_condition_differences()
        self.status_var.set(
            f"condition {reference['label']} dupliquée vers l'éditeur · "
            "modifiez un paramètre puis cliquez sur Ajouter"
        )

    def add_saved_condition(
        self,
        settings: dict[str, object],
        final_q_deg: list[float],
        label: str | None = None,
        iid: str | None = None,
        states: list[MotionState] | None = None,
        results: list[DynamicsResult] | None = None,
        comparison_reference: dict[str, object] | None = None,
    ) -> str:
        self.saved_condition_count += 1
        condition_iid = iid or f"condition-{self.saved_condition_count}"
        if condition_iid in self.saved_conditions:
            condition_iid = f"condition-{self.saved_condition_count}"
        if not final_q_deg:
            final_q_deg = [degrees(value) for value in self.final_q]
        condition_label = label or str(self.saved_condition_count)
        if states is None or results is None:
            states, results = self.simulate_from_condition(settings, final_q_deg)
        peak_torques = {
            joint: max(abs(result.torques[joint]) for result in results)
            for joint in ("cheville", "genou", "hanche")
        }
        utilization_events = [
            (result.effort_ratios[joint], index, joint)
            for index, result in enumerate(results)
            for joint in ("cheville", "genou", "hanche")
        ]
        undefined_events = [event for event in utilization_events if event[0] is None]
        if undefined_events:
            limiting_ratio, limiting_index, limiting_joint = undefined_events[0]
            utilization_label = "n.d."
            exceeds_label = "oui"
        else:
            limiting_ratio, limiting_index, limiting_joint = max(
                utilization_events, key=lambda event: float(event[0] or 0.0)
            )
            utilization_label = f"{100.0 * float(limiting_ratio or 0.0):.0f}%"
            exceeds_label = "oui" if float(limiting_ratio or 0.0) > 1.0 else "non"
        limiting_state = states[limiting_index]
        limiting_label = (
            f"{limiting_joint} · {limiting_state.time:.2f}s · "
            f"{limiting_state.phase} · {exceeds_label}"
        )
        squat_angles = self.display_joint_angles(
            tuple(radians(value) for value in final_q_deg)
        )
        differences = ()
        if comparison_reference is not None:
            differences = parameter_differences(
                dict(comparison_reference.get("settings", {})),
                list(comparison_reference.get("final_q_deg", [])),
                settings,
                final_q_deg,
            )
        summary = (
            difference_summary(differences)
            if comparison_reference is not None
            else "référence indépendante"
        )
        self.saved_conditions[condition_iid] = {
            "label": condition_label,
            "settings": settings,
            "final_q_deg": final_q_deg,
            "states": states,
            "results": results,
            "comparison_reference": comparison_reference,
            "difference_summary": summary,
        }
        self.conditions_table.insert(
            "",
            "end",
            iid=condition_iid,
            values=(
                condition_label,
                str(settings.get("subject_profile", "homme")),
                str(settings.get("bar_position", "back")),
                f"{squat_angles[0]:.0f}/{squat_angles[1]:.0f}/{squat_angles[2]:.0f}",
                f"{float(settings.get('load_percent_bw', 100.0 * float(settings.get('load_kg', 0.0)) / 70.0)):.0f}",
                (
                    f"{float(settings.get('duration_excentrique_s', settings.get('duration_phase_s', 4.0))):.1f}/"
                    f"{float(settings.get('duration_isometrique_s', 2.0)):.1f}/"
                    f"{float(settings.get('duration_concentrique_s', settings.get('duration_phase_s', 4.0))):.1f}"
                ),
                "20" if bool(settings.get("wedge_20_deg", False)) else "0",
                f"{float(settings.get('shank_percent', 0.0)):+.1f}",
                f"{float(settings.get('thigh_percent', 0.0)):+.1f}",
                f"{float(settings.get('trunk_percent', 0.0)):+.1f}",
                f"{peak_torques['cheville']:.1f}",
                f"{peak_torques['genou']:.1f}",
                f"{peak_torques['hanche']:.1f}",
                utilization_label,
                limiting_label,
                summary,
            ),
        )
        return condition_iid

    def delete_selected_conditions(self) -> None:
        selected = list(self.conditions_table.selection())
        if not selected:
            return
        answer = messagebox.askyesno(
            "Supprimer",
            f"Supprimer {len(selected)} condition(s) selectionnee(s) ?",
            parent=self,
        )
        if not answer:
            return
        for iid in selected:
            self.saved_conditions.pop(iid, None)
            if self.conditions_table.exists(iid):
                self.conditions_table.delete(iid)
            if iid == self._comparison_reference_iid:
                self._comparison_reference_iid = None
        self.on_table_selection_changed()
        self.status_var.set(f"{len(selected)} condition(s) supprimee(s)")

    def simulate_from_condition(
        self,
        settings: dict[str, object],
        final_q_deg: list[float],
    ) -> tuple[list[MotionState], list[DynamicsResult]]:
        anthro = self.anthro_from_settings(settings)
        final_q = self.clamp_final_q(
            tuple(radians(value) for value in self.normalized_final_q_deg(final_q_deg))
        )
        max_torques = {
            joint: float(
                dict(settings.get("max_torques", {})).get(
                    joint, self.max_torque_vars[joint].get()
                )
            )
            for joint in ("cheville", "genou", "hanche")
        }
        durations = self.phase_durations_from_settings(settings)
        baseline = simulate(
            anthro,
            final_q,
            durations,
            frame_count_for_duration(durations),
            max_torques,
            bool(settings.get("angle_adapt", self.angle_adapt_var.get())),
            self.model_cache,
            bool(settings.get("velocity_adapt", self.velocity_adapt_var.get())),
        )
        if not bool(settings.get("optimize_bar_path_experimental", False)):
            return baseline
        optimization = optimize_deep_squat_bar_path(
            anthro,
            final_q,
            durations,
            frame_count_for_duration(durations),
            max_torques,
            bool(settings.get("angle_adapt", self.angle_adapt_var.get())),
            self.model_cache,
            bool(settings.get("velocity_adapt", self.velocity_adapt_var.get())),
            baseline=baseline,
        )
        return optimization.states, optimization.dynamics

    def display_joint_angles(
        self, q: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        values = clinical_joint_values_from_segment_values(q)
        return tuple(
            degrees(values[joint]) for joint in ("cheville", "genou", "hanche")
        )


def main() -> None:
    app = SquatGui()
    app.mainloop()
