"""Frame template ISA ``arm_frame_template_isa_v1`` and its reference engine.

One small PL frame formatter serves every S1 TX format (RoArm JSON line,
RoArm binary bridge v1, Feetech sync-write/read).  Protocol words are never
hard-coded in RTL: the PS compiles a template from versioned protocol/profile
configuration and loads it into the formatter's 256x16 template RAM.

Word layout: ``[15:12] opcode``, ``[11:0] operand``.

====  ======  ==================================================================
code  name    operand
====  ======  ==================================================================
0x0   END     must be 0
0x1   LIT     [7:0] literal byte
0x2   DEC     [2:0] channel 0..5, [6:4] fraction digits 0..6; ASCII fixed decimal
0x3   BIN     [2:0] channel, [4:3] width (1=16, 2=32 bit), [5] big-endian,
              [7:6] encoding (0=two's complement, 1=unsigned, 2=sign-magnitude)
0x4   CKB     [0] kind (0=sum8, 1=xor8); starts checksum accumulation
0x5   CKE     [0] invert; emits the checksum byte and stops accumulation
0x6   IDB     [3]=1 -> id of feedback round-robin channel, else [2:0] channel
0x7   SEQ     must be 0; emits low byte of the motion-frame counter
====  ======  ==================================================================

All operand bits not listed above must be zero; the PL validation pass and the
Python validator both reject anything else.  Every value field saturates to
its encoding range; saturation is reported, never silently hidden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from arm_fixed_point import CHANNEL_COUNT, check_int32


ISA_VERSION = "arm_frame_template_isa_v1"
TEMPLATE_DEPTH = 256
MAX_FRACTION_DIGITS = 6

OP_END = 0x0
OP_LIT = 0x1
OP_DEC = 0x2
OP_BIN = 0x3
OP_CKB = 0x4
OP_CKE = 0x5
OP_IDB = 0x6
OP_SEQ = 0x7

ENC_TWOS = 0
ENC_UNSIGNED = 1
ENC_SIGN_MAGNITUDE = 2

WIDTH_16 = 1
WIDTH_32 = 2

CK_SUM8 = 0
CK_XOR8 = 1


class TemplateError(ValueError):
    """A template is malformed or cannot be placed in the template RAM."""


def _word(opcode: int, operand: int) -> int:
    if not 0 <= operand <= 0xFFF:
        raise TemplateError(f"operand 0x{operand:X} does not fit in 12 bits")
    return (opcode << 12) | operand


def end() -> int:
    return _word(OP_END, 0)


def lit(byte: int) -> int:
    if not 0 <= byte <= 0xFF:
        raise TemplateError(f"literal byte {byte} out of range")
    return _word(OP_LIT, byte)


def lits(data: bytes | str) -> list[int]:
    payload = data.encode("ascii") if isinstance(data, str) else bytes(data)
    return [lit(value) for value in payload]


def dec(channel: int, fraction_digits: int) -> int:
    if not 0 <= channel < CHANNEL_COUNT:
        raise TemplateError(f"DEC channel {channel} out of range")
    if not 0 <= fraction_digits <= MAX_FRACTION_DIGITS:
        raise TemplateError(f"DEC fraction digits {fraction_digits} out of range")
    return _word(OP_DEC, channel | (fraction_digits << 4))


def binf(channel: int, width_bits: int, *, big_endian: bool, encoding: int) -> int:
    if not 0 <= channel < CHANNEL_COUNT:
        raise TemplateError(f"BIN channel {channel} out of range")
    width_code = {16: WIDTH_16, 32: WIDTH_32}.get(width_bits)
    if width_code is None:
        raise TemplateError(f"BIN width {width_bits} is not supported")
    if encoding not in (ENC_TWOS, ENC_UNSIGNED, ENC_SIGN_MAGNITUDE):
        raise TemplateError(f"BIN encoding {encoding} is not supported")
    operand = channel | (width_code << 3) | (int(big_endian) << 5) | (encoding << 6)
    return _word(OP_BIN, operand)


def ckb(kind: int) -> int:
    if kind not in (CK_SUM8, CK_XOR8):
        raise TemplateError(f"checksum kind {kind} is not supported")
    return _word(OP_CKB, kind)


def cke(*, invert: bool) -> int:
    return _word(OP_CKE, int(invert))


def idb(channel: int | None) -> int:
    """``channel=None`` selects the feedback round-robin channel."""

    if channel is None:
        return _word(OP_IDB, 1 << 3)
    if not 0 <= channel < CHANNEL_COUNT:
        raise TemplateError(f"IDB channel {channel} out of range")
    return _word(OP_IDB, channel)


def seq() -> int:
    return _word(OP_SEQ, 0)


def decode_word(word: int) -> tuple[int, int]:
    if not 0 <= word <= 0xFFFF:
        raise TemplateError(f"template word 0x{word:X} does not fit in 16 bits")
    return word >> 12, word & 0xFFF


def word_is_legal(word: int) -> bool:
    """Operand legality exactly as checked by the PL validation pass."""

    opcode, operand = decode_word(word)
    if opcode == OP_END or opcode == OP_SEQ:
        return operand == 0
    if opcode == OP_LIT:
        return operand <= 0xFF
    if opcode == OP_DEC:
        channel = operand & 0x7
        digits = (operand >> 4) & 0x7
        return (operand & ~0x077) == 0 and channel < 6 and digits <= 6
    if opcode == OP_BIN:
        channel = operand & 0x7
        width = (operand >> 3) & 0x3
        encoding = (operand >> 6) & 0x3
        return (operand & ~0x0FF) == 0 and channel < 6 and width in (1, 2) and encoding != 3
    if opcode == OP_CKB or opcode == OP_CKE:
        return (operand & ~0x1) == 0
    if opcode == OP_IDB:
        if operand & 0x8:
            return operand == 0x8
        return (operand & ~0x7) == 0 and operand < 6
    return False


def validate_program(ram: Sequence[int], base: int) -> int:
    """Return the number of words including END; raise on any PL-rejected form."""

    if len(ram) != TEMPLATE_DEPTH:
        raise TemplateError(f"template RAM must contain {TEMPLATE_DEPTH} words")
    if not 0 <= base < TEMPLATE_DEPTH:
        raise TemplateError(f"program base {base} out of range")
    for offset in range(TEMPLATE_DEPTH - base):
        word = ram[base + offset]
        if not word_is_legal(word):
            raise TemplateError(f"illegal template word 0x{word:04X} at {base + offset}")
        if decode_word(word)[0] == OP_END:
            return offset + 1
    raise TemplateError("program runs past the end of template RAM without END")


def format_fixed_decimal(value: int, fraction_digits: int) -> str:
    """ASCII emitted by DEC: optional '-', integer digits, optional '.' + digits."""

    check_int32(value, name="DEC value")
    if not 0 <= fraction_digits <= MAX_FRACTION_DIGITS:
        raise TemplateError("fraction digits out of range")
    magnitude = abs(value)
    digits = f"{magnitude:010d}"
    split = len(digits) - fraction_digits
    integer_part = digits[:split].lstrip("0") or "0"
    text = ("-" if value < 0 else "") + integer_part
    if fraction_digits:
        text += "." + digits[split:]
    return text


def encode_binary_field(
    value: int, width_bits: int, *, big_endian: bool, encoding: int
) -> tuple[bytes, bool]:
    """Bytes emitted by BIN plus the saturation flag."""

    check_int32(value, name="BIN value")
    saturated = False
    if encoding == ENC_TWOS:
        low, high = -(1 << (width_bits - 1)), (1 << (width_bits - 1)) - 1
        clamped = min(max(value, low), high)
        saturated = clamped != value
        word = clamped & ((1 << width_bits) - 1)
    elif encoding == ENC_UNSIGNED:
        clamped = min(max(value, 0), (1 << width_bits) - 1)
        saturated = clamped != value
        word = clamped
    elif encoding == ENC_SIGN_MAGNITUDE:
        limit = (1 << (width_bits - 1)) - 1
        magnitude = min(abs(value), limit)
        saturated = magnitude != abs(value)
        word = magnitude | ((1 << (width_bits - 1)) if value < 0 else 0)
    else:
        raise TemplateError(f"unsupported encoding {encoding}")
    return word.to_bytes(width_bits // 8, "big" if big_endian else "little"), saturated


def decode_binary_field(
    data: bytes, *, big_endian: bool, encoding: int
) -> int:
    width_bits = 8 * len(data)
    word = int.from_bytes(data, "big" if big_endian else "little")
    if encoding == ENC_TWOS:
        return word - (1 << width_bits) if word >> (width_bits - 1) else word
    if encoding == ENC_UNSIGNED:
        return word
    if encoding == ENC_SIGN_MAGNITUDE:
        magnitude = word & ((1 << (width_bits - 1)) - 1)
        return -magnitude if word >> (width_bits - 1) else magnitude
    raise TemplateError(f"unsupported encoding {encoding}")


@dataclass
class EngineResult:
    data: bytes
    saturated: bool
    words_executed: int


def run_program(
    ram: Sequence[int],
    base: int,
    *,
    device_values: Sequence[int],
    device_ids: Sequence[int] = (0,) * CHANNEL_COUNT,
    rr_channel: int = 0,
    seq_byte: int = 0,
) -> EngineResult:
    """Reference execution of one program, byte-exact with arm_frame_formatter."""

    validate_program(ram, base)
    if len(device_values) != CHANNEL_COUNT or len(device_ids) != CHANNEL_COUNT:
        raise TemplateError("six device values and six device ids are required")
    if not 0 <= rr_channel < CHANNEL_COUNT:
        raise TemplateError("rr_channel out of range")
    output = bytearray()
    saturated = False
    ck_active = False
    ck_kind = CK_SUM8
    ck_acc = 0
    executed = 0

    def emit(values: Iterable[int]) -> None:
        nonlocal ck_acc
        for byte in values:
            output.append(byte & 0xFF)
            if ck_active:
                ck_acc = (ck_acc + byte) & 0xFF if ck_kind == CK_SUM8 else ck_acc ^ byte

    address = base
    while True:
        opcode, operand = decode_word(ram[address])
        executed += 1
        address += 1
        if opcode == OP_END:
            break
        if opcode == OP_LIT:
            emit([operand & 0xFF])
        elif opcode == OP_DEC:
            channel = operand & 0x7
            text = format_fixed_decimal(device_values[channel], (operand >> 4) & 0x7)
            emit(text.encode("ascii"))
        elif opcode == OP_BIN:
            channel = operand & 0x7
            width_bits = 16 if ((operand >> 3) & 0x3) == WIDTH_16 else 32
            data, sat = encode_binary_field(
                device_values[channel],
                width_bits,
                big_endian=bool((operand >> 5) & 1),
                encoding=(operand >> 6) & 0x3,
            )
            saturated |= sat
            emit(data)
        elif opcode == OP_CKB:
            ck_active = True
            ck_kind = operand & 1
            ck_acc = 0
        elif opcode == OP_CKE:
            ck_active = False
            output.append((~ck_acc if operand & 1 else ck_acc) & 0xFF)
        elif opcode == OP_IDB:
            channel = rr_channel if operand & 0x8 else operand & 0x7
            emit([device_ids[channel]])
        elif opcode == OP_SEQ:
            emit([seq_byte & 0xFF])
    return EngineResult(bytes(output), saturated, executed)


@dataclass
class TemplateImage:
    """Template RAM contents plus program entry points for the PL loader."""

    ram: list[int] = field(default_factory=lambda: [end()] * TEMPLATE_DEPTH)
    cmd_base: int = 0
    req_base: int = 0
    req_enable: bool = False
    cmd_words: int = 0
    req_words: int = 0

    @classmethod
    def build(
        cls, cmd_program: Sequence[int], req_program: Sequence[int] | None = None
    ) -> "TemplateImage":
        cmd = list(cmd_program)
        req = list(req_program) if req_program else []
        if not cmd or decode_word(cmd[-1])[0] != OP_END:
            raise TemplateError("command program must end with END")
        if req and decode_word(req[-1])[0] != OP_END:
            raise TemplateError("request program must end with END")
        if len(cmd) + len(req) > TEMPLATE_DEPTH:
            raise TemplateError(
                f"programs need {len(cmd) + len(req)} words, RAM has {TEMPLATE_DEPTH}"
            )
        image = cls()
        image.ram[: len(cmd)] = cmd
        image.cmd_base = 0
        image.cmd_words = len(cmd)
        if req:
            image.req_base = len(cmd)
            image.ram[image.req_base : image.req_base + len(req)] = req
            image.req_enable = True
            image.req_words = len(req)
        validate_program(image.ram, image.cmd_base)
        if image.req_enable:
            validate_program(image.ram, image.req_base)
        return image
