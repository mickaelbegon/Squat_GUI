"""Tkinter GUI for the 2D squat model."""

from __future__ import annotations

import os

os.environ.setdefault("LANG", "en_US.UTF-8")
os.environ.setdefault("LC_ALL", "en_US.UTF-8")

import tkinter as tk
from math import atan2, degrees, radians
from tkinter import ttk

from .anthropometry import Anthropometry, scale_from_percent
from .backend import BiorbdModelCache, detect_optional_backends, write_biomod_file
from .dynamics import DynamicsResult, angle_adapted_max, simulate, torque_presets
from .kinematics import MotionState, pose_from_angles
from .raster_segments import draw_sprite_segment
from .segment_shapes import draw_segment, load_segments


PLOT_CHOICES = [
    "cinematique articulaire",
    "centre de masse",
    "couples articulaires",
    "couples detailles",
    "puissances articulaires",
]

JOINT_COLORS = {"cheville": "#2e7d54", "genou": "#b46d22", "hanche": "#6d5ea8", "CoM x": "#2a8ca6", "CoM y": "#8a5a22"}
FORCE_DRAW_SCALE = 3500.0 / 3.0


class SquatGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Squat 2D - dynamique inverse")
        self.geometry("1320x820")
        self.configure(bg="#f2f4f1")

        self.final_q = (radians(22.0), radians(-58.0), radians(20.0))
        self.frame_count = 81
        self.playing = False
        self.drag_target: str | None = None
        self._redraw_pending = False
        self.states: list[MotionState] = []
        self.results: list[DynamicsResult] = []
        self.saved_condition_count = 0
        self.model_cache = BiorbdModelCache()

        self.load_var = tk.DoubleVar(value=20.0)
        self.shank_var = tk.DoubleVar(value=0.0)
        self.thigh_var = tk.DoubleVar(value=0.0)
        self.trunk_var = tk.DoubleVar(value=0.0)
        self.duration_var = tk.DoubleVar(value=1.2)
        self.frame_var = tk.IntVar(value=0)
        self.plot_choice = tk.StringVar(value=PLOT_CHOICES[0])
        self.quantity_var = tk.StringVar(value="position")
        self.show_vars = {
            "cheville": tk.BooleanVar(value=True),
            "genou": tk.BooleanVar(value=True),
            "hanche": tk.BooleanVar(value=True),
        }
        self.show_checkbuttons: dict[str, ttk.Checkbutton] = {}
        self.com_component_vars = {
            "x": tk.BooleanVar(value=True),
            "y": tk.BooleanVar(value=True),
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
        self.show_torque_bounds_var = tk.BooleanVar(value=True)
        self.show_sprite_centers_var = tk.BooleanVar(value=False)
        self.angle_adapt_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value=detect_optional_backends().message)

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
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.columnconfigure(2, weight=1)
        root.rowconfigure(1, weight=2)
        root.rowconfigure(2, weight=1)

        controls = ttk.Frame(root)
        controls.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        for index in range(10):
            controls.columnconfigure(index, weight=1)

        self._add_scale(controls, "Charge (kg)", self.load_var, 0, 100, 20, 0)
        self._add_scale(controls, "Tibia (%)", self.shank_var, -5, 5, 2.5, 1)
        self._add_scale(controls, "Cuisse (%)", self.thigh_var, -5, 5, 2.5, 2)
        self._add_scale(controls, "Tronc (%)", self.trunk_var, -5, 5, 2.5, 3)
        self._add_scale(controls, "Duree phase (s)", self.duration_var, 0.4, 3.0, 0.1, 4)

        torque_box = ttk.LabelFrame(controls, text="Couples max")
        torque_box.grid(row=0, column=5, columnspan=3, sticky="nsew", padx=6)
        for col, joint in enumerate(("cheville", "genou", "hanche")):
            ttk.Label(torque_box, text=joint).grid(row=0, column=col, padx=4)
            ttk.Entry(torque_box, textvariable=self.max_torque_vars[joint], width=7).grid(row=1, column=col, padx=4)
        ttk.OptionMenu(
            torque_box,
            self.torque_preset_var,
            self.torque_preset_var.get(),
            *torque_presets(70.0, 1.70),
            command=lambda _value: self.apply_torque_preset(),
        ).grid(row=2, column=0, columnspan=3, sticky="ew", padx=4, pady=(4, 0))
        ttk.Checkbutton(torque_box, text="max-angle", variable=self.angle_adapt_var, command=self.recompute).grid(row=3, column=0, columnspan=2)
        ttk.Checkbutton(torque_box, text="show", variable=self.show_torque_bounds_var, command=self.redraw).grid(row=3, column=2)

        plot_box = ttk.LabelFrame(controls, text="Resultats")
        plot_box.grid(row=0, column=8, columnspan=2, sticky="nsew", padx=6)
        ttk.OptionMenu(plot_box, self.plot_choice, self.plot_choice.get(), *PLOT_CHOICES, command=lambda _value: self.on_plot_choice_changed()).grid(row=0, column=0, columnspan=4, sticky="ew")
        for index, name in enumerate(self.show_vars):
            checkbutton = ttk.Checkbutton(plot_box, text=name, variable=self.show_vars[name], command=self.redraw)
            checkbutton.grid(row=1, column=index, padx=3)
            self.show_checkbuttons[name] = checkbutton
        quantity_menu = ttk.OptionMenu(plot_box, self.quantity_var, self.quantity_var.get(), "position", "vitesse", "acceleration", command=lambda _value: self.redraw())
        quantity_menu.grid(row=2, column=0, columnspan=2, sticky="ew", padx=3, pady=(4, 0))
        self.quantity_controls.append(quantity_menu)
        for index, name in enumerate(self.com_component_vars):
            checkbutton = ttk.Checkbutton(plot_box, text=f"CoM {name}", variable=self.com_component_vars[name], command=self.redraw)
            checkbutton.grid(row=2, column=index + 2, padx=3, pady=(4, 0))
            self.com_controls.append(checkbutton)
        for control in self.com_controls:
            control.state(["disabled"])
        ttk.Checkbutton(plot_box, text="centres", variable=self.show_sprite_centers_var, command=self.redraw).grid(row=3, column=0, columnspan=4)

        table_box = ttk.LabelFrame(root, text="Conditions enregistrees")
        table_box.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        table_box.rowconfigure(0, weight=1)
        table_box.columnconfigure(0, weight=1)
        columns = ("squat", "charge", "tibia", "cuisse", "tronc", "cheville", "genou", "hanche")
        self.conditions_table = ttk.Treeview(table_box, columns=columns, show="headings", height=10)
        headings = {
            "squat": "squat deg",
            "charge": "kg",
            "tibia": "tibia %",
            "cuisse": "cuisse %",
            "tronc": "tronc %",
            "cheville": "pic chev Nm",
            "genou": "pic gen Nm",
            "hanche": "pic han Nm",
        }
        widths = {"squat": 78, "charge": 52, "tibia": 58, "cuisse": 62, "tronc": 58, "cheville": 78, "genou": 76, "hanche": 76}
        for column in columns:
            self.conditions_table.heading(column, text=headings[column])
            self.conditions_table.column(column, width=widths[column], anchor="center", stretch=True)
        self.conditions_table.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        ttk.Button(table_box, text="Enregistrer", command=self.record_condition).grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 4))

        self.pose_canvas = tk.Canvas(root, bg="#fbfcf9", highlightthickness=2, highlightbackground="#7f8f83")
        self.pose_canvas.grid(row=1, column=1, sticky="nsew", padx=(0, 8))
        self.pose_canvas.bind("<Configure>", self.schedule_redraw)
        self.pose_canvas.bind("<ButtonPress-1>", self.on_pose_press)
        self.pose_canvas.bind("<B1-Motion>", self.on_pose_drag)
        self.pose_canvas.bind("<ButtonRelease-1>", self.on_pose_release)

        right = ttk.Frame(root)
        right.grid(row=1, column=2, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.animation_canvas = tk.Canvas(right, bg="#fbfcf9", highlightthickness=1, highlightbackground="#c9d1c7")
        self.animation_canvas.grid(row=0, column=0, sticky="nsew")
        self.animation_canvas.bind("<Configure>", self.schedule_redraw)

        playback = ttk.Frame(right)
        playback.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        playback.columnconfigure(1, weight=1)
        self.play_button = ttk.Button(playback, text="▶", command=self.toggle_play, width=4)
        self.play_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Scale(playback, variable=self.frame_var, from_=0, to=self.frame_count - 1, orient="horizontal", command=lambda _value: self.redraw()).grid(row=0, column=1, sticky="ew")
        ttk.Button(playback, text="Exporter bioMod", command=self.export_biomod).grid(row=0, column=2, padx=(8, 0))

        self.plot_canvas = tk.Canvas(root, bg="#ffffff", highlightthickness=1, highlightbackground="#c9d1c7")
        self.plot_canvas.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        self.plot_canvas.bind("<Configure>", self.schedule_redraw)

        ttk.Label(root, textvariable=self.status_var).grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 0))

    def _add_scale(self, parent: ttk.Frame, label: str, var: tk.DoubleVar, start: float, end: float, resolution: float, column: int) -> None:
        box = ttk.LabelFrame(parent, text=label)
        box.grid(row=0, column=column, sticky="nsew", padx=4)
        scale = ttk.Scale(box, variable=var, from_=start, to=end, orient="horizontal", command=lambda _value: self.recompute())
        scale.grid(row=0, column=0, sticky="ew", padx=4)
        value_label = ttk.Label(box, width=7)
        value_label.grid(row=1, column=0)

        def sync_label(*_args: object) -> None:
            snapped = round((var.get() - start) / resolution) * resolution + start
            snapped = min(end, max(start, snapped))
            if abs(snapped - var.get()) > 1e-6:
                var.set(snapped)
            value_label.configure(text=f"{snapped:g}")

        var.trace_add("write", sync_label)
        sync_label()

    def anthro(self) -> Anthropometry:
        return Anthropometry(
            bar_mass=self.load_var.get(),
            shank_scale=scale_from_percent(self.shank_var.get()),
            thigh_scale=scale_from_percent(self.thigh_var.get()),
            trunk_scale=scale_from_percent(self.trunk_var.get()),
        )

    def max_torques(self) -> dict[str, float]:
        return {joint: max(1.0, var.get()) for joint, var in self.max_torque_vars.items()}

    def total_motion_duration(self) -> float:
        return 2.0 * max(0.1, self.duration_var.get())

    def apply_torque_preset(self) -> None:
        preset = torque_presets(70.0, 1.70)[self.torque_preset_var.get()]
        for joint, torque in preset.torques.items():
            self.max_torque_vars[joint].set(round(torque))
        self.recompute()

    def recompute(self) -> None:
        anthro = self.anthro()
        self.states, self.results = simulate(
            anthro,
            self.final_q,
            self.total_motion_duration(),
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

    def on_plot_choice_changed(self) -> None:
        choice = self.plot_choice.get()
        quantity_plot = choice in ("cinematique articulaire", "centre de masse")
        com_plot = choice == "centre de masse"
        for checkbutton in self.show_checkbuttons.values():
            checkbutton.state(["disabled"] if com_plot else ["!disabled"])
        for control in self.quantity_controls:
            control.state(["!disabled"] if quantity_plot else ["disabled"])
        for control in self.com_controls:
            control.state(["!disabled"] if com_plot else ["disabled"])
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

    def scene_bounds(self) -> tuple[float, float, float, float]:
        anthro = self.anthro()
        return (-0.25, anthro.foot.length + anthro.shank.length + 0.65, -0.08, 1.85)

    def draw_skeleton(self, canvas: tk.Canvas, state: MotionState, result: DynamicsResult, with_handles: bool) -> None:
        bounds = self.scene_bounds()
        pose = state.pose
        joints = [pose.heel, pose.toe, pose.ankle, pose.knee, pose.hip, pose.shoulder]
        names = ["heel", "toe", "ankle", "knee", "hip", "shoulder"]
        points = {name: self.world_to_canvas(canvas, point, bounds) for name, point in zip(names, joints)}
        canvas._sprite_images = []

        def mapper(point: tuple[float, float]) -> tuple[float, float]:
            return self.world_to_canvas(canvas, point, bounds)

        raster_drawn = self.draw_raster_segments(canvas, state, mapper)
        if not raster_drawn:
            segments = load_segments()
            foot_scale = self.anthro().foot.length / 1.07
            draw_segment(canvas, segments["foot"], pose.ankle, 0.0, foot_scale, mapper)
            draw_segment(canvas, segments["shank"], pose.ankle, -state.q[0], self.anthro().shank.length, mapper)
            draw_segment(canvas, segments["thigh"], pose.knee, -state.q[1], self.anthro().thigh.length, mapper)
            draw_segment(canvas, segments["trunk_bar"], pose.hip, -state.q[2], self.anthro().trunk.length, mapper)
        canvas.create_line(*points["heel"], *points["toe"], width=3, fill="#333333")

        com = self.world_to_canvas(canvas, pose.com, bounds)
        projection = self.world_to_canvas(canvas, (pose.com[0], 0.0), bounds)
        canvas.create_line(com[0], com[1], projection[0], projection[1], fill="#3d7580", dash=(4, 4), width=1)
        canvas.create_oval(com[0] - 7, com[1] - 7, com[0] + 7, com[1] + 7, fill="#2c9ab7", outline="")
        canvas.create_oval(projection[0] - 5, projection[1] - 5, projection[0] + 5, projection[1] + 5, fill="#2c9ab7", outline="")

        cop = self.world_to_canvas(canvas, (result.cop_x, 0.0), bounds)
        force_end = self.world_to_canvas(
            canvas,
            (result.cop_x + result.ground_reaction[0] / FORCE_DRAW_SCALE, result.ground_reaction[1] / FORCE_DRAW_SCALE),
            bounds,
        )
        canvas.create_line(cop[0], cop[1], force_end[0], force_end[1], arrow=tk.LAST, width=3, fill="#c15a2b")
        for joint in (pose.knee, pose.hip):
            projected = self.project_on_force_line(joint, (result.cop_x, 0.0), result.ground_reaction)
            joint_px = self.world_to_canvas(canvas, joint, bounds)
            projected_px = self.world_to_canvas(canvas, projected, bounds)
            canvas.create_line(joint_px[0], joint_px[1], projected_px[0], projected_px[1], fill="#1f77b4", dash=(4, 4), width=2)
            canvas.create_oval(projected_px[0] - 3, projected_px[1] - 3, projected_px[0] + 3, projected_px[1] + 3, fill="#1f77b4", outline="")

        for name in ("cheville", "genou", "hanche"):
            ratio = min(1.0, result.effort_ratios[name])
            red = int(40 + 190 * ratio)
            green = int(170 * max(0.0, 1.0 - max(0.0, ratio - 0.5) * 2.0))
            color = f"#{red:02x}{green:02x}35"
            point = {"cheville": pose.ankle, "genou": pose.knee, "hanche": pose.hip}[name]
            px = self.world_to_canvas(canvas, point, bounds)
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
            return all(
                (
                    draw_sprite_segment(canvas, "foot", pose.ankle, pose.toe, mapper),
                    draw_sprite_segment(canvas, "shank", pose.ankle, pose.knee, mapper),
                    draw_sprite_segment(canvas, "thigh", pose.knee, pose.hip, mapper),
                    draw_sprite_segment(canvas, "trunk", pose.hip, pose.shoulder, mapper),
                )
            )
        except Exception:
            canvas._sprite_images = []
            return False

    def draw_pose_editor(self) -> None:
        canvas = self.pose_canvas
        canvas.delete("all")
        anthro = self.anthro()
        pose = pose_from_angles(anthro, self.final_q)
        state = MotionState(self.total_motion_duration() / 2.0, self.final_q, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), pose)
        result = self.results[len(self.results) // 2]
        if pose.com[0] < pose.heel[0] or pose.com[0] > pose.toe[0]:
            canvas.configure(highlightbackground="#c9332c")
        else:
            canvas.configure(highlightbackground="#587a5f")
        self.draw_skeleton(canvas, state, result, with_handles=True)
        self.draw_squat_angle_labels(canvas, state)
        canvas.create_text(16, 16, text="Position de squat", anchor="nw", fill="#22312a", font=("Helvetica", 13, "bold"))
        canvas.create_text(16, 38, text="Glisser genou, hanche ou epaules", anchor="nw", fill="#506158")

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
                    fill="#fbfcf9",
                    outline="#c9d1c7",
                )
                canvas.tag_lower(background, item)

    def draw_animation(self, frame: int) -> None:
        canvas = self.animation_canvas
        canvas.delete("all")
        self.draw_skeleton(canvas, self.states[frame], self.results[frame], with_handles=False)
        canvas.create_text(
            16,
            16,
            text=f"Animation {self.states[frame].phase} t={self.states[frame].time:.2f}s",
            anchor="nw",
            fill="#22312a",
            font=("Helvetica", 13, "bold"),
        )
        y = 42
        for joint in ("cheville", "genou", "hanche"):
            torque = self.results[frame].torques[joint]
            ratio = self.results[frame].effort_ratios[joint]
            canvas.create_text(16, y, text=f"{joint}: {torque: .1f} Nm ({100 * ratio: .0f}%)", anchor="nw", fill="#22312a")
            y += 20

    def draw_plot(self) -> None:
        canvas = self.plot_canvas
        canvas.delete("all")
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        pad_left, pad_top, pad_right, pad_bottom = 54, 24, 18, 36
        x0, y0 = pad_left, height - pad_bottom
        x1, y1 = width - pad_right, pad_top
        canvas.create_line(x0, y0, x1, y0, fill="#69746e")
        canvas.create_line(x0, y0, x0, y1, fill="#69746e")
        choice = self.plot_choice.get()
        series = self.plot_series(choice)
        if not series:
            return
        all_values = [value for values in series.values() for value in values]
        if choice in ("couples articulaires", "couples detailles") and self.show_torque_bounds_var.get():
            for joint, values in self.torque_bound_series().items():
                if not self.show_vars[joint].get():
                    continue
                all_values.extend(values)
                all_values.extend([-value for value in values])
        ymin = min(all_values)
        ymax = max(all_values)
        if abs(ymax - ymin) < 1e-9:
            ymin -= 1.0
            ymax += 1.0
        self.draw_y_ticks(canvas, x0, y0, y1, ymin, ymax)
        self.draw_x_ticks(canvas, x0, x1, y0)
        self.draw_time_markers(canvas, x0, x1, y0, y1)
        unit = self.plot_unit(choice)
        canvas.create_text(x1, height - 12, text="temps (s)", anchor="e", fill="#506158", font=("Helvetica", 9))
        canvas.create_text(x0 + 4, y1 - 12, text=f"y: {unit}", anchor="w", fill="#506158", font=("Helvetica", 9))
        if choice == "couples detailles":
            self.draw_detailed_torque_plot(canvas, series, x0, x1, y0, y1, ymin, ymax)
            self.draw_torque_bounds(canvas, x0, x1, y0, y1, ymin, ymax)
            canvas.create_text(16, 12, text=f"{choice} ({unit})", anchor="nw", fill="#22312a", font=("Helvetica", 12, "bold"))
            return
        colors = JOINT_COLORS
        palette = ["#2e7d54", "#b46d22", "#6d5ea8", "#2a8ca6", "#9b3d3d", "#4c6f3d", "#8a5a22"]
        for series_index, (name, values) in enumerate(series.items()):
            color = colors.get(name, palette[series_index % len(palette)])
            points = []
            for index, value in enumerate(values):
                x = x0 + (x1 - x0) * index / max(1, len(values) - 1)
                y = y0 - (y0 - y1) * (value - ymin) / (ymax - ymin)
                points.extend([x, y])
            if len(points) >= 4:
                canvas.create_line(*points, fill=color, width=2)
        self.draw_torque_bounds(canvas, x0, x1, y0, y1, ymin, ymax)
        canvas.create_text(16, 12, text=f"{choice} ({unit})", anchor="nw", fill="#22312a", font=("Helvetica", 12, "bold"))
        legend_x = x0
        for series_index, name in enumerate(series):
            color = colors.get(name, palette[series_index % len(palette)])
            canvas.create_line(legend_x, height - 14, legend_x + 18, height - 14, fill=color, width=3)
            canvas.create_text(legend_x + 24, height - 14, text=name, anchor="w", fill="#22312a")
            legend_x += max(95, 9 * len(name))

    def draw_y_ticks(self, canvas: tk.Canvas, x0: float, y0: float, y1: float, ymin: float, ymax: float) -> None:
        for index in range(5):
            fraction = index / 4
            value = ymin + fraction * (ymax - ymin)
            y = y0 - (y0 - y1) * fraction
            canvas.create_line(x0 - 4, y, x0, y, fill="#69746e")
            canvas.create_line(x0, y, canvas.winfo_width() - 18, y, fill="#edf0ec")
            canvas.create_text(x0 - 8, y, text=self.format_axis_value(value), anchor="e", fill="#506158", font=("Helvetica", 9))

    def draw_x_ticks(self, canvas: tk.Canvas, x0: float, x1: float, y0: float) -> None:
        duration = self.total_motion_duration()
        for index in range(5):
            fraction = index / 4
            x = x0 + (x1 - x0) * fraction
            value = duration * fraction
            canvas.create_line(x, y0, x, y0 + 4, fill="#69746e")
            canvas.create_text(x, y0 + 16, text=self.format_axis_value(value), anchor="n", fill="#506158", font=("Helvetica", 9))

    def draw_time_markers(self, canvas: tk.Canvas, x0: float, x1: float, y0: float, y1: float) -> None:
        midpoint_x = x0 + 0.5 * (x1 - x0)
        canvas.create_line(midpoint_x, y0, midpoint_x, y1, fill="#59645e", width=1, dash=(6, 5))
        canvas.create_text(midpoint_x + 4, y1 + 4, text="milieu", anchor="nw", fill="#59645e", font=("Helvetica", 9))

        frame = min(self.frame_count - 1, max(0, int(self.frame_var.get())))
        fraction = frame / max(1, self.frame_count - 1)
        animation_x = x0 + (x1 - x0) * fraction
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
        if choice in ("couples articulaires", "couples detailles"):
            return "Nm"
        return "W"

    def draw_torque_bounds(self, canvas: tk.Canvas, x0: float, x1: float, y0: float, y1: float, ymin: float, ymax: float) -> None:
        if self.plot_choice.get() not in ("couples articulaires", "couples detailles") or not self.show_torque_bounds_var.get():
            return
        for joint, values in self.torque_bound_series().items():
            if not self.show_vars[joint].get():
                continue
            color = JOINT_COLORS[joint]
            for sign in (1.0, -1.0):
                points = []
                for index, value in enumerate(values):
                    x = x0 + (x1 - x0) * index / max(1, len(values) - 1)
                    y = y0 - (y0 - y1) * (sign * value - ymin) / (ymax - ymin)
                    points.extend([x, y])
                if len(points) >= 4:
                    canvas.create_line(*points, fill=color, width=1, dash=(6, 5))

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
        for joint in ("cheville", "genou", "hanche"):
            if joint not in self.show_vars or not self.show_vars[joint].get():
                continue
            color = JOINT_COLORS[joint]
            sum_values = series.get(f"{joint} somme", [])
            contact_values = series.get(f"{joint} contact", [])
            self.draw_series_line(canvas, sum_values, x0, x1, y0, y1, ymin, ymax, color, width=2)
            self.draw_triangle_markers(canvas, contact_values, x0, x1, y0, y1, ymin, ymax, color)
            canvas.create_line(legend_x, canvas.winfo_height() - 14, legend_x + 18, canvas.winfo_height() - 14, fill=color, width=3)
            canvas.create_text(legend_x + 24, canvas.winfo_height() - 14, text=joint, anchor="w", fill="#22312a")
            legend_x += 95

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
    ) -> None:
        points = []
        for index, value in enumerate(values):
            x = x0 + (x1 - x0) * index / max(1, len(values) - 1)
            y = y0 - (y0 - y1) * (value - ymin) / (ymax - ymin)
            points.extend([x, y])
        if len(points) >= 4:
            canvas.create_line(*points, fill=color, width=width)

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
    ) -> None:
        step = max(1, len(values) // 18)
        for index, value in enumerate(values):
            if index % step != 0 and index != len(values) - 1:
                continue
            x = x0 + (x1 - x0) * index / max(1, len(values) - 1)
            y = y0 - (y0 - y1) * (value - ymin) / (ymax - ymin)
            canvas.create_polygon(x, y - 5, x - 5, y + 5, x + 5, y + 5, fill=color, outline=color)

    def plot_series(self, choice: str) -> dict[str, list[float]]:
        selected = [name for name, var in self.show_vars.items() if var.get()]
        data: dict[str, list[float]] = {}
        if choice == "cinematique articulaire":
            values = self.joint_kinematic_series()
        elif choice == "centre de masse":
            return self.com_plot_series()
        elif choice == "couples articulaires":
            values = {joint: [result.torques[joint] for result in self.results] for joint in ("cheville", "genou", "hanche")}
        elif choice == "couples detailles":
            values = {}
            for joint in ("cheville", "genou", "hanche"):
                if joint in selected:
                    values[f"{joint} somme"] = [result.torques[joint] for result in self.results]
                    values[f"{joint} contact"] = [result.torque_components[joint]["contact"] for result in self.results]
            return values
        else:
            values = {joint: [result.powers[joint] for result in self.results] for joint in ("cheville", "genou", "hanche")}
        for name in selected:
            if name in values:
                data[name] = values[name]
        return data

    def joint_kinematic_series(self) -> dict[str, list[float]]:
        quantity = self.quantity_var.get()
        if quantity == "position":
            return {
                "cheville": [degrees(state.q[0]) for state in self.states],
                "genou": [degrees(state.q[1] - state.q[0]) for state in self.states],
                "hanche": [degrees(state.q[2] - state.q[1]) for state in self.states],
            }
        if quantity == "vitesse":
            return {
                "cheville": [degrees(state.qdot[0]) for state in self.states],
                "genou": [degrees(state.qdot[1] - state.qdot[0]) for state in self.states],
                "hanche": [degrees(state.qdot[2] - state.qdot[1]) for state in self.states],
            }
        return {
            "cheville": [degrees(state.qddot[0]) for state in self.states],
            "genou": [degrees(state.qddot[1] - state.qddot[0]) for state in self.states],
            "hanche": [degrees(state.qddot[2] - state.qddot[1]) for state in self.states],
        }

    def com_plot_series(self) -> dict[str, list[float]]:
        quantity = self.quantity_var.get()
        source = {
            "position": [result.com for result in self.results],
            "vitesse": [result.com_velocity for result in self.results],
            "acceleration": [result.com_acceleration for result in self.results],
        }[quantity]
        data: dict[str, list[float]] = {}
        if self.com_component_vars["x"].get():
            data["CoM x"] = [value[0] for value in source]
        if self.com_component_vars["y"].get():
            data["CoM y"] = [value[1] for value in source]
        return data

    def torque_bound_series(self) -> dict[str, list[float]]:
        bounds: dict[str, list[float]] = {}
        max_torques = self.max_torques()
        for joint in ("cheville", "genou", "hanche"):
            values = []
            for state in self.states:
                joint_angle = {
                    "cheville": abs(state.q[0]),
                    "genou": abs(state.q[1] - state.q[0]),
                    "hanche": abs(state.q[2] - state.q[1]),
                }[joint]
                eccentric_factor = 1.35 if state.phase == "excentrique" else 1.0
                values.append(eccentric_factor * angle_adapted_max(max_torques[joint], joint_angle, self.angle_adapt_var.get(), joint))
            bounds[joint] = values
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
        self.final_q = (
            max(radians(-55), min(radians(75), shank)),
            max(radians(-95), min(radians(45), thigh)),
            max(radians(-120), min(radians(50), trunk)),
        )
        self.recompute()

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

    def export_biomod(self) -> None:
        path = write_biomod_file("generated/squat_2d.bioMod", self.anthro())
        self.status_var.set(f"modele ecrit: {path}")

    def record_condition(self) -> None:
        self.saved_condition_count += 1
        peak_torques = {
            joint: max(abs(result.torques[joint]) for result in self.results)
            for joint in ("cheville", "genou", "hanche")
        }
        squat_angles = (
            degrees(self.final_q[0]),
            degrees(self.final_q[1] - self.final_q[0]),
            degrees(self.final_q[2] - self.final_q[1]),
        )
        self.conditions_table.insert(
            "",
            "end",
            iid=f"condition-{self.saved_condition_count}",
            values=(
                f"{squat_angles[0]:.0f}/{squat_angles[1]:.0f}/{squat_angles[2]:.0f}",
                f"{self.load_var.get():.0f}",
                f"{self.shank_var.get():+.1f}",
                f"{self.thigh_var.get():+.1f}",
                f"{self.trunk_var.get():+.1f}",
                f"{peak_torques['cheville']:.1f}",
                f"{peak_torques['genou']:.1f}",
                f"{peak_torques['hanche']:.1f}",
            ),
        )
        self.status_var.set(f"condition {self.saved_condition_count} enregistree")


def main() -> None:
    app = SquatGui()
    app.mainloop()
