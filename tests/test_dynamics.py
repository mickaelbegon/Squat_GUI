import math
import unittest

from squat_gui.anthropometry import Anthropometry
from squat_gui.dynamics import simulate


class DynamicsTests(unittest.TestCase):
    def test_mass_includes_bar_load(self) -> None:
        anthro = Anthropometry(bar_mass=40.0)
        self.assertAlmostEqual(anthro.total_mass, 110.0)

    def test_simulation_produces_finite_values(self) -> None:
        anthro = Anthropometry(bar_mass=20.0)
        states, results = simulate(
            anthro,
            (math.radians(20.0), math.radians(-55.0), math.radians(-15.0)),
            1.2,
            11,
            {"cheville": 180.0, "genou": 220.0, "hanche": 260.0},
            True,
        )
        self.assertEqual(len(states), 11)
        self.assertEqual(len(results), 11)
        for result in results:
            self.assertTrue(math.isfinite(result.cop_x))
            self.assertTrue(math.isfinite(result.ground_reaction[0]))
            self.assertTrue(math.isfinite(result.ground_reaction[1]))
            for torque in result.torques.values():
                self.assertTrue(math.isfinite(torque))

    def test_motion_has_eccentric_then_concentric_phases(self) -> None:
        anthro = Anthropometry()
        states, _ = simulate(
            anthro,
            (math.radians(20.0), math.radians(-55.0), math.radians(-15.0)),
            1.0,
            5,
            {"cheville": 180.0, "genou": 220.0, "hanche": 260.0},
            False,
        )
        self.assertEqual(states[0].phase, "excentrique")
        self.assertEqual(states[2].phase, "excentrique")
        self.assertEqual(states[3].phase, "concentrique")
        self.assertAlmostEqual(states[0].q[0], 0.0)
        self.assertAlmostEqual(states[2].q[0], math.radians(20.0))
        self.assertAlmostEqual(states[-1].q[0], 0.0)


if __name__ == "__main__":
    unittest.main()
