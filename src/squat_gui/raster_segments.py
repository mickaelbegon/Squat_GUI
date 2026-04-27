"""Raster sprite renderer for the side-view squat segments."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import atan2, degrees, hypot
from pathlib import Path
from typing import Callable

from .kinematics import Vector


ASSET_DIR = Path(__file__).resolve().parents[2] / "assets" / "raster_segments"


@dataclass(frozen=True)
class SpriteSpec:
    filename: str
    distal_anchor: tuple[float, float]
    proximal_anchor: tuple[float, float]


SPRITES = {
    "foot": SpriteSpec("pied.png", (84.9, 66.6), (281.0, 130.0)),
    "shank": SpriteSpec("jambe.png", (88.4, 542.2), (88.6, 74.7)),
    "thigh": SpriteSpec("cuisse.png", (123.5, 573.7), (136.8, 81.3)),
    "trunk": SpriteSpec("tronc.png", (206.6, 791.3), (214.0, 315.2)),
}


def pillow_available() -> bool:
    try:
        import PIL.Image  # noqa: F401
        import PIL.ImageTk  # noqa: F401

        return True
    except Exception:
        return False


@lru_cache(maxsize=4)
def _load_transparent_sprite(filename: str):
    from PIL import Image

    image = Image.open(ASSET_DIR / filename).convert("RGBA")
    pixels = image.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if r > 245 and g > 245 and b > 245:
                pixels[x, y] = (255, 255, 255, 0)
            else:
                pixels[x, y] = (r, g, b, a)
    return image


def transformed_sprite(spec: SpriteSpec, target_vector_px: Vector):
    from PIL import Image
    from PIL.ImageTk import PhotoImage

    source = _load_transparent_sprite(spec.filename)
    anchor_vector = (
        spec.proximal_anchor[0] - spec.distal_anchor[0],
        spec.proximal_anchor[1] - spec.distal_anchor[1],
    )
    source_length = hypot(anchor_vector[0], anchor_vector[1])
    target_length = max(1.0, hypot(target_vector_px[0], target_vector_px[1]))
    scale = target_length / source_length
    scaled_size = (max(1, round(source.size[0] * scale)), max(1, round(source.size[1] * scale)))
    scaled = source.resize(scaled_size, Image.Resampling.LANCZOS)
    scaled_anchor = (spec.distal_anchor[0] * scale, spec.distal_anchor[1] * scale)
    scaled_anchor_vector = (anchor_vector[0] * scale, anchor_vector[1] * scale)
    source_angle = atan2(scaled_anchor_vector[1], scaled_anchor_vector[0])
    target_angle = atan2(target_vector_px[1], target_vector_px[0])
    angle_deg = degrees(target_angle - source_angle)
    margin = int(max(scaled.size) * 1.5)
    pivot = (margin, margin)
    canvas_size = (scaled.size[0] + 2 * margin, scaled.size[1] + 2 * margin)
    layer = Image.new("RGBA", canvas_size, (255, 255, 255, 0))
    layer.alpha_composite(scaled, (round(pivot[0] - scaled_anchor[0]), round(pivot[1] - scaled_anchor[1])))
    rotated_layer = layer.rotate(angle_deg, resample=Image.Resampling.BICUBIC, center=pivot, expand=False)
    bbox = rotated_layer.getbbox()
    if bbox is None:
        return PhotoImage(rotated_layer), pivot
    cropped = rotated_layer.crop(bbox)
    anchor = (pivot[0] - bbox[0], pivot[1] - bbox[1])
    return PhotoImage(cropped), anchor


def draw_sprite_segment(
    canvas,
    name: str,
    distal_world: Vector,
    proximal_world: Vector,
    world_to_canvas: Callable[[Vector], Vector],
) -> bool:
    if not pillow_available():
        return False
    spec = SPRITES[name]
    distal_px = world_to_canvas(distal_world)
    proximal_px = world_to_canvas(proximal_world)
    target_vector = (proximal_px[0] - distal_px[0], proximal_px[1] - distal_px[1])
    image, anchor = transformed_sprite(spec, target_vector)
    canvas.create_image(distal_px[0] - anchor[0], distal_px[1] - anchor[1], image=image, anchor="nw")
    if not hasattr(canvas, "_sprite_images"):
        canvas._sprite_images = []
    canvas._sprite_images.append(image)
    return True
