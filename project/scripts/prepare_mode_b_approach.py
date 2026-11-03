"""Prepare an empty-gripper commissioning approach, never a full-task deployment.

The first five API angles use the nominal CAD convention, still awaiting physical
alignment validation. Firmware hand feedback is held verbatim; URDF hand angles
are never sent. A synchronized native T102 stream connects HOME directly to the
high approach, without an elbow-only or horizontal-posture waypoint.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pc.mode_b.motion.collision import World
from pc.mode_b.motion.export import load_package
from pc.mode_b.motion.kinematics import Robot
from pc.mode_b.motion.trajectory import build_segment, dequantize
from pc.roarm_reference_kinematics import ReferenceGeometry, forward

NAMES = ("b", "s", "e", "t", "r", "g")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(task_path, capture_path):
    task_path, capture_path = Path(task_path), Path(capture_path)
    plan, config = load_package(task_path)
    verification_path = task_path.parent / "coppelia_verification.json"
    verification = read(verification_path)
    if not verification.get("passed") or verification.get("plan_sha256") != plan["plan_sha256"]:
        raise ValueError("Matching complete-task simulation required")
    if plan["object_class"] != "red_cube" or plan["segments"][0]["phase"] != "PREGRASP":
        raise ValueError("Only the empty red-cube PREGRASP commissioning entry is supported")
    profile_path = ROOT / "config/ai_pc/robot_home_current.json"
    home = read(profile_path)
    if not home.get("physical_pose_operator_accepted") or home["home_id"] != config["home_revision"]:
        raise ValueError("Accepted current low HOME required")
    reference = read(ROOT / "config/ai_pc/roarm_reference_geometry.json")
    geometry = ReferenceGeometry(**reference["geometry_mm"])
    capture = read(capture_path)
    samples = capture.get("samples", [])
    if capture.get("observation_status") != "CAPTURE_COMPLETE_NOT_VALIDATED" or len(samples) != 5:
        raise ValueError("Five complete current feedback states required")
    start = np.array([samples[-1]["joint_rad"][n] for n in NAMES], dtype=float)
    if not np.isfinite(start).all() or not 3.0 <= start[5] <= math.pi:
        raise ValueError("Finite near-closed empty-gripper start required")
    for i, name in enumerate(NAMES):
        tolerance = home["arrival_tolerance_deg"][name]
        if abs(math.degrees(start[i] - home["firmware_joint_rad"][name])) > tolerance:
            raise ValueError(f"Not at the accepted low HOME: {name}")
    for sample in samples:
        q = np.array([sample["joint_rad"][n] for n in NAMES], dtype=float)
        if not np.isfinite(q).all() or np.max(np.abs(np.degrees(q-start))) > .5:
            raise ValueError("Stable finite feedback required")
        feedback = sample["feedback"]
        if any(feedback.get(n) for n in ("Stalltor", "Stalltep", "Stallvol")):
            raise ValueError("Firmware reports a fault")
        for n in ("torswitchB", "torswitchS", "torswitchE", "torswitchT", "torswitchR", "torswitchG"):
            if n in feedback and feedback[n] != 1:
                raise ValueError("A joint torque switch is off")
        if math.dist(forward(q[:4], geometry)[:3], [feedback[n] for n in ("x", "y", "z")]) > 1:
            raise ValueError("Feedback does not match reference firmware FK")
    if np.max(np.abs(np.array(config["home_rad"][:5]) -
                     [home["firmware_joint_rad"][n] for n in NAMES[:5]])) > 1e-6:
        raise ValueError("Simulation HOME no longer uses the reviewed nominal arm convention")

    target = np.array(plan["milestones"]["PREGRASP"]["q_rad"], dtype=float)
    target[5] = start[5]
    robot = Robot(ROOT, config, grasp_width_mm=30)
    scene = deepcopy(plan["request"])
    yaw = math.radians(scene["pickup"]["yaw_deg"])
    size_xy = (abs(math.sin(yaw)) + abs(math.cos(yaw))) * 30
    scene.setdefault("obstacles", []).append({"id": "stationary_red_cube",
        "centre_mm": scene["pickup"]["centre_mm"], "size_mm": [size_xy, size_xy, 30]})
    world = World(robot, scene, config)
    native_config = deepcopy(config)
    native_config["vmax_rad_s"] = [min(v, math.radians(12)) for v in config["vmax_rad_s"]]
    native_config["amax_rad_s2"] = [min(a, math.radians(24)) for a in config["amax_rad_s2"]]
    segment, rows = build_segment(np.r_[start[:5], 0.], np.r_[target[:5], 0.], native_config)
    minimum, count, frames = float("inf"), 0, []
    for index, row in enumerate(rows):
        nominal = dequantize(row)
        checks = [nominal]
        if index % 10 == 0 or index == len(rows)-1:
            # Check following-error corners along the common progress path;
            # arbitrary full-range independent progress is no longer commanded.
            allowances = np.r_[[math.radians(home["arrival_tolerance_deg"][n]) for n in NAMES[:5]], 0.]
            for signs in itertools.product((-1, 1), repeat=5):
                checks.append(np.clip(nominal + np.r_[signs, 0.]*allowances,
                                      robot.limits[:, 0], robot.limits[:, 1]))
        for model_q in checks:
            robot.check_q(model_q)
            world.check(model_q)
            boxes = world.link_boxes(model_q)
            minimum = min(minimum, *(float(boxes[n].corners[:, 2].min()) for n in ("link5", "gripper_link")))
            count += 1
        command = {"T": 102, **dict(zip(("base", "shoulder", "elbow", "wrist", "roll"), nominal[:5].tolist())),
                   "hand": float(start[5]), "spd": 160, "acc": 5}
        frames.append({"wire_json": json.dumps(command, separators=(",", ":")),
                       "command_firmware_rad": dict(zip(NAMES, [*nominal[:5], start[5]]))})
    if minimum < 30:
        raise ValueError("Direct entrance leaves insufficient nominal finger clearance")
    stages = [{"label": "DIRECT_HOME_TO_RED_HIGH", "stream_frames": frames,
               "period_s": config["period_s"], "segment": segment,
               "nominal_motion_seconds": len(rows)*config["period_s"],
               "target_firmware_rad": dict(zip(NAMES, target.tolist())),
               "checked_path_and_error_samples": count,
               "nominal_minimum_finger_clearance_mm": minimum}]
    final_model = np.r_[target[:5], 0.]
    return {"schema": "gesture.mode_b.empty_approach_commissioning.v1",
            "scope": "EMPTY_APPROACH_ONLY_NO_OPEN_DESCENT_GRASP_TRANSPORT_OR_RELEASE",
            "task_file": str(task_path.resolve()), "task_sha256": digest(task_path),
            "capture_file": str(capture_path.resolve()), "capture_sha256": digest(capture_path),
            "capture_time_utc": capture["captured_at_utc"],
            "home_profile_sha256": digest(profile_path), "start_firmware_rad": dict(zip(NAMES, start.tolist())),
            "arm_mapping": "NOMINAL_IDENTITY_FIRST_FIVE; NATIVE_T102_RAD_STREAM",
            "hand_mapping": "NO_WIDTH_MAPPING; CURRENT_FIRMWARE_g_HELD_AS_T102_hand_RAD",
            "physical_general_mapping_calibrated": False, "full_task_deployable": False,
            "nominal_target_grasp_table_mm": robot.fk(final_model)[:3, 3].tolist(),
            "native_route_differs_from_synchronized_simulation": "SAME_JOINT_LINE; LOWER_COMMISSIONING_SPEED_AND_STRETCHABLE_HTTP_TIMING",
            "native_route_check": "SYNCHRONIZED_SAMPLES_AND_FOLLOWING_ERROR_CORNERS_NOT_CONTINUOUS_PROOF",
            "scheduler_policy": "STRETCH_TIMING_ON_HOST_DELAY; NEVER_BURST_OR_SKIP_SAMPLES",
            "horizontal_or_elbow_only_waypoint": False,
            "arrival_tolerance_deg": home["arrival_tolerance_deg"], "stages": stages}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.task, args.capture)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf8")
    print(json.dumps({"stages": len(result["stages"]), "target_table_mm": result["nominal_target_grasp_table_mm"],
                      "nominal_minimum_clearances_mm": [s["nominal_minimum_finger_clearance_mm"] for s in result["stages"]]}))
