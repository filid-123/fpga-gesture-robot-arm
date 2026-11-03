"""SO-ARM101 follower / STS3215 Feetech bus reference codec (pure Python).

Truth boundary
--------------
The handoff package only states that SO-101 uses six STS3215 servos from the
Feetech STS/SMS family ("protocol 0" in LeRobot).  It contains no instruction
codes, header bytes, register addresses or position encoding.  Therefore:

* The **frame structure** below is recorded as ``structure_assumption`` in the
  protocol file with ``structure_verified: false``.  It must be confirmed
  against the official Feetech STS3215 memory table / protocol manual (or the
  LeRobot Feetech tables for the exact firmware) before any real output::

      command: HDR0 HDR1 ID LEN INSTR PARAM[0..n-1] CK
      status : HDR0 HDR1 ID LEN ERR   PARAM[0..n-1] CK
      LEN = n + 2,  CK = ~(ID + LEN + INSTR/ERR + sum(PARAM)) & 0xFF

* **Every numeric constant** (header, broadcast id, instruction codes,
  register addresses/sizes, endian, position encoding) is read from
  ``config/protocols/feetech_sts_protocol.yaml`` and ships as ``null``.
  Tests use ``config/protocols/fixtures/feetech_FIXTURE_NOT_OFFICIAL.yaml`` whose
  values are deliberately synthetic.

``StatusStreamParserModel`` mirrors ``rtl/robot/arm_so101_status_parser.v``
byte for byte and generates the RTL golden vectors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import arm_frame_template as aft
from arm_fixed_point import CHANNEL_COUNT
from arm_profile import ProfileError, load_yaml_mapping
from roarm_json_reference import ProtocolFieldMissing


PROTOCOL_SCHEMA = "gesture.phase3.feetech_protocol.v1"
ENCODINGS = {"twos_complement": aft.ENC_TWOS, "unsigned": aft.ENC_UNSIGNED,
             "sign_magnitude_msb": aft.ENC_SIGN_MAGNITUDE}
MAX_STATUS_PARAMS = 4


def _opt_byte(value: Any, *, where: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFF:
        raise ProfileError(f"{where} must be a byte value or null")
    return value


@dataclass(frozen=True)
class RegisterSpec:
    address: int | None
    size: int | None


@dataclass(frozen=True)
class FeetechProtocol:
    path: Path | None
    protocol_id: str
    status: str
    fixture: bool
    structure_verified: bool
    firmware_version: str | None
    sources: tuple[Mapping[str, Any], ...]
    header: tuple[int | None, int | None]
    broadcast_id: int | None
    instructions: Mapping[str, int | None]
    registers: Mapping[str, RegisterSpec]
    position_encoding: str | None
    endian: str | None
    checksum: str | None

    TOP_KEYS = (
        "schema", "protocol_id", "status", "fixture", "servo_model", "firmware_version",
        "sources", "structure_assumption", "structure_verified", "header", "broadcast_id",
        "instructions", "registers", "position_encoding", "endian", "checksum", "notes",
    )
    INSTRUCTIONS = ("ping", "read", "write", "sync_write")
    REGISTERS = ("torque_enable", "goal_position", "present_position")

    @classmethod
    def load(cls, path: Path | str) -> "FeetechProtocol":
        path = Path(path).resolve()
        return cls.from_mapping(load_yaml_mapping(path), path=path)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], *, path: Path | None = None) -> "FeetechProtocol":
        unknown = sorted(set(raw) - set(cls.TOP_KEYS))
        missing = sorted(set(cls.TOP_KEYS) - set(raw))
        if unknown or missing:
            raise ProfileError(f"Feetech protocol keys: unknown={unknown} missing={missing}")
        if raw["schema"] != PROTOCOL_SCHEMA:
            raise ProfileError(f"Feetech protocol schema must be {PROTOCOL_SCHEMA!r}")
        if raw["status"] not in ("VERIFIED", "BLOCKED_EXTERNAL_INPUT", "FIXTURE_NOT_OFFICIAL"):
            raise ProfileError("Feetech protocol status is invalid")
        if bool(raw["fixture"]) != (raw["status"] == "FIXTURE_NOT_OFFICIAL"):
            raise ProfileError("fixture must be true exactly for FIXTURE_NOT_OFFICIAL protocols")
        header = raw["header"]
        if not isinstance(header, list) or len(header) != 2:
            raise ProfileError("header must list two bytes (null while TBD)")
        instructions = raw["instructions"]
        if set(instructions) != set(cls.INSTRUCTIONS):
            raise ProfileError(f"instructions must define exactly {cls.INSTRUCTIONS}")
        registers_raw = raw["registers"]
        if set(registers_raw) != set(cls.REGISTERS):
            raise ProfileError(f"registers must define exactly {cls.REGISTERS}")
        registers: dict[str, RegisterSpec] = {}
        for name in cls.REGISTERS:
            spec = registers_raw[name]
            if set(spec) != {"address", "size"}:
                raise ProfileError(f"registers.{name} needs address and size")
            size = spec["size"]
            if size is not None and size not in (1, 2):
                raise ProfileError(f"registers.{name}.size must be 1 or 2")
            registers[name] = RegisterSpec(_opt_byte(spec["address"], where=f"registers.{name}.address"), size)
        encoding = raw["position_encoding"]
        if encoding is not None and encoding not in ENCODINGS:
            raise ProfileError(f"position_encoding must be one of {sorted(ENCODINGS)} or null")
        if raw["endian"] not in (None, "little", "big"):
            raise ProfileError("endian must be little, big or null")
        if raw["checksum"] not in (None, "inverted_sum8", "sum8"):
            raise ProfileError("checksum must be inverted_sum8, sum8 or null")
        return cls(
            path=path,
            protocol_id=str(raw["protocol_id"]),
            status=raw["status"],
            fixture=bool(raw["fixture"]),
            structure_verified=bool(raw["structure_verified"]),
            firmware_version=raw["firmware_version"],
            sources=tuple(raw["sources"] or ()),
            header=(_opt_byte(header[0], where="header[0]"), _opt_byte(header[1], where="header[1]")),
            broadcast_id=_opt_byte(raw["broadcast_id"], where="broadcast_id"),
            instructions={k: _opt_byte(instructions[k], where=f"instructions.{k}") for k in cls.INSTRUCTIONS},
            registers=registers,
            position_encoding=encoding,
            endian=raw["endian"],
            checksum=raw["checksum"],
        )

    def missing_fields(self) -> list[str]:
        reasons: list[str] = []
        if self.fixture:
            reasons.append(f"protocol {self.protocol_id} is a synthetic FIXTURE_NOT_OFFICIAL file")
        if self.status != "VERIFIED":
            reasons.append(f"protocol status is {self.status}, not VERIFIED")
        if not self.structure_verified:
            reasons.append("frame structure assumption is not verified against official Feetech docs")
        if not self.firmware_version:
            reasons.append("firmware_version is TBD")
        if not self.sources:
            reasons.append("sources is empty (official Feetech/LeRobot documents)")
        reasons.extend(self.codec_blockers())
        return reasons

    def codec_blockers(self) -> list[str]:
        """Fields needed to compute any byte (also blocks dry-run byte previews)."""

        reasons: list[str] = []
        if None in self.header:
            reasons.append("header bytes are TBD")
        if self.broadcast_id is None:
            reasons.append("broadcast_id is TBD")
        for name, code in self.instructions.items():
            if code is None:
                reasons.append(f"instructions.{name} is TBD")
        for name, spec in self.registers.items():
            if spec.address is None or spec.size is None:
                reasons.append(f"registers.{name} address/size is TBD")
        if self.position_encoding is None:
            reasons.append("position_encoding is TBD")
        if self.endian is None:
            reasons.append("endian is TBD")
        if self.checksum is None:
            reasons.append("checksum rule is TBD")
        for name in ("goal_position", "present_position"):
            if self.registers[name].size not in (None, 2):
                reasons.append(f"registers.{name}.size must be 2 for the S1 PL position path")
        return reasons

    def require_codec(self) -> None:
        blockers = self.codec_blockers()
        if blockers:
            raise ProtocolFieldMissing("; ".join(blockers))

    @property
    def ck_invert(self) -> bool:
        return self.checksum == "inverted_sum8"

    @property
    def encoding_code(self) -> int:
        self.require_codec()
        return ENCODINGS[self.position_encoding]  # type: ignore[index]

    @property
    def big_endian(self) -> bool:
        return self.endian == "big"


def checksum(protocol: FeetechProtocol, body: bytes) -> int:
    total = sum(body) & 0xFF
    return (~total) & 0xFF if protocol.ck_invert else total


def build_packet(protocol: FeetechProtocol, device_id: int, instruction: int, params: bytes) -> bytes:
    protocol.require_codec()
    if not 0 <= device_id <= 0xFF or not 0 <= instruction <= 0xFF:
        raise ValueError("device_id and instruction must be bytes")
    length = len(params) + 2
    if length > 0xFF:
        raise ValueError("packet too long")
    body = bytes([device_id, length, instruction]) + bytes(params)
    return bytes(protocol.header) + body + bytes([checksum(protocol, body)])  # type: ignore[arg-type]


def ping(protocol: FeetechProtocol, device_id: int) -> bytes:
    return build_packet(protocol, device_id, protocol.instructions["ping"], b"")  # type: ignore[arg-type]


def read(protocol: FeetechProtocol, device_id: int, register: str) -> bytes:
    spec = protocol.registers[register]
    return build_packet(
        protocol, device_id, protocol.instructions["read"],  # type: ignore[arg-type]
        bytes([spec.address, spec.size]),  # type: ignore[list-item]
    )


def encode_position(protocol: FeetechProtocol, value: int) -> tuple[bytes, bool]:
    return aft.encode_binary_field(
        value, 16, big_endian=protocol.big_endian, encoding=protocol.encoding_code
    )


def decode_position(protocol: FeetechProtocol, data: bytes) -> int:
    return aft.decode_binary_field(data, big_endian=protocol.big_endian, encoding=protocol.encoding_code)


def write(protocol: FeetechProtocol, device_id: int, register: str, value: int) -> bytes:
    spec = protocol.registers[register]
    if spec.size == 2:
        data = encode_position(protocol, value)[0] if "position" in register else int(value).to_bytes(
            2, "big" if protocol.big_endian else "little")
    else:
        data = bytes([int(value) & 0xFF])
    return build_packet(
        protocol, device_id, protocol.instructions["write"],  # type: ignore[arg-type]
        bytes([spec.address]) + data,  # type: ignore[list-item]
    )


def sync_write_positions(
    protocol: FeetechProtocol, device_ids: Sequence[int], device_values: Sequence[int]
) -> tuple[bytes, bool]:
    """Broadcast goal-position sync write for six servos (logical channel order)."""

    if len(device_ids) != CHANNEL_COUNT or len(device_values) != CHANNEL_COUNT:
        raise ValueError("six ids and six values are required")
    spec = protocol.registers["goal_position"]
    params = bytearray([spec.address, spec.size])  # type: ignore[list-item]
    saturated = False
    for device_id, value in zip(device_ids, device_values, strict=True):
        data, sat = encode_position(protocol, value)
        params += bytes([device_id]) + data
        saturated |= sat
    return (
        build_packet(protocol, protocol.broadcast_id, protocol.instructions["sync_write"], bytes(params)),  # type: ignore[arg-type]
        saturated,
    )


def compile_sync_write_template(protocol: FeetechProtocol) -> list[int]:
    """Frame-template words equal to ``sync_write_positions`` (ids from PL config)."""

    protocol.require_codec()
    spec = protocol.registers["goal_position"]
    length = 2 + 2 + CHANNEL_COUNT * (1 + 2)
    words = [aft.lit(protocol.header[0]), aft.lit(protocol.header[1]), aft.ckb(aft.CK_SUM8)]  # type: ignore[arg-type]
    words += [aft.lit(protocol.broadcast_id), aft.lit(length), aft.lit(protocol.instructions["sync_write"])]  # type: ignore[arg-type]
    words += [aft.lit(spec.address), aft.lit(spec.size)]  # type: ignore[arg-type]
    for channel in range(CHANNEL_COUNT):
        words.append(aft.idb(channel))
        words.append(aft.binf(channel, 16, big_endian=protocol.big_endian, encoding=protocol.encoding_code))
    words += [aft.cke(invert=protocol.ck_invert), aft.end()]
    return words


def compile_read_request_template(protocol: FeetechProtocol) -> list[int]:
    """READ present_position of the feedback round-robin channel's servo."""

    protocol.require_codec()
    spec = protocol.registers["present_position"]
    words = [aft.lit(protocol.header[0]), aft.lit(protocol.header[1]), aft.ckb(aft.CK_SUM8)]  # type: ignore[arg-type]
    words += [aft.idb(None), aft.lit(4), aft.lit(protocol.instructions["read"])]  # type: ignore[arg-type]
    words += [aft.lit(spec.address), aft.lit(spec.size), aft.cke(invert=protocol.ck_invert), aft.end()]  # type: ignore[arg-type]
    return words


