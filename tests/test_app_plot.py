import json
import tempfile
import unittest
from math import radians
from pathlib import Path
from unittest.mock import patch

from squat_gui.anthropometry import Anthropometry
from squat_gui.app import (
    LOAD_PERCENT_OPTIONS,
    PLOT_CHOICES,
    SYNCHRONIZED_KINEMATICS_CHOICE,
    SquatGui,
)
from squat_gui.didactics import RevealMode
from squat_gui.dynamics import inverse_dynamics
from squat_gui.kinematics import motion_state, zmp_support_limits
from squat_gui.kinematics import PhaseDurations
from squat_gui.timeline import TimeMode


class FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeTable:
    def selection(self):
        return ("cond1", "cond2")


class RecordingCanvas:
    def __init__(self):
        self.texts = []
        self.lines = []
        self.rectangles = []
        self.ovals = []

    def create_line(self, *args, **kwargs):
        self.lines.append((args, kwargs))

    def create_text(self, *args, **kwargs):
        self.texts.append((args, kwargs))
        return len(self.texts)

    def create_rectangle(self, *args, **kwargs):
        self.rectangles.append((args, kwargs))
        return len(self.rectangles)

    def create_oval(self, *args, **kwargs):
        self.ovals.append((args, kwargs))
        return len(self.ovals)

    def bbox(self, _item):
        return (16, 62, 500, 104)

    def tag_lower(self, _item, _below):
        pass

    def winfo_width(self):
        return 320


class FakeCursorTable:
    def __init__(self):
        self.rows = {}
        self.count = 0

    def get_children(self):
        return tuple(self.rows)

    def delete(self, iid):
        self.rows.pop(iid, None)

    def insert(self, _parent, _position, values):
        self.count += 1
        iid = f"row-{self.count}"
        self.rows[iid] = values
        return iid


