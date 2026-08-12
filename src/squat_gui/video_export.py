"""Reproducible MP4 export for squat animations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Sequence

from .anthropometry import Anthropometry
from .dynamics import DynamicsResult
from .kinematics import DEFAULT_SAMPLE_PERIOD_S, MotionState
from .rendering import RenderLayers, render_animation_frame

DEFAULT_VIDEO_FPS = round(1.0 / DEFAULT_SAMPLE_PERIOD_S)


@dataclass(frozen=True)
class VideoExportReport:
    path: str
    metadata_path: str
    frame_count: int
    source_frame_count: int
    fps: int
    timeline_duration_s: float
    encoded_duration_s: float
    width: int
    height: int


def export_mp4(
    path: str | Path,
    anthro: Anthropometry,
    states: Sequence[MotionState],
    results: Sequence[DynamicsResult],
    layers: RenderLayers,
    *,
    fps: int = DEFAULT_VIDEO_FPS,
    width: int = 900,
    height: int = 720,
) -> VideoExportReport:
    if not states or len(states) != len(results):
        raise ValueError(
            "Les états et résultats vidéo doivent être non vides et de même longueur."
        )
    if fps <= 0:
        raise ValueError("Le nombre d'images par seconde doit être positif.")
    try:
        import imageio.v2 as imageio
        import numpy as np
    except ImportError as error:
        raise RuntimeError(
            "L'export MP4 requiert imageio, imageio-ffmpeg et numpy."
        ) from error

    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    timeline_duration_s = states[-1].time - states[0].time
    encoded_frame_count = max(1, round(timeline_duration_s * fps))
    encoded_samples = []
    for output_index in range(encoded_frame_count):
        target_time = states[0].time + output_index / fps
        source_index = min(
            range(len(states)),
            key=lambda index: abs(states[index].time - target_time),
        )
        encoded_samples.append((states[source_index], results[source_index]))
    writer = imageio.get_writer(
        output,
        fps=fps,
        codec="libx264",
        pixelformat="yuv420p",
        macro_block_size=2,
        ffmpeg_log_level="error",
    )
    try:
        for state, result in encoded_samples:
            image = render_animation_frame(
                anthro, state, result, layers, width=width, height=height
            )
            writer.append_data(np.asarray(image))
    finally:
        writer.close()

    metadata_path = output.with_suffix(output.suffix + ".json")
    payload = {
        "format_version": "1.1.0",
        "video": {
            "path": output.name,
            "frame_count": encoded_frame_count,
            "source_frame_count": len(states),
            "fps": fps,
            "timeline_duration_s": timeline_duration_s,
            "encoded_duration_s": encoded_frame_count / fps,
            "sample_period_s": 1.0 / fps,
            "width": width,
            "height": height,
        },
        "simulation": {
            "start_time_s": states[0].time,
            "end_time_s": states[-1].time,
            "backend": results[0].backend,
        },
        "layers": asdict(layers),
    }
    metadata_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return VideoExportReport(
        str(output),
        str(metadata_path),
        encoded_frame_count,
        len(states),
        fps,
        timeline_duration_s,
        encoded_frame_count / fps,
        width,
        height,
    )
