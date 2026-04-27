"""Optional biobuddy/biorbd integration points."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path

from .anthropometry import Anthropometry, SegmentSpec


@dataclass(frozen=True)
class OptionalBackendStatus:
    biobuddy_available: bool
    biorbd_available: bool
    message: str


def detect_optional_backends() -> OptionalBackendStatus:
    biobuddy_available = find_spec("biobuddy") is not None
    biorbd_available = find_spec("biorbd") is not None
    if biobuddy_available and biorbd_available:
        message = "biobuddy/biorbd disponibles"
    else:
        missing = []
        if not biobuddy_available:
            missing.append("biobuddy")
        if not biorbd_available:
            missing.append("biorbd")
        message = "backend analytique actif; paquets manquants: " + ", ".join(missing)
    return OptionalBackendStatus(biobuddy_available, biorbd_available, message)


def _segment_block(segment: SegmentSpec, parent: str, rt: str, translations: str, rotations: str = "z") -> str:
    inertia = segment.inertia
    return f"""
segment {segment.name}
    parent {parent}
    RT {rt}
    translations {translations}
    rotations {rotations}
    mass {segment.mass:.8f}
    inertia
        {inertia:.8f} 0 0
        0 {inertia:.8f} 0
        0 0 {inertia:.8f}
    com 0 {segment.length * segment.com_fraction:.8f} 0
endsegment
"""


def biomod_text(anthro: Anthropometry) -> str:
    foot = anthro.foot
    shank = anthro.shank
    thigh = anthro.thigh
    trunk = anthro.trunk
    return f"""version 4

// Squat 2D generated from squat_gui.
// The current GUI uses an analytical fallback and keeps this file ready for biorbd.

segment ground
    translations xy
    rotations z
    mass 0
endsegment

segment {foot.name}
    parent ground
    RT 0 0 0 xyz 0 0 0
    translations none
    rotations none
    mass {foot.mass:.8f}
    inertia
        {foot.inertia:.8f} 0 0
        0 {foot.inertia:.8f} 0
        0 0 {foot.inertia:.8f}
    com {foot.length * foot.com_fraction:.8f} 0.02500000 0
endsegment
{_segment_block(shank, foot.name, f"{anthro.ankle_x_from_heel:.8f} {anthro.ankle_height:.8f} 0 xyz 0 0 0", "none")}
{_segment_block(thigh, shank.name, f"0 {shank.length:.8f} 0 xyz 0 0 0", "none")}
{_segment_block(trunk, thigh.name, f"0 {thigh.length:.8f} 0 xyz 0 0 0", "none")}

segment barre
    parent {trunk.name}
    RT 0 {trunk.length:.8f} 0 xyz 0 0 0
    translations none
    rotations none
    mass {anthro.bar_mass:.8f}
    inertia
        0.00000000 0 0
        0 0.00000000 0
        0 0 0.00000000
    com 0 0 0
endsegment
"""


def write_biomod_file(path: str | Path, anthro: Anthropometry) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(biomod_text(anthro), encoding="utf-8")
    return output


def load_biorbd_model(path: str | Path):
    import biorbd

    return biorbd.Model(str(path))
