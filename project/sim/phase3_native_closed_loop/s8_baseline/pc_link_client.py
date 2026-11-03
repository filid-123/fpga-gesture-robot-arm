"""AI PC side of the PC <-> PYNQ link (Phase 3 S6 candidate, protocol v1).

PcLinkClient: blocking TCP client with a receive timeout; HELLO handshake (receives the PS HELLO
and the LIMITS the PS will check against); PATH_SUBMIT, CANCEL, HEARTBEAT, BYE; wait_for() keeps
sending heartbeats while it waits.  A PS silent for longer than link_timeout_s is a LinkError.
"""

from __future__ import annotations

import socket
import time
from typing import Callable, Optional

import phase3_link_protocol as lp
import phase3_path_contract as pc

T = lp.MsgType
ROLE_PC, ROLE_PS = 1, 2


class PcLinkClient:
    def __init__(self, host: str, port: int, *, heartbeat_interval_s: float = 0.3, link_timeout_s: float = 2.0,
                 log=None):
        self.addr = (host, port)
        self.hb_interval, self.link_timeout_s, self.log = heartbeat_interval_s, link_timeout_s, log
        self.sock: Optional[socket.socket] = None
        self.parser = lp.FrameParser()
        self.inbox: list = []
        self.seq = 0
        self.limits: Optional[pc.MotionLimits] = None
        self._last_tx = self._last_rx = 0.0

    def _emit(self, ev: str, task=None, **kw) -> None:
        if self.log is not None:
            self.log.emit(ev, task, **kw)

    def connect(self, timeout_s: float = 2.0) -> "PcLinkClient":
        self.sock = socket.create_connection(self.addr, timeout=timeout_s)
        self.sock.settimeout(0.02)
        self._last_rx = time.monotonic()
        return self

    def send(self, mtype: lp.MsgType, fields: tuple = ()) -> None:
        self.seq += 1
        self.sock.sendall(lp.encode(mtype, self.seq, fields))
        self._last_tx = time.monotonic()

    def hello(self, timeout_s: float = 2.0, interp: int = pc.INTERP_VERSION, contract: int = pc.CONTRACT_VERSION) -> None:
        self.send(T.HELLO, (ROLE_PC, interp, contract))
        h = self.wait_for(lambda msg: msg.type in (T.HELLO, T.BYE), timeout_s)
        if h.type == T.BYE:
            raise lp.LinkError("PS refused the session (version mismatch)")
        if h.fields[0] != ROLE_PS or h.fields[1] != interp or h.fields[2] != contract:
            raise lp.LinkError(f"PS HELLO {h.fields} does not match")
        lim = self.wait_for(lambda msg: msg.type == T.LIMITS, timeout_s)
        self.limits = lp.limits_from_fields(lim.fields)
        self._emit("session", limits_status=self.limits.status)

    def submit(self, plan: pc.PathPlan) -> None:
        self.send(T.PATH_SUBMIT, (plan,))
        self._emit("path_submitted", plan.task_id, segments=len(plan.segments))

    def cancel(self, task_id: int) -> None:
        self.send(T.CANCEL, (task_id,))
        self._emit("cancel_sent", task_id)

    def bye(self) -> None:
        try:
            self.send(T.BYE)
        finally:
            self.close()

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def _pump(self) -> None:
        try:
            data = self.sock.recv(65536)
        except socket.timeout:
            data = None
        except OSError as exc:                      # reset / aborted by the peer
            raise lp.LinkError(f"connection lost: {exc}") from exc
        if data == b"":
            raise lp.LinkError("PS closed the connection")
        if data:
            self._last_rx = time.monotonic()
            self.inbox += self.parser.feed(data)
        now = time.monotonic()
        if now - self._last_tx >= self.hb_interval:
            self.send(T.HEARTBEAT)
        if now - self._last_rx > self.link_timeout_s:
            raise lp.LinkError("PS silent: link timeout")

    def wait_for(self, pred: Callable[[lp.Message], bool], timeout_s: float) -> lp.Message:
        """First inbox message matching pred (earlier non-matching messages stay in the inbox)."""

        deadline = time.monotonic() + timeout_s
        while True:
            for i, msg in enumerate(self.inbox):
                if pred(msg):
                    return self.inbox.pop(i)
            if time.monotonic() > deadline:
                raise TimeoutError("no matching message")
            self._pump()

    def status_until(self, task_id: int, states: set, timeout_s: float) -> lp.Message:
        return self.wait_for(lambda msg: msg.type == T.STATUS and msg.fields[0] == task_id
                             and lp.TaskState(msg.fields[1]) in states, timeout_s)
