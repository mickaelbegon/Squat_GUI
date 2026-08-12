import unittest
from unittest.mock import patch

from squat_gui.backend import detect_optional_backends, optional_module_importable


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


if __name__ == "__main__":
    unittest.main()
