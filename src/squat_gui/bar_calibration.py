"""Manual bar position calibration shared by the visual assets and model geometry."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path


CALIBRATION_PATH = Path(__file__).resolve().parents[2] / "assets" / "raster_segments" / "bar_com_points.json"
PHYSICAL_REFERENCE_QUALITY = "refined"


@lru_cache(maxsize=1)
def calibration_entries() -> dict[tuple[str, str, str], tuple[float, float]]:
    """Return annotated bar offsets as (anterior, longitudinal) trunk-length fractions."""
    payload = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
    entries: dict[tuple[str, str, str], tuple[float, float]] = {}
    for entry in payload.get("entries", []):
        local = entry.get("relative_to_shoulder_in_trunk_lengths")
        if local is None:
            continue
        key = (str(entry["quality"]), str(entry["subject_profile"]), str(entry["bar_position"]))
        entries[key] = (float(local["anterior"]), float(local["longitudinal"]))
    return entries


def annotated_bar_offset_fractions(
    subject_profile: str,
    bar_position: str,
    quality: str = PHYSICAL_REFERENCE_QUALITY,
) -> tuple[float, float]:
    """Get an annotated bar centre offset relative to the shoulder."""
    key = (quality, subject_profile, bar_position)
    try:
        return calibration_entries()[key]
    except KeyError as error:
        raise ValueError(f"Calibration de barre absente pour {quality}/{subject_profile}/{bar_position}") from error


def physical_bar_offsets(
    trunk_length: float,
    subject_profile: str,
    bar_position: str,
) -> tuple[float, float]:
    """Convert the refined sprite annotation to physical offsets in metres.

    Drawing quality is deliberately excluded here: selecting low-quality images
    must not alter dynamics, CoM or CoP.
    """
    anterior, longitudinal = annotated_bar_offset_fractions(subject_profile, bar_position)
    return anterior * trunk_length, longitudinal * trunk_length
