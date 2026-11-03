"""Inverse-kinematics interface for the AI PC planner (Phase 3 S6 candidate).

The real arm (RoArm-M3-Pro: 5 positioning joints + gripper channel) is not calibrated and its IK,
zero offsets, directions and limits are TBD, so:
* UnavailableIK is what a real deployment gets today: every solve() raises IKUnavailable;
* SyntheticIK is a TEST DOUBLE: a smooth made-up mapping from (x, y, z, yaw, gripper) to six Q16.16
  channel values inside the S4 bench range.  It is NOT the arm's kinematics; plans made with it are
  IKKind.SYNTHETIC and can never pass the real-execution gate.
Joint order and units: phase3_path_contract (index 5 = gripper, Q16.16).
"""

from __future__ import annotations

import math
from typing import Protocol

import phase3_path_contract as pc

Q16 = 65536


class IKUnavailable(RuntimeError):
    pass


class IKSolver(Protocol):
    kind: pc.IKKind

    def solve(self, xyz_mm: tuple, yaw_rad: float, gripper: float) -> tuple: ...


class UnavailableIK:
    kind = pc.IKKind.REAL

    def solve(self, xyz_mm, yaw_rad, gripper):
        raise IKUnavailable("real IK is TBD: arm geometry, zero offsets, directions and limits are not measured")


class SyntheticIK:
    kind = pc.IKKind.SYNTHETIC

    def solve(self, xyz_mm, yaw_rad, gripper):
        x, y, z = xyz_mm
        r = math.hypot(x, y)
        rad = (math.atan2(y, x), 0.9 - r / 600.0, 0.4 + z / 400.0, -0.3 + z / 800.0, yaw_rad * 0.5, 0.2 + 1.2 * gripper)
        return tuple(int(round(a * Q16)) for a in rad)
