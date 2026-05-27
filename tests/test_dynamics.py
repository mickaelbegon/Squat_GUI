import math
import unittest

from squat_gui.anthropometry import Anthropometry
from squat_gui.backend import biomod_cache_key, biomod_text
from squat_gui.dynamics import (
    _biorbd_native_cop_x,
    athlete_reference_max_torques,
    anderson_angle_factor,
    anderson_reference_max_torques,
    angle_adapted_max,
    inverse_dynamics,
    simulate,
    torque_presets,
)
from squat_gui.kinematics import MotionState, PhaseDurations, motion_state, pose_from_angles


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

    def test_bar_hold_and_pregnancy_shift_combined_com_forward(self) -> None:
        q = (0.0, 0.0, 0.0)
        back = pose_from_angles(Anthropometry(bar_mass=20.0, bar_position="back"), q)
        front = pose_from_angles(Anthropometry(bar_mass=20.0, bar_position="front"), q)
        overhead = pose_from_angles(Anthropometry(bar_mass=20.0, bar_position="over-head"), q)
        pregnant = pose_from_angles(
            Anthropometry(bar_mass=20.0, subject_profile="femme enceinte", bar_position="back"),
            q,
        )

        self.assertGreater(front.bar[0], back.bar[0])
        self.assertGreater(overhead.bar[1], front.bar[1])
        self.assertGreater(front.com[0], back.com[0])
        self.assertGreater(pregnant.com[0], back.com[0])
        self.assertGreater(
            Anthropometry(subject_profile="femme enceinte").trunk.inertia,
            Anthropometry().trunk.inertia,
        )

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

    def test_motion_supports_an_isometric_squat_phase(self) -> None:
        anthro = Anthropometry()
        final_q = (math.radians(20.0), math.radians(-55.0), math.radians(-15.0))
        durations = PhaseDurations(2.0, 3.0, 4.0)
        states, _ = simulate(
            anthro,
            final_q,
            durations,
            10,
            {"cheville": 180.0, "genou": 220.0, "hanche": 260.0},
            False,
        )

        self.assertEqual(states[2].phase, "excentrique")
        self.assertEqual(states[3].phase, "isometrique")
        self.assertEqual(states[5].phase, "isometrique")
        self.assertEqual(states[6].phase, "concentrique")
        squat = motion_state(anthro, final_q, durations, 3.0)
        self.assertEqual(squat.q, final_q)
        self.assertEqual(squat.qdot, (0.0, 0.0, 0.0))

    def test_wedge_is_in_geometry_and_biomod_cache_identity(self) -> None:
        flat = Anthropometry()
        wedge = Anthropometry(wedge_angle_deg=20.0)
        flat_pose = pose_from_angles(flat, (0.0, 0.0, 0.0))
        wedge_pose = pose_from_angles(wedge, (0.0, 0.0, 0.0))

        self.assertGreater(wedge_pose.knee[0], flat_pose.knee[0])
        self.assertNotEqual(biomod_cache_key(flat), biomod_cache_key(wedge))
        self.assertIn("0.939693", biomod_text(wedge))

    def test_eccentric_phase_increases_available_torque_by_135_percent(self) -> None:
        anthro = Anthropometry()
        q = (math.radians(20.0), math.radians(-55.0), math.radians(-15.0))
        qdot = (0.1, -0.2, -0.05)
        qddot = (0.0, 0.0, 0.0)
        max_torques = {"cheville": 180.0, "genou": 220.0, "hanche": 260.0}
        eccentric = MotionState(0.2, q, qdot, qddot, pose_from_angles(anthro, q), "excentrique")
        concentric = MotionState(0.8, q, qdot, qddot, pose_from_angles(anthro, q), "concentrique")
        eccentric_result = inverse_dynamics(anthro, eccentric, max_torques, False)
        concentric_result = inverse_dynamics(anthro, concentric, max_torques, False)

        for joint in max_torques:
            self.assertAlmostEqual(
                eccentric_result.effort_ratios[joint],
                concentric_result.effort_ratios[joint] / 1.35,
            )

    def test_torque_components_keep_total_and_contact_terms(self) -> None:
        anthro = Anthropometry(bar_mass=20.0)
        _, results = simulate(
            anthro,
            (math.radians(22.0), math.radians(-58.0), math.radians(20.0)),
            8.0,
            21,
            {"cheville": 222.0, "genou": 380.0, "hanche": 376.0},
            True,
        )

        for result in results:
            for joint in ("cheville", "genou", "hanche"):
                components = result.torque_components[joint]
                self.assertAlmostEqual(result.torques[joint], components["total"])
                self.assertAlmostEqual(
                    components["inertiels_non_lineaires"],
                    components["total"] - components["contact"],
                )

    def test_angle_adaptation_uses_anderson_coefficients(self) -> None:
        reference = anderson_reference_max_torques(70.0, 1.70)

        self.assertAlmostEqual(reference["cheville"], 221.7283565)
        self.assertAlmostEqual(anderson_reference_max_torques(70.0, 1.70, side_count=1)["cheville"], 110.86417825)
        self.assertAlmostEqual(anderson_angle_factor("genou", 1.133), 1.0)
        self.assertLess(anderson_angle_factor("genou", 0.0), 1.0)
        self.assertAlmostEqual(angle_adapted_max(200.0, 1.133, True, "genou"), 200.0)

    def test_athlete_torque_preset_scales_combined_sides_to_body_mass(self) -> None:
        athlete = athlete_reference_max_torques(70.0)
        presets = torque_presets(70.0, 1.70)

        self.assertAlmostEqual(athlete["cheville"], 229.12140575)
        self.assertAlmostEqual(athlete["genou"], 497.0)
        self.assertAlmostEqual(athlete["hanche"], 329.7)
        self.assertEqual(presets["Sportifs"].torques, athlete)

    def test_native_biorbd_zmp_uses_ground_plane_normal(self) -> None:
        class ArrayResult:
            def to_array(self):
                return [0.123, 0.0, 0.0]

        class Model:
            def __init__(self):
                self.normal = None
                self.point = None

            def CalcZeroMomentPoint(self, _q, _qdot, _qddot, normal, point):
                self.normal = normal
                self.point = point
                return ArrayResult()

        model = Model()

        self.assertAlmostEqual(_biorbd_native_cop_x(model, [0], [0], [0]), 0.123)
        self.assertEqual(list(model.normal), [0.0, 1.0, 0.0])
        self.assertEqual(list(model.point), [0.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
