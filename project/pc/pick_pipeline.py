"""AI PC request handling: TARGET_REQUEST -> RGB-D frame -> detection -> grasp -> sparse path
(Phase 3 S6 candidate).

The pipeline answers one request with either a finalised PathPlan (to be submitted once) or a
failure state; on failure the PC sends CANCEL for the task instead of letting S4 wait for the
path-wait timeout.  Every stage is timed (host monotonic clock, raw ns in the report) for the S8
metrics; these are timings of THIS host on THIS data, not GPU/ROCm results.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import phase3_link_protocol as lp
import phase3_path_contract as pc
from alignment import align_depth_to_color
from detector import Detector, DetStatus
from grasp import GraspParams, GraspStatus, top_down_grasp
from sparse_planner import PlanStatus, plan_pick


@dataclass(frozen=True)
class TargetRequest:
    task_id: int
    object_id: int
    mode: int
    home: tuple
    pre_delivery: tuple
    period_cycles: int
    path_deadline_ms: int

    @classmethod
    def from_message(cls, msg: lp.Message) -> "TargetRequest":
        f = msg.fields
        return cls(f[0], f[1], f[2], tuple(f[3:9]), tuple(f[9:15]), f[15], f[16])


@dataclass
class PipelineReport:
    task_id: int
    object_id: int
    outcome: str                      # PLANNED | NO_FRAME | DET_<s> | GRASP_<s> | PLAN_<s> | DEADLINE
    t_ns: dict = field(default_factory=dict)
    detection: Optional[object] = None
    plan_status: Optional[str] = None
    samples: int = 0


class PickPipeline:
    def __init__(self, device, calib, scene, detector: Detector, ik, pr, grasp_params: GraspParams = GraspParams(),
                 clock=time.monotonic_ns):
        self.device, self.calib, self.scene, self.detector = device, calib, scene, detector
        self.ik, self.pr, self.grasp_params, self.clock = ik, pr, grasp_params, clock

    def handle(self, req: TargetRequest, limits: pc.MotionLimits) -> tuple:
        t = {"start": self.clock()}
        rep = PipelineReport(req.task_id, req.object_id, "")
        frame = self.device.read()
        t["frame"] = self.clock()
        rep.t_ns = t
        if frame is None:
            rep.outcome = "NO_FRAME"
            return None, rep
        frame.check()
        depth = align_depth_to_color(frame.depth, self.calib)
        t["aligned"] = self.clock()
        det = self.detector.detect(frame.color, depth, self.calib, self.scene, req.object_id)
        t["detected"] = self.clock()
        rep.detection, rep.t_ns = det, t
        if det.status != DetStatus.FOUND:
            rep.outcome = f"DET_{det.status.value}"
            return None, rep
        g = top_down_grasp(det, self.scene, self.grasp_params)
        if g.status != GraspStatus.OK:
            rep.outcome = f"GRASP_{g.status.value}"
            return None, rep
        out = plan_pick(req.task_id, req.object_id, g, self.ik, req.home, req.pre_delivery, limits,
                        self.calib.calib_id, self.pr, self.grasp_params)
        t["planned"] = self.clock()
        rep.plan_status = out.status.value
        if out.status != PlanStatus.OK:
            rep.outcome = f"PLAN_{out.status.value}"
            return None, rep
        if (t["planned"] - t["start"]) / 1e6 > req.path_deadline_ms:
            rep.outcome = "DEADLINE"
            return None, rep
        rep.outcome, rep.samples = "PLANNED", out.check.samples
        return out.plan, rep
