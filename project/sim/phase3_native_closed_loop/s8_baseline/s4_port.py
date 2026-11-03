"""The PS path service's view of the S4 task controller (Phase 3 S6 candidate).

S4Port is the only thing the path service touches.  Two implementations:
  AxiS4Port   the S4 v0.1.1 register window through s4_task_axi_driver (board; NOT_RUN here)
  ModelS4Port the S4 v0.1.1 reference model (s4_task_reference.S4TaskModel + Plant) for the
              same-machine fake PYNQ server and the scenario tests (no RTL, no board)
Both deliver the same observable behaviour to the service: a status snapshot, the S4 events since
the last drain, single commands with their CMD_RESULT code, and a one-shot path commit
(PATH_RESET, FIFO words, PATH_INFO, PATH_COMMIT) whose outcome is the PL's own PATH_ACCEPTED /
PATH_REJECTED event.  Nothing here re-implements an S4 check; the PL stays the final gate.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

import s4_task_reference as m


@dataclass(frozen=True)
class S4Snapshot:
    state: m.State
    phase: m.Phase
    object: int
    holding: bool
    released: bool
    fault_latched: bool
    fault: m.Fault
    refuse: m.Refuse
    s1_mode: int


@dataclass(frozen=True)
class CommitOutcome:
    accepted: bool
    detail: str


class S4Port(ABC):
    @abstractmethod
    def status(self) -> S4Snapshot: ...

    @abstractmethod
    def drain_events(self) -> list: ...

    @abstractmethod
    def command(self, cmd: m.Cmd) -> int: ...

    @abstractmethod
    def commit_path(self, obj: int, s4_task_id: int, segments: Sequence[m.Segment]) -> CommitOutcome: ...


class AxiS4Port(S4Port):
    """Board implementation over S4TaskAxiDriver (proposed base 0x43C5_0000)."""

    def __init__(self, driver, commit_timeout_s: float = 0.05):
        self.drv = driver
        self._acc: list = []
        self.commit_timeout_s = commit_timeout_s

    def status(self) -> S4Snapshot:
        import s4_task_axi_driver as d
        st = self.drv.status()
        fault, _detail, refuse = self.drv.fault()
        s1_mode = (self.drv.read(d.T_S1_STATUS) >> 12) & 3
        return S4Snapshot(st.state, st.phase, st.object, st.holding, st.released, st.fault_latched, fault, refuse, s1_mode)

    def drain_events(self) -> list:
        self._acc += self.drv.events()
        out, self._acc = self._acc, []
        return out

    def command(self, cmd: m.Cmd) -> int:
        return self.drv.command(cmd, check=False)

    def commit_path(self, obj, s4_task_id, segments) -> CommitOutcome:
        import s4_task_axi_driver as d
        if self.command(m.Cmd.PATH_RESET) != m.CmdReject.ACCEPTED:
            return CommitOutcome(False, "PATH_RESET rejected")
        self.drv.write_all(d.fifo_writes(segments))
        fs = self.drv.read(d.FIFO_STATUS)
        if (fs & 0x3F) != len(segments) or (fs >> 6) & 7 or (fs >> 9) & 1:
            return CommitOutcome(False, f"FIFO_STATUS 0x{fs:03X} after {len(segments)} segments")
        self.drv.write(d.PATH_INFO, (s4_task_id & 0xFFFF) << 16 | (obj & 3))
        code = self.command(m.Cmd.PATH_COMMIT)
        if code != m.CmdReject.ACCEPTED:
            return CommitOutcome(False, f"PATH_COMMIT {m.CmdReject(code).name}")
        deadline = time.monotonic() + self.commit_timeout_s
        while True:
            evs = self.drv.events()
            self._acc += evs
            if m.Event.PATH_ACCEPTED in evs:
                return CommitOutcome(True, "PATH_ACCEPTED")
            if m.Event.PATH_REJECTED in evs:
                return CommitOutcome(False, "PATH_REJECTED")
            if time.monotonic() > deadline:
                return CommitOutcome(False, "no PATH_ACCEPTED/PATH_REJECTED event")
            time.sleep(0.001)


class ModelS4Port(S4Port):
    """Reference-model implementation.  A command is applied at the next model tick, so command()
    ticks once (the RTL also needs cycles) and returns the model's CMD_RESULT code."""

    def __init__(self, model: m.S4TaskModel):
        self.model = model
        self.lock = threading.RLock()
        self._ev_seen = 0

    def status(self) -> S4Snapshot:
        with self.lock:
            md = self.model
            return S4Snapshot(md.state, md.phase, md.object, md.holding, md.released, md.fault_latched, md.fault,
                              md.refuse, md.plant.s1_mode)

    def drain_events(self) -> list:
        with self.lock:
            out = self.model.events[self._ev_seen:]
            self._ev_seen = len(self.model.events)
            return list(out)

    def command(self, cmd: m.Cmd) -> int:
        with self.lock:
            n = len(self.model.cmd_results)
            self.model.command(cmd)
            self.model.tick()
            return int(self.model.cmd_results[n][1])

    def commit_path(self, obj, s4_task_id, segments) -> CommitOutcome:
        with self.lock:
            if self.command(m.Cmd.PATH_RESET) != m.CmdReject.ACCEPTED:
                return CommitOutcome(False, "PATH_RESET rejected")
            for s in segments:
                if not self.model.push_fifo(s):
                    return CommitOutcome(False, "FIFO write refused")
            self.model.path_info = (obj, s4_task_id)
            before = len(self.model.events)
            code = self.command(m.Cmd.PATH_COMMIT)
            if code != m.CmdReject.ACCEPTED:
                return CommitOutcome(False, f"PATH_COMMIT {m.CmdReject(code).name}")
            evs = self.model.events[before:]
            if m.Event.PATH_ACCEPTED in evs:
                return CommitOutcome(True, "PATH_ACCEPTED")
            return CommitOutcome(False, "PATH_REJECTED" if m.Event.PATH_REJECTED in evs else "no path event")

    def advance(self, ticks: int, before_tick=None) -> None:
        with self.lock:
            for _ in range(ticks):
                if before_tick is not None:
                    before_tick(self.model)
                self.model.tick()
