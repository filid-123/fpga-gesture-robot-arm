"""PS driver of the Phase 3 S4 task controller window (ABI 0x0000_3401, candidate;
0x0000_3402 when the RTL is built with the tray-exit patch, TRAY_EXIT = 1).

Register map: docs/PHASE3_S4_TASK_REGISTER_MAP_CN.md (RTL rtl/robot/s4_task_regs.v).
Proposed base 0x43C5_0000 / 4 KiB (not frozen), IRQ_F2P[3].  S1/S2 windows and
ABIs are unchanged (0x43C2 0x3002, 0x43C3 0x3101, 0x43C4 0x3201).

Rules the driver follows:
  * CONTROL takes exactly one bit per write; the result is read back from
    CMD_RESULT (the S4 window answers OKAY for rejected commands and locked
    configuration writes - a bus error would kill the PYNQ process);
  * configuration and tables only in OFF/IDLE (FIFO also in WAIT_PATH);
  * while S4 owns motion, writes to the S1/S2 windows are dropped by the PL
    (EVENT.PS_WRITE_BLOCKED); release ownership before using S1/S2 drivers.
Tray-exit patch: MODE_CFG[4] tray_exit, PATH_TRAY (0x120, {count[13:8], first[5:0]}, locked like
the other descriptors), STATUS[24] tray_ok_task, STATUS[25] tray_active.  The PATH_TRAY write is
emitted only for a non-empty tray path, and MODE_CFG[4] only when tray_exit is set, so the
register traffic of a v0.1.1 configuration is unchanged.
No hardware is touched by this module unless an MMIO object is passed in.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

import s4_task_reference as m

ABI_VERSION = 0x0000_3401
ABI_VERSION_TRAY = 0x0000_3402
PATH_TRAY = 0x120            # tray-exit patch
MMIO_SIZE = 0x1000
PROPOSED_BASE_ADDRESS = 0x43C5_0000

CONTROL, STATUS, FAULT, EVENT, ABI, CAPABILITIES, IRQ_ENABLE, CMD_RESULT, PROGRESS = (
    0x000, 0x004, 0x008, 0x00C, 0x010, 0x014, 0x018, 0x01C, 0x020)
MODE_CFG, TICK_PRESCALE, T_PALM_HOLD, T_PALM_WAIT, BLIND_PERIODS = 0x024, 0x028, 0x02C, 0x030, 0x034
T_ARRIVAL, T_COMM, T_PATH_WAIT, T_HEARTBEAT, MOVE_MARGIN = 0x038, 0x03C, 0x040, 0x044, 0x048
PERIOD_CYCLES, STALL_CYCLES, KP_CFG, TASK_REQUEST, PATH_INFO, VISION_SIM = 0x04C, 0x050, 0x054, 0x058, 0x05C, 0x060
FIFO_STATUS, FIFO_DATA = 0x064, 0x068
JOINT_MIN, JOINT_MAX, VMAX, AMAX = 0x080, 0x098, 0x0B0, 0x0C8
PATH_BASE = 0x0E0            # 12 descriptors: approach1..3, grasp1..3, lift1..3, deliver, release, retreat
KP_ADDR, KP_DATA, SEG_ADDR, SEG_DATA = 0x110, 0x114, 0x118, 0x11C
T_S1_STATUS, T_S1_ERROR, T_FB_MASKS, T_FB_AGE, T_FRAMES = 0x200, 0x204, 0x208, 0x20C, 0x210
T_PL_STATUS, T_PL_ERROR, T_PL_INDEX, T_LAST = 0x214, 0x218, 0x21C, 0x220
CNT_DONE, CNT_CANCEL, CNT_FAULT, CNT_REFUSE, CNT_BLIND, CNT_PS_BLOCK, LAST_DROPPED, CNT_POLLS, LAST_TASK_ID = (
    0x240, 0x244, 0x248, 0x24C, 0x250, 0x254, 0x258, 0x25C, 0x260)
MASK32 = 0xFFFF_FFFF


def u32(value: int) -> int:
    return value & MASK32


def s32(value: int) -> int:
    value &= MASK32
    return value - (1 << 32) if value & 0x8000_0000 else value


def mode_cfg_word(cfg: m.S4Config, vision_sim: bool = False) -> int:
    return (int(cfg.mode_b) | int(cfg.require_line) << 1 | int(cfg.hold_policy) << 2 | int(vision_sim) << 3
            | int(getattr(cfg, "tray_exit", False)) << 4 | (cfg.rearm_mask & 0xFF) << 8 | (cfg.select_mask & 0xFF) << 16)


def config_writes(cfg: m.S4Config, *, vision_sim: bool = False) -> list:
    w = [(MODE_CFG, mode_cfg_word(cfg, vision_sim)), (TICK_PRESCALE, cfg.tick_prescale),
         (T_PALM_HOLD, cfg.t_palm_hold), (T_PALM_WAIT, cfg.t_palm_wait), (BLIND_PERIODS, cfg.blind_periods),
         (T_ARRIVAL, cfg.t_arrival), (T_COMM, cfg.t_comm), (T_PATH_WAIT, cfg.t_path_wait),
         (T_HEARTBEAT, cfg.t_heartbeat), (MOVE_MARGIN, cfg.move_margin), (PERIOD_CYCLES, cfg.period_cycles),
         (STALL_CYCLES, cfg.stall_cycles),
         (KP_CFG, (cfg.arrival_mask & 0x3F) | (cfg.home_kp & 0x3F) << 8 | (cfg.predelivery_kp & 0x3F) << 16)]
    for base, values in ((JOINT_MIN, cfg.joint_min), (JOINT_MAX, cfg.joint_max), (VMAX, cfg.vmax), (AMAX, cfg.amax)):
        w += [(base + 4 * ch, u32(v)) for ch, v in enumerate(values)]
    return w


def seg_words(kp: int, n: int, na: int, profile: int, flags: int) -> tuple:
    return ((flags & 0xFF) << 24 | (profile & 1) << 16 | (kp & 0x3F), (na & 0xFFFF) << 16 | (n & 0xFFFF))


def path_desc(desc: tuple) -> int:
    first, count = desc
    return (count & 0x3F) << 8 | (first & 0x3F)


def table_writes(tables: m.S4Tables) -> list:
    w = [(KP_ADDR, 0)]                     # KP_ADDR = {kp, ch}; advances to the next kp after ch 5
    for kp in range(m.KP_DEPTH):
        w += [(KP_DATA, u32(v)) for v in tables.keypoints[kp]]
    w.append((SEG_ADDR, 0))
    for seg in range(m.SEG_DEPTH):
        w += [(SEG_DATA, word) for word in seg_words(*tables.segments[seg])]
    descs = ([tables.approach[k] for k in (1, 2, 3)] + [tables.grasp[k] for k in (1, 2, 3)]
             + [tables.lift[k] for k in (1, 2, 3)] + [tables.deliver, tables.release, tables.retreat])
    w += [(PATH_BASE + 4 * i, path_desc(d)) for i, d in enumerate(descs)]
    tray = getattr(tables, "tray", (0, 0))
    if tray[1]:
        w.append((PATH_TRAY, path_desc(tray)))
    return w


def fifo_writes(segments: Iterable[m.Segment]) -> list:
    w = []
    for s in segments:
        w += [(FIFO_DATA, u32(v)) for v in s.target]
        w += [(FIFO_DATA, (s.flags & 0xFF) << 24 | (s.profile & 1) << 16), (FIFO_DATA, (s.na & 0xFFFF) << 16 | (s.n & 0xFFFF))]
    return w


def command_word(cmd: m.Cmd) -> int:
    return 1 << int(cmd)


@dataclass(frozen=True)
class S4Status:
    raw: int

    @property
    def state(self) -> m.State:
        return m.State(self.raw & 0xF)

    @property
    def phase(self) -> m.Phase:
        return m.Phase((self.raw >> 4) & 7)

    owner_s4 = property(lambda self: bool(self.raw >> 7 & 1))
    armed = property(lambda self: bool(self.raw >> 8 & 1))
    holding = property(lambda self: bool(self.raw >> 9 & 1))
    released = property(lambda self: bool(self.raw >> 10 & 1))
    fault_latched = property(lambda self: bool(self.raw >> 11 & 1))
    motion_enable = property(lambda self: bool(self.raw >> 12 & 1))
    estop_ok = property(lambda self: bool(self.raw >> 13 & 1))
    feedback_checks = property(lambda self: bool(self.raw >> 14 & 1))
    ready_latched = property(lambda self: bool(self.raw >> 15 & 1))
    cancel_req = property(lambda self: bool(self.raw >> 16 & 1))
    blind_req = property(lambda self: bool(self.raw >> 17 & 1))
    link_busy = property(lambda self: bool(self.raw >> 18 & 1))
    mode_b = property(lambda self: bool(self.raw >> 19 & 1))
    object = property(lambda self: self.raw >> 20 & 3)
    move_active = property(lambda self: bool(self.raw >> 22 & 1))
    window_hung = property(lambda self: bool(self.raw >> 23 & 1))
    tray_ok = property(lambda self: bool(self.raw >> 24 & 1))          # tray-exit patch
    tray_active = property(lambda self: bool(self.raw >> 25 & 1))      # tray-exit patch


class S4CommandError(RuntimeError):
    def __init__(self, cmd: m.Cmd, result: int):
        super().__init__(f"S4 command {cmd.name} rejected: {m.CmdReject(result).name if result < 6 else result}")
        self.cmd, self.result = cmd, result


class S4TaskAxiDriver:
    def __init__(self, mmio, *, sleeper: Callable[[float], None] = time.sleep):
        self.mmio = mmio
        self.sleep = sleeper

    @classmethod
    def from_pynq(cls, base_address: int = PROPOSED_BASE_ADDRESS) -> "S4TaskAxiDriver":
        from pynq import MMIO                                # board only
        return cls(MMIO(base_address, MMIO_SIZE))

    def read(self, offset: int) -> int:
        return int(self.mmio.read(offset)) & MASK32

    def write(self, offset: int, value: int) -> None:
        self.mmio.write(offset, u32(value))

    def write_all(self, writes: Sequence[tuple]) -> None:
        for offset, value in writes:
            self.write(offset, value)

    def assert_abi(self, expected: int = ABI_VERSION) -> None:
        abi = self.read(ABI)
        if abi != expected:
            raise RuntimeError(f"S4 ABI 0x{abi:08X}, expected 0x{expected:08X}")

    def status(self) -> S4Status:
        return S4Status(self.read(STATUS))

    def fault(self) -> tuple:
        raw = self.read(FAULT)
        return m.Fault(raw & 0xFF), (raw >> 8) & 0xFF, m.Refuse((raw >> 16) & 0xFF)

    def events(self, clear: bool = True) -> list:
        raw = self.read(EVENT)
        if clear and raw:
            self.write(EVENT, raw)
        return [e for e in m.Event if raw >> int(e) & 1]

    def command(self, cmd: m.Cmd, *, check: bool = True, timeout_s: float = 0.1) -> int:
        before = self.read(CMD_RESULT) >> 16
        self.write(CONTROL, command_word(cmd))
        deadline = time.monotonic() + timeout_s
        while True:
            res = self.read(CMD_RESULT)
            if (res >> 16) != before and (res & 0xF) == int(cmd):
                code = (res >> 8) & 0xF
                break
            if time.monotonic() > deadline:
                raise TimeoutError(f"S4 command {cmd.name}: no result")
            self.sleep(0.001)
        if check and code != 0:
            raise S4CommandError(cmd, code)
        return code

    def load(self, cfg: m.S4Config, tables: m.S4Tables, *, vision_sim: bool = False) -> None:
        st = self.status().state
        if st not in (m.State.OFF, m.State.IDLE):
            raise RuntimeError(f"configuration only in OFF/IDLE, state is {st.name}")
        self.write_all(config_writes(cfg, vision_sim=vision_sim))
        self.write_all(table_writes(tables))
        if m.Event.CONFIG_LOCKED in self.events():
            raise RuntimeError("a configuration write was locked")

    def commit_path(self, obj: int, task_id: int, segments: Sequence[m.Segment]) -> None:
        self.command(m.Cmd.PATH_RESET)
        self.write_all(fifo_writes(segments))
        self.write(PATH_INFO, (task_id & 0xFFFF) << 16 | (obj & 3))
        self.command(m.Cmd.PATH_COMMIT)

    def start_task(self, obj: int, task_id: int) -> None:
        self.write(TASK_REQUEST, (task_id & 0xFFFF) << 16 | (obj & 3))
        self.command(m.Cmd.START_TASK)

    def vision_sim(self, cls_code: int, *, valid: bool = True, window_ok: bool = False, changed: bool = True) -> None:
        self.write(VISION_SIM, (cls_code & 7) | int(valid) << 3 | int(window_ok) << 4 | int(changed) << 8)

    def wait_state(self, states: set, timeout_s: float, poll_s: float = 0.005) -> S4Status:
        deadline = time.monotonic() + timeout_s
        while True:
            st = self.status()
            if st.state in states:
                return st
            if time.monotonic() > deadline:
                raise TimeoutError(f"S4 state {st.state.name}, waiting for {[s.name for s in states]}")
            self.sleep(poll_s)
