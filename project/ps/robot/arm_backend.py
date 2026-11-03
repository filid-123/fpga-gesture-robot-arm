"""Common arm-backend layer: PL configuration image, PL reference model, gate.

Data flow (S1, PL path)::

    PS: keyframe segment (start/target Q16.16) --COMMIT--> trajectory scheduler (PL)
    PL: 32 smoothstep samples --ready/valid--> arm_backend_core
        -> arm_joint_unit_mapper (limits, direction, zero, scale)
        -> arm_frame_formatter (CHECK pass, then EMIT) -> UART / half-duplex bus
        <- UART RX -> JSON key parser | Feetech status parser -> feedback watchdog

The PS never interpolates and never forwards per-sample data; it only loads
configuration, commits keyframe segments and reads status snapshots.

``ArmBackendPlModel`` reproduces the PL byte stream for golden vectors.  The
PC/PS bring-up path (pyserial, dry-run by default) lives in
``roarm_serial_transport.py`` and ``so101_serial_transport.py``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import arm_frame_template as aft
from arm_fixed_point import CHANNEL_COUNT, ChannelMap, map_joint_vector
from arm_profile import ArmProfile, ProfileError, RealOutputBlocked
from roarm_json_reference import JsonParserConfig, RoArmJsonProtocol, compile_template
from so101_feetech_reference import (
    FeetechProtocol,
    StatusParserConfig,
    compile_read_request_template,
    compile_sync_write_template,
)
import roarm_binary_bridge_reference as bridge


PL_CLOCK_HZ = 100_000_000
MIN_BAUD_DIV = 16
MAX_BAUD_ERROR = 0.02
WATCHDOG_TICK_CYCLES = 100_000     # 1 ms at 100 MHz
DEFAULT_PRIME_PERIOD_MS = 20.0

BACKEND_ROARM = 0
BACKEND_SO101 = 1

MODE_OFF = 0
MODE_DRY_RUN = 1
MODE_MONITOR = 2
MODE_LINE = 3


def baud_divisor(baudrate: int, clock_hz: int = PL_CLOCK_HZ) -> int:
    divisor = int(round(clock_hz / baudrate))
    if divisor < MIN_BAUD_DIV or divisor > 0xFFFF:
        raise ProfileError(f"baud {baudrate} needs divisor {divisor}, allowed {MIN_BAUD_DIV}..65535")
    error = abs(clock_hz / divisor - baudrate) / baudrate
    if error > MAX_BAUD_ERROR:
        raise ProfileError(f"baud {baudrate}: divisor error {error:.2%} exceeds {MAX_BAUD_ERROR:.0%}")
    return divisor


def us_to_cycles(value_us: float, clock_hz: int = PL_CLOCK_HZ) -> int:
    return int(math.ceil(value_us * clock_hz / 1_000_000))


def ms_to_cycles(value_ms: float, clock_hz: int = PL_CLOCK_HZ) -> int:
    return int(math.ceil(value_ms * clock_hz / 1000))


@dataclass(frozen=True)
class StsPlConfig:
    header0: int
    header1: int
    read_len: int
    encoding: int
    big_endian: bool
    ck_invert: bool

    def word(self) -> int:
        return (
            self.header0
            | (self.header1 << 8)
            | ((self.read_len & 0x7) << 16)
            | ((self.encoding & 0x3) << 20)
            | (int(self.big_endian) << 22)
            | (int(self.ck_invert) << 23)
        )


@dataclass(frozen=True)
class JsonPlConfig:
    parser: JsonParserConfig

    def cfg_word(self) -> int:
        p = self.parser
        return (p.fraction_digits & 0x7) | (p.line_terminator << 8) | (p.max_line_length << 16)


@dataclass(frozen=True)
class PlBackendConfig:
    """Everything ``ArmBackendAxiDriver.load_config`` writes, as integers."""

    backend_sel: int
    channel_maps: tuple[ChannelMap, ...]
    template: aft.TemplateImage
    baud_div_roarm: int
    baud_div_bus: int
    hd_lead_cycles: int
    hd_lag_cycles: int
    response_timeout_cycles: int
    wd_prescale: int
    feedback_timeout_ticks: int
    arrival_count: int
    required_mask: int
    prime_period_cycles: int
    reads_per_cycle: int = 1
    json: JsonPlConfig | None = None
    sts: StsPlConfig | None = None
    source: str = ""

    def __post_init__(self) -> None:
        if len(self.channel_maps) != CHANNEL_COUNT:
            raise ProfileError("six channel maps are required")
        for label in ("baud_div_roarm", "baud_div_bus"):
            if not MIN_BAUD_DIV <= getattr(self, label) <= 0xFFFF:
                raise ProfileError(f"{label} must be {MIN_BAUD_DIV}..65535")
        if self.required_mask and (self.feedback_timeout_ticks == 0 or self.arrival_count == 0):
            raise ProfileError("feedback timeout and arrival count must be non-zero when feedback is required")
        if self.backend_sel == BACKEND_SO101 and self.sts is None:
            raise ProfileError("SO-ARM101 backend needs the STS parser configuration")
        if self.backend_sel == BACKEND_ROARM and self.required_mask and self.json is None:
            raise ProfileError("RoArm feedback requires the JSON parser configuration")
        if not 1 <= self.reads_per_cycle <= CHANNEL_COUNT:
            raise ProfileError("reads_per_cycle must be 1..6")
        # PL field widths (arm_backend_axi_top): 24-bit timers, 20-bit prescaler.
        for label, limit in (("response_timeout_cycles", 0xFF_FFFF), ("prime_period_cycles", 0xFF_FFFF),
                             ("hd_lead_cycles", 0xFFFF), ("hd_lag_cycles", 0xFFFF)):
            if not 0 <= getattr(self, label) <= limit:
                raise ProfileError(f"{label} exceeds the PL register width (max {limit})")
        if not 1 <= self.wd_prescale <= 0xF_FFFF:
            raise ProfileError("wd_prescale must be 1..1048575 cycles (20-bit PL register)")

    @property
    def device_ids(self) -> tuple[int, ...]:
        return tuple(m.device_id for m in self.channel_maps)


def _common_timing(profile: ArmProfile, *, prime_period_ms: float) -> dict[str, int]:
    if profile.transport.baudrate is None:
        raise ProfileError("transport.baudrate is TBD")
    if profile.feedback_timeout_ms is None and profile.required_feedback_channels:
        raise ProfileError("timeouts.feedback_timeout_ms is TBD")
    if profile.arrival_consecutive is None and profile.required_feedback_channels:
        raise ProfileError("feedback.arrival_consecutive is TBD")
    required = 0
    for channel in profile.required_feedback_channels:
        required |= 1 << channel
    ticks = 0
    if profile.feedback_timeout_ms is not None:
        ticks = int(math.ceil(profile.feedback_timeout_ms * PL_CLOCK_HZ / 1000 / WATCHDOG_TICK_CYCLES))
        if ticks > 0xFFFF:
            raise ProfileError("feedback timeout exceeds the 16-bit tick counter")
    return {
        "reads_per_cycle": max(1, len(profile.required_feedback_channels)),
        "wd_prescale": WATCHDOG_TICK_CYCLES,
        "feedback_timeout_ticks": ticks,
        "arrival_count": profile.arrival_consecutive or 0,
        "required_mask": required,
        "prime_period_cycles": ms_to_cycles(prime_period_ms),
    }


def build_pl_config(
    profile: ArmProfile,
    protocol: RoArmJsonProtocol | FeetechProtocol,
    *,
    prime_period_ms: float = DEFAULT_PRIME_PERIOD_MS,
) -> PlBackendConfig:
    """Translate a numerically complete profile + protocol into PL register values.

    This does **not** grant real output; it also serves DRY_RUN on the board.
    Missing values raise ``ProfileError`` / ``ProtocolFieldMissing``.
    """

    maps = profile.channel_maps()
    timing = _common_timing(profile, prime_period_ms=prime_period_ms)
    divisor = baud_divisor(profile.transport.baudrate)  # type: ignore[arg-type]
    if profile.backend == "roarm_m3_json":
        if not isinstance(protocol, RoArmJsonProtocol):
            raise ProfileError("roarm_m3_json needs a RoArm JSON protocol file")
        if profile.device_encoding.fraction_digits != protocol.fraction_digits:
            raise ProfileError("profile device_encoding.fraction_digits must equal the protocol fraction_digits")
        request = compile_template(protocol, "feedback_request") if protocol.commands.get("feedback_request") else None
        image = aft.TemplateImage.build(compile_template(protocol, "set_joints"), request)
        json_cfg = None
        if protocol.feedback_fraction_digits is not None:
            json_cfg = JsonPlConfig(JsonParserConfig.from_protocol(protocol))
        return PlBackendConfig(
            backend_sel=BACKEND_ROARM,
            channel_maps=maps,
            template=image,
            baud_div_roarm=divisor,
            baud_div_bus=divisor,
            hd_lead_cycles=0,
            hd_lag_cycles=0,
            response_timeout_cycles=0,
            json=json_cfg,
            source=f"{profile.path.name} + {protocol.protocol_id}",
            **timing,
        )
    if profile.backend == "roarm_m3_binary_bridge":
        image = aft.TemplateImage.build(bridge.compile_command_template())
        return PlBackendConfig(
            backend_sel=BACKEND_ROARM,
            channel_maps=maps,
            template=image,
            baud_div_roarm=divisor,
            baud_div_bus=divisor,
            hd_lead_cycles=0,
            hd_lag_cycles=0,
            response_timeout_cycles=0,
            source=f"{profile.path.name} + {bridge.BRIDGE_PROTOCOL}",
            **{**timing, "required_mask": 0, "reads_per_cycle": 1},
        )
    if not isinstance(protocol, FeetechProtocol):
        raise ProfileError("so101_feetech needs a Feetech protocol file")
    if profile.transport.half_duplex_lead_us is None or profile.transport.half_duplex_lag_us is None:
        raise ProfileError("half-duplex lead/lag are TBD")
    if profile.response_timeout_ms is None:
        raise ProfileError("timeouts.response_timeout_ms is TBD")
    if any(m.device_id == 0 and j.device_id is None for m, j in zip(maps, profile.joints, strict=True)):
        raise ProfileError("SO-ARM101 device ids are TBD")
    image = aft.TemplateImage.build(
        compile_sync_write_template(protocol), compile_read_request_template(protocol)
    )
    refresh_ticks = ms_to_cycles(prime_period_ms) / WATCHDOG_TICK_CYCLES
    if timing["required_mask"] and refresh_ticks >= timing["feedback_timeout_ticks"]:
        raise ProfileError("prime period must be shorter than the feedback timeout")
    parser = StatusParserConfig.from_protocol(protocol)
    sts = StsPlConfig(parser.header0, parser.header1, parser.expected_nparams,
                      parser.encoding, parser.big_endian, parser.ck_invert)
    return PlBackendConfig(
        backend_sel=BACKEND_SO101,
        channel_maps=maps,
        template=image,
        baud_div_roarm=divisor,
        baud_div_bus=divisor,
        hd_lead_cycles=us_to_cycles(profile.transport.half_duplex_lead_us),
        hd_lag_cycles=us_to_cycles(profile.transport.half_duplex_lag_us),
        response_timeout_cycles=ms_to_cycles(profile.response_timeout_ms),
        sts=sts,
        source=f"{profile.path.name} + {protocol.protocol_id}",
        **timing,
    )


def feedback_refresh_ok(config: PlBackendConfig, sample_period_cycles: int, *, margin: float = 2.0) -> bool:
    """True when every required channel is refreshed well inside the timeout.

    With ``reads_per_cycle`` READs per motion sample, a channel is refreshed
    every ``ceil(n_required / reads_per_cycle)`` samples.  The PS must choose
    the trajectory period so this interval (times ``margin``) stays below the
    feedback timeout, otherwise the PL will (correctly) fault on timeout.
    """

    required = bin(config.required_mask).count("1")
    if required == 0:
        return True
    reads = config.reads_per_cycle if config.backend_sel == BACKEND_SO101 else CHANNEL_COUNT
    samples_per_refresh = -(-required // reads)
    refresh_cycles = samples_per_refresh * max(sample_period_cycles, 1)
    return refresh_cycles * margin < config.feedback_timeout_ticks * config.wd_prescale


# --------------------------------------------------------------------------
# PL sequencing reference model
# --------------------------------------------------------------------------
def first_required(mask: int) -> int:
    for channel in range(CHANNEL_COUNT):
        if mask & (1 << channel):
            return channel
    return 0


def next_required(current: int, mask: int) -> int:
    for step in range(1, CHANNEL_COUNT + 1):
        channel = (current + step) % CHANNEL_COUNT
        if mask & (1 << channel):
            return channel
    return current


@dataclass
class FrameResult:
    """``accepted`` mirrors the PL sample handshake: the PL maps and CHECKs the
    sample while it is still held by ready/valid and only handshakes it when a
    frame will be sent, so a faulting sample is never consumed."""

    accepted: bool
    fault: str | None
    cmd: bytes = b""
    req: bytes = b""
    rr_channel: int | None = None
    rr_channels: tuple[int, ...] = ()
    device_values: tuple[int, ...] = ()
    limit_mask: int = 0


@dataclass
class ArmBackendPlModel:
    """Byte-exact model of arm_backend_core for DRY_RUN and LINE after PRIME."""

    config: PlBackendConfig
    frames_tx: int = 0
    rr_channel: int = 0
    faulted: str | None = None
    log: list[FrameResult] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.rr_channel = first_required(self.config.required_mask)

    @property
    def request_enabled(self) -> bool:
        return self.config.template.req_enable and (
            self.config.backend_sel == BACKEND_ROARM or self.config.required_mask != 0
        )

    def request_frame(self) -> tuple[bytes, int]:
        """One REQ frame for the current round-robin channel, then advance."""

        channel = self.rr_channel
        data = aft.run_program(
            self.config.template.ram,
            self.config.template.req_base,
            device_values=(0,) * CHANNEL_COUNT,
            device_ids=self.config.device_ids,
            rr_channel=channel,
        ).data
        self.rr_channel = next_required(channel, self.config.required_mask)
        return data, channel

    def poll_cycle(self) -> tuple[bytes, tuple[int, ...]]:
        """One request-only cycle (PRIME / idle polling in MONITOR and LINE).

        The PL runs it whenever no sample is pending and PRIME_PERIOD cycles
        have elapsed since the last cycle; motion cycles restart that timer.
        """

        if self.faulted or not self.request_enabled:
            return b"", ()
        count = self.config.reads_per_cycle if self.config.backend_sel == BACKEND_SO101 else 1
        data = b""
        channels: list[int] = []
        for _ in range(count):
            frame, channel = self.request_frame()
            data += frame
            channels.append(channel)
        return data, tuple(channels)

    def process_sample(self, joints_q16: Sequence[int], *, permitted: bool = True) -> FrameResult:
        """Map, check and emit one motion sample.

        ``permitted=False`` models the PL last gate at the end of CHECK (ARM
        dropped or permission lost while the sample was mapped): limit and
        saturation checks still run first, exactly as in the RTL, but nothing
        is emitted, the sample is not consumed and no counter advances.
        """

        if self.faulted:
            return FrameResult(False, self.faulted)
        devices, limit_mask, sat_mask = map_joint_vector(joints_q16, self.config.channel_maps)
        if limit_mask:
            self.faulted = "limit_violation"
            result = FrameResult(False, self.faulted, device_values=devices, limit_mask=limit_mask)
            self.log.append(result)
            return result
        if sat_mask:
            self.faulted = "encode_saturation"
            result = FrameResult(False, self.faulted, device_values=devices)
            self.log.append(result)
            return result
        cmd = aft.run_program(
            self.config.template.ram,
            self.config.template.cmd_base,
            device_values=devices,
            device_ids=self.config.device_ids,
            rr_channel=self.rr_channel,
            seq_byte=self.frames_tx & 0xFF,
        )
        if cmd.saturated:
            self.faulted = "encode_saturation"
            result = FrameResult(False, self.faulted, device_values=devices)
            self.log.append(result)
            return result
        if not permitted:
            return FrameResult(False, None, device_values=devices)
        self.frames_tx += 1
        req = b""
        channels: list[int] = []
        if self.request_enabled:
            count = self.config.reads_per_cycle if self.config.backend_sel == BACKEND_SO101 else 1
            for _ in range(count):
                frame, channel = self.request_frame()
                req += frame
                channels.append(channel)
        result = FrameResult(
            accepted=True,
            fault=None,
            cmd=cmd.data,
            req=req,
            rr_channel=channels[0] if channels else None,
            rr_channels=tuple(channels),
            device_values=devices,
        )
        self.log.append(result)
        return result


# --------------------------------------------------------------------------
# Real-output gate
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class RealOutputPermit:
    """Proof object required by drivers/transports before driving a line."""

    purpose: str                # "robot" | "bench_loopback"
    profile_path: str
    protocol_id: str


def require_real_output(
    profile: ArmProfile,
    protocol: RoArmJsonProtocol | FeetechProtocol | None,
    *,
    purpose: str,
    confirm_no_robot: bool = False,
) -> RealOutputPermit:
    """Raise ``RealOutputBlocked`` unless every required input is present.

    ``purpose="robot"``: full profile + verified official protocol.
    ``purpose="robot_readonly"``: open the port and read feedback only (no
    motion writes); needs port/baud and the verified feedback vocabulary.
    ``purpose="bench_loopback"``: only ``bench_only`` profiles, only with the
    operator's explicit statement that no robot is connected to the line.
    """

    reasons: list[str] = []
    protocol_id = getattr(protocol, "protocol_id", bridge.BRIDGE_PROTOCOL)
    if purpose == "robot_readonly":
        if profile.bench_only:
            reasons.append("bench_only profile cannot open a robot port")
        if profile.transport.port is None or profile.transport.baudrate is None:
            reasons.append("transport.port/baudrate are TBD")
        if isinstance(protocol, RoArmJsonProtocol):
            reasons.extend(
                r for r in protocol.missing_fields(required_channels=profile.required_feedback_channels)
                if "set_joints" not in r
            )
        elif isinstance(protocol, FeetechProtocol):
            reasons.extend(protocol.missing_fields())
        else:
            reasons.append("protocol file is required")
    elif purpose == "robot":
        reasons.extend(profile.missing_for_real_output())
        if protocol is not None:
            if isinstance(protocol, RoArmJsonProtocol):
                reasons.extend(protocol.missing_fields(required_channels=profile.required_feedback_channels))
            else:
                reasons.extend(protocol.missing_fields())
        elif profile.backend != "roarm_m3_binary_bridge":
            reasons.append("protocol file is required")
        if profile.backend == "roarm_m3_binary_bridge":
            reasons.append("binary bridge firmware is not delivered/validated in S1")
    elif purpose == "bench_loopback":
        if not profile.bench_only:
            reasons.append("bench_loopback requires a bench_only profile")
        if not confirm_no_robot:
            reasons.append("operator must confirm that no robot/servo bus is connected (--confirm-no-robot)")
        if not profile.mapping_complete():
            reasons.append("bench profile mapping incomplete")
    else:
        reasons.append(f"unknown purpose {purpose!r}")
    if reasons:
        raise RealOutputBlocked(reasons)
    return RealOutputPermit(purpose, str(profile.path), protocol_id)
