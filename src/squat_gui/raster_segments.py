"""Raster sprite renderer for the side-view squat segments."""

from __future__ import annotations

from collections import OrderedDict, namedtuple
from dataclasses import dataclass
from functools import lru_cache
from math import atan2, ceil, cos, degrees, hypot, radians, sin
from pathlib import Path
from threading import RLock
from typing import Callable

from .kinematics import Vector
from .resources import asset_path


ASSET_DIR = asset_path("raster_segments")


class SpriteError(RuntimeError):
    """Base exception for a sprite that cannot be prepared for rendering."""


class SpriteDefinitionError(SpriteError, ValueError):
    """Raised when a requested sprite or its variant is not registered."""


class SpriteAssetError(SpriteError):
    """Raised when a registered sprite asset cannot be opened."""


class SpriteCalibrationError(SpriteError, ValueError):
    """Raised when the calibration targets embedded in a sprite are invalid."""


@dataclass(frozen=True)
class SpriteSpec:
    name: str
    filename: str
    distal_anchor: tuple[float, float]
    proximal_anchor: tuple[float, float]


SPRITE_FILES = {
    "foot": "pied.png",
    "shank": "jambe.png",
    "thigh": "cuisse.png",
    "trunk": "tronc.png",
}

TRUNK_VARIANTS = {
    ("homme", "front"): "trunk_homme_front.png",
    ("homme", "back"): "trunk_homme_back.png",
    ("homme", "over-head"): "trunk_homme_over-head.png",
    ("femme enceinte", "front"): "trunk_femme_enceinte_front.png",
    ("femme enceinte", "back"): "trunk_femme_enceinte_back.png",
    ("femme enceinte", "over-head"): "trunk_femme_enceinte_over-head.png",
}

# Display-only adjustments. The articulated anchors and all model quantities
# remain defined by the kinematic model, while silhouettes read more naturally.
DISPLAY_WIDTH_SCALE = {
    "shank": 1.20,
    "thigh": 1.30,
}
DISPLAY_EXTENSION_SCALE = {
    "foot": 1.16,
}

# The transformed refined sprites are expensive (LANCZOS resize followed by a
# BICUBIC rotation), but they are immutable throughout rendering.  Cache only
# these PIL images: ImageTk.PhotoImage instances remain owned by their canvas
# and are never retained here.
TRANSFORMED_SPRITE_CACHE_MAX_ENTRIES = 96
TRANSFORMED_SPRITE_CACHE_MAX_BYTES = 64 * 1024 * 1024

# Canonical transforms make keys stable across harmless floating-point noise.
# At a 300 px segment length, half an angular step displaces the proximal end
# by at most 0.13 px; half a length step is 0.03 px.  This stays below raster
# sampling precision while allowing repeated renders to share their result.
TRANSFORMED_SPRITE_ANGLE_STEP_DEGREES = 0.05
TRANSFORMED_SPRITE_LENGTH_STEP_PX = 1.0 / 16.0


TransformedSpriteCacheInfo = namedtuple(
    "TransformedSpriteCacheInfo",
    "hits misses max_entries curr_entries max_bytes curr_bytes evictions",
)


@dataclass(frozen=True)
class _TransformedSpriteKey:
    spec: SpriteSpec
    refined: bool
    target_length_step: int
    target_angle_step: int


class _TransformedSpriteCache:
    """Thread-safe LRU bounded by both entry count and estimated pixel bytes."""

    def __init__(self, max_entries: int, max_bytes: int) -> None:
        if max_entries < 0 or max_bytes < 0:
            raise ValueError("Sprite cache limits cannot be negative.")
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self._items = OrderedDict()
        self._bytes = 0
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._lock = RLock()

    @staticmethod
    def _image_bytes(image) -> int:
        return image.width * image.height * len(image.getbands())

    def get(self, key):
        with self._lock:
            try:
                image, anchor, image_bytes = self._items.pop(key)
            except KeyError:
                self._misses += 1
                return None
            self._items[key] = (image, anchor, image_bytes)
            self._hits += 1
            return image, anchor

    def put(self, key, value) -> None:
        image, anchor = value
        image_bytes = self._image_bytes(image)
        with self._lock:
            previous = self._items.pop(key, None)
            if previous is not None:
                self._bytes -= previous[2]
            if (
                self.max_entries == 0
                or self.max_bytes == 0
                or image_bytes > self.max_bytes
            ):
                return
            self._items[key] = (image, anchor, image_bytes)
            self._bytes += image_bytes
            while (
                len(self._items) > self.max_entries
                or self._bytes > self.max_bytes
            ):
                _, (_, _, evicted_bytes) = self._items.popitem(last=False)
                self._bytes -= evicted_bytes
                self._evictions += 1

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._bytes = 0
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def info(self) -> TransformedSpriteCacheInfo:
        with self._lock:
            return TransformedSpriteCacheInfo(
                self._hits,
                self._misses,
                self.max_entries,
                len(self._items),
                self.max_bytes,
                self._bytes,
                self._evictions,
            )


