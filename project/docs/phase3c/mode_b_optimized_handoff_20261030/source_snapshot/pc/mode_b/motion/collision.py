"""Conservative oriented mesh bounding boxes, including carried-object geometry.

Boxes enclose each supplied STL; a rejection can be conservative. This is a
kinematic check, not contact/friction simulation or a continuous-collision proof.
"""
from __future__ import annotations
from dataclasses import dataclass
import itertools
import numpy as np

from .kinematics import transform, vector


@dataclass
class Box:
    name: str
    centre: np.ndarray
    axes: np.ndarray
    half: np.ndarray

    @classmethod
    def local(cls, name, matrix, low, high):
        return cls(name, matrix[:3, :3] @ ((low+high)/2)+matrix[:3, 3],
                   matrix[:3, :3], (high-low)/2)

    @property
    def corners(self):
        signs = np.array(list(itertools.product([-1, 1], repeat=3)))
        return signs*self.half @ self.axes.T + self.centre


def separating_gap(a: Box, b: Box):
    """SAT separating-axis gap. Positive certifies separation, not Euclidean distance."""
    sphere_gap = float(np.linalg.norm(b.centre-a.centre)-np.linalg.norm(a.half)-np.linalg.norm(b.half))
    if sphere_gap > 4:
        return sphere_gap
    directions = [*a.axes.T, *b.axes.T]
    directions += [np.cross(x, y) for x in a.axes.T for y in b.axes.T]
    directions = np.array([d/np.linalg.norm(d) for d in directions if np.linalg.norm(d)>1e-8])
    radii = np.abs(directions @ a.axes) @ a.half + np.abs(directions @ b.axes) @ b.half
    return float(np.max(np.abs(directions @ (b.centre-a.centre))-radii))


class CollisionError(ValueError):
    pass


class World:
    def __init__(self, robot, request, config):
        self.robot, self.request, self.config = robot, request, config
        self.margin = float(config["collision_margin_mm"])
        self.table_clearance_by_link = dict(config.get('table_clearance_by_link_mm', {}))
        for name, value in self.table_clearance_by_link.items():
            if name not in ('link5', 'gripper_link') or not np.isfinite(value) or not .25 <= value <= self.margin:
                raise ValueError('Invalid local fingertip/table clearance')
        self.obstacles = []
        for item in request.get("obstacles", []):
            self.obstacles.append(Box(item["id"], vector(item["centre_mm"], 3), np.eye(3),
                                      vector(item["size_mm"], 3)/2))
        support = request["destination"]
        centre = np.array(support["support_centre_mm"], dtype=float)
        height = centre[2]
        self.support = None
        if height > 0:
            self.support = Box("destination_support", np.r_[centre[:2], height/2], np.eye(3),
                               np.r_[np.array(support["size_xy_mm"])/2, height/2])
        chain = ["base_link", "link1", "link2", "link3", "link4", "link5", "gripper_link"]
        self.self_pairs = [(a, b) for i, a in enumerate(chain) for j, b in enumerate(chain)
                           if j > i+1]

    def link_boxes(self, q):
        frames = self.robot.frames(q)
        return {name: Box.local(name, frames[name], *bounds)
                for name, bounds in self.robot.boxes.items()}

    def payload_box(self, q, size, grasp_from_object):
        matrix = self.robot.fk(q) @ np.asarray(grasp_from_object)
        size = np.array(size, dtype=float)
        return Box.local("payload", matrix, -size/2, size/2)

    def check(self, q, *, payload=None, payload_support_contact=False):
        boxes = self.link_boxes(q)
        minimum = float("inf")
        for name, box in boxes.items():
            if name != "base_link":
                clearance = float(np.min(box.corners[:, 2]))
                minimum = min(minimum, clearance)
                table_margin = float(self.table_clearance_by_link.get(name, self.margin))
                if clearance < table_margin:
                    raise CollisionError(f"TABLE:{name}:{clearance:.2f}mm")
            for obstacle in self.obstacles + ([self.support] if self.support else []):
                gap = separating_gap(box, obstacle)
                minimum = min(minimum, gap)
                if gap < self.margin:
                    raise CollisionError(f"OBSTACLE:{name}:{obstacle.name}:{gap:.2f}mm")
        for a, b in self.self_pairs:
            gap = separating_gap(boxes[a], boxes[b])
            minimum = min(minimum, gap)
            if gap < self.margin:
                raise CollisionError(f"SELF:{a}:{b}:{gap:.2f}mm")
        if payload is not None:
            box = self.payload_box(q, payload["size_mm"], payload["grasp_from_object"])
            bottom = float(np.min(box.corners[:, 2]))
            minimum = min(minimum, bottom)
            # Source tabletop contact is allowed at acquisition; penetration is not.
            if bottom < -.15:
                raise CollisionError(f"PAYLOAD_TABLE:{bottom:.2f}mm")
            for name, link_box in boxes.items():
                if name in ("link5", "gripper_link"):
                    continue  # declared intended grasp contacts only
                gap = separating_gap(box, link_box)
                if gap < self.margin:
                    raise CollisionError(f"PAYLOAD_ARM:{name}:{gap:.2f}mm")
                minimum = min(minimum, gap)
            for obstacle in self.obstacles + ([self.support] if self.support else []):
                if obstacle is self.support and payload_support_contact:
                    if bottom < self.request["destination"]["support_centre_mm"][2]-.15:
                        raise CollisionError("PAYLOAD_SUPPORT_PENETRATION")
                    continue
                gap = separating_gap(box, obstacle)
                minimum = min(minimum, gap)
                if gap < self.margin:
                    raise CollisionError(f"PAYLOAD_OBSTACLE:{obstacle.name}:{gap:.2f}mm")
        return minimum
