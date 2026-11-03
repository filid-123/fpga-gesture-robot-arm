"""Reference model of the Phase 3 S4 PL task controller (ABI 0x0000_3401, candidate;
ABI 0x0000_3402 with the tray-exit patch built in, see "Tray exit" below).

The model defines the task semantics that rtl/robot/s4_task_fsm.v implements.  It
works on ticks (TICK_PRESCALE cycles, 1 ms by default) and on the same abstract
downstream operations as rtl/robot/s4_motion_link.v:

  POLL                           snapshot of the S1 backend (0x3101) and S2 planner (0x3201)
  MOVE(target, N, Na, profile)   29 planner register writes + START, START = LAST_DELIVERED
  PAUSE / RESUME / CLEAR / ESTOP planner CONTROL commands
  SOURCE(v)                      planner SOURCE_SELECT

The plant (planner + backend) is abstracted by ``Plant``; the RTL testbenches use
the real, unchanged S1 v0.1.1 / S2 v0.2.3 RTL instead.  Model and RTL are compared
on the ACTION TRACE (MOVE targets and planner commands in order), final state,
fault/refuse codes and events - not cycle by cycle.

Task (mode A = fixed PL tables, mode B = path committed by the PS; one skeleton):
  IDLE --OBJECT_k change event, armed by a re-arm class (BACKGROUND/NO_DETECTION)-->
  [mode B: WAIT_PATH --PATH_COMMIT--> path check] --> PRECHECK --> RUN(OUT: approach,
  grasp, lift, ends at PRE_DELIVERY) --> WAIT_PALM --PALM_READY and palm_window_ok for
  T_PALM_HOLD ticks--> READY latched --> RUN(DELIVER) --release gate--> RUN(RELEASE)
  --> RUN(RETREAT, ends at HOME) --> IDLE (disarmed until a re-arm class is seen).
Every completed OUT/DELIVER segment is pushed onto a retrace stack {start pose, N,
Na, profile, flags}.  After every completed or stopped move ONE decision function,
next_action(), chooses what happens next:
  cancel or blind request pending (and nothing released yet):
     holding and HOLD policy and cancel      -> HALT (stop and hold, PS takes over)
     the last move was stopped part-way      -> move back to that move's start pose
     stack above the floor                   -> pop, move back to the popped start pose
                                                 (popping the grasp segment re-opens the
                                                 gripper: the object goes back to its slot)
     floor reached: cancel -> CANCELLED -> IDLE;  blind -> WAIT_PALM again
     floor = 0 for a cancel, the stack level at the start of DELIVER for a blind request
  otherwise the next segment of the phase, or the next phase.
Cancel (FIST_CANCEL event, PS CANCEL, palm-wait timeout, PS heartbeat timeout in
mode B) stops the running move at once if its segment has STOP_ON_CANCEL (or when
the HOLD policy applies), else the move is finished first.  After RELEASE started a
cancel is ignored (never take the object back from the user).
Blind delivery: RELEASE starts only if blind + N(release) <= BLIND_PERIODS sample
periods after the READY latch; if the window runs out during DELIVER the move is
stopped at once.  Either way: no release, retrace to PRE_DELIVERY, WAIT_PALM again.
Faults (latched): e-stop input, S1 fault, S1 permission lost (LINE), planner
ERROR/ESTOP, move timeout, arrival timeout (LINE), comm timeout (LINE: no new feedback
record), AXI error/timeout, LAST_DELIVERED != target after DONE, PS ABORT.  A fault
revokes the motion permission at once (motion_enable to S1 low), sends planner ESTOP,
and blocks every later motion until RELEASE (ownership back to PS) and FAULT_CLEAR.

Tray exit (patch candidate, RTL parameter TRAY_EXIT = 1, ABI 0x0000_3402; off by default):
mode B, MODE_CFG.tray_exit = 1 and a fixed tray path (PATH_TRAY: segment-table path that starts at
PRE_DELIVERY, opens the gripper over the fixed return tray and ends at HOME) that passed the
PATH_COMMIT scan (non-empty, every target inside the joint limits, last keypoint = HOME) arm a
validated exit for that task (tray_ok_task).  A cancel while holding and not released then never
halts and never returns the object to its (random) grasp position:
  holding during OUT     the current move is finished (never stopped) and the rest of the COMMITTED
                         OUT path is completed up to PRE_DELIVERY (cancel stays pending);
  at PRE_DELIVERY        (WAIT_PALM, or OUT just completed) -> TRAY phase;
  during DELIVER         the stop / retrace rules above apply with the floor at the DELIVER start
                         (= PRE_DELIVERY) instead of 0, then -> TRAY phase;
  TRAY phase             forward segments of PATH_TRAY, not pushed, further cancels ignored; at the
                         end TASK_CANCELLED (cancel counter) and IDLE.
Without a validated tray path the v0.1.1 behaviour applies unchanged (HOLD policy -> HALT).
sp_deliver is also set when OUT completes (same value as at the DELIVER start, so the v0.1.1
blind-retrace floor is unchanged).

Truth boundary: reference model of a source candidate; no arm, no board.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import IntEnum
from typing import Callable, Optional, Sequence

CHANNELS = 6
ABI_VERSION = 0x0000_3401
ABI_VERSION_TRAY = 0x0000_3402          # RTL built with TRAY_EXIT = 1 (patch candidate)
KP_DEPTH = 64
SEG_DEPTH = 64
FIFO_SEGMENTS = 32
STACK_DEPTH = 32
INT32_MIN, INT32_MAX = -(1 << 31), (1 << 31) - 1

# Vision codes of the S3 candidate interface (S3 docs/05).
BACKGROUND, OBJECT_1, OBJECT_2, OBJECT_3, PALM_READY, FIST_CANCEL, OTHER_INVALID, NO_DETECTION = range(8)


class State(IntEnum):
    OFF = 0
    IDLE = 1
    WAIT_PATH = 2
    PRECHECK = 3
    RUN = 4
    WAIT_PALM = 5
    PAUSED = 6
    STOPPING = 7
    RETRACE = 8
    HALT = 9
    FAULT = 10


class Phase(IntEnum):
    NONE = 0
    OUT = 1
    DELIVER = 2
    RELEASE = 3
    RETREAT = 4
    TRAY = 5                    # tray-exit patch: cancel return to the fixed tray (mode B)


class Fault(IntEnum):
    NONE = 0
    ESTOP_INPUT = 1
    S1_FAULT = 2
    S1_PERMISSION_LOST = 3
    PLANNER_ERROR = 4
    MOVE_TIMEOUT = 5
    ARRIVAL_TIMEOUT = 6
    COMM_TIMEOUT = 7
    AXI_ERROR = 8
    STATE_MISMATCH = 9
    ABORT = 10


class Refuse(IntEnum):
    NONE = 0
    ESTOP = 1
    S1_NOT_READY = 2
    S1_MODE = 3
    PLANNER_NOT_READY = 4
    NOT_AT_HOME = 5
    TABLE_INVALID = 6
    RANGE = 7
    DUPLICATE_TASK = 8
    PATH_INVALID = 9
    LINK_ERROR = 10


class Event(IntEnum):
    TASK_DONE = 0
    TASK_CANCELLED = 1
    TASK_REFUSED = 2
    FAULT = 3
    SELECTED = 4
    PATH_ACCEPTED = 5
    PATH_REJECTED = 6
    CANCEL_IGNORED = 7
    BLIND_TIMEOUT = 8
    PALM_TIMEOUT = 9
    HALTED = 10
    PS_WRITE_BLOCKED = 11
    CMD_REJECTED = 12
    HEARTBEAT_TIMEOUT = 13
    CONFIG_LOCKED = 14
    PATH_TIMEOUT = 15


class Cmd(IntEnum):
    ENABLE = 0
    RELEASE = 1
    START_TASK = 2
    CANCEL = 3
    PAUSE = 4
    RESUME = 5
    ABORT = 6
    FAULT_CLEAR = 7
    PATH_COMMIT = 8
    PATH_RESET = 9
    HEARTBEAT = 10


class CmdReject(IntEnum):
    ACCEPTED = 0
    MULTI_BIT = 1
    STATE = 2
    FAULT_LATCHED = 3
    ESTOP = 4
    SOURCE_REFUSED = 5


F_GRASP = 1 << 0            # completing this segment means the gripper holds the object
F_STOP_ON_CANCEL = 1 << 1   # a cancel stops this segment at once (else it is finished first)

# S1 backend STATUS (0x008) bits and active mode [13:12]
S1_CONFIG_VALID, S1_PERMISSION, S1_ESTOP_OK, S1_FAULT_BIT, S1_FEEDBACK_VALID = 0, 2, 3, 4, 5
S1_MODE_OFF, S1_MODE_DRY_RUN, S1_MODE_MONITOR, S1_MODE_LINE = 0, 1, 2, 3
# S2 planner states (STATUS[2:0])
PL_IDLE, PL_VALIDATE, PL_RUN, PL_PAUSED, PL_DONE, PL_ERROR, PL_ESTOP = range(7)
PL_FATAL_MASK = 0x3F


@dataclass(frozen=True)
class Segment:
    target: tuple
    n: int
    na: int
    profile: int
    flags: int = 0


@dataclass(frozen=True)
class S4Config:
    mode_b: bool = False
    require_line: bool = False
    hold_policy: bool = False                 # True: HALT when cancelled while holding (mode B default)
    rearm_mask: int = (1 << BACKGROUND) | (1 << NO_DETECTION)
    select_mask: int = (1 << OBJECT_1) | (1 << OBJECT_2) | (1 << OBJECT_3)
    tick_prescale: int = 100_000
    t_palm_hold: int = 300          # ticks
    t_palm_wait: int = 20_000       # ticks
    blind_periods: int = 400        # sample periods, READY latch -> end of release
    t_arrival: int = 500            # ticks after planner DONE (LINE)
    t_comm: int = 200               # ticks without a new feedback record (LINE)
    t_path_wait: int = 10_000       # ticks (mode B)
    t_heartbeat: int = 0            # ticks, 0 = off (mode B)
    move_margin: int = 200          # sample periods beyond N
    period_cycles: int = 1_000_000  # planner P for every move (TBD from the arm profile)
    stall_cycles: int = 50_000_000
    arrival_mask: int = 0x3F
    home_kp: int = 0
    predelivery_kp: int = 1
    joint_min: tuple = (INT32_MIN,) * CHANNELS
    joint_max: tuple = (INT32_MAX,) * CHANNELS
    vmax: tuple = (0,) * CHANNELS
    amax: tuple = (0,) * CHANNELS
    tray_exit: bool = False         # tray-exit patch: MODE_CFG[4] (only with the TRAY_EXIT build)


@dataclass
class S4Tables:
    keypoints: list = field(default_factory=lambda: [(0,) * CHANNELS for _ in range(KP_DEPTH)])
    segments: list = field(default_factory=lambda: [(0, 1, 0, 0, 0) for _ in range(SEG_DEPTH)])  # kp,n,na,profile,flags
    approach: dict = field(default_factory=lambda: {1: (0, 0), 2: (0, 0), 3: (0, 0)})           # object -> (first, count)
    grasp: dict = field(default_factory=lambda: {1: (0, 0), 2: (0, 0), 3: (0, 0)})
    lift: dict = field(default_factory=lambda: {1: (0, 0), 2: (0, 0), 3: (0, 0)})
    deliver: tuple = (0, 0)
    release: tuple = (0, 0)
    retreat: tuple = (0, 0)
    tray: tuple = (0, 0)            # tray-exit patch: PATH_TRAY descriptor (first, count)

    def segment(self, index: int) -> Segment:
        kp, n, na, profile, flags = self.segments[index]
        return Segment(tuple(self.keypoints[kp]), n, na, profile, flags)

    def seg_kp(self, index: int) -> int:
        return self.segments[index][0]

    @staticmethod
    def path(desc: tuple) -> list:
        first, count = desc
        return list(range(first, first + count))


@dataclass(frozen=True)
class Poll:
    s1_status: int
    fb_arrival: int
    fb_seq: int
    pl_state: int
    pl_error: int
    pl_pending: bool
    pl_last_valid: bool
    pl_source: int
    last: tuple
    ok: bool = True             # False: the poll itself failed (AXI error or timeout)

    @property
    def s1_mode(self) -> int:
        return (self.s1_status >> 12) & 3


class Plant:
    """Tick-level abstraction of S2 planner + S1 backend (for the reference model only).

    Scenario hooks: s1_fault, feedback_alive, estop_ok, arrival_delay (ticks after
    DONE, None = never), axi_fail, done_ticks_override, validate_fn (S2 reference),
    done_pending_ticks (the planner reports DONE while its last sample is still
    pending in the backend for that many ticks; LAST_DELIVERED is the previous
    sample meanwhile, as with the real S1 frame time; None = forever)."""

    def __init__(self, *, s1_mode: int = S1_MODE_DRY_RUN, home: Sequence[int] = (0,) * CHANNELS,
                 prescale: int = 100_000, validate_fn: Optional[Callable] = None):
        self.s1_mode = s1_mode
        self.config_valid = True
        self.s1_fault = False
        self.permission = s1_mode == S1_MODE_LINE
        self.feedback_valid = s1_mode == S1_MODE_LINE
        self.feedback_alive = True
        self.estop_ok = True
        self.fb_seq = 0
        self.arrival = 0
        self.arrival_delay: Optional[int] = 2
        self.pl_state = PL_IDLE
        self.pl_error = 0
        self.pending = False
        self.source = 0
        self.last = tuple(home)
        self.last_valid = True
        self.prescale = prescale
        self.validate_fn = validate_fn
        self.axi_fail = False
        self.done_ticks_override: Optional[int] = None
        self.done_pending_ticks: Optional[int] = 0
        self._pending_left: Optional[int] = 0
        self._move = None
        self._remaining = 0
        self._elapsed = 0
        self._since_done = 0

    def poll(self) -> Poll:
        status = ((int(self.config_valid) << S1_CONFIG_VALID) | (int(self.permission) << S1_PERMISSION)
                  | (int(self.estop_ok) << S1_ESTOP_OK) | (int(self.s1_fault) << S1_FAULT_BIT)
                  | (int(self.feedback_valid) << S1_FEEDBACK_VALID) | (self.s1_mode << 12))
        return Poll(status, self.arrival, self.fb_seq, self.pl_state, self.pl_error, self.pending,
                    self.last_valid, self.source, self.last, ok=not self.axi_fail)

    def move(self, target, n, na, profile, cfg: S4Config) -> bool:
        if self.axi_fail or self.pl_state not in (PL_IDLE, PL_DONE) or self.pending or self.source != 1:
            return False
        start = self.last
        err = self.validate_fn(start, target, n, na, profile, cfg) if self.validate_fn else 0
        if err:
            self.pl_state, self.pl_error = PL_ERROR, self.pl_error | err
            return True                      # the AXI writes succeed, validation fails afterwards
        self._move = (start, tuple(target))
        self.pl_state = PL_RUN
        ticks = -(-n * cfg.period_cycles // self.prescale)
        self._remaining = self.done_ticks_override if self.done_ticks_override is not None else max(1, ticks)
        self._elapsed = 0
        self.arrival = 0
        return True

    def command(self, name: str) -> bool:
        if self.axi_fail:
            return False
        if name == "PAUSE":
            if self.pl_state != PL_RUN:
                return False
            self.pl_state = PL_PAUSED
            return True
        if name == "RESUME":
            if self.pl_state != PL_PAUSED:
                return False
            self.pl_state = PL_RUN
            return True
        if name == "CLEAR":
            if self.pl_state in (PL_VALIDATE, PL_RUN):
                return False
            if self.pl_state == PL_PAUSED and self._move:
                start, target = self._move        # abandoned part-way: an intermediate pose
                self.last = tuple(s + (t - s) * self._elapsed // max(1, self._elapsed + self._remaining)
                                  for s, t in zip(start, target))
            self.pl_state, self.pl_error, self._move = PL_IDLE, 0, None
            return True
        if name == "ESTOP":
            self.pl_state = PL_ESTOP
            self.pl_error |= 1 << 5
            return True
        return False

    def set_source(self, value: int) -> bool:
        if self.axi_fail or self.pl_state in (PL_VALIDATE, PL_RUN, PL_PAUSED):
            return False
        self.source = value
        return True

    def tick(self) -> None:
        if self.s1_mode == S1_MODE_LINE and self.feedback_alive:
            self.fb_seq = (self.fb_seq + 1) & 0xFFFF
        if self.pl_state == PL_RUN and self._move is not None:
            self._remaining -= 1
            self._elapsed += 1
            if self._remaining <= 0:
                self.pl_state = PL_DONE
                self._since_done = 0
                self._pending_left = self.done_pending_ticks
                if self._pending_left == 0:
                    self.last = self._move[1]
                else:
                    self.pending = True          # last sample offered, not yet accepted by the backend
        elif self.pl_state == PL_DONE and self.pending:
            if self._pending_left is not None:
                self._pending_left -= 1
                if self._pending_left <= 0:
                    self.pending, self.last = False, self._move[1]
        elif self.pl_state == PL_DONE:
            self._since_done += 1
            if (self.s1_mode == S1_MODE_LINE and self.feedback_alive and self.arrival_delay is not None
                    and self._since_done >= self.arrival_delay):
                self.arrival = 0x3F
        if self.s1_fault or not self.estop_ok:
            self.permission = False


@dataclass
class _Move:
    seg: Segment
    start: tuple
    kind: str                   # "forward" | "retrace" | "partial"
    push: bool = False
    cycles: int = 0             # cycles in RUN/VALIDATE since START (move timeout, in sample periods)
    done_ticks: int = 0
    stopped: bool = False


class S4TaskModel:
    """Tick-level S4 FSM.  command(), vision(), push_fifo() are inputs; tick()
    advances one tick; state/phase/fault/refuse/events/actions are outputs."""

    def __init__(self, cfg: S4Config, tables: S4Tables, plant: Plant):
        self.cfg, self.tables, self.plant = cfg, tables, plant
        self.state = State.OFF
        self.phase = Phase.NONE
        self.owner_s4 = False
        self.fault = Fault.NONE
        self.fault_detail = 0
        self.fault_latched = False
        self.refuse = Refuse.NONE
        self.events: list = []
        self.actions: list = []
        self.cmd_results: list = []
        self.armed = False
        self.holding = self.released = self.ready_latched = False
        self.cancel_req = self.blind_req = False
        self.object = 0
        self.task_id = 0
        self.last_task_id: Optional[int] = None
        self.stack: list = []
        self.sp_deliver = 0
        self.queue: list = []
        self.move: Optional[_Move] = None
        self.plan: dict = {}
        self.palm_hold = self.palm_wait = self.path_wait = self.hb_age = self.fb_age = 0
        self.blind_cycles = 0
        self.fb_seq_seen = 0
        self.fifo: list = []
        self.path_info = (0, 0)
        self.task_request = (0, 0)
        self.vis = (False, NO_DETECTION, False)
        self._vis_changed = False
        self._pending_cmds: list = []
        self.counters = {"tasks_done": 0, "cancels": 0, "faults": 0, "refusals": 0, "blind_timeouts": 0,
                         "tray_returns": 0}
        self.tray_ok_task = False       # tray-exit patch: this task has a validated tray exit
        self.tray_active = False        # tray-exit patch: TRAY phase running
        self.tick_count = 0

    # ------------------------------------------------------------------ inputs
    def command(self, cmd: Cmd) -> None:
        self._pending_cmds.append(cmd)

    def vision(self, valid: bool, stable: int, changed: bool = False, palm_window_ok: bool = False) -> None:
        self.vis = (valid, stable, palm_window_ok)
        self._vis_changed = self._vis_changed or changed

    def push_fifo(self, seg: Segment) -> bool:
        if self.state not in (State.OFF, State.IDLE, State.WAIT_PATH) or len(self.fifo) >= FIFO_SEGMENTS:
            return False
        self.fifo.append(seg)
        return True

    # ------------------------------------------------------------------ helpers
    @property
    def motion_enable(self) -> bool:
        return not self.fault_latched

    @property
    def active(self) -> bool:
        return self.state in (State.RUN, State.WAIT_PALM, State.PAUSED, State.STOPPING, State.RETRACE, State.HALT)

    @property
    def feedback_checks(self) -> bool:
        return self.plant.s1_mode == S1_MODE_LINE

    @property
    def blind(self) -> int:
        """Whole sample periods since the READY latch."""
        return self.blind_cycles // self.cfg.period_cycles

    def _event(self, ev: Event) -> None:
        self.events.append(ev)

    def _act(self, *action) -> None:
        self.actions.append(action)

    def _in_range(self, pose) -> bool:
        return all(lo <= v <= hi for v, lo, hi in zip(pose, self.cfg.joint_min, self.cfg.joint_max))

    def _raise_fault(self, code: Fault, detail: int = 0) -> None:
        if self.fault_latched:
            return
        self.fault_latched, self.fault, self.fault_detail = True, code, detail
        self.counters["faults"] += 1
        if code != Fault.AXI_ERROR and self.plant.command("ESTOP"):
            self._act("ESTOP")
        self.state, self.phase, self.move, self.queue = State.FAULT, Phase.NONE, None, []
        self._event(Event.FAULT)

    def _to_idle(self) -> None:
        self.state, self.phase, self.move, self.queue = State.IDLE, Phase.NONE, None, []
        self.armed = False
        self.holding = self.released = self.ready_latched = False
        self.cancel_req = self.blind_req = False
        self.stack = []
        self.tray_ok_task = self.tray_active = False

    def _tray_applies(self) -> bool:
        return self.tray_ok_task and self.holding and not self.released

    def _tray_path_ok(self) -> bool:
        t = self.tables
        tray = t.path(t.tray)
        return bool(tray) and all(self._in_range(t.segment(i).target) for i in tray) \
            and t.seg_kp(tray[-1]) == self.cfg.home_kp

    def _refuse(self, code: Refuse) -> None:
        self.refuse = code
        self.counters["refusals"] += 1
        self._event(Event.TASK_REFUSED)
        self._to_idle()

    def _cancelled(self) -> None:
        self.counters["cancels"] += 1
        self._event(Event.TASK_CANCELLED)
        self._to_idle()

    # ------------------------------------------------------------------ tables
    def _plan_mode_a(self) -> Optional[dict]:
        t, k, c = self.tables, self.object, self.cfg
        approach, grasp, lift = t.path(t.approach[k]), t.path(t.grasp[k]), t.path(t.lift[k])
        out = approach + grasp + lift
        common = self._plan_common()
        if common is None or not approach or not lift:
            return None
        if sum(1 for i in out if t.segments[i][4] & F_GRASP) != 1 or t.seg_kp(out[-1]) != c.predelivery_kp:
            return None
        if len(out) + len(common["deliver"]) > STACK_DEPTH:
            return None
        return dict(common, out=[t.segment(i) for i in out])

    def _plan_common(self) -> Optional[dict]:
        t = self.tables
        deliver, release, retreat = t.path(t.deliver), t.path(t.release), t.path(t.retreat)
        if not deliver or not release or not retreat or t.seg_kp(retreat[-1]) != self.cfg.home_kp:
            return None
        return {"deliver": [t.segment(i) for i in deliver], "release": [t.segment(i) for i in release],
                "retreat": [t.segment(i) for i in retreat]}

    # ------------------------------------------------------------------ PS commands
    def _handle_command(self, cmd: Cmd) -> None:
        ok, s = CmdReject.ACCEPTED, self.state
        if cmd == Cmd.ENABLE:
            if s != State.OFF:
                ok = CmdReject.STATE
            elif self.fault_latched:
                ok = CmdReject.FAULT_LATCHED
            elif not self.plant.estop_ok:
                ok = CmdReject.ESTOP
            elif not self.plant.set_source(1):
                ok = CmdReject.SOURCE_REFUSED
            else:
                self._act("SOURCE", 1)
                self.owner_s4 = True
                self._to_idle()
        elif cmd == Cmd.RELEASE:
            if s not in (State.IDLE, State.FAULT, State.HALT):
                ok = CmdReject.STATE
            else:
                if self.plant.set_source(0):
                    self._act("SOURCE", 0)
                self.owner_s4 = False
                self.state, self.phase, self.move = State.OFF, Phase.NONE, None
        elif cmd == Cmd.START_TASK:
            obj, tid = self.task_request
            if s != State.IDLE or obj not in (1, 2, 3):
                ok = CmdReject.STATE
            else:
                self._start_task(obj, tid)
        elif cmd == Cmd.CANCEL:
            if not (self.active or s in (State.WAIT_PATH, State.PRECHECK)) or s == State.HALT:
                ok = CmdReject.STATE
            else:
                self._request_cancel()
        elif cmd == Cmd.PAUSE:
            if s != State.RUN or self.move is None or not self.plant.command("PAUSE"):
                ok = CmdReject.STATE
            else:
                self._act("PAUSE")
                self.state = State.PAUSED
        elif cmd == Cmd.RESUME:
            if s != State.PAUSED or not self.plant.command("RESUME"):
                ok = CmdReject.STATE
            else:
                self._act("RESUME")
                self.state = State.RUN
        elif cmd == Cmd.ABORT:
            if not self.owner_s4 or s == State.FAULT:
                ok = CmdReject.STATE
            else:
                self._raise_fault(Fault.ABORT)
        elif cmd == Cmd.FAULT_CLEAR:
            if s != State.OFF or not self.fault_latched:
                ok = CmdReject.STATE
            elif not self.plant.estop_ok:
                ok = CmdReject.ESTOP
            else:
                self.fault_latched, self.fault, self.fault_detail = False, Fault.NONE, 0
        elif cmd == Cmd.PATH_COMMIT:
            if s != State.WAIT_PATH or self.path_info != (self.object, self.task_id):
                ok = CmdReject.STATE
            else:
                self._path_check()
        elif cmd == Cmd.PATH_RESET:
            if s not in (State.OFF, State.IDLE, State.WAIT_PATH):
                ok = CmdReject.STATE
            else:
                self.fifo = []
        elif cmd == Cmd.HEARTBEAT:
            self.hb_age = 0
        self.cmd_results.append((cmd, ok))
        if ok != CmdReject.ACCEPTED:
            self._event(Event.CMD_REJECTED)

    # ------------------------------------------------------------------ task start
    def _start_task(self, obj: int, tid: int) -> None:
        if tid != 0 and tid == self.last_task_id:
            return self._refuse(Refuse.DUPLICATE_TASK)
        self.object, self.task_id = obj, tid
        if self.cfg.mode_b:
            self.state, self.path_wait, self.hb_age = State.WAIT_PATH, 0, 0
            self._event(Event.SELECTED)
            return None
        return self._precheck()

    def _path_check(self) -> None:
        fifo, pre = self.fifo, tuple(self.tables.keypoints[self.cfg.predelivery_kp])
        common = self._plan_common()
        good = (common is not None and 1 <= len(fifo) <= FIFO_SEGMENTS
                and sum(1 for s in fifo if s.flags & F_GRASP) == 1 and fifo[-1].target == pre
                and all(self._in_range(s.target) for s in fifo + common["deliver"] + common["release"] + common["retreat"])
                and len(fifo) + len(common["deliver"]) <= STACK_DEPTH)
        if not good:
            self._event(Event.PATH_REJECTED)
            return self._refuse(Refuse.PATH_INVALID)
        self._event(Event.PATH_ACCEPTED)
        self.tray_ok_task = self.cfg.tray_exit and self._tray_path_ok()
        return self._precheck()

    def _precheck(self) -> None:
        self.state = State.PRECHECK
        if not self.plant.estop_ok:
            return self._refuse(Refuse.ESTOP)
        p = self.plant.poll()
        if not p.ok:
            return self._refuse(Refuse.LINK_ERROR)
        if not (p.s1_status >> S1_CONFIG_VALID & 1) or (p.s1_status >> S1_FAULT_BIT & 1):
            return self._refuse(Refuse.S1_NOT_READY)
        if p.s1_mode not in (S1_MODE_DRY_RUN, S1_MODE_LINE) or (self.cfg.require_line and p.s1_mode != S1_MODE_LINE):
            return self._refuse(Refuse.S1_MODE)
        if p.s1_mode == S1_MODE_LINE and not ((p.s1_status >> S1_PERMISSION & 1)
                                              and (p.s1_status >> S1_FEEDBACK_VALID & 1)):
            return self._refuse(Refuse.S1_NOT_READY)
        if p.pl_state not in (PL_IDLE, PL_DONE) or (p.pl_error & PL_FATAL_MASK) or p.pl_pending or p.pl_source != 1:
            return self._refuse(Refuse.PLANNER_NOT_READY)
        if not p.pl_last_valid or p.last != tuple(self.tables.keypoints[self.cfg.home_kp]):
            return self._refuse(Refuse.NOT_AT_HOME)
        plan = (dict(self._plan_common(), out=list(self.fifo)) if self.cfg.mode_b and self._plan_common()
                else (None if self.cfg.mode_b else self._plan_mode_a()))
        if plan is not None:
            t = self.tables
            plan["tray"] = [t.segment(i) for i in t.path(t.tray)] if self.tray_ok_task else []
        if plan is None:
            return self._refuse(Refuse.TABLE_INVALID)
        if not all(self._in_range(s.target) for key in ("out", "deliver", "release", "retreat") for s in plan[key]):
            return self._refuse(Refuse.RANGE)
        self.plan = plan
        self.last_task_id = self.task_id
        self.fb_seq_seen, self.fb_age, self.hb_age = p.fb_seq, 0, 0
        return self._begin_phase(Phase.OUT)

    # ------------------------------------------------------------------ execution
    def _begin_phase(self, phase: Phase) -> None:
        self.phase, self.state = phase, State.RUN
        self.queue = list(self.plan[{Phase.OUT: "out", Phase.DELIVER: "deliver", Phase.RELEASE: "release",
                                     Phase.RETREAT: "retreat", Phase.TRAY: "tray"}[phase]])
        if phase == Phase.DELIVER:
            self.sp_deliver = len(self.stack)
        self._next_action()

    def _issue(self, seg: Segment, kind: str, push: bool = False) -> None:
        if kind == "forward" and self.phase == Phase.RELEASE:
            self.released = True
        self.move = _Move(seg, self.plant.last, kind, push)
        if not self.plant.move(seg.target, seg.n, seg.na, seg.profile, self.cfg):
            return self._raise_fault(Fault.AXI_ERROR)
        self._act("MOVE", seg.target, seg.n, seg.na, seg.profile, kind)
        return None

    def _begin_tray(self) -> None:
        self.cancel_req = self.blind_req = False
        self.tray_active, self.move = True, None
        self._begin_phase(Phase.TRAY)

    def _next_action(self) -> None:
        """The single decision point after a completed or stopped move (and at phase starts)."""
        tray = self.cancel_req and self._tray_applies()
        m = self.move
        if tray and self.phase == Phase.OUT and not (m is not None and m.stopped):
            pass                                   # tray exit: finish the committed OUT path first (below)
        elif (self.cancel_req or self.blind_req) and not self.released:
            if tray:
                self.state = State.RETRACE
                if m is not None and m.stopped:          # DELIVER only (an OUT move is never stopped while holding)
                    return self._issue(Segment(m.start, m.seg.n, m.seg.na, m.seg.profile, 0), "partial")
                if len(self.stack) > self.sp_deliver:
                    start, n, na, profile, flags = self.stack.pop()
                    return self._issue(Segment(start, n, na, profile, flags), "retrace")
                return self._begin_tray()
            if self.cancel_req and self.holding and self.cfg.hold_policy:
                self.state, self.move = State.HALT, None
                self._event(Event.HALTED)
                return None
            floor = 0 if self.cancel_req else self.sp_deliver
            m = self.move
            self.state = State.RETRACE
            if m is not None and m.stopped:
                return self._issue(Segment(m.start, m.seg.n, m.seg.na, m.seg.profile, 0), "partial")
            if len(self.stack) > floor:
                start, n, na, profile, flags = self.stack.pop()
                return self._issue(Segment(start, n, na, profile, flags), "retrace")
            self.move = None
            if self.cancel_req:
                return self._cancelled()
            self.blind_req = self.ready_latched = False
            self.state, self.phase, self.palm_hold = State.WAIT_PALM, Phase.NONE, 0
            return None
        self.state = State.RUN
        if self.queue:
            seg = self.queue.pop(0)
            return self._issue(seg, "forward", push=self.phase in (Phase.OUT, Phase.DELIVER))
        self.move = None
        if self.phase == Phase.OUT:
            self.sp_deliver = len(self.stack)                # = the DELIVER floor (tray-exit patch)
            if tray:
                return self._begin_tray()
            self.state, self.phase = State.WAIT_PALM, Phase.NONE
            self.palm_hold = self.palm_wait = 0
        elif self.phase == Phase.DELIVER:
            if self.blind + sum(s.n for s in self.plan["release"]) > self.cfg.blind_periods:  # periods
                self._blind_timeout()
                return self._next_action()
            self._begin_phase(Phase.RELEASE)
        elif self.phase == Phase.RELEASE:
            self._begin_phase(Phase.RETREAT)
        elif self.phase == Phase.RETREAT:
            self.counters["tasks_done"] += 1
            self._event(Event.TASK_DONE)
            self._to_idle()
        elif self.phase == Phase.TRAY:
            self.counters["tray_returns"] += 1
            self._cancelled()
        return None

    def _move_complete(self) -> None:
        m = self.move
        if m.kind == "forward" and m.push:
            self.stack.append((m.start, m.seg.n, m.seg.na, m.seg.profile, m.seg.flags))
            if m.seg.flags & F_GRASP:
                self.holding = True
        if m.kind == "retrace" and m.seg.flags & F_GRASP:
            self.holding = False               # gripper re-opened at the grasp pose: object back in the slot
        self.move = None
        self._next_action()

    def _stop_now(self) -> None:
        if self.plant.command("PAUSE"):
            self._act("PAUSE")
        self.state = State.STOPPING

    def _blind_timeout(self) -> None:
        self._event(Event.BLIND_TIMEOUT)
        self.counters["blind_timeouts"] += 1
        self.blind_req = True

    def _request_cancel(self) -> None:
        s = self.state
        if s in (State.WAIT_PATH, State.PRECHECK):
            return self._cancelled()
        if self.released or s == State.HALT or self.cancel_req or self.tray_active:
            self._event(Event.CANCEL_IGNORED)
            return None
        self.cancel_req = True
        if s == State.WAIT_PALM:
            return self._next_action()
        m = self.move
        keep_out = self._tray_applies() and self.phase == Phase.OUT     # tray exit: finish the committed OUT path
        if s == State.PAUSED:
            if not keep_out:
                self.state = State.STOPPING                    # already paused: clear it
        elif s == State.RUN and m is not None and not keep_out and (m.seg.flags & F_STOP_ON_CANCEL
                                                                     or (self.holding and self.cfg.hold_policy)):
            self._stop_now()
        return None                                            # else: finish the move, then _next_action

    # ------------------------------------------------------------------ tick
    def tick(self) -> None:
        self.tick_count += 1
        self.plant.tick()
        for cmd in self._pending_cmds:
            self._handle_command(cmd)
        self._pending_cmds = []
        vis_valid, stable, window_ok = self.vis
        changed, self._vis_changed = self._vis_changed, False
        if self.state in (State.OFF, State.FAULT):
            return None
        if not self.plant.estop_ok and self.active:
            return self._raise_fault(Fault.ESTOP_INPUT)
        if self.state == State.IDLE:
            if vis_valid and (self.cfg.rearm_mask >> stable) & 1:
                self.armed = True
            if vis_valid and changed and self.armed and (self.cfg.select_mask >> stable) & 1:
                self.armed = False
                return self._start_task(stable, 0)
            return None
        if self.state == State.WAIT_PATH:
            self.path_wait += 1
            self.hb_age += 1
            if vis_valid and changed and stable == FIST_CANCEL:
                return self._request_cancel()
            if self.path_wait > self.cfg.t_path_wait:
                self._event(Event.PATH_TIMEOUT)
                return self._cancelled()
            if self.cfg.t_heartbeat and self.hb_age > self.cfg.t_heartbeat:
                self._event(Event.HEARTBEAT_TIMEOUT)
                return self._cancelled()
            return None
        if not self.active:
            return None
        # ---- monitoring of an active task (every tick: one poll)
        p = self.plant.poll()
        if not p.ok:
            return self._raise_fault(Fault.AXI_ERROR)
        if p.s1_status >> S1_FAULT_BIT & 1:
            return self._raise_fault(Fault.S1_FAULT)
        if self.feedback_checks and not (p.s1_status >> S1_PERMISSION & 1):
            return self._raise_fault(Fault.S1_PERMISSION_LOST)
        if p.pl_state in (PL_ERROR, PL_ESTOP):
            return self._raise_fault(Fault.PLANNER_ERROR, p.pl_error & 0xFF)
        if self.feedback_checks:
            if p.fb_seq != self.fb_seq_seen:
                self.fb_seq_seen, self.fb_age = p.fb_seq, 0
            else:
                self.fb_age += 1
                if self.fb_age > self.cfg.t_comm:
                    return self._raise_fault(Fault.COMM_TIMEOUT)
        if self.cfg.mode_b and self.cfg.t_heartbeat and not self.released:
            self.hb_age += 1
            if self.hb_age > self.cfg.t_heartbeat and not self.cancel_req and not self.tray_active:
                self._event(Event.HEARTBEAT_TIMEOUT)
                return self._request_cancel()          # a cancel ends this tick (the poll is stale now)
        if vis_valid and changed and stable == FIST_CANCEL and self.state != State.HALT:
            return self._request_cancel()
        if self.state == State.HALT:
            return None
        if self.ready_latched and self.phase == Phase.DELIVER and not self.blind_req:
            self.blind_cycles += self.cfg.tick_prescale
            if self.blind > self.cfg.blind_periods and not self.cancel_req:
                self._blind_timeout()
                if self.state == State.RUN and self.move is not None:
                    self._stop_now()
                elif self.state == State.PAUSED:
                    self.state = State.STOPPING                # paused by the PS: clear it, no resume
        if self.state == State.WAIT_PALM:
            return self._wait_palm(vis_valid, stable, window_ok)
        if self.state == State.STOPPING:
            if p.pl_state == PL_PAUSED and not p.pl_pending:
                if self.plant.command("CLEAR"):
                    self._act("CLEAR")
                self.move.stopped = True
                return self._next_action()
            if p.pl_state == PL_DONE:                          # finished before the pause took effect
                return self._check_done(p)
            return None
        if self.state in (State.RUN, State.RETRACE) and self.move is not None:
            return self._check_done(p)
        return None

    def _check_done(self, p: Poll) -> None:
        m = self.move
        if p.pl_state in (PL_RUN, PL_VALIDATE) or (p.pl_state == PL_DONE and p.pl_pending):
            # DONE with the last sample still pending: LAST_DELIVERED is not the target yet
            m.cycles += self.cfg.tick_prescale
            if m.cycles // self.cfg.period_cycles > m.seg.n + self.cfg.move_margin:
                self._raise_fault(Fault.MOVE_TIMEOUT)
            return None
        if p.pl_state != PL_DONE:
            return None
        if p.last != tuple(m.seg.target):
            return self._raise_fault(Fault.STATE_MISMATCH)
        if self.feedback_checks and (p.fb_arrival & self.cfg.arrival_mask) != self.cfg.arrival_mask:
            m.done_ticks += 1
            if m.done_ticks > self.cfg.t_arrival:
                self._raise_fault(Fault.ARRIVAL_TIMEOUT)
            return None
        return self._move_complete()

    def _wait_palm(self, vis_valid: bool, stable: int, window_ok: bool) -> None:
        self.palm_wait += 1
        self.palm_hold = self.palm_hold + 1 if (vis_valid and stable == PALM_READY and window_ok) else 0
        if self.palm_hold >= self.cfg.t_palm_hold:
            self.ready_latched, self.blind_cycles = True, 0
            return self._begin_phase(Phase.DELIVER)
        if self.palm_wait > self.cfg.t_palm_wait:
            self._event(Event.PALM_TIMEOUT)
            return self._request_cancel()
        return None


def planner_validate_fn(pr_module) -> Callable:
    """Adapter: S2 planner_p2p_reference.validate() as Plant.validate_fn (returns an error bit mask)."""

    def fn(start, target, n, na, profile, cfg: S4Config) -> int:
        move = pr_module.MoveParams(tuple(start), tuple(target), n, na, profile, cfg.period_cycles, cfg.stall_cycles,
                                    tuple(cfg.vmax), tuple(cfg.amax))
        v = pr_module.validate(move, start)
        return 0 if v.ok else (1 << int(v.error))

    return fn


def move_actions(model: S4TaskModel) -> list:
    return [a for a in model.actions if a[0] == "MOVE"]


def with_changes(cfg: S4Config, **kw) -> S4Config:
    return replace(cfg, **kw)
