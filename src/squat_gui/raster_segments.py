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


def _rotated_anchor_bbox(width: int, height: int, anchor: tuple[float, float], angle_deg: float) -> tuple[float, float, float, float]:
    from PIL import Image

    # Pillow already has the exact affine math; rotating a blank layer gives us the expanded bbox.
    blank = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    rotated = blank.rotate(angle_deg, resample=Image.Resampling.BICUBIC, center=anchor, expand=True)
    # Recompute the anchor shift by rotating the four corners around the anchor.
    from math import cos, radians, sin

    angle = radians(angle_deg)
    c = cos(angle)
    s = sin(angle)
    xs = []
    ys = []
    for x, y in ((0, 0), (width, 0), (0, height), (width, height)):
        dx = x - anchor[0]
        dy = y - anchor[1]
        xs.append(anchor[0] + c * dx - s * dy)
        ys.append(anchor[1] + s * dx + c * dy)
    min_x = min(xs)
    min_y = min(ys)
    return rotated.size[0], rotated.size[1], anchor[0] - min_x, anchor[1] - min_y


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
    rotated = scaled.rotate(angle_deg, resample=Image.Resampling.BICUBIC, center=scaled_anchor, expand=True)
    _, _, anchor_x, anchor_y = _rotated_anchor_bbox(scaled.size[0], scaled.size[1], scaled_anchor, angle_deg)
    return PhotoImage(rotated), (anchor_x, anchor_y)


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
