"""Tk widget construction for :class:`~squat_gui.app.SquatGui`.

This module deliberately owns only widget creation and geometry.  Event
handlers and all simulation state remain on ``SquatGui``; widgets are attached
to that object to preserve the public integration points used by the GUI and
its layout tests.
"""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING
from tkinter import ttk

from .anthropometry import ANTHROPOMETRY_MODES, BAR_POSITIONS, SUBJECT_PROFILES
from .didactics import (
    DYNAMIC_PHASE_DURATION_OPTIONS,
    ISOMETRIC_PHASE_DURATION_OPTIONS,
    TEMPORAL_PRESETS,
    RevealMode,
    temporal_preset_display,
)
from .pose_angle_dialog import PrecisePoseAngleDialog
from .timeline import TimeMode
from .torque_capacity import torque_presets

if TYPE_CHECKING:
    from .app import SquatGui


class LayoutBuilder:
    """Build the Tkinter view while delegating callbacks to the GUI object."""

    def __init__(
        self,
        gui: SquatGui,
        *,
        canvas_background: str,
        plot_choices: tuple[str, ...],
        load_percent_options: tuple[float, ...],
    ) -> None:
        self.gui = gui
        self.canvas_background = canvas_background
        self.plot_choices = plot_choices
        self.load_percent_options = load_percent_options

    def build(self) -> None:
        self._configure_styles()
        root = self._build_root()
        self._build_left_panel(root)
        self._build_pose_panel(root)
        self._build_animation_panel(root)
        self._build_playback_panel(root)
        self._build_plot_panel(root)
        self._build_status(root)
        self.gui.update_didactic_guide()

    def _configure_styles(self) -> None:
        style = ttk.Style(self.gui)
        style.theme_use("clam")
        style.configure("TFrame", background="#f2f4f1")
        style.configure("TLabelframe", background="#f2f4f1")
        style.configure("TLabel", background="#f2f4f1", foreground="#22312a")
        style.configure("TCheckbutton", background="#f2f4f1")
        style.configure("TButton", padding=6)
        style.configure("Invalid.TSpinbox", fieldbackground="#ffe3df")
        style.configure("GuideNav.TButton", padding=(3, 2), font=("Helvetica", 11, "bold"))
        self.gui._configure_didactic_styles(style)

    def _build_root(self) -> ttk.Frame:
        root = ttk.Frame(self.gui, padding=10)
        self.gui.root_layout = root
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=0, minsize=360)
        root.columnconfigure(1, weight=1, minsize=260)
        root.columnconfigure(2, weight=2, minsize=280)
        root.rowconfigure(0, weight=1, minsize=420)
        root.rowconfigure(2, weight=3, minsize=250)
        return root

    def _build_left_panel(self, root: ttk.Frame) -> None:
        gui = self.gui
        gui.left_scroll_host = ttk.Frame(root)
        gui.left_scroll_host.grid(row=0, column=0, rowspan=3, sticky="nsew", padx=(0, 8))
        gui.left_scroll_host.rowconfigure(0, weight=1)
        gui.left_scroll_host.columnconfigure(0, weight=1)
        gui.left_scroll_canvas = tk.Canvas(gui.left_scroll_host, width=420, bg="#f2f4f1", highlightthickness=0)
        gui.left_scroll_canvas.grid(row=0, column=0, sticky="nsew")
        gui.left_scrollbar = ttk.Scrollbar(gui.left_scroll_host, orient="vertical", command=gui.left_scroll_canvas.yview)
        gui.left_scrollbar.grid(row=0, column=1, sticky="ns")
        gui.left_scroll_canvas.configure(yscrollcommand=gui.left_scrollbar.set)
        left = ttk.Frame(gui.left_scroll_canvas)
        gui.left_panel = left
        gui.left_scroll_window = gui.left_scroll_canvas.create_window(0, 0, anchor="nw", window=left)
        left.bind("<Configure>", gui._update_left_scroll_region)
        gui.left_scroll_canvas.bind("<Configure>", gui._resize_left_contents)
        gui.left_scroll_canvas.bind("<MouseWheel>", gui._scroll_left_panel)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(4, weight=1)
        self._build_didactic_panel(left)
        self._build_parameter_panel(left)
        self._build_torque_panel(left)
        self._build_result_panel(left)
        self._build_conditions_panel(left)

    def _build_didactic_panel(self, left: ttk.Frame) -> None:
        gui = self.gui
        guide_box = ttk.LabelFrame(left, text="Parcours didactique")
        guide_box.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        guide_box.columnconfigure(1, weight=1)
        gui.didactic_switch = tk.Canvas(guide_box, width=38, height=20, bg="#f2f4f1", highlightthickness=0, cursor="hand2")
        gui.didactic_switch.grid(row=0, column=0, sticky="w", padx=(6, 4), pady=4)
        gui.didactic_switch.bind("<Button-1>", lambda _event: gui.toggle_didactic_mode())
        gui.didactic_label = tk.Text(guide_box, height=1, width=34, wrap="none", relief="flat", borderwidth=0, bg="#f2f4f1", fg="#22312a", font=("Helvetica", 9), padx=4, pady=4)
        gui.didactic_label.grid(row=0, column=1, sticky="ew", padx=2)
        for tag, color in (("sujet", "#16756d"), ("barre", "#b05e16"), ("charge", "#237f9f"), ("phase", "#6d5ea8"), ("pose", "#2e7d54"), ("alerte", "#c9332c")):
            gui.didactic_label.tag_configure(tag, foreground=color, font=("Helvetica", 9, "bold"))
        gui.didactic_previous_button = ttk.Button(guide_box, text="◀", command=gui.retreat_didactic_guide, width=2, style="GuideNav.TButton")
        gui.didactic_previous_button.grid(row=0, column=2, padx=(3, 1), pady=3)
        gui.didactic_next_button = ttk.Button(guide_box, text="▶", command=gui.advance_didactic_guide, width=2, style="GuideNav.TButton")
        gui.didactic_next_button.grid(row=0, column=3, padx=(1, 4), pady=3)

    def _build_parameter_panel(self, left: ttk.Frame) -> None:
        gui = self.gui
        gui.parameter_box = ttk.LabelFrame(left, text="Parametres")
        gui.parameter_box.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        gui.parameter_box.columnconfigure(0, weight=1)
        gui.parameter_box.columnconfigure(1, weight=1)
        gui.identity_box = ttk.Frame(gui.parameter_box)
        gui.identity_box.grid(row=0, column=0, sticky="nsew", padx=(4, 2), pady=3)
        for column in range(2):
            gui.identity_box.columnconfigure(column, weight=1)
        ttk.Label(gui.identity_box, text="Sujet").grid(row=0, column=0, sticky="w")
        ttk.Label(gui.identity_box, text="Prise barre").grid(row=0, column=1, sticky="w")
        gui.profile_menu = ttk.Combobox(gui.identity_box, textvariable=gui.subject_profile_var, values=SUBJECT_PROFILES, state="readonly", width=9)
        gui.profile_menu.grid(row=1, column=0, sticky="ew", padx=(0, 3))
        gui.profile_menu.bind("<<ComboboxSelected>>", lambda _event: gui.on_parameter_changed())
        gui.bar_menu = ttk.Combobox(gui.identity_box, textvariable=gui.bar_position_var, values=BAR_POSITIONS, state="readonly", width=9)
        gui.bar_menu.grid(row=1, column=1, sticky="ew", padx=(3, 0))
        gui.bar_menu.bind("<<ComboboxSelected>>", lambda _event: gui.on_parameter_changed())
        gui.charge_box = ttk.LabelFrame(gui.parameter_box, text="Charge %BW (sujet 70 kg)")
        gui.charge_box.grid(row=0, column=1, sticky="nsew", padx=(2, 4), pady=3)
        gui.charge_box.columnconfigure(0, weight=1)
        gui.load_menu = ttk.Combobox(gui.charge_box, textvariable=gui.load_display_var, values=tuple(f"{value:g} %BW" for value in self.load_percent_options), state="readonly", width=10)
        gui.load_menu.grid(row=0, column=0, sticky="ew", padx=4, pady=3)
        gui.load_menu.bind("<<ComboboxSelected>>", lambda _event: gui.on_load_menu_changed())
        self._build_duration_panel()
        self._build_lengths_panel()
        gui.parameter_options = ttk.Frame(gui.parameter_box)
        gui.parameter_options.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(3, 4))
        ttk.Checkbutton(gui.parameter_options, text="wedge 20 deg", variable=gui.wedge_var, command=gui.on_parameter_changed).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(gui.parameter_options, text="CoM segments + barre", variable=gui.show_segment_com_var, command=gui.redraw).grid(row=0, column=1, sticky="w", padx=(8, 0))

    def _build_duration_panel(self) -> None:
        gui = self.gui
        gui.duration_box = ttk.LabelFrame(gui.parameter_box, text="Durée des phases (s)")
        gui.duration_box.grid(row=1, column=0, sticky="nsew", padx=(4, 2), pady=3)
        durations = (("excent.", gui.eccentric_duration_var, DYNAMIC_PHASE_DURATION_OPTIONS), ("isomet.", gui.isometric_duration_var, ISOMETRIC_PHASE_DURATION_OPTIONS), ("concent.", gui.concentric_duration_var, DYNAMIC_PHASE_DURATION_OPTIONS))
        for column, (label, variable, values) in enumerate(durations):
            gui.duration_box.columnconfigure(column, weight=1)
            ttk.Label(gui.duration_box, text=label).grid(row=0, column=column)
            duration = ttk.Combobox(gui.duration_box, textvariable=variable, values=values, state="readonly", width=4)
            duration.grid(row=1, column=column, sticky="ew", padx=2, pady=(0, 3))
            duration.bind("<<ComboboxSelected>>", lambda _event: gui.on_duration_changed())
        gui.temporal_preset_label = ttk.Label(gui.duration_box, text="Preset temporel (Descente | Iso | Montée)")
        gui.temporal_preset_label.grid(row=2, column=0, columnspan=3, sticky="w", padx=2)
        gui.temporal_preset_menu = ttk.Combobox(gui.duration_box, textvariable=gui.temporal_preset_display_var, values=("", *(temporal_preset_display(preset) for preset in TEMPORAL_PRESETS)), state="readonly", width=30)
        gui.temporal_preset_menu.grid(row=3, column=0, columnspan=3, sticky="ew", padx=2, pady=(0, 3))
        gui.temporal_preset_menu.bind("<<ComboboxSelected>>", lambda _event: gui.apply_temporal_preset())

    def _build_lengths_panel(self) -> None:
        gui = self.gui
        gui.lengths_box = ttk.LabelFrame(gui.parameter_box, text="Longueurs (%)")
        gui.lengths_box.grid(row=1, column=1, sticky="nsew", padx=(2, 4), pady=3)
        for column, (label, variable) in enumerate((("tibia", gui.shank_var), ("cuisse", gui.thigh_var), ("tronc", gui.trunk_var))):
            gui.lengths_box.columnconfigure(column, weight=1)
            ttk.Label(gui.lengths_box, text=label).grid(row=0, column=column)
            length_menu = ttk.Combobox(gui.lengths_box, textvariable=variable, values=(-5.0, -2.5, 0.0, 2.5, 5.0), state="readonly", width=4)
            length_menu.grid(row=1, column=column, sticky="ew", padx=2, pady=(0, 3))
            length_menu.bind("<<ComboboxSelected>>", lambda _event: gui.on_parameter_changed())
        gui.anthropometry_mode_label = ttk.Label(gui.lengths_box, text="mode")
        gui.anthropometry_mode_label.grid(row=2, column=0, columnspan=3, sticky="w", padx=2)
        gui.anthropometry_mode_menu = ttk.Combobox(gui.lengths_box, textvariable=gui.anthropometry_mode_var, values=ANTHROPOMETRY_MODES, state="readonly", width=22)
        gui.anthropometry_mode_menu.grid(row=3, column=0, columnspan=3, sticky="ew", padx=2, pady=(0, 3))
        gui.anthropometry_mode_menu.bind("<<ComboboxSelected>>", lambda _event: gui.on_parameter_changed())

    def _build_torque_panel(self, left: ttk.Frame) -> None:
        gui = self.gui
        gui.torque_box = ttk.LabelFrame(left, text="Couples max")
        gui.torque_box.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        for column in range(4):
            gui.torque_box.columnconfigure(column, weight=1)
        gui.torque_box.columnconfigure(0, weight=0)
        gui.torque_preset_menu = ttk.OptionMenu(gui.torque_box, gui.torque_preset_var, gui.torque_preset_var.get(), *torque_presets(70.0, 1.70), command=lambda _value: gui.apply_torque_preset())
        gui.torque_preset_menu.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=4, pady=(3, 0))
        for column, joint in enumerate(("cheville", "genou", "hanche")):
            ttk.Label(gui.torque_box, text=joint).grid(row=0, column=column + 1, padx=4)
            entry = ttk.Entry(gui.torque_box, textvariable=gui.max_torque_vars[joint], width=7)
            entry.grid(row=1, column=column + 1, sticky="ew", padx=4)
            entry.bind("<FocusOut>", lambda _event: gui.on_parameter_changed())
            entry.bind("<Return>", lambda _event: gui.on_parameter_changed())
        torque_checks = ttk.Frame(gui.torque_box)
        torque_checks.grid(row=2, column=0, columnspan=4, sticky="ew", padx=4, pady=(4, 0))
        for column in range(3):
            torque_checks.columnconfigure(column, weight=1)
        ttk.Checkbutton(torque_checks, text="max-angle (Anderson)", variable=gui.angle_adapt_var, command=gui.on_parameter_changed).grid(row=0, column=0, sticky="w", padx=(0, 4))
        ttk.Checkbutton(torque_checks, text="max-vitesse (Anderson)", variable=gui.velocity_adapt_var, command=gui.on_parameter_changed).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Checkbutton(torque_checks, text="afficher les limites", variable=gui.show_torque_bounds_var, command=gui.redraw).grid(row=0, column=2, sticky="w", padx=(4, 0))

    def _build_result_panel(self, left: ttk.Frame) -> None:
        gui = self.gui
        gui.plot_box = ttk.LabelFrame(left, text="Resultats")
        gui.plot_box.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        for column in range(4):
            gui.plot_box.columnconfigure(column, weight=1)
        gui.plot_menu = ttk.Combobox(gui.plot_box, textvariable=gui.plot_choice, values=self.plot_choices, state="readonly")
        gui.plot_menu.grid(row=0, column=0, columnspan=4, sticky="ew", padx=4, pady=(2, 4))
        gui.plot_menu.bind("<<ComboboxSelected>>", lambda _event: gui.on_plot_choice_changed())
        for index, name in enumerate(gui.show_vars):
            checkbutton = ttk.Checkbutton(gui.plot_box, text=name, variable=gui.show_vars[name], command=gui.redraw)
            checkbutton.grid(row=1, column=index, sticky="w", padx=4)
            gui.show_checkbuttons[name] = checkbutton
        gui.quantity_menu = ttk.OptionMenu(gui.plot_box, gui.quantity_var, gui.quantity_var.get(), "position", "vitesse", "acceleration", command=lambda _value: gui.redraw())
        gui.quantity_menu.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(6, 2))
        gui.quantity_controls.append(gui.quantity_menu)
        gui.synchronized_source_menu = ttk.OptionMenu(gui.plot_box, gui.synchronized_source_var, gui.synchronized_source_var.get(), "angles articulaires", "centre de masse", command=lambda _value: gui.on_plot_choice_changed())
        gui.synchronized_source_menu.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(6, 2))
        gui.synchronized_source_menu.grid_remove()
        for index, name in enumerate(gui.com_component_vars):
            checkbutton = ttk.Checkbutton(gui.plot_box, text=name, variable=gui.com_component_vars[name], command=gui.redraw)
            checkbutton.grid(row=2, column=index + 2, sticky="w", padx=4, pady=(6, 2))
            gui.com_controls.append(checkbutton)
        for control in gui.com_controls:
            control.state(["disabled"])
        gui.phase_menu_button = ttk.Menubutton(gui.plot_box, text="Phases")
        phase_menu = tk.Menu(gui.phase_menu_button, tearoff=False)
        phase_menu.add_checkbutton(label="Afficher les limites", variable=gui.show_phase_limits_var, command=gui.redraw)
        phase_menu.add_checkbutton(label="Afficher les noms", variable=gui.show_phase_names_var, command=gui.redraw)
        gui.phase_menu_button.configure(menu=phase_menu)
        gui.phase_menu_button.grid(row=1, column=3, sticky="ew", padx=4)

    def _build_conditions_panel(self, left: ttk.Frame) -> None:
        gui = self.gui
        gui.table_box = ttk.LabelFrame(left, text="Conditions enregistrees", width=420, height=250)
        gui.table_box.grid(row=4, column=0, sticky="nsew")
        gui.table_box.grid_propagate(False)
        gui.table_box.rowconfigure(1, weight=1)
        gui.table_box.columnconfigure(0, weight=1)
        gui.table_buttons = ttk.Frame(gui.table_box)
        gui.table_buttons.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        for column in range(3):
            gui.table_buttons.columnconfigure(column, weight=1)
        gui.add_condition_button = ttk.Button(gui.table_buttons, text="Ajouter", command=gui.record_condition)
        gui.add_condition_button.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        gui.duplicate_condition_button = ttk.Button(gui.table_buttons, text="Dupliquer", command=gui.duplicate_selected_condition)
        gui.duplicate_condition_button.grid(row=0, column=1, sticky="ew", padx=3)
        gui.duplicate_condition_button.state(["disabled"])
        gui.delete_condition_button = ttk.Button(gui.table_buttons, text="Supprimer", command=gui.delete_selected_conditions)
        gui.delete_condition_button.grid(row=0, column=2, sticky="ew", padx=(3, 0))
        gui.delete_condition_button.state(["disabled"])
        self._build_condition_notebook()
        gui.file_box = ttk.Frame(gui.table_box)
        gui.file_box.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 4))
        for column in range(4):
            gui.file_box.columnconfigure(column, weight=1)
        gui.save_conditions_button = ttk.Button(gui.file_box, text="💾 Sauver", command=gui.save_json)
        gui.save_conditions_button.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        gui.load_conditions_button = ttk.Button(gui.file_box, text="📂 Charger", command=gui.load_json)
        gui.load_conditions_button.grid(row=0, column=1, sticky="ew", padx=3)
        gui.export_excel_button = ttk.Button(gui.file_box, text="▦ Excel", command=gui.export_excel)
        gui.export_excel_button.grid(row=0, column=2, sticky="ew", padx=3)
        gui.export_mp4_button = ttk.Button(gui.file_box, text="▶ MP4", command=gui.export_video)
        gui.export_mp4_button.grid(row=0, column=3, sticky="ew", padx=(3, 0))
        gui.export_csv_button = ttk.Button(gui.file_box, text="⇩ CSV combiné", command=gui.export_csv_results)
        gui.export_csv_button.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        gui.table_notebook.bind("<<NotebookTabChanged>>", gui.on_table_tab_changed)

    def _build_condition_notebook(self) -> None:
        gui = self.gui
        columns = ("numero", "profil", "prise", "squat", "charge", "phases", "wedge", "tibia", "cuisse", "tronc", "cheville", "genou", "hanche", "u_max", "limitant", "modifications")
        gui.table_notebook = ttk.Notebook(gui.table_box)
        gui.table_notebook.grid(row=1, column=0, sticky="nsew", padx=4, pady=(4, 0))
        gui.conditions_tab = ttk.Frame(gui.table_notebook)
        gui.cursor_tab = ttk.Frame(gui.table_notebook)
        gui.differences_tab = ttk.Frame(gui.table_notebook)
        gui.table_notebook.add(gui.conditions_tab, text="Conditions")
        gui.table_notebook.add(gui.cursor_tab, text="Valeurs au curseur")
        gui.table_notebook.add(gui.differences_tab, text="Variables contrôlées")
        for tab in (gui.conditions_tab, gui.cursor_tab, gui.differences_tab):
            tab.rowconfigure(0, weight=1)
            tab.columnconfigure(0, weight=1)
        gui.conditions_table = ttk.Treeview(gui.conditions_tab, columns=columns, show="headings", height=7, selectmode="extended")
        headings = {"numero": "#", "profil": "sujet", "prise": "barre", "squat": "squat deg", "charge": "%BW", "phases": "ecc/iso/con s", "wedge": "wedge", "tibia": "tibia %", "cuisse": "cuisse %", "tronc": "tronc %", "cheville": "pic chev Nm", "genou": "pic gen Nm", "hanche": "pic han Nm", "u_max": "U max", "limitant": "limitant · temps · phase · U>1", "modifications": "modifications contrôlées"}
        widths = {"numero": 34, "profil": 80, "prise": 64, "squat": 78, "charge": 48, "phases": 90, "wedge": 46, "tibia": 56, "cuisse": 60, "tronc": 56, "cheville": 76, "genou": 74, "hanche": 74, "u_max": 58, "limitant": 190, "modifications": 190}
        for column in columns:
            gui.conditions_table.heading(column, text=headings[column])
            gui.conditions_table.column(column, width=widths[column], anchor="center", stretch=True)
        gui.conditions_table.grid(row=0, column=0, sticky="nsew")
        table_scroll = ttk.Scrollbar(gui.conditions_tab, orient="horizontal", command=gui.conditions_table.xview)
        table_scroll.grid(row=1, column=0, sticky="ew")
        gui.conditions_table.configure(xscrollcommand=table_scroll.set)
        gui.conditions_table.bind("<<TreeviewSelect>>", gui.on_table_selection_changed)
        gui.conditions_table.bind("<Button-1>", gui.on_table_click)
        self._build_cursor_table()
        self._build_difference_table()

    def _build_cursor_table(self) -> None:
        gui = self.gui
        columns = ("condition", "variable", "value", "unit", "time", "phase")
        gui.cursor_table = ttk.Treeview(gui.cursor_tab, columns=columns, show="headings", height=7)
        headings = {"condition": "condition", "variable": "courbe visible", "value": "valeur", "unit": "unité", "time": "t courbe", "phase": "phase"}
        widths = {"condition": 70, "variable": 155, "value": 78, "unit": 58, "time": 72, "phase": 82}
        for column in columns:
            gui.cursor_table.heading(column, text=headings[column])
            gui.cursor_table.column(column, width=widths[column], anchor="center", stretch=True)
        gui.cursor_table.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(gui.cursor_tab, orient="vertical", command=gui.cursor_table.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        xscroll = ttk.Scrollbar(gui.cursor_tab, orient="horizontal", command=gui.cursor_table.xview)
        xscroll.grid(row=1, column=0, sticky="ew")
        gui.cursor_table.configure(yscrollcommand=scroll.set, xscrollcommand=xscroll.set)

    def _build_difference_table(self) -> None:
        gui = self.gui
        columns = ("variable", "reference", "compared")
        gui.differences_table = ttk.Treeview(gui.differences_tab, columns=columns, show="headings", height=7)
        for column, heading, width in (("variable", "paramètre modifié", 180), ("reference", "référence", 105), ("compared", "comparée", 105)):
            gui.differences_table.heading(column, text=heading)
            gui.differences_table.column(column, width=width, anchor="center", stretch=True)
        gui.differences_table.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(gui.differences_tab, orient="vertical", command=gui.differences_table.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        gui.differences_table.configure(yscrollcommand=scroll.set)

    def _build_pose_panel(self, root: ttk.Frame) -> None:
        gui = self.gui
        gui.pose_panel = ttk.Frame(root)
        gui.pose_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        gui.pose_panel.rowconfigure(0, weight=1)
        gui.pose_panel.columnconfigure(0, weight=1)
        gui.pose_canvas = tk.Canvas(gui.pose_panel, bg=self.canvas_background, highlightthickness=2, highlightbackground="#7f8f83")
        gui.pose_canvas.grid(row=0, column=0, sticky="nsew")
        gui.pose_canvas.bind("<Configure>", gui.schedule_redraw)
        gui.pose_canvas.bind("<ButtonPress-1>", gui.on_pose_press)
        gui.pose_canvas.bind("<B1-Motion>", gui.on_pose_drag)
        gui.pose_canvas.bind("<ButtonRelease-1>", gui.on_pose_release)
        gui.pose_canvas.bind("<ButtonPress-3>", gui.on_pose_context_menu)
        gui.optimize_bar_path_button = ttk.Button(gui.pose_canvas, text="Verticaliser la barre", command=gui.verticalize_bar)
        gui.optimize_bar_path_button.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor="se")
        controller = PrecisePoseAngleDialog(gui, gui.pose_canvas, apply_angle=gui.apply_clinical_joint_angle, status_message=gui.status_var.get)
        gui.pose_angle_controller = controller
        gui.pose_angle_dialog = controller.dialog
        gui.pose_angle_editor = controller.editor
        gui.pose_angle_joint_var = controller.joint_var
        gui.pose_angle_value_var = controller.value_var
        gui.pose_angle_feedback_var = controller.feedback_var
        gui.pose_angle_joint_label = controller.joint_label
        gui.pose_angle_entry = controller.entry
        gui.pose_angle_cancel_button = controller.cancel_button
        gui.pose_angle_apply_button = controller.apply_button
        gui.pose_angle_feedback_label = controller.feedback_label

    def _build_animation_panel(self, root: ttk.Frame) -> None:
        gui = self.gui
        right = ttk.Frame(root)
        gui.animation_panel = right
        right.grid(row=0, column=2, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        gui.animation_canvas = tk.Canvas(right, bg=self.canvas_background, highlightthickness=2, highlightbackground="#c9d1c7")
        gui.animation_canvas.grid(row=0, column=0, sticky="nsew")
        gui.animation_canvas.bind("<Configure>", gui.schedule_redraw)
        gui.animation_canvas.bind("<Motion>", gui.on_animation_motion)
        gui.animation_canvas.bind("<Leave>", gui.clear_animation_tooltip)
        gui.display_menu_upper_button = gui._build_display_menu(right, scope="upper")
        gui.display_menu_upper_button.place(relx=1.0, x=-8, y=8, anchor="ne")

    def _build_playback_panel(self, root: ttk.Frame) -> None:
        gui = self.gui
        playback = ttk.Frame(root)
        gui.playback_panel = playback
        playback.grid(row=1, column=1, columnspan=2, sticky="ew", pady=(2, 0))
        playback.columnconfigure(2, weight=1)
        gui.reveal_mode_menu = ttk.Combobox(playback, textvariable=gui.reveal_mode_var, values=[mode.value for mode in RevealMode], state="readonly", width=13)
        gui.reveal_mode_menu.grid(row=0, column=0, padx=(0, 8))
        gui.reveal_mode_menu.bind("<<ComboboxSelected>>", lambda _event: gui.on_reveal_mode_changed())
        gui.play_button = ttk.Button(playback, text="▶", command=gui.toggle_play, width=4)
        gui.play_button.grid(row=0, column=1, padx=(0, 8))
        gui.frame_scale = ttk.Scale(playback, variable=gui.frame_var, from_=0, to=gui.frame_count - 1, orient="horizontal", command=lambda _value: gui.redraw())
        gui.frame_scale.grid(row=0, column=2, sticky="ew")
        gui.time_mode_menu = ttk.Combobox(playback, textvariable=gui.time_mode_var, values=[mode.value for mode in TimeMode], state="readonly", width=10)
        gui.time_mode_menu.grid(row=0, column=3, padx=(8, 0))
        gui.time_mode_menu.bind("<<ComboboxSelected>>", lambda _event: gui.on_time_mode_changed())

    def _build_plot_panel(self, root: ttk.Frame) -> None:
        gui = self.gui
        panel = ttk.Frame(root)
        gui.plot_panel = panel
        panel.grid(row=2, column=1, columnspan=2, sticky="nsew", pady=(2, 0))
        panel.rowconfigure(0, weight=1)
        panel.columnconfigure(0, weight=1)
        gui.plot_canvas = tk.Canvas(panel, bg="#ffffff", highlightthickness=1, highlightbackground="#c9d1c7")
        gui.plot_canvas.grid(row=0, column=0, sticky="nsew")
        gui.plot_canvas.bind("<Configure>", gui.schedule_redraw)
        gui.plot_canvas.bind("<Button-1>", gui.on_plot_cursor_event)
        gui.plot_canvas.bind("<B1-Motion>", gui.on_plot_cursor_event)
        gui.display_menu_lower_button = gui._build_display_menu(panel, scope="lower")
        gui.display_menu_lower_button.place(relx=1.0, x=-8, y=8, anchor="ne")

    def _build_status(self, root: ttk.Frame) -> None:
        gui = self.gui
        gui.status_label = ttk.Label(root, textvariable=gui.status_var, justify="left", anchor="w")
        gui.status_label.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        root.bind("<Configure>", gui._resize_status_text)


def build_layout(
    gui: SquatGui,
    *,
    canvas_background: str,
    plot_choices: tuple[str, ...],
    load_percent_options: tuple[float, ...],
) -> None:
    """Construct all widgets for ``gui`` without coupling this module to app globals."""

    LayoutBuilder(
        gui,
        canvas_background=canvas_background,
        plot_choices=plot_choices,
        load_percent_options=load_percent_options,
    ).build()
