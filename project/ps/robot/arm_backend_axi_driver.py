"""PS driver for ``arm_backend_axi_top`` (development ABI 0x0000_3101).

Proposed S1 BD address: 0x43C3_0000 / 4 KiB (not yet implemented in Vivado;
always pass the base address explicitly).

Configuration registers are writable only while MODE=OFF and the engine is
idle.  Any configuration write clears ``config_valid``; ``CONFIG_COMMIT``
re-validates the frame templates in hardware and sets ``config_valid``.  This
write-lock + commit rule gives the same atomicity as a shadow/COMMIT pair
without duplicating ~900 configuration flip-flops.

The PS only loads configuration, selects the mode and reads snapshots.  It
never forwards trajectory samples.  LINE/MONITOR modes need a
``RealOutputPermit`` from ``arm_backend.require_real_output``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from arm_backend import (
    BACKEND_ROARM,
    BACKEND_SO101,
    MODE_DRY_RUN,
    MODE_LINE,
    MODE_MONITOR,
    MODE_OFF,
    PlBackendConfig,
    RealOutputPermit,
)
from arm_feedback import ArmError, decode_pl_errors
from arm_fixed_point import CHANNEL_COUNT, UINT32_MAX, signed32
from arm_profile import RealOutputBlocked


ARM_BACKEND_ABI_VERSION = 0x0000_3101
ARM_BACKEND_MMIO_SIZE = 0x1000
PROPOSED_BASE_ADDRESS = 0x43C3_0000

CONTROL = 0x000
MODE = 0x004
STATUS = 0x008
ERROR_STATUS = 0x00C
ABI_VERSION = 0x010
CAPABILITIES = 0x014
LIMIT_MASK = 0x018
IRQ_ENABLE = 0x01C
BAUD_DIV_ROARM = 0x020
BAUD_DIV_BUS = 0x024
HD_GUARD = 0x028
RESP_TIMEOUT = 0x02C
WD_PRESCALE = 0x030
FEEDBACK_CFG = 0x034
PROGRAM_CFG = 0x038
PRIME_PERIOD = 0x03C
TEMPLATE_ADDR = 0x040
TEMPLATE_DATA = 0x044
KEY_ADDR = 0x048
KEY_DATA = 0x04C
JSON_CFG = 0x050
JSON_KEY_LEN = 0x054
JSON_DISC = 0x058
STS_CFG = 0x05C
CH_BASE = 0x100
CH_STRIDE = 0x20
CH_SOFT_MIN = 0x00
CH_SOFT_MAX = 0x04
CH_ZERO = 0x08
CH_SCALE = 0x0C
CH_FLAGS = 0x10
CH_ARRIVAL_TOL = 0x14
SNAP_FB_DEV = 0x200
SNAP_FB_MASKS = 0x218
SNAP_FB_AGE = 0x21C
SNAP_CMD_DEV = 0x220
SNAP_FB_ERR = 0x238
CNT_FRAMES_TX = 0x300
CNT_FB_OK = 0x304
CNT_FB_ERR = 0x308
CNT_RESP_TIMEOUT = 0x30C
FRAME_CYCLES_LAST = 0x310
FRAME_CYCLES_MAX = 0x314
CNT_LINES_IGNORED = 0x318

CTRL_CONFIG_COMMIT = 1 << 0
CTRL_CLEAR_ERRORS = 1 << 1
CTRL_FB_SNAPSHOT = 1 << 2
CTRL_COUNTER_CLEAR = 1 << 3

ST_CONFIG_VALID = 1 << 0
ST_ENGINE_BUSY = 1 << 1
ST_PERMISSION = 1 << 2
ST_ESTOP_OK = 1 << 3
ST_FAULT = 1 << 4
ST_FEEDBACK_VALID = 1 << 5
ST_SNAPSHOT_VALID = 1 << 6
ST_IRQ = 1 << 7

CAP_HAS_ROARM = 1 << 0
CAP_HAS_SO101 = 1 << 1


@dataclass(frozen=True)
class ArmBackendStatus:
    raw: int
    config_valid: bool
    engine_busy: bool
    permission: bool
    estop_ok: bool
    fault: bool
    feedback_valid: bool
    snapshot_valid: bool
    irq: bool
    core_state: int
    active_mode: int
    active_backend: int


@dataclass(frozen=True)
class ArmBackendSnapshot:
    fb_dev: tuple[int, ...]
    valid_mask: int
    arrival_mask: int
    servo_fault_mask: int
    age_max_ticks: int
    fb_seq: int
    cmd_dev: tuple[int, ...]
    last_servo_error: int
    last_servo_error_id: int


@dataclass(frozen=True)
class ArmBackendCounters:
    frames_tx: int
    fb_ok: int
    fb_err: int
    resp_timeouts: int
    frame_cycles_last: int
    frame_cycles_max: int
    lines_ignored: int


class ArmBackendAxiError(RuntimeError):
    def __init__(self, raw: int):
        self.raw = raw & UINT32_MAX
        names = ", ".join(code.name for code in decode_pl_errors(self.raw)) or "unknown"
        super().__init__(f"arm backend error 0x{self.raw:08X}: {names}")


class ArmBackendAxiDriver:
    def __init__(
        self,
        mmio,
        *,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        if not hasattr(mmio, "read") or not hasattr(mmio, "write"):
            raise TypeError("mmio must provide read(offset) and write(offset, value)")
        self.mmio = mmio
        self._sleep = sleeper
        self._monotonic = monotonic

    @classmethod
    def from_pynq(cls, base_address: int) -> "ArmBackendAxiDriver":
        if not isinstance(base_address, int) or base_address < 0:
            raise ValueError("base_address must be a non-negative integer")
        try:
            from pynq import MMIO
        except ImportError as exc:  # pragma: no cover - PYNQ only
            raise RuntimeError("from_pynq() must run on a PYNQ image") from exc
        return cls(MMIO(base_address, ARM_BACKEND_MMIO_SIZE))

    # ---------------------------------------------------------------- basics
    def read(self, offset: int) -> int:
        return int(self.mmio.read(offset)) & UINT32_MAX

    def write(self, offset: int, value: int) -> None:
        self.mmio.write(offset, int(value) & UINT32_MAX)

    def assert_abi(self) -> None:
        actual = self.read(ABI_VERSION)
        if actual != ARM_BACKEND_ABI_VERSION:
            raise RuntimeError(
                f"arm backend ABI mismatch: expected 0x{ARM_BACKEND_ABI_VERSION:08X}, got 0x{actual:08X}"
            )

    def capabilities(self) -> dict[str, int | bool]:
        raw = self.read(CAPABILITIES)
        return {
            "has_roarm": bool(raw & CAP_HAS_ROARM),
            "has_so101": bool(raw & CAP_HAS_SO101),
            "template_depth": 1 << ((raw >> 8) & 0xF),
            "json_slots": (raw >> 12) & 0xF,
            "max_status_params": (raw >> 16) & 0xF,
            "min_baud_div": (raw >> 20) & 0xFF,
        }

    def status(self) -> ArmBackendStatus:
        raw = self.read(STATUS)
        return ArmBackendStatus(
            raw=raw,
            config_valid=bool(raw & ST_CONFIG_VALID),
            engine_busy=bool(raw & ST_ENGINE_BUSY),
            permission=bool(raw & ST_PERMISSION),
            estop_ok=bool(raw & ST_ESTOP_OK),
            fault=bool(raw & ST_FAULT),
            feedback_valid=bool(raw & ST_FEEDBACK_VALID),
            snapshot_valid=bool(raw & ST_SNAPSHOT_VALID),
            irq=bool(raw & ST_IRQ),
            core_state=(raw >> 8) & 0xF,
            active_mode=(raw >> 12) & 0x3,
            active_backend=(raw >> 14) & 0x1,
        )

    def errors(self) -> list[ArmError]:
        return decode_pl_errors(self.read(ERROR_STATUS))

    def raise_for_error(self) -> None:
        raw = self.read(ERROR_STATUS)
        if raw:
            raise ArmBackendAxiError(raw)

    # --------------------------------------------------------------- config
    def _wait_idle_off(self, timeout_s: float = 1.0) -> None:
        deadline = self._monotonic() + timeout_s
        while True:
            state = self.status()
            if state.active_mode == MODE_OFF and not state.engine_busy:
                return
            if self._monotonic() >= deadline:
                raise TimeoutError("arm backend did not reach OFF/idle")
            self._sleep(0.0001)

    def load_config(self, config: PlBackendConfig) -> None:
        """Write the complete configuration image (MODE must be OFF)."""

        self.write(MODE, MODE_OFF | (config.backend_sel << 4))
        self._wait_idle_off()
        self.write(BAUD_DIV_ROARM, config.baud_div_roarm)
        self.write(BAUD_DIV_BUS, config.baud_div_bus)
        self.write(HD_GUARD, (config.hd_lead_cycles & 0xFFFF) | ((config.hd_lag_cycles & 0xFFFF) << 16))
        self.write(RESP_TIMEOUT, config.response_timeout_cycles)
        self.write(WD_PRESCALE, config.wd_prescale)
        self.write(
            FEEDBACK_CFG,
            (config.feedback_timeout_ticks & 0xFFFF)
            | ((config.arrival_count & 0xF) << 16)
            | ((config.required_mask & 0x3F) << 24),
        )
        image = config.template
        self.write(
            PROGRAM_CFG,
            (image.cmd_base & 0xFF)
            | ((image.req_base & 0xFF) << 8)
            | (int(image.req_enable) << 16)
            | ((config.reads_per_cycle & 0x7) << 17),
        )
        self.write(PRIME_PERIOD, config.prime_period_cycles)
        self.write(TEMPLATE_ADDR, 0)
        for word in image.ram:
            self.write(TEMPLATE_DATA, word)
        if config.json is not None:
            parser = config.json.parser
            self.write(KEY_ADDR, 0)
            for byte in parser.key_ram():
                self.write(KEY_DATA, byte)
            self.write(JSON_CFG, config.json.cfg_word())
            self.write(JSON_KEY_LEN, parser.key_len_word())
            self.write(JSON_DISC, parser.discriminator_value & UINT32_MAX)
        if config.sts is not None:
            self.write(STS_CFG, config.sts.word())
        for channel, channel_map in enumerate(config.channel_maps):
            base = CH_BASE + CH_STRIDE * channel
            self.write(base + CH_SOFT_MIN, channel_map.soft_min_q16 & UINT32_MAX)
            self.write(base + CH_SOFT_MAX, channel_map.soft_max_q16 & UINT32_MAX)
            self.write(base + CH_ZERO, channel_map.zero_dev & UINT32_MAX)
            self.write(base + CH_SCALE, channel_map.scale_uq16_16)
            self.write(base + CH_FLAGS, int(channel_map.dir_neg) | (channel_map.device_id << 8))
            self.write(base + CH_ARRIVAL_TOL, channel_map.arrival_tol_dev)

    def commit_config(self, *, timeout_s: float = 0.1) -> None:
        self.write(CONTROL, CTRL_CONFIG_COMMIT)
        deadline = self._monotonic() + timeout_s
        while True:
            state = self.status()
            if state.config_valid and not state.engine_busy:
                return
            if not state.engine_busy and self.read(ERROR_STATUS) & (1 << ArmError.CONFIG_INVALID_COMMIT):
                raise ArmBackendAxiError(self.read(ERROR_STATUS))
            if self._monotonic() >= deadline:
                raise TimeoutError("CONFIG_COMMIT did not complete")
            self._sleep(0.0001)

    # ----------------------------------------------------------------- mode
    def set_mode(
        self,
        mode: int,
        *,
        backend: int,
        arm: bool = False,
        permit: RealOutputPermit | None = None,
    ) -> None:
        if mode not in (MODE_OFF, MODE_DRY_RUN, MODE_MONITOR, MODE_LINE):
            raise ValueError(f"invalid mode {mode}")
        if backend not in (BACKEND_ROARM, BACKEND_SO101):
            raise ValueError(f"invalid backend {backend}")
        if mode in (MODE_MONITOR, MODE_LINE) and permit is None:
            raise RealOutputBlocked(["MONITOR/LINE drive physical pins and require a RealOutputPermit"])
        if mode == MODE_LINE and arm and permit is not None and permit.purpose == "robot_readonly":
            raise RealOutputBlocked(["a read-only permit cannot arm motion"])
        self.write(MODE, mode | (backend << 4) | (int(arm) << 8))

    def stop(self) -> None:
        """Drop ARM and return to OFF (current frame completes)."""

        raw = self.read(MODE)
        self.write(MODE, raw & ~((1 << 8) | 0x3))

    def clear_errors(self) -> None:
        self.write(CONTROL, CTRL_CLEAR_ERRORS)

    def clear_counters(self) -> None:
        self.write(CONTROL, CTRL_COUNTER_CLEAR)

    # ------------------------------------------------------------ readback
    def snapshot(self) -> ArmBackendSnapshot:
        self.write(CONTROL, CTRL_FB_SNAPSHOT)
        masks = self.read(SNAP_FB_MASKS)
        age = self.read(SNAP_FB_AGE)
        err = self.read(SNAP_FB_ERR)
        return ArmBackendSnapshot(
            fb_dev=tuple(signed32(self.read(SNAP_FB_DEV + 4 * ch)) for ch in range(CHANNEL_COUNT)),
            valid_mask=masks & 0x3F,
            arrival_mask=(masks >> 8) & 0x3F,
            servo_fault_mask=(masks >> 16) & 0x3F,
            age_max_ticks=age & 0xFFFF,
            fb_seq=(age >> 16) & 0xFFFF,
            cmd_dev=tuple(signed32(self.read(SNAP_CMD_DEV + 4 * ch)) for ch in range(CHANNEL_COUNT)),
            last_servo_error=err & 0xFF,
            last_servo_error_id=(err >> 8) & 0xFF,
        )

    def counters(self) -> ArmBackendCounters:
        return ArmBackendCounters(
            frames_tx=self.read(CNT_FRAMES_TX),
            fb_ok=self.read(CNT_FB_OK),
            fb_err=self.read(CNT_FB_ERR),
            resp_timeouts=self.read(CNT_RESP_TIMEOUT),
            frame_cycles_last=self.read(FRAME_CYCLES_LAST),
            frame_cycles_max=self.read(FRAME_CYCLES_MAX),
            lines_ignored=self.read(CNT_LINES_IGNORED),
        )

    def limit_mask(self) -> int:
        """Sticky per-channel soft-limit mask (bits 5:0); cleared by CLEAR_ERRORS."""

        return self.read(LIMIT_MASK) & 0x3F
