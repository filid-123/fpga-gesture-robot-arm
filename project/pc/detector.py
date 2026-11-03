"""Detection and 3-D localisation of the three registered objects (Phase 3 S6 candidate).

Detector is the replaceable interface.  ColorBlobDetector is the REFERENCE implementation for the
coloured registered items (HSV range -> connected components inside the colour image), validated
only on synthetic / recorded data; a learned detector (inference_backend) can replace it without
changing the result type.  The 3-D position comes from the aligned depth of the blob (median of
the valid depth pixels) and the calibration; it is reported in the robot-base frame.

Failure states (never guessed away): NOT_FOUND, MULTIPLE_INSTANCES (the plan allows one instance
per class), INSUFFICIENT_DEPTH (too few valid depth pixels on the blob), OUT_OF_WORKSPACE.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import cv2
import numpy as np

from alignment import deproject
from calibration import CalibrationSet
from scene_config import RegisteredObject, SceneConfig


class DetStatus(str, Enum):
    FOUND = "FOUND"
    NOT_FOUND = "NOT_FOUND"
    MULTIPLE_INSTANCES = "MULTIPLE_INSTANCES"
    INSUFFICIENT_DEPTH = "INSUFFICIENT_DEPTH"
    OUT_OF_WORKSPACE = "OUT_OF_WORKSPACE"


@dataclass(frozen=True)
class Detection:
    object_id: int
    status: DetStatus
    pixel_uv: Optional[tuple] = None
    area_px: int = 0
    depth_valid_ratio: float = 0.0
    top_camera_mm: Optional[tuple] = None        # top-surface centre, colour camera frame
    top_base_mm: Optional[tuple] = None          # same point, robot-base frame
    yaw_rad: Optional[float] = None              # blob orientation in the image (approximate, top-down view)


class Detector(ABC):
    @abstractmethod
    def detect(self, color_bgr: np.ndarray, depth_mm: np.ndarray, calib: CalibrationSet, scene: SceneConfig,
               object_id: int) -> Detection: ...


class ColorBlobDetector(Detector):
    MIN_DEPTH_RATIO = 0.3

    @staticmethod
    def _rect_yaw(width: float, height: float, angle_deg: float) -> float:
        # A square has no preferred grasp axis. OpenCV may return either of
        # its perpendicular edges, which otherwise changes the path digest.
        if abs(width - height) <= 1.0:
            return 0.0
        long_axis_deg = angle_deg + (90.0 if width < height else 0.0)
        return float(np.deg2rad((long_axis_deg + 90.0) % 180.0 - 90.0))

    def detect(self, color_bgr, depth_mm, calib, scene, object_id) -> Detection:
        obj: RegisteredObject = scene.by_id(object_id)
        hsv = cv2.cvtColor(color_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(obj.hsv_low, np.uint8), np.array(obj.hsv_high, np.uint8))
        n, labels, stats, cents = cv2.connectedComponentsWithStats(mask, connectivity=8)
        blobs = [k for k in range(1, n) if obj.min_area_px <= stats[k, cv2.CC_STAT_AREA] <= obj.max_area_px]
        if not blobs:
            return Detection(object_id, DetStatus.NOT_FOUND)
        if len(blobs) > 1:
            return Detection(object_id, DetStatus.MULTIPLE_INSTANCES, area_px=int(sum(stats[k, cv2.CC_STAT_AREA] for k in blobs)))
        k = blobs[0]
        sel = labels == k
        area = int(stats[k, cv2.CC_STAT_AREA])
        z = depth_mm[sel]
        z = z[~np.isnan(z)]
        ratio = z.size / max(1, area)
        u, v = float(cents[k][0]), float(cents[k][1])
        ys, xs = np.nonzero(sel)
        (_cx, _cy), (width, height), angle = cv2.minAreaRect(np.stack([xs, ys], axis=1).astype(np.float32))
        yaw = self._rect_yaw(width, height, angle)
        if ratio < self.MIN_DEPTH_RATIO:
            return Detection(object_id, DetStatus.INSUFFICIENT_DEPTH, (u, v), area, ratio, yaw_rad=yaw)
        top_cam = deproject(u, v, float(np.median(z)), calib)
        top_base = calib.color_to_base.apply(top_cam[None, :])[0]
        status = DetStatus.FOUND if scene.workspace.contains(top_base[0], top_base[1]) else DetStatus.OUT_OF_WORKSPACE
        return Detection(object_id, status, (u, v), area, ratio, tuple(top_cam), tuple(top_base), yaw)
