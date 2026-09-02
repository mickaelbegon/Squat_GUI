import builtins
import math
import unittest
from unittest.mock import patch

from squat_gui.anthropometry import Anthropometry
from squat_gui.bar_path_optimization import (
    ANGLE_PERTURBATION_RAD,
    DEPTH_TOLERANCE_M,
    optimize_deep_squat_bar_path,
)
from squat_gui.dynamics import simulate, torque_presets
from squat_gui.kinematics import (
    PhaseDurations,
    functional_support_limits,
    joint_values_from_segment_values,
    motion_state,
    pose_from_angles,
)


class BarPathOptimizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.anthro = Anthropometry()
        self.durations = PhaseDurations(4.0, 2.0, 4.0)
        self.max_torques = dict(
            torque_presets(70.0, 1.70)["Anderson actif x2"].torques
        )

    def optimize(self, requested_deg=(22.0, -58.0, 50.0)):
        requested = tuple(math.radians(value) for value in requested_deg)
        return optimize_deep_squat_bar_path(
            self.anthro,
            requested,
            self.durations,
            41,
            self.max_torques,
            True,
        )

    def test_slsqp_reduces_horizontal_motion_with_all_constraints(self) -> None:
        result = self.optimize()

        self.assertTrue(result.applied, result.message)
        self.assertLess(
            result.after.horizontal_velocity_energy_m2_s,
            result.before.horizontal_velocity_energy_m2_s,
        )
        self.assertLess(
            result.after.horizontal_excursion_m,
            result.before.horizontal_excursion_m,
        )
        requested_joints = joint_values_from_segment_values(
            result.requested_final_q
        )
        optimized_joints = joint_values_from_segment_values(result.final_q)
        for joint in ("cheville", "genou", "hanche"):
            self.assertLessEqual(
                abs(optimized_joints[joint] - requested_joints[joint]),
                ANGLE_PERTURBATION_RAD + 1e-8,
            )

        joint_angles = optimized_joints
        self.assertGreaterEqual(joint_angles["cheville"], math.radians(-30.0))
        self.assertLessEqual(joint_angles["cheville"], math.radians(40.0))
        self.assertGreaterEqual(joint_angles["genou"], math.radians(-140.0))
        self.assertLessEqual(joint_angles["genou"], 0.0)
        self.assertGreaterEqual(joint_angles["hanche"], math.radians(-15.0))
        self.assertLessEqual(joint_angles["hanche"], math.radians(120.0))

        requested_depth = pose_from_angles(
            self.anthro, result.requested_final_q
        ).hip[1]
        optimized_depth = pose_from_angles(self.anthro, result.final_q).hip[1]
        self.assertLessEqual(
            abs(optimized_depth - requested_depth), DEPTH_TOLERANCE_M + 1e-7
        )
        for state, dynamics in zip(result.states, result.dynamics):
            posterior, anterior = functional_support_limits(state.pose)
            self.assertGreaterEqual(dynamics.cop_x, posterior - 1e-7)
            self.assertLessEqual(dynamics.cop_x, anterior + 1e-7)
            self.assertGreater(dynamics.ground_reaction[1], 0.0)

    def test_optimized_motion_still_uses_the_quintic_trajectory(self) -> None:
        result = self.optimize()
        self.assertTrue(result.applied, result.message)

        for state in result.states:
            expected = motion_state(
                self.anthro,
                result.final_q,
                self.durations,
                state.time,
            )
            for actual, reference in zip(state.q, expected.q):
                self.assertAlmostEqual(actual, reference, places=11)
            for actual, reference in zip(state.qdot, expected.qdot):
                self.assertAlmostEqual(actual, reference, places=11)
            for actual, reference in zip(state.qddot, expected.qddot):
                self.assertAlmostEqual(actual, reference, places=11)

    def test_infeasible_case_returns_the_exact_baseline_objects(self) -> None:
        requested = tuple(math.radians(value) for value in (22.0, -58.0, 20.0))
        baseline = simulate(
            self.anthro,
            requested,
            self.durations,
            41,
            self.max_torques,
            True,
        )

        solver_calls = 0

        def solver_must_not_run(*_args, **_kwargs):
            nonlocal solver_calls
            solver_calls += 1
            raise AssertionError("SLSQP ne doit pas recevoir un cas infaisable")

        result = optimize_deep_squat_bar_path(
            self.anthro,
            requested,
            self.durations,
            41,
            self.max_torques,
            True,
            baseline=baseline,
            minimize_function=solver_must_not_run,
        )

        self.assertFalse(result.applied)
        self.assertIs(result.states, baseline[0])
        self.assertIs(result.dynamics, baseline[1])
        self.assertEqual(result.final_q, requested)
        self.assertEqual(result.before, result.after)
        self.assertIn("aucune posture faisable", result.message)
        self.assertEqual(solver_calls, 0)

    def test_missing_scipy_returns_baseline_and_clear_diagnostic(self) -> None:
        requested = tuple(math.radians(value) for value in (22.0, -58.0, 50.0))
        baseline = simulate(
            self.anthro,
            requested,
            self.durations,
            21,
            self.max_torques,
            True,
        )
        original_import = builtins.__import__

        def without_scipy(name, *args, **kwargs):
            if name == "scipy.optimize":
                raise ModuleNotFoundError("test: scipy absent")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=without_scipy):
            result = optimize_deep_squat_bar_path(
                self.anthro,
                requested,
                self.durations,
                21,
                self.max_torques,
                True,
                baseline=baseline,
            )

        self.assertFalse(result.applied)
        self.assertFalse(result.scipy_available)
        self.assertIs(result.states, baseline[0])
        self.assertIs(result.dynamics, baseline[1])
        self.assertIn("SciPy", result.message)


if __name__ == "__main__":
    unittest.main()
