"""PYNQ PS path service: AI PC -> PS -> S4 one-shot path commit (Phase 3 S6 candidate, mode B).

PathServiceCore is transport-agnostic: the TCP server below and the in-memory transport of the
S7 scenarios feed it decoded messages and send what it returns.  It owns
  * the link state  DOWN -> CONNECTED (TCP up) -> SESSION (HELLO versions agree) -> DOWN;
  * the task table  one task per S4 SELECTED event (PS task id = own u32 sequence; the S4 task id of
    a vision-selected task is 0, as in S4 v0.1.1), states phase3_link_protocol.TaskState;
  * the commit rule a PATH_SUBMIT is taken only as one complete message, only for the task that is
    waiting, only once: link in SESSION -> task waiting (else DUPLICATE for a committed task id,
    NO_TASK otherwise) -> object matches -> full contract check with the PS's own HOME,
    PRE_DELIVERY, limits and S2 reference (digest recomputed) -> real-arm gate when the S1 backend is
    in LINE -> S4 still in WAIT_PATH for that object -> PATH_RESET, FIFO, PATH_INFO, PATH_COMMIT;
    the PL answer (PATH_ACCEPTED / PATH_REJECTED) is the result.  Nothing is sent per sample.
  * link loss (BYE, socket closed, protocol error, no PC traffic for link_timeout_s): a task that is
    still waiting for a path is cancelled in S4 at once (no path can come); a committed task keeps
    running on its PL-held path (the operator still has FIST / PALM); while the link is down every new
    SELECTED task is cancelled immediately (mode B sends no new task without a PC).
  * the PS -> S4 heartbeat (S4 HEARTBEAT command) that proves the PS process is alive; it is
    independent of the PC link.
Every decision is written to the event log (phase3_event_log).
"""

from __future__ import annotations

import selectors
import socket
import threading
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, Optional

import phase3_link_protocol as lp
import phase3_path_contract as pc
import s4_task_reference as m
from phase3_event_log import EventLog
from s4_port import S4Port

T = lp.MsgType
ROLE_PC, ROLE_PS = 1, 2
MODE_B = 2


class LinkState(IntEnum):
    DOWN = 0
    CONNECTED = 1
    SESSION = 2


@dataclass(frozen=True)
class ServiceConfig:
    home: tuple
    pre_delivery: tuple
    limits: pc.MotionLimits
    path_deadline_ms: int
    accepted_calibrations: frozenset = frozenset()   # calibration ids approved after a measured run; empty = none
    link_timeout_s: float = 2.0
    heartbeat_interval_s: float = 0.5
    s4_heartbeat_interval_s: float = 0.0             # 0 = do not send (S4 T_HEARTBEAT off)


@dataclass
class Task:
    task_id: int
    object_id: int
    s4_task_id: int
    state: lp.TaskState
    t_selected_ns: int
    events: list = field(default_factory=list)


_S4_TO_TASK = {m.State.WAIT_PATH: lp.TaskState.WAIT_PATH, m.State.PRECHECK: lp.TaskState.COMMITTED,
               m.State.RUN: lp.TaskState.RUNNING, m.State.WAIT_PALM: lp.TaskState.RUNNING,
               m.State.PAUSED: lp.TaskState.RUNNING, m.State.STOPPING: lp.TaskState.RUNNING,
               m.State.RETRACE: lp.TaskState.RUNNING, m.State.HALT: lp.TaskState.HALTED}
_TERMINAL = {m.Event.TASK_DONE: lp.TaskState.DONE, m.Event.TASK_CANCELLED: lp.TaskState.CANCELLED,
             m.Event.TASK_REFUSED: lp.TaskState.REFUSED, m.Event.FAULT: lp.TaskState.FAULT}
_FINAL = (lp.TaskState.DONE, lp.TaskState.CANCELLED, lp.TaskState.REFUSED, lp.TaskState.FAULT)
_COMMITTED = (lp.TaskState.COMMITTED, lp.TaskState.RUNNING, lp.TaskState.DONE, lp.TaskState.HALTED)


