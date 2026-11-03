"""RoArm ESP32 binary bridge protocol v1 (project-defined fallback).

This is **our** fixed-length frame between the PL and a future modified ESP32
bridge firmware.  It is only needed if measurements prove the official JSON
path too slow (plan section 11.2 step 3).  The bridge firmware may only convert
these frames into official servo calls and report state; it must not
interpolate, plan or own task state.  S1 ships the frame definition, this
reference codec and PL TX support (via the frame template engine).  The PL RX
parser and the ESP32 firmware are deferred until the JSON throughput test
shows they are needed.

Command frame (PL -> bridge), 18 bytes::

    A5 5A | LEN=14 | TYPE=0x01 | SEQ | POS0..POS5 int16 LE | CK
    CK = ~(sum8 of LEN..last POS byte)

State frame (bridge -> PL), 19 bytes::

    A5 5A | LEN=15 | TYPE=0x81 | SEQ_ECHO | STATUS | POS0..POS5 int16 LE | CK

``POS`` is in the bridge's device unit (declared in the profile).  Values
saturate to int16; saturation is reported by the PL encode_saturation flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import arm_frame_template as aft
from arm_fixed_point import CHANNEL_COUNT


BRIDGE_PROTOCOL = "roarm_binary_bridge_v1"
SYNC = (0xA5, 0x5A)
TYPE_JOINT_TARGET = 0x01
TYPE_JOINT_STATE = 0x81
COMMAND_LEN = 14
STATE_LEN = 15
COMMAND_FRAME_BYTES = 18
STATE_FRAME_BYTES = 19


class BridgeFrameError(ValueError):
    """A bridge frame is malformed."""


def checksum(payload: bytes) -> int:
    return (~sum(payload)) & 0xFF


def compile_command_template() -> list[int]:
    words = [aft.lit(SYNC[0]), aft.lit(SYNC[1]), aft.ckb(aft.CK_SUM8)]
    words += [aft.lit(COMMAND_LEN), aft.lit(TYPE_JOINT_TARGET), aft.seq()]
    for channel in range(CHANNEL_COUNT):
        words.append(aft.binf(channel, 16, big_endian=False, encoding=aft.ENC_TWOS))
    words += [aft.cke(invert=True), aft.end()]
    return words


def encode_command(device_values: Sequence[int], seq: int) -> tuple[bytes, bool]:
    if len(device_values) != CHANNEL_COUNT:
        raise BridgeFrameError("six device values are required")
    body = bytearray([COMMAND_LEN, TYPE_JOINT_TARGET, seq & 0xFF])
    saturated = False
    for value in device_values:
        data, sat = aft.encode_binary_field(value, 16, big_endian=False, encoding=aft.ENC_TWOS)
        body += data
        saturated |= sat
    return bytes(SYNC) + bytes(body) + bytes([checksum(bytes(body))]), saturated


@dataclass(frozen=True)
class BridgeState:
    seq_echo: int
    status: int
    device_values: tuple[int, ...]


def encode_state(state: BridgeState) -> bytes:
    """Used by PC-side bridge emulators and tests."""

    body = bytearray([STATE_LEN, TYPE_JOINT_STATE, state.seq_echo & 0xFF, state.status & 0xFF])
    for value in state.device_values:
        body += aft.encode_binary_field(value, 16, big_endian=False, encoding=aft.ENC_TWOS)[0]
    return bytes(SYNC) + bytes(body) + bytes([checksum(bytes(body))])


def decode_state(frame: bytes) -> BridgeState:
    if len(frame) != STATE_FRAME_BYTES:
        raise BridgeFrameError(f"state frame must be {STATE_FRAME_BYTES} bytes")
    if tuple(frame[:2]) != SYNC:
        raise BridgeFrameError("bad sync bytes")
    if frame[2] != STATE_LEN or frame[3] != TYPE_JOINT_STATE:
        raise BridgeFrameError("unexpected LEN/TYPE")
    if checksum(frame[2:-1]) != frame[-1]:
        raise BridgeFrameError("checksum mismatch")
    values = tuple(
        aft.decode_binary_field(frame[6 + 2 * ch : 8 + 2 * ch], big_endian=False, encoding=aft.ENC_TWOS)
        for ch in range(CHANNEL_COUNT)
    )
    return BridgeState(frame[4], frame[5], values)


class BridgeStateStreamParser:
    """Resynchronizing byte-stream parser for PC/PS tools (no PL model in S1)."""

    def __init__(self) -> None:
        self.buffer = bytearray()
        self.errors = 0

    def feed(self, data: bytes) -> list[BridgeState]:
        self.buffer += data
        states: list[BridgeState] = []
        while True:
            start = self.buffer.find(bytes(SYNC))
            if start < 0:
                del self.buffer[:-1]
                return states
            del self.buffer[:start]
            if len(self.buffer) < STATE_FRAME_BYTES:
                return states
            candidate = bytes(self.buffer[:STATE_FRAME_BYTES])
            try:
                states.append(decode_state(candidate))
                del self.buffer[:STATE_FRAME_BYTES]
            except BridgeFrameError:
                self.errors += 1
                del self.buffer[:1]
