"""SYNTHETIC RGB-D scenes for tests and recordings (never used as real data).

A table plane and up to three upright cubes, seen by a colour camera and a depth camera that is
offset from it (so alignment is exercised), both looking straight down.  Depth is rendered in the
depth camera, colour in the colour camera, from the same geometry; depth noise and dropped pixels
are added.  The calibration returned has status SYNTHETIC: nothing derived from it is executable.
Frames: base X forward, Y left, Z up; camera x right, y down, z along the optical axis.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from calibration import CalibrationSet, CameraIntrinsics, RigidTransform
from rgbd_device import RGBDDevice, RGBDFrame
from scene_config import RegisteredObject, SceneConfig, Workspace

CAM_BASE_T = (300.0, 0.0, 800.0)                  # colour camera centre in the base frame (mm)
R_BASE_FROM_CAM = (0.0, -1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, -1.0)
DEPTH_OFFSET_CAM = (25.0, 0.0, 0.0)               # depth camera centre in the colour camera frame (mm)
TABLE_Z = 0.0
BGR = {1: (40, 100, 220), 2: (40, 200, 40), 3: (220, 60, 40)}      # orange, green, blue (hue away from the 0/180 wrap)


def synthetic_calibration(calib_id: int = 900001) -> CalibrationSet:
    color = CameraIntrinsics(640, 480, 600.0, 600.0, 320.0, 240.0)
    depth = CameraIntrinsics(640, 480, 580.0, 580.0, 318.0, 242.0)
    d2c = RigidTransform((1.0, 0, 0, 0, 1.0, 0, 0, 0, 1.0), DEPTH_OFFSET_CAM)
    c2b = RigidTransform(R_BASE_FROM_CAM, CAM_BASE_T)
    return CalibrationSet(calib_id, "SYNTHETIC", color, depth, d2c, c2b, 1.0, 200.0, 1500.0, "synthetic_scene.py")


def synthetic_scene_config() -> SceneConfig:
    objs = (RegisteredObject(1, "orange_cube", (3, 120, 80), (18, 255, 255), 45.0, 400, 20000),
            RegisteredObject(2, "green_cube", (50, 120, 80), (70, 255, 255), 45.0, 400, 20000),
            RegisteredObject(3, "blue_cube", (100, 120, 80), (130, 255, 255), 45.0, 400, 20000))
    ws = Workspace((150.0, 450.0), (-180.0, 180.0), TABLE_Z, 120.0, (200.0, -220.0, 40.0), "SYNTHETIC")
    return SceneConfig("SYNTHETIC", objs, ws)


@dataclass(frozen=True)
class CubePose:
    object_id: int
    x_mm: float
    y_mm: float
    size_mm: float = 45.0


def _render(intr: CameraIntrinsics, cam_from_base: RigidTransform, cubes, depth: bool):
    """Per-pixel z (mm, camera frame) of table / cube tops, and the owning object id (0 = table)."""

    H, W = intr.height, intr.width
    t = cam_from_base.apply(np.array([[0.0, 0.0, TABLE_Z]]))[0]          # a table point, for its depth
    z = np.full((H, W), t[2])
    owner = np.zeros((H, W), np.int32)
    for c in sorted(cubes, key=lambda c: -c.size_mm):
        top = TABLE_Z + c.size_mm
        h = c.size_mm / 2
        corners = np.array([[c.x_mm + dx, c.y_mm + dy, top] for dx in (-h, h) for dy in (-h, h)])
        pc = cam_from_base.apply(corners)
        u = pc[:, 0] * intr.fx / pc[:, 2] + intr.cx
        v = pc[:, 1] * intr.fy / pc[:, 2] + intr.cy
        u0, u1 = int(np.ceil(u.min())), int(np.floor(u.max()))
        v0, v1 = int(np.ceil(v.min())), int(np.floor(v.max()))
        u0, v0, u1, v1 = max(u0, 0), max(v0, 0), min(u1, W - 1), min(v1, H - 1)
        if u0 <= u1 and v0 <= v1:
            z[v0:v1 + 1, u0:u1 + 1] = pc[0, 2]
            owner[v0:v1 + 1, u0:u1 + 1] = c.object_id
    return z, owner


def render_frame(cubes, index: int = 0, seed: int = 0, drop_ratio: float = 0.03, noise_mm: float = 1.5,
                 calib: CalibrationSet | None = None) -> RGBDFrame:
    calib = calib or synthetic_calibration()
    rng = np.random.default_rng(seed)
    cam_from_base_c = calib.color_to_base.inverse()
    base_from_depth = RigidTransform(tuple((calib.color_to_base.R @ calib.depth_to_color.R).reshape(-1)),
                                     tuple(calib.color_to_base.apply(calib.depth_to_color.t[None, :])[0]))
    cam_from_base_d = base_from_depth.inverse()
    _zc, owner = _render(calib.color, cam_from_base_c, cubes, depth=False)
    color = np.full((calib.color.height, calib.color.width, 3), (150, 150, 150), np.uint8)
    for oid, bgr in BGR.items():
        color[owner == oid] = bgr
    color = np.clip(color.astype(np.int16) + rng.integers(-6, 7, color.shape), 0, 255).astype(np.uint8)
    zd, _od = _render(calib.depth, cam_from_base_d, cubes, depth=True)
    zd = zd + rng.normal(0.0, noise_mm, zd.shape)
    depth = np.clip(np.round(zd), 0, 65535).astype(np.uint16)
    depth[rng.random(depth.shape) < drop_ratio] = 0
    return RGBDFrame(index, color, depth, 1_000_000 * index, 1_000_000 * index + 250_000)


class SyntheticRGBDDevice(RGBDDevice):
    """An RGBDDevice that returns pre-rendered SYNTHETIC frames in order (tests only)."""

    def __init__(self, frames):
        self.frames, self._i = list(frames), 0

    def open(self) -> None:
        self._i = 0

    def read(self):
        if self._i >= len(self.frames):
            return None
        self._i += 1
        return self.frames[self._i - 1]

    def close(self) -> None:
        pass

    def info(self) -> dict:
        return {"kind": "synthetic", "frames": len(self.frames), "status": "SYNTHETIC"}
