"""RoArm-M3 JSON-line reference codec (no serial port, deterministic).

Truth boundary
--------------
The handoff package contains **no** RoArm JSON command numbers or feedback
field names.  Nothing here invents them.  Every official word comes from a
firmware-versioned protocol file (``config/protocols/roarm_m3_json_protocol.yaml``)
whose shipped values are ``null``; while any required field is ``null`` the
codec can only produce a *preview* marked ``sendable=False``.

Unit convention: a JSON "device unit" is the protocol's native number scaled
by ``10^fraction_digits``.  Example: a firmware taking radians with 4 decimals
uses ``fraction_digits: 4`` and ``device_units_per_rad: 10000`` in the profile.

Contents
--------
* ``RoArmJsonProtocol``: load/validate the protocol file and report blockers.
* ``compile_template`` / ``encode_command``: ``${chN}`` templates -> frame
  template words (``arm_frame_template``) -> bytes, identical to the PL output.
* ``parse_feedback_line``: semantic parse (``json.loads``) for PC/PS tools.
* ``JsonKeyLineParserModel``: byte-streaming model of
  ``rtl/robot/arm_json_feedback_parser.v`` used to generate golden vectors.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import arm_frame_template as aft
from arm_fixed_point import CHANNEL_COUNT, INT32_MAX, INT32_MIN
from arm_profile import ProfileError, load_yaml_mapping


PROTOCOL_SCHEMA = "gesture.phase3.roarm_json_protocol.v1"
PLACEHOLDER = re.compile(r"\$\{ch([0-9])\}")
MAX_KEY_LENGTH = 15
PARSER_SLOTS = 7          # slots 0..5 = position channels, slot 6 = discriminator
DISCRIMINATOR_SLOT = 6
WHITESPACE = (0x20, 0x09, 0x0D)
VALUE_STOP = (0x2C, 0x7D, 0x5D) + WHITESPACE  # ',' '}' ']' and whitespace


class ProtocolFieldMissing(RuntimeError):
    """An official protocol field required for this operation is still TBD."""


@dataclass(frozen=True)
class RoArmJsonProtocol:
    path: Path | None
    protocol_id: str
    status: str
    fixture: bool
    firmware_version: str | None
    sources: tuple[Mapping[str, Any], ...]
    line_terminator: bytes
    fraction_digits: int | None
    commands: Mapping[str, str | None]
    discriminator_key: str | None
    discriminator_value: int | None
    position_keys: tuple[str | None, ...]
    feedback_fraction_digits: int | None
    max_line_length: int

    TOP_KEYS = (
        "schema", "protocol_id", "status", "fixture", "firmware_version", "sources",
        "line_terminator", "fraction_digits", "commands", "feedback", "notes",
    )
    FEEDBACK_KEYS = (
        "discriminator_key", "discriminator_value", "position_keys",
        "fraction_digits", "max_line_length",
    )

    @classmethod
    def load(cls, path: Path | str) -> "RoArmJsonProtocol":
        path = Path(path).resolve()
        return cls.from_mapping(load_yaml_mapping(path), path=path)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], *, path: Path | None = None) -> "RoArmJsonProtocol":
        unknown = sorted(set(raw) - set(cls.TOP_KEYS))
        missing = sorted(set(cls.TOP_KEYS) - set(raw))
        if unknown or missing:
            raise ProfileError(f"RoArm protocol keys: unknown={unknown} missing={missing}")
        if raw["schema"] != PROTOCOL_SCHEMA:
            raise ProfileError(f"RoArm protocol schema must be {PROTOCOL_SCHEMA!r}")
        if raw["status"] not in ("VERIFIED", "BLOCKED_EXTERNAL_INPUT", "FIXTURE_NOT_OFFICIAL"):
            raise ProfileError("RoArm protocol status is invalid")
        if bool(raw["fixture"]) != (raw["status"] == "FIXTURE_NOT_OFFICIAL"):
            raise ProfileError("fixture must be true exactly for FIXTURE_NOT_OFFICIAL protocols")
        terminator = str(raw["line_terminator"]).encode("ascii")
        if len(terminator) != 1:
            raise ProfileError("S1 PL parser supports a single-byte line terminator")
        commands = raw["commands"]
        if not isinstance(commands, Mapping) or "set_joints" not in commands:
            raise ProfileError("commands.set_joints must exist (null while TBD)")
        feedback = raw["feedback"]
        f_unknown = sorted(set(feedback) - set(cls.FEEDBACK_KEYS))
        f_missing = sorted(set(cls.FEEDBACK_KEYS) - set(feedback))
        if f_unknown or f_missing:
            raise ProfileError(f"feedback keys: unknown={f_unknown} missing={f_missing}")
        keys = feedback["position_keys"]
        if not isinstance(keys, list) or len(keys) != CHANNEL_COUNT:
            raise ProfileError("feedback.position_keys must list six entries (null for TBD)")
        for key in list(keys) + [feedback["discriminator_key"]]:
            if key is not None:
                _check_key(key)
        for label in ("fraction_digits",):
            value = raw[label]
            if value is not None and not (isinstance(value, int) and 0 <= value <= 6):
                raise ProfileError(f"{label} must be 0..6 or null")
        fb_digits = feedback["fraction_digits"]
        if fb_digits is not None and not (isinstance(fb_digits, int) and 0 <= fb_digits <= 6):
            raise ProfileError("feedback.fraction_digits must be 0..6 or null")
        max_len = feedback["max_line_length"]
        if not isinstance(max_len, int) or not 16 <= max_len <= 0xFFFF:
            raise ProfileError("feedback.max_line_length must be 16..65535")
        disc_value = feedback["discriminator_value"]
        if disc_value is not None and not (
            isinstance(disc_value, int) and INT32_MIN <= disc_value <= INT32_MAX
        ):
            raise ProfileError("feedback.discriminator_value must be an int32 or null")
        if (feedback["discriminator_key"] is None) != (disc_value is None):
            raise ProfileError("discriminator_key and discriminator_value must both be set or both null")
        protocol = cls(
            path=path,
            protocol_id=str(raw["protocol_id"]),
            status=raw["status"],
            fixture=bool(raw["fixture"]),
            firmware_version=raw["firmware_version"],
            sources=tuple(raw["sources"] or ()),
            line_terminator=terminator,
            fraction_digits=raw["fraction_digits"],
            commands=dict(commands),
            discriminator_key=feedback["discriminator_key"],
            discriminator_value=disc_value,
            position_keys=tuple(keys),
            feedback_fraction_digits=fb_digits,
            max_line_length=max_len,
        )
        for name, template in protocol.commands.items():
            if template is not None:
                protocol.check_template(template, name=name)
        return protocol

    # ----------------------------------------------------------- readiness
    def missing_fields(self, *, required_channels: Sequence[int] = range(CHANNEL_COUNT)) -> list[str]:
        reasons: list[str] = []
        if self.fixture:
            reasons.append(f"protocol {self.protocol_id} is a synthetic FIXTURE_NOT_OFFICIAL file")
        if self.status != "VERIFIED":
            reasons.append(f"protocol status is {self.status}, not VERIFIED")
        if not self.firmware_version:
            reasons.append("firmware_version is TBD")
        if not self.sources:
            reasons.append("sources is empty (official Waveshare documents for the purchased firmware)")
        if self.commands.get("set_joints") is None:
            reasons.append("commands.set_joints template is TBD")
        if self.fraction_digits is None:
            reasons.append("fraction_digits is TBD")
        if self.feedback_fraction_digits is None:
            reasons.append("feedback.fraction_digits is TBD")
        for channel in required_channels:
            if self.position_keys[channel] is None:
                reasons.append(f"feedback.position_keys[{channel}] is TBD")
        return reasons

    # ------------------------------------------------------------ templates
    def check_template(self, template: str, *, name: str) -> None:
        if not isinstance(template, str) or not template:
            raise ProfileError(f"command {name}: template must be a non-empty string")
        try:
            template.encode("ascii")
        except UnicodeEncodeError as error:
            raise ProfileError(f"command {name}: template must be ASCII") from error
        if "\n" in template or "\r" in template:
            raise ProfileError(f"command {name}: the line terminator is appended automatically")
        channels = [int(m.group(1)) for m in PLACEHOLDER.finditer(template)]
        if any(ch >= CHANNEL_COUNT for ch in channels) or len(channels) != len(set(channels)):
            raise ProfileError(f"command {name}: placeholders must be unique ${{ch0}}..${{ch5}}")
        if "${" in PLACEHOLDER.sub("", template):
            raise ProfileError(f"command {name}: unknown placeholder syntax")
        probe = PLACEHOLDER.sub("0", template)
        try:
            decoded = json.loads(probe)
        except json.JSONDecodeError as error:
            raise ProfileError(f"command {name}: template is not valid JSON: {error}") from error
        if not isinstance(decoded, dict):
            raise ProfileError(f"command {name}: template must be a JSON object")


def _check_key(key: Any) -> None:
    if not isinstance(key, str) or not 1 <= len(key) <= MAX_KEY_LENGTH:
        raise ProfileError(f"feedback key {key!r} must be 1..{MAX_KEY_LENGTH} characters")
    try:
        raw = key.encode("ascii")
    except UnicodeEncodeError as error:
        raise ProfileError(f"feedback key {key!r} must be ASCII") from error
    if b'"' in raw or b"\\" in raw:
        raise ProfileError(f"feedback key {key!r} may not contain quotes or backslashes")


def compile_template(protocol: RoArmJsonProtocol, name: str) -> list[int]:
    """Compile a command template into frame-template words (ending with END)."""

    template = protocol.commands.get(name)
    if template is None:
        raise ProtocolFieldMissing(f"commands.{name} is TBD in {protocol.protocol_id}")
    words: list[int] = []
    cursor = 0
    has_placeholder = False
    for match in PLACEHOLDER.finditer(template):
        words.extend(aft.lits(template[cursor : match.start()]))
        if protocol.fraction_digits is None:
            raise ProtocolFieldMissing("fraction_digits is TBD")
        words.append(aft.dec(int(match.group(1)), protocol.fraction_digits))
        cursor = match.end()
        has_placeholder = True
    words.extend(aft.lits(template[cursor:]))
    words.extend(aft.lits(protocol.line_terminator))
    words.append(aft.end())
    if name == "set_joints" and not has_placeholder:
        raise ProfileError("set_joints must contain at least one ${chN} placeholder")
    return words


def encode_command(protocol: RoArmJsonProtocol, name: str, device_values: Sequence[int]) -> bytes:
    """Exact bytes the PL formatter emits for this command."""

    image = aft.TemplateImage.build(compile_template(protocol, name))
    return aft.run_program(image.ram, image.cmd_base, device_values=device_values).data


@dataclass(frozen=True)
class CommandPreview:
    sendable: bool
    data: bytes | None
    text: str
    blockers: tuple[str, ...]


def preview_command(
    protocol: RoArmJsonProtocol,
    name: str,
    device_values: Sequence[int | None],
    *,
    extra_blockers: Sequence[str] = (),
) -> CommandPreview:
    """Dry-run preview that works even when protocol or mapping fields are TBD."""

    blockers = list(extra_blockers)
    template = protocol.commands.get(name)
    if template is None:
        blockers.append(f"commands.{name} is TBD")
        values = ", ".join(
            f"ch{i}={'<TBD>' if v is None else v}" for i, v in enumerate(device_values)
        )
        return CommandPreview(False, None, f"<TBD command {name!r}: {values}>", tuple(blockers))
    if protocol.fraction_digits is None or any(v is None for v in device_values):
        if protocol.fraction_digits is None:
            blockers.append("fraction_digits is TBD")
        if any(v is None for v in device_values):
            blockers.append("device values incomplete (unit mapping TBD)")
        text = PLACEHOLDER.sub(lambda m: f"<TBD:ch{m.group(1)}>", template)
        return CommandPreview(False, None, text + "\\n", tuple(blockers))
    data = encode_command(protocol, name, [int(v) for v in device_values])  # type: ignore[arg-type]
    return CommandPreview(not blockers, data, data.decode("ascii").replace("\n", "\\n"), tuple(blockers))


# --------------------------------------------------------------------------
# Semantic feedback parse for PC/PS tools (not the PL model).
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class RoArmFeedbackLine:
    device_values: tuple[int | None, ...]
    valid_mask: int
    raw: Mapping[str, Any]


def scale_decimal_text(text: str, fraction_digits: int) -> int:
    """Round a JSON decimal to ``value * 10^D`` with the PL first-dropped-digit rule."""

    match = re.fullmatch(r"(-?)([0-9]+)(?:\.([0-9]+))?", text)
    if not match:
        raise ValueError(f"unsupported JSON number {text!r}")
    negative, integer, fraction = match.group(1), match.group(2), match.group(3) or ""
    kept = (fraction + "0" * fraction_digits)[:fraction_digits]
    value = int(integer + kept) if (integer + kept) else 0
    if len(fraction) > fraction_digits and int(fraction[fraction_digits]) >= 5:
        value += 1
    value = -value if negative else value
    if not INT32_MIN <= value <= INT32_MAX:
        raise ValueError(f"JSON number {text!r} overflows int32 device units")
    return value


class _NumberText(str):
    """Exact JSON number text, kept distinct from JSON string values."""


def parse_feedback_line(protocol: RoArmJsonProtocol, line: bytes) -> RoArmFeedbackLine | None:
    """Return a feedback record, or None when the line is not a feedback line."""

    if protocol.feedback_fraction_digits is None:
        raise ProtocolFieldMissing("feedback.fraction_digits is TBD")
    text = line.rstrip(b"\r\n").decode("ascii", errors="strict")
    if not text.strip():
        return None
    try:
        payload = json.loads(text, parse_float=_NumberText, parse_int=_NumberText)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if protocol.discriminator_key is not None:
        disc = payload.get(protocol.discriminator_key)
        if not isinstance(disc, _NumberText) or scale_decimal_text(disc, 0) != protocol.discriminator_value:
            return None
    values: list[int | None] = []
    mask = 0
    for channel, key in enumerate(protocol.position_keys):
        raw_value = payload.get(key) if key is not None else None
        if isinstance(raw_value, _NumberText):
            values.append(scale_decimal_text(raw_value, protocol.feedback_fraction_digits))
            mask |= 1 << channel
        else:
            values.append(None)
    if mask == 0:
        return None
    return RoArmFeedbackLine(tuple(values), mask, payload)


# --------------------------------------------------------------------------
# Byte-streaming model mirroring rtl/robot/arm_json_feedback_parser.v
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class JsonParserConfig:
    keys: tuple[bytes, ...]            # 7 entries; b"" disables a slot
    fraction_digits: int
    line_terminator: int = 0x0A
    max_line_length: int = 512
    discriminator_value: int = 0

    def __post_init__(self) -> None:
        if len(self.keys) != PARSER_SLOTS:
            raise ValueError("JsonParserConfig needs exactly seven key slots")
        for key in self.keys:
            if len(key) > MAX_KEY_LENGTH:
                raise ValueError("key too long")
        if not 0 <= self.fraction_digits <= 6:
            raise ValueError("fraction digits out of range")

    @classmethod
    def from_protocol(cls, protocol: RoArmJsonProtocol) -> "JsonParserConfig":
        if protocol.feedback_fraction_digits is None:
            raise ProtocolFieldMissing("feedback.fraction_digits is TBD")
        keys = [k.encode("ascii") if k is not None else b"" for k in protocol.position_keys]
        keys.append(protocol.discriminator_key.encode("ascii") if protocol.discriminator_key else b"")
        return cls(
            keys=tuple(keys),
            fraction_digits=protocol.feedback_fraction_digits,
            line_terminator=protocol.line_terminator[0],
            max_line_length=protocol.max_line_length,
            discriminator_value=protocol.discriminator_value or 0,
        )

    def key_ram(self) -> list[int]:
        """128-byte key RAM image: address = {slot[2:0], index[3:0]}."""

        ram = [0] * 128
        for slot, key in enumerate(self.keys):
            for index, byte in enumerate(key):
                ram[(slot << 4) | index] = byte
        return ram

    def key_len_word(self) -> int:
        word = 0
        for slot, key in enumerate(self.keys):
            word |= len(key) << (4 * slot)
        return word


@dataclass
class JsonParserEvent:
    kind: str                       # "record" | "ignored" | "error"
    values: tuple[int, ...] = (0,) * CHANNEL_COUNT
    mask: int = 0


@dataclass
class JsonKeyLineParserModel:
    config: JsonParserConfig
    events: list[JsonParserEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._reset_line()

    # States match the RTL encoding names.
    def _reset_line(self) -> None:
        self.state = "SCAN"
        self.line_len = 0
        self.line_bad = False
        self.seen = 0
        self.values = [0] * PARSER_SLOTS
        self.key = bytearray()
        self.key_bad = False
        self._reset_value()

    def _reset_value(self) -> None:
        self.slot = 0
        self.neg = False
        self.acc = 0
        self.int_digits = 0
        self.frac_count = 0
        self.round_digit = 0
        self.got_digit = False
        self.value_overflow = False

    def _digits_for_slot(self) -> int:
        return 0 if self.slot == DISCRIMINATOR_SLOT else self.config.fraction_digits

    def _accumulate(self, digit: int) -> None:
        if self.value_overflow:
            return
        self.acc = self.acc * 10 + digit
        if self.acc >= (1 << 32):
            self.value_overflow = True

    def _finalize_value(self) -> None:
        digits = self._digits_for_slot()
        acc = self.acc
        overflow = self.value_overflow
        count = self.frac_count
        while not overflow and count < digits:
            acc *= 10
            count += 1
            if acc >= (1 << 32):
                overflow = True
        if not overflow and self.round_digit >= 5:
            acc += 1
        limit = (1 << 31) if self.neg else (1 << 31) - 1
        if overflow or acc > limit:
            self.line_bad = True
        else:
            self.values[self.slot] = -acc if self.neg else acc
            self.seen |= 1 << self.slot
        self._reset_value()

    def _match_key(self) -> int | None:
        if self.key_bad:
            return None
        for slot, key in enumerate(self.config.keys):
            if key and key == bytes(self.key):
                return slot
        return None

    def _end_of_line(self) -> None:
        pos_enabled = 0
        for slot in range(CHANNEL_COUNT):
            if self.config.keys[slot]:
                pos_enabled |= 1 << slot
        disc_enabled = bool(self.config.keys[DISCRIMINATOR_SLOT])
        seen_pos = self.seen & pos_enabled
        if disc_enabled:
            disc_ok = bool(self.seen & (1 << DISCRIMINATOR_SLOT)) and (
                self.values[DISCRIMINATOR_SLOT] == self.config.discriminator_value
            )
            if not disc_ok:
                event = JsonParserEvent("ignored")
            elif self.line_bad or seen_pos != pos_enabled:
                event = JsonParserEvent("error")
            else:
                event = self._record(pos_enabled)
        else:
            if self.line_bad:
                event = JsonParserEvent("error")
            elif seen_pos == 0:
                event = JsonParserEvent("ignored")
            elif seen_pos != pos_enabled:
                event = JsonParserEvent("error")
            else:
                event = self._record(pos_enabled)
        self.events.append(event)
        self._reset_line()

    def _record(self, mask: int) -> JsonParserEvent:
        values = tuple(
            self.values[ch] if mask & (1 << ch) else 0 for ch in range(CHANNEL_COUNT)
        )
        return JsonParserEvent("record", values, mask)

    def feed(self, data: bytes) -> list[JsonParserEvent]:
        start = len(self.events)
        for byte in data:
            self._feed_byte(byte)
        return self.events[start:]

    def _feed_byte(self, b: int) -> None:
        self.line_len += 1
        if b == self.config.line_terminator:
            if self.state in ("VALUE_INT", "VALUE_FRAC"):
                self._close_number()
            elif self.state == "VALUE_WS":
                self.line_bad = True
            self._end_of_line()
            return
        if self.line_len > self.config.max_line_length:
            self.line_bad = True
            self.state = "SKIP"
            return
        state = self.state
        if state == "SKIP":
            return
        if state == "SCAN":
            if b == 0x22:
                self._start_key()
        elif state == "KEY":
            if b == 0x5C:
                self.key_bad = True
                self.state = "KEY_ESC"
            elif b == 0x22:
                self.state = "AFTER_KEY"
            elif len(self.key) < MAX_KEY_LENGTH:
                self.key.append(b)
            else:
                self.key_bad = True
        elif state == "KEY_ESC":
            self.state = "KEY"
        elif state == "AFTER_KEY":
            if b in WHITESPACE:
                return
            if b == 0x3A:
                slot = self._match_key()
                if slot is None:
                    self.state = "SCAN"
                elif self.seen & (1 << slot):
                    self.line_bad = True
                    self.state = "SCAN"
                else:
                    self._reset_value()
                    self.slot = slot
                    self.state = "VALUE_WS"
            elif b == 0x22:
                self._start_key()
            else:
                self.state = "SCAN"
        elif state == "VALUE_WS":
            if b in WHITESPACE:
                return
            if b == 0x2D:
                self.neg = True
                self.state = "VALUE_INT"
            elif 0x30 <= b <= 0x39:
                self._integer_digit(b - 0x30)
                self.state = "VALUE_INT"
            else:
                self.line_bad = True
                self.state = "SCAN"
        elif state == "VALUE_INT":
            if 0x30 <= b <= 0x39:
                self._integer_digit(b - 0x30)
            elif b == 0x2E:
                if not self.got_digit:
                    self.line_bad = True
                    self.state = "SCAN"
                else:
                    self.got_digit = False
                    self.state = "VALUE_FRAC"
            elif b in VALUE_STOP:
                self._close_number()
                self.state = "SCAN"
            else:
                self.line_bad = True
                self.state = "SCAN"
        elif state == "VALUE_FRAC":
            if 0x30 <= b <= 0x39:
                self._fraction_digit(b - 0x30)
            elif b in VALUE_STOP:
                self._close_number()
                self.state = "SCAN"
            else:
                self.line_bad = True
                self.state = "SCAN"

    def _start_key(self) -> None:
        self.key = bytearray()
        self.key_bad = False
        self.state = "KEY"

    def _integer_digit(self, digit: int) -> None:
        self.got_digit = True
        if self.int_digits >= 10:
            self.value_overflow = True
            return
        self.int_digits += 1
        self._accumulate(digit)

    def _fraction_digit(self, digit: int) -> None:
        self.got_digit = True
        digits = self._digits_for_slot()
        if self.frac_count < digits:
            self._accumulate(digit)
            self.frac_count += 1
        elif self.frac_count == digits:
            self.round_digit = digit
            self.frac_count += 1

    def _close_number(self) -> None:
        if not self.got_digit:
            self.line_bad = True
            self._reset_value()
            return
        if self.frac_count > self._digits_for_slot():
            self.frac_count = self._digits_for_slot()
        self._finalize_value()