@dataclass(frozen=True)
class StatusPacket:
    device_id: int
    error: int
    params: bytes


def parse_status_packet(protocol: FeetechProtocol, frame: bytes) -> StatusPacket:
    protocol.require_codec()
    if len(frame) < 6 or tuple(frame[:2]) != protocol.header:
        raise ValueError("bad status header")
    length = frame[3]
    if length < 2 or len(frame) != length + 4:
        raise ValueError("status LEN does not match frame size")
    if checksum(protocol, frame[2:-1]) != frame[-1]:
        raise ValueError("status checksum mismatch")
    return StatusPacket(frame[2], frame[4], bytes(frame[5:-1]))


def encode_status_packet(protocol: FeetechProtocol, device_id: int, error: int, params: bytes) -> bytes:
    """Used by the PC-side servo emulator and tests."""

    body = bytes([device_id, len(params) + 2, error]) + bytes(params)
    return bytes(protocol.header) + body + bytes([checksum(protocol, body)])  # type: ignore[arg-type]


@dataclass(frozen=True)
class StatusParserConfig:
    header0: int
    header1: int
    expected_nparams: int
    encoding: int
    big_endian: bool
    ck_invert: bool

    @classmethod
    def from_protocol(cls, protocol: FeetechProtocol) -> "StatusParserConfig":
        protocol.require_codec()
        return cls(
            header0=protocol.header[0],  # type: ignore[arg-type]
            header1=protocol.header[1],  # type: ignore[arg-type]
            expected_nparams=protocol.registers["present_position"].size,  # type: ignore[arg-type]
            encoding=protocol.encoding_code,
            big_endian=protocol.big_endian,
            ck_invert=protocol.ck_invert,
        )


