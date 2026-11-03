"""Unified feedback, arrival, timeout and error model shared by both arms.

* ``ArmFeedback``: the common feedback record (guide 05 section 5).  Positions
  are carried both in device units (what the PL holds) and in Q16.16 rad
  (PS/PC conversion with ``arm_fixed_point.map_device_to_rad_q16``).
* ``ArmError``: one error taxonomy.  Values below 16 are the PL
  ``ERROR_STATUS`` bit numbers of ``arm_backend_axi_top`` (ABI 0x0000_3101);
  values from 32 are PS/PC-only conditions.
* ``FeedbackWatchdogModel``: event-level model of ``arm_feedback_watchdog.v``.
* ``PermissionGateModel``: cycle-level model of ``arm_motion_permission_gate.v``.

Feedback timeout blocks further motion frames; the last feedback is never
extrapolated.  No observer or filter is implemented in S1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Sequence

from arm_fixed_point import CHANNEL_COUNT, ChannelMap, map_device_to_rad_q16


class ArmError(IntEnum):
    # --- PL ERROR_STATUS bit numbers (arm_backend_axi_top) ---
    LIMIT_VIOLATION = 0
    ENCODE_SATURATION = 1
    TEMPLATE_ERROR = 2
    CONFIG_INVALID_COMMIT = 3
    CONFIG_WRITE_LOCKED = 4
    AXI_ACCESS = 5
    UART_FRAMING = 6
    RX_OVERRUN = 7
    RX_CHECKSUM = 8
    RX_PROTOCOL = 9
    RESPONSE_TIMEOUT = 10
    FEEDBACK_TIMEOUT = 11
    ESTOP_EVENT = 12
    SERVO_FAULT = 13
    CONTROL_CONFLICT = 14
    # --- PS/PC-only conditions ---
    CONFIG_INCOMPLETE = 32
    REAL_OUTPUT_BLOCKED = 33
    PROTOCOL_FIELD_MISSING = 34
    SERIAL_OPEN_FAILED = 35
    SERIAL_WRITE_TIMEOUT = 36
    HOST_FEEDBACK_TIMEOUT = 37


PL_FATAL_ERRORS = frozenset(
    {
        ArmError.LIMIT_VIOLATION,
        ArmError.ENCODE_SATURATION,
        ArmError.TEMPLATE_ERROR,
        ArmError.FEEDBACK_TIMEOUT,
        ArmError.ESTOP_EVENT,
        ArmError.SERVO_FAULT,
    }
)
PL_ERROR_MASK = 0x7FFF
PL_FATAL_MASK = sum(1 << int(code) for code in PL_FATAL_ERRORS)


def decode_pl_errors(raw: int) -> list[ArmError]:
    return [code for code in ArmError if int(code) < 16 and raw & (1 << int(code))]


@dataclass(frozen=True)
class ArmFeedback:
    sample_seq: int
    rx_tick: int
    position_device: tuple[int | None, ...]
    position_q16_16: tuple[int | None, ...]
    valid_mask: int
    moving_mask: int | None
    fault_mask: int
    transport_ok: bool
    feedback_age_ticks: int

    @classmethod
    def from_device(
        cls,
        *,
        sample_seq: int,
        rx_tick: int,
        position_device: Sequence[int | None],
        channel_maps: Sequence[ChannelMap] | None,
        fault_mask: int = 0,
        moving_mask: int | None = None,
        transport_ok: bool = True,
        feedback_age_ticks: int = 0,
    ) -> "ArmFeedback":
        if len(position_device) != CHANNEL_COUNT:
            raise ValueError("six channels are required")
        rad: list[int | None] = []
        mask = 0
        for channel, value in enumerate(position_device):
            if value is None:
                rad.append(None)
                continue
            mask |= 1 << channel
            if channel_maps is None:
                rad.append(None)
            else:
                rad.append(map_device_to_rad_q16(value, channel_maps[channel])[0])
        return cls(
            sample_seq=sample_seq,
            rx_tick=rx_tick,
            position_device=tuple(position_device),
            position_q16_16=tuple(rad),
            valid_mask=mask,
            moving_mask=moving_mask,
            fault_mask=fault_mask,
            transport_ok=transport_ok,
            feedback_age_ticks=feedback_age_ticks,
        )


@dataclass(frozen=True)
class WatchdogConfig:
    timeout_ticks: int
    arrival_count: int
    required_mask: int
    tolerance_dev: tuple[int, ...]

    def __post_init__(self) -> None:
        if not 0 <= self.timeout_ticks <= 0xFFFF:
            raise ValueError("timeout_ticks must fit in 16 bits")
        if not 1 <= self.arrival_count <= 15:
            raise ValueError("arrival_count must be 1..15")
        if not 0 <= self.required_mask <= 0x3F:
            raise ValueError("required_mask must be 6 bits")
        if len(self.tolerance_dev) != CHANNEL_COUNT or any(not 0 <= t <= 0xFFFF for t in self.tolerance_dev):
            raise ValueError("six 16-bit tolerances are required")


@dataclass(frozen=True)
class WatchdogState:
    ages: tuple[int, ...]
    valid_mask: int
    arrival_mask: int
    timeout: bool
    age_max: int
    fb_seq: int
    fb_dev: tuple[int, ...]


@dataclass
class FeedbackWatchdogModel:
    """Event-level model: every event completes before the next one is applied."""

    config: WatchdogConfig
    enabled: bool = False
    ages: list[int] = field(default_factory=lambda: [0] * CHANNEL_COUNT)
    arrival_counts: list[int] = field(default_factory=lambda: [0] * CHANNEL_COUNT)
    valid_mask: int = 0
    arrival_mask: int = 0
    fb_seq: int = 0
    fb_dev: list[int] = field(default_factory=lambda: [0] * CHANNEL_COUNT)
    cmd_dev: list[int] = field(default_factory=lambda: [0] * CHANNEL_COUNT)

    def set_enable(self, enable: bool) -> None:
        self.enabled = enable
        if not enable:
            self.ages = [0] * CHANNEL_COUNT
            self.arrival_counts = [0] * CHANNEL_COUNT
            self.valid_mask = 0
            self.arrival_mask = 0

    def tick(self) -> None:
        if not self.enabled:
            return
        self.ages = [min(age + 1, 0xFFFF) for age in self.ages]

    def command(self, values: Sequence[int]) -> None:
        self.cmd_dev = list(values)
        if not self.enabled:
            return
        self.arrival_counts = [0] * CHANNEL_COUNT
        self.arrival_mask = 0

    def update(self, mask: int, values: Sequence[int]) -> None:
        if not self.enabled:
            return
        for channel in range(CHANNEL_COUNT):
            if not mask & (1 << channel):
                continue
            self.fb_dev[channel] = values[channel]
            self.ages[channel] = 0
            self.valid_mask |= 1 << channel
            within = abs(values[channel] - self.cmd_dev[channel]) <= self.config.tolerance_dev[channel]
            self.arrival_counts[channel] = min(self.arrival_counts[channel] + 1, 15) if within else 0
            if self.arrival_counts[channel] >= self.config.arrival_count:
                self.arrival_mask |= 1 << channel
            else:
                self.arrival_mask &= ~(1 << channel)
        self.fb_seq = (self.fb_seq + 1) & 0xFFFF

    def state(self) -> WatchdogState:
        required = [ch for ch in range(CHANNEL_COUNT) if self.config.required_mask & (1 << ch)]
        age_max = max((self.ages[ch] for ch in required), default=0)
        timeout = self.enabled and any(self.ages[ch] > self.config.timeout_ticks for ch in required)
        return WatchdogState(
            ages=tuple(self.ages),
            valid_mask=self.valid_mask,
            arrival_mask=self.arrival_mask,
            timeout=timeout,
            age_max=age_max,
            fb_seq=self.fb_seq,
            fb_dev=tuple(self.fb_dev),
        )


@dataclass
class PermissionGateModel:
    """Cycle-level model of the motion permission gate.

    ``estop_ok`` asserts only after the synchronized input has been high for
    ``debounce_cycles`` consecutive cycles and drops on the first low cycle.
    """

    debounce_cycles: int
    sync1: int = 0
    sync2: int = 0
    counter: int = 0
    estop_ok: int = 0
    estop_event: int = 0

    def step(self, raw_in: int, *, line_mode: int, arm: int) -> None:
        next_event = int(bool(self.estop_ok and not self.sync2 and line_mode and arm))
        if not self.sync2:
            next_ok, next_counter = 0, 0
        elif not self.estop_ok:
            if self.counter == self.debounce_cycles - 1:
                next_ok, next_counter = 1, self.counter
            else:
                next_ok, next_counter = 0, self.counter + 1
        else:
            next_ok, next_counter = 1, self.counter
        self.sync2, self.sync1 = self.sync1, int(bool(raw_in))
        self.estop_ok, self.counter, self.estop_event = next_ok, next_counter, next_event

    @staticmethod
    def permission(estop_ok: int, *, line_mode: int, arm: int, config_valid: int, fault: int) -> int:
        return int(bool(line_mode and arm and config_valid and not fault and estop_ok))
