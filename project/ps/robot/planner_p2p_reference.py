"""Joint-space point-to-point planner, contract ``planner_p2p_q16_16_v1`` (Phase 3 S2).

Bit-exact Python reference of ``rtl/robot/planner_p2p_core.v``.  All six axes
share ONE scalar path parameter s(k) in [0, 1]; each axis is
``p_i(k) = start_i + round_away((target_i - start_i) * s(k))``, so both arms
(RoArm-M3, SO-ARM101) use the same planner and differ only in the S1 unit
mapping and communication backend.

Integer definition (no floating point anywhere in the planner):

* Positions: signed Q16.16 rad (int32), channel 0 in the low word of the
  192-bit sample (S1 trajectory contract layout).
* N samples at a fixed period P (cycles), sample k = 1..N; sample N is exactly
  the target, sample 0 (the start) is not emitted.
* Profile LINEAR:     S(k) = k,                      D = N
  Profile TRAPEZOID:  Na accel samples, 1 <= Na <= N/2, D = 2*Na*(N-Na)
      S(k) = k*k                        for k <= Na
             2*Na*k - Na*Na             for Na <= k <= N-Na
             D - (N-k)*(N-k)            for k >= N-Na
  S is advanced incrementally (2k+1, 2Na, 2(N-k)-1): exact, no drift.
* s_frac(k) = floor(S(k) * 2^32 / D)                     (UQ0.32, k < N)
* p_i(k)    = start_i + sign(d_i) * floor((|d_i| * s_frac + 2^31) / 2^32),
  d_i = target_i - start_i (33-bit)  -> round half away from zero.

START validation (first failure wins, in this order):
  1. scalars: N >= 1; LINEAR: Na == 0; TRAPEZOID: 1 <= Na, 2*Na <= N;
     P >= MIN_PERIOD_CYCLES; stall timeout != 0            -> PARAM_INVALID
  2. per channel 0..5:
     continuity: if a last delivered sample exists, start_i must equal it
                                                           -> START_MISMATCH
     velocity:   |d_i|        <= vmax_i * V   (vmax UQ16.16 rad/sample)
                                                           -> VELOCITY_LIMIT
     acceleration: |d_i|*2^16 <= amax_i * A   (amax UQ0.32 rad/sample^2)
                                                           -> ACCEL_LIMIT
     with V = N-Na, A = Na*(N-Na) (TRAPEZOID) or V = A = N (LINEAR).
  Emitted steps can exceed |d_i|/V by at most 1 LSB (2^-16 rad) because of
  rounding.

Soft limits stay where S1 enforces them (PL mapper per sample); the PS helper
``check_soft_limits`` refuses a request before START (advisory, not in PL).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Mapping, Sequence

CONTRACT = "planner_p2p_q16_16_v1"
REQUEST_SCHEMA = "gesture.phase3.s2_move_request.v1"
CHANNEL_COUNT = 6
MAX_SAMPLES = 0xFFFF
MIN_PERIOD_CYCLES = 512          # must equal the RTL parameter MIN_PERIOD_CYCLES
CLOCK_HZ = 100_000_000
PROFILE_LINEAR = 0
PROFILE_TRAPEZOID = 1
PROFILE_NAMES = {"linear": PROFILE_LINEAR, "trapezoid": PROFILE_TRAPEZOID}
INT32_MIN = -(1 << 31)
INT32_MAX = (1 << 31) - 1
UINT32_MAX = (1 << 32) - 1


class PlannerError(IntEnum):
    """ERROR_STATUS bit numbers of planner_axi_top (ABI 0x0000_3201)."""

    PARAM_INVALID = 0
    VELOCITY_LIMIT = 1
    ACCEL_LIMIT = 2
    START_MISMATCH = 3
    STALL_TIMEOUT = 4
    ESTOP = 5
    CONFIG_LOCKED = 6
    COMMAND_CONFLICT = 7
    SOURCE_CONFLICT = 8
    AXI_ACCESS = 9


FATAL_ERRORS = frozenset(PlannerError(i) for i in range(6))


class PlannerState(IntEnum):
    IDLE = 0
    VALIDATE = 1
    RUN = 2
    PAUSED = 3
    DONE = 4
    ERROR = 5
    ESTOP = 6


class MoveRequestError(ValueError):
    """A move request cannot be turned into planner registers (PS side)."""


def _check_range(value: int, low: int, high: int, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise ValueError(f"{name}={value!r} outside register range [{low}, {high}]")
    return value


@dataclass(frozen=True)
class MoveParams:
    """Exactly the planner register image of one move."""

    start: tuple[int, ...]
    target: tuple[int, ...]
    n_samples: int
    accel_samples: int
    profile: int
    period_cycles: int
    stall_timeout_cycles: int
    vmax_q16: tuple[int, ...]
    amax_q32: tuple[int, ...]

    def __post_init__(self) -> None:
        for name in ("start", "target", "vmax_q16", "amax_q32"):
            values = tuple(getattr(self, name))
            if len(values) != CHANNEL_COUNT:
                raise ValueError(f"{name} needs {CHANNEL_COUNT} values")
            low, high = (INT32_MIN, INT32_MAX) if name in ("start", "target") else (0, UINT32_MAX)
            for ch, value in enumerate(values):
                _check_range(value, low, high, f"{name}[{ch}]")
            object.__setattr__(self, name, values)
        _check_range(self.n_samples, 0, MAX_SAMPLES, "n_samples")
        _check_range(self.accel_samples, 0, MAX_SAMPLES, "accel_samples")
        _check_range(self.profile, 0, 1, "profile")
        _check_range(self.period_cycles, 0, UINT32_MAX, "period_cycles")
        _check_range(self.stall_timeout_cycles, 0, UINT32_MAX, "stall_timeout_cycles")


@dataclass(frozen=True)
class Validation:
    error: PlannerError | None
    channel: int = 0
    d: int = 0
    a: int = 0
    v: int = 0

    @property
    def ok(self) -> bool:
        return self.error is None


def scalars_ok(p: MoveParams) -> bool:
    n, na = p.n_samples, p.accel_samples
    if n < 1 or p.period_cycles < MIN_PERIOD_CYCLES or p.stall_timeout_cycles == 0:
        return False
    if p.profile == PROFILE_LINEAR:
        return na == 0
    return na >= 1 and 2 * na <= n


def profile_constants(p: MoveParams) -> tuple[int, int, int]:
    """(D, A, V) of a move whose scalars are valid."""

    n, na = p.n_samples, p.accel_samples
    if p.profile == PROFILE_LINEAR:
        return n, n, n
    v = n - na
    a = na * v
    return 2 * a, a, v


def validate(p: MoveParams, last_delivered: Sequence[int] | None = None) -> Validation:
    if not scalars_ok(p):
        return Validation(PlannerError.PARAM_INVALID)
    d, a, v = profile_constants(p)
    for ch in range(CHANNEL_COUNT):
        if last_delivered is not None and p.start[ch] != last_delivered[ch]:
            return Validation(PlannerError.START_MISMATCH, ch, d, a, v)
        magnitude = abs(p.target[ch] - p.start[ch])
        if magnitude > p.vmax_q16[ch] * v:
            return Validation(PlannerError.VELOCITY_LIMIT, ch, d, a, v)
        if (magnitude << 16) > p.amax_q32[ch] * a:
            return Validation(PlannerError.ACCEL_LIMIT, ch, d, a, v)
    return Validation(None, 0, d, a, v)


def s_increment(k: int, p: MoveParams) -> int:
    """S(k+1) - S(k)."""

    if p.profile == PROFILE_LINEAR:
        return 1
    n, na = p.n_samples, p.accel_samples
    if k + 1 <= na:
        return 2 * k + 1
    if k + 1 <= n - na:
        return 2 * na
    return 2 * (n - k) - 1


def s_values(p: MoveParams) -> list[int]:
    """S(k) for k = 0..N (requires valid scalars)."""

    values = [0]
    for k in range(p.n_samples):
        values.append(values[-1] + s_increment(k, p))
    return values


def s_frac(s: int, d: int) -> int:
    if not 0 <= s < d:
        raise ValueError("s_frac needs 0 <= S < D")
    return (s << 32) // d


def interpolate(start: int, target: int, fraction: int) -> int:
    delta = target - start
    magnitude = (abs(delta) * fraction + (1 << 31)) >> 32
    return start + magnitude if delta >= 0 else start - magnitude


def samples(p: MoveParams) -> list[tuple[int, ...]]:
    """The N samples the PL emits for a validated move (k = 1..N)."""

    if not scalars_ok(p):
        raise ValueError("move scalars are invalid; validate() first")
    d, _a, _v = profile_constants(p)
    s = s_values(p)
    if s[-1] != d:
        raise AssertionError("profile does not end at S(N) = D")   # contract self-check
    out: list[tuple[int, ...]] = []
    for k in range(1, p.n_samples + 1):
        if k == p.n_samples:
            out.append(tuple(p.target))
        else:
            fraction = s_frac(s[k], d)
            out.append(tuple(interpolate(a, b, fraction) for a, b in zip(p.start, p.target)))
    return out


def presentation_offsets(p: MoveParams) -> list[int]:
    """Cycles from entering RUN to each sample's valid (sink always ready)."""

    return [p.period_cycles * k for k in range(1, p.n_samples + 1)]