class PathServiceCore:
    def __init__(self, port: S4Port, cfg: ServiceConfig, pr, *, log: Optional[EventLog] = None,
                 clock: Callable[[], float] = time.monotonic):
        self.port, self.cfg, self.pr, self.clock = port, cfg, pr, clock
        self.log = log or EventLog("ps")
        self.link = LinkState.DOWN
        self.tasks: dict = {}
        self.current: Optional[int] = None
        self.next_task_id = 1
        self.committed_ids: set = set()
        self._last_rx = self._last_hb_tx = self._last_s4_hb = 0.0
        self._last_state = None
        self._close_requested = False

    # ------------------------------------------------------------------ helpers
    def _status_msg(self, task: Task, events: int = 0) -> tuple:
        snap = self.port.status()
        return (T.STATUS, (task.task_id, int(task.state), int(snap.state), int(snap.phase), int(snap.fault),
                           int(snap.refuse), 0, events & 0xFFFF))

    def _set_state(self, task: Task, state: lp.TaskState, why: str, out: list, events: int = 0) -> None:
        if task.state == state and not events:
            return
        task.state = state
        self.log.emit("task_state", task.task_id, state=state.name, why=why)
        if self.link == LinkState.SESSION:
            out.append(self._status_msg(task, events))
        if state in _FINAL and self.current == task.task_id:
            self.current = None

    def take_close_request(self) -> bool:
        c, self._close_requested = self._close_requested, False
        return c

    # ------------------------------------------------------------------ link
    def on_connect(self) -> list:
        self.link, self._last_rx = LinkState.CONNECTED, self.clock()
        self.log.emit("link_connected")
        return []

    def on_disconnect(self, reason: str) -> list:
        out: list = []
        if self.link == LinkState.DOWN:
            return out
        self.link = LinkState.DOWN
        self.log.emit("link_down", reason=reason)
        task = self.tasks.get(self.current) if self.current is not None else None
        if task is not None and task.state == lp.TaskState.WAIT_PATH:
            code = self.port.command(m.Cmd.CANCEL)
            self.log.emit("cancel_waiting_task", task.task_id, reason="link lost", cmd_result=code)
        elif task is not None:
            self.log.emit("committed_task_continues", task.task_id, state=task.state.name)
        return out

    def _result(self, tid: int, res: lp.PathResult, problem: int = 0, detail: int = 0) -> tuple:
        self.log.emit("path_result", tid, result=res.name, problem=problem, detail=detail)
        return (T.PATH_RESULT, (tid & 0xFFFF_FFFF, int(res), problem & 0xFF, detail & 0xFFFF))

    def on_message(self, msg: lp.Message) -> list:
        self._last_rx = self.clock()
        t = msg.type
        if t == T.HELLO:
            role, interp, cver = msg.fields
            if role != ROLE_PC or interp != pc.INTERP_VERSION or cver != pc.CONTRACT_VERSION:
                self.log.emit("hello_rejected", role=role, interp=interp, contract=cver)
                self._close_requested = True
                return [(T.BYE, ())]
            self.link = LinkState.SESSION
            self.log.emit("session", interp=interp, contract=cver)
            return [(T.HELLO, (ROLE_PS, pc.INTERP_VERSION, pc.CONTRACT_VERSION)),
                    (T.LIMITS, lp.limits_fields(self.cfg.limits))]
        if t == T.HEARTBEAT:
            return []
        if t == T.BYE:
            self._close_requested = True
            return []
        if t == T.PATH_SUBMIT:
            return self._on_submit(msg.fields[0])
        if t == T.CANCEL:
            return self._on_cancel(msg.fields[0])
        # PS -> PC message types arriving at the PS: protocol violation
        raise lp.LinkError(f"{t.name} is not a PC -> PS message")

    def _on_cancel(self, tid: int) -> list:
        task = self.tasks.get(tid)
        if task is None or task.task_id != self.current:
            self.log.emit("cancel_no_task", tid)
            return []
        code = self.port.command(m.Cmd.CANCEL)
        self.log.emit("pc_cancel", tid, cmd_result=code)
        return []

    def _on_submit(self, payload: bytes) -> list:
        plan = lp.decode_plan(payload, self.cfg.home)
        tid = plan.task_id
        self.log.emit("path_received", tid, object=plan.object_id, segments=len(plan.segments), bytes=len(payload))
        if self.link != LinkState.SESSION:
            return [self._result(tid, lp.PathResult.LINK_STATE)]
        task = self.tasks.get(tid)
        if task is None or task.state != lp.TaskState.WAIT_PATH or tid != self.current:
            dup = tid in self.committed_ids or (task is not None and task.state in _COMMITTED)
            return [self._result(tid, lp.PathResult.DUPLICATE if dup else lp.PathResult.NO_TASK)]
        if plan.object_id != task.object_id:
            return [self._result(tid, lp.PathResult.WRONG_OBJECT, 0, plan.object_id)]
        r = pc.check(plan, self.cfg.limits, self.cfg.home, self.cfg.pre_delivery, self.pr)
        if not r.ok:
            first = r.problems[0]
            return [self._result(tid, lp.PathResult.REJECTED, int(first[0]), first[1] & 0xFFFF)]
        snap = self.port.status()
        if snap.s1_mode == m.S1_MODE_LINE:
            calib = "CALIBRATED" if plan.calib_id in self.cfg.accepted_calibrations else "NOT_APPROVED"
            ok, reasons = pc.executable_on_real_arm(plan, self.cfg.limits, calib)
            if not ok:
                self.log.emit("not_executable", tid, reasons=reasons)
                return [self._result(tid, lp.PathResult.NOT_EXECUTABLE)]
        if snap.state != m.State.WAIT_PATH or snap.object != task.object_id:
            return [self._result(tid, lp.PathResult.NO_TASK, 0, int(snap.state))]
        segs = [m.Segment(tuple(s.target), s.n, s.na, s.profile, s.flags) for s in plan.segments]
        outcome = self.port.commit_path(task.object_id, task.s4_task_id, segs)
        self.log.emit("pl_commit", tid, accepted=outcome.accepted, detail=outcome.detail, samples=r.samples)
        if not outcome.accepted:
            return [self._result(tid, lp.PathResult.PL_REJECTED)]
        self.committed_ids.add(tid)
        out = [self._result(tid, lp.PathResult.COMMITTED)]
        self._set_state(task, lp.TaskState.COMMITTED, "PATH_ACCEPTED", out)
        return out

    # ------------------------------------------------------------------ periodic
    def step(self) -> list:
        out: list = []
        now = self.clock()
        if self.cfg.s4_heartbeat_interval_s and now - self._last_s4_hb >= self.cfg.s4_heartbeat_interval_s:
            self.port.command(m.Cmd.HEARTBEAT)
            self._last_s4_hb = now
        if self.link != LinkState.DOWN and now - self._last_rx > self.cfg.link_timeout_s:
            self.log.emit("link_timeout", silent_s=round(now - self._last_rx, 3))
            self._close_requested = True
            out += self.on_disconnect("heartbeat timeout")
        if self.link == LinkState.SESSION and now - self._last_hb_tx >= self.cfg.heartbeat_interval_s:
            out.append((T.HEARTBEAT, ()))
            self._last_hb_tx = now
        evs = self.port.drain_events()
        snap = self.port.status()
        mask = 0
        for ev in evs:
            mask |= 1 << int(ev)
        for ev in evs:
            self.log.emit("s4_event", self.current, event=ev.name, s4_state=snap.state.name)
            if ev == m.Event.SELECTED:
                out += self._on_selected(snap)
            elif ev in _TERMINAL and self.current is not None:
                self._set_state(self.tasks[self.current], _TERMINAL[ev], ev.name, out, mask)
        task = self.tasks.get(self.current) if self.current is not None else None
        if task is not None and snap.state in _S4_TO_TASK:
            want = _S4_TO_TASK[snap.state]
            if want != task.state and not (want == lp.TaskState.WAIT_PATH and task.state != lp.TaskState.WAIT_PATH):
                self._set_state(task, want, snap.state.name, out)
        return out

    def _on_selected(self, snap) -> list:
        out: list = []
        tid = self.next_task_id
        self.next_task_id = (self.next_task_id + 1) & 0xFFFF_FFFF or 1
        task = Task(tid, snap.object, 0, lp.TaskState.WAIT_PATH, self.log.clock())
        self.tasks[tid] = task
        self.current = tid
        self.log.emit("task_selected", tid, object=snap.object)
        if self.link != LinkState.SESSION:
            code = self.port.command(m.Cmd.CANCEL)
            self.log.emit("no_pc_link", tid, action="S4 CANCEL", cmd_result=code)
            self._set_state(task, lp.TaskState.CANCELLED, "no PC session", out)
            return out
        c = self.cfg
        out.append((T.TARGET_REQUEST, (tid, snap.object, MODE_B, *c.home, *c.pre_delivery, c.limits.period_cycles,
                                       c.path_deadline_ms)))
        self.log.emit("target_request", tid, object=snap.object)
        return out


