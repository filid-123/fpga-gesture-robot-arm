"""PS driver for the Phase 3 trajectory AXI4-Lite development ABI.

The driver intentionally requires an explicit base address because the RTL has
not yet been integrated into a Block Design.  It transports signed Q16.16 joint
values only; conversion to a real RoArm command remains a separate, unfrozen
hardware-adapter layer.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Sequence


TRAJECTORY_ABI_VERSION = 0x0000_3001
# S1: same register map, but the sample stream is consumed by the PL arm
# backend (EXTERNAL_SAMPLE_SINK=1).  The sample window stays readable as a
# monitor; SAMPLE_POP returns SLVERR.
TRAJECTORY_ABI_VERSION_EXT_SINK = 0x0000_3002
TRAJECTORY_MMIO_SIZE = 0x1000

CONTROL = 0x00
STATUS = 0x04
ERROR_STATUS = 0x08
ABI_VERSION = 0x0C
IRQ_ENABLE = 0x10
PERIOD_SHADOW = 0x14
MIN_PERIOD_CYCLES = 0x18
START_CH0 = 0x20
TARGET_CH0 = 0x40
SAMPLE_CH0 = 0x60
SAMPLE_META = 0x78

CTRL_COMMIT = 1 << 0
CTRL_SAMPLE_POP = 1 << 1
CTRL_DONE_CLEAR = 1 << 2

STATUS_BUSY = 1 << 0
STATUS_CMD_READY = 1 << 1
STATUS_SAMPLE_VALID = 1 << 2
STATUS_SAMPLE_LAST = 1 << 3
STATUS_DONE = 1 << 4
STATUS_IRQ = 1 << 5
STATUS_ERROR = 1 << 6

META_INDEX_MASK = 0x3F
META_LAST = 1 << 8
META_VALID = 1 << 9
META_BUSY = 1 << 10

INT32_MIN = -(1 << 31)
INT32_MAX = (1 << 31) - 1

ERROR_NAMES = (
    "scheduler_invalid_period",
    "fill_protocol",
    "deadline_miss",
    "core",
    "commit_while_busy",
    "pop_empty",
    "axi_access",
    "control_conflict",
    "commit_invalid_period",
)


class TrajectoryAxiError(RuntimeError):
    """The trajectory AXI block reports a sticky hardware error."""

    def __init__(self, raw: int):
        self.raw = int(raw) & 0xFFFF_FFFF
        active = [name for bit, name in enumerate(ERROR_NAMES) if self.raw & (1 << bit)]
        detail = ", ".join(active) if active else "unknown"
        super().__init__(f"trajectory AXI error 0x{self.raw:08X}: {detail}")


@dataclass(frozen=True)
class TrajectoryStatus:
    raw: int
    busy: bool
    command_ready: bool
    sample_valid: bool
    sample_last: bool
    done: bool
    irq: bool
    error: bool
    sample_index: int


@dataclass(frozen=True)
class TrajectorySample:
    index: int
    last: bool
    joints_q16_16: tuple[int, int, int, int, int, int]


def _signed32(value: int) -> int:
    word = int(value) & 0xFFFF_FFFF
    return word - (1 << 32) if word & 0x8000_0000 else word


def _validate_joint_vector(values: Sequence[int], *, name: str) -> tuple[int, ...]:
    if len(values) != 6:
        raise ValueError(f"{name} must contain exactly six joints")
    checked: list[int] = []
    for channel, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name}[{channel}] must be a signed Q16.16 integer")
        if value < INT32_MIN or value > INT32_MAX:
            raise ValueError(f"{name}[{channel}] is outside signed 32-bit range")
        checked.append(value)
    return tuple(checked)


class TrajectoryAxiDriver:
    def __init__(
        self,
        mmio,
        *,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        expected_abi: int = TRAJECTORY_ABI_VERSION,
    ):
        if not hasattr(mmio, "read") or not hasattr(mmio, "write"):
            raise TypeError("mmio must provide read(offset) and write(offset, value)")
        if expected_abi not in (TRAJECTORY_ABI_VERSION, TRAJECTORY_ABI_VERSION_EXT_SINK):
            raise ValueError(f"unsupported trajectory ABI 0x{expected_abi:08X}")
        self.mmio = mmio
        self._sleep = sleeper
        self._monotonic = monotonic
        self.expected_abi = expected_abi

    @property
    def external_sink(self) -> bool:
        return self.expected_abi == TRAJECTORY_ABI_VERSION_EXT_SINK

    @classmethod
    def from_pynq(cls, base_address: int, *, expected_abi: int = TRAJECTORY_ABI_VERSION):
        """Construct from PYNQ MMIO after the future BD assigns a base address."""

        if not isinstance(base_address, int) or base_address < 0:
            raise ValueError("base_address must be a non-negative integer")
        try:
            from pynq import MMIO
        except ImportError as exc:  # pragma: no cover - only available on PYNQ
            raise RuntimeError("from_pynq() must run on a PYNQ image") from exc
        return cls(MMIO(base_address, TRAJECTORY_MMIO_SIZE), expected_abi=expected_abi)

    def read(self, offset: int) -> int:
        return int(self.mmio.read(offset)) & 0xFFFF_FFFF

    def write(self, offset: int, value: int) -> None:
        self.mmio.write(offset, int(value) & 0xFFFF_FFFF)

    def assert_abi(self) -> None:
        actual = self.read(ABI_VERSION)
        if actual != self.expected_abi:
            raise RuntimeError(
                f"Trajectory ABI mismatch: expected 0x{self.expected_abi:08X}, "
                f"got 0x{actual:08X}"
            )

    def status(self) -> TrajectoryStatus:
        raw = self.read(STATUS)
        return TrajectoryStatus(
            raw=raw,
            busy=bool(raw & STATUS_BUSY),
            command_ready=bool(raw & STATUS_CMD_READY),
            sample_valid=bool(raw & STATUS_SAMPLE_VALID),
            sample_last=bool(raw & STATUS_SAMPLE_LAST),
            done=bool(raw & STATUS_DONE),
            irq=bool(raw & STATUS_IRQ),
            error=bool(raw & STATUS_ERROR),
            sample_index=(raw >> 8) & META_INDEX_MASK,
        )

    def error_status(self) -> int:
        return self.read(ERROR_STATUS)

    def raise_for_error(self) -> None:
        raw = self.error_status()
        if raw:
            raise TrajectoryAxiError(raw)

    def configure_irq(self, *, done: bool, error: bool) -> None:
        self.write(IRQ_ENABLE, (1 if done else 0) | (2 if error else 0))

    def wait_ready(self, *, timeout_s: float = 1.0, poll_s: float = 0.0001) -> None:
        deadline = self._monotonic() + timeout_s
        while True:
            state = self.status()
            if state.error:
                self.raise_for_error()
            if state.command_ready:
                return
            if self._monotonic() >= deadline:
                raise TimeoutError("timeout waiting for trajectory command readiness")
            self._sleep(poll_s)

    def submit_q16_16(
        self,
        start: Sequence[int],
        target: Sequence[int],
        period_cycles: int,
        *,
        wait_ready: bool = False,
        timeout_s: float = 1.0,
    ) -> None:
        start_words = _validate_joint_vector(start, name="start")
        target_words = _validate_joint_vector(target, name="target")
        if isinstance(period_cycles, bool) or not isinstance(period_cycles, int):
            raise TypeError("period_cycles must be an integer")
        minimum = self.read(MIN_PERIOD_CYCLES)
        if period_cycles < minimum or period_cycles > 0xFFFF_FFFF:
            raise ValueError(
                f"period_cycles must be in [{minimum}, 4294967295], got {period_cycles}"
            )

        if wait_ready:
            self.wait_ready(timeout_s=timeout_s)
        else:
            state = self.status()
            if state.error:
                self.raise_for_error()
            if not state.command_ready:
                raise RuntimeError("trajectory command interface is busy")

        for channel, value in enumerate(start_words):
            self.write(START_CH0 + 4 * channel, value)
        for channel, value in enumerate(target_words):
            self.write(TARGET_CH0 + 4 * channel, value)
        self.write(PERIOD_SHADOW, period_cycles)

        # Recheck the command boundary after all shadow writes. This also keeps
        # a second software producer from silently turning COMMIT into SLVERR.
        state = self.status()
        if state.error:
            self.raise_for_error()
        if not state.command_ready:
            raise RuntimeError("trajectory interface became busy before COMMIT")
        self.write(CONTROL, CTRL_COMMIT)

    def wait_sample(
        self, *, timeout_s: float = 1.0, poll_s: float = 0.0001
    ) -> TrajectorySample:
        deadline = self._monotonic() + timeout_s
        while True:
            meta = self.read(SAMPLE_META)
            if meta & META_VALID:
                return self.read_sample()
            state = self.status()
            if state.error:
                self.raise_for_error()
            if self._monotonic() >= deadline:
                raise TimeoutError("timeout waiting for trajectory sample")
            self._sleep(poll_s)

    def read_sample(self) -> TrajectorySample:
        before = self.read(SAMPLE_META)
        if not before & META_VALID:
            raise RuntimeError("no valid trajectory sample is available")
        index = before & META_INDEX_MASK
        if index < 1 or index > 32:
            raise RuntimeError(f"invalid trajectory sample index {index}")

        joints = tuple(_signed32(self.read(SAMPLE_CH0 + 4 * channel)) for channel in range(6))
        after = self.read(SAMPLE_META)
        if after != before:
            raise RuntimeError("trajectory sample metadata changed during MMIO read")

        return TrajectorySample(
            index=index,
            last=bool(before & META_LAST),
            joints_q16_16=joints,  # type: ignore[arg-type]
        )

    def pop_sample(self) -> None:
        if self.external_sink:
            raise RuntimeError("the PL arm backend owns the sample stream; SAMPLE_POP is disabled")
        if not self.read(SAMPLE_META) & META_VALID:
            raise RuntimeError("cannot POP an empty trajectory sample window")
        self.write(CONTROL, CTRL_SAMPLE_POP)

    def consume_sample(self, *, timeout_s: float = 1.0) -> TrajectorySample:
        sample = self.wait_sample(timeout_s=timeout_s)
        self.pop_sample()
        return sample

    def clear_done(self) -> None:
        self.write(CONTROL, CTRL_DONE_CLEAR)

