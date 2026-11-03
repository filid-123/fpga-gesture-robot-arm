"""Sparse joint-path planning on the AI PC (Phase 3 S6 candidate).

From one grasp candidate and the two fixed poses the PS sends with the target request (HOME, the
S4 start, and PRE_DELIVERY, the required end), build the mode-B path S4 expects:
  1 pre-grasp (approach point, gripper open, STOP_ON_CANCEL)
  2 grasp pose, gripper open (STOP_ON_CANCEL)
  3 close the gripper (F_GRASP, N=2, Na=0, linear profile - as the S4 bench grasp segment)
  4 lift (gripper closed)
  5 PRE_DELIVERY (exactly the S4 keypoint)
Each segment's N is the smallest value the S2 v0.2.3 reference planner accepts under the motion
limits (search from n_min), so velocity/acceleration are checked by the same model the PL is bit-exact
with; then the whole path is checked sample by sample and its digest is attached.
Failure states: NO_GRASP, IK_UNAVAILABLE, INFEASIBLE (no N up to n_max), CONTRACT (check failed).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import phase3_path_contract as pc
from grasp import GraspCandidate, GraspParams, GraspStatus
from ik_interface import IKUnavailable


class PlanStatus(str, Enum):
    OK = "OK"
    NO_GRASP = "NO_GRASP"
    IK_UNAVAILABLE = "IK_UNAVAILABLE"
    INFEASIBLE = "INFEASIBLE"
    CONTRACT = "CONTRACT"


@dataclass(frozen=True)
class PlanOutcome:
    status: PlanStatus
    plan: Optional[pc.PathPlan] = None
    detail: str = ""
    check: Optional[pc.CheckResult] = None


def _min_n(start, target, na_ratio, profile, lim: pc.MotionLimits, pr, n_min: int, n_max: int) -> Optional[tuple]:
    for n in range(n_min, n_max + 1):
        na = 0 if profile == 0 else max(1, int(n * na_ratio))
        move = pr.MoveParams(tuple(start), tuple(target), n, na, profile, lim.period_cycles, lim.stall_cycles,
                             tuple(lim.vmax_q16), tuple(lim.amax_q32))
        if pr.validate(move, tuple(start)).ok:
            return n, na
    return None


def plan_pick(task_id: int, object_id: int, grasp: GraspCandidate, ik, home: tuple, pre_delivery: tuple,
              lim: pc.MotionLimits, calib_id: int, pr, params: GraspParams = GraspParams(),
              n_min: int = 4, n_max: int = 2000, na_ratio: float = 0.25) -> PlanOutcome:
    if grasp.status != GraspStatus.OK:
        return PlanOutcome(PlanStatus.NO_GRASP, detail=grasp.status.value)
    try:
        pre_grasp = ik.solve(grasp.approach_mm, grasp.yaw_rad, params.gripper_open)
        at_grasp = ik.solve(grasp.grasp_mm, grasp.yaw_rad, params.gripper_open)
        closed = ik.solve(grasp.grasp_mm, grasp.yaw_rad, params.gripper_closed)
        lift = ik.solve(grasp.lift_mm, grasp.yaw_rad, params.gripper_closed)
    except IKUnavailable as exc:
        return PlanOutcome(PlanStatus.IK_UNAVAILABLE, detail=str(exc))
    keys = [(pre_grasp, 1, pc.F_STOP_ON_CANCEL), (at_grasp, 1, pc.F_STOP_ON_CANCEL), (closed, 0, pc.F_GRASP),
            (lift, 1, 0), (tuple(pre_delivery), 1, 0)]
    segs, pose = [], tuple(home)
    for target, profile, flags in keys:
        if flags & pc.F_GRASP:
            n, na = 2, 0
            move = pr.MoveParams(pose, tuple(target), n, na, profile, lim.period_cycles, lim.stall_cycles,
                                 tuple(lim.vmax_q16), tuple(lim.amax_q32))
            if not pr.validate(move, pose).ok:
                found = _min_n(pose, target, na_ratio, profile, lim, pr, 2, n_max)
                if found is None:
                    return PlanOutcome(PlanStatus.INFEASIBLE, detail="grasp segment")
                n, na = found
        else:
            found = _min_n(pose, target, na_ratio, profile, lim, pr, n_min, n_max)
            if found is None:
                return PlanOutcome(PlanStatus.INFEASIBLE, detail=f"segment {len(segs)}")
            n, na = found
        segs.append(pc.Segment(tuple(target), n, na, profile, flags))
        pose = tuple(target)
    plan = pc.PathPlan(task_id, object_id, tuple(home), tuple(segs), calib_id, ik.kind)
    plan, result = pc.finalize(plan, lim, home, pre_delivery, pr)
    if not result.ok:
        return PlanOutcome(PlanStatus.CONTRACT, plan, detail=result.first().name, check=result)
    return PlanOutcome(PlanStatus.OK, plan, check=result)
