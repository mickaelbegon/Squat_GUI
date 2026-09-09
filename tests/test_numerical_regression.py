"""Deterministic numerical references for the analytical calculation chain.

The kinematics and analytical dynamics paths only use Python floating-point
operations, so their tolerances can be tight. The SLSQP reference deliberately
uses wider, outcome-level tolerances because convergence details can vary across
supported SciPy/BLAS builds while the biomechanical solution remains equivalent.
"""

from __future__ import annotations

import math

import pytest

from squat_gui.anthropometry import Anthropometry
from squat_gui.bar_path_optimization import optimize_deep_squat_bar_path
from squat_gui.dynamics import inverse_dynamics
from squat_gui.kinematics import (
    MotionState,
    PhaseDurations,
    com_accelerations,
    com_velocities,
    joint_values_from_segment_values,
    pose_from_angles,
)
from squat_gui.torque_capacity import torque_presets


ANALYTICAL_REL_TOLERANCE = 1e-9
ANALYTICAL_ABS_TOLERANCE = 1e-8
SLSQP_ANGLE_ABS_TOLERANCE_DEG = 0.75
SLSQP_METRIC_REL_TOLERANCE = 0.08


def _reference_anthropometry() -> Anthropometry:
    """Return a non-default morphology exercising every geometric offset."""

    return Anthropometry(
        body_mass=82.0,
        height=1.83,
        foot_scale=1.05,
        shank_scale=0.98,
        thigh_scale=1.04,
        trunk_scale=0.97,
        bar_mass=45.0,
        subject_profile="femme enceinte",
        bar_position="front",
        wedge_angle_deg=12.0,
        scaling_mode="morphotype recalibre",
    )


def _reference_motion_state(anthro: Anthropometry) -> MotionState:
    q = tuple(math.radians(value) for value in (24.0, -69.0, 31.0))
    return MotionState(
        time=1.25,
        q=q,
        qdot=(0.42, -0.31, 0.18),
        qddot=(-0.75, 0.62, -0.27),
        pose=pose_from_angles(anthro, q),
        phase="excentrique",
    )


def _assert_analytical_vector(
    actual: tuple[float, float], expected: tuple[float, float]
) -> None:
    assert actual == pytest.approx(
        expected,
        rel=ANALYTICAL_REL_TOLERANCE,
        abs=ANALYTICAL_ABS_TOLERANCE,
    )


def test_reference_kinematics_preserves_landmarks_and_com_derivatives() -> None:
    anthro = _reference_anthropometry()
    state = _reference_motion_state(anthro)

    expected_landmarks = {
        "ankle": (0.1448264580909544, 0.11364924972640485),
        "knee": (0.4041434396704395, 0.4705684548435644),
        "hip": (0.013084772566575364, 0.7245249226465114),
        "shoulder": (0.37626935925065774, 1.1139927093697684),
        "bar": (0.4894678443861934, 1.0953212493720106),
        "com": (0.33744371033145043, 0.8705854609636491),
    }
    for landmark, expected in expected_landmarks.items():
        _assert_analytical_vector(getattr(state.pose, landmark), expected)

    velocities = com_velocities(anthro, state.q, state.qdot)
    accelerations = com_accelerations(anthro, state.q, state.qdot, state.qddot)
    expected_velocities = {
        "shank": (0.08499673950660037, -0.06175374599333858),
        "thigh": (0.10526813780348303, -0.17764951418022992),
        "trunk": (0.09930229710693968, -0.27728630478207905),
        "bar": (0.1379228999408833, -0.3158902719931128),
    }
    expected_accelerations = {
        "shank": (-0.1777164652932743, 0.07457591582390387),
        "thigh": (-0.20284878430282055, 0.2551621944484648),
        "trunk": (-0.16906937283592127, 0.4152337315494293),
        "bar": (-0.2339489911848228, 0.4661879738558701),
    }
    for segment, expected in expected_velocities.items():
        _assert_analytical_vector(velocities[segment], expected)
    for segment, expected in expected_accelerations.items():
        _assert_analytical_vector(accelerations[segment], expected)


