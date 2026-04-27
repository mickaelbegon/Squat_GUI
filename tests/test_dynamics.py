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


if __name__ == "__main__":
    unittest.main()
