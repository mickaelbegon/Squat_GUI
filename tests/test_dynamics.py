import math
import unittest

from squat_gui.anthropometry import Anthropometry
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
from squat_gui.kinematics import MotionState, pose_from_angles


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

    def test_torque_components_sum_to_inverse_dynamics_torque(self) -> None:
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
                self.assertAlmostEqual(
                    result.torques[joint],
                    components["Mqddot"] + components["NLeffects"],
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
