"""AI PC task agent (Phase 3 S7 candidate): one TARGET_REQUEST -> at most one path, plus scene checks.

Transport-agnostic (like the S6 PathServiceCore): on_connect / on_message / step return the
messages to send; the TCP client or the in-memory link carries them.
  * target missing / not graspable / not plannable      -> CANCEL (S4 does not wait for the timeout)
  * scene changed before submission: the plan is made on frame F1, the object is re-detected on a
    fresh frame F2; if it moved more than scene_tol_mm (or vanished) the path is re-planned on F2
    (at most max_replans times), otherwise CANCEL ("scene_unstable");
  * scene changed after the commit, before the arm reaches the object: the object is re-detected
    during the watch window (until the predicted end of the first segment, HOME -> pre-grasp, minus
    a margin, from the committed N and the period); a move beyond scene_tol_mm or a vanished object
    -> CANCEL.  After the window no cancel is sent for scene reasons (the arm is at the object);
  * PATH_RESULT REJECTED / NOT_EXECUTABLE / WRONG_OBJECT -> CANCEL (nothing will be executed);
    DUPLICATE / NO_TASK / PL_REJECTED -> nothing (S4 already refused or never waited);
  * link loss: the agent forgets the request; it never resubmits after a reconnect (a new task needs
    a new selection by the user).
The watch window prediction uses the PL period: in simulation the harness passes pl_time_scale
(seconds of simulated wall time per second of PL time); on hardware it is 1.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Optional

import phase3_link_protocol as lp
import phase3_path_contract as pc
from detector import DetStatus
from phase3_event_log import EventLog
from pick_pipeline import TargetRequest

T, R = lp.MsgType, lp.PathResult
ROLE_PC = 1


@dataclass(frozen=True)
class AgentConfig:
    scene_tol_mm: float = 10.0
    max_replans: int = 1
    watch_after_commit: bool = True
    watch_margin_s: float = 0.0
    watch_period_s: float = 0.02
    pl_clock_hz: int = 100_000_000
    pl_time_scale: float = 1.0
    heartbeat_interval_s: float = 0.3
    resubmit_after_commit: bool = False     # FAULT INJECTION (duplicate scenario only)


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class PcTaskAgent:
    def __init__(self, pipeline, cfg: AgentConfig = AgentConfig(), log: Optional[EventLog] = None,
                 clock: Callable[[], float] = time.monotonic):
        self.pipe, self.cfg, self.clock = pipeline, cfg, clock
        self.log = log or EventLog("pc")
        self.session = False
        self.limits: Optional[pc.MotionLimits] = None
        self.req: Optional[TargetRequest] = None
        self.plan: Optional[pc.PathPlan] = None
        self.ref_xy: Optional[tuple] = None
        self.watch_until: Optional[float] = None
        self._next_watch = 0.0
        self._last_hb = -1e9
        self.submissions = 0
        self.last_submitted: Optional[pc.PathPlan] = None

    # ------------------------------------------------------------------ link
    def on_connect(self) -> list:
        self.log.emit("pc_connect")
        return [(T.HELLO, (ROLE_PC, pc.INTERP_VERSION, pc.CONTRACT_VERSION))]

    def on_disconnect(self, reason: str) -> None:
        self.session = False
        if self.req is not None:
            self.log.emit("request_dropped", self.req.task_id, reason=reason)
        self.req = self.plan = None
        self.watch_until = None

    def _cancel(self, why: str) -> list:
        tid = self.req.task_id
        self.log.emit("pc_cancel", tid, reason=why)
        self.watch_until = None
        return [(T.CANCEL, (tid,))]

    def on_message(self, msg: lp.Message) -> list:
        t = msg.type
        if t == T.HELLO:
            self.session = True
            return []
        if t == T.LIMITS:
            self.limits = lp.limits_from_fields(msg.fields)
            self.log.emit("limits", status=self.limits.status)
            return []
        if t == T.TARGET_REQUEST:
            return self._on_request(TargetRequest.from_message(msg))
        if t == T.PATH_RESULT:
            return self._on_result(msg.fields)
        if t == T.STATUS:
            tid, st = msg.fields[0], lp.TaskState(msg.fields[1])
            self.log.emit("status", tid, task_state=st.name, s4_state=msg.fields[2], s4_phase=msg.fields[3],
                          events=msg.fields[7])
            if self.req is not None and tid == self.req.task_id and st in (lp.TaskState.DONE, lp.TaskState.CANCELLED,
                                                                          lp.TaskState.REFUSED, lp.TaskState.FAULT,
                                                                          lp.TaskState.HALTED):
                self.req = self.plan = None
                self.watch_until = None
            return []
        if t == T.BYE:
            self.on_disconnect("BYE")
        return []

    # ------------------------------------------------------------------ planning
    def _on_request(self, req: TargetRequest) -> list:
        self.req, self.plan, self.watch_until = req, None, None
        self.log.emit("target_request", req.task_id, object=req.object_id)
        if self.limits is None:
            return self._cancel("no LIMITS received")
        for attempt in range(self.cfg.max_replans + 1):
            plan, rep = self.pipe.handle(req, self.limits)
            self.log.emit("pipeline", req.task_id, attempt=attempt, outcome=rep.outcome,
                          host_ns={k: int(v) for k, v in rep.t_ns.items()},
                          det=rep.detection.status.value if rep.detection is not None else None)
            if plan is None:
                return self._cancel(rep.outcome)
            check = self.pipe.detect_only(req.object_id)
            if check.status != DetStatus.FOUND:
                self.log.emit("scene_check", req.task_id, attempt=attempt, result=check.status.value)
                continue
            moved = _dist(check.top_base_mm, rep.detection.top_base_mm)
            self.log.emit("scene_check", req.task_id, attempt=attempt, moved_mm=round(moved, 2))
            if moved <= self.cfg.scene_tol_mm:
                self.plan, self.ref_xy, self.last_submitted = plan, check.top_base_mm, plan
                self.submissions += 1
                self.log.emit("path_submitted", req.task_id, segments=len(plan.segments))
                return [(T.PATH_SUBMIT, (plan,))]
        return self._cancel("scene_unstable")

    def _on_result(self, f: tuple) -> list:
        tid, res = f[0], R(f[1])
        self.log.emit("path_result", tid, result=res.name, problem=f[2], detail=f[3])
        if self.req is None or tid != self.req.task_id:
            return []
        if res == R.COMMITTED:
            out = []
            if self.cfg.resubmit_after_commit:
                self.log.emit("fault_injection_resubmit", tid)
                out.append((T.PATH_SUBMIT, (self.plan,)))
            if self.cfg.watch_after_commit:
                first = self.plan.segments[0]
                t_first = first.n * self.req.period_cycles / self.cfg.pl_clock_hz * self.cfg.pl_time_scale
                self.watch_until = self.clock() + max(0.0, t_first - self.cfg.watch_margin_s)
                self._next_watch = self.clock()
                self.log.emit("scene_watch", tid, window_s=round(t_first - self.cfg.watch_margin_s, 6))
            return out
        if res in (R.REJECTED, R.NOT_EXECUTABLE, R.WRONG_OBJECT):
            return self._cancel(f"path {res.name}")
        return []

    # ------------------------------------------------------------------ periodic
    def step(self) -> list:
        out: list = []
        now = self.clock()
        if self.session and now - self._last_hb >= self.cfg.heartbeat_interval_s:
            out.append((T.HEARTBEAT, ()))
            self._last_hb = now
        if self.watch_until is not None and self.req is not None:
            if now > self.watch_until:
                self.log.emit("scene_watch_end", self.req.task_id)
                self.watch_until = None
            elif now >= self._next_watch:
                self._next_watch = now + self.cfg.watch_period_s
                det = self.pipe.detect_only(self.req.object_id)
                if det.status != DetStatus.FOUND:
                    out += self._cancel(f"scene_changed ({det.status.value})")
                elif _dist(det.top_base_mm, self.ref_xy) > self.cfg.scene_tol_mm:
                    out += self._cancel(f"scene_changed (moved {_dist(det.top_base_mm, self.ref_xy):.1f} mm)")
        return out
