import math
import tempfile
import unittest
from pathlib import Path

from squat_gui.anthropometry import Anthropometry
from squat_gui.backend import BiorbdModelCache, detect_optional_backends
from squat_gui.dynamics import _contact_moments, simulate
from squat_gui.kinematics import (
    PhaseDurations,
    balanced_standing_angles,
    motion_state,
)


@unittest.skipUnless(
    detect_optional_backends().biorbd_available,
    "biorbd is absent or cannot import its native extensions",
)
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

            self.assertEqual(states[0].q, balanced_standing_angles(anthro))
            self.assertGreater(states[0].pose.heel[1], states[0].pose.toe[1])
            self.assertAlmostEqual(results[0].com[0], expected.pose.com[0], places=5)
            self.assertAlmostEqual(results[0].com[1], expected.pose.com[1], places=5)
            self.assertTrue(all(result.backend == "biorbd" for result in results))

    def test_contact_component_is_computed_with_biorbd_external_force_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            anthro = Anthropometry(bar_mass=28.0, bar_position="back")
            states, results = simulate(
                anthro,
                (math.radians(22.0), math.radians(-58.0), math.radians(20.0)),
                PhaseDurations(4.0, 1.0, 4.0),
                5,
                {"cheville": 222.0, "genou": 380.0, "hanche": 376.0},
                True,
                BiorbdModelCache(Path(tmpdir)),
            )
            state = states[2]
            result = results[2]
            self.assertEqual(result.backend, "biorbd")
            self.assertEqual(result.contact_source, "biorbd.ExternalForceSet")
            geometric = _contact_moments(state, result.ground_reaction, result.cop_x)

            for joint in ("cheville", "genou", "hanche"):
                self.assertAlmostEqual(
                    result.torque_components[joint]["contact"],
                    geometric[joint],
                    places=8,
                )
                self.assertAlmostEqual(
                    result.torque_components[joint]["total"],
                    result.torque_components[joint]["mass_acceleration"]
                    + result.torque_components[joint]["velocity"]
                    + result.torque_components[joint]["gravity"],
                    places=8,
                )
                self.assertAlmostEqual(
                    result.torque_components[joint]["total_with_external_contact"],
                    result.torque_components[joint]["total"]
                    + result.torque_components[joint]["external_contact"],
                    places=8,
                )


if __name__ == "__main__":
    unittest.main()
