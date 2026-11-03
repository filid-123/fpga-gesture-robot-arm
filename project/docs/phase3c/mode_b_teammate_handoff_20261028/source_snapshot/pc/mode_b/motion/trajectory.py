"""Timed segments using the existing PL bit-exact Q16.16 P2P reference."""
from __future__ import annotations
import hashlib
import math
import struct
import numpy as np
from pc import planner_p2p_reference as pl


def quantize(q):
    return tuple(int(math.copysign(math.floor(abs(float(v))*65536+.5), float(v))) for v in q)


def dequantize(q):
    return np.array(q, dtype=float)/65536


def build_segment(start, target, config, *, speed_scale=1.):
    start, target = quantize(start), quantize(target)
    period = config["period_s"]
    vmax = tuple(max(1, int(v*period*speed_scale*65536)) for v in config["vmax_rad_s"])
    amax = tuple(max(1, int(a*period**2*speed_scale**2*2**32)) for a in config["amax_rad_s2"])
    delta = np.abs(np.array(target, dtype=float)-start)
    n = max(4, int(np.max(delta/np.array(vmax))*1.5)+2,
            int(math.sqrt(float(np.max(delta*65536/np.array(amax))))*2.4)+2)
    for n in range(n, 65536):
        move = pl.MoveParams(start, target, n, max(1, n//4), pl.PROFILE_TRAPEZOID,
            int(round(period*config["clock_hz"])), config["clock_hz"], vmax, amax)
        if pl.validate(move, start).ok:
            rows = pl.samples(move)
            # Include stops on each side in finite-difference validation. Scaling
            # the same scalar path preserves the PL's actual emitted samples.
            positions = np.array([start, start, *rows, target, target], dtype=np.int64)
            velocity = np.diff(positions, axis=0)
            acceleration = np.diff(velocity, axis=0)
            if (np.any(np.max(np.abs(velocity), axis=0) > np.array(vmax)+1) or
                np.any(np.max(np.abs(acceleration), axis=0)*65536 > np.array(amax)+2*65536)):
                continue
            return {"target_q16": list(target), "n": n, "na": n//4, "profile": 1,
                    "period_cycles": move.period_cycles, "vmax_q16": list(vmax),
                    "amax_q32": list(amax)}, rows
    raise ValueError("No PL-compatible segment timing within uint16 sample count")


def sample_digest(rows):
    digest = hashlib.sha256()
    for row in rows:
        digest.update(struct.pack("<6i", *row))
    return digest.hexdigest()


def regenerate(start_q16, segments, config):
    pose = tuple(start_q16)
    for segment in segments:
        if tuple(segment["start_q16"]) != pose:
            raise ValueError("Segment discontinuity")
        p = pl.MoveParams(pose, tuple(segment["target_q16"]), segment["n"], segment["na"],
            segment["profile"], segment["period_cycles"], config["clock_hz"],
            tuple(segment["vmax_q16"]), tuple(segment["amax_q32"]))
        if not pl.validate(p, pose).ok:
            raise ValueError("Invalid PL segment")
        rows = pl.samples(p)
        if sample_digest(rows) != segment["sample_sha256"]:
            raise ValueError("PL sample digest mismatch")
        yield segment, rows
        pose = tuple(segment["target_q16"])
