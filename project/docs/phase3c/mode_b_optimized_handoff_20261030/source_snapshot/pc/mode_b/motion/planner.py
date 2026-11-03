"""Full Mode B tasks, distinct from the legacy HOME-to-PRE_DELIVERY contract.

All results are nominal simulation candidates. No network/serial execution is
provided. Neither model IK nor simulated feedback grants hardware permission.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

from .collision import Box, CollisionError, World, separating_gap
from .kinematics import IKError, Robot, transform, vector
from .trajectory import build_segment, dequantize, quantize, sample_digest


class PlanningError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                      allow_nan=False).encode()).hexdigest()


def plan_digest(plan):
    document = deepcopy(plan)
    document.pop("plan_sha256", None)
    document.pop("sample_rows", None)
    for branch in document["cancel_branches"].values():
        branch.pop("sample_rows", None)
    return digest(document)


def validate_request(request, config):
    r = deepcopy(request)
    if r.get("schema") != "gesture.mode_b.motion_request.v1" or r.get("frame") != "desk_global_mm":
        raise PlanningError("Explicit Mode B request and desk_global_mm frame required")
    if r.get("object_class") not in config["objects"]:
        raise PlanningError("Only red_cube, eraser, small_canister are grasp targets")
    if not isinstance(r.get("task_id"), str) or not r["task_id"]:
        raise PlanningError("Non-empty unique task_id required")
    obj = config["objects"][r["object_class"]]
    pickup = vector(r["pickup"]["centre_mm"], 3, "object centre")
    yaw = r["pickup"].get("yaw_deg")
    if type(yaw) not in (float, int) or not math.isfinite(yaw):
        raise PlanningError("Finite object yaw required, including simulation inputs")
    size = np.array(obj["size_mm"])
    rotation = transform(rpy=[0, 0, math.radians(yaw)])[:2, :2]
    half_xy = np.abs(rotation) @ (size[:2]/2)
    bounds = config["pickup_bounds_xy_mm"]
    if (np.any(pickup[:2]-half_xy < np.array(bounds)[[0, 2]]) or
        np.any(pickup[:2]+half_xy > np.array(bounds)[[1, 3]]) or pickup[2] < size[2]/2-1e-6):
        raise PlanningError("Object footprint or support height outside pickup region")
    destination = r["destination"]
    centre = vector(destination["support_centre_mm"], 3, "support centre")
    support_size = vector(destination["size_xy_mm"], 2, "support size")
    if np.any(support_size <= 0) or np.any(support_size/2 < half_xy+config["collision_margin_mm"]):
        raise PlanningError("Insufficient support area for the object and clearance")
    table = np.array(config["table_bounds_xy_mm"])
    if (centre[2] < 0 or np.any(centre[:2]-support_size/2 < table[[0, 2]]) or
        np.any(centre[:2]+support_size/2 > table[[1, 3]])):
        raise PlanningError("Support lies outside desk bounds")
    rim = destination.get("rim_height_mm", 0)
    if type(rim) not in (float, int) or not math.isfinite(rim) or rim != 0:
        raise PlanningError("First version requires an explicitly rim-free flat support")
    for obstacle in r.get("obstacles", []):
        if not isinstance(obstacle.get("id"), str) or not obstacle["id"]:
            raise PlanningError("Obstacle requires an id")
        vector(obstacle["centre_mm"], 3, "obstacle centre")
        if np.any(vector(obstacle["size_mm"], 3, "obstacle size") <= 0):
            raise PlanningError("Obstacle requires positive known dimensions")
        obstacle_box = Box(obstacle["id"], np.array(obstacle["centre_mm"], dtype=float), np.eye(3),
                           np.array(obstacle["size_mm"], dtype=float)/2)
        for role, position in (("SOURCE", pickup), ("DESTINATION", np.r_[centre[:2], centre[2]+size[2]/2+2.5])):
            object_box = Box.local(role, transform(position, [0, 0, math.radians(yaw)]), -size/2, size/2)
            if separating_gap(object_box, obstacle_box) < config["collision_margin_mm"]:
                raise PlanningError(role+"_FOOTPRINT_OCCUPIED_OR_OCCLUDED")
    return r


class Planner:
    def __init__(self, root: Path, config: dict):
        self.root, self.config = root, deepcopy(config)
        if config.get("physical_execution_allowed") is not False:
            raise PlanningError("This planner is a simulation candidate, not a deployment adapter")
        if config["deployment"].get("npu_required") is not True:
            raise PlanningError("NPU is mandatory in Mode B")
        if config["deployment"].get("rocm_surface_required") is not True:
            raise PlanningError("ROCm surface inference is mandatory in Mode B")
        for name in ("vmax_rad_s", "amax_rad_s2"):
            if np.any(vector(config[name], 6, name) <= 0):
                raise PlanningError("Positive six-channel motion limits required")
        if not 0 < config["period_s"] <= 1 or config["clock_hz"] <= 0:
            raise PlanningError("Invalid nominal control period/clock")
        for name in ("grasp_tilt_deg", "transit_tilt_deg", "place_tilt_deg"):
            if not math.isfinite(config[name]) or not 0 <= config[name] <= 30:
                raise PlanningError("Invalid allowable tilt cone")
        phase_limits = config.get("phase_tilt_limits_deg", {})
        if not isinstance(phase_limits, dict):
            raise PlanningError("Phase tilt limits must be a mapping")
        for phase, limit in phase_limits.items():
            if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not math.isfinite(limit) or not 0 <= limit <= 30:
                raise PlanningError(f"Invalid phase tilt limit: {phase}")
        if any(phase not in phase_limits for phase in config.get("strict_vertical_phases", [])):
            raise PlanningError("Every strict vertical phase needs an explicit tilt limit")
        self.robot = Robot(root, config)

    def plan(self, request):
        started = time.perf_counter()
        request = validate_request(request, self.config)
        obj = self.config["objects"][request["object_class"]]
        width = obj["size_mm"][1] if request["object_class"] == "eraser" else obj["size_mm"][0]
        self.robot = Robot(self.root, self.config, grasp_width_mm=width)
        yaw = math.radians(request["pickup"]["yaw_deg"])
        if obj["shape"] == "cylinder":
            yaws = [0, math.pi/2, math.pi/4, -math.pi/4]
        elif request["object_class"] == "eraser":
            yaws = [yaw+math.pi/2, yaw-math.pi/2]
        else:
            yaws = [yaw+k*math.pi/2 for k in range(4)]
        failures = []
        for closing_yaw in yaws:
            # Reject an unreachable final placement before searching transport
            # heights: a higher transit cannot make an invalid support reachable.
            destination = np.array(request["destination"]["support_centre_mm"], dtype=float)
            destination[2] += obj["size_mm"][2]/2+self.config["collision_margin_mm"]+.5
            try:
                self.robot.solve(destination, closing_yaw, self.config["home_rad"],
                                 max_tilt_deg=self.config["place_tilt_deg"])
            except IKError as exc:
                failures.append({"yaw_rad": closing_yaw, "reason": "DESTINATION:"+str(exc)})
                continue
            for bottom in self.config["transport_bottom_candidates_mm"]:
                if bottom <= request["destination"]["support_centre_mm"][2]+25:
                    continue
                for buffer_xy in self.config["buffer_candidates_xy_mm"]:
                    try:
                        result = self._candidate(request, obj, closing_yaw, bottom, buffer_xy)
                        result["planning_ms"] = (time.perf_counter()-started)*1000
                        result["search"] = {"attempts": len(failures)+1, "rejected_candidates": failures}
                        result["plan_sha256"] = plan_digest(result)
                        return result
                    except (IKError, CollisionError, PlanningError) as exc:
                        failures.append({"yaw_rad": closing_yaw, "transport_bottom_mm": bottom,
                                         "buffer_xy_mm": buffer_xy, "reason": str(exc)})
                        # A grasp pose is independent of buffer/transport candidates.
                        if str(exc).startswith(("GRASP:", "SOURCE:")):
                            break
                if failures and failures[-1]["reason"].startswith(("GRASP:", "SOURCE:")):
                    break
        raise PlanningError("NO_VALID_COMPLETE_TASK: "+json.dumps(failures[-8:], ensure_ascii=False))

    def _candidate(self, request, obj, closing_yaw, bottom, buffer_xy):
        c, robot = self.config, self.robot
        world = World(robot, request, c)
        home = np.array(c["home_rad"], dtype=float)
        robot.check_q(home)
        world.check(home)
        size = np.array(obj["size_mm"], dtype=float)
        pickup = np.array(request["pickup"]["centre_mm"], dtype=float)
        destination = np.array(request["destination"]["support_centre_mm"], dtype=float)
        destination[2] += size[2]/2 + c["collision_margin_mm"]+.5
        height = bottom+size[2]/2
        half_xy = np.abs(transform(rpy=[0, 0, math.radians(request["pickup"]["yaw_deg"])])[:2, :2]) @ (size[:2]/2)
        bb = np.array(c["buffer_bounds_xy_mm"])
        if (np.any(np.array(buffer_xy)-half_xy-c["collision_margin_mm"] < bb[[0, 2]]) or
            np.any(np.array(buffer_xy)+half_xy+c["collision_margin_mm"] > bb[[1, 3]])):
            raise PlanningError("Buffer object footprint exceeds holding region")
        if height < max(pickup[2], destination[2])+25:
            raise PlanningError("Transport height leaves no approach clearance")
        width = size[1] if request["object_class"] == "eraser" else size[0]
        g = c["gripper"]
        if width+g["opening_margin_mm"] > g["max_opening_mm"]:
            raise PlanningError("GRASP:Object exceeds nominal gripper opening")
        opened = (width+g["opening_margin_mm"])/g["max_opening_mm"]*g["max_angle_rad"]
        closed = max(0., width-g["compression_mm"])/g["max_opening_mm"]*g["max_angle_rad"]
        current = home.copy()
        segments, rows, milestones = [], [], {}
        carrying = False
        attachment = None
        stationary_object_frame = transform(pickup, [0, 0, math.radians(request["pickup"]["yaw_deg"])])
        stationary_on_destination = False
        stats = {"minimum_sat_separation_or_table_height_mm": float("inf"),
                 "max_cartesian_chord_error_mm": 0., "checked_samples": 0}

        def append(q, phase, *, event=None, contact=False, line=None, speed=1.):
            nonlocal current
            robot.check_q(q)
            segment, samples = build_segment(current, q, c, speed_scale=speed)
            if line is not None and np.max(np.abs(np.array(q[:5])-current[:5])) > c["max_joint_step_rad"]:
                raise PlanningError(f"IK_BRANCH_JUMP:{phase}")
            for sample in samples:
                actual = dequantize(sample)
                if phase in c.get("strict_vertical_phases", []):
                    limit = c["phase_tilt_limits_deg"][phase]
                    tilt = math.degrees(math.acos(float(np.clip(-robot.fk(actual)[2, 2], -1, 1))))
                    if tilt > limit+.1:
                        raise PlanningError(f"VERTICAL_PHASE:{phase}:{tilt:.3f}deg")
                # The known object remains an obstacle before acquisition and
                # after release. Only its declared finger contact links are
                # excluded by the OBB layer; Coppelia checks finger meshes
                # separately during approach and withdrawal.
                checked_payload = attachment if carrying else {
                    "size_mm": size.tolist(),
                    "grasp_from_object": np.linalg.inv(robot.fk(actual)) @ stationary_object_frame}
                clearance = world.check(actual, payload=checked_payload,
                    payload_support_contact=contact or (not carrying and stationary_on_destination))
                stats["minimum_sat_separation_or_table_height_mm"] = min(
                    stats["minimum_sat_separation_or_table_height_mm"], clearance)
                stats["checked_samples"] += 1
                if line is not None:
                    a, b = line
                    p = robot.fk(actual)[:3, 3]
                    delta = b-a
                    t = np.clip(np.dot(p-a, delta)/max(np.dot(delta, delta), 1e-12), 0, 1)
                    error = float(np.linalg.norm(p-(a+t*delta)))
                    stats["max_cartesian_chord_error_mm"] = max(stats["max_cartesian_chord_error_mm"], error)
                    if error > c["cartesian_chord_tolerance_mm"]:
                        raise PlanningError(f"CARTESIAN_CHORD:{phase}:{error:.3f}mm")
            segment.update(start_q16=list(quantize(current)), phase=phase,
                           payload_attached=carrying, payload_support_contact=contact,
                           event_after=event, sample_offset=len(rows), sample_sha256=sample_digest(samples),
                           cartesian_line_mm=None if line is None else [line[0].tolist(), line[1].tolist()])
            rows.extend(samples)
            segments.append(segment)
            current = dequantize(segment["target_q16"])
            milestones[phase] = {"segment_index": len(segments)-1, "sample_index": len(rows)-1,
                                  "q_rad": current.tolist(), "grasp_xyz_mm": robot.fk(current)[:3, 3].tolist()}

        def phase_tilt(phase):
            # Optional policy keeps existing frozen task configurations intact.
            explicit = c.get("phase_tilt_limits_deg", {})
            if phase in explicit:
                return float(explicit[phase])
            return (c["place_tilt_deg"] if phase in ("PLACE", "RETREAT") else
                    c["transit_tilt_deg"] if phase in ("BUFFER", "PREPLACE") else c["grasp_tilt_deg"])

        def solve(point, phase, tilt=None, *, continuous=False):
            try:
                return np.array(robot.solve(point, closing_yaw, current,
                    max_tilt_deg=tilt if tilt is not None else phase_tilt(phase),
                    extra_seeds=True, max_joint_delta_rad=c["max_joint_step_rad"] if continuous else None).q)
            except IKError as exc:
                raise IKError(("GRASP:" if phase == "DESCEND" else phase+":")+str(exc)) from exc

        def cartesian(point, phase, *, contact=False, event=None):
            start = robot.fk(current)[:3, 3]
            count = max(1, int(math.ceil(np.linalg.norm(np.array(point)-start)/c["cartesian_step_mm"])))
            def reach(target, final, depth=0):
                previous = robot.fk(current)[:3, 3]
                before_stats = deepcopy(stats)
                if phase == "PLACE":
                    # Tighten the tilt cone over the final 40 mm, rather than
                    # switching abruptly from transit to placement at one point.
                    remaining = float(np.linalg.norm(np.array(point)-target))
                    # Reserve 0.5 mm for quantisation/IK chord effects. A long
                    # object can strike the support with a corner even while
                    # its centre is at the correct nominal release height.
                    radial_half = float(np.linalg.norm(size[:2])/2)
                    angular_clearance = math.degrees(math.asin(min(1., max(0.,
                        c["collision_margin_mm"]/radial_half))))
                    final_tilt = min(c["place_tilt_deg"], angular_clearance)
                    tilt = final_tilt+(c["transit_tilt_deg"]-final_tilt)*min(1., remaining/40.)
                else:
                    tilt = phase_tilt(phase) if phase in c.get("phase_tilt_limits_deg", {}) else (
                        c["transit_tilt_deg"] if phase == "RETREAT" else None)
                try:
                    q = solve(target, phase, tilt, continuous=True)
                    append(q, phase, contact=contact, event=event if final else None, line=(previous, target))
                except (IKError, PlanningError) as exc:
                    stats.clear()
                    stats.update(before_stats)
                    # Failed append has not emitted a segment. Subdivide the
                    # Cartesian interval; retain all joint/chord/collision limits.
                    if depth >= 4 or np.linalg.norm(target-previous) <= 1.:
                        raise
                    if not isinstance(exc, IKError) and not str(exc).startswith(("IK_BRANCH_JUMP:", "CARTESIAN_CHORD:")):
                        raise
                    reach((previous+target)/2, False, depth+1)
                    reach(target, final, depth+1)
            for index in range(1, count+1):
                target = start+(np.array(point)-start)*index/count
                reach(target, index == count)

        def transit(point, phase, event=None):
            """Try a direct swept-checked edge, then bounded obstacle-corner detours.

            This is a finite waypoint search, not a completeness/optimality claim.
            Every alternative still undergoes the same full-arm sample checks.
            """
            nonlocal current, stats, milestones
            before = (current.copy(), len(segments), len(rows), deepcopy(stats), deepcopy(milestones))
            def restore():
                nonlocal current, stats, milestones
                current = before[0].copy()
                del segments[before[1]:]
                del rows[before[2]:]
                stats, milestones = deepcopy(before[3]), deepcopy(before[4])
            options = [[]]
            radius = float(np.linalg.norm(size[:2])/2+35+c["collision_margin_mm"])
            for obstacle in world.obstacles:
                for sx, sy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                    xy = obstacle.centre[:2]+np.array([sx, sy])*(obstacle.half[:2]+radius)
                    options.append([np.r_[xy, point[2]]])
            last_error = None
            for via in options:
                restore()
                try:
                    for p in via:
                        append(solve(p, "BUFFER"), "TRANSIT_"+phase)
                    append(solve(point, phase), phase, event=event)
                    return
                except (IKError, CollisionError, PlanningError) as exc:
                    last_error = exc
            restore()
            raise PlanningError(f"NO_CHECKED_TRANSIT:{phase}:{last_error}")

        # High pre-grasp is solved before any descent; all emitted joint samples
        # of this orientation-changing connector are checked against the world.
        append(solve(np.r_[pickup[:2], height], "PREGRASP"), "PREGRASP")
        if c.get("align_grasp_at_high_point", False):
            # The empty connector may tilt. Finish aligning at clearance height,
            # before opening/descent, so lifting can preserve the grasp pose.
            append(solve(np.r_[pickup[:2], height], "GRASP_ALIGN", c["grasp_tilt_deg"]), "GRASP_ALIGN")
        q = current.copy(); q[5] = opened
        append(q, "OPEN")
        cartesian(pickup, "DESCEND")
        q = current.copy(); q[5] = closed
        append(q, "GRASP", event="GRASP_VERIFIED", speed=.65)
        object_frame = transform(pickup, [0, 0, math.radians(request["pickup"]["yaw_deg"])])
        attachment = {"size_mm": size.tolist(),
                      "grasp_from_object": (np.linalg.inv(robot.fk(current)) @ object_frame).tolist()}
        carrying = True
        world.check(current, payload=attachment)
        cartesian(np.r_[pickup[:2], height], "LIFT")
        transit(np.r_[buffer_xy, height], "BUFFER", event="PALM_READY")
        transit(np.r_[destination[:2], height], "PREPLACE")
        cartesian(destination, "PLACE", contact=True, event="SUPPORT_VERIFIED")
        q = current.copy(); q[5] = opened
        append(q, "RELEASE", contact=True)
        stationary_object_frame = robot.fk(current) @ np.asarray(attachment["grasp_from_object"])
        stationary_on_destination = True
        carrying = False
        cartesian(np.r_[destination[:2], height], "RETREAT", contact=True)
        append(home, "RETURN_HOME")

        # Cancellation branches are planned from stationary, checked phase
        # boundaries. A cancel in mid-segment first holds; no blind reversal.
        normal_segments = deepcopy(segments)
        normal_rows = list(rows)
        normal_stats = deepcopy(stats)
        normal_milestones = deepcopy(milestones)
        branches = {}
        for phase in ("LIFT", "BUFFER", "PREPLACE"):
            at = normal_milestones[phase]
            current = np.array(at["q_rad"])
            carrying = True
            segments, rows = [], []
            # Reverse checked high waypoints, then descend to the reserved
            # original pose. Recheck with the payload; source vacancy is an event.
            lift_index = normal_milestones["LIFT"]["segment_index"]
            for index in range(at["segment_index"]-1, lift_index, -1):
                append(dequantize(normal_segments[index]["target_q16"]), "CANCEL_TRANSIT")
            append(normal_milestones["LIFT"]["q_rad"], "CANCEL_APPROACH", event="SOURCE_VACANT")
            cartesian(pickup, "CANCEL_PLACE")
            q = current.copy(); q[5] = opened
            append(q, "CANCEL_RELEASE")
            stationary_object_frame = robot.fk(current) @ np.asarray(attachment["grasp_from_object"])
            stationary_on_destination = False
            carrying = False
            cartesian(np.r_[pickup[:2], height], "CANCEL_RETREAT")
            append(home, "CANCEL_HOME")
            branches[phase] = {"start_q16": list(quantize(at["q_rad"])), "segments": deepcopy(segments),
                "sample_count": len(rows), "sample_sha256": sample_digest(rows),
                "requires": ["KNOWN_PAYLOAD", "VALID_FEEDBACK", "SOURCE_VACANT"],
                "sample_rows": list(rows)}
        normal_stats["cancel_branches_checked_samples"] = stats["checked_samples"]-normal_stats["checked_samples"]
        return {"schema": "gesture.mode_b.complete_task.v1", "task_id": request["task_id"],
            "mode": "B", "object_class": request["object_class"], "gesture_object_id": obj["task_id"],
            "frame": "desk_global_mm", "joint_order": list(robot.config.get("joint_order", ("b", "s", "e", "t", "r", "g"))),
            "joint_space": "URDF_SIMULATION_RAD_NOT_FIRMWARE_RAD", "request": request,
            "config_sha256": digest(c), "urdf_sha256": robot.sha256,
            "grasp_model": {"object_width_mm": robot.grasp_width_mm,
                "link5_from_grasp_mm": robot.grasp.tolist(), "source": c["grasp_centre_model"]["source"],
                "asymmetric_jaw_width_dependency": True, "physical_calibration_verified": False},
            "start_q16": list(quantize(home)), "segments": normal_segments,
            "milestones": normal_milestones, "attachment": attachment,
            "cancel_branches": branches, "sample_rows": normal_rows,
            "sample_count": len(normal_rows), "sample_sha256": sample_digest(normal_rows),
            "period_s": c["period_s"], "nominal_motion_seconds": len(normal_rows)*c["period_s"],
            "transport_object_bottom_mm": bottom, "buffer_xy_mm": list(buffer_xy),
            "gripper": {"open_rad": opened, "closed_rad": closed, "width_mapping_measured": False},
            "verification": normal_stats,
            "execution_semantics": {"mid_segment_cancel": "HOLD_REPLAN_FROM_FRESH_FEEDBACK",
                "source_occupied": "HOLD", "link_loss": "FAULT_HOLD_NO_AUTORETURN",
                "release_requires": ["PALM_READY_VALID", "SUPPORT_VERIFIED"],
                "complete_requires": ["PHYSICAL_PLACEMENT_VERIFIED", "EMPTY_HOME_FEEDBACK"]},
            "deployment": {"physical_execution_allowed": False, "npu_required": True,
                "npu_verified": False, "rocm_verified": False, "calibration_verified": False,
                "fpga_contract": c["deployment"]["fpga_contract"],
                "blockers": ["NPU_ROCM_TARGET_EVIDENCE", "CURRENT_CAMERA_METRIC_CALIBRATION",
                    "DESK_BASE_TOOL_CALIBRATION", "SIM_TO_FIRMWARE_JOINT_MAPPING", "MEASURED_MOTION_LIMITS",
                    "FPGA_COMPLETE_TASK_ADAPTER", "PHYSICAL_GRIP_AND_PLACEMENT_VALIDATION"]}}
