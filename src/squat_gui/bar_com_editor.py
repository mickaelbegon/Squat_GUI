"""Small GUI for manually locating the bar centre of mass on trunk sprites."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from math import hypot
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .raster_segments import ASSET_DIR, TRUNK_VARIANTS, SpriteSpec, sprite_spec


OUTPUT_PATH = ASSET_DIR / "bar_com_points.json"
CANVAS_SIZE = (780, 720)


@dataclass(frozen=True)
class CalibrationImage:
    quality: str
    refined: bool
    subject_profile: str
    bar_position: str
    filename: str

    @property
    def key(self) -> str:
        return f"{self.quality}/{self.subject_profile.replace(' ', '_')}/{self.bar_position}"

    @property
    def path(self) -> Path:
        directory = ASSET_DIR / "refined" if self.refined else ASSET_DIR
        return directory / self.filename

    @property
    def label(self) -> str:
        return f"{self.quality} | {self.subject_profile} | {self.bar_position}"


def calibration_images() -> tuple[CalibrationImage, ...]:
    images: list[CalibrationImage] = []
    for quality, refined in (("low_quality", False), ("refined", True)):
        for subject_profile in ("homme", "femme enceinte"):
            for bar_position in ("front", "back", "over-head"):
                images.append(
                    CalibrationImage(
                        quality,
                        refined,
                        subject_profile,
                        bar_position,
                        TRUNK_VARIANTS[(subject_profile, bar_position)],
                    )
                )
    return tuple(images)


def point_relative_to_shoulder(point: tuple[float, float], spec: SpriteSpec) -> tuple[float, float]:
    """Return anterior and longitudinal offsets expressed in trunk lengths."""
    axis = (
        spec.proximal_anchor[0] - spec.distal_anchor[0],
        spec.proximal_anchor[1] - spec.distal_anchor[1],
    )
    length = hypot(axis[0], axis[1])
    if length <= 0.0:
        raise ValueError("The trunk anchors cannot occupy the same pixel.")
    longitudinal = (axis[0] / length, axis[1] / length)
    anterior = (-longitudinal[1], longitudinal[0])
    delta = (point[0] - spec.proximal_anchor[0], point[1] - spec.proximal_anchor[1])
    return (
        (delta[0] * anterior[0] + delta[1] * anterior[1]) / length,
        (delta[0] * longitudinal[0] + delta[1] * longitudinal[1]) / length,
    )


def calibration_payload(points: dict[str, tuple[float, float]]) -> dict[str, object]:
    from PIL import Image

    entries: list[dict[str, object]] = []
    for item in calibration_images():
        spec = sprite_spec("trunk", item.refined, (item.subject_profile, item.bar_position))
        with Image.open(item.path) as source:
            width, height = source.size
        point = points.get(item.key)
        entry: dict[str, object] = {
            "id": item.key,
            "quality": item.quality,
            "subject_profile": item.subject_profile,
            "bar_position": item.bar_position,
            "image": str(item.path.relative_to(ASSET_DIR.parent.parent)),
            "image_size_px": [width, height],
            "bar_com_pixel": None,
            "bar_com_normalized": None,
            "relative_to_shoulder_in_trunk_lengths": None,
        }
        if point is not None:
            anterior, longitudinal = point_relative_to_shoulder(point, spec)
            entry["bar_com_pixel"] = [round(point[0], 3), round(point[1], 3)]
            entry["bar_com_normalized"] = [round(point[0] / width, 6), round(point[1] / height, 6)]
            entry["relative_to_shoulder_in_trunk_lengths"] = {
                "anterior": round(anterior, 6),
                "longitudinal": round(longitudinal, 6),
            }
        entries.append(entry)
    return {
        "version": 1,
        "description": "Manual positions of the bar centre of mass on each trunk sprite.",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "placed_count": len(points),
        "expected_count": len(entries),
        "entries": entries,
    }


class BarComEditor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Calibration du CoM de la barre")
        self.geometry("1040x820")
        self.minsize(900, 700)
        self.items = calibration_images()
        self.index = 0
        self.points: dict[str, tuple[float, float]] = {}
        self.photo = None
        self.image_origin = (0.0, 0.0)
        self.image_scale = 1.0

        self.choice_var = tk.StringVar()
        self.coordinate_var = tk.StringVar()
        self.progress_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Cliquer au centre de la barre dessinee.")
        self._build_layout()
        self.show_item(0)

    def _build_layout(self) -> None:
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        top = ttk.Frame(frame)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(1, weight=1)
        ttk.Button(top, text="< Precedente", command=lambda: self.show_item(self.index - 1)).grid(row=0, column=0, padx=(0, 8))
        choice = ttk.Combobox(top, textvariable=self.choice_var, values=[item.label for item in self.items], state="readonly")
        choice.grid(row=0, column=1, sticky="ew")
        choice.bind("<<ComboboxSelected>>", lambda _event: self.show_item(choice.current()))
        ttk.Button(top, text="Suivante >", command=lambda: self.show_item(self.index + 1)).grid(row=0, column=2, padx=(8, 0))

        self.canvas = tk.Canvas(frame, width=CANVAS_SIZE[0], height=CANVAS_SIZE[1], bg="#f8faf8", highlightthickness=1, highlightbackground="#acb7ae")
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Configure>", lambda _event: self.redraw())

        details = ttk.Frame(frame)
        details.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        details.columnconfigure(1, weight=1)
        ttk.Label(details, textvariable=self.progress_var, font=("Helvetica", 10, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(details, textvariable=self.coordinate_var).grid(row=0, column=1, sticky="w", padx=(20, 0))
        ttk.Label(details, textvariable=self.status_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))

        actions = ttk.Frame(frame)
        actions.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Effacer ce point", command=self.clear_point).pack(side="left")
        ttk.Button(actions, text="Charger JSON", command=self.load_json).pack(side="right", padx=(6, 0))
        ttk.Button(actions, text="Sauver JSON", command=self.save_json).pack(side="right")
        self.bind("<Left>", lambda _event: self.show_item(self.index - 1))
        self.bind("<Right>", lambda _event: self.show_item(self.index + 1))

    @property
    def current(self) -> CalibrationImage:
        return self.items[self.index]

    def show_item(self, index: int) -> None:
        self.index = index % len(self.items)
        self.choice_var.set(self.current.label)
        self.redraw()

    def redraw(self) -> None:
        from PIL import Image, ImageTk

        item = self.current
        image = Image.open(item.path).convert("RGBA")
        canvas_width = max(100, self.canvas.winfo_width())
        canvas_height = max(100, self.canvas.winfo_height())
        scale = min((canvas_width - 30) / image.width, (canvas_height - 30) / image.height)
        display_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        display = image.resize(display_size, Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(display)
        origin = ((canvas_width - display_size[0]) / 2.0, (canvas_height - display_size[1]) / 2.0)
        self.image_origin = origin
        self.image_scale = scale

        self.canvas.delete("all")
        self.canvas.create_image(origin[0], origin[1], image=self.photo, anchor="nw")
        spec = sprite_spec("trunk", item.refined, (item.subject_profile, item.bar_position))
        self._draw_reference(spec.distal_anchor, "#228b5a", "hanche")
        self._draw_reference(spec.proximal_anchor, "#167a8b", "epaule")
        selected = self.points.get(item.key)
        if selected is None:
            self.coordinate_var.set("CoM barre: non place")
        else:
            anterior, longitudinal = point_relative_to_shoulder(selected, spec)
            self._draw_selected(selected)
            self.coordinate_var.set(
                f"CoM barre: px=({selected[0]:.1f}, {selected[1]:.1f}) | local=({anterior:+.3f}, {longitudinal:+.3f}) Ltronc"
            )
        self.progress_var.set(f"Image {self.index + 1}/12 - {len(self.points)}/12 placees")

    def _display_point(self, source_point: tuple[float, float]) -> tuple[float, float]:
        return (
            self.image_origin[0] + source_point[0] * self.image_scale,
            self.image_origin[1] + source_point[1] * self.image_scale,
        )

    def _draw_reference(self, source_point: tuple[float, float], color: str, label: str) -> None:
        x, y = self._display_point(source_point)
        self.canvas.create_oval(x - 7, y - 7, x + 7, y + 7, outline=color, width=2)
        self.canvas.create_text(x + 10, y, text=label, fill=color, anchor="w", font=("Helvetica", 9, "bold"))

    def _draw_selected(self, source_point: tuple[float, float]) -> None:
        x, y = self._display_point(source_point)
        self.canvas.create_line(x - 12, y, x + 12, y, fill="#c9332c", width=2)
        self.canvas.create_line(x, y - 12, x, y + 12, fill="#c9332c", width=2)
        self.canvas.create_oval(x - 6, y - 6, x + 6, y + 6, outline="#c9332c", width=2)
        self.canvas.create_text(x + 14, y - 10, text="CoM barre", fill="#c9332c", anchor="sw", font=("Helvetica", 9, "bold"))

    def on_canvas_click(self, event: tk.Event) -> None:
        from PIL import Image

        with Image.open(self.current.path) as image:
            width, height = image.size
        source = (
            (event.x - self.image_origin[0]) / self.image_scale,
            (event.y - self.image_origin[1]) / self.image_scale,
        )
        if not (0.0 <= source[0] <= width and 0.0 <= source[1] <= height):
            return
        self.points[self.current.key] = source
        self.status_var.set("Point place; utiliser Suivante pour poursuivre ou recliquer pour ajuster.")
        self.redraw()

    def clear_point(self) -> None:
        self.points.pop(self.current.key, None)
        self.status_var.set("Point efface pour cette image.")
        self.redraw()

    def save_json(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="Sauver les positions de CoM de barre",
            initialdir=str(OUTPUT_PATH.parent),
            initialfile=OUTPUT_PATH.name,
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not filename:
            return
        Path(filename).write_text(json.dumps(calibration_payload(self.points), indent=2) + "\n", encoding="utf-8")
        self.status_var.set(f"Calibration sauvee: {filename}")
        if len(self.points) < len(self.items):
            messagebox.showinfo("Calibration partielle", f"{len(self.points)}/12 points ont ete places; le fichier reste rechargeable.")

    def load_json(self) -> None:
        filename = filedialog.askopenfilename(
            title="Charger des positions de CoM de barre",
            initialdir=str(OUTPUT_PATH.parent),
            filetypes=[("JSON", "*.json")],
        )
        if not filename:
            return
        payload = json.loads(Path(filename).read_text(encoding="utf-8"))
        loaded: dict[str, tuple[float, float]] = {}
        for entry in payload.get("entries", []):
            point = entry.get("bar_com_pixel")
            if point is not None and len(point) == 2:
                loaded[str(entry["id"])] = (float(point[0]), float(point[1]))
        self.points = loaded
        self.status_var.set(f"Calibration chargee: {len(loaded)}/12 points.")
        self.redraw()


def main() -> None:
    BarComEditor().mainloop()


if __name__ == "__main__":
    main()
