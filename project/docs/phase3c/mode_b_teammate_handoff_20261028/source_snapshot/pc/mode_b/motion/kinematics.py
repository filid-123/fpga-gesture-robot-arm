"""URDF five-joint kinematics with a separately controlled gripper (mm/rad)."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

ORDER = ("base_link_to_link1", "link1_to_link2", "link2_to_link3",
         "link3_to_link4", "link4_to_link5", "link5_to_gripper_link")


def vector(values, size, name="vector"):
    value = np.asarray(values, dtype=float)
    if value.shape != (size,) or not np.isfinite(value).all():
        raise ValueError(f"{name}: expected {size} finite numbers")
    return value


def transform(xyz=(0, 0, 0), rpy=(0, 0, 0)):
    result = np.eye(4)
    result[:3, :3] = Rotation.from_euler("xyz", vector(rpy, 3)).as_matrix()
    result[:3, 3] = vector(xyz, 3)
    return result


@dataclass(frozen=True)
class IKSolution:
    q: tuple[float, ...]
    position_error_mm: float
    orientation_error_deg: float
    tilt_deg: float


class IKError(ValueError):
    pass


class Robot:
    def __init__(self, root: Path, config: dict, *, grasp_width_mm=None):
        self.config = config
        self.path = root / config["urdf"]
        self.sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        xml = ET.parse(self.path).getroot()
        self.origins, self.parents, self.children, self.axes = {}, {}, {}, {}
        self.joints = list(xml.findall("joint"))
        self.limits = np.zeros((6, 2))
        for joint in self.joints:
            name = joint.attrib["name"]
            origin = joint.find("origin")
            xyz = [float(v)*1000 for v in origin.attrib.get("xyz", "0 0 0").split()]
            rpy = [float(v) for v in origin.attrib.get("rpy", "0 0 0").split()]
            self.origins[name] = transform(xyz, rpy)
            self.parents[name] = joint.find("parent").attrib["link"]
            self.children[name] = joint.find("child").attrib["link"]
            self.axes[name] = np.array([float(v) for v in joint.find("axis").attrib["xyz"].split()])
            if name in ORDER:
                limit = joint.find("limit")
                self.limits[ORDER.index(name)] = [float(limit.attrib["lower"]), float(limit.attrib["upper"])]
        self.world = transform(config["table_from_urdf_world"]["xyz_mm"],
                               config["table_from_urdf_world"]["rpy_rad"])
        self.grasp = transform(config["link5_from_grasp"]["xyz_mm"],
                               config["link5_from_grasp"]["rpy_rad"])
        model = config["grasp_centre_model"]
        self.grasp_width_mm = float(model["default_object_width_mm"] if grasp_width_mm is None else grasp_width_mm)
        if not math.isfinite(self.grasp_width_mm) or self.grasp_width_mm <= 0:
            raise ValueError("Positive object width required for asymmetric gripper TCP")
        self.grasp[0, 3] = model["fixed_jaw_inner_x_mm"]+self.grasp_width_mm/2+model["approach_clearance_mm"]
        self.bias = vector(config["residual"]["joint_bias_rad"], 6)
        self.tool_residual = transform(config["residual"]["tool_xyz_mm"],
                                       config["residual"]["tool_rpy_rad"])
        self.boxes = {}
        for link in xml.findall("link"):
            collision = link.find("collision")
            if collision is None:
                continue
            mesh = collision.find("geometry/mesh")
            if mesh is None:
                raise ValueError("Nominal model requires mesh collision geometry")
            data = (self.path.parent / mesh.attrib["filename"]).read_bytes()
            n = int.from_bytes(data[80:84], "little")
            triangles = np.frombuffer(data, dtype=np.dtype([("normal", "<f4", 3),
                ("vertices", "<f4", (3, 3)), ("attr", "<u2")]), count=n, offset=84)
            scale = np.array([float(v) for v in mesh.attrib.get("scale", "1 1 1").split()])*1000
            vertices = triangles["vertices"].reshape(-1, 3)*scale
            origin = collision.find("origin")
            local = transform([float(v)*1000 for v in origin.attrib.get("xyz", "0 0 0").split()],
                              [float(v) for v in origin.attrib.get("rpy", "0 0 0").split()])
            vertices = vertices @ local[:3, :3].T + local[:3, 3]
            self.boxes[link.attrib["name"]] = (vertices.min(0), vertices.max(0))

    def check_q(self, q):
        q = vector(q, 6, "six-channel joint pose")
        if np.any(q < self.limits[:, 0]-1e-8) or np.any(q > self.limits[:, 1]+1e-8):
            raise ValueError("Joint limit exceeded")
        return q

    def frames(self, q):
        q = vector(q, 6) + self.bias
        frames = {"world": self.world.copy()}
        for joint in self.joints:
            name = joint.attrib["name"]
            matrix = frames[self.parents[name]] @ self.origins[name]
            if name in ORDER:
                rotation = np.eye(4)
                rotation[:3, :3] = Rotation.from_rotvec(self.axes[name]*q[ORDER.index(name)]).as_matrix()
                matrix = matrix @ rotation
            frames[self.children[name]] = matrix
        frames["grasp"] = frames["link5"] @ self.grasp @ self.tool_residual
        return frames

    def fk(self, q):
        return self.frames(q)["grasp"]

    def solve(self, xyz, closing_yaw, seed, *, max_tilt_deg=10, position_tolerance_mm=.3,
              orientation_tolerance_deg=2, extra_seeds=True, max_joint_delta_rad=None):
        """Bounded numerical IK; full orientation is accepted only within tolerances.

        Grasp +Z points out of the fingers, downward at zero tilt. The X axis
        is the nominal closing axis. Gripper does not participate in arm IK.
        """
        xyz = vector(xyz, 3, "grasp centre")
        seed = self.check_q(seed)
        yaw = float(closing_yaw)
        if not math.isfinite(yaw) or not 0 <= max_tilt_deg <= 30:
            raise ValueError("Invalid yaw or tilt cone")
        if max_joint_delta_rad is not None and (
                not math.isfinite(max_joint_delta_rad) or max_joint_delta_rad <= 0):
            raise ValueError("Positive finite IK continuity bound required")
        upright = Rotation.from_euler("z", yaw).as_matrix() @ np.diag([1., -1., -1.])
        # Leave room for Q16.16 rounding near a joint limit.
        lower, upper = self.limits[:5, 0]+2/65536, self.limits[:5, 1]-2/65536
        radial = math.atan2(xyz[1]-self.world[1, 3], xyz[0]-self.world[0, 3])
        world_yaw = math.atan2(self.world[1, 0], self.world[0, 0])
        starts = [seed[:5]]
        if extra_seeds:
            for shoulder, elbow, wrist in [(0.4, 1.3, 1.0), (.8, .8, 1.),
                                           (-.4, 1.8, 1.), (.5, -.6, -1.)]:
                starts.append(np.array([radial-world_yaw, shoulder, elbow, wrist, seed[4]]))
        tangent = np.array([-math.sin(radial), math.cos(radial), 0.])
        trials = [(start, 0.) for start in starts]
        if max_tilt_deg:
            trials += [(starts[0], angle) for angle in
                       [max_tilt_deg/2, -max_tilt_deg/2, max_tilt_deg, -max_tilt_deg]]
        if max_joint_delta_rad is not None:
            # Follow the preceding orientation inside the requested cone before
            # trying upright/discrete tilts. The arm has five pose joints; a
            # different feasible orientation can otherwise be returned first
            # and cause a discontinuous joint-space branch near the wrist limit.
            relative = Rotation.from_matrix(self.fk(seed)[:3, :3] @ upright.T).as_rotvec()
            previous_tilt = math.degrees(float(relative @ tangent))
            trials.insert(0, (starts[0], float(np.clip(previous_tilt, -max_tilt_deg, max_tilt_deg))))
        for start, angle in trials:
            desired = Rotation.from_rotvec(tangent*math.radians(angle)).as_matrix() @ upright
            def residual(arm):
                pose = self.fk(np.r_[arm, seed[5]])
                rotation_error = Rotation.from_matrix(desired @ pose[:3, :3].T).as_rotvec()
                return np.r_[pose[:3, 3]-xyz, 65*rotation_error]
            result = least_squares(residual, np.clip(start, lower, upper), bounds=(lower, upper),
                                   max_nfev=110, ftol=1e-8, xtol=1e-8, gtol=1e-8)
            q = np.r_[result.x, seed[5]]
            pose = self.fk(q)
            pe = float(np.linalg.norm(pose[:3, 3]-xyz))
            oe = float(np.degrees(np.linalg.norm(Rotation.from_matrix(desired @ pose[:3, :3].T).as_rotvec())))
            tilt = math.degrees(math.acos(float(np.clip(-pose[2, 2], -1, 1))))
            continuous = max_joint_delta_rad is None or np.max(np.abs(q[:5]-seed[:5])) <= max_joint_delta_rad
            if pe <= position_tolerance_mm and oe <= orientation_tolerance_deg and tilt <= max_tilt_deg+1e-5 and continuous:
                return IKSolution(tuple(float(v) for v in q), pe, oe, tilt)
        raise IKError(f"No bounded IK at {tuple(np.round(xyz, 2))}; last position error={pe:.2f}mm, orientation={oe:.2f}deg")
