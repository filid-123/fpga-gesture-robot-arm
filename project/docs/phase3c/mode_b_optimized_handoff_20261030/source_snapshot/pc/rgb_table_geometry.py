"""RGB ray intersections with known-height table planes; local preview only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


class RGBTableGeometry:
    def __init__(self, table_path, project_root=None):
        root = Path(project_root or Path(__file__).resolve().parents[1])
        table_path = Path(table_path).resolve()
        raw = table_path.read_bytes()
        self.table = json.loads(raw)
        if self.table.get("schema") != "gesture.ai_pc.rgb_table_transform.v1":
            raise ValueError("Not an RGB table transform")
        intr_path = root / self.table["intrinsics_file"]
        intr_raw = intr_path.read_bytes()
        if hashlib.sha256(intr_raw).hexdigest() != self.table["intrinsics_sha256"]:
            raise ValueError("Intrinsics hash does not match table transform")
        self.intrinsics = json.loads(intr_raw)
        if self.intrinsics.get("schema") != "gesture.ai_pc.rgb_intrinsics.v1":
            raise ValueError("Not RGB intrinsics")
        self.size = self.table["image_size_wh"]
        if self.size != self.intrinsics["image_size_wh"]:
            raise ValueError("Intrinsics/table image sizes differ")
        self.K = np.array(self.intrinsics["camera_matrix"], dtype=float)
        self.dist = np.array(self.intrinsics["distortion_coefficients"], dtype=float)
        pose = self.table["table_to_camera_nominal"]
        self.R = np.array(pose["rotation"], dtype=float)
        self.t = np.array(pose["translation_mm"], dtype=float)
        if (self.R.shape != (3, 3) or self.t.shape != (3,) or self.K.shape != (3, 3)
                or not all(np.isfinite(a).all() for a in (self.R, self.t, self.K, self.dist))
                or not np.allclose(self.R.T @ self.R, np.eye(3), atol=1e-6)
                or not np.isclose(np.linalg.det(self.R), 1, atol=1e-6)
                or min(self.K[0, 0], self.K[1, 1]) <= 0):
            raise ValueError("Invalid RGB table geometry")
        self.origin = -self.R.T @ self.t
        self.record = {
            "schema": "gesture.ai_pc.rgb_table_geometry_snapshot.v1",
            "table_file": str(table_path), "table_sha256": hashlib.sha256(raw).hexdigest(),
            "intrinsics_sha256": hashlib.sha256(intr_raw).hexdigest(),
            "table": self.table, "intrinsics": self.intrinsics,
            "physical_execution": False, "depth_available": False,
            "scope": "Known-height manual top-point preview; no robot-base coordinates or grasp authorization",
        }

    def check_frame(self, shape):
        if [shape[1], shape[0]] != self.size:
            raise ValueError("Actual frame size differs from RGB calibration")

    def project(self, pixel_uv, plane_z_mm):
        uv = np.array(pixel_uv, dtype=float)
        z = float(plane_z_mm)
        if uv.shape != (2,) or not np.isfinite(uv).all() or not np.isfinite(z):
            raise ValueError("Invalid pixel/height")
        if not (0 <= uv[0] < self.size[0] and 0 <= uv[1] < self.size[1]):
            raise ValueError("Pixel outside calibrated image")
        criteria = (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 50, 1e-12)
        iterative = getattr(cv2, "undistortPointsIter", None)
        if iterative is not None:
            ray_uv = iterative(uv.reshape(1, 1, 2), self.K, self.dist, None, None, criteria).reshape(2)
        else:
            # OpenCV 5 folds the iterative overload into undistortPoints.
            ray_uv = cv2.undistortPoints(uv.reshape(1, 1, 2), self.K, self.dist,
                                       criteria=criteria).reshape(2)
        ray = self.R.T @ np.array([ray_uv[0], ray_uv[1], 1.0])
        if abs(ray[2]) < 1e-10:
            raise ValueError("Ray is parallel to height plane")
        distance = (z - self.origin[2]) / ray[2]
        if distance <= 0:
            raise ValueError("Height plane is behind camera")
        xyz = self.origin + distance * ray
        if not np.isfinite(xyz).all():
            raise ValueError("Nonfinite plane intersection")
        return xyz.tolist()

    def manual_top(self, pixel_uv, plane_z_mm):
        xyz = self.project(pixel_uv, plane_z_mm)
        bounds = self.intrinsics.get("calibrated_corner_bounds_xy")
        inside = bounds is None or all(bounds[0][i] <= pixel_uv[i] <= bounds[1][i] for i in (0, 1))
        return {
            "status": "MANUAL_TOP_CANDIDATE" if inside else "MANUAL_TOP_EXTRAPOLATED",
            "input_method": "USER_CLICKED_TOP_CENTRE", "pixel_uv": list(pixel_uv),
            "coordinate_system": self.table["table_frame_id"], "table_xyz_mm": xyz,
            "assumed_top_height_mm": float(plane_z_mm),
            "height_source": "USER_REPORTED_CUBE_HEIGHT", "depth_measured": False,
            "top_centre_automatically_validated": False,
            "inside_intrinsics_observed_corner_bounds": inside,
            "independent_metric_validation": "NOT_RECORDED_BY_PROGRAM",
            "robot_base_xyz_mm": None, "physical_execution": False,
        }
