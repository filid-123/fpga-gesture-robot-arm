"""Saved vision-to-motion integration for PC simulation, never a live observation.

Keep this separate from perception_input's production NPU/ROCm/freshness gate.
The millimetre diagnostic is provisional, even when every source hash matches.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

from .planner import validate_request

TASKS = {1: "red_cube", 2: "eraser", 3: "small_canister"}
WORKSPACE = "config/ai_pc/rgb_workspace_20261027_desktop_candidate.json"
PROFILE = "config/ai_pc/mode_b_six_objects_v1.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def checked(root, relative, expected):
    path = Path(relative)
    path = (path if path.is_absolute() else root/path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Source must stay within the project")
    if not isinstance(expected, str) or sha(path) != expected:
        raise ValueError("Source hash mismatch: "+str(relative))
    return path


def saved_scene(root, metric_path, frame_index=0):
    """Bind one saved metric frame to its raw image, observation and geometry."""
    root, metric_path = Path(root).resolve(), Path(metric_path).resolve()
    report = read(metric_path)
    if (report.get("schema") != "gesture.ai_pc.saved_top_metric_diagnostic.v1"
            or report.get("offline_snapshot") is not True
            or report.get("physical_execution") is not False
            or report.get("metric_localization_accepted") is not False):
        raise ValueError("An explicitly offline, unaccepted saved metric diagnostic is required")
    capture_path = checked(root, report["source_capture"], report["capture_sha256"])
    workspace_path = checked(root, WORKSPACE, report["workspace_sha256"])
    profile_path = checked(root, PROFILE, report["profile_sha256_file"])
    workspace, profile, capture = read(workspace_path), read(profile_path), read(capture_path)
    if profile.get("profile_id") != "mode_b_red_eraser_canister_v1":
        raise ValueError("Wrong Mode B profile")
    if profile.get("task_mapping") != {str(k): v for k, v in TASKS.items()}:
        raise ValueError("Mode A/B task mapping conflict")
    if capture.get("status") != "COMPLETED" or capture.get("used_for_training") is not False:
        raise ValueError("Completed excluded check capture required")
    if (type(frame_index) is not int or frame_index < 0
            or frame_index >= len(report["records"]) or frame_index >= len(capture["frames"])):
        raise ValueError("Saved frame index out of range")
    table_path = checked(root, workspace["table_file"], report["table_sha256"])
    table = read(table_path)
    if (workspace["table_sha256"] != report["table_sha256"]
            or table.get("table_frame_id") != "desk_global_mm"):
        raise ValueError("Global desktop coordinate frame required")
    registration_path = checked(root, table["desktop_registration_file"], report["registration_sha256"])
    if table["desktop_registration_sha256"] != report["registration_sha256"]:
        raise ValueError("Registration binding mismatch")
    intrinsics_path = checked(root, table["intrinsics_file"], table["intrinsics_sha256"])
    entry, source = report["records"][frame_index], capture["frames"][frame_index]
    if entry["image"] != source["image"] or entry["image_sha256"] != source["image_sha256"]:
        raise ValueError("Metric record and raw frame differ")
    image_path = checked(root, source["image"], source["image_sha256"])
    observation_path = checked(root, Path(report["source_observations"])/f"{frame_index:02d}_observation.json",
                               entry["observation_sha256"])
    observation = read(observation_path)
    canonical_profile = hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if (observation.get("schema") != "gesture.ai_pc.mode_b_observation.v1"
            or observation.get("profile_id") != profile["profile_id"]
            or observation.get("profile_sha256") != canonical_profile
            or observation.get("frame_index") != frame_index
            or observation.get("frame_sha256") != source["pixel_sha256"]):
        raise ValueError("Saved observation/frame/profile binding mismatch")
    targets = {}
    for task_id, name in TASKS.items():
        rows = [r for r in entry["targets"] if r.get("class_name") == name]
        neural = [r for r in observation.get("localizations", []) if r.get("class_name") == name]
        if (len(rows) != 1 or rows[0].get("task_id") != task_id or len(neural) != 1
                or neural[0].get("instances") != 1 or not neural[0].get("pixel_surface")
                or rows[0].get("same_runtime_shape_dimension_gate_would_pass") is not True
                or rows[0].get("projected_top_inside_workspace") is not True
                or rows[0].get("diagnostic_status") != "PROJECTED_SAVED_PIXELS_ONLY"):
            raise ValueError("Unique in-workspace saved neural top required: "+name)
        row = deepcopy(rows[0])
        point = row["centre_desktop_xyz_mm"]
        if (len(point) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in point)
                or point[2] != row["assumed_top_height_mm"]):
            raise ValueError("Invalid top-centre coordinates")
        targets[name] = row
    unknown = [r["class_name"] for r in observation.get("recognitions", [])
               if r.get("class_name") not in TASKS.values()]
    return {"schema": "gesture.mode_b.pc_saved_scene.v1", "offline_snapshot": True,
            "physical_execution_allowed": False, "fresh_for_hardware": False,
            "metric_localization_accepted": False, "npu_acceptance": "NOT_RUN", "rocm_acceptance": "NOT_RUN",
            "source_role": "OLD_SAVED_SCENE_CANDIDATE_NOT_CURRENT_ROBOT_TARGET",
            "frame_index": frame_index, "received_utc": source["received_utc"],
            "metric_report_sha256": sha(metric_path), "targets": targets,
            "unmodelled_recognized_objects": unknown,
            "environment_completely_modelled": not bool(unknown),
            "files_sha256": {str(p.relative_to(root)): sha(p) for p in
                (capture_path, workspace_path, profile_path, table_path, registration_path,
                 intrinsics_path, image_path, observation_path)},
            "frame_pixel_sha256": source["pixel_sha256"]}


def scene_request(scene, object_id, destination, config, *, task_id):
    if (scene.get("schema") != "gesture.mode_b.pc_saved_scene.v1"
            or scene.get("offline_snapshot") is not True
            or scene.get("physical_execution_allowed") is not False):
        raise ValueError("Explicit saved simulation scene required")
    if type(object_id) is not int or object_id not in TASKS:
        raise ValueError("Mode B task ID must be integer 1/2/3")
    name = TASKS[object_id]
    obstacles, pickup = [], None
    for other, row in scene["targets"].items():
        size = config["objects"][other]["size_mm"]
        if abs(row["assumed_top_height_mm"]-size[2]) > 1e-6:
            raise ValueError("Object height differs between perception and motion")
        top = list(row["centre_desktop_xyz_mm"])
        centre = [top[0], top[1], top[2]-size[2]/2]
        yaw = 0. if other == "small_canister" else row.get("long_axis_yaw_mod180_deg")
        if type(yaw) not in (int, float) or not math.isfinite(yaw):
            raise ValueError("Object long-axis yaw required")
        if other == name:
            pickup = {"centre_mm": centre, "yaw_deg": yaw}
            continue
        # World currently accepts axis-aligned obstacles. Enclose each rotated
        # physical footprint; do not pretend other visible targets disappeared.
        c, s = abs(math.cos(math.radians(yaw))), abs(math.sin(math.radians(yaw)))
        obstacles.append({"id": "stationary_"+other, "centre_mm": centre,
                          "size_mm": [c*size[0]+s*size[1], s*size[0]+c*size[1], size[2]]})
    if pickup is None:
        raise ValueError("Selected target missing")
    request = {"schema": "gesture.mode_b.motion_request.v1", "frame": "desk_global_mm",
               "task_id": task_id, "object_class": name, "pickup": pickup,
               "destination": deepcopy(destination), "obstacles": obstacles,
               "pc_trial_source": {"role": scene["source_role"], "frame_index": scene["frame_index"],
                   "metric_report_sha256": scene["metric_report_sha256"],
                   "frame_pixel_sha256": scene["frame_pixel_sha256"],
                   "unmodelled_recognized_objects": scene["unmodelled_recognized_objects"],
                   "independent_task_from_original_scene_not_three_sequential_picks": True,
                   "metric_accepted": False, "physical_execution_allowed": False}}
    return validate_request(request, config)