_transformed_sprite_cache = _TransformedSpriteCache(
    TRANSFORMED_SPRITE_CACHE_MAX_ENTRIES,
    TRANSFORMED_SPRITE_CACHE_MAX_BYTES,
)


def pillow_available() -> bool:
    try:
        import PIL.Image  # noqa: F401
        import PIL.ImageTk  # noqa: F401

        return True
    except ImportError:
        return False


def _rgb_on_white(image):
    from PIL import Image

    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    background.alpha_composite(rgba)
    return background.convert("RGB")


def _asset_path(filename: str, refined: bool) -> Path:
    if refined:
        return ASSET_DIR / "refined" / filename
    return ASSET_DIR / filename


def _sprite_filename(name: str, trunk_variant: tuple[str, str] | None) -> str:
    """Resolve a public segment name to its image filename.

    Keeping this lookup separate gives callers a useful error instead of the
    opaque ``KeyError`` that used to escape from the module-level mappings.
    """

    if name == "trunk" and trunk_variant is not None:
        try:
            return TRUNK_VARIANTS[trunk_variant]
        except KeyError as exc:
            raise SpriteDefinitionError(
                f"Unknown trunk sprite variant {trunk_variant!r}. "
                f"Expected one of: {', '.join(map(str, TRUNK_VARIANTS))}."
            ) from exc
    try:
        return SPRITE_FILES[name]
    except KeyError as exc:
        raise SpriteDefinitionError(
            f"Unknown sprite segment {name!r}. Expected one of: "
            f"{', '.join(SPRITE_FILES)}."
        ) from exc


def _load_source_image(filename: str, refined: bool, mode: str):
    """Open and detach a sprite image, translating file failures to domain errors."""

    from PIL import Image

    source_path = _asset_path(filename, refined)
    try:
        with Image.open(source_path) as source:
            return source.convert(mode)
    except FileNotFoundError as exc:
        raise SpriteAssetError(f"Sprite asset is missing: {source_path}") from exc
    except OSError as exc:
        raise SpriteAssetError(f"Sprite asset cannot be read: {source_path}") from exc


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
            150 <= count <= 3000
            and 12 <= box_width <= 50
            and 12 <= box_height <= 50
            and abs(box_width - box_height) <= 5
            and 0.45 <= fill_ratio <= 0.95
        )
        if round_dot:
            centers.append((sum_x / count, sum_y / count))
    return sorted(centers, key=lambda center: (center[1], center[0]))


