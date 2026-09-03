"""Characterize the GUI-settings and CLI condition paths without Tk.

The GUI persists a mapping produced by ``SquatGui.current_settings``.  These
tests deliberately exercise that public-compatible mapping through
``condition_from_settings`` rather than creating a Tk root, then compare it
to the command-line parser path.  They protect the scientific calculation
while the GUI/CLI responsibilities are refactored.
"""

from __future__ import annotations

import unittest

from squat_gui.cli import (
    DEFAULT_SEGMENT_ANGLES_DEG,
    build_parser,
    condition_from_args,
    condition_from_settings,
    simulate_condition,
)


class GuiCliCharacterizationTests(unittest.TestCase):
    """GUI-compatible settings must remain equivalent to CLI inputs."""

    @staticmethod
    def _cli_condition(*arguments: str):
        args = build_parser().parse_args(["run", *arguments])
        return condition_from_args(args)

    def assert_equivalent_simulation(self, gui_condition, cli_condition) -> None:
        self.assertEqual(gui_condition, cli_condition)

        gui_rows, gui_summary = simulate_condition(gui_condition)
        cli_rows, cli_summary = simulate_condition(cli_condition)

        # The analytical backend is deterministic.  Full equality protects
        # both the exported parameters and every sampled trajectory value.
        self.assertEqual(gui_rows, cli_rows)
        self.assertEqual(gui_summary, cli_summary)

    def test_default_gui_settings_match_standard_cli_condition(self) -> None:
        gui_condition = condition_from_settings(
            {},
            DEFAULT_SEGMENT_ANGLES_DEG,
            "standard",
            frames=7,
            backend="analytical",
        )
        cli_condition = self._cli_condition(
            "--condition-id",
            "standard",
            "--frames",
            "7",
            "--backend",
            "analytical",
        )

        self.assert_equivalent_simulation(gui_condition, cli_condition)

    def test_gui_settings_match_cli_with_timing_morphology_and_torques(self) -> None:
        gui_settings = {
            "subject_profile": "homme",
            "bar_position": "front",
            "load_percent_bw": 65.0,
            "wedge_20_deg": True,
            "shank_percent": 5.0,
            "thigh_percent": -5.0,
            "trunk_percent": 2.5,
            "anthropometry_mode": "morphotype recalibre",
            "duration_excentrique_s": 1.0,
            "duration_isometrique_s": 0.5,
            "duration_concentrique_s": 2.0,
            "torque_preset": "Sportifs",
            "max_torques": {
                "cheville": 211.0,
                "genou": 344.0,
                "hanche": 377.0,
            },
            "angle_adapt": False,
            "velocity_adapt": False,
        }
        final_q_deg = (30.0, -65.0, 10.0)
        gui_condition = condition_from_settings(
            gui_settings,
            final_q_deg,
            "options",
            frames=9,
            backend="analytical",
        )
        cli_condition = self._cli_condition(
            "--condition-id",
            "options",
            "--load-percent-bw",
            "65",
            "--bar-position",
            "front",
            "--wedge",
            "--shank",
            "5",
            "--thigh",
            "-5",
            "--trunk",
            "2.5",
            "--anthropometry-mode",
            "morphotype recalibre",
            "--duration-excentrique",
            "1",
            "--duration-isometrique",
            "0.5",
            "--duration-concentrique",
            "2",
            "--q-segment-deg",
            "30",
            "-65",
            "10",
            "--torque-preset",
            "sportifs",
            "--max-cheville",
            "211",
            "--max-genou",
            "344",
            "--max-hanche",
            "377",
            "--angle-adapt",
            "false",
            "--velocity-adapt",
            "false",
            "--frames",
            "9",
            "--backend",
            "analytical",
        )

        self.assert_equivalent_simulation(gui_condition, cli_condition)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
