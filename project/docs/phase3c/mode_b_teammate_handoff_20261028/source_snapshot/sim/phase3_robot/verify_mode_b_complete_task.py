"""Independent CoppeliaSim mesh/FK verification of exported Mode B PL samples.

Uses the teammate's URDF/ZMQ control approach, with a temporary import of the
same CAD model. The simulator must be an isolated instance on localhost:23020.
This tool resets that instance's scene; it never connects to a physical robot.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pc.mode_b.motion.collision import World
from pc.mode_b.motion.export import load_package
from pc.mode_b.motion.kinematics import ORDER, Robot, transform
from pc.mode_b.motion.trajectory import dequantize, regenerate


def sim_matrix(matrix):
    matrix = np.array(matrix, dtype=float).copy()
    matrix[:3, 3] /= 1000
    return matrix[:3].reshape(-1).tolist()


def np_matrix(matrix):
    result = np.eye(4)
    result[:3] = np.array(matrix).reshape(3, 4)
    result[:3, 3] *= 1000
    return result


def verify(task_path, output, *, port=23020):
    from coppeliasim_zmqremoteapi_client import RemoteAPIClient
    plan, config = load_package(Path(task_path))
    robot = Robot(ROOT, config, grasp_width_mm=plan["grasp_model"]["object_width_mm"])
    if robot.sha256 != plan["urdf_sha256"]:
        raise ValueError("URDF hash mismatch")
    client = RemoteAPIClient(host="127.0.0.1", port=port)
    sim = client.require("sim")
    if sim.getSimulationState() != sim.simulation_stopped:
        raise ValueError("Dedicated simulation must be stopped before verification")
    sim.closeScene()
    plugin = client.require("simURDF")
    with tempfile.TemporaryDirectory(prefix="mode_b_sim_") as temp:
        model = Path(temp)/"model"
        shutil.copytree(robot.path.parent, model)
        urdf = model/robot.path.name
        tree = ET.parse(urdf)
        # CoppeliaSim's URDF importer cannot import geometry-free root/leaf
        # links in this model. Preserve their transforms explicitly below.
        for element in list(tree.getroot()):
            if element.attrib.get("name") in ("world", "world_to_base_link", "hand_tcp", "link5_to_hand_tcp"):
                tree.getroot().remove(element)
        tree.write(urdf, encoding="utf-8", xml_declaration=True)
        name, models = getattr(plugin, "import")(str(urdf), 32+256)
    if name != "roarm_m3" or len(models) != 1:
        raise ValueError("RoArm model import failed")
    aliases = {sim.getObjectAlias(h): h for h in sim.getObjectsInTree(sim.handle_scene, sim.handle_all, 0)}
    joints = [aliases[name] for name in ORDER]
    root = models[0]
    initial_base = np_matrix(sim.getObjectMatrix(joints[0], sim.handle_world))
    initial_root = np_matrix(sim.getObjectMatrix(root, sim.handle_world))
    expected_base = robot.world @ robot.origins["world_to_base_link"]
    relocated = expected_base @ np.linalg.inv(initial_base) @ initial_root
    sim.setObjectMatrix(root, sim.handle_world, sim_matrix(relocated))
    tcp = sim.createDummy(.01)
    sim.setObjectAlias(tcp, "mode_b_grasp_frame")
    sim.setObjectParent(tcp, joints[4], False)
    sim.setObjectMatrix(tcp, sim.handle_parent, sim_matrix(robot.grasp @ robot.tool_residual))
    script = sim.createScript(sim.scripttype_customization,
        (ROOT/"sim/phase3_robot/mode_b_validate.lua").read_text(encoding="utf8"), 0, "lua")
    sim.initScript(script)

    def cuboid(name, centre, size):
        handle = sim.createPrimitiveShape(sim.primitiveshape_cuboid, (np.array(size)/1000).tolist(), 0)
        sim.setObjectAlias(handle, name)
        sim.setObjectPosition(handle, sim.handle_world, (np.array(centre)/1000).tolist())
        return handle

    world = World(robot, plan["request"], config)
    links = {name: aliases[name+"_respondable"] for name in robot.boxes}
    table = cuboid("mode_b_table", [400, 300, -10], [800, 600, 20])
    static = [table]
    if world.support:
        static.append(cuboid("mode_b_support", world.support.centre, world.support.half*2))
    for obstacle in world.obstacles:
        static.append(cuboid(obstacle.name, obstacle.centre, obstacle.half*2))
    shape = config["objects"][plan["object_class"]]
    if shape["shape"] == "cylinder":
        payload = sim.createPrimitiveShape(sim.primitiveshape_cylinder, (np.array(shape["size_mm"])/1000).tolist(), 0)
        sim.setObjectAlias(payload, "mode_b_payload")
    else:
        payload = cuboid("mode_b_payload", plan["request"]["pickup"]["centre_mm"], shape["size_mm"])
    sim.setObjectMatrix(payload, sim.handle_world, sim_matrix(transform(plan["request"]["pickup"]["centre_mm"],
        [0, 0, np.radians(plan["request"]["pickup"]["yaw_deg"])])))
    self_pairs = [[links[a], links[b]] for a, b in world.self_pairs]
    external_pairs = [[h, obstacle] for name, h in links.items() for obstacle in static
                      if not (name == "base_link" and obstacle == table)]
    payload_arm_pairs = [[payload, h] for name, h in links.items() if name not in ("link5", "gripper_link")]
    attachment = sim_matrix(plan["attachment"]["grasp_from_object"])
    checked, maximum_error, collisions = 0, 0., []
    results = []
    for segment, rows in regenerate(plan["start_q16"], plan["segments"], config):
        expected = [(robot.fk(dequantize(row))[:3, 3]/1000).tolist() for row in rows]
        pairs = self_pairs+external_pairs+payload_arm_pairs
        if segment["payload_attached"]:
            pairs += [[payload, h] for h in static]
        elif segment["phase"] != "GRASP":
            pairs += [[payload, links[name]] for name in ("link5", "gripper_link")]
        result = sim.callScriptFunction("modeBReplay", script, rows, joints, tcp, expected,
                                        pairs, payload, attachment, segment["payload_attached"])
        checked += result["samples"]
        maximum_error = max(maximum_error, result["maximum_tcp_error_m"]*1000)
        if result.get("first_collision"):
            collisions.append({"phase": segment["phase"], **result["first_collision"]})
        results.append({"phase": segment["phase"], "samples": result["samples"],
                        "max_tcp_error_mm": result["maximum_tcp_error_m"]*1000})
    final_payload = np_matrix(result["last_payload_matrix"])[:3, 3]
    normal_home_error = max(abs(sim.getJointPosition(h)-v/65536) for h, v in zip(joints, plan["start_q16"]))
    target = np.array(plan["request"]["destination"]["support_centre_mm"], dtype=float)
    target[2] += shape["size_mm"][2]/2+config["collision_margin_mm"]+.5
    branch_reports = {}
    for phase, branch in plan["cancel_branches"].items():
        branch_collisions, branch_error, count = [], 0., 0
        for segment, rows in regenerate(branch["start_q16"], branch["segments"], config):
            expected = [(robot.fk(dequantize(row))[:3, 3]/1000).tolist() for row in rows]
            pairs = self_pairs+external_pairs+payload_arm_pairs
            if segment["payload_attached"]:
                pairs += [[payload, h] for h in static if not (
                    h == table and segment["phase"] in ("CANCEL_PLACE", "CANCEL_RELEASE"))]
            else:
                pairs += [[payload, links[name]] for name in ("link5", "gripper_link")]
            result = sim.callScriptFunction("modeBReplay", script, rows, joints, tcp, expected,
                pairs, payload, attachment, segment["payload_attached"])
            count += result["samples"]
            branch_error = max(branch_error, result["maximum_tcp_error_m"]*1000)
            if result.get("first_collision"):
                branch_collisions.append({"phase": segment["phase"], **result["first_collision"]})
        returned = np_matrix(result["last_payload_matrix"])[:3, 3]
        return_error = float(np.linalg.norm(returned-plan["request"]["pickup"]["centre_mm"]))
        home_error = max(abs(sim.getJointPosition(h)-v/65536) for h, v in zip(joints, plan["start_q16"]))
        branch_reports[phase] = {"samples_checked": count, "max_tcp_error_mm": branch_error,
            "mesh_collisions": branch_collisions, "source_return_error_mm": return_error,
            "joint_home_error_rad": home_error,
            "passed": not branch_collisions and branch_error < .1 and return_error < 1 and home_error < 1e-6,
            "intentional_table_contact": "PAYLOAD_ONLY_DURING_CANCEL_PLACE_RELEASE; penetration checked offline"}
    report = {"schema": "gesture.mode_b.coppelia_verification.v1", "task_id": plan["task_id"],
        "plan_sha256": plan["plan_sha256"], "config_sha256": plan["config_sha256"],
        "sample_sha256": plan["sample_sha256"], "urdf_sha256": robot.sha256,
        "mesh_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((robot.path.parent/"meshes").glob("*.stl"))},
        "simulator_version": sim.getInt32Param(sim.intparam_program_version), "samples_checked": checked,
        "max_tcp_model_error_mm": maximum_error, "mesh_collisions": collisions,
        "final_payload_centre_mm": final_payload.tolist(), "placement_error_mm": float(np.linalg.norm(final_payload-target)),
        "joint_home_error_rad": normal_home_error,
        "cancel_branches": branch_reports,
        "passed": bool(checked == plan["sample_count"] and maximum_error < .1 and not collisions and np.linalg.norm(final_payload-target) < 1 and normal_home_error < 1e-6
                       and all(b["passed"] for b in branch_reports.values())),
        "simulation_type": "KINEMATIC_MESH_COLLISION_WITH_RIGID_PAYLOAD_ATTACHMENT",
        "friction_force_and_slip_validated": False, "physical_execution_allowed": False, "segments": results}
    Path(output).write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=23020)
    args = parser.parse_args()
    report = verify(args.task, args.output, port=args.port)
    print(json.dumps({k: v for k, v in report.items() if k != "segments"}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
