from math import isclose, radians, sin

import pytest

from squat_gui.anthropometry import Anthropometry
from squat_gui.dynamics import inverse_dynamics
from squat_gui.kinematics import PhaseDurations, motion_state
from squat_gui.patellofemoral import (
    estimate_patellofemoral_load,
    patellar_mechanism_angle_deg,
    patellofemoral_contact_area_mm2,
    quadriceps_moment_arm_m,
)


def test_ninety_degree_estimate_uses_one_half_of_bilateral_moment() -> None:
    estimate = estimate_patellofemoral_load(90.0, 100.0, 70.0)

    expected_quadriceps_force = 50.0 / 0.02
    expected_reaction = 2.0 * expected_quadriceps_force * sin(
        radians((30.46 + 0.53 * 90.0) / 2.0)
    )
    expected_area = 0.0781 * 90.0**2 + 0.6763 * 90.0 + 151.75

    assert estimate.knee_extension_moment_per_side_Nm == 50.0
    assert estimate.quadriceps_moment_arm_m == 0.02
    assert isclose(estimate.quadriceps_force_per_side_N, expected_quadriceps_force)
    assert isclose(estimate.reaction_force_per_side_N, expected_reaction)
    assert isclose(estimate.contact_area_mm2, expected_area)
    assert isclose(estimate.stress_MPa, expected_reaction / expected_area)
    assert not estimate.extrapolated


def test_negative_extension_moment_does_not_create_compressive_load() -> None:
    estimate = estimate_patellofemoral_load(20.0, -30.0, 70.0)

    assert estimate.knee_extension_moment_per_side_Nm == 0.0
    assert estimate.quadriceps_force_per_side_N == 0.0
    assert estimate.reaction_force_per_side_N == 0.0
    assert estimate.stress_MPa == 0.0


def test_deep_flexion_is_calculated_but_explicitly_marked_as_extrapolated() -> None:
    estimate = estimate_patellofemoral_load(120.0, 120.0, 70.0)

    assert estimate.stress_MPa > 0.0
    assert estimate.extrapolated
    assert estimate.validity == "extrapolation_flexion_profonde"


def test_inverse_dynamics_attaches_the_estimate_to_every_result() -> None:
    anthro = Anthropometry()
    state = motion_state(
        anthro,
        (radians(22.0), radians(-58.0), radians(20.0)),
        PhaseDurations(4.0, 1.0, 4.0),
        4.0,
    )

    result = inverse_dynamics(
        anthro,
        state,
        {"cheville": 222.0, "genou": 380.0, "hanche": 376.0},
        adapt_max_by_angle=False,
    )

    assert result.patellofemoral is not None
    assert result.patellofemoral.knee_flexion_deg == pytest.approx(80.0)
    assert result.patellofemoral.knee_extension_moment_per_side_Nm == pytest.approx(
        max(0.0, result.torques["genou"]) / 2.0
    )


def test_published_angle_functions_are_exposed_for_auditing() -> None:
    assert quadriceps_moment_arm_m(0.0) == pytest.approx(0.03)
    assert quadriceps_moment_arm_m(45.0) == pytest.approx(0.03465)
    assert quadriceps_moment_arm_m(75.0) == pytest.approx(0.02275)
    assert patellar_mechanism_angle_deg(60.0) == pytest.approx(62.26)
    assert patellofemoral_contact_area_mm2(0.0) == pytest.approx(151.75)


@pytest.mark.parametrize("mass, sides", [(0.0, 2), (70.0, 0)])
def test_invalid_normalization_inputs_are_rejected(mass: float, sides: int) -> None:
    with pytest.raises(ValueError):
        estimate_patellofemoral_load(60.0, 100.0, mass, side_count=sides)
