import unittest
from unittest.mock import patch

from squat_gui.anthropometry import Anthropometry
from squat_gui.backend import (
    detect_optional_backends,
    optional_module_importable,
    resolve_biorbd_model,
)


class OptionalBackendDetectionTests(unittest.TestCase):
    def test_installed_but_non_importable_extension_is_unavailable(self) -> None:
        with (
            patch("squat_gui.backend.find_spec", return_value=object()),
            patch(
                "squat_gui.backend.import_module",
                side_effect=ImportError("numpy ABI mismatch"),
            ),
        ):
            self.assertFalse(optional_module_importable("biorbd"))

    def test_importable_extension_is_available(self) -> None:
        with (
            patch("squat_gui.backend.find_spec", return_value=object()),
            patch(
                "squat_gui.backend.import_module",
                return_value=object(),
            ),
        ):
            self.assertTrue(optional_module_importable("biorbd"))

    def test_biorbd_is_active_without_unused_biobuddy(self) -> None:
        with patch(
            "squat_gui.backend.optional_module_importable",
            side_effect=lambda name: name == "biorbd",
        ):
            status = detect_optional_backends()
        self.assertTrue(status.biorbd_available)
        self.assertFalse(status.biobuddy_available)
        self.assertIn("biorbd disponible", status.message)
        self.assertNotIn("backend analytique actif", status.message)

    def test_model_resolution_reports_the_analytical_choice(self) -> None:
        resolution = resolve_biorbd_model(None, Anthropometry())

        self.assertIsNone(resolution.model)
        self.assertFalse(resolution.uses_biorbd)
        self.assertIn("analytique", resolution.diagnostic.lower())

    def test_model_resolution_preserves_fallback_and_reports_failure(self) -> None:
        class BrokenCache:
            def model_for(self, _anthro):
                raise RuntimeError("native extension mismatch")

        resolution = resolve_biorbd_model(BrokenCache(), Anthropometry())

        self.assertIsNone(resolution.model)
        self.assertFalse(resolution.uses_biorbd)
        self.assertIn("Fallback analytique", resolution.diagnostic)
        self.assertIn("RuntimeError", resolution.diagnostic)

    def test_model_resolution_reports_success(self) -> None:
        model = object()

        class Cache:
            def model_for(self, _anthro):
                return model

        resolution = resolve_biorbd_model(Cache(), Anthropometry())

        self.assertIs(resolution.model, model)
        self.assertTrue(resolution.uses_biorbd)
        self.assertEqual(resolution.diagnostic, "Backend biorbd actif.")


if __name__ == "__main__":
    unittest.main()
