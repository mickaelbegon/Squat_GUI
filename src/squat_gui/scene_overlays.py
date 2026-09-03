"""Biomechanical alerts and scientific canvas overlays."""

from __future__ import annotations

import tkinter as tk
from math import degrees

from .anthropometry import Anthropometry
from .dynamics import DynamicsResult, force_balance
from .kinematics import MotionState
from .observables import neighbor_samples, segment_anthropometry, support_margins
from .scene_styles import ALERT_BG, ALERT_BORDER, CANVAS_BG, OK_BORDER


class SceneOverlayMixin:
    """Draw alerts and explanatory biomechanical overlays."""

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
        if not self.app.support_point_in_functional_base(state, result):
            alerts.append(
                f"{result.support_point_label} hors zone fonctionnelle d'appui"
            )
        if include_com and not self.app.com_projection_in_foot(state):
            alerts.append("CoM hors pied")
        over_limit = self.app.over_limit_joints(result)
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
        text = "Problèmes biomécaniques :\n" + "\n".join(
            f"• {alert}" for alert in alerts
        )
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
