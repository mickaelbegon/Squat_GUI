import math
import unittest

from squat_gui.anthropometry import Anthropometry
from squat_gui.bar_calibration import annotated_bar_offset_fractions
from squat_gui.backend import biomod_cache_key, biomod_text
from squat_gui.dynamics import (
    GRAVITY,
    _biorbd_inverse_dynamics_decomposition,
    _biorbd_native_cop_x,
    athlete_reference_max_torques,
    anderson_angle_factor,
    anderson_angle_domain,
    anderson_reference_max_torques,
    anderson_velocity_factor,
    angle_adapted_max,
    force_balance,
    inverse_dynamics,
    simulate,
    torque_presets,
)
from squat_gui.kinematics import (
    MotionState,
    PhaseDurations,
    motion_state,
    pose_from_angles,
    zmp_in_support,
    zmp_support_limits,
)


class DynamicsTests(unittest.TestCase):
    def test_biorbd_decomposition_uses_mass_matrix_and_reconstructs_total(self) -> None:
        import numpy as np

        class ArrayResult:
            def __init__(self, value):
                self.value = np.asarray(value, dtype=float)

            def to_array(self):
                return self.value

        class FakeModel:
            def __init__(self):
                self.mass_matrix_calls = 0

            def massMatrix(self, _q):
                self.mass_matrix_calls += 1
                return ArrayResult(np.diag([2.0, 3.0, 4.0]))

            def InverseDynamics(self, _q, qdot, qddot):
                gravity = np.array([10.0, 20.0, 30.0])
                velocity = np.asarray(qdot, dtype=float) ** 2
                mass_acceleration = np.diag([2.0, 3.0, 4.0]) @ np.asarray(
                    qddot, dtype=float
                )
                return ArrayResult(mass_acceleration + velocity + gravity)

        anthro = Anthropometry()
        q = (0.2, -0.5, -0.2)
        state = MotionState(
            0.2,
            q,
            (0.4, -0.3, 0.2),
            (0.7, -0.5, 0.3),
            pose_from_angles(anthro, q),
            "excentrique",
        )
        model = FakeModel()

        total, mass_acceleration, velocity, gravity = (
            _biorbd_inverse_dynamics_decomposition(
                model,
                state,
            )
        )

        self.assertEqual(model.mass_matrix_calls, 1)
        for joint in ("cheville", "genou", "hanche"):
            self.assertAlmostEqual(
                total[joint],
                mass_acceleration[joint] + velocity[joint] + gravity[joint],
                places=12,
            )

    def test_mass_includes_bar_load(self) -> None:
        anthro = Anthropometry(bar_mass=40.0)
        self.assertAlmostEqual(anthro.total_mass, 110.0)

    def test_winter_dempster_com_respects_model_origins_and_bilateral_mass(
        self,
    ) -> None:
        male = Anthropometry()

        self.assertAlmostEqual(male.foot.mass / male.body_mass, 0.029)
        self.assertAlmostEqual(male.shank.mass / male.body_mass, 0.093)
        self.assertAlmostEqual(male.thigh.mass / male.body_mass, 0.200)
        self.assertAlmostEqual(male.foot.com_fraction, 0.50)
        self.assertAlmostEqual(male.shank.com_fraction, 1.0 - 0.433)
        self.assertAlmostEqual(male.thigh.com_fraction, 1.0 - 0.433)
        self.assertGreater(male.shank.com_fraction, 0.5)

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

    def test_ground_reaction_weight_and_com_acceleration_close_force_balance(
        self,
    ) -> None:
        anthro = Anthropometry(
            bar_mass=40.0,
            subject_profile="femme enceinte",
            bar_position="front",
            wedge_angle_deg=20.0,
        )
        states, results = simulate(
            anthro,
            (math.radians(22.0), math.radians(-58.0), math.radians(20.0)),
            PhaseDurations(3.0, 1.0, 3.0),
            31,
            {"cheville": 222.0, "genou": 380.0, "hanche": 376.0},
            True,
        )

        self.assertEqual(len(states), len(results))
        for result in results:
            balance = force_balance(anthro, result)
            self.assertAlmostEqual(
                balance.weight_magnitude_N, anthro.total_mass * GRAVITY
            )
            self.assertAlmostEqual(
                result.ground_reaction[0],
                anthro.total_mass * result.com_acceleration[0],
                places=11,
            )
            self.assertAlmostEqual(
                result.ground_reaction[1] - balance.weight_magnitude_N,
                anthro.total_mass * result.com_acceleration[1],
                places=11,
            )
            self.assertAlmostEqual(balance.residual_N[0], 0.0, places=11)
            self.assertAlmostEqual(balance.residual_N[1], 0.0, places=11)

    def test_analytical_support_point_reports_cop_provenance(self) -> None:
        anthro = Anthropometry(bar_mass=20.0)
        state = motion_state(
            anthro,
            (math.radians(22.0), math.radians(-58.0), math.radians(20.0)),
            PhaseDurations(3.0, 1.0, 3.0),
            1.5,
        )

        result = inverse_dynamics(
            anthro,
            state,
            {"cheville": 222.0, "genou": 380.0, "hanche": 376.0},
            True,
        )

        self.assertEqual(result.support_point_label, "CoP")
        self.assertEqual(result.support_point_source, "bilan dynamique analytique")

    def test_bar_hold_and_pregnancy_shift_combined_com_forward(self) -> None:
        q = (0.0, 0.0, 0.0)
        back = pose_from_angles(Anthropometry(bar_mass=20.0, bar_position="back"), q)
        front = pose_from_angles(Anthropometry(bar_mass=20.0, bar_position="front"), q)
        overhead = pose_from_angles(
            Anthropometry(bar_mass=20.0, bar_position="over-head"), q
        )
        pregnant = pose_from_angles(
            Anthropometry(
                bar_mass=20.0, subject_profile="femme enceinte", bar_position="back"
            ),
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

    def test_manual_refined_bar_points_define_model_bar_location(self) -> None:
        for subject in ("homme", "femme enceinte"):
            for hold in ("front", "back", "over-head"):
                with self.subTest(subject=subject, hold=hold):
                    anthro = Anthropometry(
                        bar_mass=20.0, subject_profile=subject, bar_position=hold
                    )
                    anterior, longitudinal = annotated_bar_offset_fractions(
                        subject, hold
                    )
                    self.assertAlmostEqual(
                        anthro.bar_anterior_offset, anterior * anthro.trunk.length
                    )
                    self.assertAlmostEqual(
                        anthro.bar_longitudinal_offset,
                        longitudinal * anthro.trunk.length,
                    )
                    text = biomod_text(anthro)
                    self.assertIn(f"{anthro.bar_anterior_offset:.6f}", text)
                    self.assertIn(
                        f"{anthro.trunk.length + anthro.bar_longitudinal_offset:.6f}",
                        text,
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
        wedge_state = motion_state(
            wedge, (0.0, 0.0, 0.0), PhaseDurations(2.0, 2.0, 2.0), 0.0
        )
        wedge_pose = wedge_state.pose

        self.assertGreater(wedge_pose.heel[1], wedge_pose.toe[1])
        self.assertAlmostEqual(wedge_state.q[0], math.radians(-20.0))
        self.assertAlmostEqual(
            wedge_pose.knee[0] - wedge_pose.ankle[0],
            flat_pose.knee[0] - flat_pose.ankle[0],
        )
        self.assertNotEqual(biomod_cache_key(flat), biomod_cache_key(wedge))
        self.assertIn("0.939693", biomod_text(wedge))

    def test_functional_zmp_support_excludes_posterior_heel_margin(self) -> None:
        pose = pose_from_angles(Anthropometry(), (0.0, 0.0, 0.0))
        posterior, anterior = zmp_support_limits(pose)

        self.assertAlmostEqual(
            posterior, pose.heel[0] + 0.15 * (pose.toe[0] - pose.heel[0])
        )
        self.assertFalse(
            zmp_in_support(pose, pose.heel[0] + 0.10 * (pose.toe[0] - pose.heel[0]))
        )
        self.assertTrue(zmp_in_support(pose, posterior))
        self.assertTrue(zmp_in_support(pose, anterior))

    def test_wedge_moves_posterior_zmp_limit_to_ankle_projection(self) -> None:
        anthro = Anthropometry(wedge_angle_deg=20.0)
        pose = pose_from_angles(anthro, (0.0, 0.0, 0.0))
        posterior, _ = zmp_support_limits(pose)

        self.assertAlmostEqual(posterior, pose.ankle[0])
        self.assertFalse(zmp_in_support(pose, posterior - 0.001))
        self.assertTrue(zmp_in_support(pose, posterior))

    def test_capacity_depends_on_velocity_not_phase_label(self) -> None:
        anthro = Anthropometry()
        q = (math.radians(20.0), math.radians(-55.0), math.radians(-15.0))
        qdot = (0.1, -0.2, -0.05)
        qddot = (0.0, 0.0, 0.0)
        max_torques = {"cheville": 180.0, "genou": 220.0, "hanche": 260.0}
        eccentric = MotionState(
            0.2, q, qdot, qddot, pose_from_angles(anthro, q), "excentrique"
        )
        concentric = MotionState(
            0.8, q, qdot, qddot, pose_from_angles(anthro, q), "concentrique"
        )
        eccentric_result = inverse_dynamics(anthro, eccentric, max_torques, False)
        concentric_result = inverse_dynamics(anthro, concentric, max_torques, False)

        for joint in max_torques:
            self.assertAlmostEqual(
                eccentric_result.effort_ratios[joint],
                concentric_result.effort_ratios[joint],
            )

    def test_anderson_velocity_surface_hits_published_reference_points(self) -> None:
        params = {
            "cheville": (0.987, 3.558),
            "genou": (1.517, 3.952),
            "hanche": (1.578, 3.190),
        }
        for joint, (c4, c5) in params.items():
            self.assertAlmostEqual(anderson_velocity_factor(joint, 0.0), 1.0)
            self.assertAlmostEqual(anderson_velocity_factor(joint, c4), 0.75)
            self.assertAlmostEqual(anderson_velocity_factor(joint, c5), 0.50)
            self.assertGreater(
                anderson_velocity_factor(joint, -c4),
                anderson_velocity_factor(joint, c4),
            )

    def test_capacity_regime_is_coherent_with_reported_joint_power(self) -> None:
        _, results = simulate(
            Anthropometry(),
            (math.radians(22.0), math.radians(-58.0), math.radians(20.0)),
            PhaseDurations(4.0, 2.0, 4.0),
            201,
            {"cheville": 222.0, "genou": 380.0, "hanche": 376.0},
            True,
        )
        for result in results:
            for joint, power in result.powers.items():
                capacity = result.torque_capacities[joint]
                if abs(capacity.angular_velocity_rad_s) < 1e-12:
                    self.assertEqual(capacity.regime, "isometrique")
                elif power > 0.0:
                    self.assertEqual(capacity.regime, "concentrique")
                    self.assertGreater(capacity.angular_velocity_rad_s, 0.0)
                else:
                    self.assertEqual(capacity.regime, "excentrique")
                    self.assertLess(capacity.angular_velocity_rad_s, 0.0)

    def test_capacity_preserves_the_condition_base_torque_and_source(self) -> None:
        max_torques = {"cheville": 201.0, "genou": 302.0, "hanche": 403.0}
        anthro = Anthropometry()
        state = motion_state(
            anthro,
            (math.radians(20.0), math.radians(-55.0), math.radians(-15.0)),
            PhaseDurations(2.0, 1.0, 2.0),
            1.0,
        )
        result = inverse_dynamics(
            anthro, state, max_torques, True, adapt_max_by_velocity=True
        )
        for joint, expected in max_torques.items():
            capacity = result.torque_capacities[joint]
            self.assertEqual(capacity.base_torque_Nm, expected)
            self.assertIn("torque_preset", capacity.source)
            self.assertIn("Anderson", capacity.model)

    def test_angle_factor_has_no_arbitrary_floor_outside_active_domain(self) -> None:
        lower, upper = anderson_angle_domain("genou")
        self.assertAlmostEqual(anderson_angle_factor("genou", lower), 0.0, places=12)
        self.assertAlmostEqual(anderson_angle_factor("genou", upper), 0.0, places=12)
        self.assertEqual(anderson_angle_factor("genou", upper + 0.1), 0.0)

    def test_torque_components_reconstruct_total_from_physical_terms(self) -> None:
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
            self.assertEqual(result.contact_source, "moment géométrique de la GRF")
            for joint in ("cheville", "genou", "hanche"):
                components = result.torque_components[joint]
                self.assertAlmostEqual(result.torques[joint], components["total"])
                self.assertAlmostEqual(
                    components["total"],
                    components["mass_acceleration"]
                    + components["velocity"]
                    + components["gravity"],
                    places=11,
                )
                self.assertAlmostEqual(
                    components["reconstruction_residual"],
                    0.0,
                    places=11,
                )
                self.assertAlmostEqual(
                    components["total_with_external_contact"],
                    components["total"] + components["external_contact"],
                    places=11,
                )

    def test_velocity_and_mass_acceleration_terms_are_isolated_by_zeroing(self) -> None:
        anthro = Anthropometry(bar_mass=20.0)
        q = (math.radians(20.0), math.radians(-55.0), math.radians(-15.0))
        max_torques = {"cheville": 180.0, "genou": 220.0, "hanche": 260.0}
        no_velocity = MotionState(
            0.2,
            q,
            (0.0, 0.0, 0.0),
            (0.4, -0.3, 0.2),
            pose_from_angles(anthro, q),
            "excentrique",
        )
        no_acceleration = MotionState(
            0.2,
            q,
            (0.4, -0.3, 0.2),
            (0.0, 0.0, 0.0),
            pose_from_angles(anthro, q),
            "excentrique",
        )

        no_velocity_result = inverse_dynamics(anthro, no_velocity, max_torques, False)
        no_acceleration_result = inverse_dynamics(
            anthro, no_acceleration, max_torques, False
        )
        for joint in ("cheville", "genou", "hanche"):
            self.assertAlmostEqual(
                no_velocity_result.torque_components[joint]["velocity"],
                0.0,
                places=12,
            )
            self.assertAlmostEqual(
                no_acceleration_result.torque_components[joint]["mass_acceleration"],
                0.0,
                places=12,
            )
            self.assertAlmostEqual(
                no_velocity_result.torque_components[joint]["gravity"],
                no_acceleration_result.torque_components[joint]["gravity"],
                places=12,
            )

    def test_angle_adaptation_uses_anderson_coefficients(self) -> None:
        reference = anderson_reference_max_torques(70.0, 1.70)

        self.assertAlmostEqual(reference["cheville"], 221.7283565)
        self.assertAlmostEqual(
            anderson_reference_max_torques(70.0, 1.70, side_count=1)["cheville"],
            110.86417825,
        )
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
