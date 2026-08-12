import unittest
from math import radians

from squat_gui.anthropometry import Anthropometry
from squat_gui.dynamics import simulate
from squat_gui.kinematics import (
    PhaseDurations,
    com_accelerations,
    com_velocities,
    pose_from_angles,
)


SEGMENTS = ("foot", "shank", "thigh", "trunk", "bar")
MAX_TORQUES = {"cheville": 222.0, "genou": 380.0, "hanche": 376.0}


class ComDerivativeTests(unittest.TestCase):
    def test_segment_com_velocities_match_central_position_difference(self) -> None:
        anthro = Anthropometry(
            bar_mass=35.0,
            subject_profile="femme enceinte",
            bar_position="front",
            wedge_angle_deg=20.0,
        )
        q = (radians(18.0), radians(-52.0), radians(16.0))
        qdot = (0.35, -0.42, 0.27)
        step = 1e-6

        analytical = com_velocities(anthro, q, qdot)
        forward = pose_from_angles(anthro, tuple(q[i] + step * qdot[i] for i in range(3)))
        backward = pose_from_angles(anthro, tuple(q[i] - step * qdot[i] for i in range(3)))

        for segment in SEGMENTS:
            with self.subTest(segment=segment):
                for axis in (0, 1):
                    numerical = (
                        forward.segment_coms[segment][axis] - backward.segment_coms[segment][axis]
                    ) / (2.0 * step)
                    self.assertAlmostEqual(analytical[segment][axis], numerical, places=8)

    def test_segment_com_accelerations_match_velocity_difference(self) -> None:
        anthro = Anthropometry(bar_mass=28.0, bar_position="over-head", wedge_angle_deg=20.0)
        q = (radians(21.0), radians(-60.0), radians(15.0))
        qdot = (0.31, -0.38, 0.22)
        qddot = (-0.17, 0.29, -0.11)
        step = 1e-5
        q_forward = tuple(q[i] + step * qdot[i] + 0.5 * step**2 * qddot[i] for i in range(3))
        q_backward = tuple(q[i] - step * qdot[i] + 0.5 * step**2 * qddot[i] for i in range(3))
        qdot_forward = tuple(qdot[i] + step * qddot[i] for i in range(3))
        qdot_backward = tuple(qdot[i] - step * qddot[i] for i in range(3))

        analytical = com_accelerations(anthro, q, qdot, qddot)
        velocity_forward = com_velocities(anthro, q_forward, qdot_forward)
        velocity_backward = com_velocities(anthro, q_backward, qdot_backward)

        for segment in SEGMENTS:
            with self.subTest(segment=segment):
                for axis in (0, 1):
                    numerical = (
                        velocity_forward[segment][axis] - velocity_backward[segment][axis]
                    ) / (2.0 * step)
                    self.assertAlmostEqual(analytical[segment][axis], numerical, places=7)

    def test_simulated_global_com_derivatives_match_neighboring_frames(self) -> None:
        anthro = Anthropometry(bar_mass=30.0, bar_position="front", wedge_angle_deg=20.0)
        durations = PhaseDurations(3.0, 1.0, 3.0)
        states, results = simulate(
            anthro,
            (radians(22.0), radians(-58.0), radians(20.0)),
            durations,
            701,
            MAX_TORQUES,
            True,
        )
        index = 150
        delta_time = states[index + 1].time - states[index].time

        for axis in (0, 1):
            velocity_difference = (
                results[index + 1].com[axis] - results[index - 1].com[axis]
            ) / (2.0 * delta_time)
            acceleration_difference = (
                results[index + 1].com_velocity[axis] - results[index - 1].com_velocity[axis]
            ) / (2.0 * delta_time)
            self.assertAlmostEqual(results[index].com_velocity[axis], velocity_difference, delta=1e-5)
            self.assertAlmostEqual(results[index].com_acceleration[axis], acceleration_difference, delta=2e-4)

        self.assertGreater(abs(results[index].com_velocity[0]) + abs(results[index].com_velocity[1]), 1e-6)
        isometric_index = 350
        self.assertEqual(states[isometric_index].phase, "isometrique")
        self.assertEqual(results[isometric_index].com_velocity, (0.0, 0.0))
        self.assertEqual(results[isometric_index].com_acceleration, (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