def max_step(p: MoveParams) -> tuple[int, ...]:
    """Largest per-sample change of each axis (including the first step from start)."""

    previous = tuple(p.start)
    best = [0] * CHANNEL_COUNT
    for sample in samples(p):
        for ch in range(CHANNEL_COUNT):
            best[ch] = max(best[ch], abs(sample[ch] - previous[ch]))
        previous = sample
    return tuple(best)


# --------------------------------------------------------------------------
# PS-side conversion helpers (the PL never sees seconds or radians)
# --------------------------------------------------------------------------
def seconds_to_cycles(seconds: float) -> int:
    if not math.isfinite(seconds) or seconds < 0:
        raise MoveRequestError(f"invalid time {seconds!r}")
    return int(math.floor(seconds * CLOCK_HZ + 0.5))


def limits_from_profile(profile: Any, period_s: float) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """vmax (UQ16.16 rad/sample) and amax (UQ0.32 rad/sample^2), rounded DOWN."""

    vmax, amax, missing = [], [], []
    for joint in profile.joints:
        v, a = joint.max_velocity_rad_s, joint.max_accel_rad_s2
        if v is None or a is None:
            missing.append(f"joints[{joint.logical_channel}].max_velocity_rad_s/max_accel_rad_s2")
            continue
        if v <= 0 or a <= 0:
            raise MoveRequestError(f"joint {joint.logical_channel} limits must be positive")
        vmax.append(min(UINT32_MAX, math.floor(v * period_s * (1 << 16))))
        amax.append(min(UINT32_MAX, math.floor(a * period_s * period_s * (1 << 32))))
    if missing:
        raise MoveRequestError("profile limits are TBD: " + ", ".join(missing))
    return tuple(vmax), tuple(amax)


