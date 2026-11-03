"""AI PC <-> PYNQ PS link protocol (Phase 3 S6 candidate, version 1).

Only low-rate high-level messages cross the network: target request, one-shot sparse path, result,
task status, ordinary cancel, heartbeat.  The PC never sends per-period motion; the PL generates
every sample.  Fixed little-endian binary messages over one TCP connection; no fragmentation, no
per-point acknowledgement, no extra CRC (TCP already checks integrity) - as the project plan asks.

Frame: header 16 bytes  magic b"P3S6" | version u16 | type u16 | seq u32 | payload length u32
Messages (payload layouts in _LAYOUT):
  HELLO          both   role u8 (1 PC, 2 PS), interp_version u32, contract_version u16
  TARGET_REQUEST PS->PC task_id u32, object_id u8, mode u8 (2 = mode B), home[6] i32, pre_delivery[6] i32,
                        period_cycles u32, path_deadline_ms u32
  PATH_SUBMIT    PC->PS task_id u32, object_id u8, ik_kind u8, calib_id u32, interp_version u32,
                        contract_version u16, digest 32 B, n_seg u8, then n_seg x (target[6] i32, n u16,
                        na u16, profile u8, flags u8, 2 B pad)
  PATH_RESULT    PS->PC task_id u32, result u8, problem u8, detail u16
  STATUS         PS->PC task_id u32, task_state u8, s4_state u8, s4_phase u8, s4_fault u8, s4_refuse u8,
                        executable u8 (1 = real-arm execution allowed), events u16
  CANCEL         PC->PS task_id u32   (ordinary cancel -> S4 CANCEL; not an e-stop)
  HEARTBEAT      both   (empty)
  BYE            both   (empty)
  LIMITS         PS->PC joint_min[6] i32, joint_max[6] i32, vmax[6] u32, amax[6] u32, period_cycles u32,
                        stall_cycles u32, status u8 (0 TBD, 1 BENCH, 2 MEASURED) - sent right after HELLO, so the
                        PC plans against exactly the limits the PS will check (no second config copy)
Session: PC connects, sends HELLO; PS answers HELLO + LIMITS (or BYE and closes on a version
mismatch).  A PATH_SUBMIT is only considered after the complete message has arrived (the length
field covers it), so a path is committed once, whole, or not at all.
Any bad magic / version / type / length closes the connection (LinkError).
"""

from __future__ import annotations

import socket
import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

import phase3_path_contract as pc

MAGIC = b"P3S6"
PROTOCOL_VERSION = 1
HEADER = struct.Struct("<4sHHII")
MAX_PAYLOAD = 4096
SEGMENT = struct.Struct("<6iHHBB2x")


class MsgType(IntEnum):
    HELLO = 1
    TARGET_REQUEST = 2
    PATH_SUBMIT = 3
    PATH_RESULT = 4
    STATUS = 5
    CANCEL = 6
    HEARTBEAT = 7
    BYE = 8
    LIMITS = 9


class PathResult(IntEnum):
    COMMITTED = 0          # validated on the PS and accepted by the PL PATH_COMMIT
    REJECTED = 1           # contract check failed (problem code in 'problem')
    DUPLICATE = 2          # this task id was already committed / finished: not executed again
    NO_TASK = 3            # no task waiting for a path (e.g. S4 path wait already timed out)
    WRONG_OBJECT = 4
    NOT_EXECUTABLE = 5     # real-arm mode and a TBD precondition (calibration / limits / IK / period)
    PL_REJECTED = 6        # S4 PATH_COMMIT scan rejected it (PATH_REJECTED)
    LINK_STATE = 7         # link not in session (no HELLO / after BYE)


class TaskState(IntEnum):
    IDLE = 0
    WAIT_PATH = 1
    COMMITTED = 2
    RUNNING = 3
    DONE = 4
    CANCELLED = 5
    FAULT = 6
    REFUSED = 7
    HALTED = 8             # stopped and holding (mode B HOLD policy): waits for a human


class LinkError(RuntimeError):
    pass


_LAYOUT = {
    MsgType.HELLO: struct.Struct("<BIH"),
    MsgType.TARGET_REQUEST: struct.Struct("<IBB6i6iII"),
    MsgType.PATH_RESULT: struct.Struct("<IBBH"),
    MsgType.STATUS: struct.Struct("<IBBBBBBH"),
    MsgType.CANCEL: struct.Struct("<I"),
    MsgType.HEARTBEAT: struct.Struct("<"),
    MsgType.BYE: struct.Struct("<"),
    MsgType.LIMITS: struct.Struct("<6i6i6I6IIIB"),
}
LIMIT_STATUS = {"TBD": 0, "BENCH": 1, "MEASURED": 2}
LIMIT_STATUS_NAME = {v: k for k, v in LIMIT_STATUS.items()}
_SUBMIT_HEAD = struct.Struct("<IBBIIH32sB")


@dataclass(frozen=True)
class Message:
    type: MsgType
    seq: int
    fields: tuple


