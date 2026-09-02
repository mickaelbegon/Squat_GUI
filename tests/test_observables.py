import unittest
from math import degrees, radians

from squat_gui.anthropometry import Anthropometry
from squat_gui.kinematics import (
    PhaseDurations,
    clinical_joint_values_from_segment_values,
    joint_angles_from_pose,
    joint_values_from_segment_values,
    motion_state,
    pose_from_angles,
    segment_orientations,
    segment_values_from_joint_values,
    segment_values_from_clinical_joint_values,
)
from squat_gui.observables import (
    com_contributions,
    frame_info,
    joint_coordinates,
    neighbor_samples,
    reconstruct_global_com,
    segment_anthropometry,
    support_margins,
)


class ObservableTests(unittest.TestCase):
    def test_frame_info_reports_time_step_phase_and_normalized_time(self) -> None:
        anthro = Anthropometry()
        durations = PhaseDurations(2.0, 1.0, 3.0)
        states = [motion_state(anthro, (0.2, -0.8, 0.3), durations, float(time)) for time in range(7)]

        info = frame_info(states, 3)

        self.assertEqual(info.frame, 3)
        self.assertEqual(info.frame_count, 7)
        self.assertAlmostEqual(info.time_s, 3.0)
        self.assertAlmostEqual(info.delta_time_s, 1.0)
        self.assertAlmostEqual(info.normalized_time_percent, 50.0)
        self.assertEqual(info.phase, "isometrique")

    def test_frame_info_clamps_index_and_uses_previous_step_at_end(self) -> None:
        anthro = Anthropometry()
        durations = PhaseDurations(1.0, 0.0, 1.0)
        states = [motion_state(anthro, (0.1, -0.4, 0.2), durations, time) for time in (0.0, 0.5, 2.0)]

        info = frame_info(states, 99)

        self.assertEqual(info.frame, 2)
        self.assertAlmostEqual(info.delta_time_s, 1.5)
        self.assertAlmostEqual(info.normalized_time_percent, 100.0)

    def test_joint_coordinates_are_global_metres_and_preserve_segment_lengths(self) -> None:
        anthro = Anthropometry(wedge_angle_deg=20.0)
        pose = pose_from_angles(anthro, (radians(22.0), radians(-58.0), radians(20.0)))

        points = joint_coordinates(pose)

        self.assertEqual(set(points), {"ankle", "knee", "hip", "shoulder", "bar"})
        self.assertEqual(points["bar"], pose.bar)
        shank_length = ((points["knee"][0] - points["ankle"][0]) ** 2 + (points["knee"][1] - points["ankle"][1]) ** 2) ** 0.5
        thigh_length = ((points["hip"][0] - points["knee"][0]) ** 2 + (points["hip"][1] - points["knee"][1]) ** 2) ** 0.5
        self.assertAlmostEqual(shank_length, anthro.shank.length)
        self.assertAlmostEqual(thigh_length, anthro.thigh.length)

    def test_absolute_orientations_use_global_x_axis_and_ccw_positive(self) -> None:
        anthro = Anthropometry(wedge_angle_deg=20.0)
        q = (radians(22.0), radians(-58.0), radians(20.0))

        orientations = segment_orientations(pose_from_angles(anthro, q))

        self.assertAlmostEqual(degrees(orientations["foot"]), -20.0)
        self.assertAlmostEqual(degrees(orientations["shank"]), 90.0 - 42.0)
        self.assertAlmostEqual(degrees(orientations["thigh"]), 90.0 - (-38.0))
        self.assertAlmostEqual(degrees(orientations["trunk"]), 90.0 - 40.0)

    def test_pose_joint_angles_match_internal_joint_convention_with_wedge(self) -> None:
        anthro = Anthropometry(wedge_angle_deg=20.0)
        q = (radians(22.0), radians(-58.0), radians(20.0))

        from_pose = joint_angles_from_pose(pose_from_angles(anthro, q))
        from_q = joint_values_from_segment_values(q)

        for joint in ("cheville", "genou", "hanche"):
            self.assertAlmostEqual(from_pose[joint], from_q[joint])

    def test_segment_joint_conversion_round_trip_preserves_units(self) -> None:
        joint_values = (22.0, -80.0, 78.0)
        segments = segment_values_from_joint_values(*joint_values)
        reconstructed = joint_values_from_segment_values(segments)

        self.assertEqual(segments, (22.0, -58.0, 20.0))
        self.assertEqual(tuple(reconstructed.values()), joint_values)

    def test_clinical_joint_conversion_displays_knee_flexion_as_positive(self) -> None:
        segments = (22.0, -58.0, 20.0)

        clinical = clinical_joint_values_from_segment_values(segments)
        reconstructed = segment_values_from_clinical_joint_values(
            clinical["cheville"], clinical["genou"], clinical["hanche"]
        )

        self.assertEqual(
            clinical, {"cheville": 22.0, "genou": 80.0, "hanche": 78.0}
        )
        self.assertEqual(reconstructed, segments)

    def test_anthropometry_table_reports_effective_scaled_lengths_and_mass(self) -> None:
        anthro = Anthropometry(
            shank_scale=1.05,
            thigh_scale=0.95,
            trunk_scale=1.025,
            bar_mass=35.0,
            subject_profile="femme enceinte",
            bar_position="front",
        )

        table = segment_anthropometry(anthro)

        self.assertEqual(set(table), {"foot", "shank", "thigh", "trunk", "bar"})
        self.assertAlmostEqual(table["shank"].length_m, 0.246 * anthro.height * 1.05)
        self.assertAlmostEqual(table["thigh"].length_m, 0.245 * anthro.height * 0.95)
        self.assertAlmostEqual(table["foot"].com_transverse_offset_m, 0.025)
        self.assertAlmostEqual(table["trunk"].com_transverse_offset_m, anthro.trunk.com_anterior_offset)
        self.assertAlmostEqual(table["bar"].mass_kg, 35.0)
        self.assertIsNone(table["bar"].com_fraction)
        self.assertAlmostEqual(sum(row.mass_kg for row in table.values()), anthro.total_mass)

    def test_segment_contributions_reconstruct_global_com_with_bar_and_wedge(self) -> None:
        anthro = Anthropometry(
            bar_mass=42.0,
            subject_profile="femme enceinte",
            bar_position="over-head",
            wedge_angle_deg=20.0,
        )
        pose = pose_from_angles(anthro, (radians(24.0), radians(-62.0), radians(18.0)))

        contributions = com_contributions(anthro, pose)
        reconstructed = reconstruct_global_com(contributions)

        self.assertAlmostEqual(reconstructed[0], pose.com[0], places=12)
        self.assertAlmostEqual(reconstructed[1], pose.com[1], places=12)
        for key, contribution in contributions.items():
            with self.subTest(segment=key):
                self.assertAlmostEqual(
                    contribution.weighted_position_kg_m[0],
                    contribution.mass_kg * contribution.position_m[0],
                )
                self.assertAlmostEqual(
                    contribution.weighted_position_kg_m[1],
                    contribution.mass_kg * contribution.position_m[1],
                )

    def test_global_com_reconstruction_rejects_empty_table(self) -> None:
        with self.assertRaises(ValueError):
            reconstruct_global_com({})

    def test_neighbor_samples_report_three_distinct_frames_and_time_steps(self) -> None:
        anthro = Anthropometry()
        durations = PhaseDurations(2.0, 1.0, 2.0)
        states = [
            motion_state(anthro, (0.2, -0.8, 0.3), durations, time)
            for time in (0.0, 0.5, 1.5, 3.0, 5.0)
        ]

        previous, current, following = neighbor_samples(states, 2)

        self.assertIsNotNone(previous)
        self.assertIsNotNone(current)
        self.assertIsNotNone(following)
        self.assertEqual((previous.frame, current.frame, following.frame), (1, 2, 3))
        self.assertAlmostEqual(previous.delta_from_center_s, -1.0)
        self.assertAlmostEqual(current.delta_from_center_s, 0.0)
        self.assertAlmostEqual(following.delta_from_center_s, 1.5)

    def test_neighbor_samples_do_not_duplicate_missing_boundary_frames(self) -> None:
        anthro = Anthropometry()
        states = [
            motion_state(anthro, (0.2, -0.8, 0.3), PhaseDurations(1.0, 0.0, 1.0), time)
            for time in (0.0, 1.0, 2.0)
        ]

        first = neighbor_samples(states, 0)
        last = neighbor_samples(states, 99)

        self.assertIsNone(first[0])
        self.assertEqual((first[1].frame, first[2].frame), (0, 1))
        self.assertEqual((last[0].frame, last[1].frame), (1, 2))
        self.assertIsNone(last[2])

    def test_geometric_and_functional_support_margins_are_distinct_and_signed(self) -> None:
        pose = pose_from_angles(Anthropometry(), (0.0, 0.0, 0.0))
        geometric_length = pose.toe[0] - pose.heel[0]
        point_x = pose.heel[0] + 0.10 * geometric_length

        margins = support_margins(pose, point_x)

        self.assertTrue(margins.in_geometric_base)
        self.assertFalse(margins.in_functional_base)
        self.assertAlmostEqual(margins.geometric_posterior_margin_m, 0.10 * geometric_length)
        self.assertLess(margins.functional_posterior_margin_m, 0.0)
        self.assertGreater(margins.functional_anterior_margin_m, 0.0)

        metatarsal_point = pose.heel[0] + 0.85 * geometric_length
        forefoot = support_margins(pose, metatarsal_point)
        self.assertTrue(forefoot.in_functional_base)
        self.assertAlmostEqual(forefoot.functional_anterior_margin_m, 0.0)

    def test_wedge_support_margins_use_ankle_as_functional_posterior_limit(self) -> None:
        pose = pose_from_angles(Anthropometry(wedge_angle_deg=20.0), (0.0, 0.0, 0.0))

        margins = support_margins(pose, pose.ankle[0])

        self.assertAlmostEqual(margins.functional_posterior_m, pose.ankle[0])
        self.assertAlmostEqual(margins.functional_posterior_margin_m, 0.0)
        self.assertTrue(margins.in_functional_base)


if __name__ == "__main__":
    unittest.main()
