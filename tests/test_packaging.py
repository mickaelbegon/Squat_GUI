"""Static release-contract checks for the student bundles."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PackagingContractTests(unittest.TestCase):
    def test_release_version_is_consistent(self) -> None:
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        package = (ROOT / "src" / "squat_gui" / "__init__.py").read_text(
            encoding="utf-8"
        )
        spec = (ROOT / "packaging" / "squat_gui.spec").read_text(encoding="utf-8")
        windows_version = (ROOT / "packaging" / "windows_version_info.txt").read_text(
            encoding="utf-8"
        )
        for source in (project, package, spec, windows_version):
            self.assertIn('0.2.0', source)

    def test_build_scripts_install_video_runtime(self) -> None:
        macos = (ROOT / "packaging" / "build_macos.sh").read_text(encoding="utf-8")
        windows = (ROOT / "packaging" / "build_windows.ps1").read_text(
            encoding="utf-8"
        )
        for module in ("numpy", "imageio", "imageio_ffmpeg"):
            self.assertIn(module, macos)
            self.assertIn(module, windows)
        self.assertIn("openpyxl", macos)
        self.assertIn("openpyxl", windows)
        self.assertIn("scipy", macos)
        self.assertIn("scipy", windows)

    def test_conda_setup_installs_workbook_dependency(self) -> None:
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        development_guide = (ROOT / "DOCS" / "DEVELOPMENT.md").read_text(
            encoding="utf-8"
        )
        self.assertIn('"openpyxl>=3.1,<4"', project)
        self.assertIn('"openpyxl>=3.1"', development_guide)
        self.assertIn('"scipy>=1.10,<1.17"', project)
        self.assertIn('"scipy>=1.10,<1.17"', development_guide)
        self.assertIn('"libblas=*=*openblas"', development_guide)

    def test_pyinstaller_bundle_contains_video_and_workbook_assets(self) -> None:
        spec = (ROOT / "packaging" / "squat_gui.spec").read_text(encoding="utf-8")
        self.assertIn('"build_workbook.mjs"', spec)
        self.assertIn('"imageio"', spec)
        self.assertIn('"imageio_ffmpeg"', spec)
        self.assertIn('"openpyxl"', spec)
        self.assertIn('"scipy"', spec)

    def test_frozen_smoke_test_encodes_video_and_checks_optional_backends(self) -> None:
        launcher = (ROOT / "packaging" / "squat_gui_launcher.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("export_mp4", launcher)
        self.assertIn("reader.count_frames()", launcher)
        self.assertIn('import_module("biorbd")', launcher)
        self.assertIn('result.backend == "biorbd"', launcher)
        self.assertIn('excel_report["writer"] == "openpyxl"', launcher)

    def test_external_release_validators_cover_clean_profiles_and_exports(self) -> None:
        macos = (ROOT / "packaging" / "validate_macos_release.sh").read_text(
            encoding="utf-8"
        )
        windows = (ROOT / "packaging" / "validate_windows_release.ps1").read_text(
            encoding="utf-8"
        )
        for validator in (macos, windows):
            self.assertIn("SQUAT_GUI_SMOKE_TEST", validator)
            self.assertIn("SQUAT_GUI_NODE", validator)
            self.assertIn("0.2.0", validator)
        self.assertIn("CFBundleShortVersionString", macos)
        self.assertIn("ProductVersion", windows)


if __name__ == "__main__":
    unittest.main()
