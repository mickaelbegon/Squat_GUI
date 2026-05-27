"""Tkinter GUI for the 2D squat model."""

from __future__ import annotations

import os

os.environ.setdefault("LANG", "en_US.UTF-8")
os.environ.setdefault("LC_ALL", "en_US.UTF-8")

import json
import tkinter as tk
from math import atan2, degrees, radians
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .anthropometry import BAR_POSITIONS, SUBJECT_PROFILES, Anthropometry, scale_from_percent
from .backend import BiorbdModelCache, detect_optional_backends
from .dynamics import DynamicsResult, available_joint_torque_limits, simulate, torque_presets
from .kinematics import MotionState, PhaseDurations, pose_from_angles
from .raster_segments import draw_sprite_segment
from .segment_shapes import draw_segment, load_segments


DETAILED_PLOT_CHOICE = "couples detailles"
PLOT_CHOICES = [
    "cinematique articulaire",
    "centre de masse",
    "force reaction sol",
    "couples articulaires",
    "couples normalises",
    DETAILED_PLOT_CHOICE,
    "puissances articulaires",
]

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


class SquatGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Squat 2D - dynamique inverse")
        self.geometry("1480x920")
        self.configure(bg="#f2f4f1")

        self.final_q = (radians(22.0), radians(-58.0), radians(20.0))
        self.frame_count = 81
        self.playing = False
        self.drag_target: str | None = None
        self._redraw_pending = False
        self._suspend_selection_clear = False
        self.states: list[MotionState] = []
        self.results: list[DynamicsResult] = []
        self.saved_condition_count = 0
        self.saved_conditions: dict[str, dict[str, object]] = {}
        self.model_cache = BiorbdModelCache()

        self.subject_profile_var = tk.StringVar(value="homme")
        self.bar_position_var = tk.StringVar(value="back")
        self.load_var = tk.DoubleVar(value=0.0)
        self.shank_var = tk.DoubleVar(value=0.0)
        self.thigh_var = tk.DoubleVar(value=0.0)
        self.trunk_var = tk.DoubleVar(value=0.0)
        self.eccentric_duration_var = tk.DoubleVar(value=4.0)
        self.isometric_duration_var = tk.DoubleVar(value=2.0)
        self.concentric_duration_var = tk.DoubleVar(value=4.0)
        self.wedge_var = tk.BooleanVar(value=False)
        self.frame_var = tk.IntVar(value=self.frame_count // 2)
        self.plot_choice = tk.StringVar(value=PLOT_CHOICES[0])
        self.quantity_var = tk.StringVar(value="position")
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
        self.quantity_controls: list[tk.Widget] = []
        self.com_controls: list[tk.Widget] = []
        self.torque_preset_var = tk.StringVar(value="Anderson actif x2")
        reference_torques = torque_presets(70.0, 1.70)[self.torque_preset_var.get()].torques
        self.max_torque_vars = {
            "cheville": tk.DoubleVar(value=round(reference_torques["cheville"])),
            "genou": tk.DoubleVar(value=round(reference_torques["genou"])),
            "hanche": tk.DoubleVar(value=round(reference_torques["hanche"])),
        }
        self.show_torque_bounds_var = tk.BooleanVar(value=False)
        self.show_sprite_centers_var = tk.BooleanVar(value=False)
        self.show_segment_com_var = tk.BooleanVar(value=False)
        self.low_quality_sprites_var = tk.BooleanVar(value=False)
        self.angle_adapt_var = tk.BooleanVar(value=True)
        self.subplot_mode_var = tk.BooleanVar(value=True)
        self.normalize_time_var = tk.BooleanVar(value=False)
        self.plot_title_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value=detect_optional_backends().message)
        self.didactic_mode_var = tk.BooleanVar(value=False)
        self.didactic_step = 0

        self._build_layout()
        self.recompute()

    def _build_layout(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f2f4f1")
        style.configure("TLabelframe", background="#f2f4f1")
        style.configure("TLabel", background="#f2f4f1", foreground="#22312a")
        style.configure("TCheckbutton", background="#f2f4f1")
        style.configure("TButton", padding=6)

        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=0, minsize=420)
        root.columnconfigure(1, weight=1)
        root.columnconfigure(2, weight=1)
        root.rowconfigure(0, weight=1, minsize=420)
        root.rowconfigure(2, weight=3, minsize=320)

        left = ttk.Frame(root)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(0, weight=1)
        guide_box = ttk.LabelFrame(left, text="Parcours didactique")
        guide_box.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        guide_box.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            guide_box,
            text="activer",
            variable=self.didactic_mode_var,
            command=self.update_didactic_guide,
        ).grid(row=0, column=0, sticky="w", padx=4, pady=3)
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
        self.didactic_label.tag_configure("sujet", foreground="#16756d", font=("Helvetica", 9, "bold"))
        self.didactic_label.tag_configure("barre", foreground="#b05e16", font=("Helvetica", 9, "bold"))
        self.didactic_label.tag_configure("charge", foreground="#237f9f", font=("Helvetica", 9, "bold"))
        self.didactic_label.tag_configure("phase", foreground="#6d5ea8", font=("Helvetica", 9, "bold"))
        self.didactic_label.tag_configure("pose", foreground="#2e7d54", font=("Helvetica", 9, "bold"))
        self.didactic_label.tag_configure("alerte", foreground="#c9332c", font=("Helvetica", 9, "bold"))
        ttk.Button(guide_box, text="Suivant", command=self.advance_didactic_guide).grid(row=0, column=2, padx=4, pady=3)
        self.update_didactic_guide()

        parameter_box = ttk.LabelFrame(left, text="Parametres")
        parameter_box.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        parameter_box.columnconfigure(0, weight=1)
        parameter_box.columnconfigure(1, weight=1)
        identity = ttk.Frame(parameter_box)
        identity.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=3)
        identity.columnconfigure(0, weight=1)
        identity.columnconfigure(1, weight=1)
        ttk.Label(identity, text="Sujet").grid(row=0, column=0, sticky="w")
        ttk.Label(identity, text="Prise barre").grid(row=0, column=1, sticky="w")
        profile_menu = ttk.Combobox(identity, textvariable=self.subject_profile_var, values=SUBJECT_PROFILES, state="readonly", width=14)
        profile_menu.grid(row=1, column=0, sticky="ew", padx=(0, 3))
        profile_menu.bind("<<ComboboxSelected>>", lambda _event: self.on_parameter_changed())
        bar_menu = ttk.Combobox(identity, textvariable=self.bar_position_var, values=BAR_POSITIONS, state="readonly", width=12)
        bar_menu.grid(row=1, column=1, sticky="ew", padx=(3, 0))
        bar_menu.bind("<<ComboboxSelected>>", lambda _event: self.on_parameter_changed())
        self._add_scale(parameter_box, "Charge %BW (sujet 70 kg)", self.load_var, 0, 100, 10, 1, 2)
        duration_box = ttk.LabelFrame(parameter_box, text="Durees des phases (s)")
        duration_box.grid(row=2, column=0, sticky="ew", padx=(4, 2), pady=3)
        for column, (label, variable) in enumerate(
            (
                ("excent.", self.eccentric_duration_var),
                ("isomet.", self.isometric_duration_var),
                ("concent.", self.concentric_duration_var),
            )
        ):
            duration_box.columnconfigure(column, weight=1)
            ttk.Label(duration_box, text=label).grid(row=0, column=column)
            duration = ttk.Combobox(duration_box, textvariable=variable, values=(0.0, 0.5, 1.0, 1.5, 2.0), state="readonly", width=4)
            duration.grid(row=1, column=column, sticky="ew", padx=2, pady=(0, 3))
            duration.bind("<<ComboboxSelected>>", lambda _event: self.on_parameter_changed())
        lengths = ttk.LabelFrame(parameter_box, text="Longueurs (%)")
        lengths.grid(row=2, column=1, sticky="ew", padx=(2, 4), pady=3)
        for column, (label, variable) in enumerate((("tibia", self.shank_var), ("cuisse", self.thigh_var), ("tronc", self.trunk_var))):
            lengths.columnconfigure(column, weight=1)
            ttk.Label(lengths, text=label).grid(row=0, column=column)
            length_menu = ttk.Combobox(lengths, textvariable=variable, values=(-5.0, -2.5, 0.0, 2.5, 5.0), state="readonly", width=4)
            length_menu.grid(row=1, column=column, sticky="ew", padx=2, pady=(0, 3))
            length_menu.bind("<<ComboboxSelected>>", lambda _event: self.on_parameter_changed())
        options = ttk.Frame(parameter_box)
        options.grid(row=3, column=0, columnspan=2, sticky="ew", padx=4, pady=(3, 4))
        ttk.Checkbutton(options, text="wedge 20 deg", variable=self.wedge_var, command=self.on_parameter_changed).pack(side="left")
        ttk.Checkbutton(options, text="CoM segments + barre", variable=self.show_segment_com_var, command=self.redraw).pack(side="left", padx=(8, 0))

        torque_box = ttk.LabelFrame(left, text="Couples max")
        torque_box.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        for col in range(3):
            torque_box.columnconfigure(col, weight=1)
        for col, joint in enumerate(("cheville", "genou", "hanche")):
            ttk.Label(torque_box, text=joint).grid(row=0, column=col, padx=4)
            entry = ttk.Entry(torque_box, textvariable=self.max_torque_vars[joint], width=7)
            entry.grid(row=1, column=col, sticky="ew", padx=4)
            entry.bind("<FocusOut>", lambda _event: self.on_parameter_changed())
            entry.bind("<Return>", lambda _event: self.on_parameter_changed())
        ttk.OptionMenu(
            torque_box,
            self.torque_preset_var,
            self.torque_preset_var.get(),
            *torque_presets(70.0, 1.70),
            command=lambda _value: self.apply_torque_preset(),
        ).grid(row=2, column=0, columnspan=3, sticky="ew", padx=4, pady=(4, 0))
        ttk.Checkbutton(torque_box, text="max-angle", variable=self.angle_adapt_var, command=self.on_parameter_changed).grid(row=3, column=0, columnspan=2)
        ttk.Checkbutton(torque_box, text="show", variable=self.show_torque_bounds_var, command=self.redraw).grid(row=3, column=2)

        plot_box = ttk.LabelFrame(left, text="Resultats")
        plot_box.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        for col in range(4):
            plot_box.columnconfigure(col, weight=1)
        self.plot_menu = ttk.Combobox(plot_box, textvariable=self.plot_choice, values=PLOT_CHOICES, state="readonly")
        self.plot_menu.grid(row=0, column=0, columnspan=4, sticky="ew", padx=4, pady=(2, 4))
        self.plot_menu.bind("<<ComboboxSelected>>", lambda _event: self.on_plot_choice_changed())
        for index, name in enumerate(self.show_vars):
            checkbutton = ttk.Checkbutton(plot_box, text=name, variable=self.show_vars[name], command=self.redraw)
            checkbutton.grid(row=1, column=index, sticky="w", padx=4)
            self.show_checkbuttons[name] = checkbutton
        quantity_menu = ttk.OptionMenu(plot_box, self.quantity_var, self.quantity_var.get(), "position", "vitesse", "acceleration", command=lambda _value: self.redraw())
        quantity_menu.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(6, 2))
        self.quantity_controls.append(quantity_menu)
        for index, name in enumerate(self.com_component_vars):
            checkbutton = ttk.Checkbutton(plot_box, text=name, variable=self.com_component_vars[name], command=self.redraw)
            checkbutton.grid(row=2, column=index + 2, sticky="w", padx=4, pady=(6, 2))
            self.com_controls.append(checkbutton)
        for control in self.com_controls:
            control.state(["disabled"])
        ttk.Checkbutton(
            plot_box,
            text="3 subplots",
            variable=self.subplot_mode_var,
            command=self.update_plot_choices,
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 2))
        ttk.Checkbutton(
            plot_box,
            text="low quality",
            variable=self.low_quality_sprites_var,
            command=self.redraw,
        ).grid(row=3, column=2, sticky="w", padx=4, pady=(4, 2))
        ttk.Checkbutton(
            plot_box,
            text="temps %",
            variable=self.normalize_time_var,
            command=self.redraw,
        ).grid(row=3, column=3, sticky="w", padx=4, pady=(4, 2))

        table_box = ttk.LabelFrame(root, text="Conditions enregistrees", width=420, height=318)
        table_box.grid(row=2, column=0, sticky="nsew", padx=(0, 8), pady=(8, 0))
        table_box.grid_propagate(False)
        table_box.rowconfigure(1, weight=1)
        table_box.columnconfigure(0, weight=1)
        table_buttons = ttk.Frame(table_box)
        table_buttons.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        table_buttons.columnconfigure(0, weight=1)
        table_buttons.columnconfigure(1, weight=1)
        ttk.Button(table_buttons, text="Ajouter", command=self.record_condition).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self.delete_condition_button = ttk.Button(table_buttons, text="Supprimer", command=self.delete_selected_conditions)
        self.delete_condition_button.grid(row=0, column=1, sticky="ew", padx=(3, 0))
        self.delete_condition_button.state(["disabled"])
        columns = ("numero", "profil", "prise", "squat", "charge", "phases", "wedge", "tibia", "cuisse", "tronc", "cheville", "genou", "hanche")
        self.conditions_table = ttk.Treeview(table_box, columns=columns, show="headings", height=7, selectmode="extended")
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
        }
        for column in columns:
            self.conditions_table.heading(column, text=headings[column])
            self.conditions_table.column(column, width=widths[column], anchor="center", stretch=True)
        self.conditions_table.grid(row=1, column=0, sticky="nsew", padx=4, pady=(4, 0))
        table_scroll = ttk.Scrollbar(table_box, orient="horizontal", command=self.conditions_table.xview)
        table_scroll.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 4))
        self.conditions_table.configure(xscrollcommand=table_scroll.set)
        self.conditions_table.bind("<<TreeviewSelect>>", self.on_table_selection_changed)
        self.conditions_table.bind("<Button-1>", self.on_table_click)
        file_box = ttk.Frame(table_box)
        file_box.grid(row=3, column=0, sticky="ew", padx=4, pady=(0, 4))
        file_box.columnconfigure(0, weight=1)
        file_box.columnconfigure(1, weight=1)
        ttk.Button(file_box, text="Sauver conditions", command=self.save_json).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(file_box, text="Charger conditions", command=self.load_json).grid(row=0, column=1, sticky="ew", padx=(3, 0))

        self.pose_canvas = tk.Canvas(root, bg=CANVAS_BG, highlightthickness=2, highlightbackground="#7f8f83")
        self.pose_canvas.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        self.pose_canvas.bind("<Configure>", self.schedule_redraw)
        self.pose_canvas.bind("<ButtonPress-1>", self.on_pose_press)
        self.pose_canvas.bind("<B1-Motion>", self.on_pose_drag)
        self.pose_canvas.bind("<ButtonRelease-1>", self.on_pose_release)

        right = ttk.Frame(root)
        right.grid(row=0, column=2, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.animation_canvas = tk.Canvas(right, bg=CANVAS_BG, highlightthickness=2, highlightbackground="#c9d1c7")
        self.animation_canvas.grid(row=0, column=0, sticky="nsew")
        self.animation_canvas.bind("<Configure>", self.schedule_redraw)

        plot_header = ttk.Frame(root)
        plot_header.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(8, 0))
        ttk.Label(
            plot_header,
            textvariable=self.plot_title_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w")

        playback = ttk.Frame(root)
        playback.grid(row=1, column=2, sticky="ew", pady=(8, 0))
        playback.columnconfigure(1, weight=1)
        self.play_button = ttk.Button(playback, text="▶", command=self.toggle_play, width=4)
        self.play_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Scale(playback, variable=self.frame_var, from_=0, to=self.frame_count - 1, orient="horizontal", command=lambda _value: self.redraw()).grid(row=0, column=1, sticky="ew")

        self.plot_canvas = tk.Canvas(root, bg="#ffffff", highlightthickness=1, highlightbackground="#c9d1c7")
        self.plot_canvas.grid(row=2, column=1, columnspan=2, sticky="nsew", pady=(8, 0))
        self.plot_canvas.bind("<Configure>", self.schedule_redraw)

        ttk.Label(root, textvariable=self.status_var).grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 0))

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
    ) -> None:
        box = ttk.LabelFrame(parent, text=label)
        box.grid(row=row, column=0, columnspan=columnspan, sticky="ew", padx=4, pady=2)
        box.columnconfigure(0, weight=1)
        scale = ttk.Scale(box, variable=var, from_=start, to=end, orient="horizontal", command=lambda _value: self.on_parameter_changed())
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

    def update_didactic_guide(self) -> None:
        steps = (
            (("1. Choisir le ", None), ("sujet", "sujet"), (": homme ou femme enceinte.", None)),
            (("2. Selectionner la ", None), ("barre", "barre"), (": front, back ou over-head.", None)),
            (("3. Regler la ", None), ("charge", "charge"), ("; commencer a 0 %BW.", None)),
            (("4. Choisir les trois ", None), ("durees de phase", "phase"), (".", None)),
            (("5. Glisser les articulations pour la ", None), ("position basse", "pose"), (".", None)),
            (("6. Lancer l'", None), ("animation", "pose"), (" et surveiller les ", None), ("alertes", "alerte"), (".", None)),
            (("7. Voir cinematique, CoM puis ", None), ("couples", "barre"), (".", None)),
            (("8. Cliquer sur ", None), ("Ajouter", "pose"), (" pour conserver l'essai.", None)),
            (("9. Generer un autre cas en changeant un ", None), ("parametre", "charge"), (".", None)),
            (("10. Selectionner deux lignes pour ", None), ("comparer", "phase"), (".", None)),
            (("Avance: longueurs, couples max et couples detailles.", None),),
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

    def advance_didactic_guide(self) -> None:
        if not self.didactic_mode_var.get():
            self.didactic_mode_var.set(True)
        self.didactic_step = min(10, self.didactic_step + 1)
        self.update_didactic_guide()

    def anthro(self) -> Anthropometry:
        return Anthropometry(
            bar_mass=70.0 * self.load_var.get() / 100.0,
            shank_scale=scale_from_percent(self.shank_var.get()),
            thigh_scale=scale_from_percent(self.thigh_var.get()),
            trunk_scale=scale_from_percent(self.trunk_var.get()),
            subject_profile=self.subject_profile_var.get(),
            bar_position=self.bar_position_var.get(),
            wedge_angle_deg=20.0 if self.wedge_var.get() else 0.0,
        )

    def available_plot_choices(self) -> list[str]:
        return PLOT_CHOICES

    def update_plot_choices(self) -> None:
        choices = self.available_plot_choices()
        self.plot_menu.configure(values=choices)
        if self.plot_choice.get() not in choices:
            self.plot_choice.set("couples articulaires")
        self.on_plot_choice_changed()

    def max_torques(self) -> dict[str, float]:
        return {joint: max(1.0, var.get()) for joint, var in self.max_torque_vars.items()}

    def phase_durations(self) -> PhaseDurations:
        return PhaseDurations(
            max(2.0, min(4.0, self.eccentric_duration_var.get())),
            max(0.0, min(2.0, self.isometric_duration_var.get())),
            max(2.0, min(4.0, self.concentric_duration_var.get())),
        )

    def total_motion_duration(self) -> float:
        return self.phase_durations().total

    def centered_times(self, states: list[MotionState] | None = None) -> list[float]:
        states = states or self.states
        if not states:
            return []
        isometric_times = [state.time for state in states if state.phase == "isometrique"]
        squat_time = (
            (isometric_times[0] + isometric_times[-1]) / 2.0
            if isometric_times
            else states[len(states) // 2].time
        )
        return [state.time - squat_time for state in states]

    def plot_times(self, states: list[MotionState] | None = None) -> list[float]:
        times = self.centered_times(states)
        if not self.normalize_time_var.get() or not times:
            return times
        scale = max(abs(time) for time in times)
        if scale < 1e-9:
            return [0.0 for _time in times]
        return [100.0 * time / scale for time in times]

    def current_centered_time(self) -> float:
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

    def apply_torque_preset(self) -> None:
        preset = torque_presets(70.0, 1.70)[self.torque_preset_var.get()]
        for joint, torque in preset.torques.items():
            self.max_torque_vars[joint].set(round(torque))
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
            self.update_plot_choices()

    def recompute(self) -> None:
        anthro = self.anthro()
        self.states, self.results = simulate(
            anthro,
            self.final_q,
            self.phase_durations(),
            self.frame_count,
            self.max_torques(),
            self.angle_adapt_var.get(),
            self.model_cache,
        )
        if self.results and self.results[0].backend == "biorbd":
            model = self.model_cache.model_for(anthro)
            cop_source = "ZMP biorbd" if hasattr(model, "CalcZeroMomentPoint") else "CoP fallback"
            self.status_var.set(f"biorbd actif ({cop_source}): {self.model_cache.cached_path_for(anthro)}")
        elif self.results:
            self.status_var.set("backend analytique actif: biorbd indisponible ou modele non charge")
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
            "duration_excentrique_s": self.eccentric_duration_var.get(),
            "duration_isometrique_s": self.isometric_duration_var.get(),
            "duration_concentrique_s": self.concentric_duration_var.get(),
            "wedge_20_deg": self.wedge_var.get(),
            "frame": self.frame_var.get(),
            "plot_choice": self.plot_choice.get(),
            "quantity": self.quantity_var.get(),
            "show_joints": {name: var.get() for name, var in self.show_vars.items()},
            "show_com_components": {name: var.get() for name, var in self.com_component_vars.items()},
            "max_torques": {joint: var.get() for joint, var in self.max_torque_vars.items()},
            "torque_preset": self.torque_preset_var.get(),
            "show_torque_bounds": self.show_torque_bounds_var.get(),
            "angle_adapt": self.angle_adapt_var.get(),
            "show_sprite_centers": self.show_sprite_centers_var.get(),
            "show_segment_com": self.show_segment_com_var.get(),
            "low_quality_sprites": self.low_quality_sprites_var.get(),
            "refined_sprites": not self.low_quality_sprites_var.get(),
            "normalize_time": self.normalize_time_var.get(),
            "subplot_mode": self.subplot_mode_var.get(),
            "final_q_deg": [degrees(value) for value in self.final_q],
            "frame_count": self.frame_count,
        }

    def apply_settings(self, settings: dict[str, object]) -> None:
        self._suspend_selection_clear = True
        try:
            self.subject_profile_var.set(str(settings.get("subject_profile", self.subject_profile_var.get())))
            self.bar_position_var.set(str(settings.get("bar_position", self.bar_position_var.get())))
            if "load_percent_bw" in settings:
                self.load_var.set(float(settings["load_percent_bw"]))
            elif "load_kg" in settings:
                self.load_var.set(100.0 * float(settings["load_kg"]) / 70.0)
            self.shank_var.set(float(settings.get("shank_percent", self.shank_var.get())))
            self.thigh_var.set(float(settings.get("thigh_percent", self.thigh_var.get())))
            self.trunk_var.set(float(settings.get("trunk_percent", self.trunk_var.get())))
            legacy_duration = float(settings.get("duration_phase_s", 4.0))
            self.eccentric_duration_var.set(float(settings.get("duration_excentrique_s", legacy_duration)))
            self.isometric_duration_var.set(float(settings.get("duration_isometrique_s", 2.0)))
            self.concentric_duration_var.set(float(settings.get("duration_concentrique_s", legacy_duration)))
            self.wedge_var.set(bool(settings.get("wedge_20_deg", False)))
            self.torque_preset_var.set(str(settings.get("torque_preset", self.torque_preset_var.get())))
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
            self.show_torque_bounds_var.set(bool(settings.get("show_torque_bounds", self.show_torque_bounds_var.get())))
            self.angle_adapt_var.set(bool(settings.get("angle_adapt", self.angle_adapt_var.get())))
            self.show_sprite_centers_var.set(bool(settings.get("show_sprite_centers", self.show_sprite_centers_var.get())))
            self.show_segment_com_var.set(bool(settings.get("show_segment_com", self.show_segment_com_var.get())))
            if "low_quality_sprites" in settings:
                self.low_quality_sprites_var.set(bool(settings["low_quality_sprites"]))
            else:
                self.low_quality_sprites_var.set(not bool(settings.get("refined_sprites", True)))
            self.normalize_time_var.set(bool(settings.get("normalize_time", self.normalize_time_var.get())))
            self.subplot_mode_var.set(bool(settings.get("subplot_mode", self.subplot_mode_var.get())))
            self.final_q = self.clamp_final_q(
                tuple(radians(value) for value in self.normalized_final_q_deg(settings.get("final_q_deg")))
            )
            self.quantity_var.set(str(settings.get("quantity", self.quantity_var.get())))
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
            "conditions": [
                {
                    "iid": iid,
                    "label": condition["label"],
                    "settings": condition["settings"],
                    "final_q_deg": condition["final_q_deg"],
                }
                for iid, condition in self.saved_conditions.items()
            ]
            if include_conditions
            else [],
        }
        Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
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
                final_q_deg=[float(value) for value in condition.get("final_q_deg", [])],
                label=str(condition.get("label", "")) or None,
                iid=str(condition.get("iid", "")) or None,
            )
        self.status_var.set(f"configuration chargee: {path}")
        self.redraw()

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
        self.draw_pose_editor()
        self.draw_plot()
        self.draw_animation(frame)

    def on_table_selection_changed(self, _event: tk.Event | None = None) -> None:
        self.update_condition_buttons()
        self.update_plot_choices()
        self.redraw()

    def update_condition_buttons(self) -> None:
        if self.conditions_table.selection():
            self.delete_condition_button.state(["!disabled"])
        else:
            self.delete_condition_button.state(["disabled"])

    def on_table_click(self, event: tk.Event) -> None:
        if not self.conditions_table.identify_row(event.y):
            selected = self.conditions_table.selection()
            if selected:
                self.conditions_table.selection_remove(selected)
                self.on_table_selection_changed()

    def on_plot_choice_changed(self) -> None:
        choice = self.plot_choice.get()
        quantity_plot = choice in ("cinematique articulaire", "centre de masse")
        component_plot = choice in ("centre de masse", "force reaction sol")
        for checkbutton in self.show_checkbuttons.values():
            checkbutton.state(["disabled"] if component_plot else ["!disabled"])
        for control in self.quantity_controls:
            control.state(["!disabled"] if quantity_plot else ["disabled"])
        for control in self.com_controls:
            control.state(["!disabled"] if component_plot else ["disabled"])
        self.redraw()

    def world_to_canvas(self, canvas: tk.Canvas, point: tuple[float, float], bounds: tuple[float, float, float, float]) -> tuple[float, float]:
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        xmin, xmax, ymin, ymax = bounds
        pad = 42
        scale = min((width - 2 * pad) / (xmax - xmin), (height - 2 * pad) / (ymax - ymin))
        x = pad + (point[0] - xmin) * scale
        y = height - pad - (point[1] - ymin) * scale
        return x, y

    def canvas_to_world(self, canvas: tk.Canvas, x: float, y: float, bounds: tuple[float, float, float, float]) -> tuple[float, float]:
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        xmin, xmax, ymin, ymax = bounds
        pad = 42
        scale = min((width - 2 * pad) / (xmax - xmin), (height - 2 * pad) / (ymax - ymin))
        return (xmin + (x - pad) / scale, ymin + (height - pad - y) / scale)

    def scene_bounds(self, extra_x: float = 0.0) -> tuple[float, float, float, float]:
        anthro = self.anthro()
        ymax = 2.22 if anthro.bar_position == "over-head" else 1.92
        return (-0.36, anthro.foot.length + anthro.shank.length + 0.78 + extra_x, -0.08, ymax)

    def cop_in_foot(self, state: MotionState, result: DynamicsResult) -> bool:
        return state.pose.heel[0] <= result.cop_x <= state.pose.toe[0]

    def com_projection_in_foot(self, state: MotionState) -> bool:
        return state.pose.heel[0] <= state.pose.com[0] <= state.pose.toe[0]

    def over_limit_joints(self, result: DynamicsResult) -> list[str]:
        return [
            joint
            for joint in ("cheville", "genou", "hanche")
            if result.effort_ratios[joint] > 1.0
        ]

    def biomechanical_alerts(self, state: MotionState, result: DynamicsResult, include_com: bool) -> list[str]:
        alerts = []
        if not self.cop_in_foot(state, result):
            alerts.append("CoP hors pied")
        if include_com and not self.com_projection_in_foot(state):
            alerts.append("CoM hors pied")
        over_limit = self.over_limit_joints(result)
        if over_limit:
            alerts.append("couple > max: " + ", ".join(over_limit))
        return alerts

    def configure_alert_canvas(self, canvas: tk.Canvas, alerts: list[str]) -> None:
        if alerts:
            canvas.configure(bg=ALERT_BG, highlightbackground=ALERT_BORDER)
        else:
            canvas.configure(bg=CANVAS_BG, highlightbackground=OK_BORDER)

    def draw_alert_banner(self, canvas: tk.Canvas, alerts: list[str], y: int) -> None:
        if not alerts:
            return
        text = "Probleme biomecanique: " + " | ".join(alerts)
        item = canvas.create_text(
            16,
            y,
            text=text,
            anchor="nw",
            fill="#8a1f17",
            font=("Helvetica", 10, "bold"),
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
    ) -> None:
        bounds = bounds or self.scene_bounds()
        pose = state.pose
        joints = [pose.heel, pose.toe, pose.ankle, pose.knee, pose.hip, pose.shoulder]
        names = ["heel", "toe", "ankle", "knee", "hip", "shoulder"]

        def shifted(point: tuple[float, float]) -> tuple[float, float]:
            return (point[0] + x_offset, point[1])

        points = {name: self.world_to_canvas(canvas, shifted(point), bounds) for name, point in zip(names, joints)}
        if not hasattr(canvas, "_sprite_images"):
            canvas._sprite_images = []

        def mapper(point: tuple[float, float]) -> tuple[float, float]:
            return self.world_to_canvas(canvas, shifted(point), bounds)

        raster_drawn = self.draw_raster_segments(canvas, state, mapper)
        if not raster_drawn:
            segments = load_segments()
            foot_scale = self.anthro().foot.length / 1.07
            draw_segment(canvas, segments["foot"], pose.ankle, 0.0, foot_scale, mapper)
            draw_segment(canvas, segments["shank"], pose.ankle, -state.q[0], self.anthro().shank.length, mapper)
            draw_segment(canvas, segments["thigh"], pose.knee, -state.q[1], self.anthro().thigh.length, mapper)
            draw_segment(canvas, segments["trunk_bar"], pose.hip, -state.q[2], self.anthro().trunk.length, mapper)
        canvas.create_line(*points["heel"], *points["toe"], width=3, fill="#333333")
        if self.anthro().wedge_angle_deg:
            heel = self.world_to_canvas(canvas, shifted(pose.heel), bounds)
            toe = self.world_to_canvas(canvas, shifted(pose.toe), bounds)
            floor_heel = self.world_to_canvas(canvas, shifted((pose.heel[0], 0.0)), bounds)
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
        canvas.create_line(com[0], com[1], projection[0], projection[1], fill="#3d7580", dash=(4, 4), width=1)
        canvas.create_oval(com[0] - 7, com[1] - 7, com[0] + 7, com[1] + 7, fill="#2c9ab7", outline="")
        canvas.create_oval(projection[0] - 5, projection[1] - 5, projection[0] + 5, projection[1] + 5, fill="#2c9ab7", outline="")
        if self.show_segment_com_var.get():
            for label, point in state.pose.segment_coms.items():
                px = self.world_to_canvas(canvas, shifted(point), bounds)
                canvas.create_oval(px[0] - 4, px[1] - 4, px[0] + 4, px[1] + 4, fill="#e64357", outline="#ffffff")
                canvas.create_text(px[0] + 6, px[1] - 6, text=label, anchor="sw", fill="#8a1f32", font=("Helvetica", 8, "bold"))

        cop = self.world_to_canvas(canvas, (result.cop_x + x_offset, 0.0), bounds)
        force_end = self.world_to_canvas(
            canvas,
            (result.cop_x + x_offset + result.ground_reaction[0] / FORCE_DRAW_SCALE, result.ground_reaction[1] / FORCE_DRAW_SCALE),
            bounds,
        )
        canvas.create_line(cop[0], cop[1], force_end[0], force_end[1], arrow=tk.LAST, width=3, fill="#c15a2b")
        for joint in (pose.knee, pose.hip):
            projected = self.project_on_force_line(joint, (result.cop_x, 0.0), result.ground_reaction)
            joint_px = self.world_to_canvas(canvas, shifted(joint), bounds)
            projected_px = self.world_to_canvas(canvas, shifted(projected), bounds)
            canvas.create_line(joint_px[0], joint_px[1], projected_px[0], projected_px[1], fill="#1f77b4", dash=(4, 4), width=2)
            canvas.create_oval(projected_px[0] - 3, projected_px[1] - 3, projected_px[0] + 3, projected_px[1] + 3, fill="#1f77b4", outline="")

        for name in ("cheville", "genou", "hanche"):
            ratio = min(1.0, result.effort_ratios[name])
            red = int(40 + 190 * ratio)
            green = int(170 * max(0.0, 1.0 - max(0.0, ratio - 0.5) * 2.0))
            color = f"#{red:02x}{green:02x}35"
            point = {"cheville": pose.ankle, "genou": pose.knee, "hanche": pose.hip}[name]
            px = self.world_to_canvas(canvas, shifted(point), bounds)
            canvas.create_oval(px[0] - 12, px[1] - 12, px[0] + 12, px[1] + 12, outline=color, width=4)
        for name in ("ankle", "knee", "hip", "shoulder"):
            x, y = points[name]
            canvas.create_oval(x - 6, y - 6, x + 6, y + 6, fill="#ffffff", outline="#1f1f1f", width=2)
        if self.show_sprite_centers_var.get():
            for name in ("ankle", "knee", "hip", "shoulder", "toe"):
                x, y = points[name]
                canvas.create_line(x - 12, y, x + 12, y, fill="#26a69a", width=2)
                canvas.create_line(x, y - 12, x, y + 12, fill="#26a69a", width=2)

        if with_handles:
            for name in ("knee", "hip", "shoulder"):
                x, y = points[name]
                canvas.create_oval(x - 9, y - 9, x + 9, y + 9, fill="#f7f7f2", outline="#1d3d35", width=2, tags=name)

    def draw_raster_segments(self, canvas: tk.Canvas, state: MotionState, mapper) -> bool:
        try:
            pose = state.pose
            refined = not self.low_quality_sprites_var.get()
            trunk_variant = (self.subject_profile_var.get(), self.bar_position_var.get())
            return all(
                (
                    draw_sprite_segment(
                        canvas,
                        "foot",
                        pose.ankle,
                        pose.toe,
                        mapper,
                        refined,
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
        result = min(self.results, key=lambda item: abs(item.com[0] - state.pose.com[0]) + abs(item.com[1] - state.pose.com[1]))
        alerts = self.biomechanical_alerts(state, result, include_com=True)
        self.configure_alert_canvas(canvas, alerts)
        self.draw_skeleton(canvas, state, result, with_handles=True)
        self.draw_squat_angle_labels(canvas, state)
        canvas.create_text(16, 16, text="Position de squat", anchor="nw", fill="#22312a", font=("Helvetica", 13, "bold"))
        canvas.create_text(16, 38, text="Glisser genou, hanche ou epaules", anchor="nw", fill="#506158")
        self.draw_alert_banner(canvas, alerts, 62)

    def draw_squat_angle_labels(self, canvas: tk.Canvas, state: MotionState) -> None:
        pose = state.pose
        bounds = self.scene_bounds()
        labels = (
            ("cheville", degrees(state.q[0]), pose.ankle, (12, -24)),
            ("genou", degrees(state.q[1] - state.q[0]), pose.knee, (12, -24)),
            ("hanche", degrees(state.q[2] - state.q[1]), pose.hip, (12, 22)),
        )
        for name, value, point, offset in labels:
            x, y = self.world_to_canvas(canvas, point, bounds)
            item = canvas.create_text(
                x + offset[0],
                y + offset[1],
                text=f"{name}: {value:.0f} deg",
                anchor="w",
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
        datasets = self.plot_datasets()
        current_plot_time = self.current_centered_time()
        sampled = [
            {
                **dataset,
                **self.sample_dataset_at_time(dataset, current_plot_time),
            }
            for dataset in datasets
        ]
        alerts = [
            alert
            for item in sampled
            for alert in self.biomechanical_alerts(item["state"], item["result"], include_com=False)  # type: ignore[arg-type]
        ]
        self.configure_alert_canvas(canvas, alerts)
        bounds = self.scene_bounds(extra_x=max(0, len(sampled) - 1))
        for index, item in enumerate(sampled):
            self.draw_skeleton(canvas, item["state"], item["result"], with_handles=False, bounds=bounds, x_offset=float(index))  # type: ignore[arg-type]
            if len(sampled) > 1:
                label_point = self.world_to_canvas(canvas, (float(index), -0.045), bounds)
                color = str(item["color"])
                canvas.create_text(label_point[0], label_point[1], text=str(item["label"]), anchor="n", fill=color, font=("Helvetica", 10, "bold"))
        state = sampled[0]["state"]  # type: ignore[assignment]
        result = sampled[0]["result"]  # type: ignore[assignment]
        canvas.create_text(
            16,
            16,
            text=f"Animation {state.phase} {self.animation_time_label(current_plot_time)}",
            anchor="nw",
            fill="#22312a",
            font=("Helvetica", 13, "bold"),
        )
        self.draw_animation_values(canvas, sampled)
        self.draw_alert_banner(canvas, alerts, 126)

    def draw_animation_values(self, canvas: tk.Canvas, sampled: list[dict[str, object]]) -> None:
        column_width = 155
        for index, item in enumerate(sampled):
            x = 16 + index * column_width
            y = 42
            color = str(item["color"] or "#22312a")
            result = item["result"]  # type: ignore[assignment]
            canvas.create_text(x, y, text=str(item["label"]), anchor="nw", fill=color, font=("Helvetica", 10, "bold"))
            y += 18
            for joint in ("cheville", "genou", "hanche"):
                torque = result.torques[joint]
                ratio = result.effort_ratios[joint]
                text_color = "#8a1f17" if ratio > 1.0 else color
                canvas.create_text(x, y, text=f"{joint}: {torque: .1f} Nm ({100 * ratio: .0f}%)", anchor="nw", fill=text_color, font=("Helvetica", 9))
                y += 18

    def draw_plot(self) -> None:
        canvas = self.plot_canvas
        canvas.delete("all")
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        choice = self.plot_choice.get()
        self.plot_title_var.set(f"{choice} ({self.plot_unit(choice)})")
        datasets = self.plot_datasets()
        plotted = [
            {
                **dataset,
                "series": self.plot_series_for(choice, dataset["states"], dataset["results"]),  # type: ignore[arg-type]
                "times": self.plot_times(dataset["states"]),  # type: ignore[arg-type]
            }
            for dataset in datasets
        ]
        plotted = [dataset for dataset in plotted if dataset["series"]]
        if not plotted:
            return
        if self.subplot_mode_var.get():
            self.draw_subplot_plot(canvas, plotted, choice, width, height)
        else:
            self.draw_single_axis_plot(canvas, plotted, choice, width, height)

    def plot_datasets(self) -> list[dict[str, object]]:
        selected = [iid for iid in self.conditions_table.selection() if iid in self.saved_conditions]
        if not selected:
            return [{"label": "courant", "states": self.states, "results": self.results, "color": None}]
        total = len(selected)
        datasets: list[dict[str, object]] = []
        for index, iid in enumerate(selected):
            condition = self.saved_conditions[iid]
            datasets.append(
                {
                    "label": condition["label"],
                    "states": condition["states"],
                    "results": condition["results"],
                    "color": self.condition_color(index, total),
                }
            )
        return datasets

    def sample_dataset_at_time(self, dataset: dict[str, object], plot_time: float) -> dict[str, object]:
        states = dataset["states"]  # type: ignore[assignment]
        results = dataset["results"]  # type: ignore[assignment]
        times = self.plot_times(states)
        if not times:
            return {"state": self.states[0], "result": self.results[0]}
        if plot_time <= times[0]:
            return {"state": states[0], "result": results[0]}
        if plot_time >= times[-1]:
            return {"state": states[-1], "result": results[-1]}
        index = min(range(len(times)), key=lambda candidate: abs(times[candidate] - plot_time))
        return {"state": states[index], "result": results[index]}

    def animation_time_label(self, plot_time: float) -> str:
        if self.normalize_time_var.get():
            return f"t={plot_time:.0f}%"
        return f"t={plot_time:.2f}s"

    def plot_time_bounds(self, plotted: list[dict[str, object]]) -> tuple[float, float]:
        if self.normalize_time_var.get():
            return (-100.0, 100.0)
        times = [
            time
            for dataset in plotted
            for time in dataset.get("times", [])  # type: ignore[union-attr]
        ]
        if not times:
            duration = self.total_motion_duration()
            return (-duration / 2.0, duration / 2.0)
        xmin = min(times)
        xmax = max(times)
        if abs(xmax - xmin) < 1e-9:
            return (xmin - 1.0, xmax + 1.0)
        return xmin, xmax

    def x_from_time(self, time: float, x0: float, x1: float, tmin: float, tmax: float) -> float:
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
        rgb = tuple(round(start[channel] + local * (end[channel] - start[channel])) for channel in range(3))
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

    def blend_color(self, color: str, target: str, fraction: float) -> str:
        color = color.lstrip("#")
        target = target.lstrip("#")
        rgb = tuple(int(color[index : index + 2], 16) for index in (0, 2, 4))
        target_rgb = tuple(int(target[index : index + 2], 16) for index in (0, 2, 4))
        mixed = tuple(round(rgb[index] + fraction * (target_rgb[index] - rgb[index])) for index in range(3))
        return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"

    def component_color(self, base_color: str, component: str) -> str:
        if component == "inertiels/non-lineaires":
            return base_color
        if component == "total":
            return self.blend_color(base_color, "#ffffff", 0.28)
        if component == "contact":
            return self.blend_color(base_color, "#ffffff", 0.48)
        return base_color

    def selected_panel_names(self, plotted: list[dict[str, object]], choice: str) -> list[str]:
        if choice == DETAILED_PLOT_CHOICE:
            return [joint for joint in ("cheville", "genou", "hanche") if self.show_vars[joint].get()]
        names: list[str] = []
        for dataset in plotted:
            for name in dataset["series"]:  # type: ignore[union-attr]
                if name not in names:
                    names.append(str(name))
        return names

    def draw_subplot_plot(self, canvas: tk.Canvas, plotted: list[dict[str, object]], choice: str, width: int, height: int) -> None:
        panels = self.selected_panel_names(plotted, choice)
        if not panels:
            return
        pad_left, pad_top, pad_right, pad_bottom = 54, 32, 18, 44
        gap = 22
        panel_width = (width - pad_left - pad_right - gap * (len(panels) - 1)) / len(panels)
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
            self.draw_panel_axes(canvas, x0, x1, y0, y1, ymin, ymax, unit, panel_name, tmin, tmax)
            if choice == DETAILED_PLOT_CHOICE:
                self.draw_detailed_panel(canvas, plotted, panel_name, x0, x1, y0, y1, ymin, ymax, tmin, tmax)
            else:
                self.draw_panel_series(canvas, plotted, panel_name, x0, x1, y0, y1, ymin, ymax, tmin, tmax)
            self.draw_panel_limits(canvas, plotted, choice, panel_name, x0, x1, y0, y1, ymin, ymax, tmin, tmax)
        self.draw_condition_legend(canvas, plotted, width, height)
        if choice == DETAILED_PLOT_CHOICE:
            self.draw_detailed_component_legend(canvas, width - 270, pad_top + 6)

    def draw_single_axis_plot(self, canvas: tk.Canvas, plotted: list[dict[str, object]], choice: str, width: int, height: int) -> None:
        pad_left, pad_top, pad_right, pad_bottom = 54, 24, 18, 36
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
        self.draw_panel_axes(canvas, x0, x1, y0, y1, ymin, ymax, unit, choice, tmin, tmax)
        if choice == DETAILED_PLOT_CHOICE:
            for panel in panels:
                self.draw_detailed_panel(canvas, plotted, panel, x0, x1, y0, y1, ymin, ymax, tmin, tmax)
            self.draw_detailed_component_legend(canvas, x1 - 270, y1 + 4)
        else:
            palette = ["#2e7d54", "#b46d22", "#6d5ea8", "#2a8ca6", "#9b3d3d", "#4c6f3d", "#8a5a22"]
            for dataset_index, dataset in enumerate(plotted):
                multi_condition = len(plotted) > 1
                for series_index, (name, values) in enumerate(dataset["series"].items()):  # type: ignore[union-attr]
                    color = str(dataset["color"]) if multi_condition else JOINT_COLORS.get(name, palette[series_index % len(palette)])
                    dash = None if not multi_condition else (None, (6, 4), (2, 3))[series_index % 3]
                    self.draw_series_line(canvas, values, x0, x1, y0, y1, ymin, ymax, color, width=2, dash=dash, times=dataset["times"], tmin=tmin, tmax=tmax)  # type: ignore[arg-type]
        self.draw_torque_bounds(canvas, x0, x1, y0, y1, ymin, ymax, tmin, tmax)
        self.draw_normalized_torque_limit(canvas, x0, x1, y0, y1, ymin, ymax)
        if choice == "force reaction sol" and "vertical" in panels:
            self.draw_body_weight_line(canvas, plotted, x0, x1, y0, y1, ymin, ymax)
        self.draw_condition_legend(canvas, plotted, width, height)

    def panel_values(self, plotted: list[dict[str, object]], choice: str, panel_name: str) -> list[float]:
        if choice == DETAILED_PLOT_CHOICE:
            return [
                value
                for dataset in plotted
                for component in ("inertiels/non-lineaires", "total", "contact")
                for value in dataset["series"].get(f"{panel_name} {component}", [])  # type: ignore[union-attr]
            ]
        return [
            value
            for dataset in plotted
            for value in dataset["series"].get(panel_name, [])  # type: ignore[union-attr]
        ]

    def value_bounds(self, values: list[float], choice: str, panel_name: str | None) -> tuple[float, float]:
        all_values = list(values)
        if panel_name is not None:
            all_values.extend(self.limit_values_for_plot(choice, panel_name))
        if choice == "couples normalises":
            all_values.append(100.0)
        ymin = min(all_values)
        ymax = max(all_values)
        if abs(ymax - ymin) < 1e-9:
            ymin -= 1.0
            ymax += 1.0
        margin = 0.05 * (ymax - ymin)
        return ymin - margin, ymax + margin

    def limit_values_for_plot(self, choice: str, panel_name: str) -> list[float]:
        if choice not in ("couples articulaires", DETAILED_PLOT_CHOICE) or not self.show_torque_bounds_var.get():
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
    ) -> None:
        canvas.create_line(x0, y0, x1, y0, fill="#69746e")
        canvas.create_line(x0, y0, x0, y1, fill="#69746e")
        self.draw_y_ticks(canvas, x0, y0, y1, ymin, ymax, x1)
        self.draw_x_ticks(canvas, x0, x1, y0, tmin, tmax)
        self.draw_time_markers(canvas, x0, x1, y0, y1, tmin, tmax)
        canvas.create_text(x0 + 4, y1 - 14, text=f"{title} ({unit})", anchor="w", fill="#22312a", font=("Helvetica", 10, "bold"))
        xlabel = "temps (%)" if self.normalize_time_var.get() else "temps (s)"
        canvas.create_text(x1, canvas.winfo_height() - 12, text=xlabel, anchor="e", fill="#506158", font=("Helvetica", 9))

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
            color = str(dataset["color"]) if multi_condition else JOINT_COLORS.get(panel_name, "#2e7d54")
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
            self.draw_torque_bound_for_joint(canvas, panel_name, x0, x1, y0, y1, ymin, ymax, tmin=tmin, tmax=tmax)

    def draw_condition_legend(self, canvas: tk.Canvas, plotted: list[dict[str, object]], width: int, height: int) -> None:
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
            canvas.create_text(x0 - 8, y, text=self.format_axis_value(value), anchor="e", fill="#506158", font=("Helvetica", 9))

    def draw_x_ticks(self, canvas: tk.Canvas, x0: float, x1: float, y0: float, tmin: float, tmax: float) -> None:
        for index in range(5):
            fraction = index / 4
            x = x0 + (x1 - x0) * fraction
            value = tmin + (tmax - tmin) * fraction
            canvas.create_line(x, y0, x, y0 + 4, fill="#69746e")
            canvas.create_text(x, y0 + 16, text=self.format_axis_value(value), anchor="n", fill="#506158", font=("Helvetica", 9))

    def draw_time_markers(self, canvas: tk.Canvas, x0: float, x1: float, y0: float, y1: float, tmin: float, tmax: float) -> None:
        if tmin <= 0.0 <= tmax:
            squat_x = self.x_from_time(0.0, x0, x1, tmin, tmax)
            canvas.create_line(squat_x, y0, squat_x, y1, fill="#59645e", width=1, dash=(6, 5))
            canvas.create_text(squat_x + 4, y1 + 4, text="squat t=0", anchor="nw", fill="#59645e", font=("Helvetica", 9))

        current_time = min(tmax, max(tmin, self.current_centered_time()))
        animation_x = self.x_from_time(current_time, x0, x1, tmin, tmax)
        canvas.create_line(animation_x, y0, animation_x, y1, fill="#c9332c", width=2)

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
            return {"position": "deg", "vitesse": "deg/s", "acceleration": "deg/s2"}[self.quantity_var.get()]
        if choice == "centre de masse":
            return {"position": "m", "vitesse": "m/s", "acceleration": "m/s2"}[self.quantity_var.get()]
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
        if self.plot_choice.get() not in ("couples articulaires", "couples detailles") or not self.show_torque_bounds_var.get():
            return
        if tmin is None or tmax is None:
            tmin, tmax = self.plot_time_bounds([{"times": self.plot_times()}])
        for joint, values in self.torque_bound_series().items():
            self.draw_torque_bound_for_joint(canvas, joint, x0, x1, y0, y1, ymin, ymax, values, tmin=tmin, tmax=tmax)

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
        if joint not in self.show_vars or not self.show_vars[joint].get() or not self.show_torque_bounds_var.get():
            return
        values = values or self.torque_bound_series().get(joint, [])
        if tmin is None or tmax is None:
            tmin, tmax = self.plot_time_bounds([{"times": self.plot_times()}])
        times = self.plot_times()
        color = JOINT_COLORS[joint]
        for sign in (1.0, -1.0):
            points = []
            for index, value in enumerate(values):
                x = self.x_from_time(times[index], x0, x1, tmin, tmax) if index < len(times) else x0
                y = y0 - (y0 - y1) * (sign * value - ymin) / (ymax - ymin)
                points.extend([x, y])
            if len(points) >= 4:
                canvas.create_line(*points, fill=color, width=1, dash=(6, 5))

    def draw_normalized_torque_limit(self, canvas: tk.Canvas, x0: float, x1: float, y0: float, y1: float, ymin: float, ymax: float) -> None:
        if self.plot_choice.get() != "couples normalises":
            return
        y = y0 - (y0 - y1) * (100.0 - ymin) / (ymax - ymin)
        canvas.create_line(x0, y, x1, y, fill="#c9332c", width=1, dash=(6, 5))
        canvas.create_text(x1 - 4, y - 4, text="100%", anchor="se", fill="#8a1f17", font=("Helvetica", 9, "bold"))

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
            results = dataset["results"]  # type: ignore[assignment]
            if results:
                weight = float(results[0].ground_reaction[1])
                if all(abs(weight - existing) > 1e-6 for existing in weights):
                    weights.append(weight)
        for weight in weights:
            if not ymin <= weight <= ymax:
                continue
            y = y0 - (y0 - y1) * (weight - ymin) / (ymax - ymin)
            canvas.create_line(x0, y, x1, y, fill="#59645e", width=1, dash=(6, 5))
            canvas.create_text(x1 - 4, y - 4, text=f"poids {weight:.0f} N", anchor="se", fill="#59645e", font=("Helvetica", 9))

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
        component_styles = (
            ("inertiels/non-lineaires", 2, None, None),
            ("total", 1, (7, 4), None),
            ("contact", 1, (7, 3, 2, 3), "triangle"),
        )
        for joint in ("cheville", "genou", "hanche"):
            if joint not in self.show_vars or not self.show_vars[joint].get():
                continue
            color = JOINT_COLORS[joint]
            for component, width, dash, marker in component_styles:
                values = series.get(f"{joint} {component}", [])
                component_color = self.component_color(color, component)
                self.draw_series_line(canvas, values, x0, x1, y0, y1, ymin, ymax, component_color, width=width, dash=dash)
                if marker == "triangle":
                    self.draw_triangle_markers(canvas, values, x0, x1, y0, y1, ymin, ymax, component_color)
            canvas.create_line(legend_x, canvas.winfo_height() - 14, legend_x + 18, canvas.winfo_height() - 14, fill=color, width=3)
            canvas.create_text(legend_x + 24, canvas.winfo_height() - 14, text=joint, anchor="w", fill="#22312a")
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
        component_styles = (
            ("inertiels/non-lineaires", 2, None, None),
            ("total", 1, (7, 4), None),
            ("contact", 1, (7, 3, 2, 3), "triangle"),
        )
        for dataset in plotted:
            color = str(dataset["color"]) if multi_condition else JOINT_COLORS[joint]
            series = dataset["series"]  # type: ignore[assignment]
            times = dataset["times"]  # type: ignore[assignment]
            for component, width, dash, marker in component_styles:
                values = series.get(f"{joint} {component}", [])
                component_color = self.component_color(color, component)
                self.draw_series_line(canvas, values, x0, x1, y0, y1, ymin, ymax, component_color, width=width, dash=dash, times=times, tmin=tmin, tmax=tmax)
                if marker == "triangle":
                    self.draw_triangle_markers(canvas, values, x0, x1, y0, y1, ymin, ymax, component_color, times=times, tmin=tmin, tmax=tmax)

    def draw_detailed_component_legend(self, canvas: tk.Canvas, x: float, y: float) -> None:
        styles = (
            ("inertiels/non-lineaires", None, None),
            ("total", (7, 4), None),
            ("contact", (7, 3, 2, 3), "triangle"),
        )
        for index, (label, dash, marker) in enumerate(styles):
            yy = y + 16 * index
            canvas.create_line(x, yy, x + 28, yy, fill="#334139", width=2, dash=dash)
            if marker == "triangle":
                canvas.create_polygon(x + 14, yy - 4, x + 10, yy + 4, x + 18, yy + 4, fill="#334139", outline="#334139")
            canvas.create_text(x + 34, yy, text=label, anchor="w", fill="#334139", font=("Helvetica", 9))

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
        points = []
        for index, value in enumerate(values):
            if times is not None and tmin is not None and tmax is not None and index < len(times):
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
            if times is not None and tmin is not None and tmax is not None and index < len(times):
                x = self.x_from_time(times[index], x0, x1, tmin, tmax)
            else:
                x = x0 + (x1 - x0) * index / max(1, len(values) - 1)
            y = y0 - (y0 - y1) * (value - ymin) / (ymax - ymin)
            canvas.create_polygon(x, y - 5, x - 5, y + 5, x + 5, y + 5, fill=color, outline=color)

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
            values = {joint: [result.torques[joint] for result in results] for joint in ("cheville", "genou", "hanche")}
        elif choice == "couples normalises":
            values = {
                joint: [100.0 * result.effort_ratios[joint] for result in results]
                for joint in ("cheville", "genou", "hanche")
            }
        elif choice == "couples detailles":
            values = {}
            for joint in ("cheville", "genou", "hanche"):
                if joint in selected:
                    values[f"{joint} inertiels/non-lineaires"] = [
                        result.torque_components[joint]["inertiels_non_lineaires"] for result in results
                    ]
                    values[f"{joint} total"] = [result.torque_components[joint]["total"] for result in results]
                    values[f"{joint} contact"] = [result.torque_components[joint]["contact"] for result in results]
            return values
        else:
            values = {joint: [result.powers[joint] for result in results] for joint in ("cheville", "genou", "hanche")}
        for name in selected:
            if name in values:
                data[name] = values[name]
        return data

    def joint_kinematic_series(self, states: list[MotionState] | None = None) -> dict[str, list[float]]:
        states = states or self.states
        quantity = self.quantity_var.get()
        if quantity == "position":
            return {
                "cheville": [degrees(state.q[0]) for state in states],
                "genou": [degrees(state.q[1] - state.q[0]) for state in states],
                "hanche": [degrees(state.q[2] - state.q[1]) for state in states],
            }
        if quantity == "vitesse":
            return {
                "cheville": [degrees(state.qdot[0]) for state in states],
                "genou": [degrees(state.qdot[1] - state.qdot[0]) for state in states],
                "hanche": [degrees(state.qdot[2] - state.qdot[1]) for state in states],
            }
        return {
            "cheville": [degrees(state.qddot[0]) for state in states],
            "genou": [degrees(state.qddot[1] - state.qddot[0]) for state in states],
            "hanche": [degrees(state.qddot[2] - state.qddot[1]) for state in states],
        }

    def com_plot_series(self, results: list[DynamicsResult] | None = None) -> dict[str, list[float]]:
        results = results or self.results
        quantity = self.quantity_var.get()
        source = {
            "position": [result.com for result in results],
            "vitesse": [result.com_velocity for result in results],
            "acceleration": [result.com_acceleration for result in results],
        }[quantity]
        return self.horizontal_vertical_series(source)

    def ground_reaction_plot_series(self, results: list[DynamicsResult] | None = None) -> dict[str, list[float]]:
        results = results or self.results
        return self.horizontal_vertical_series([result.ground_reaction for result in results])

    def horizontal_vertical_series(self, source: list[tuple[float, float]]) -> dict[str, list[float]]:
        data: dict[str, list[float]] = {}
        if self.com_component_vars["horizontal"].get():
            data["horizontal"] = [value[0] for value in source]
        if self.com_component_vars["vertical"].get():
            data["vertical"] = [value[1] for value in source]
        return data

    def torque_bound_series(self) -> dict[str, list[float]]:
        bounds: dict[str, list[float]] = {}
        max_torques = self.max_torques()
        for joint in ("cheville", "genou", "hanche"):
            bounds[joint] = [
                available_joint_torque_limits(state, max_torques, self.angle_adapt_var.get())[joint]
                for state in self.states
            ]
        return bounds

    def nearest_handle(self, x: float, y: float) -> str | None:
        anthro = self.anthro()
        pose = pose_from_angles(anthro, self.final_q)
        bounds = self.scene_bounds()
        candidates = {"knee": pose.knee, "hip": pose.hip, "shoulder": pose.shoulder}
        for name, point in candidates.items():
            px, py = self.world_to_canvas(self.pose_canvas, point, bounds)
            if (px - x) ** 2 + (py - y) ** 2 < 20**2:
                return name
        return None

    def on_pose_press(self, event: tk.Event) -> None:
        self.drag_target = self.nearest_handle(event.x, event.y)

    def on_pose_drag(self, event: tk.Event) -> None:
        if not self.drag_target:
            return
        anthro = self.anthro()
        pose = pose_from_angles(anthro, self.final_q)
        point = self.canvas_to_world(self.pose_canvas, event.x, event.y, self.scene_bounds())
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
        self.on_parameter_changed()

    def clamp_final_q(self, q: tuple[float, float, float]) -> tuple[float, float, float]:
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
        factor = (relative[0] * force_vector[0] + relative[1] * force_vector[1]) / norm_squared
        return (force_origin[0] + factor * force_vector[0], force_origin[1] + factor * force_vector[1])

    def on_pose_release(self, _event: tk.Event) -> None:
        self.drag_target = None

    def toggle_play(self) -> None:
        self.playing = not self.playing
        self.play_button.configure(text="⏸" if self.playing else "▶")
        if self.playing:
            self.after(30, self.step_animation)

    def step_animation(self) -> None:
        if not self.playing:
            return
        self.frame_var.set((self.frame_var.get() + 1) % self.frame_count)
        self.redraw()
        self.after(30, self.step_animation)

    def record_condition(self) -> None:
        self.add_saved_condition(
            self.current_settings(),
            [degrees(value) for value in self.final_q],
            states=list(self.states),
            results=list(self.results),
        )
        self.status_var.set(f"condition {self.saved_condition_count} enregistree")
        if self.didactic_mode_var.get() and self.didactic_step < 8:
            self.didactic_step = 8
            self.update_didactic_guide()

    def clear_conditions(self) -> None:
        self.saved_conditions.clear()
        self.saved_condition_count = 0
        for iid in self.conditions_table.get_children():
            self.conditions_table.delete(iid)

    def add_saved_condition(
        self,
        settings: dict[str, object],
        final_q_deg: list[float],
        label: str | None = None,
        iid: str | None = None,
        states: list[MotionState] | None = None,
        results: list[DynamicsResult] | None = None,
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
        squat_angles = self.display_joint_angles(tuple(radians(value) for value in final_q_deg))
        self.saved_conditions[condition_iid] = {
            "label": condition_label,
            "settings": settings,
            "final_q_deg": final_q_deg,
            "states": states,
            "results": results,
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
        self.on_table_selection_changed()
        self.status_var.set(f"{len(selected)} condition(s) supprimee(s)")

    def simulate_from_condition(
        self,
        settings: dict[str, object],
        final_q_deg: list[float],
    ) -> tuple[list[MotionState], list[DynamicsResult]]:
        load_kg = float(settings.get("load_kg", 70.0 * float(settings.get("load_percent_bw", 0.0)) / 100.0))
        anthro = Anthropometry(
            bar_mass=load_kg,
            shank_scale=scale_from_percent(float(settings.get("shank_percent", 0.0))),
            thigh_scale=scale_from_percent(float(settings.get("thigh_percent", 0.0))),
            trunk_scale=scale_from_percent(float(settings.get("trunk_percent", 0.0))),
            subject_profile=str(settings.get("subject_profile", "homme")),
            bar_position=str(settings.get("bar_position", "back")),
            wedge_angle_deg=20.0 if bool(settings.get("wedge_20_deg", False)) else 0.0,
        )
        final_q = self.clamp_final_q(tuple(radians(value) for value in self.normalized_final_q_deg(final_q_deg)))
        max_torques = {
            joint: float(dict(settings.get("max_torques", {})).get(joint, self.max_torque_vars[joint].get()))
            for joint in ("cheville", "genou", "hanche")
        }
        legacy_duration = float(settings.get("duration_phase_s", 4.0))
        durations = PhaseDurations(
            max(2.0, min(4.0, float(settings.get("duration_excentrique_s", legacy_duration)))),
            max(0.0, min(2.0, float(settings.get("duration_isometrique_s", 2.0)))),
            max(2.0, min(4.0, float(settings.get("duration_concentrique_s", legacy_duration)))),
        )
        return simulate(
            anthro,
            final_q,
            durations,
            self.frame_count,
            max_torques,
            bool(settings.get("angle_adapt", self.angle_adapt_var.get())),
            self.model_cache,
        )

    def display_joint_angles(self, q: tuple[float, float, float]) -> tuple[float, float, float]:
        return (
            degrees(q[0]),
            degrees(q[1] - q[0]),
            degrees(q[2] - q[1]),
        )


def main() -> None:
    app = SquatGui()
    app.mainloop()
