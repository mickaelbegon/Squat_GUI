"""Tkinter GUI for the 2D squat model."""

from __future__ import annotations

import os

os.environ.setdefault("LANG", "en_US.UTF-8")
os.environ.setdefault("LC_ALL", "en_US.UTF-8")

import tkinter as tk
from math import atan2, degrees, radians
from tkinter import ttk

from .anthropometry import Anthropometry, scale_from_percent
from .backend import detect_optional_backends, write_biomod_file
from .dynamics import DynamicsResult, simulate, total_com_acceleration
from .kinematics import MotionState, com_accelerations, pose_from_angles


PLOT_CHOICES = [
    "positions articulaires",
    "vitesses articulaires",
    "accelerations articulaires",
    "couples articulaires",
    "couples detailles",
    "puissances articulaires",
]


class SquatGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Squat 2D - dynamique inverse")
        self.geometry("1320x820")
        self.configure(bg="#f2f4f1")

        self.final_q = (radians(22.0), radians(-58.0), radians(-18.0))
        self.frame_count = 81
        self.playing = False
        self.drag_target: str | None = None
        self.states: list[MotionState] = []
        self.results: list[DynamicsResult] = []

        self.load_var = tk.DoubleVar(value=20.0)
        self.shank_var = tk.DoubleVar(value=0.0)
        self.thigh_var = tk.DoubleVar(value=0.0)
        self.trunk_var = tk.DoubleVar(value=0.0)
        self.duration_var = tk.DoubleVar(value=1.2)
        self.frame_var = tk.IntVar(value=0)
        self.plot_choice = tk.StringVar(value=PLOT_CHOICES[0])
        self.show_vars = {
            "cheville": tk.BooleanVar(value=True),
            "genou": tk.BooleanVar(value=True),
            "hanche": tk.BooleanVar(value=True),
            "CoM": tk.BooleanVar(value=True),
        }
        self.max_torque_vars = {
            "cheville": tk.DoubleVar(value=180.0),
            "genou": tk.DoubleVar(value=220.0),
            "hanche": tk.DoubleVar(value=260.0),
        }
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
        root.rowconfigure(1, weight=1)

        controls = ttk.Frame(root)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        for index in range(10):
            controls.columnconfigure(index, weight=1)

        self._add_scale(controls, "Charge (kg)", self.load_var, 0, 100, 20, 0)
        self._add_scale(controls, "Tibia (%)", self.shank_var, -5, 5, 2.5, 1)
        self._add_scale(controls, "Cuisse (%)", self.thigh_var, -5, 5, 2.5, 2)
        self._add_scale(controls, "Tronc (%)", self.trunk_var, -5, 5, 2.5, 3)
        self._add_scale(controls, "Duree (s)", self.duration_var, 0.4, 3.0, 0.1, 4)

        torque_box = ttk.LabelFrame(controls, text="Couples max")
        torque_box.grid(row=0, column=5, columnspan=3, sticky="nsew", padx=6)
        for col, joint in enumerate(("cheville", "genou", "hanche")):
            ttk.Label(torque_box, text=joint).grid(row=0, column=col, padx=4)
            ttk.Entry(torque_box, textvariable=self.max_torque_vars[joint], width=7).grid(row=1, column=col, padx=4)
        ttk.Checkbutton(torque_box, text="max-angle", variable=self.angle_adapt_var, command=self.recompute).grid(row=2, column=0, columnspan=3)

        plot_box = ttk.LabelFrame(controls, text="Resultats")
        plot_box.grid(row=0, column=8, columnspan=2, sticky="nsew", padx=6)
        ttk.OptionMenu(plot_box, self.plot_choice, self.plot_choice.get(), *PLOT_CHOICES, command=lambda _value: self.redraw()).grid(row=0, column=0, columnspan=4, sticky="ew")
        for index, name in enumerate(self.show_vars):
            ttk.Checkbutton(plot_box, text=name, variable=self.show_vars[name], command=self.redraw).grid(row=1, column=index, padx=3)

        left = ttk.Frame(root)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        left.rowconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        self.pose_canvas = tk.Canvas(left, bg="#fbfcf9", highlightthickness=2, highlightbackground="#7f8f83")
        self.pose_canvas.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        self.pose_canvas.bind("<ButtonPress-1>", self.on_pose_press)
        self.pose_canvas.bind("<B1-Motion>", self.on_pose_drag)
        self.pose_canvas.bind("<ButtonRelease-1>", self.on_pose_release)

        self.plot_canvas = tk.Canvas(left, bg="#ffffff", highlightthickness=1, highlightbackground="#c9d1c7")
        self.plot_canvas.grid(row=1, column=0, sticky="nsew")

        right = ttk.Frame(root)
        right.grid(row=1, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.animation_canvas = tk.Canvas(right, bg="#fbfcf9", highlightthickness=1, highlightbackground="#c9d1c7")
        self.animation_canvas.grid(row=0, column=0, sticky="nsew")

        playback = ttk.Frame(right)
        playback.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        playback.columnconfigure(1, weight=1)
        self.play_button = ttk.Button(playback, text="▶", command=self.toggle_play, width=4)
        self.play_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Scale(playback, variable=self.frame_var, from_=0, to=self.frame_count - 1, orient="horizontal", command=lambda _value: self.redraw()).grid(row=0, column=1, sticky="ew")
        ttk.Button(playback, text="bioMod", command=self.export_biomod).grid(row=0, column=2, padx=(8, 0))

        ttk.Label(root, textvariable=self.status_var).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

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

    def recompute(self) -> None:
        self.states, self.results = simulate(
            self.anthro(),
            self.final_q,
            max(0.1, self.duration_var.get()),
            self.frame_count,
            self.max_torques(),
            self.angle_adapt_var.get(),
        )
        self.redraw()

    def redraw(self) -> None:
        if not self.states:
            return
        frame = min(self.frame_count - 1, max(0, int(self.frame_var.get())))
        self.draw_pose_editor()
        self.draw_plot()
        self.draw_animation(frame)

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
        canvas.create_line(*points["heel"], *points["toe"], width=5, fill="#333333")
        for a, b in (("ankle", "knee"), ("knee", "hip"), ("hip", "shoulder")):
            canvas.create_line(*points[a], *points[b], width=7, fill="#33443b", capstyle="round")
        canvas.create_line(points["shoulder"][0] - 28, points["shoulder"][1], points["shoulder"][0] + 28, points["shoulder"][1], width=8, fill="#6d5f57", capstyle="round")

        com = self.world_to_canvas(canvas, pose.com, bounds)
        projection = self.world_to_canvas(canvas, (pose.com[0], 0.0), bounds)
        canvas.create_line(com[0], com[1], projection[0], projection[1], fill="#3d7580", dash=(4, 4), width=1)
        canvas.create_oval(com[0] - 7, com[1] - 7, com[0] + 7, com[1] + 7, fill="#2c9ab7", outline="")
        canvas.create_oval(projection[0] - 5, projection[1] - 5, projection[0] + 5, projection[1] + 5, fill="#2c9ab7", outline="")

        cop = self.world_to_canvas(canvas, (result.cop_x, 0.0), bounds)
        force_end = self.world_to_canvas(canvas, (result.cop_x + result.ground_reaction[0] / 3500.0, result.ground_reaction[1] / 3500.0), bounds)
        canvas.create_line(cop[0], cop[1], force_end[0], force_end[1], arrow=tk.LAST, width=3, fill="#c15a2b")
        for joint in (pose.ankle, pose.knee, pose.hip):
            joint_px = self.world_to_canvas(canvas, joint, bounds)
            canvas.create_line(joint_px[0], joint_px[1], force_end[0], force_end[1], fill="#8f8f8f", dash=(3, 5))

        for name in ("cheville", "genou", "hanche"):
            ratio = min(1.0, result.effort_ratios[name])
            red = int(40 + 190 * ratio)
            green = int(170 * max(0.0, 1.0 - max(0.0, ratio - 0.5) * 2.0))
            color = f"#{red:02x}{green:02x}35"
            point = {"cheville": pose.ankle, "genou": pose.knee, "hanche": pose.hip}[name]
            px = self.world_to_canvas(canvas, point, bounds)
            canvas.create_oval(px[0] - 12, px[1] - 12, px[0] + 12, px[1] + 12, outline=color, width=4)

        if with_handles:
            for name in ("knee", "hip", "shoulder"):
                x, y = points[name]
                canvas.create_oval(x - 9, y - 9, x + 9, y + 9, fill="#f7f7f2", outline="#1d3d35", width=2, tags=name)

    def draw_pose_editor(self) -> None:
        canvas = self.pose_canvas
        canvas.delete("all")
        anthro = self.anthro()
        pose = pose_from_angles(anthro, self.final_q)
        state = MotionState(self.duration_var.get(), self.final_q, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), pose)
        result = self.results[-1]
        if pose.com[0] < pose.heel[0] or pose.com[0] > pose.toe[0]:
            canvas.configure(highlightbackground="#c9332c")
        else:
            canvas.configure(highlightbackground="#587a5f")
        self.draw_skeleton(canvas, state, result, with_handles=True)
        canvas.create_text(16, 16, text="Position finale", anchor="nw", fill="#22312a", font=("Helvetica", 13, "bold"))
        canvas.create_text(16, 38, text="Glisser genou, hanche ou epaules", anchor="nw", fill="#506158")

    def draw_animation(self, frame: int) -> None:
        canvas = self.animation_canvas
        canvas.delete("all")
        self.draw_skeleton(canvas, self.states[frame], self.results[frame], with_handles=False)
        canvas.create_text(16, 16, text=f"Animation t={self.states[frame].time:.2f}s", anchor="nw", fill="#22312a", font=("Helvetica", 13, "bold"))
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
        ymin = min(all_values)
        ymax = max(all_values)
        if abs(ymax - ymin) < 1e-9:
            ymin -= 1.0
            ymax += 1.0
        colors = {"cheville": "#2e7d54", "genou": "#b46d22", "hanche": "#6d5ea8", "CoM": "#2a8ca6"}
        for name, values in series.items():
            points = []
            for index, value in enumerate(values):
                x = x0 + (x1 - x0) * index / max(1, len(values) - 1)
                y = y0 - (y0 - y1) * (value - ymin) / (ymax - ymin)
                points.extend([x, y])
            if len(points) >= 4:
                canvas.create_line(*points, fill=colors.get(name, "#222222"), width=2)
        canvas.create_text(16, 12, text=choice, anchor="nw", fill="#22312a", font=("Helvetica", 12, "bold"))
        legend_x = x0
        for name in series:
            canvas.create_line(legend_x, height - 14, legend_x + 18, height - 14, fill=colors.get(name, "#222222"), width=3)
            canvas.create_text(legend_x + 24, height - 14, text=name, anchor="w", fill="#22312a")
            legend_x += 95

    def plot_series(self, choice: str) -> dict[str, list[float]]:
        selected = [name for name, var in self.show_vars.items() if var.get()]
        data: dict[str, list[float]] = {}
        if choice == "positions articulaires":
            values = {
                "cheville": [degrees(state.q[0]) for state in self.states],
                "genou": [degrees(state.q[1] - state.q[0]) for state in self.states],
                "hanche": [degrees(state.q[2] - state.q[1]) for state in self.states],
                "CoM": [state.pose.com[1] for state in self.states],
            }
        elif choice == "vitesses articulaires":
            values = {
                "cheville": [degrees(state.qdot[0]) for state in self.states],
                "genou": [degrees(state.qdot[1] - state.qdot[0]) for state in self.states],
                "hanche": [degrees(state.qdot[2] - state.qdot[1]) for state in self.states],
                "CoM": self.com_velocity_series(),
            }
        elif choice == "accelerations articulaires":
            values = {
                "cheville": [degrees(state.qddot[0]) for state in self.states],
                "genou": [degrees(state.qddot[1] - state.qddot[0]) for state in self.states],
                "hanche": [degrees(state.qddot[2] - state.qddot[1]) for state in self.states],
                "CoM": self.com_acceleration_series(),
            }
        elif choice == "couples articulaires":
            values = {joint: [result.torques[joint] for result in self.results] for joint in ("cheville", "genou", "hanche")}
        elif choice == "couples detailles":
            values = {}
            for joint in ("cheville", "genou", "hanche"):
                if joint in selected:
                    values[f"{joint} Mqddot"] = [result.torque_components[joint]["Mqddot"] for result in self.results]
                    values[f"{joint} NLeffects"] = [result.torque_components[joint]["NLeffects"] for result in self.results]
                    values[f"{joint} contact"] = [result.torque_components[joint]["contact"] for result in self.results]
            return values
        else:
            values = {joint: [result.powers[joint] for result in self.results] for joint in ("cheville", "genou", "hanche")}
        for name in selected:
            if name in values:
                data[name] = values[name]
        return data

    def com_velocity_series(self) -> list[float]:
        if len(self.states) < 2:
            return [0.0 for _ in self.states]
        values: list[float] = []
        for index, state in enumerate(self.states):
            if index == 0:
                dt = self.states[1].time - state.time
                values.append((self.states[1].pose.com[1] - state.pose.com[1]) / dt)
            elif index == len(self.states) - 1:
                dt = state.time - self.states[index - 1].time
                values.append((state.pose.com[1] - self.states[index - 1].pose.com[1]) / dt)
            else:
                dt = self.states[index + 1].time - self.states[index - 1].time
                values.append((self.states[index + 1].pose.com[1] - self.states[index - 1].pose.com[1]) / dt)
        return values

    def com_acceleration_series(self) -> list[float]:
        anthro = self.anthro()
        values = []
        for state in self.states:
            accs = com_accelerations(anthro, state.q, state.qdot, state.qddot)
            values.append(total_com_acceleration(anthro, accs)[1])
        return values

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
            max(radians(-70), min(radians(35), trunk)),
        )
        self.recompute()

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


def main() -> None:
    app = SquatGui()
    app.mainloop()
