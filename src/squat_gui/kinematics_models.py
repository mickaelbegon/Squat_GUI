"""Data models and shared constants for planar squat kinematics."""

from __future__ import annotations

from dataclasses import dataclass


Vector = tuple[float, float]

# The simplified foot model has no separate toe-joint.  The metatarsal head is
# therefore represented by the anterior 85% point of the heel-to-toe segment;
# the remaining 15% represents the distal toes beyond the functional forefoot.
METATARSAL_HEAD_FRACTION = 0.85
DEFAULT_SAMPLE_PERIOD_S = 0.05
CLINICAL_JOINT_LIMITS_DEG = {
    "cheville": (-30.0, 40.0),
    "genou": (0.0, 140.0),
    "hanche": (-15.0, 120.0),
}


@dataclass(frozen=True)
class Pose:
    heel: Vector
    toe: Vector
    ankle: Vector
    knee: Vector
    hip: Vector
    shoulder: Vector
    bar: Vector
    com: Vector
    segment_coms: dict[str, Vector]


@dataclass(frozen=True)
class _SegmentAngles:
    """Three absolute segment values stored by the squat model.

    The public API deliberately continues to exchange tuples and dictionaries.
    This small internal value object simply gives the conversion and geometry
    code explicit names for the three entries while it is being assembled.
    """

    shank: float
    thigh: float
    trunk: float

    @classmethod
    def from_values(cls, values: tuple[float, float, float]) -> _SegmentAngles:
        return cls(*values)

    @classmethod
    def from_joint_values(cls, ankle: float, knee: float, hip: float) -> _SegmentAngles:
        thigh = ankle + knee
        return cls(ankle, thigh, thigh + hip)

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.shank, self.thigh, self.trunk)

    def joint_values(self) -> dict[str, float]:
        return {
            "cheville": self.shank,
            "genou": self.thigh - self.shank,
            "hanche": self.trunk - self.thigh,
        }


@dataclass(frozen=True)
class _PoseGeometry:
    """Named landmarks assembled before mass and support projections."""

    heel: Vector
    toe: Vector
    ankle: Vector
    knee: Vector
    hip: Vector
    shoulder: Vector
    bar: Vector

    def pose(self, com: Vector, segment_coms: dict[str, Vector]) -> Pose:
        return Pose(
            self.heel,
            self.toe,
            self.ankle,
            self.knee,
            self.hip,
            self.shoulder,
            self.bar,
            com,
            segment_coms,
        )


@dataclass(frozen=True)
class MotionState:
    time: float
    q: tuple[float, float, float]
    qdot: tuple[float, float, float]
    qddot: tuple[float, float, float]
    pose: Pose
    phase: str = "statique"


@dataclass(frozen=True)
class PhaseDurations:
    excentrique: float = 4.0
    isometrique: float = 2.0
    concentrique: float = 4.0

    @property
    def total(self) -> float:
        return self.excentrique + self.isometrique + self.concentrique

    @property
    def squat_reference_time(self) -> float:
        return self.excentrique + self.isometrique / 2.0
