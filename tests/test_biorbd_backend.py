import math
import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path

from squat_gui.anthropometry import Anthropometry
from squat_gui.backend import BiorbdModelCache
from squat_gui.dynamics import simulate


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


if __name__ == "__main__":
    unittest.main()
