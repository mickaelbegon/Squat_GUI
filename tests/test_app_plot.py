import unittest

from squat_gui.anthropometry import Anthropometry
from squat_gui.app import PLOT_CHOICES, SquatGui
from squat_gui.dynamics import inverse_dynamics
from squat_gui.kinematics import motion_state


class FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class PlotSeriesTests(unittest.TestCase):
    def test_main_plot_menu_groups_joint_kinematics(self):
        self.assertIn("cinematique articulaire", PLOT_CHOICES)
        self.assertNotIn("positions articulaires", PLOT_CHOICES)
        self.assertNotIn("vitesses articulaires", PLOT_CHOICES)
        self.assertNotIn("accelerations articulaires", PLOT_CHOICES)

    def gui_without_tk(self):
        anthro = Anthropometry()
        states = [motion_state(anthro, (0.2, -0.5, -0.2), 1.0, time) for time in (0.0, 0.5, 1.0)]
        results = [
            inverse_dynamics(anthro, state, {"cheville": 180, "genou": 220, "hanche": 260}, True)
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
        gui.com_component_vars = {"x": FakeVar(True), "y": FakeVar(False)}
        return gui

    def test_kinematic_series_do_not_include_com(self):
        gui = self.gui_without_tk()

        self.assertEqual(list(gui.plot_series("cinematique articulaire")), ["cheville", "genou", "hanche"])
        self.assertEqual(gui.plot_unit("cinematique articulaire"), "deg/s")

    def test_com_series_uses_quantity_and_components(self):
        gui = self.gui_without_tk()

        self.assertEqual(list(gui.plot_series("centre de masse")), ["CoM x"])
        self.assertEqual(gui.plot_unit("centre de masse"), "m/s")

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

        self.assertEqual(gui.biomechanical_alerts(state, safe, include_com=False), [])
        self.assertEqual(
            gui.biomechanical_alerts(state, unsafe, include_com=False),
            ["CoP hors pied", "couple > max: cheville, hanche"],
        )


if __name__ == "__main__":
    unittest.main()