def check_soft_limits(profile: Any, positions_q16: Sequence[Sequence[int]]) -> list[str]:
    """PS advisory check that start/target stay inside the profile soft limits."""

    problems = []
    for joint in profile.joints:
        low, high = joint.soft_min_rad, joint.soft_max_rad
        ch = joint.logical_channel
        if low is None or high is None:
            problems.append(f"joints[{ch}] soft limits are TBD")
            continue
        low_q, high_q = math.ceil(low * 65536), math.floor(high * 65536)
        for label, values in zip(("start", "target"), positions_q16):
            if not low_q <= values[ch] <= high_q:
                problems.append(f"{label}[{ch}]={values[ch] / 65536:.5f} rad outside [{low}, {high}]")
    return problems


def plan_move(start_q16: Sequence[int], target_q16: Sequence[int], *, duration_s: float, period_s: float,
              profile_kind: str, accel_time_s: float = 0.0, stall_timeout_s: float = 0.5,
              vmax_q16: Sequence[int], amax_q32: Sequence[int]) -> MoveParams:
    if profile_kind not in PROFILE_NAMES:
        raise MoveRequestError(f"profile must be one of {sorted(PROFILE_NAMES)}")
    if period_s <= 0 or duration_s <= 0:
        raise MoveRequestError("duration_s and period_s must be positive")
    n = int(math.floor(duration_s / period_s + 0.5))
    na = int(math.floor(accel_time_s / period_s + 0.5)) if profile_kind == "trapezoid" else 0
    if profile_kind == "trapezoid" and accel_time_s <= 0:
        raise MoveRequestError("trapezoid needs accel_time_s > 0")
    if not 1 <= n <= MAX_SAMPLES:
        raise MoveRequestError(f"duration gives N={n} samples, allowed 1..{MAX_SAMPLES}")
    return MoveParams(tuple(start_q16), tuple(target_q16), n, na, PROFILE_NAMES[profile_kind],
                      seconds_to_cycles(period_s), seconds_to_cycles(stall_timeout_s),
                      tuple(vmax_q16), tuple(amax_q32))


