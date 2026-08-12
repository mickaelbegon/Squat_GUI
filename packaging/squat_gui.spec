# -*- mode: python ; coding: utf-8 -*-

from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules


ROOT_CANDIDATES = [
    Path(SPECPATH).resolve(),
    Path(SPECPATH).resolve().parent,
    Path.cwd().resolve(),
    Path.cwd().resolve().parent,
]
ROOT = next(
    candidate
    for candidate in ROOT_CANDIDATES
    if (candidate / "pyproject.toml").exists() and (candidate / "src" / "squat_gui").exists()
)

datas = [
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "examples"), "examples"),
    (str(ROOT / "src" / "squat_gui" / "build_workbook.mjs"), "squat_gui"),
]
binaries = []
hiddenimports = [
    "PIL.Image",
    "PIL.ImageTk",
    "PIL._tkinter_finder",
    "imageio",
    "imageio_ffmpeg",
    "numpy",
    "openpyxl",
]

for runtime_module in ("imageio", "imageio_ffmpeg", "openpyxl"):
    module_datas, module_binaries, module_hiddenimports = collect_all(runtime_module)
    datas += module_datas
    binaries += module_binaries
    hiddenimports += module_hiddenimports

if os.environ.get("SQUAT_GUI_INCLUDE_OPTIONAL_BACKENDS") == "1":
    for optional_module in ("biorbd",):
        try:
            importlib.import_module(optional_module)
        except Exception as error:
            print(f"Skipping optional module {optional_module!r}: {error}")
            continue
        try:
            module_datas, module_binaries, module_hiddenimports = collect_all(optional_module)
        except Exception:
            try:
                module_datas = []
                module_binaries = []
                module_hiddenimports = collect_submodules(optional_module)
            except Exception:
                continue
        datas += module_datas
        binaries += module_binaries
        hiddenimports += module_hiddenimports
else:
    print("Skipping optional biorbd collection; set SQUAT_GUI_INCLUDE_OPTIONAL_BACKENDS=1 for a complete build.")

a = Analysis(
    [str(ROOT / "packaging" / "squat_gui_launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Squat GUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=(
        str(ROOT / "packaging" / "windows_version_info.txt")
        if sys.platform == "win32"
        else None
    ),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Squat GUI",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Squat GUI.app",
        icon=None,
        bundle_identifier="ca.umontreal.squat-gui",
        info_plist={
            "NSHighResolutionCapable": "True",
            "CFBundleShortVersionString": "0.2.0",
            "CFBundleDisplayName": "Squat GUI",
        },
    )