def _toe_anchor_from_silhouette(image, filename: str) -> tuple[float, float]:
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
        raise SpriteCalibrationError(
            f"Sprite calibration for {filename} cannot locate the foot silhouette."
        )
    y_values.sort()
    return (float(rightmost), float(y_values[len(y_values) // 2]))


def _trunk_anchor_from_silhouette(
    image,
    distal_anchor: tuple[float, float],
    filename: str,
) -> tuple[float, float]:
    width, height = image.size
    pixels = image.load()
    ys: list[int] = []
    for y in range(height):
        for x in range(width):
            if _is_foreground(pixels[x, y]):
                ys.append(y)
    if not ys:
        raise SpriteCalibrationError(
            f"Sprite calibration for {filename} cannot locate the trunk silhouette."
        )
    top = min(ys)
    shoulder_y = top + 0.30 * (distal_anchor[1] - top)
    return (distal_anchor[0], shoulder_y)


def _sprite_spec_from_targets(name: str, filename: str, image, centers: list[tuple[float, float]]) -> SpriteSpec:
    """Build anchors from embedded calibration targets for one loaded sprite."""

    if name == "foot":
        if len(centers) != 1:
            raise SpriteCalibrationError(
                f"Sprite calibration for {filename} must contain one rotation target; "
                f"found {len(centers)}."
            )
        return SpriteSpec(name, filename, centers[0], _toe_anchor_from_silhouette(image, filename))

    if name == "trunk" and len(centers) == 1:
        distal = centers[0]
        return SpriteSpec(
            name,
            filename,
            distal,
            _trunk_anchor_from_silhouette(image, distal, filename),
        )

    if len(centers) < 2:
        raise SpriteCalibrationError(
            f"Sprite calibration for {filename} must contain at least two rotation "
            f"targets; found {len(centers)}."
        )
    proximal = centers[0]
    distal = centers[-1]
    return SpriteSpec(name, filename, distal, proximal)


@lru_cache(maxsize=32)
def sprite_spec(name: str, refined: bool = False, trunk_variant: tuple[str, str] | None = None) -> SpriteSpec:
    filename = _sprite_filename(name, trunk_variant)
    image = _rgb_on_white(_load_source_image(filename, refined, "RGBA"))
    centers = _component_centers(image)
    return _sprite_spec_from_targets(name, filename, image, centers)


def sprite_rotation_degrees(source_vector: Vector, target_vector: Vector) -> float:
    source_angle = atan2(source_vector[1], source_vector[0])
    target_angle = atan2(target_vector[1], target_vector[0])
    return degrees(source_angle - target_angle)


@lru_cache(maxsize=32)
def _load_transparent_sprite(filename: str, refined: bool):
    from PIL import ImageDraw

    image = _load_source_image(filename, refined, "RGBA")
    # The calibration image must be captured before the display cleanup below.
    # This also means the source PNG is opened only once per cached sprite.
    calibration_image = _rgb_on_white(image)
    pixels = image.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if r > 225 and g > 225 and b > 225:
                pixels[x, y] = (255, 255, 255, 0)
            else:
                pixels[x, y] = (r, g, b, a)

    # The black/white circles embedded in the source PNGs are calibration
    # targets.  They are useful to locate the physical joint anchors, but
    # they must not be part of the athlete silhouette: in the didactic mode
    # they otherwise overlap the joint and capacity overlays, giving the
    # misleading impression that the body is made from mixed-quality pieces.
    # Locate them from an untouched RGB copy so calibration remains entirely
    # independent from the display cleanup.
    target_centers = _component_centers(calibration_image)
    target_radius = max(12, round(min(width, height) * 0.032))
    painter = ImageDraw.Draw(image)
    for center_x, center_y in target_centers:
        painter.ellipse(
            (
                center_x - target_radius,
                center_y - target_radius,
                center_x + target_radius,
                center_y + target_radius,
            ),
            fill=(255, 255, 255, 0),
        )
    return image


def _stretch_horizontal_about_distal(source, spec: SpriteSpec, factor: float, extend_only: bool):
    from PIL import Image

    if factor == 1.0:
        return source, spec.distal_anchor, spec.proximal_anchor
    stretched = source.resize((max(1, round(source.width * factor)), source.height), Image.Resampling.LANCZOS)
    distal = (spec.distal_anchor[0] * factor, spec.distal_anchor[1])
    if extend_only:
        proximal = (
            distal[0] + spec.proximal_anchor[0] - spec.distal_anchor[0],
            spec.proximal_anchor[1],
        )
    else:
        proximal = (spec.proximal_anchor[0] * factor, spec.proximal_anchor[1])
    return stretched, distal, proximal


def _canonical_target_vector(target_vector_px: Vector) -> tuple[Vector, int, int]:
    """Return a deterministic sub-pixel transform and its integer cache steps."""

    target_length = max(1.0, hypot(target_vector_px[0], target_vector_px[1]))
    length_step = round(target_length / TRANSFORMED_SPRITE_LENGTH_STEP_PX)
    canonical_length = max(
        1.0,
        length_step * TRANSFORMED_SPRITE_LENGTH_STEP_PX,
    )

    target_angle = degrees(atan2(target_vector_px[1], target_vector_px[0]))
    target_angle = (target_angle + 180.0) % 360.0 - 180.0
    angle_step = round(target_angle / TRANSFORMED_SPRITE_ANGLE_STEP_DEGREES)
    canonical_angle = angle_step * TRANSFORMED_SPRITE_ANGLE_STEP_DEGREES
    angle_radians = radians(canonical_angle)
    canonical_vector = (
        canonical_length * cos(angle_radians),
        canonical_length * sin(angle_radians),
    )
    return canonical_vector, length_step, angle_step


def _render_transformed_sprite(
    spec: SpriteSpec,
    target_vector_px: Vector,
    refined: bool,
):
    from PIL import Image

    source = _load_transparent_sprite(spec.filename, refined)
    source, display_distal, display_proximal = _stretch_horizontal_about_distal(
        source,
        spec,
        DISPLAY_WIDTH_SCALE.get(spec.name, DISPLAY_EXTENSION_SCALE.get(spec.name, 1.0)),
        spec.name in DISPLAY_EXTENSION_SCALE,
    )
    anchor_vector = (
        display_proximal[0] - display_distal[0],
        display_proximal[1] - display_distal[1],
    )
    source_length = hypot(anchor_vector[0], anchor_vector[1])
    target_length = max(1.0, hypot(target_vector_px[0], target_vector_px[1]))
    scale = target_length / source_length
    scaled_size = (max(1, round(source.size[0] * scale)), max(1, round(source.size[1] * scale)))
    scaled = source.resize(scaled_size, Image.Resampling.LANCZOS)
    scaled_anchor = (display_distal[0] * scale, display_distal[1] * scale)
    scaled_anchor_vector = (anchor_vector[0] * scale, anchor_vector[1] * scale)
    angle_deg = sprite_rotation_degrees(scaled_anchor_vector, target_vector_px)
    canvas_size, pivot = _rotation_workspace(scaled.size, scaled_anchor)
    layer = Image.new("RGBA", canvas_size, (255, 255, 255, 0))
    layer.alpha_composite(scaled, (round(pivot[0] - scaled_anchor[0]), round(pivot[1] - scaled_anchor[1])))
    rotated_layer = layer.rotate(angle_deg, resample=Image.Resampling.BICUBIC, center=pivot, expand=False)
    bbox = rotated_layer.getbbox()
    if bbox is None:
        return rotated_layer, pivot
    cropped = rotated_layer.crop(bbox)
    anchor = (pivot[0] - bbox[0], pivot[1] - bbox[1])
    return cropped, anchor


def _rotation_workspace(
    image_size: tuple[int, int],
    anchor: Vector,
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Return the smallest safe square for a full rotation around ``anchor``.

    Refined source images are resized before rotation.  The former workspace
    added a 150% margin on every side, so BICUBIC filtering spent most of its
    time visiting pixels which were guaranteed to stay transparent.  A square
    enclosing the farthest source corner preserves the exact filter and pivot
    while substantially reducing that temporary image.
    """

    width, height = image_size
    farthest_x = max(anchor[0], width - anchor[0])
    farthest_y = max(anchor[1], height - anchor[1])
    # Two transparent pixels retain the complete BICUBIC support at the edge.
    radius = ceil(hypot(farthest_x, farthest_y)) + 2
    side = 2 * radius + 1
    return (side, side), (radius, radius)


def transformed_sprite_cache_clear() -> None:
    """Discard cached PIL transforms, for example after replacing an asset."""

    _transformed_sprite_cache.clear()


def transformed_sprite_cache_info() -> TransformedSpriteCacheInfo:
    """Expose bounded-cache statistics for diagnostics and regression tests."""

    return _transformed_sprite_cache.info()


def transformed_sprite_image(
    spec: SpriteSpec,
    target_vector_px: Vector,
    refined: bool = False,
):
    if not refined:
        return _render_transformed_sprite(spec, target_vector_px, refined)

    canonical_vector, length_step, angle_step = _canonical_target_vector(
        target_vector_px
    )
    key = _TransformedSpriteKey(
        spec,
        refined,
        length_step,
        angle_step,
    )
    cached = _transformed_sprite_cache.get(key)
    if cached is not None:
        return cached

    transformed = _render_transformed_sprite(spec, canonical_vector, refined)
    _transformed_sprite_cache.put(key, transformed)
    return transformed


def transformed_sprite(spec: SpriteSpec, target_vector_px: Vector, refined: bool = False):
    from PIL.ImageTk import PhotoImage

    image, anchor = transformed_sprite_image(spec, target_vector_px, refined)
    return PhotoImage(image), anchor


def clip_sprite_at_canvas_floor(image, anchor: Vector, distal_px: Vector, floor_canvas_y: float):
    """Crop pixels below a horizontal floor without moving the joint anchor."""

    image_top = distal_px[1] - anchor[1]
    visible_height = max(1, min(image.height, int(floor_canvas_y - image_top) + 1))
    if visible_height == image.height:
        return image, anchor
    return image.crop((0, 0, image.width, visible_height)), anchor


def draw_sprite_segment(
    canvas,
    name: str,
    distal_world: Vector,
    proximal_world: Vector,
    world_to_canvas: Callable[[Vector], Vector],
    refined: bool = False,
    trunk_variant: tuple[str, str] | None = None,
    floor_world_y: float | None = None,
) -> bool:
    if not pillow_available():
        return False
    spec = sprite_spec(name, refined, trunk_variant)
    distal_px = world_to_canvas(distal_world)
    proximal_px = world_to_canvas(proximal_world)
    target_vector = (proximal_px[0] - distal_px[0], proximal_px[1] - distal_px[1])
    image, anchor = transformed_sprite_image(spec, target_vector, refined)
    if floor_world_y is not None:
        floor_canvas_y = world_to_canvas((distal_world[0], floor_world_y))[1]
        image, anchor = clip_sprite_at_canvas_floor(
            image, anchor, distal_px, floor_canvas_y
        )
    from PIL.ImageTk import PhotoImage

    image = PhotoImage(image)
    canvas.create_image(distal_px[0] - anchor[0], distal_px[1] - anchor[1], image=image, anchor="nw")
    if not hasattr(canvas, "_sprite_images"):
        canvas._sprite_images = []
    canvas._sprite_images.append(image)
    return True