def test_reference_analytical_dynamics_preserves_forces_and_joint_terms() -> None:
    anthro = _reference_anthropometry()
    state = _reference_motion_state(anthro)

    result = inverse_dynamics(
        anthro,
        state,
        {"cheville": 240.0, "genou": 430.0, "hanche": 410.0},
        adapt_max_by_angle=False,
        adapt_max_by_velocity=False,
    )

    assert result.backend == "analytical"
    _assert_analytical_vector(
        result.ground_reaction,
        (-24.612832727631222, 1294.077769529465),
    )
    _assert_analytical_vector(
        result.com_velocity,
        (0.11096805705262855, -0.2590417971996727),
    )
    _assert_analytical_vector(
        result.com_acceleration,
        (-0.19380183250103325, 0.38293873645248094),
    )
    assert result.cop_x == pytest.approx(
        0.3546265952189223,
        rel=ANALYTICAL_REL_TOLERANCE,
        abs=ANALYTICAL_ABS_TOLERANCE,
    )
    assert result.dynamic_moment_z == pytest.approx(
        458.9143933567314,
        rel=ANALYTICAL_REL_TOLERANCE,
        abs=ANALYTICAL_ABS_TOLERANCE,
    )

    expected_components = {
        "cheville": {
            "mass_acceleration": -31.247198806360547,
            "velocity": 0.2968339987987396,
            "gravity": -239.10581797447043,
            "total": -270.05618278203224,
        },
        "genou": {
            "mass_acceleration": -8.062788552890062,
            "velocity": -1.661880667669542,
            "gravity": 69.09183625764524,
            "total": 59.367167037085636,
        },
        "hanche": {
            "mass_acceleration": -25.412256705249458,
            "velocity": 2.9169628728722428,
            "gravity": -350.5320623003653,
            "total": -373.0273561327425,
        },
    }
    for joint, expected_terms in expected_components.items():
        actual_terms = result.torque_components[joint]
        for term, expected in expected_terms.items():
            assert actual_terms[term] == pytest.approx(
                expected,
                rel=ANALYTICAL_REL_TOLERANCE,
                abs=ANALYTICAL_ABS_TOLERANCE,
            )


def test_reference_slsqp_solution_stays_in_the_same_biomechanical_basin() -> None:
    """Characterize the solution without depending on exact solver iterates."""

    anthro = Anthropometry()
    requested = tuple(math.radians(value) for value in (22.0, -58.0, 50.0))
    max_torques = dict(torque_presets(70.0, 1.70)["Anderson actif x2"].torques)

    result = optimize_deep_squat_bar_path(
        anthro,
        requested,
        PhaseDurations(4.0, 2.0, 4.0),
        21,
        max_torques,
        adapt_max_by_angle=True,
    )

    assert result.applied, result.message
    assert result.diagnostic is None

    # The baseline is pure analytical Python and therefore uses tight checks.
    assert result.before.horizontal_velocity_energy_m2_s == pytest.approx(
        0.010554090413306013,
        rel=ANALYTICAL_REL_TOLERANCE,
        abs=ANALYTICAL_ABS_TOLERANCE,
    )
    assert result.before.horizontal_excursion_m == pytest.approx(
        0.12413078763021548,
        rel=ANALYTICAL_REL_TOLERANCE,
        abs=ANALYTICAL_ABS_TOLERANCE,
    )

    # SciPy releases can stop at slightly different points on the same basin.
    final_joints_deg = {
        joint: math.degrees(value)
        for joint, value in joint_values_from_segment_values(result.final_q).items()
    }
    expected_joints_deg = {
        "cheville": 23.888282955501747,
        "genou": -82.63587653375207,
        "hanche": 103.0,
    }
    for joint, expected in expected_joints_deg.items():
        assert final_joints_deg[joint] == pytest.approx(
            expected,
            abs=SLSQP_ANGLE_ABS_TOLERANCE_DEG,
        )

    assert result.after.horizontal_velocity_energy_m2_s == pytest.approx(
        0.006270603214542522,
        rel=SLSQP_METRIC_REL_TOLERANCE,
    )
    assert result.after.horizontal_excursion_m == pytest.approx(
        0.09371831612958811,
        rel=SLSQP_METRIC_REL_TOLERANCE,
    )
    assert result.after.deep_hip_height_m == pytest.approx(
        0.6684596615329532,
        abs=0.0015,
    )
    assert result.after.minimum_vertical_grf_N == pytest.approx(
        678.1799511009848,
        rel=0.005,
    )
    assert (
        result.after.horizontal_velocity_energy_m2_s
        / result.before.horizontal_velocity_energy_m2_s
        == pytest.approx(0.5941396149721148, abs=0.06)
    )
    assert (
        result.after.horizontal_excursion_m / result.before.horizontal_excursion_m
        == pytest.approx(0.7549965477442562, abs=0.04)
    )
