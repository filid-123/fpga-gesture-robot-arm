"""Meaningful regression checks for nominal Mode B planning and execution semantics."""
from __future__ import annotations
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pc.mode_b.motion.collision import Box, CollisionError, World, separating_gap
from pc.mode_b.motion.export import load_package, verify_task, write_package
from pc.mode_b.motion.kinematics import IKError, Robot, transform
from pc.mode_b.motion.perception_input import request_from_observation
from pc.mode_b.motion.planner import Planner, PlanningError, plan_digest, validate_request
from pc.mode_b.motion.state_machine import TaskMachine, simulate_task
from pc.mode_b.motion.trajectory import dequantize, regenerate, sample_digest

CONFIG = json.loads((ROOT/"config/ai_pc/mode_b_motion_nominal_v1.json").read_text())
# The user's current destination is editable and may deliberately be infeasible.
# Keep the known reachable regression scene independent of that input.
REQUEST = json.loads((ROOT/"scripts/fixtures/mode_b_motion_red_request_v1.json").read_text())


class MotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.planner = Planner(ROOT, CONFIG)
        cls.plan = cls.planner.plan(REQUEST)

    def test_fk_ik_roundtrip_random_reachable_downward_poses(self):
        rng = np.random.default_rng(20261027)
        robot = self.planner.robot
        accepted = 0
        for _ in range(45):
            b, s, e = rng.uniform(-.2, 1.1), rng.uniform(.25, 1.1), rng.uniform(.9, 1.7)
            t = math.pi-s-e
            if t >= 1.54:
                continue
            q = np.array([b, s, e, t, b, .8])
            goal = robot.fk(q)[:3, 3]
            result = robot.solve(goal, 0, q, max_tilt_deg=2)
            self.assertLess(result.position_error_mm, .3)
            self.assertLess(result.tilt_deg, 2)
            robot.check_q(result.q)
            accepted += 1
        self.assertGreaterEqual(accepted, 20)

    def test_ik_unreachable_nonfinite_and_joint_limits(self):
        robot = self.planner.robot
        with self.assertRaises(IKError):
            robot.solve([5000, 5000, 5000], 0, CONFIG["home_rad"])
        for xyz in ([math.nan, 1, 2], [1, math.inf, 2]):
            with self.assertRaises(ValueError):
                robot.solve(xyz, 0, CONFIG["home_rad"])
        with self.assertRaises(ValueError):
            robot.check_q([0, 0, 0, 0, 0, 10])

    def test_requests_reject_wrong_frame_unsupported_class_outside_footprint(self):
        for mutate in (lambda r: r.update(frame="robot_base_mm"),
                       lambda r: r.update(object_class="scissors"),
                       lambda r: r["pickup"].update(centre_mm=[490, 215, 15]),
                       lambda r: r["destination"].update(size_xy_mm=[10, 10]),
                       lambda r: r["destination"].update(rim_height_mm=5),
                       lambda r: r["pickup"].update(yaw_deg=math.nan)):
            r = deepcopy(REQUEST); mutate(r)
            with self.assertRaises((PlanningError, ValueError)):
                validate_request(r, CONFIG)

    def test_mode_b_npu_and_rocm_requirements_cannot_be_disabled(self):
        for field in ("npu_required", "rocm_surface_required"):
            c = deepcopy(CONFIG); c["deployment"][field] = False
            with self.assertRaises(PlanningError):
                Planner(ROOT, c)

    def test_complete_task_contains_all_stages_and_returns_home(self):
        required = {"PREGRASP", "OPEN", "DESCEND", "GRASP", "LIFT", "BUFFER", "PREPLACE",
                    "PLACE", "RELEASE", "RETREAT", "RETURN_HOME"}
        self.assertTrue(required <= {s["phase"] for s in self.plan["segments"]})
        self.assertEqual(self.plan["segments"][-1]["target_q16"], self.plan["start_q16"])
        self.assertFalse(self.plan["deployment"]["physical_execution_allowed"])
        self.assertGreater(len(self.plan["segments"]), 32)

    def test_entire_sequence_regenerates_with_pl_exact_hash(self):
        rows = [q for _, values in regenerate(self.plan["start_q16"], self.plan["segments"], CONFIG) for q in values]
        self.assertEqual(len(rows), self.plan["sample_count"])
        self.assertEqual(sample_digest(rows), self.plan["sample_sha256"])
        self.assertEqual(plan_digest(self.plan), self.plan["plan_sha256"])

    def test_velocity_and_acceleration_at_all_segment_boundaries(self):
        rows = np.array([self.plan["start_q16"], self.plan["start_q16"], *self.plan["sample_rows"],
                         self.plan["start_q16"], self.plan["start_q16"]], dtype=float)/65536
        velocity = np.diff(rows, axis=0)/CONFIG["period_s"]
        acceleration = np.diff(velocity, axis=0)/CONFIG["period_s"]
        self.assertTrue(np.all(np.max(np.abs(velocity), axis=0) <= np.array(CONFIG["vmax_rad_s"])+.002))
        self.assertTrue(np.all(np.max(np.abs(acceleration), axis=0) <= np.array(CONFIG["amax_rad_s2"])+.2))

    def test_open_close_do_not_move_arm_joints(self):
        for s in self.plan["segments"]:
            if s["phase"] in ("OPEN", "GRASP", "RELEASE"):
                self.assertEqual(s["start_q16"][:5], s["target_q16"][:5])

    def test_descent_and_lift_respect_vertical_chord_tolerance(self):
        robot = self.planner.robot
        for s, rows in regenerate(self.plan["start_q16"], self.plan["segments"], CONFIG):
            if s["phase"] not in ("DESCEND", "LIFT"):
                continue
            xy = np.array(REQUEST["pickup"]["centre_mm"][:2])
            for row in rows:
                self.assertLess(np.linalg.norm(robot.fk(dequantize(row))[:2, 3]-xy), 1.01)

    def test_eraser_far_delivery_continuity_and_corner_clearance(self):
        request = deepcopy(REQUEST)
        request.update(object_class="eraser", task_id="eraser_continuity_regression")
        request["pickup"]["centre_mm"][2] = 7.5
        request["destination"]["support_centre_mm"] = [260, 160, 30]
        planner = Planner(ROOT, CONFIG)
        plan = planner.plan(request)
        robot = planner.robot
        world = World(robot, request, CONFIG)
        for s, rows in regenerate(plan["start_q16"], plan["segments"], CONFIG):
            if s["cartesian_line_mm"] is not None:
                delta = np.abs(dequantize(s["target_q16"])-dequantize(s["start_q16"]))
                self.assertLessEqual(float(np.max(delta[:5])), CONFIG["max_joint_step_rad"]+2/65536)
            if s["phase"] not in ("PLACE", "RELEASE"):
                continue
            for row in rows:
                actual = dequantize(row)
                box = world.payload_box(actual, plan["attachment"]["size_mm"],
                                        plan["attachment"]["grasp_from_object"])
                self.assertGreaterEqual(float(np.min(box.corners[:, 2])), 30-.15)
        final = plan["milestones"]["PLACE"]["q_rad"]
        tilt = np.degrees(np.arccos(np.clip(-robot.fk(final)[2, 2], -1, 1)))
        self.assertLessEqual(tilt, CONFIG["place_tilt_deg"]+.01)
        self.assertTrue(simulate_task(plan)["complete"])

    def test_ik_continuity_bound_rejects_invalid_arguments(self):
        robot = self.planner.robot
        point = robot.fk(CONFIG["home_rad"])[:3, 3]
        for bound in (0, -1, math.nan, math.inf):
            with self.assertRaisesRegex(ValueError, "continuity"):
                robot.solve(point, 0, CONFIG["home_rad"], max_joint_delta_rad=bound)

    def test_buffer_inside_left_region_and_not_a_release(self):
        x, y = self.plan["buffer_xy_mm"]
        self.assertLess(x, CONFIG["pickup_bounds_xy_mm"][0])
        self.assertTrue(270 < x < 450 and 215 < y < 355)
        segment = self.plan["segments"][self.plan["milestones"]["BUFFER"]["segment_index"]]
        self.assertEqual(segment["event_after"], "PALM_READY")
        self.assertEqual(segment["start_q16"][5], segment["target_q16"][5])

    def test_cancel_branches_are_payload_checked_and_return_to_source(self):
        robot = self.planner.robot
        for phase, branch in self.plan["cancel_branches"].items():
            rows = [q for _, values in regenerate(branch["start_q16"], branch["segments"], CONFIG) for q in values]
            self.assertEqual(sample_digest(rows), branch["sample_sha256"])
            self.assertEqual(branch["segments"][-1]["target_q16"], self.plan["start_q16"])
            place = next(s for s in reversed(branch["segments"]) if s["phase"] == "CANCEL_PLACE")
            self.assertLess(np.linalg.norm(robot.fk(dequantize(place["target_q16"]))[:3, 3]-REQUEST["pickup"]["centre_mm"]), .3)
            self.assertTrue(any(s["event_after"] == "SOURCE_VACANT" for s in branch["segments"]))

    def test_obstacle_midway_is_detected(self):
        robot = self.planner.robot
        row = self.plan["sample_rows"][len(self.plan["sample_rows"])//2]
        frame = robot.frames(dequantize(row))["link3"]
        request = deepcopy(REQUEST)
        request["obstacles"] = [{"id": "unexpected_block", "centre_mm": frame[:3, 3].tolist(), "size_mm": [20, 20, 20]}]
        with self.assertRaises(CollisionError):
            World(robot, request, CONFIG).check(dequantize(row))

    def test_sat_rotated_boxes_and_separation(self):
        a = Box.local("a", transform(rpy=[0, 0, .7]), np.array([-10., -1, -1]), np.array([10., 1, 1]))
        b = Box("b", np.array([0., 0., 0.]), np.eye(3), np.ones(3))
        self.assertLess(separating_gap(a, b), 0)
        b.centre += [100, 0, 0]
        self.assertGreater(separating_gap(a, b), 0)

    def test_residual_placeholder_changes_fk_without_authorizing_hardware(self):
        config = deepcopy(CONFIG); config["residual"]["joint_bias_rad"][1] = .02
        changed = Robot(ROOT, config)
        self.assertGreater(np.linalg.norm(changed.fk(CONFIG["home_rad"])[:3, 3]-self.planner.robot.fk(CONFIG["home_rad"])[:3, 3]), 1)
        self.assertFalse(Planner(ROOT, config).config["physical_execution_allowed"])

    def test_asymmetric_jaw_tcp_depends_on_object_width(self):
        cube = Robot(ROOT, CONFIG, grasp_width_mm=30)
        eraser = Robot(ROOT, CONFIG, grasp_width_mm=15)
        self.assertAlmostEqual(cube.grasp[0, 3]-eraser.grasp[0, 3], 7.5)
        self.assertAlmostEqual(cube.grasp[0, 3]-15-CONFIG["grasp_centre_model"]["fixed_jaw_inner_x_mm"], 2)
        self.assertTrue(self.plan["grasp_model"]["asymmetric_jaw_width_dependency"])

    def test_state_machine_normal_complete_and_simulation_labelled(self):
        result = simulate_task(self.plan)
        self.assertTrue(result["complete"])
        self.assertTrue(result["events_are_simulated"])

    def test_state_machine_no_duplicate_send_missing_feedback_or_wrong_task(self):
        machine = TaskMachine(self.plan)
        s = machine.next_segment(0)
        self.assertIsNotNone(s)
        self.assertIsNone(machine.next_segment(1))
        self.assertFalse(machine.feedback("another_task", dequantize(s["target_q16"]), settled=True))
        self.assertFalse(machine.feedback(self.plan["task_id"], [0, 0], settled=True))
        machine.fault("LINK_LOSS")
        self.assertFalse(machine.feedback(self.plan["task_id"], dequantize(s["target_q16"]), settled=True))
        self.assertIsNone(machine.next_segment(100))

    def test_expired_palm_ready_blocks_delivery(self):
        machine = TaskMachine(self.plan)
        machine.index = self.plan["milestones"]["BUFFER"]["segment_index"]+1
        machine.observed_q16 = tuple(self.plan["segments"][machine.index]["start_q16"])
        machine.waiting = "PALM_READY"
        self.assertFalse(machine.event(machine.task_id, "PALM_READY", 0, valid_for_ms=0))
        self.assertTrue(machine.event(machine.task_id, "PALM_READY", 0, valid_for_ms=1))
        self.assertIsNone(machine.next_segment(1000))
        self.assertEqual(machine.waiting, "PALM_READY")

    def test_cancel_in_motion_does_not_blindly_reverse(self):
        machine = TaskMachine(self.plan); machine.next_segment(0)
        self.assertIsNone(machine.cancel())
        self.assertEqual(machine.status, "CANCEL_HOLD")
        self.assertIsNone(machine.next_segment(200))

    def test_accepted_tolerance_preserves_actual_feedback_and_cancel_requires_exact_pose(self):
        machine = TaskMachine(self.plan)
        i = self.plan["milestones"]["LIFT"]["segment_index"]
        machine.index = i
        machine.nominal_cursor_q16 = tuple(self.plan["segments"][i]["start_q16"])
        segment = machine.next_segment(0)
        actual = dequantize(segment["target_q16"])
        actual[0] += .005
        self.assertTrue(machine.feedback(machine.task_id, actual, settled=True))
        self.assertNotEqual(machine.observed_q16, machine.nominal_cursor_q16)
        self.assertIsNone(machine.cancel())

    def test_branch_digest_checked_even_with_recomputed_whole_task_hash(self):
        tampered = deepcopy(self.plan)
        tampered["cancel_branches"]["LIFT"]["sample_count"] += 1
        tampered["plan_sha256"] = plan_digest(tampered)
        with self.assertRaisesRegex(ValueError, "sample count"):
            verify_task(tampered, CONFIG)

    def test_mode_b_observation_rejects_cpu_unverified_and_stale_input(self):
        obs = {"schema": "gesture.ai_pc.mode_b_observation.v1", "profile_id": "mode_b_red_eraser_canister_v1",
               "backend": {"actual_backend": "cpu", "npu_execution_verified": False, "cpu_fallback": True}}
        with self.assertRaisesRegex(ValueError, "NPU"):
            request_from_observation(obs, 1, REQUEST["destination"], task_id="x", now_ms=10, observed_at_ms=5)
        with self.assertRaisesRegex(ValueError, "Stale"):
            request_from_observation(obs, 1, REQUEST["destination"], task_id="x", now_ms=1000, observed_at_ms=5)

    def test_observation_adapter_converts_top_centre_to_object_centre(self):
        # Explicit fixture, never reported as actual NPU/ROCm validation.
        obs = {"schema":"gesture.ai_pc.mode_b_observation.v1", "profile_id":"mode_b_red_eraser_canister_v1",
            "backend":{"actual_backend":"npu", "npu_execution_verified":True, "cpu_fallback":False},
            "npu_acceptance":"ACCEPTED", "surface_backend":{"device_type":"rocm_gpu"},
            "rocm_acceptance":"ACCEPTED", "metric_localization_accepted":True,
            "frame_sha256":"fixture", "profile_sha256":"fixture", "localizations":[{
                "task_id":2,"instances":1,"class_name":"eraser", "metric_surface":{
                    "metric_localization_verified":True, "centre_table_xyz_mm":[550,270,15],
                    "long_axis_yaw_mod180_deg":30}}]}
        request = request_from_observation(obs, 2, REQUEST["destination"], task_id="fixture", now_ms=10, observed_at_ms=5)
        self.assertEqual(request["pickup"]["centre_mm"], [550,270,7.5])
        self.assertEqual(request["pickup"]["yaw_deg"], 30)
        obs["metric_localization_accepted"] = False
        with self.assertRaisesRegex(ValueError,"calibration"):
            request_from_observation(obs, 2, REQUEST["destination"], task_id="fixture", now_ms=10, observed_at_ms=5)

    def test_export_roundtrip_and_integrity_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/"package"
            write_package(self.plan, CONFIG, target)
            exported = json.loads((target/"complete_task.json").read_text())
            loaded, loaded_config = load_package(target/"complete_task.json")
            self.assertEqual(loaded["plan_sha256"], self.plan["plan_sha256"])
            self.assertEqual(loaded_config, CONFIG)
            self.assertEqual(plan_digest(exported), self.plan["plan_sha256"])
            self.assertTrue((target/"trajectory.csv").exists())
            adapter = json.loads((target/"fpga_adapter_draft.json").read_text())
            self.assertTrue(all(len(c["segments"]) <= 32 for c in adapter["chunks"]))
            self.assertFalse(adapter["physical_execution_allowed"])
            self.assertFalse(adapter["mode_a_tables_changed"])
            tampered = deepcopy(self.plan); tampered["segments"][0]["target_q16"][0] += 1
            with self.assertRaises(ValueError):
                write_package(tampered, CONFIG, Path(temp)/"tampered")
            with (target/"trajectory.csv").open("a", encoding="utf8") as stream:
                stream.write("corrupted\n")
            with self.assertRaisesRegex(ValueError, "file integrity"):
                load_package(target/"complete_task.json")


if __name__ == "__main__":
    unittest.main(verbosity=2)
