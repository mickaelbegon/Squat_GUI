"""Yeadon-style quintic motion law."""

from __future__ import annotations


class QuinticBoundaryTrajectory:
    """Quintic trajectory with zero velocity and acceleration at both ends."""

    def __init__(self, t0: float, t1: float, q0: float, q1: float) -> None:
        if t1 <= t0:
            raise ValueError("t1 must be strictly greater than t0.")
        self.t0 = float(t0)
        self.t1 = float(t1)
        self.q0 = float(q0)
        self.q1 = float(q1)

    @property
    def duration(self) -> float:
        return self.t1 - self.t0

    def phase(self, time: float) -> float:
        raw = (float(time) - self.t0) / self.duration
        return min(1.0, max(0.0, raw))

    def position(self, time: float) -> float:
        x = self.phase(time)
        profile = 10.0 * x**3 - 15.0 * x**4 + 6.0 * x**5
        return self.q0 + (self.q1 - self.q0) * profile

    def velocity(self, time: float) -> float:
        if time < self.t0 or time > self.t1:
            return 0.0
        x = self.phase(time)
        profile_d1 = 30.0 * x**2 - 60.0 * x**3 + 30.0 * x**4
        return (self.q1 - self.q0) * profile_d1 / self.duration

    def acceleration(self, time: float) -> float:
        if time < self.t0 or time > self.t1:
            return 0.0
        x = self.phase(time)
        profile_d2 = 60.0 * x - 180.0 * x**2 + 120.0 * x**3
        return (self.q1 - self.q0) * profile_d2 / (self.duration**2)
