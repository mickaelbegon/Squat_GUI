"""Cheap dependency-boundary checks for the layered application architecture.

The test parses source files instead of importing them, so it stays independent
from Tk, optional numerical backends, and package installation details.
"""

from __future__ import annotations

import ast
from pathlib import Path


PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "squat_gui"


def local_imports(module_name: str) -> set[str]:
    """Return direct sibling-module imports without importing application code."""
    tree = ast.parse((PACKAGE_ROOT / f"{module_name}.py").read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.level:
            continue
        if node.module:
            imports.add(node.module.split(".", maxsplit=1)[0])
        else:
            imports.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
    return imports


def test_gui_and_cli_do_not_depend_on_each_other():
    assert "cli" not in local_imports("app")
    assert "app" not in local_imports("cli")


def test_shared_simulation_service_has_no_presentation_dependency():
    imports = local_imports("simulation_service")
    assert not imports.intersection({"app", "cli"})


def test_session_models_and_store_stay_independent_from_presentation_and_simulation():
    forbidden = {"app", "cli", "simulation_service", "rendering", "video_export"}
    for module_name in ("session_persistence", "condition_store", "comparison"):
        assert not local_imports(module_name).intersection(forbidden), module_name


def test_rendering_and_exports_do_not_depend_on_presentation_or_cli():
    forbidden = {"app", "cli", "simulation_service", "session_persistence", "condition_store"}
    for module_name in (
        "rendering",
        "scene_model",
        "export_io",
        "export_schema",
        "workbook_model",
        "xlsx_writers",
        "video_export",
    ):
        assert not local_imports(module_name).intersection(forbidden), module_name
