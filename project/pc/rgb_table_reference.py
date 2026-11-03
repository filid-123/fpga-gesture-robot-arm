"""Offline table-reference candidates and ruler measurements; no robot control."""
from __future__ import annotations

import math

import cv2
import numpy as np


def fit_reference(corners, pattern_wh, square_mm, camera_matrix, distortion, surface_height_mm):
    """Corners must be rows top-to-bottom, columns left-to-right in the RAW image."""
    cols, rows = pattern_wh
    if cols < 2 or rows < 2 or not math.isfinite(square_mm) or square_mm <= 0:
        raise ValueError("Invalid pattern or square size")
    if not math.isfinite(surface_height_mm) or surface_height_mm < 0:
        raise ValueError("Invalid reference surface height")
    uv = np.asarray(corners, dtype=np.float64).reshape(rows * cols, 2)
    if not np.isfinite(uv).all():
        raise ValueError("Nonfinite corners")
    xyz = np.array([[c * square_mm, (rows - 1 - r) * square_mm, 0.]
                    for r in range(rows) for c in range(cols)], dtype=np.float64)
    K = np.asarray(camera_matrix, dtype=float)
    dist = np.asarray(distortion, dtype=float)
    ok, rvec, tvec = cv2.solvePnP(xyz, uv, K, dist, flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok:
        raise ValueError("Reference pose fit failed")
    R = cv2.Rodrigues(rvec)[0]
    t_board = tvec.reshape(3)
    t_table = t_board - surface_height_mm * R[:, 2]
    camera_origin = -R.T @ t_table
    if camera_origin[2] <= surface_height_mm or np.min((xyz @ R.T + t_board)[:, 2]) <= 0:
        raise ValueError("Reference pose faces away from camera")
    reprojection = cv2.projectPoints(xyz, rvec, tvec, K, dist)[0].reshape(-1, 2)
    error = np.linalg.norm(reprojection - uv, axis=1)
    return {
        "board_surface_to_camera": {"rotation": R.tolist(), "translation_mm": t_board.tolist()},
        "table_to_camera_nominal": {"rotation": R.tolist(), "translation_mm": t_table.tolist()},
        "rms_reprojection_px": float(np.sqrt(np.mean(error ** 2))),
        "max_reprojection_px": float(error.max()),
        "corner_pixel_uv": uv.tolist(),
        "corner_table_xyz_mm": (xyz + [0, 0, surface_height_mm]).tolist(),
        "metric_localization_accepted": False,
    }


def raw_pixel_from_preview(xy, raw_wh, preview_wh):
    """Map a resized pixel centre back to the original, without rotating the image."""
    return [min(raw_wh[i] - 1., max(0., (float(xy[i]) + .5) * raw_wh[i] / preview_wh[i] - .5))
            for i in (0, 1)]


def measure_ruler(geometry, points_uv, plane_height_mm, expected_mm):
    uv = np.asarray(points_uv, dtype=float)
    if uv.shape != (2, 2) or not np.isfinite(uv).all():
        raise ValueError("Select exactly two finite endpoints")
    if not math.isfinite(expected_mm) or expected_mm <= 0:
        raise ValueError("Expected length must be positive")
    if not math.isfinite(plane_height_mm) or plane_height_mm < 0:
        raise ValueError("Ruler scale surface height must be nonnegative")
    if np.linalg.norm(uv[1] - uv[0]) < 1:
        raise ValueError("Ruler endpoints coincide")
    xyz = np.array([geometry.project(p, plane_height_mm) for p in uv])
    measured = float(np.linalg.norm(xyz[1] - xyz[0]))
    return {
        "schema": "gesture.ai_pc.rgb_ruler_check.v1", "status": "RECORDED_PENDING_REVIEW",
        "table_frame_id": geometry.table["table_frame_id"],
        "pixel_uv": uv.tolist(), "table_xyz_mm": xyz.tolist(),
        "assumed_scale_surface_height_mm": float(plane_height_mm),
        "height_source": "USER_SUPPLIED_NOT_DEPTH_MEASURED",
        "expected_length_mm": float(expected_mm), "measured_length_mm": measured,
        "signed_error_mm": measured - expected_mm,
        "relative_error_percent": 100 * (measured - expected_mm) / expected_mm,
        "reference_type": "USER_SELECTED_INDEPENDENT_RULER_MARKS_NOT_FIT_GRID",
        "independent_reference_verified_by_program": False,
        "metric_localization_accepted": False, "physical_execution": False,
        "robot_base_xyz_mm": None,
    }
