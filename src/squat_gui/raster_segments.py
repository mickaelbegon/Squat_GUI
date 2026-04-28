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


SPRITE_FILES = {
    "foot": "pied.png",
    "shank": "jambe.png",
    "thigh": "cuisse.png",
    "trunk": "tronc.png",
}


def pillow_available() -> bool:
    try:
        import PIL.Image  # noqa: F401
        import PIL.ImageTk  # noqa: F401

        return True
    except Exception:
        return False


def _is_dark(pixel: tuple[int, int, int]) -> bool:
    return pixel[0] < 65 and pixel[1] < 65 and pixel[2] < 65


def _is_foreground(pixel: tuple[int, int, int]) -> bool:
    return pixel[0] < 245 or pixel[1] < 245 or pixel[2] < 245


def _component_centers(image) -> list[tuple[float, float]]:
    width, height = image.size
    pixels = image.load()
    dark = bytearray(width * height)
    for y in range(height):
        row = y * width
        for x in range(width):
            dark[row + x] = 1 if _is_dark(pixels[x, y]) else 0

    seen = bytearray(width * height)
    centers: list[tuple[float, float]] = []
    for start in range(width * height):
        if not dark[start] or seen[start]:
            continue
        stack = [start]
        seen[start] = 1
        count = 0
        sum_x = 0
        sum_y = 0
        min_x = width
        max_x = -1
        min_y = height
        max_y = -1
        while stack:
            index = stack.pop()
            y, x = divmod(index, width)
            count += 1
            sum_x += x
            sum_y += y
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            for ny in range(max(0, y - 1), min(height, y + 2)):
                row = ny * width
                for nx in range(max(0, x - 1), min(width, x + 2)):
                    neighbor = row + nx
                    if dark[neighbor] and not seen[neighbor]:
                        seen[neighbor] = 1
                        stack.append(neighbor)

        box_width = max_x - min_x + 1
        box_height = max_y - min_y + 1
        fill_ratio = count / (box_width * box_height)
        round_dot = (
            150 <= count <= 500
            and 12 <= box_width <= 30
            and 12 <= box_height <= 30
            and abs(box_width - box_height) <= 5
            and 0.45 <= fill_ratio <= 0.95
        )
        if round_dot:
            centers.append((sum_x / count, sum_y / count))
    return sorted(centers, key=lambda center: (center[1], center[0]))


def _toe_anchor_from_silhouette(image) -> tuple[float, float]:
    width, height = image.size
    pixels = image.load()
    rightmost = 0
    y_values: list[int] = []
    for y in range(height):
        for x in range(width):
            if _is_foreground(pixels[x, y]):
                if x > rightmost:
                    rightmost = x
                    y_values = [y]
                elif x >= rightmost - 2:
                    y_values.append(y)
    if not y_values:
        raise ValueError("No foreground pixels found for foot sprite")
    y_values.sort()
    return (float(rightmost), float(y_values[len(y_values) // 2]))


@lru_cache(maxsize=4)
def sprite_spec(name: str) -> SpriteSpec:
    from PIL import Image

    filename = SPRITE_FILES[name]
    image = Image.open(ASSET_DIR / filename).convert("RGB")
    centers = _component_centers(image)
    if name == "foot":
        if len(centers) != 1:
            raise ValueError(f"Expected one rotation target in {filename}, found {len(centers)}")
        return SpriteSpec(filename, centers[0], _toe_anchor_from_silhouette(image))

    if len(centers) < 2:
        raise ValueError(f"Expected two rotation targets in {filename}, found {len(centers)}")
    proximal = centers[0]
    distal = centers[-1]
    return SpriteSpec(filename, distal, proximal)


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
    spec = sprite_spec(name)
    distal_px = world_to_canvas(distal_world)
    proximal_px = world_to_canvas(proximal_world)
    target_vector = (proximal_px[0] - distal_px[0], proximal_px[1] - distal_px[1])
    image, anchor = transformed_sprite(spec, target_vector)
    canvas.create_image(distal_px[0] - anchor[0], distal_px[1] - anchor[1], image=image, anchor="nw")
    if not hasattr(canvas, "_sprite_images"):
        canvas._sprite_images = []
    canvas._sprite_images.append(image)
    return True
