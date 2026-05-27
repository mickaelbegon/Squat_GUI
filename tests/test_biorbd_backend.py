import math
import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path

from squat_gui.anthropometry import Anthropometry
from squat_gui.backend import BiorbdModelCache
from squat_gui.dynamics import simulate
from squat_gui.kinematics import PhaseDurations, motion_state


@unittest.skipUnless(find_spec("biorbd") is not None, "biorbd is not installed")
class BiorbdBackendTests(unittest.TestCase):
    def test_simulation_uses_cached_biorbd_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = BiorbdModelCache(Path(tmpdir))
            anthro = Anthropometry(bar_mass=20.0)
            states, results = simulate(
                anthro,
                (math.radians(20.0), math.radians(-55.0), math.radians(-15.0)),
                1.2,
                7,
                {"cheville": 180.0, "genou": 220.0, "hanche": 260.0},
                True,
                cache,
            )

            self.assertEqual(len(states), 7)
            self.assertTrue(cache.cached_path_for(anthro).exists())
            self.assertTrue(all(result.backend == "biorbd" for result in results))
            self.assertAlmostEqual(states[3].pose.com[0], results[3].com[0])
            self.assertAlmostEqual(states[3].pose.com[1], results[3].com[1])
            self.assertTrue(math.isfinite(results[3].com_velocity[1]))
            self.assertTrue(math.isfinite(results[3].com_acceleration[1]))
            self.assertTrue(math.isfinite(results[3].dynamic_moment_z))

    def test_wedge_standing_compensation_matches_biorbd_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            anthro = Anthropometry(
                bar_mass=21.0,
                subject_profile="femme enceinte",
                bar_position="over-head",
                wedge_angle_deg=20.0,
            )
            durations = PhaseDurations(2.0, 2.0, 2.0)
            final_q = (math.radians(22.0), math.radians(-80.0), math.radians(78.0))
            expected = motion_state(anthro, final_q, durations, 0.0)
            states, results = simulate(
                anthro,
                final_q,
                durations,
                5,
                {"cheville": 222.0, "genou": 380.0, "hanche": 376.0},
                True,
                BiorbdModelCache(Path(tmpdir)),
            )

            self.assertAlmostEqual(math.degrees(states[0].q[0]), -20.0)
            self.assertGreater(states[0].pose.heel[1], states[0].pose.toe[1])
            self.assertAlmostEqual(results[0].com[0], expected.pose.com[0], places=5)
            self.assertAlmostEqual(results[0].com[1], expected.pose.com[1], places=5)


if __name__ == "__main__":
    unittest.main()
