"""Compatibility facade for the planar squat kinematics subsystem.

Consumers may keep importing the historical symbols from this module. The
implementation lives in focused modules separating immutable state, spatial
geometry, and temporal derivatives and sampling.
"""

from __future__ import annotations

from .anthropometry import Anthropometry as Anthropometry
from .kinematics_geometry import _absolute_segment_angles as _absolute_segment_angles
from .kinematics_geometry import _pose_geometry as _pose_geometry
from .kinematics_geometry import _segment_com_positions as _segment_com_positions
from .kinematics_geometry import _whole_body_com as _whole_body_com
from .kinematics_geometry import _wrapped_angle as _wrapped_angle
from .kinematics_geometry import add as add
from .kinematics_geometry import anterior_unit_from_vertical as anterior_unit_from_vertical
from .kinematics_geometry import balanced_standing_angles as balanced_standing_angles
from .kinematics_geometry import (
    clinical_joint_values_from_segment_values as clinical_joint_values_from_segment_values,
)
from .kinematics_geometry import cross_z as cross_z
from .kinematics_geometry import dot as dot
from .kinematics_geometry import functional_support_limits as functional_support_limits
from .kinematics_geometry import geometric_support_limits as geometric_support_limits
from .kinematics_geometry import (
    joint_angles_from_orientations as joint_angles_from_orientations,
)
from .kinematics_geometry import joint_angles_from_pose as joint_angles_from_pose
from .kinematics_geometry import (
    joint_values_from_segment_values as joint_values_from_segment_values,
)
from .kinematics_geometry import local_point as local_point
from .kinematics_geometry import metatarsal_head_point as metatarsal_head_point
from .kinematics_geometry import pose_from_angles as pose_from_angles
from .kinematics_geometry import rotate_clockwise as rotate_clockwise
from .kinematics_geometry import scale as scale
from .kinematics_geometry import segment_orientations as segment_orientations
from .kinematics_geometry import (
    segment_values_from_clinical_joint_values as segment_values_from_clinical_joint_values,
)
from .kinematics_geometry import (
    segment_values_from_joint_values as segment_values_from_joint_values,
)
from .kinematics_geometry import sub as sub
from .kinematics_geometry import unit_from_vertical as unit_from_vertical
from .kinematics_geometry import zmp_in_support as zmp_in_support
from .kinematics_geometry import zmp_support_limits as zmp_support_limits
from .kinematics_models import CLINICAL_JOINT_LIMITS_DEG as CLINICAL_JOINT_LIMITS_DEG
from .kinematics_models import DEFAULT_SAMPLE_PERIOD_S as DEFAULT_SAMPLE_PERIOD_S
from .kinematics_models import METATARSAL_HEAD_FRACTION as METATARSAL_HEAD_FRACTION
from .kinematics_models import MotionState as MotionState
from .kinematics_models import PhaseDurations as PhaseDurations
from .kinematics_models import Pose as Pose
from .kinematics_models import Vector as Vector
from .kinematics_models import _PoseGeometry as _PoseGeometry
from .kinematics_models import _SegmentAngles as _SegmentAngles
from .kinematics_motion import _validate_sample_period as _validate_sample_period
from .kinematics_motion import angle_derivative_vector as angle_derivative_vector
from .kinematics_motion import (
    angle_second_derivative_vector as angle_second_derivative_vector,
)
from .kinematics_motion import com_accelerations as com_accelerations
from .kinematics_motion import com_velocities as com_velocities
from .kinematics_motion import frame_count_for_duration as frame_count_for_duration
from .kinematics_motion import (
    local_angle_derivative_vector as local_angle_derivative_vector,
)
from .kinematics_motion import (
    local_angle_second_derivative_vector as local_angle_second_derivative_vector,
)
from .kinematics_motion import motion_state as motion_state
from .kinematics_motion import phase_durations as phase_durations
from .yeadon import QuinticBoundaryTrajectory as QuinticBoundaryTrajectory
