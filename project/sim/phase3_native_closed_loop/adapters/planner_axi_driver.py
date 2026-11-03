"""NativeMotion PS driver: S2 ABI 0x3202 at 0x43C40000.

Only S2 produces trajectory samples. SOURCE_SELECT resets/reads as 1;
source 0 has no S1 cubic trajectory semantics. Motion buffering, accepted
LAST_DELIVERED, backend permissions, and configuration write locks remain.
Legacy S1 software is available only with the frozen old BIT/HWH and driver.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from planner_p2p_reference import (
    CHANNEL_COUNT,
    FATAL_ERRORS,
    MoveParams,
    PlannerError,
    PlannerState,
)

PLANNER_ABI_VERSION = 0x0000_3202
PLANNER_MMIO_SIZE = 0x1000
PROPOSED_BASE_ADDRESS = 0x43C4_0000

CONTROL = 0x000
STATUS = 0x004
ERROR_STATUS = 0x008
ABI_VERSION = 0x00C
CAPABILITIES = 0x010
IRQ_ENABLE = 0x014
SOURCE_SELECT = 0x018
SAMPLE_INDEX = 0x01C
LATE_COUNT = 0x020
N_SAMPLES = 0x040
ACCEL_SAMPLES = 0x044
PROFILE = 0x048
PERIOD_CYCLES = 0x04C
STALL_TIMEOUT = 0x050
CH_BASE = 0x100
CH_STRIDE = 0x20
CH_START = 0x00
CH_TARGET = 0x04
CH_VMAX = 0x08
CH_AMAX = 0x0C
LAST_DELIVERED = 0x200

CMD_START = 1 << 0
CMD_PAUSE = 1 << 1
CMD_RESUME = 1 << 2
CMD_ESTOP = 1 << 3
CMD_CLEAR = 1 << 4

SOURCE_S1_TRAJECTORY = 0
SOURCE_S2_PLANNER = 1

IRQ_DONE = 1 << 0
IRQ_ERROR = 1 << 1


class PlannerAxiError(RuntimeError):
    def __init__(self, raw: int, channel: int):
        self.raw = raw & 0x3FF
        self.channel = channel
        names = ", ".join(e.name for e in decode_errors(self.raw)) or "unknown"
        super().__init__(f"planner error 0x{self.raw:03X} (channel {channel}): {names}")


def decode_errors(raw: int) -> list[PlannerError]:
    return [e for e in PlannerError if raw & (1 << int(e))]


def move_register_writes(move: MoveParams) -> list[tuple[int, int]]:
    """Register writes of one move (planner idle); START is not included."""

    writes = [(N_SAMPLES, move.n_samples), (ACCEL_SAMPLES, move.accel_samples), (PROFILE, move.profile),
              (PERIOD_CYCLES, move.period_cycles), (STALL_TIMEOUT, move.stall_timeout_cycles)]
    for ch in range(CHANNEL_COUNT):
        base = CH_BASE + CH_STRIDE * ch
        writes += [(base + CH_START, move.start[ch] & 0xFFFF_FFFF), (base + CH_TARGET, move.target[ch] & 0xFFFF_FFFF),
                   (base + CH_VMAX, move.vmax_q16[ch]), (base + CH_AMAX, move.amax_q32[ch])]
    return writes


@dataclass(frozen=True)
class PlannerStatus:
    raw: int
    state: PlannerState
    busy: bool
    computing: bool
    planner_pending: bool
    trajectory_pending: bool
    last_valid: bool
    source: int
    done: bool
    irq: bool
    trajectory_segment_open: bool
    planner_moved: bool
    error_channel: int


def _signed32(value: int) -> int:
    value &= 0xFFFF_FFFF
    return value - (1 << 32) if value & 0x8000_0000 else value


class PlannerAxiDriver:
    def __init__(self, mmio, *, sleeper: Callable[[float], None] = time.sleep,
                 monotonic: Callable[[], float] = time.monotonic):
        if not hasattr(mmio, "read") or not hasattr(mmio, "write"):
            raise TypeError("mmio must provide read(offset) and write(offset, value)")
        self.mmio = mmio
        self._sleep = sleeper
        self._monotonic = monotonic

    @classmethod
    def from_pynq(cls, base_address: int) -> "PlannerAxiDriver":
        if not isinstance(base_address, int) or base_address < 0:
            raise ValueError("base_address must be a non-negative integer")
        try:
            from pynq import MMIO
        except ImportError as exc:  # pragma: no cover - PYNQ only
            raise RuntimeError("from_pynq() must run on a PYNQ image") from exc
        return cls(MMIO(base_address, PLANNER_MMIO_SIZE))

    def read(self, offset: int) -> int:
        return int(self.mmio.read(offset)) & 0xFFFF_FFFF

    def write(self, offset: int, value: int) -> None:
        self.mmio.write(offset, int(value) & 0xFFFF_FFFF)

    def assert_abi(self) -> None:
        actual = self.read(ABI_VERSION)
        if actual != PLANNER_ABI_VERSION:
            raise RuntimeError(f"planner ABI mismatch: expected 0x{PLANNER_ABI_VERSION:08X}, got 0x{actual:08X}")

    def capabilities(self) -> dict[str, int]:
        raw = self.read(CAPABILITIES)
        return {"channels": raw & 0xF, "profiles_mask": (raw >> 4) & 0x3, "sample_bits": (raw >> 8) & 0xFF,
                "min_period_cycles": (raw >> 16) & 0xFFFF}

    def status(self) -> PlannerStatus:
        raw = self.read(STATUS)
        return PlannerStatus(raw=raw, state=PlannerState(raw & 0x7), busy=bool(raw & (1 << 3)),
                             computing=bool(raw & (1 << 4)), planner_pending=bool(raw & (1 << 5)),
                             trajectory_pending=bool(raw & (1 << 6)), last_valid=bool(raw & (1 << 7)),
                             source=(raw >> 8) & 1, done=bool(raw & (1 << 9)), irq=bool(raw & (1 << 10)),
                             trajectory_segment_open=bool(raw & (1 << 11)), planner_moved=bool(raw & (1 << 12)),
                             error_channel=(raw >> 16) & 0x7)

    def errors(self) -> list[PlannerError]:
        return decode_errors(self.read(ERROR_STATUS))

    def raise_for_fatal(self) -> None:
        raw = self.read(ERROR_STATUS)
        if any(e in FATAL_ERRORS for e in decode_errors(raw)):
            raise PlannerAxiError(raw, self.status().error_channel)

    def last_delivered(self) -> tuple[int, ...] | None:
        """Current commanded position (last sample the arm backend accepted)."""

        if not self.status().last_valid:
            return None
        return tuple(_signed32(self.read(LAST_DELIVERED + 4 * ch)) for ch in range(CHANNEL_COUNT))

    def select_source(self, source: int) -> None:
        if source not in (SOURCE_S1_TRAJECTORY, SOURCE_S2_PLANNER):
            raise ValueError("source must be 0 (S1 trajectory) or 1 (S2 planner)")
        self.write(SOURCE_SELECT, source)
        if (self.read(SOURCE_SELECT) & 1) != source:
            s = self.status()
            if source == SOURCE_S2_PLANNER:
                why = "S1 sample offered" if s.trajectory_pending else "S1 segment still running"
            elif s.busy or s.planner_pending:
                why = f"planner {s.state.name}{' with a sample pending' if s.planner_pending else ''}"
            elif s.trajectory_pending and s.planner_moved:
                why = "an S1 segment committed for an old position is waiting (PL reset needed)"
            else:
                why = "refused"
            raise RuntimeError(f"SOURCE_SELECT refused: {why}")

    def load_move(self, move: MoveParams) -> None:
        status = self.status()
        if status.busy:
            raise RuntimeError(f"planner busy ({status.state.name}); parameters are write-locked")
        for offset, value in move_register_writes(move):
            self.write(offset, value)

    def command(self, bit: int) -> None:
        self.write(CONTROL, bit)

    def start(self) -> None:
        self.command(CMD_START)

    def pause(self) -> None:
        self.command(CMD_PAUSE)

    def resume(self) -> None:
        self.command(CMD_RESUME)

    def estop(self) -> None:
        self.command(CMD_ESTOP)

    def clear(self) -> None:
        self.command(CMD_CLEAR)

    def wait_state(self, states: set[PlannerState], timeout_s: float, poll_s: float = 0.001) -> PlannerStatus:
        deadline = self._monotonic() + timeout_s
        while True:
            status = self.status()
            if status.state in states:
                return status
            if self._monotonic() >= deadline:
                raise TimeoutError(f"planner stayed in {status.state.name}")
            self._sleep(poll_s)

    def run_move(self, move: MoveParams, *, timeout_s: float) -> PlannerStatus:
        """Load, START and wait for DONE (raises on a fatal error)."""

        self.load_move(move)
        self.start()
        status = self.wait_state({PlannerState.DONE, PlannerState.ERROR, PlannerState.ESTOP}, timeout_s)
        if status.state is not PlannerState.DONE:
            self.raise_for_fatal()
        return status