def _positions(raw: Mapping[str, Any], key: str) -> tuple[int, ...] | None:
    from arm_fixed_point import rad_to_q16_16

    if f"{key}_q16" in raw:
        values = tuple(int(v) for v in raw[f"{key}_q16"])
    elif f"{key}_rad" in raw:
        values = tuple(rad_to_q16_16(float(v), name=f"{key}_rad") for v in raw[f"{key}_rad"])
    else:
        return None
    if len(values) != CHANNEL_COUNT:
        raise MoveRequestError(f"{key} needs {CHANNEL_COUNT} values")
    return values


def move_from_request(raw: Mapping[str, Any], profile: Any,
                      current_q16: Sequence[int] | None) -> tuple[MoveParams, list[str]]:
    """``gesture.phase3.s2_move_request.v1`` -> (MoveParams, advisory problems).

    ``start`` defaults to the current commanded position (LAST_DELIVERED);
    an explicit start is only allowed when no position is known yet.
    """

    if raw.get("schema") != REQUEST_SCHEMA:
        raise MoveRequestError(f"schema must be {REQUEST_SCHEMA!r}")
    target = _positions(raw, "target")
    if target is None:
        raise MoveRequestError("target_rad or target_q16 is required")
    start = _positions(raw, "start")
    if start is None:
        if current_q16 is None:
            raise MoveRequestError("no current position known: give start_rad/start_q16 explicitly")
        start = tuple(current_q16)
    elif current_q16 is not None and tuple(start) != tuple(current_q16):
        raise MoveRequestError("start differs from the current commanded position (continuity)")
    period_s = float(raw.get("period_s", 0.02))
    vmax, amax = limits_from_profile(profile, period_s)
    move = plan_move(start, target, duration_s=float(raw["duration_s"]), period_s=period_s,
                     profile_kind=str(raw.get("profile", "trapezoid")),
                     accel_time_s=float(raw.get("accel_time_s", 0.0)),
                     stall_timeout_s=float(raw.get("stall_timeout_s", 0.5)), vmax_q16=vmax, amax_q32=amax)
    return move, check_soft_limits(profile, (move.start, move.target))


def load_request(path: Path | str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@dataclass
class PlannerCoreModel:
    """Event-level model of the core state machine (commands, samples, errors)."""

    state: PlannerState = PlannerState.IDLE
    move: MoveParams | None = None
    pending: tuple[int, ...] | None = None
    delivered: list[tuple[int, ...]] = field(default_factory=list)
    last_delivered: tuple[int, ...] | None = None
    error: PlannerError | None = None
    error_channel: int = 0
    _queue: list[tuple[int, ...]] = field(default_factory=list)

    def start(self, move: MoveParams) -> Validation:
        if self.state not in (PlannerState.IDLE, PlannerState.DONE) or self.pending is not None:
            raise RuntimeError("START is only legal in IDLE/DONE without a pending sample")
        result = validate(move, self.last_delivered)
        self.move = move
        if not result.ok:
            self.state, self.error, self.error_channel = PlannerState.ERROR, result.error, result.channel
            return result
        self.state = PlannerState.RUN
        self._queue = samples(move)
        return result

    def present(self) -> tuple[int, ...] | None:
        """Next sample offered to the sink (RUN only)."""

        if self.state is PlannerState.RUN and self.pending is None and self._queue:
            self.pending = self._queue.pop(0)
        return self.pending

    def accept(self) -> None:
        if self.pending is None:
            raise RuntimeError("nothing pending")
        self.delivered.append(self.pending)
        self.last_delivered = self.pending
        self.pending = None
        if self.state in (PlannerState.RUN, PlannerState.PAUSED) and not self._queue:
            self.state = PlannerState.DONE

    def pause(self) -> None:
        if self.state is PlannerState.RUN:
            self.state = PlannerState.PAUSED

    def resume(self) -> None:
        if self.state is PlannerState.PAUSED:
            self.state = PlannerState.RUN

    def estop(self) -> None:
        self.state, self.error = PlannerState.ESTOP, PlannerError.ESTOP
        self._queue = []

    def stall(self) -> None:
        self.state, self.error = PlannerState.ERROR, PlannerError.STALL_TIMEOUT
        self._queue = []

    def clear(self) -> None:
        if self.state in (PlannerState.RUN, PlannerState.VALIDATE):
            raise RuntimeError("CLEAR is not legal while running")
        self.state, self.error, self.error_channel = PlannerState.IDLE, None, 0
        self._queue = []