class PlotSeriesTests(unittest.TestCase):
    def test_csv_export_writes_time_series_and_summary_without_cli(self):
        gui = self.gui_without_tk()
        gui.current_settings = lambda: {
            "subject_profile": "homme",
            "bar_position": "back",
        }
        gui.final_q = (radians(22.0), radians(-58.0), radians(20.0))
        gui.saved_conditions = {}
        gui.status_var = FakeVar("")

        with tempfile.TemporaryDirectory() as temporary:
            csv_path = Path(temporary) / "resultats.csv"
            exported = gui.export_csv_results(csv_path)

            self.assertIsNotNone(exported)
            assert exported is not None
            output, summary_path = exported
            self.assertTrue(output.exists())
            self.assertIn("zmp_in_support", output.read_text(encoding="utf-8").splitlines()[0])
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["csv"], "resultats.csv")
            self.assertEqual(len(payload["conditions"]), 1)
            self.assertIn(
                "zmp_outside_support_frames", payload["conditions"][0]
            )

    def test_bar_trajectory_stops_at_the_lowest_bar_position(self):
        gui = object.__new__(SquatGui)
        canvas = RecordingCanvas()
        gui.world_to_canvas = lambda _canvas, point, _bounds: point
        states = self.gui_without_tk().states

        gui.draw_bar_trajectory(canvas, states, (-1.0, 1.0, -1.0, 2.0), 0.0, "#123456")

        self.assertEqual(len(canvas.lines), 1)
        self.assertEqual(len(canvas.ovals), 2)
        line_coordinates = canvas.lines[0][0]
        bottom_index = min(range(len(states)), key=lambda index: states[index].pose.bar[1])
        self.assertEqual(len(line_coordinates), 2 * (bottom_index + 1))
        self.assertEqual(canvas.texts[-2][1]["text"], "haut")
        self.assertEqual(canvas.texts[-1][1]["text"], "bas")

    def test_alert_banner_wraps_each_alert_on_its_own_line(self):
        canvas = RecordingCanvas()

        SquatGui.draw_alert_banner(
            object.__new__(SquatGui),
            canvas,
            [
                "Condition 1 : CoP hors zone fonctionnelle d'appui",
                "Condition 2 : faisabilité mécanique U > 1",
            ],
            62,
        )

        _args, options = canvas.texts[0]
        self.assertIn("\n• Condition 1", options["text"])
        self.assertIn("\n• Condition 2", options["text"])
        self.assertEqual(options["width"], 288)
        self.assertEqual(len(canvas.rectangles), 1)

    def test_animation_uses_elapsed_wall_time_and_skips_late_frames(self):
        gui = object.__new__(SquatGui)
        gui.playing = True
        gui.frame_count = 201
        gui.frame_var = FakeVar(20)
        gui._play_started_at = 100.0
        gui._play_start_time_s = 1.0
        gui.redraw = lambda: None
        scheduled = []
        gui.after = lambda delay, callback: scheduled.append((delay, callback))

        with patch("squat_gui.app.perf_counter", return_value=102.05):
            gui.step_animation()

        self.assertEqual(gui.frame_var.get(), 61)
        self.assertEqual(scheduled[0][0], 50)

    def test_charge_popup_uses_discrete_percent_bw_steps(self):
        self.assertEqual(LOAD_PERCENT_OPTIONS, (0.0, 25.0, 50.0, 75.0, 100.0))

        gui = object.__new__(SquatGui)
        gui.load_var = FakeVar(34.0)
        gui.load_display_var = FakeVar("")
        gui._sync_load_display()
        self.assertEqual(gui.load_var.get(), 25.0)
        self.assertEqual(gui.load_display_var.get(), "25 %BW")

    def test_charge_popup_selection_updates_numeric_setting(self):
        gui = object.__new__(SquatGui)
        gui.load_var = FakeVar(0.0)
        gui.load_display_var = FakeVar("75 %BW")
        gui.parameter_changed = False
        gui.on_parameter_changed = lambda: setattr(gui, "parameter_changed", True)

        gui.on_load_menu_changed()

        self.assertEqual(gui.load_var.get(), 75.0)
        self.assertTrue(gui.parameter_changed)

    def test_manual_duration_change_clears_the_temporal_preset(self):
        gui = object.__new__(SquatGui)
        gui.temporal_preset_var = FakeVar("Rapide")
        gui.temporal_preset_display_var = FakeVar("Rapide — 1 | 0.5 | 1 s")
        gui.parameter_changed = False
        gui.on_parameter_changed = lambda: setattr(gui, "parameter_changed", True)

        gui.on_duration_changed()

        self.assertEqual(gui.temporal_preset_var.get(), "")
        self.assertEqual(gui.temporal_preset_display_var.get(), "")
        self.assertTrue(gui.parameter_changed)

    def test_main_plot_menu_groups_joint_kinematics(self):
        self.assertIn("cinematique articulaire", PLOT_CHOICES)
        self.assertNotIn("positions articulaires", PLOT_CHOICES)
        self.assertNotIn("vitesses articulaires", PLOT_CHOICES)
        self.assertNotIn("accelerations articulaires", PLOT_CHOICES)
        self.assertIn("couples detailles", PLOT_CHOICES)

    def test_detailed_torques_remain_available_with_multiple_conditions(self):
        gui = object.__new__(SquatGui)
        gui.conditions_table = FakeTable()

        self.assertIn("couples detailles", gui.available_plot_choices())

    def test_reveal_modes_constrain_plot_choices(self):
        gui = object.__new__(SquatGui)
        gui.__dict__["reveal_mode_var"] = FakeVar(RevealMode.OBSERVATION.value)
        self.assertEqual(gui.available_plot_choices(), [])

        gui.__dict__["reveal_mode_var"] = FakeVar(RevealMode.KINEMATICS.value)
        self.assertEqual(
            gui.available_plot_choices(),
            [
                SYNCHRONIZED_KINEMATICS_CHOICE,
                "cinematique articulaire",
                "centre de masse",
            ],
        )

        gui.__dict__["reveal_mode_var"] = FakeVar(RevealMode.DYNAMICS.value)
        self.assertEqual(gui.available_plot_choices(), PLOT_CHOICES)

    def test_multiple_conditions_keep_their_own_sprite_variant_and_quality(self):
        gui = self.gui_without_tk()
        gui.conditions_table = FakeTable()
        gui.saved_conditions = {
            "cond1": {
                "label": "homme back",
                "states": gui.states,
                "results": gui.results,
                "settings": {
                    "subject_profile": "homme",
                    "bar_position": "back",
                    "low_quality_sprites": False,
                },
            },
            "cond2": {
                "label": "femme overhead",
                "states": gui.states,
                "results": gui.results,
                "settings": {
                    "subject_profile": "femme enceinte",
                    "bar_position": "over-head",
                    "wedge_20_deg": True,
                    "low_quality_sprites": True,
                },
            },
        }
        datasets = gui.plot_datasets()

        self.assertEqual(datasets[1]["anthro"].subject_profile, "femme enceinte")
        self.assertEqual(datasets[1]["anthro"].bar_position, "over-head")
        self.assertEqual(datasets[1]["anthro"].wedge_angle_deg, 20.0)
        self.assertFalse(datasets[1]["refined_sprites"])
        with patch(
            "squat_gui.app.draw_sprite_segment", side_effect=lambda *args: True
        ) as draw_sprite:
            gui.draw_raster_segments(
                None,
                gui.states[0],
                lambda point: point,
                datasets[1]["anthro"],
                datasets[1]["refined_sprites"],
            )
        trunk_call = draw_sprite.call_args_list[-1].args
        self.assertFalse(trunk_call[5])
        self.assertEqual(trunk_call[6], ("femme enceinte", "over-head"))

    def gui_without_tk(self):
        anthro = Anthropometry()
        states = [
            motion_state(anthro, (0.2, -0.5, -0.2), 1.0, time)
            for time in (0.0, 0.5, 1.0)
        ]
        results = [
            inverse_dynamics(
                anthro, state, {"cheville": 180, "genou": 220, "hanche": 260}, True
            )
            for state in states
        ]
        gui = object.__new__(SquatGui)
        gui.states = states
        gui.results = results
        gui.show_vars = {
            "cheville": FakeVar(True),
            "genou": FakeVar(True),
            "hanche": FakeVar(True),
        }
        gui.quantity_var = FakeVar("vitesse")
        gui.com_component_vars = {
            "horizontal": FakeVar(True),
            "vertical": FakeVar(False),
        }
        gui.torque_component_vars = {
            "M(q) qddot": FakeVar(True),
            "termes qdot": FakeVar(True),
            "gravité": FakeVar(True),
            "contact externe (signé)": FakeVar(True),
            "total ID": FakeVar(True),
        }
        gui.time_mode_var = FakeVar(TimeMode.CENTERED.value)
        return gui

    def test_kinematic_series_do_not_include_com(self):
        gui = self.gui_without_tk()

        self.assertEqual(
            list(gui.plot_series("cinematique articulaire")),
            ["cheville", "genou", "hanche"],
        )
        self.assertEqual(gui.plot_unit("cinematique articulaire"), "deg/s")

    def test_com_series_uses_quantity_and_components(self):
        gui = self.gui_without_tk()

        self.assertEqual(list(gui.plot_series("centre de masse")), ["horizontal"])
        self.assertEqual(gui.plot_unit("centre de masse"), "m/s")

    def test_synchronized_kinematics_exposes_all_three_orders(self):
        gui = self.gui_without_tk()

        orders = {
            quantity: gui.synchronized_series_for(
                "angles articulaires",
                quantity,
                gui.states,
                gui.results,
            )
            for quantity in ("position", "vitesse", "acceleration")
        }

        self.assertEqual(set(orders), {"position", "vitesse", "acceleration"})
        self.assertTrue(
            all(
                list(series) == ["cheville", "genou", "hanche"]
                for series in orders.values()
            )
        )
        self.assertEqual(
            gui.kinematic_unit("angles articulaires", "acceleration"), "deg/s²"
        )

    def test_cursor_table_reports_exact_visible_sample(self):
        gui = self.gui_without_tk()
        gui.cursor_table = FakeCursorTable()
        gui.show_phase_names_var = FakeVar(True)
        gui.current_plot_time = lambda: 0.0
        plotted = [
            {
                "label": "courant",
                "times": [-0.5, 0.0, 0.5],
                "states": gui.states,
                "series": {"cheville": [1.0, 2.1234567, 3.0]},
            }
        ]

        gui.update_cursor_table(plotted, "cinematique articulaire")

        row = next(iter(gui.cursor_table.rows.values()))
        self.assertEqual(row[1], "cheville")
        self.assertEqual(row[2], "2.123457")
        self.assertEqual(row[3], "deg/s")
        self.assertEqual(row[4], "0.000 s")

    def test_plot_click_moves_the_shared_cursor(self):
        gui = object.__new__(SquatGui)
        gui.__dict__["frame_var"] = FakeVar(0)
        gui.__dict__["frame_count"] = 201
        gui.__dict__["_plot_hit_regions"] = [(0.0, 100.0, 0.0, 100.0, -5.0, 5.0)]
        gui.redraw = lambda: None
        event = type("Event", (), {"x": 75.0, "y": 50.0})()

        gui.on_plot_cursor_event(event)

        self.assertEqual(gui.frame_var.get(), 150)

    def test_saved_legacy_six_second_dynamic_phases_are_capped_at_four(self):
        durations = SquatGui.phase_durations_from_settings(
            {
                "duration_excentrique_s": 6.0,
                "duration_isometrique_s": 2.0,
                "duration_concentrique_s": 6.0,
            }
        )

        self.assertEqual(durations.excentrique, 4.0)
        self.assertEqual(durations.concentrique, 4.0)

    def test_ground_reaction_series_uses_horizontal_vertical_components(self):
        gui = self.gui_without_tk()

        series = gui.plot_series("force reaction sol")

        self.assertEqual(list(series), ["horizontal"])
        self.assertEqual(gui.plot_unit("force reaction sol"), "N")
        self.assertEqual(series["horizontal"][0], gui.results[0].ground_reaction[0])

    def test_body_weight_reference_line_uses_mass_times_gravity(self):
        gui = object.__new__(SquatGui)
        canvas = RecordingCanvas()
        anthro = Anthropometry(bar_mass=30.0)

        gui.draw_body_weight_line(
            canvas,
            [{"anthro": anthro}],
            0.0,
            100.0,
            100.0,
            0.0,
            0.0,
            2000.0,
        )

        self.assertEqual(len(canvas.lines), 1)
        self.assertEqual(len(canvas.texts), 1)
        self.assertEqual(canvas.texts[0][1]["text"], "m·g 981 N")

    def test_normalized_plot_times_are_percent_of_movement(self):
        gui = self.gui_without_tk()
        gui.time_mode_var = FakeVar(TimeMode.NORMALIZED.value)

        self.assertEqual(gui.plot_times(gui.states), [0.0, 50.0, 100.0])
        self.assertEqual(
            gui.plot_time_bounds([{"times": gui.plot_times(gui.states)}]), (0.0, 100.0)
        )

    def test_absolute_plot_times_keep_seconds_since_start(self):
        gui = self.gui_without_tk()
        gui.time_mode_var = FakeVar(TimeMode.ABSOLUTE.value)

        self.assertEqual(gui.plot_times(gui.states), [0.0, 0.5, 1.0])
        self.assertEqual(gui.animation_time_label(0.5), "temps absolu=0.50s")

    def test_normalized_comparison_warns_that_duration_is_hidden(self):
        gui = self.gui_without_tk()
        gui.time_mode_var = FakeVar(TimeMode.NORMALIZED.value)
        datasets = [
            {"durations": PhaseDurations(4.0, 2.0, 4.0)},
            {"durations": PhaseDurations(6.0, 2.0, 6.0)},
        ]

        self.assertIn(
            "différences de durée sont masquées", gui.time_mode_notice(datasets)
        )

    def test_display_change_never_recomputes_scientific_results(self):
        gui = object.__new__(SquatGui)
        calls = []
        gui.update_plot_choices = lambda: calls.append("redraw")
        gui.recompute = lambda: self.fail("display change must not recompute")

        gui.on_display_changed()

        self.assertEqual(calls, ["redraw"])

    def test_normalized_torque_series_uses_effort_ratios(self):
        gui = self.gui_without_tk()

        self.assertIn("couples normalises", PLOT_CHOICES)
        series = gui.plot_series("couples normalises")

        self.assertEqual(list(series), ["cheville", "genou", "hanche"])
        self.assertEqual(gui.plot_unit("couples normalises"), "% max")
        self.assertAlmostEqual(
            series["cheville"][0], 100.0 * gui.results[0].effort_ratios["cheville"]
        )

    def test_detailed_torque_series_include_all_components(self):
        gui = self.gui_without_tk()

        series = gui.plot_series("couples detailles")

        self.assertIn("cheville M(q) qddot", series)
        self.assertIn("cheville termes qdot", series)
        self.assertIn("cheville gravité", series)
        self.assertIn("cheville contact externe (signé)", series)
        self.assertIn("cheville total ID", series)
        self.assertEqual(len(series["cheville M(q) qddot"]), len(gui.results))

    def test_detailed_torque_components_can_be_hidden_without_recomputation(self):
        gui = self.gui_without_tk()
        gui.torque_component_vars["termes qdot"].set(False)

        series = gui.plot_series("couples detailles")

        self.assertNotIn("cheville termes qdot", series)
        self.assertIn("cheville total ID", series)

    def test_biomechanical_alerts_report_cop_and_torque_problems(self):
        gui = self.gui_without_tk()
        state = gui.states[0]
        result = gui.results[0]

        safe = result.__class__(
            **{
                **result.__dict__,
                "cop_x": (state.pose.heel[0] + state.pose.toe[0]) / 2,
                "effort_ratios": {"cheville": 0.2, "genou": 0.3, "hanche": 0.4},
            }
        )
        unsafe = result.__class__(
            **{
                **result.__dict__,
                "cop_x": state.pose.toe[0] + 0.1,
                "effort_ratios": {"cheville": 1.2, "genou": 0.3, "hanche": 1.1},
            }
        )
        posterior, _ = zmp_support_limits(state.pose)
        rear_edge = result.__class__(
            **{
                **result.__dict__,
                "cop_x": posterior - 0.001,
                "effort_ratios": {"cheville": 0.2, "genou": 0.3, "hanche": 0.4},
            }
        )

        self.assertEqual(gui.biomechanical_alerts(state, safe, include_com=False), [])
        self.assertEqual(
            gui.biomechanical_alerts(state, unsafe, include_com=False),
            [
                "CoP hors zone fonctionnelle d'appui",
                "faisabilité mécanique U > 1 sous les hypothèses du modèle: cheville, hanche",
            ],
        )
        self.assertEqual(
            gui.biomechanical_alerts(state, rear_edge, include_com=False),
            ["CoP hors zone fonctionnelle d'appui"],
        )

    def test_pose_limits_are_applied_in_joint_coordinates(self):
        gui = object.__new__(SquatGui)
        q = gui.clamp_final_q((radians(80), radians(-180), radians(100)))
        ankle, knee, hip = gui.display_joint_angles(q)

        self.assertAlmostEqual(ankle, 40.0)
        self.assertGreaterEqual(knee, -140.0)
        self.assertLessEqual(knee, 0.0)
        self.assertGreaterEqual(hip, -15.0)
        self.assertLessEqual(hip, 120.0)


if __name__ == "__main__":
    unittest.main()
