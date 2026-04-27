import math
import unittest

from squat_gui.yeadon import QuinticBoundaryTrajectory


class QuinticTests(unittest.TestCase):
    def test_boundary_conditions(self) -> None:
        trajectory = QuinticBoundaryTrajectory(0.0, 0.3, math.pi, 0.0)
        self.assertAlmostEqual(trajectory.position(0.0), math.pi)
        self.assertAlmostEqual(trajectory.position(0.3), 0.0)
        self.assertAlmostEqual(trajectory.velocity(0.0), 0.0)
        self.assertAlmostEqual(trajectory.velocity(0.3), 0.0)
        self.assertAlmostEqual(trajectory.acceleration(0.0), 0.0)
        self.assertAlmostEqual(trajectory.acceleration(0.3), 0.0)

    def test_clamps_outside_interval(self) -> None:
        trajectory = QuinticBoundaryTrajectory(0.1, 0.4, 1.2, -0.3)
        self.assertAlmostEqual(trajectory.position(-1.0), 1.2)
        self.assertAlmostEqual(trajectory.position(10.0), -0.3)
        self.assertAlmostEqual(trajectory.velocity(-1.0), 0.0)
        self.assertAlmostEqual(trajectory.acceleration(10.0), 0.0)


if __name__ == "__main__":
    unittest.main()