# ---------------------------------------------------------------------- TCP transport
class TcpPathServer:
    """Single-client TCP server around PathServiceCore (one PC).  A second connection while one is
    open is answered with BYE and closed.  board_step(), if given, is called every loop turn before
    core.step() (the fake board advances its model there)."""

    def __init__(self, core: PathServiceCore, host: str = "127.0.0.1", port: int = 0,
                 board_step: Optional[Callable[[], None]] = None, loop_period_s: float = 0.001):
        self.core, self.board_step, self.loop_period_s = core, board_step, loop_period_s
        self.listener = socket.create_server((host, port))
        self.listener.setblocking(False)
        self.address = self.listener.getsockname()
        self.sel = selectors.DefaultSelector()
        self.sel.register(self.listener, selectors.EVENT_READ, "listen")
        self.conn: Optional[socket.socket] = None
        self.parser = lp.FrameParser()
        self.seq = 0
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None

    def _send(self, msgs: list) -> None:
        if self.conn is None:
            return
        try:
            for mtype, fields in msgs:
                self.seq += 1
                self.conn.sendall(lp.encode(mtype, self.seq, fields))
        except OSError as exc:
            self._drop(f"send failed: {exc}")

    def _drop(self, reason: str) -> None:
        if self.conn is not None:
            try:
                self.sel.unregister(self.conn)
            except (KeyError, ValueError):
                pass
            self.conn.close()
            self.conn = None
        self.core.on_disconnect(reason)

    def _accept(self) -> None:
        c, _addr = self.listener.accept()
        if self.conn is not None:
            c.sendall(lp.encode(T.BYE, 0))
            c.close()
            self.core.log.emit("second_client_refused")
            return
        c.setblocking(False)
        self.conn, self.parser = c, lp.FrameParser()
        self.sel.register(c, selectors.EVENT_READ, "conn")
        self._send(self.core.on_connect())

    def _read(self) -> None:
        try:
            data = self.conn.recv(65536)
        except BlockingIOError:
            return
        except OSError as exc:
            return self._drop(f"recv failed: {exc}")
        if not data:
            return self._drop("peer closed")
        try:
            msgs = self.parser.feed(data)
            for msg in msgs:
                self._send(self.core.on_message(msg))
                if self.conn is None:
                    return
        except lp.LinkError as exc:
            self.core.log.emit("protocol_error", detail=str(exc))
            self._send([(T.BYE, ())])
            return self._drop(f"protocol error: {exc}")
        if self.core.take_close_request():
            self._drop("closed by service")

    def serve(self) -> None:
        while not self.stop_event.is_set():
            for key, _ev in self.sel.select(timeout=self.loop_period_s):
                if key.data == "listen":
                    self._accept()
                elif self.conn is not None:
                    self._read()
            if self.board_step is not None:
                self.board_step()
            self._send(self.core.step())
            if self.core.take_close_request() and self.conn is not None:
                self._drop("closed by service")
        if self.conn is not None:
            self._drop("server stopped")
        self.sel.close()
        self.listener.close()

    def start(self) -> "TcpPathServer":
        self.thread = threading.Thread(target=self.serve, name="ps-path-server", daemon=True)
        self.thread.start()
        return self

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=5)
