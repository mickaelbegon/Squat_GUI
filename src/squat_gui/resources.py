"""Resource paths that also work from a frozen desktop application."""

from __future__ import annotations

from pathlib import Path
import sys


def project_root() -> Path:
    """Return the runtime root for repository files or bundled assets."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parents[2]


def asset_path(*parts: str) -> Path:
    """Return a path inside the bundled or repository `assets` directory."""
    return project_root() / "assets" / Path(*parts)
