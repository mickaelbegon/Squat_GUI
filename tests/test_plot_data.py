import unittest
from math import radians

from squat_gui.anthropometry import Anthropometry
from squat_gui.dynamics import inverse_dynamics
from squat_gui.kinematics import PhaseDurations, motion_state
from squat_gui.plot_data import (
    PlotDataset,
    centered_times,
    current_plot_time,
    plot_times,
    sample_dataset_at_time,
    select_plot_datasets,
)
from squat_gui.timeline import TimeMode


class PlotDataTests(unittest.TestCase):
    def dataset(self, label: str = "courant") -> PlotDataset:
        anthro = Anthropometry()
        durations = PhaseDurations(1.0, 1.0, 1.0)
        final_q = (radians(20.0), radians(-60.0), radians(25.0))
        states = [
            motion_state(anthro, final_q, durations, time)
            for time in (0.0, 1.5, 3.0)
        ]
        limits = {"cheville": 180.0, "genou": 220.0, "hanche": 260.0}
        results = [
            inverse_dynamics(anthro, state, limits, True) for state in states
        ]
        return PlotDataset(
            label=label,
            states=states,
            results=results,
            color=None,
            anthro=anthro,
            refined_sprites=True,
            durations=durations,
        )

    def test_selection_preserves_ui_order_and_falls_back_to_current(self) -> None:
        current = self.dataset()
        first = self.dataset("première")
        second = self.dataset("deuxième")
        saved = {"a": first, "b": second}

        self.assertEqual(
            select_plot_datasets(current, saved, ("b", "inconnue", "a")),
            [second, first],
        )
        self.assertEqual(select_plot_datasets(current, saved, ()), [current])

    def test_time_modes_are_prepared_without_gui_state(self) -> None:
        dataset = self.dataset()

        self.assertEqual(centered_times(dataset.states), [-0.75, 0.75, 2.25])
        self.assertEqual(
            plot_times(dataset.states, TimeMode.ABSOLUTE), [0.0, 1.5, 3.0]
        )
        self.assertEqual(
            plot_times(dataset.states, TimeMode.NORMALIZED), [0.0, 50.0, 100.0]
        )

    def test_sampling_keeps_state_and_result_synchronized(self) -> None:
        dataset = self.dataset()

        sample = sample_dataset_at_time(dataset, 0.6, TimeMode.CENTERED)

        self.assertIs(sample.dataset, dataset)
        self.assertIs(sample.state, dataset.states[1])
        self.assertIs(sample.result, dataset.results[1])

    def test_shared_frame_spans_all_visible_dataset_times(self) -> None:
        first = self.dataset("première")
        second = self.dataset("deuxième")
        shifted_states = [
            type(state)(
                state.time + 2.0,
                state.q,
                state.qdot,
                state.qddot,
                state.pose,
                state.phase,
            )
            for state in second.states
        ]
        second = PlotDataset(
            second.label,
            shifted_states,
            second.results,
            second.color,
            second.anthro,
            second.refined_sprites,
            second.durations,
        )

        self.assertEqual(
            current_plot_time(
                [first, second], TimeMode.ABSOLUTE, frame=50, frame_count=101
            ),
            2.5,
        )

    def test_empty_dataset_cannot_be_sampled(self) -> None:
        dataset = self.dataset()
        empty = PlotDataset(
            dataset.label,
            [],
            [],
            dataset.color,
            dataset.anthro,
            dataset.refined_sprites,
            dataset.durations,
        )

        with self.assertRaisesRegex(ValueError, "aucun échantillon"):
            sample_dataset_at_time(empty, 0.0, TimeMode.CENTERED)


if __name__ == "__main__":
    unittest.main()
