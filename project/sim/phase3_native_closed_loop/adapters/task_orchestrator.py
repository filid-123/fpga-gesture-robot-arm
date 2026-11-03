"""PYNQ PS task orchestrator (Phase 3 S7 candidate): one supervisor for mode A and mode B.

It sits on top of the S6 PathServiceCore (unchanged) and the S4 v0.1.1 port and adds what a whole
task needs on the PS side, without moving any real-time decision out of the PL:
  * task records: start, commit, end, outcome, cancel source, fault/refuse code, raw timestamps
    (event log records "task_start", "task_commit", "task_end" consumed by the S8 tools);
  * mode A (pure FPGA): the PL selects, grasps, delivers and returns on its own; the orchestrator
    only observes and reports (STATUS to a PC if one happens to be connected).  Nothing in mode A
    depends on the PC link or a PC heartbeat;
  * mode B (AI PC): the S6 service does the target request / one-shot commit / link policy (no new
    task without a PC session, waiting task cancelled on link loss, committed path continues);
  * cancel return policy (the PL executes it, the PS only checks the precondition at start-up):
      mode A          S4 v0.1.1 retrace: before the grasp back HOME, holding back to the fixed slot;
      mode B          HOLD policy is REQUIRED (S4 MODE_CFG[2]); a cancel while holding
                      - with the tray-exit S4 patch (ABI 0x0000_3402) and a validated tray path:
                        the PL finishes the committed path to PRE_DELIVERY and runs the fixed tray
                        path -> outcome TRAY_RETURN;
                      - otherwise: the PL stops and holds (HALT) -> outcome HALTED, the orchestrator
                        waits for the operator (never moves the arm itself, never auto-returns);
  * operator actions (explicit calls only): release (S4 RELEASE), fault_clear, enable, cancel;
    nothing is cleared or re-enabled automatically after a HALT or a FAULT.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

import phase3_link_protocol as lp
import s4_task_reference as m
from phase3_event_log import EventLog
from s4_port import S4Port

T = lp.MsgType


class Mode(str, Enum):
    A = "A_PURE_FPGA"
    B = "B_AI_PC"


class Outcome(str, Enum):
    DONE = "DONE"
    CANCELLED_BEFORE_MOTION = "CANCELLED_BEFORE_MOTION"    # WAIT_PATH / PRECHECK: nothing moved
    CANCELLED_HOME = "CANCELLED_HOME"                      # retraced to HOME before the grasp
    RETURNED_TO_SLOT = "RETURNED_TO_SLOT"                  # mode A: held object back to its fixed slot
    TRAY_RETURN = "TRAY_RETURN"                            # mode B + tray patch: object put in the tray
    HALTED = "HALTED"                                      # stopped and holding: operator required
    FAULT = "FAULT"
    REFUSED = "REFUSED"


@dataclass
class TaskRecord:
    task_id: int
    mode: Mode
    object_id: int
    t_start_ns: int
    t_commit_ns: Optional[int] = None
    t_end_ns: Optional[int] = None
    held: bool = False
    tray_seen: bool = False
    moved: bool = False
    outcome: Optional[Outcome] = None
    cancel_source: Optional[str] = None
    fault: str = "NONE"
    refuse: str = "NONE"
    s4_events: list = field(default_factory=list)


class EventTap(S4Port):
    """S4Port proxy: the path service drains events as before, the orchestrator gets a copy."""

    def __init__(self, inner: S4Port):
        self.inner = inner
        self.pending: list = []

    def status(self):
        return self.inner.status()

    def drain_events(self) -> list:
        evs = self.inner.drain_events()
        self.pending += evs
        return evs

    def command(self, cmd):
        return self.inner.command(cmd)

    def commit_path(self, obj, s4_task_id, segments):
        return self.inner.commit_path(obj, s4_task_id, segments)

    def take(self) -> list:
        self.drain_events()
        out, self.pending = self.pending, []
        return out


def s4_mode_cfg(port) -> dict:
    """MODE_CFG of the S4 behind a port: reference model (fake board) or AXI (register 0x024, readable)."""

    inner = getattr(port, "inner", port)
    if hasattr(inner, "model"):
        c = inner.model.cfg
        return {"mode_b": c.mode_b, "hold_policy": c.hold_policy, "tray_exit": bool(getattr(c, "tray_exit", False)),
                "abi": getattr(m, "ABI_VERSION_TRAY", m.ABI_VERSION) if getattr(c, "tray_exit", False) else m.ABI_VERSION}
    import s4_task_axi_driver as d
    raw = inner.drv.read(d.MODE_CFG)
    return {"mode_b": bool(raw & 1), "hold_policy": bool(raw >> 2 & 1), "tray_exit": bool(raw >> 4 & 1),
            "abi": inner.drv.read(d.ABI)}


def tray_state(port) -> tuple:
    """(tray_ok_task, tray_active) - STATUS[24]/[25] of the tray-exit patch; (False, False) on v0.1.1."""

    inner = getattr(port, "inner", port)
    if hasattr(inner, "model"):
        md = inner.model
        return bool(getattr(md, "tray_ok_task", False)), bool(getattr(md, "tray_active", False))
    raw = inner.drv.read(0x004)
    return bool(raw >> 24 & 1), bool(raw >> 25 & 1)


GRIPPER = 5


def validate_tray_path(tables, cfg, pr) -> tuple:
    """PS-side check of the fixed tray exit path (tray-exit patch) with the S2 v0.2.3 reference, run once
    when the tables are loaded: starts at PRE_DELIVERY, every segment accepted by the S2 START
    validation (continuity, VMAX, AMAX) and inside the joint limits, a pure release segment before the
    last one (arm joints unchanged, gripper opening: the object is let go at rest over the tray, not while
    the arm moves), the last target is HOME.  The PL repeats the
    structural part (PATH_COMMIT scan) and S2 repeats the per-move validation; this check only finds a
    bad table before the first task instead of at the first cancel.  Returns (ok, problems)."""

    first, count = getattr(tables, "tray", (0, 0))
    problems = []
    if count == 0:
        return False, ["empty tray path"]
    pose = tuple(tables.keypoints[cfg.predelivery_kp])
    release = False
    for i in range(first, first + count):
        seg = tables.segment(i)
        if not all(lo <= v <= hi for v, lo, hi in zip(seg.target, cfg.joint_min, cfg.joint_max)):
            problems.append(f"segment {i}: target outside the joint limits")
        mv = pr.MoveParams(pose, tuple(seg.target), seg.n, seg.na, seg.profile, cfg.period_cycles, cfg.stall_cycles,
                           tuple(cfg.vmax), tuple(cfg.amax))
        v = pr.validate(mv, pose)
        if not v.ok:
            problems.append(f"segment {i}: S2 {v.error.name}")
        if i < first + count - 1 and seg.target[:GRIPPER] == pose[:GRIPPER] and seg.target[GRIPPER] > pose[GRIPPER]:
            release = True
        pose = tuple(seg.target)
    if not release:
        problems.append("no pure release segment (arm at rest, gripper opening) before the last segment")
    if pose != tuple(tables.keypoints[cfg.home_kp]):
        problems.append("does not end at HOME")
    return not problems, problems


_ACTIVE = (m.State.PRECHECK, m.State.RUN, m.State.WAIT_PALM, m.State.PAUSED, m.State.STOPPING, m.State.RETRACE)
_CANCEL_EVENTS = {m.Event.PALM_TIMEOUT: "PALM_TIMEOUT", m.Event.HEARTBEAT_TIMEOUT: "PS_HEARTBEAT_TIMEOUT",
                  m.Event.PATH_TIMEOUT: "PATH_WAIT_TIMEOUT"}
_SERVICE_CAUSES = {"pc_cancel": "PC_CANCEL", "cancel_waiting_task": "LINK_LOSS", "no_pc_link": "NO_PC_SESSION"}


class StartupRefused(RuntimeError):
    pass


class TaskOrchestrator:
    def __init__(self, mode: Mode, port: S4Port, service=None, *, log: Optional[EventLog] = None,
                 clock_ns: Callable[[], int] = time.monotonic_ns):
        self.mode = mode
        self.tap = EventTap(port)
        self.service = service
        if service is not None:
            service.port = self.tap
        self.log = log or (service.log if service is not None else EventLog("ps"))
        self.clock_ns = clock_ns
        self.records: dict = {}
        self.current: Optional[int] = None
        self.next_a_id = 1
        self.awaiting_operator: Optional[str] = None
        self._last_state = None
        self._log_seen = 0
        cfg = s4_mode_cfg(port)
        self.s4_cfg = cfg
        if mode == Mode.B and not (cfg["mode_b"] and cfg["hold_policy"]):
            raise StartupRefused("mode B needs S4 MODE_CFG mode_b = 1 and hold_policy = 1 (random items must never be "
                                 "returned to their pick position)")
        if mode == Mode.A and cfg["mode_b"]:
            raise StartupRefused("mode A needs S4 MODE_CFG mode_b = 0")
        if mode == Mode.B and service is None:
            raise StartupRefused("mode B needs the S6 path service")
        self.tray_available = cfg["tray_exit"] and cfg["abi"] in (0x0000_3402,0x0000_3403)
        self.log.emit("orchestrator_start", mode=mode.value, hold_policy=cfg["hold_policy"], tray_exit=cfg["tray_exit"],
                      abi=f"0x{cfg['abi']:08X}", cancel_policy_holding=(
                          "TRAY_EXIT (PL, validated path)" if self.tray_available else
                          "RETURN_TO_SLOT (PL, mode A)" if mode == Mode.A else "HALT (stop and hold, operator)"))

    # ------------------------------------------------------------------ transport pass-through
    def on_connect(self) -> list:
        return self.service.on_connect() if self.service is not None else []

    def on_disconnect(self, reason: str) -> list:
        return self.service.on_disconnect(reason) if self.service is not None else []

    def on_message(self, msg) -> list:
        if self.service is None:
            return []
        return self.service.on_message(msg)

    def take_close_request(self) -> bool:
        return self.service.take_close_request() if self.service is not None else False

    # ------------------------------------------------------------------ operator (explicit only)
    def _operator(self, name: str, cmd: m.Cmd) -> int:
        code = self.tap.command(cmd)
        self.log.emit("operator", self.current, action=name, cmd_result=int(code))
        return code

    def operator_release(self) -> int:
        return self._operator("release", m.Cmd.RELEASE)

    def operator_fault_clear(self) -> int:
        return self._operator("fault_clear", m.Cmd.FAULT_CLEAR)

    def operator_enable(self) -> int:
        code = self._operator("enable", m.Cmd.ENABLE)
        if code == m.CmdReject.ACCEPTED:
            self.awaiting_operator = None
        return code

    def operator_cancel(self) -> int:
        if self.current is not None:
            self.records[self.current].cancel_source = self.records[self.current].cancel_source or "OPERATOR"
        return self._operator("cancel", m.Cmd.CANCEL)

    # ------------------------------------------------------------------ records
    def _new_record(self, task_id: int, obj: int) -> TaskRecord:
        rec = TaskRecord(task_id, self.mode, obj, self.clock_ns())
        self.records[task_id] = rec
        self.current = task_id
        self.log.emit("task_start", task_id, mode=self.mode.value, object=obj)
        return rec

    def _end(self, rec: TaskRecord, outcome: Outcome, snap) -> None:
        rec.outcome, rec.t_end_ns = outcome, self.clock_ns()
        rec.fault, rec.refuse = snap.fault.name, snap.refuse.name
        if outcome not in (Outcome.DONE, Outcome.FAULT, Outcome.REFUSED) and rec.cancel_source is None:
            rec.cancel_source = self._cancel_cause(rec)
        self.log.emit("task_end", rec.task_id, mode=self.mode.value, object=rec.object_id, outcome=outcome.value,
                      cancel_source=rec.cancel_source, fault=rec.fault, refuse=rec.refuse, held=rec.held,
                      tray=rec.tray_seen, t_start_ns=rec.t_start_ns, t_commit_ns=rec.t_commit_ns, t_end_ns=rec.t_end_ns)
        if outcome in (Outcome.HALTED, Outcome.FAULT):
            self.awaiting_operator = outcome.value
            self.log.emit("awaiting_operator", rec.task_id, reason=outcome.value)
        if outcome != Outcome.HALTED:
            self.current = None

    def _cancel_cause(self, rec: TaskRecord) -> str:
        for ev in rec.s4_events:
            if ev in _CANCEL_EVENTS.values():
                return ev
        if self.service is not None:
            for r in self.service.log.records:
                if r.get("task") == rec.task_id and r["ev"] in _SERVICE_CAUSES:
                    return _SERVICE_CAUSES[r["ev"]]
        return "VISION_FIST (inferred: no PS/PC/timeout cause recorded)"

    def _cancel_outcome(self, rec: TaskRecord) -> Outcome:
        if rec.tray_seen:
            return Outcome.TRAY_RETURN
        if not rec.moved:
            return Outcome.CANCELLED_BEFORE_MOTION
        if rec.held and self.mode == Mode.A:
            return Outcome.RETURNED_TO_SLOT
        return Outcome.CANCELLED_HOME

    # ------------------------------------------------------------------ periodic
    def step(self) -> list:
        out = self.service.step() if self.service is not None else []
        evs = self.tap.take()
        snap = self.tap.status()
        tray_ok, tray_active = tray_state(self.tap)
        rec = self.records.get(self.current) if self.current is not None else None
        # task start
        for ev in evs:
            if ev == m.Event.SELECTED and self.mode == Mode.B:
                tid = max(self.service.tasks) if self.service.tasks else 0
                rec = self._new_record(tid, self.service.tasks[tid].object_id if tid else snap.object)
        if self.mode == Mode.A and rec is None and (snap.state in _ACTIVE or
                                                     any(e in (m.Event.TASK_DONE, m.Event.TASK_CANCELLED) for e in evs)):
            rec = self._new_record(self.next_a_id, snap.object)
            self.next_a_id += 1
        if rec is not None and rec.outcome is None:
            rec.s4_events += [e.name for e in evs]
            rec.held |= snap.holding
            rec.tray_seen |= tray_active
            rec.moved |= snap.state in (m.State.RUN, m.State.RETRACE, m.State.STOPPING, m.State.WAIT_PALM)
            if rec.t_commit_ns is None and (m.Event.PATH_ACCEPTED in evs or
                                            (self.mode == Mode.A and snap.state in _ACTIVE)):
                rec.t_commit_ns = self.clock_ns()
                self.log.emit("task_commit", rec.task_id, mode=self.mode.value)
            for ev in evs:
                if ev == m.Event.TASK_DONE:
                    self._end(rec, Outcome.DONE, snap)
                elif ev == m.Event.TASK_CANCELLED:
                    self._end(rec, self._cancel_outcome(rec), snap)
                elif ev == m.Event.TASK_REFUSED:
                    self._end(rec, Outcome.REFUSED, snap)
                elif ev == m.Event.FAULT:
                    self._end(rec, Outcome.FAULT, snap)
                elif ev == m.Event.HALTED:
                    self._end(rec, Outcome.HALTED, snap)
                if rec.outcome is not None:
                    break
        elif m.Event.FAULT in evs:
            self.awaiting_operator = Outcome.FAULT.value
            self.log.emit("fault_without_task", fault=snap.fault.name)
        if self.mode == Mode.A and rec is not None and self.service is not None and self.service.link.name == "SESSION":
            if snap.state != self._last_state or rec.outcome is not None:
                out.append((T.STATUS, (rec.task_id, int(self._a_state(rec, snap)), int(snap.state), int(snap.phase),
                                       int(snap.fault), int(snap.refuse), 0, 0)))
        self._last_state = snap.state
        return out

    @staticmethod
    def _a_state(rec: TaskRecord, snap) -> lp.TaskState:
        return {Outcome.DONE: lp.TaskState.DONE, Outcome.FAULT: lp.TaskState.FAULT, Outcome.REFUSED: lp.TaskState.REFUSED,
                Outcome.HALTED: lp.TaskState.HALTED, None: lp.TaskState.RUNNING}.get(rec.outcome, lp.TaskState.CANCELLED)
