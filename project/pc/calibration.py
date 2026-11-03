"""Calibration data structures (Phase 3 S6 candidate).

CalibrationSet = colour intrinsics, depth intrinsics, depth->colour extrinsics, colour->robot-base
extrinsics (hand-eye / table), depth scale and valid depth range, and a status:
  CALIBRATED  from a measured calibration run (the only status that allows real execution)
  SYNTHETIC   generated for tests / recordings of synthetic scenes
  TBD         placeholder; perception may run for display but nothing is executable
All real values are TBD (no camera, no arm, no calibration run); this module only defines, loads,
saves and applies them.  Units: pixels, millimetres, right-handed frames.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

SCHEMA = "gesture.phase3.s6_calibration.v1"
STATUSES = ("CALIBRATED", "SYNTHETIC", "TBD")


@dataclass(frozen=True)
class CameraIntrinsics:
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    dist: tuple = (0.0, 0.0, 0.0, 0.0, 0.0)          # k1 k2 p1 p2 k3 (OpenCV); applied by the vendor adapter

    def matrix(self) -> np.ndarray:
        return np.array([[self.fx, 0, self.cx], [0, self.fy, self.cy], [0, 0, 1]], dtype=np.float64)


@dataclass(frozen=True)
class RigidTransform:
    rotation: tuple          # row-major 3x3
    translation: tuple       # mm

    @property
    def R(self) -> np.ndarray:
        return np.array(self.rotation, dtype=np.float64).reshape(3, 3)

    @property
    def t(self) -> np.ndarray:
        return np.array(self.translation, dtype=np.float64)

    def apply(self, points: np.ndarray) -> np.ndarray:
        return points @ self.R.T + self.t

    def inverse(self) -> "RigidTransform":
        R = self.R.T
        return RigidTransform(tuple(R.reshape(-1)), tuple(-(R @ self.t)))

    def check(self) -> None:
        R = self.R
        if not np.allclose(R @ R.T, np.eye(3), atol=1e-6) or not np.isclose(np.linalg.det(R), 1.0, atol=1e-6):
            raise ValueError("rotation is not orthonormal / right-handed")


IDENTITY = RigidTransform((1.0, 0, 0, 0, 1.0, 0, 0, 0, 1.0), (0.0, 0.0, 0.0))


@dataclass(frozen=True)
class CalibrationSet:
    calib_id: int
    status: str
    color: CameraIntrinsics
    depth: CameraIntrinsics
    depth_to_color: RigidTransform
    color_to_base: RigidTransform
    depth_scale_mm: float = 1.0
    depth_min_mm: float = 200.0
    depth_max_mm: float = 1500.0
    source: str = "TBD"

    def check(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"unknown calibration status {self.status}")
        self.depth_to_color.check()
        self.color_to_base.check()
        if not 0 < self.depth_min_mm < self.depth_max_mm:
            raise ValueError("depth range")

    def require_calibrated(self) -> None:
        if self.status != "CALIBRATED":
            raise PermissionError(f"calibration {self.calib_id} is {self.status}: not usable for real execution")

    def save(self, path: Path) -> None:
        d = asdict(self)
        d["schema"] = SCHEMA
        Path(path).write_bytes((json.dumps(d, indent=2) + "\n").encode("utf-8"))

    @classmethod
    def load(cls, path: Path) -> "CalibrationSet":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        if d.pop("schema", None) != SCHEMA:
            raise ValueError(f"{path}: not an S6 calibration file")
        c = cls(calib_id=d["calib_id"], status=d["status"], color=CameraIntrinsics(**{**d["color"], "dist": tuple(d["color"]["dist"])}),
                depth=CameraIntrinsics(**{**d["depth"], "dist": tuple(d["depth"]["dist"])}),
                depth_to_color=RigidTransform(tuple(d["depth_to_color"]["rotation"]), tuple(d["depth_to_color"]["translation"])),
                color_to_base=RigidTransform(tuple(d["color_to_base"]["rotation"]), tuple(d["color_to_base"]["translation"])),
                depth_scale_mm=d["depth_scale_mm"], depth_min_mm=d["depth_min_mm"], depth_max_mm=d["depth_max_mm"],
                source=d["source"])
        c.check()
        return c
