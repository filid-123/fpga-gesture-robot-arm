"""Validated neural observation -> Mode B planning request. No stale-frame reuse."""
from __future__ import annotations
from copy import deepcopy
import math


def request_from_observation(observation, object_id, destination, *, task_id, now_ms,
                             observed_at_ms, max_age_ms=300, obstacles=()):
    if observation.get("schema") != "gesture.ai_pc.mode_b_observation.v1":
        raise ValueError("Mode B neural observation required")
    if observation.get("profile_id") != "mode_b_red_eraser_canister_v1":
        raise ValueError("Wrong task profile")
    if object_id not in (1, 2, 3) or type(object_id) is not int:
        raise ValueError("Mode B object id must be 1,2,3")
    if not all(math.isfinite(t) for t in (now_ms, observed_at_ms, max_age_ms)) or not 0 <= now_ms-observed_at_ms <= max_age_ms:
        raise ValueError("Stale or future perception observation")
    backend = observation.get("backend", {})
    surface = observation.get("surface_backend", {})
    if (backend.get("actual_backend") != "npu" or backend.get("npu_execution_verified") is not True or
        backend.get("cpu_fallback") is not False or observation.get("npu_acceptance") != "ACCEPTED"):
        raise ValueError("Verified NPU execution is mandatory; CPU/CUDA fallback refused")
    if surface.get("device_type") != "rocm_gpu" or observation.get("rocm_acceptance") != "ACCEPTED":
        raise ValueError("Verified ROCm surface inference required")
    if observation.get("metric_localization_accepted") is not True:
        raise ValueError("Current camera metric calibration not accepted")
    rows = [r for r in observation.get("localizations", []) if r.get("task_id") == object_id]
    if len(rows) != 1 or rows[0].get("instances") != 1:
        raise ValueError("Exactly one current target instance required")
    row = rows[0]
    metric = row.get("metric_surface")
    if not metric or metric.get("metric_localization_verified") is not True:
        raise ValueError("Verified millimetre surface localization required")
    centre = list(metric["centre_table_xyz_mm"])
    # Existing perception returns TOP centre; planning uses OBJECT centre.
    heights = {"red_cube": 30, "eraser": 15, "small_canister": 46}
    name = row["class_name"]
    if name != {1: "red_cube", 2: "eraser", 3: "small_canister"}[object_id]:
        raise ValueError("Class/gesture mapping mismatch")
    centre[2] -= heights[name]/2
    yaw = metric.get("long_axis_yaw_mod180_deg")
    if name == "small_canister":
        yaw = 0.
    if yaw is None:
        raise ValueError("Object orientation required")
    return {"schema": "gesture.mode_b.motion_request.v1", "frame": "desk_global_mm", "task_id": task_id,
            "object_class": name, "pickup": {"centre_mm": centre, "yaw_deg": yaw},
            "destination": deepcopy(destination), "obstacles": deepcopy(list(obstacles)),
            "perception_source": {"frame_sha256": observation["frame_sha256"], "observed_at_ms": observed_at_ms,
                                  "profile_sha256": observation["profile_sha256"]}}
