"""Versioned AI-PC -> PYNQ sparse path contract (Phase 3 S6 candidate), shared by the PC planner and
the PS path service.  Both sides run the SAME checks; the PL (S4 v0.1.1 PATH_COMMIT scan + S2 START
validation) remains the final range / structure / velocity gate.

Semantics (identical to S4 mode B and S2 v0.2.3, nothing new is invented):
* six channels in S1 order, index 5 = gripper; units Q16.16 of the S1 joint units (rad); int32;
* a plan is a list of segments, each = target pose + N samples + Na accel samples + profile + flags;
  segment k starts where segment k-1 ends, segment 0 starts at HOME (S4 requires LAST_DELIVERED == HOME);
  the last target must equal PRE_DELIVERY; exactly one segment carries F_GRASP (gripper closes);
  F_STOP_ON_CANCEL segments stop at once on a cancel; at most 32 segments (S4 FIFO);
* sample-by-sample check: every segment is interpolated with the S2 v0.2.3 reference
  (planner_p2p_reference), every sample must lie inside the joint limits and pass the planner's
  VMAX/AMAX validation; the SHA-256 of all samples is carried in the plan (sample_digest) and the PS
  recomputes it, so a PC/PS interpolation mismatch is rejected before anything reaches the PL;
* execution gate: a plan may drive a REAL arm only if the calibration is CALIBRATED, the motion
  limits are MEASURED, the IK is REAL and the period is measured; otherwise it is at most a
  bench (DRY_RUN) plan.  Synthetic paths are never called executable.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field, replace
from enum import IntEnum
from typing import Callable, Optional, Sequence

CONTRACT_VERSION = 1
INTERP_VERSION = 0x0002_0003                  # S2 v0.2.3 planner_p2p_reference
CHANNELS = 6
GRIPPER_CHANNEL = 5
JOINT_ORDER = ("J1", "J2", "J3", "J4", "J5", "GRIPPER")
UNITS = "Q16.16 of the S1 joint units (rad), int32"
MAX_SEGMENTS = 32
F_GRASP, F_STOP_ON_CANCEL = 1, 2
INT32_MIN, INT32_MAX = -(1 << 31), (1 << 31) - 1


class IKKind(IntEnum):
    SYNTHETIC = 0          # test double, never executable on an arm
    REAL = 1               # a measured, validated IK (TBD: not available)


class Problem(IntEnum):
    OK = 0
    VERSION = 1
    SEGMENT_COUNT = 2
    GRASP_COUNT = 3
    START_NOT_HOME = 4
    END_NOT_PRE_DELIVERY = 5
    TARGET_RANGE = 6
    SAMPLE_RANGE = 7
    PLANNER_REJECT = 8
    DIGEST_MISMATCH = 9
    BAD_FIELD = 10


@dataclass(frozen=True)
class Segment:
    target: tuple
    n: int
    na: int
    profile: int
    flags: int = 0


@dataclass(frozen=True)
class MotionLimits:
    joint_min: tuple
    joint_max: tuple
    vmax_q16: tuple
    amax_q32: tuple
    period_cycles: int
    stall_cycles: int
    status: str = "TBD"               # MEASURED | BENCH | TBD


@dataclass(frozen=True)
class PathPlan:
    task_id: int
    object_id: int
    start_pose: tuple
    segments: tuple
    calib_id: int
    ik_kind: IKKind
    sample_digest: bytes = b""
    interp_version: int = INTERP_VERSION
    contract_version: int = CONTRACT_VERSION


@dataclass
class CheckResult:
    problems: list = field(default_factory=list)      # (Problem, segment index, detail)
    samples: int = 0
    digest: bytes = b""

    @property
    def ok(self) -> bool:
        return not self.problems

    def first(self) -> Problem:
        return self.problems[0][0] if self.problems else Problem.OK


def _in_range(pose: Sequence[int], lim: MotionLimits) -> bool:
    return all(lo <= v <= hi for v, lo, hi in zip(pose, lim.joint_min, lim.joint_max))


def interpolate(plan_segments: Sequence[Segment], start: tuple, lim: MotionLimits, pr) -> tuple:
    """(list of per-segment sample lists, list of (segment, error)) with the S2 reference module ``pr``."""

    out, errors, pose = [], [], tuple(start)
    for k, s in enumerate(plan_segments):
        move = pr.MoveParams(pose, tuple(s.target), s.n, s.na, s.profile, lim.period_cycles, lim.stall_cycles,
                             tuple(lim.vmax_q16), tuple(lim.amax_q32))
        v = pr.validate(move, pose)
        if not v.ok:
            errors.append((k, v.error.name if v.error is not None else "PARAM"))
            out.append([])
        else:
            out.append(pr.samples(move))
        pose = tuple(s.target)
    return out, errors


def digest_of(samples: Sequence[Sequence[tuple]]) -> bytes:
    h = hashlib.sha256()
    for seg in samples:
        for smp in seg:
            h.update(struct.pack("<6i", *smp))
    return h.digest()


def check(plan: PathPlan, lim: MotionLimits, home: tuple, pre_delivery: tuple, pr) -> CheckResult:
    """All contract rules; returns every problem found (the PS rejects on any)."""

    r = CheckResult()
    if plan.contract_version != CONTRACT_VERSION or plan.interp_version != INTERP_VERSION:
        r.problems.append((Problem.VERSION, -1, f"contract {plan.contract_version} interp 0x{plan.interp_version:08X}"))
        return r
    segs = plan.segments
    if not 1 <= len(segs) <= MAX_SEGMENTS:
        r.problems.append((Problem.SEGMENT_COUNT, -1, str(len(segs))))
        return r
    for k, s in enumerate(segs):
        if len(s.target) != CHANNELS or not all(INT32_MIN <= v <= INT32_MAX for v in s.target) \
                or not (1 <= s.n <= 0xFFFF and 0 <= s.na <= 0xFFFF and s.profile in (0, 1) and 0 <= s.flags <= 0xFF):
            r.problems.append((Problem.BAD_FIELD, k, "segment field"))
    if r.problems:
        return r
    if sum(1 for s in segs if s.flags & F_GRASP) != 1:
        r.problems.append((Problem.GRASP_COUNT, -1, ""))
    if tuple(plan.start_pose) != tuple(home):
        r.problems.append((Problem.START_NOT_HOME, -1, ""))
    if tuple(segs[-1].target) != tuple(pre_delivery):
        r.problems.append((Problem.END_NOT_PRE_DELIVERY, len(segs) - 1, ""))
    for k, s in enumerate(segs):
        if not _in_range(s.target, lim):
            r.problems.append((Problem.TARGET_RANGE, k, ""))
    samples, errors = interpolate(segs, tuple(plan.start_pose), lim, pr)
    for k, e in errors:
        r.problems.append((Problem.PLANNER_REJECT, k, e))
    for k, seg in enumerate(samples):
        if any(not _in_range(smp, lim) for smp in seg):
            r.problems.append((Problem.SAMPLE_RANGE, k, ""))
    r.samples = sum(len(s) for s in samples)
    r.digest = digest_of(samples)
    if plan.sample_digest and plan.sample_digest != r.digest:
        r.problems.append((Problem.DIGEST_MISMATCH, -1, ""))
    elif not plan.sample_digest:
        r.problems.append((Problem.DIGEST_MISMATCH, -1, "missing digest"))
    return r


def executable_on_real_arm(plan: PathPlan, lim: MotionLimits, calibration_status: str) -> tuple:
    """(ok, reasons): every precondition of a real execution; any TBD item refuses."""

    reasons = []
    if calibration_status != "CALIBRATED":
        reasons.append(f"calibration {calibration_status}")
    if lim.status != "MEASURED":
        reasons.append(f"motion limits {lim.status}")
    if plan.ik_kind != IKKind.REAL:
        reasons.append(f"IK {plan.ik_kind.name}")
    if lim.period_cycles <= 0:
        reasons.append("period unknown")
    return (not reasons, reasons)


def finalize(plan: PathPlan, lim: MotionLimits, home: tuple, pre_delivery: tuple, pr) -> tuple:
    """PC side: compute the digest and return (plan with digest, CheckResult)."""

    r = check(replace(plan, sample_digest=b"\x00" * 32), lim, home, pre_delivery, pr)
    r.problems = [p for p in r.problems if p[0] != Problem.DIGEST_MISMATCH]
    return replace(plan, sample_digest=r.digest), r