def encode(msg_type: MsgType, seq: int, fields: tuple = ()) -> bytes:
    if msg_type == MsgType.PATH_SUBMIT:
        payload = encode_plan(fields[0])
    else:
        payload = _LAYOUT[msg_type].pack(*fields)
    return HEADER.pack(MAGIC, PROTOCOL_VERSION, int(msg_type), seq & 0xFFFF_FFFF, len(payload)) + payload


def encode_plan(plan: pc.PathPlan) -> bytes:
    if len(plan.segments) > pc.MAX_SEGMENTS:
        raise ValueError("too many segments")
    head = _SUBMIT_HEAD.pack(plan.task_id, plan.object_id, int(plan.ik_kind), plan.calib_id, plan.interp_version,
                             plan.contract_version, plan.sample_digest.ljust(32, b"\0")[:32], len(plan.segments))
    body = b"".join(SEGMENT.pack(*s.target, s.n, s.na, s.profile, s.flags) for s in plan.segments)
    return head + body


def decode_plan(payload: bytes, start_pose: tuple) -> pc.PathPlan:
    if len(payload) < _SUBMIT_HEAD.size:
        raise LinkError("short PATH_SUBMIT")
    tid, obj, ik, calib, interp, cver, digest, n = _SUBMIT_HEAD.unpack_from(payload, 0)
    if len(payload) != _SUBMIT_HEAD.size + n * SEGMENT.size:
        raise LinkError("PATH_SUBMIT length does not match the segment count")
    segs = []
    for k in range(n):
        v = SEGMENT.unpack_from(payload, _SUBMIT_HEAD.size + k * SEGMENT.size)
        segs.append(pc.Segment(tuple(v[:6]), v[6], v[7], v[8], v[9]))
    return pc.PathPlan(tid, obj, tuple(start_pose), tuple(segs), calib, pc.IKKind(ik) if ik in (0, 1) else pc.IKKind.SYNTHETIC,
                       digest, interp, cver)


def decode(header: bytes, payload: bytes) -> Message:
    magic, version, mtype, seq, length = HEADER.unpack(header)
    if magic != MAGIC:
        raise LinkError(f"bad magic {magic!r}")
    if version != PROTOCOL_VERSION:
        raise LinkError(f"protocol version {version}, expected {PROTOCOL_VERSION}")
    try:
        t = MsgType(mtype)
    except ValueError as exc:
        raise LinkError(f"unknown message type {mtype}") from exc
    if len(payload) != length:
        raise LinkError("payload length mismatch")
    if t == MsgType.PATH_SUBMIT:
        return Message(t, seq, (payload,))          # decoded by the PS against its own HOME pose
    lay = _LAYOUT[t]
    if length != lay.size:
        raise LinkError(f"{t.name} payload {length} bytes, expected {lay.size}")
    return Message(t, seq, lay.unpack(payload))


def limits_fields(lim: pc.MotionLimits) -> tuple:
    return (*lim.joint_min, *lim.joint_max, *lim.vmax_q16, *lim.amax_q32, lim.period_cycles, lim.stall_cycles,
            LIMIT_STATUS.get(lim.status, 0))


def limits_from_fields(f: tuple) -> pc.MotionLimits:
    return pc.MotionLimits(tuple(f[0:6]), tuple(f[6:12]), tuple(f[12:18]), tuple(f[18:24]), f[24], f[25],
                           LIMIT_STATUS_NAME.get(f[26], "TBD"))


class FrameParser:
    """Incremental decoder for a byte stream (non-blocking sockets, in-memory transports)."""

    def __init__(self) -> None:
        self._buf = b""

    def feed(self, data: bytes) -> list:
        self._buf += data
        out = []
        while len(self._buf) >= HEADER.size:
            magic, version, _t, _seq, length = HEADER.unpack_from(self._buf, 0)
            if magic != MAGIC or version != PROTOCOL_VERSION:
                raise LinkError(f"bad header magic {magic!r} version {version}")
            if length > MAX_PAYLOAD:
                raise LinkError(f"payload {length} bytes > {MAX_PAYLOAD}")
            if len(self._buf) < HEADER.size + length:
                break
            header, payload = self._buf[:HEADER.size], self._buf[HEADER.size:HEADER.size + length]
            self._buf = self._buf[HEADER.size + length:]
            out.append(decode(header, payload))
        return out


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise LinkError("connection closed")
        buf += chunk
    return buf


def read_message(sock: socket.socket) -> Message:
    header = _recv_exact(sock, HEADER.size)
    length = HEADER.unpack(header)[4]
    if length > MAX_PAYLOAD:
        raise LinkError(f"payload {length} bytes > {MAX_PAYLOAD}")
    return decode(header, _recv_exact(sock, length) if length else b"")


def send_message(sock: socket.socket, msg_type: MsgType, seq: int, fields: tuple = ()) -> None:
    sock.sendall(encode(msg_type, seq, fields))