@dataclass
class StatusParserEvent:
    kind: str               # "packet" | "checksum_error" | "protocol_error"
    device_id: int = 0
    error: int = 0
    value: int = 0


@dataclass
class StatusStreamParserModel:
    """Mirror of arm_so101_status_parser.v (states HUNT0..CK)."""

    config: StatusParserConfig
    expected_id: int = 0
    events: list[StatusParserEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.flush()

    def flush(self) -> None:
        self.state = "HUNT0"
        self.device_id = 0
        self.length = 0
        self.error = 0
        self.params = bytearray()
        self.sum = 0

    def feed(self, data: bytes) -> list[StatusParserEvent]:
        start = len(self.events)
        for byte in data:
            self._feed_byte(byte)
        return self.events[start:]

    def _feed_byte(self, b: int) -> None:
        cfg = self.config
        state = self.state
        if state == "HUNT0":
            if b == cfg.header0:
                self.state = "HUNT1"
        elif state == "HUNT1":
            if b == cfg.header1:
                self.state = "ID"
            elif b != cfg.header0:
                self.state = "HUNT0"
        elif state == "ID":
            if b == cfg.header1 and cfg.header0 == cfg.header1:
                return
            self.device_id = b
            self.sum = b
            self.state = "LEN"
        elif state == "LEN":
            if b < 2 or b > 2 + MAX_STATUS_PARAMS:
                self.events.append(StatusParserEvent("protocol_error", self.device_id))
                self.flush()
                return
            self.length = b
            self.sum = (self.sum + b) & 0xFF
            self.state = "ERR"
        elif state == "ERR":
            self.error = b
            self.sum = (self.sum + b) & 0xFF
            self.params = bytearray()
            self.state = "PARAM" if self.length > 2 else "CK"
        elif state == "PARAM":
            self.params.append(b)
            self.sum = (self.sum + b) & 0xFF
            if len(self.params) == self.length - 2:
                self.state = "CK"
        elif state == "CK":
            expected = (~self.sum) & 0xFF if cfg.ck_invert else self.sum
            if b != expected:
                self.events.append(StatusParserEvent("checksum_error", self.device_id))
            elif self.device_id != self.expected_id or len(self.params) != cfg.expected_nparams:
                self.events.append(StatusParserEvent("protocol_error", self.device_id))
            else:
                value = aft.decode_binary_field(
                    bytes(self.params[:2]), big_endian=cfg.big_endian, encoding=cfg.encoding
                ) if cfg.expected_nparams == 2 else 0
                self.events.append(StatusParserEvent("packet", self.device_id, self.error, value))
            self.flush()
