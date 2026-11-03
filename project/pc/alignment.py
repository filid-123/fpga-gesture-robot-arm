"""Colour / depth alignment and invalid-depth handling (Phase 3 S6 candidate).

align_depth_to_color(): every valid depth pixel is back-projected with the depth intrinsics,
moved into the colour frame with depth_to_color and projected with the colour intrinsics; where
several depth pixels land on one colour pixel the nearest wins (z-buffer).  Invalid depth
(0, outside [depth_min, depth_max]) and colour pixels that receive no depth stay NaN - holes are
NOT filled or interpolated (a filled hole would invent geometry).  Lens distortion is assumed
already removed by the device adapter (vendor SDK alignment/undistortion is TBD).
"""

from __future__ import annotations

import numpy as np

from calibration import CalibrationSet


def valid_depth_mm(depth_u16: np.ndarray, calib: CalibrationSet) -> np.ndarray:
    d = depth_u16.astype(np.float64) * calib.depth_scale_mm
    d[(depth_u16 == 0) | (d < calib.depth_min_mm) | (d > calib.depth_max_mm)] = np.nan
    return d


def align_depth_to_color(depth_u16: np.ndarray, calib: CalibrationSet) -> np.ndarray:
    """(H_color, W_color) float64 depth in mm in the colour camera frame (z), NaN where unknown."""

    di, ci = calib.depth, calib.color
    d = valid_depth_mm(depth_u16, calib)
    v, u = np.nonzero(~np.isnan(d))
    out = np.full((ci.height, ci.width), np.nan)
    if u.size == 0:
        return out
    z = d[v, u]
    pts = np.stack([(u - di.cx) * z / di.fx, (v - di.cy) * z / di.fy, z], axis=1)
    pts = calib.depth_to_color.apply(pts)
    zc = pts[:, 2]
    front = zc > 0
    pts, zc = pts[front], zc[front]
    uc = np.round(pts[:, 0] * ci.fx / zc + ci.cx).astype(np.int64)
    vc = np.round(pts[:, 1] * ci.fy / zc + ci.cy).astype(np.int64)
    inside = (uc >= 0) & (uc < ci.width) & (vc >= 0) & (vc < ci.height)
    uc, vc, zc = uc[inside], vc[inside], zc[inside]
    order = np.argsort(-zc)                       # far first, near overwrites -> z-buffer
    out[vc[order], uc[order]] = zc[order]
    return out


def deproject(u: float, v: float, z_mm: float, calib: CalibrationSet) -> np.ndarray:
    """Colour pixel + depth (mm, colour frame) -> 3-D point in the colour camera frame (mm)."""

    ci = calib.color
    return np.array([(u - ci.cx) * z_mm / ci.fx, (v - ci.cy) * z_mm / ci.fy, z_mm])
