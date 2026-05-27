"""Optional biobuddy/biorbd integration points."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from math import cos, radians, sin
import os
from pathlib import Path

from .anthropometry import Anthropometry, SegmentSpec


@dataclass(frozen=True)
class OptionalBackendStatus:
    biobuddy_available: bool
    biorbd_available: bool
    message: str


@dataclass(frozen=True)
class BiomodCacheKey:
    load_tenths_kg: int
    shank_percent: float
    thigh_percent: float
    trunk_percent: float
    subject_profile: str
    bar_position: str
    wedge_angle_deg: float


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


def biomod_cache_key(anthro: Anthropometry) -> BiomodCacheKey:
    return BiomodCacheKey(
        load_tenths_kg=int(round(10.0 * anthro.bar_mass)),
        shank_percent=round((anthro.shank_scale - 1.0) * 100.0, 1),
        thigh_percent=round((anthro.thigh_scale - 1.0) * 100.0, 1),
        trunk_percent=round((anthro.trunk_scale - 1.0) * 100.0, 1),
        subject_profile=anthro.subject_profile,
        bar_position=anthro.bar_position,
        wedge_angle_deg=round(anthro.wedge_angle_deg, 1),
    )


def _matrix_block(translation: tuple[float, float, float], angle_z: float = 0.0) -> str:
    tx, ty, tz = translation
    c = cos(angle_z)
    s = sin(angle_z)
    return (
        "\tRTinMatrix\t1\n"
        "\tRT\n"
        f"\t\t{c:.6f}\t{-s:.6f}\t0.000000\t{tx:.6f}\n"
        f"\t\t{s:.6f}\t{c:.6f}\t0.000000\t{ty:.6f}\n"
        f"\t\t0.000000\t0.000000\t1.000000\t{tz:.6f}\n"
        "\t\t0.000000\t0.000000\t0.000000\t1.000000\n"
    )


def _segment_block(
    segment: SegmentSpec,
    parent: str,
    translation: tuple[float, float, float],
    *,
    rotations: str | None = "z",
    initial_angle_z: float = 0.0,
) -> str:
    inertia = max(segment.inertia, 1e-8)
    out = [f"segment\t{segment.name}\n", f"\tparent\t{parent}\n", _matrix_block(translation, initial_angle_z)]
    if rotations is not None:
        out.append(f"\trotations\t{rotations}\n")
        out.append("\trangesQ\n\t\t-3.141593\t3.141593\n")
    out.append(f"\tmass\t{segment.mass:.8f}\n")
    out.append(f"\tCenterOfMass\t{segment.com_anterior_offset:.8f}\t{segment.length * segment.com_fraction:.8f}\t0.00000000\n")
    out.append("\tinertia\n")
    out.append(f"\t\t{inertia:.8f}\t0.00000000\t0.00000000\n")
    out.append(f"\t\t0.00000000\t{inertia:.8f}\t0.00000000\n")
    out.append(f"\t\t0.00000000\t0.00000000\t{inertia:.8f}\n")
    out.append("endsegment\n\n")
    return "".join(out)


def biomod_text(anthro: Anthropometry) -> str:
    foot = anthro.foot
    shank = anthro.shank
    thigh = anthro.thigh
    trunk = anthro.trunk
    bar_inertia = max(anthro.bar_mass * 0.01**2, 1e-8)
    return (
        "version 4\n\n"
        f"gravity\t0.000000\t{-9.80665:.6f}\t0.000000\n\n"
        "// Squat 2D generated from squat_gui.\n"
        "// Coordinates: x horizontal, y vertical, z out of plane.\n\n"
        f"segment\t{foot.name}\n"
        "\tparent\tbase\n"
        f"{_matrix_block((0.0, foot.length * sin(radians(anthro.wedge_angle_deg)), 0.0), -radians(anthro.wedge_angle_deg))}"
        f"\tmass\t{foot.mass:.8f}\n"
        f"\tCenterOfMass\t{foot.length * foot.com_fraction:.8f}\t0.02500000\t0.00000000\n"
        "\tinertia\n"
        f"\t\t{foot.inertia:.8f}\t0.00000000\t0.00000000\n"
        f"\t\t0.00000000\t{foot.inertia:.8f}\t0.00000000\n"
        f"\t\t0.00000000\t0.00000000\t{foot.inertia:.8f}\n"
        "endsegment\n\n"
        f"{_segment_block(shank, foot.name, (anthro.ankle_x_from_heel, anthro.ankle_height, 0.0))}"
        f"{_segment_block(thigh, shank.name, (0.0, shank.length, 0.0))}"
        f"{_segment_block(trunk, thigh.name, (0.0, thigh.length, 0.0))}"
        "segment\tbarre\n"
        f"\tparent\t{trunk.name}\n"
        f"{_matrix_block((anthro.bar_anterior_offset, trunk.length + anthro.bar_longitudinal_offset, 0.0))}"
        f"\tmass\t{anthro.bar_mass:.8f}\n"
        "\tCenterOfMass\t0.00000000\t0.00000000\t0.00000000\n"
        "\tinertia\n"
        f"\t\t{bar_inertia:.8f}\t0.00000000\t0.00000000\n"
        f"\t\t0.00000000\t{bar_inertia:.8f}\t0.00000000\n"
        f"\t\t0.00000000\t0.00000000\t{bar_inertia:.8f}\n"
        "endsegment\n"
    )


def write_biomod_file(path: str | Path, anthro: Anthropometry) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(biomod_text(anthro), encoding="utf-8")
    return output


def load_biorbd_model(path: str | Path):
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

    import biorbd

    return biorbd.Model(str(path))


class BiorbdModelCache:
    def __init__(self, directory: str | Path = "generated/biomod_cache") -> None:
        self.directory = Path(directory)
        self._models: dict[BiomodCacheKey, object] = {}
        self._paths: dict[BiomodCacheKey, Path] = {}

    def path_for(self, anthro: Anthropometry) -> Path:
        key = biomod_cache_key(anthro)
        profile = key.subject_profile.replace(" ", "_")
        stem = (
            f"squat_load{key.load_tenths_kg / 10.0:04.1f}_"
            f"shank{key.shank_percent:+.1f}_"
            f"thigh{key.thigh_percent:+.1f}_"
            f"trunk{key.trunk_percent:+.1f}_"
            f"{profile}_{key.bar_position}_wedge{key.wedge_angle_deg:.0f}"
        )
        return self.directory / f"{stem.replace('+', 'p').replace('-', 'm').replace('.', 'd')}.bioMod"

    def model_for(self, anthro: Anthropometry):
        key = biomod_cache_key(anthro)
        if key not in self._models:
            path = self.path_for(anthro)
            write_biomod_file(path, anthro)
            self._paths[key] = path
            self._models[key] = load_biorbd_model(path)
        return self._models[key]

    def cached_path_for(self, anthro: Anthropometry) -> Path:
        key = biomod_cache_key(anthro)
        if key not in self._paths:
            self.model_for(anthro)
        return self._paths[key]
