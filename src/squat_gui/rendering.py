"""Shared render-layer contract and off-screen animation renderer."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, pi, sin

from .anthropometry import Anthropometry
from .dynamics import GRAVITY, DynamicsResult, force_balance
from .kinematics import (
    MotionState,
    joint_angles_from_pose,
    segment_orientations,
)
from .observables import segment_anthropometry, support_margins
from .raster_segments import sprite_spec, transformed_sprite_image
from .scene_model import (
    SceneGeometry,
    ViewportTransform,
    build_scene_geometry,
    project_point_on_line,
    scene_bounds as common_scene_bounds,
)

FORCE_DRAW_SCALE = 3500.0 / 3.0


@dataclass(frozen=True)
class RenderLayers:
    global_com: bool = True
    com_projection: bool = True
    segment_com: bool = False
    cop_zmp: bool = True
    grf: bool = True
    weight: bool = False
    geometric_base: bool = False
    functional_base: bool = True
    force_balance: bool = False
    joint_coordinates: bool = False
    segment_orientations: bool = False
    joint_angles: bool = False
    anthropometry: bool = False
    moment_arms: bool = True
    capacity_rings: bool = True
    joint_markers: bool = True
    alerts: bool = True
    time_label: bool = True
    refined_sprites: bool = True


def scene_bounds(anthro: Anthropometry) -> tuple[float, float, float, float]:
    """Compatibility wrapper for the historical single-subject API."""

    return common_scene_bounds((anthro,))


def _font(size: int, bold: bool = False):
    from PIL import ImageFont

    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(filename, size)
    except OSError:
        return ImageFont.load_default()


def _mapper(width: int, height: int, bounds: tuple[float, float, float, float]):
    return ViewportTransform(width, height, bounds, 52).world_to_pixel


def _arrow(draw, start, end, fill: str, width: int = 4) -> None:
    draw.line((*start, *end), fill=fill, width=width)
    angle = atan2(end[1] - start[1], end[0] - start[0])
    size = 13
    points = [
        end,
        (end[0] - size * cos(angle - pi / 6), end[1] - size * sin(angle - pi / 6)),
        (end[0] - size * cos(angle + pi / 6), end[1] - size * sin(angle + pi / 6)),
    ]
    draw.polygon(points, fill=fill)


def _draw_interval(draw, mapper, limits, offset: int, color: str, label: str) -> None:
    posterior = mapper((limits[0], 0.0))
    anterior = mapper((limits[1], 0.0))
    y = posterior[1] + offset
    draw.line((posterior[0], y, anterior[0], y), fill=color, width=3)
    for x in (posterior[0], anterior[0]):
        draw.line((x, y - 6, x, y + 6), fill=color, width=2)
    draw.text(
        ((posterior[0] + anterior[0]) / 2, y + 7),
        label,
        anchor="ma",
        fill=color,
        font=_font(12, True),
    )


def _draw_sprites(
    image, scene: SceneGeometry, mapper, refined: bool
) -> bool:
    try:
        for segment in scene.segments:
            spec = sprite_spec(segment.name, refined, segment.variant)
            distal_px = mapper(segment.distal)
            proximal_px = mapper(segment.proximal)
            target = (proximal_px[0] - distal_px[0], proximal_px[1] - distal_px[1])
            sprite, anchor = transformed_sprite_image(spec, target, refined)
            image.alpha_composite(
                sprite,
                (round(distal_px[0] - anchor[0]), round(distal_px[1] - anchor[1])),
            )
    except Exception:
        return False
    return True


def render_animation_frame(
    anthro: Anthropometry,
    state: MotionState,
    result: DynamicsResult,
    layers: RenderLayers,
    *,
    width: int = 900,
    height: int = 720,
):
    """Render one deterministic RGB frame without a Tk display."""
    from PIL import Image, ImageDraw

    point = support_margins(state.pose, result.cop_x)
    alerts = []
    if not point.in_functional_base:
        alerts.append(f"{result.support_point_label} hors zone fonctionnelle")
    over = [
        name
        for name, ratio in result.effort_ratios.items()
        if ratio is None or ratio > 1.0
    ]
    if over:
        alerts.append("faisabilité mécanique U > 1: " + ", ".join(over))
    background = "#ffe7e3" if alerts and layers.alerts else "#fbfcf9"
    image = Image.new("RGBA", (width, height), background)
    draw = ImageDraw.Draw(image)
    mapper = _mapper(width, height, scene_bounds(anthro))
    pose = state.pose
    scene = build_scene_geometry(anthro, state, result.cop_x)

    if not _draw_sprites(image, scene, mapper, layers.refined_sprites):
        chain = [
            scene.point(name)
            for name in ("heel", "toe", "ankle", "knee", "hip", "shoulder")
        ]
        draw.line(
            [mapper(item) for item in chain], fill="#333333", width=10, joint="curve"
        )
    draw.line(
        (*mapper(scene.ground_line[0]), *mapper(scene.ground_line[1])),
        fill="#333333",
        width=4,
    )

    if scene.wedge_polygon is not None:
        draw.polygon(
            [mapper(point) for point in scene.wedge_polygon],
            fill="#d9c39b",
            outline="#7d6542",
        )
    if layers.geometric_base:
        _draw_interval(
            draw,
            mapper,
            scene.geometric_support.limits,
            10,
            "#506158",
            "base geometrique",
        )
    if layers.functional_base:
        _draw_interval(
            draw,
            mapper,
            scene.functional_support.limits,
            42 if layers.geometric_base else 12,
            "#9a5b16",
            "zone fonctionnelle",
        )

    com = mapper(scene.point("com"))
    projection = mapper(scene.com_projection)
    if layers.global_com and layers.com_projection:
        draw.line((*com, *projection), fill="#3d7580", width=2)
    if layers.global_com:
        draw.ellipse((com[0] - 8, com[1] - 8, com[0] + 8, com[1] + 8), fill="#2c9ab7")
    if layers.com_projection:
        draw.ellipse(
            (
                projection[0] - 6,
                projection[1] - 6,
                projection[0] + 6,
                projection[1] + 6,
            ),
            fill="#2c9ab7",
        )
    if layers.segment_com:
        for segment_com in scene.segment_coms:
            pixel = mapper(segment_com.position)
            draw.ellipse(
                (pixel[0] - 5, pixel[1] - 5, pixel[0] + 5, pixel[1] + 5), fill="#e64357"
            )
            draw.text(
                (pixel[0] + 7, pixel[1] - 7),
                segment_com.name,
                anchor="ls",
                fill="#8a1f32",
                font=_font(11, True),
            )

    cop = mapper(scene.support_point)
    if layers.cop_zmp:
        draw.ellipse((cop[0] - 6, cop[1] - 6, cop[0] + 6, cop[1] + 6), fill="#c15a2b")
        draw.text(
            (cop[0] + 8, cop[1] - 8),
            result.support_point_label,
            anchor="ls",
            fill="#8a3f1f",
            font=_font(12, True),
        )
    if layers.grf:
        force_end = mapper(
            (
                scene.support_point[0]
                + result.ground_reaction[0] / FORCE_DRAW_SCALE,
                result.ground_reaction[1] / FORCE_DRAW_SCALE,
            )
        )
        _arrow(draw, cop, force_end, "#c15a2b")
        draw.text(
            (force_end[0] + 6, force_end[1]),
            "GRF",
            anchor="lm",
            fill="#8a3f1f",
            font=_font(12, True),
        )
    if layers.weight:
        weight_end = mapper(
            (
                scene.point("com")[0],
                scene.point("com")[1]
                - anthro.total_mass * GRAVITY / FORCE_DRAW_SCALE,
            )
        )
        _arrow(draw, com, weight_end, "#315f8a")

    if layers.moment_arms:
        for joint in (scene.point("knee"), scene.point("hip")):
            projected = project_point_on_line(
                joint, scene.support_point, result.ground_reaction
            )
            draw.line((*mapper(joint), *mapper(projected)), fill="#1f77b4", width=2)
    if layers.capacity_rings:
        for name, joint in (
            ("cheville", scene.point("ankle")),
            ("genou", scene.point("knee")),
            ("hanche", scene.point("hip")),
        ):
            utilization = result.effort_ratios[name]
            ratio = 1.0 if utilization is None else min(1.0, utilization)
            color = (
                int(40 + 190 * ratio),
                int(170 * max(0.0, 1.0 - max(0.0, ratio - 0.5) * 2)),
                53,
            )
            pixel = mapper(joint)
            draw.ellipse(
                (pixel[0] - 14, pixel[1] - 14, pixel[0] + 14, pixel[1] + 14),
                outline=color,
                width=5,
            )
    if layers.joint_markers:
        for joint in (
            scene.point("ankle"),
            scene.point("knee"),
            scene.point("hip"),
            scene.point("shoulder"),
        ):
            pixel = mapper(joint)
            draw.ellipse(
                (pixel[0] - 7, pixel[1] - 7, pixel[0] + 7, pixel[1] + 7),
                fill="white",
                outline="#1f1f1f",
                width=2,
            )

    if layers.joint_coordinates:
        for label, joint in (
            ("cheville", scene.point("ankle")),
            ("genou", scene.point("knee")),
            ("hanche", scene.point("hip")),
            ("épaule", scene.point("shoulder")),
        ):
            pixel = mapper(joint)
            draw.text(
                (pixel[0] + 10, pixel[1] - 12),
                f"{label} ({joint[0]:.3f}; {joint[1]:.3f}) m",
                fill="#276c92",
                font=_font(11, True),
            )
    if layers.segment_orientations:
        values = segment_orientations(pose)
        draw.text(
            (18, 52),
            "Orientations: "
            + " · ".join(
                f"{key}={degrees(value):.1f}°" for key, value in values.items()
            ),
            fill="#276c92",
            font=_font(12, True),
        )
    if layers.joint_angles:
        values = joint_angles_from_pose(pose)
        draw.text(
            (18, 72),
            "Angles: "
            + " · ".join(
                f"{key}={degrees(value):.1f}°" for key, value in values.items()
            ),
            fill="#6d5ea8",
            font=_font(12, True),
        )
    if layers.anthropometry:
        table = segment_anthropometry(anthro)
        lines = ["Anthropométrie utilisée"] + [
            f"{table[key].label}: L={table[key].length_m:.3f} m · m={table[key].mass_kg:.2f} kg"
            for key in ("foot", "shank", "thigh", "trunk")
        ]
        draw.multiline_text(
            (width - 340, 18),
            "\n".join(lines),
            fill="#17364a",
            font=_font(12, True),
            spacing=4,
        )
    if layers.force_balance:
        balance = force_balance(anthro, result)
        text = (
            f"GRF+P−m·a=({balance.residual_N[0]:.1e}; {balance.residual_N[1]:.1e}) N\n"
            f"{result.support_point_label}: x={result.cop_x:.4f} m · {result.support_point_source}"
        )
        draw.multiline_text(
            (18, height - 58), text, fill="#4f3518", font=_font(12, True), spacing=3
        )
    if layers.time_label:
        draw.text(
            (18, 18),
            f"t={state.time:.2f} s · {state.phase}",
            fill="#22312a",
            font=_font(18, True),
        )
    if alerts and layers.alerts:
        draw.text(
            (18, 100),
            "Probleme biomecanique: " + " | ".join(alerts),
            fill="#8a1f17",
            font=_font(13, True),
        )
    return image.convert("RGB")
