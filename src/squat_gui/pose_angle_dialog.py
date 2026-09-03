"""Tkinter controller for the precise clinical pose-angle editor.

The widget lifecycle and focus policy live here so the main application only
provides the current pose and commits a validated value.  Numeric parsing and
joint limits remain in :mod:`squat_gui.pose_editing`.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from .pose_editing import SegmentAngles, clinical_angle_editor_spec, format_pose_angle

ApplyClinicalAngle = Callable[[str, str], bool]
StatusMessage = Callable[[], str]


class PrecisePoseAngleDialog:
    """Non-modal dialog that edits one clinical joint angle at a time."""

    def __init__(
        self,
        parent: tk.Misc,
        pose_canvas: tk.Canvas,
        *,
        apply_angle: ApplyClinicalAngle,
        status_message: StatusMessage,
    ) -> None:
        self._parent = parent
        self._pose_canvas = pose_canvas
        self._apply_angle = apply_angle
        self._status_message = status_message
        self.active_joint: str | None = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.withdraw()
        self.dialog.transient(parent)
        self.dialog.resizable(False, False)
        self.dialog.protocol("WM_DELETE_WINDOW", self.close)

        self.editor = ttk.LabelFrame(self.dialog, text="Angle articulaire", padding=(8, 5))
        self.editor.grid(row=0, column=0, sticky="nsew")
        self.editor.columnconfigure(1, weight=1)
        self.joint_var = tk.StringVar(value="")
        self.value_var = tk.StringVar(value="")
        self.feedback_var = tk.StringVar(value="")
        self.joint_label = ttk.Label(
            self.editor,
            textvariable=self.joint_var,
            font=("Helvetica", 10, "bold"),
        )
        self.joint_label.grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(self.editor, text="Valeur précise (deg) :").grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )
        self.entry = ttk.Entry(
            self.editor,
            textvariable=self.value_var,
            width=12,
            justify="right",
        )
        self.entry.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(4, 0))
        self.entry.bind("<Return>", self.confirm)
        self.entry.bind("<KP_Enter>", self.confirm)
        self.entry.bind("<Escape>", lambda _event: self.close())
        self.cancel_button = ttk.Button(self.editor, text="Annuler", command=self.close)
        self.cancel_button.grid(row=1, column=2, padx=(6, 0), pady=(4, 0))
        self.apply_button = ttk.Button(self.editor, text="Valider", command=self.confirm)
        self.apply_button.grid(row=1, column=3, padx=(6, 0), pady=(4, 0))
        self.feedback_label = ttk.Label(
            self.editor,
            textvariable=self.feedback_var,
            foreground="#c83d3d",
        )
        self.feedback_label.grid(row=2, column=0, columnspan=4, sticky="w", pady=(3, 0))
        self.dialog.bind("<Return>", self.confirm)
        self.dialog.bind("<KP_Enter>", self.confirm)
        self.dialog.bind("<Escape>", lambda _event: self.close())

    def synchronize(self, q: SegmentAngles) -> None:
        """Refresh an open editor after a drag without committing input."""

        if self.active_joint is not None:
            spec = clinical_angle_editor_spec(self.active_joint, q)
            self.value_var.set(format_pose_angle(spec.value_deg))

    def open(self, joint: str, q: SegmentAngles) -> None:
        """Replace any pending edit with ``joint`` and position the dialog."""

        spec = clinical_angle_editor_spec(joint, q)
        self.active_joint = joint
        self.joint_var.set(spec.display_label)
        self.value_var.set(format_pose_angle(spec.value_deg))
        self.feedback_var.set("")
        self.dialog.title(f"Angle — {spec.label}")
        self.dialog.deiconify()
        self.dialog.lift(self._parent)
        self.dialog.update_idletasks()
        x = self._pose_canvas.winfo_rootx() + max(
            16,
            (self._pose_canvas.winfo_width() - self.dialog.winfo_reqwidth()) // 2,
        )
        y = self._pose_canvas.winfo_rooty() + max(
            32, self._pose_canvas.winfo_height() - 52
        )
        self.dialog.geometry(f"+{x}+{y}")
        self._parent.after_idle(lambda: self._focus_editor(joint))

    def _focus_editor(self, joint: str) -> None:
        if self.active_joint == joint and self.dialog.winfo_viewable():
            self.dialog.focus_force()
            self.entry.focus_force()
            self.entry.selection_range(0, tk.END)

    def confirm(self, _event: tk.Event | None = None) -> str | None:
        """Commit only on explicit validation or Enter."""

        joint = self.active_joint
        if joint is None:
            return "break"
        if self._apply_angle(joint, self.value_var.get()):
            self.close()
            return "break"
        self.feedback_var.set(self._status_message())
        self.entry.focus_set()
        self.entry.selection_range(0, tk.END)
        return "break"

    def close(self) -> None:
        """Discard the pending value and hide the window."""

        self.active_joint = None
        self.feedback_var.set("")
        self.dialog.withdraw()
