"""Grasp candidates for the registered objects (Phase 3 S6 candidate).

Only a top-down grasp of an upright registered object inside the workspace is produced: grasp
centre = measured top-surface centre lowered by half the registered size (clamped to the table),
approach point above it, lift point above that.  Gripper widths and clearances are TBD (the
gripper is not measured); the defaults are SYNTHETIC test values.  No arbitrary-pose, stacked or
unknown-object grasps.  Failure states: NO_DETECTION (detector failure), BELOW_TABLE (measured top
lower than the table: depth / calibration inconsistent), TOO_TALL.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from detector import Detection, DetStatus
from scene_config import SceneConfig


class GraspStatus(str, Enum):
    OK = "OK"
    NO_DETECTION = "NO_DETECTION"
    BELOW_TABLE = "BELOW_TABLE"
    TOO_TALL = "TOO_TALL"


@dataclass(frozen=True)
class GraspParams:
    approach_clearance_mm: float = 60.0      # SYNTHETIC / TBD
    lift_height_mm: float = 80.0             # SYNTHETIC / TBD
    gripper_open: float = 1.0                # normalised, mapped to the gripper channel by the IK (TBD)
    gripper_closed: float = 0.2


@dataclass(frozen=True)
class GraspCandidate:
    object_id: int
    status: GraspStatus
    grasp_mm: Optional[tuple] = None
    approach_mm: Optional[tuple] = None
    lift_mm: Optional[tuple] = None
    yaw_rad: float = 0.0
    detection: Optional[Detection] = None


def top_down_grasp(det: Detection, scene: SceneConfig, params: GraspParams = GraspParams()) -> GraspCandidate:
    if det.status != DetStatus.FOUND:
        return GraspCandidate(det.object_id, GraspStatus.NO_DETECTION, detection=det)
    x, y, z_top = det.top_base_mm
    ws, size = scene.workspace, scene.by_id(det.object_id).size_mm
    if z_top < ws.table_z_mm:
        return GraspCandidate(det.object_id, GraspStatus.BELOW_TABLE, detection=det)
    if z_top - ws.table_z_mm > ws.max_object_height_mm:
        return GraspCandidate(det.object_id, GraspStatus.TOO_TALL, detection=det)
    zg = max(ws.table_z_mm + 0.25 * size, z_top - 0.5 * size)
    return GraspCandidate(det.object_id, GraspStatus.OK, (x, y, zg), (x, y, zg + params.approach_clearance_mm),
                          (x, y, zg + params.lift_height_mm), det.yaw_rad or 0.0, det)
