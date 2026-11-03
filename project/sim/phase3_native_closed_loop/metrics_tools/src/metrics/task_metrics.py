"""Task, latency, deadline and continuous-run metrics from Phase 3 event logs (Phase 3 S8 candidate).

Inputs are the JSON-lines logs of phase3_event_log (PS: S6 path service + S7 orchestrator; PC: S7
agent) and an optional annotation file (human ground truth of physical results).  Every number is
computed from raw integer timestamps of ONE clock: a duration is always t2 - t1 of two records of
the same clock_id.  The only cross-host quantity, the network round trip, is a difference of two
DURATIONS (PS round trip on the PS clock minus PC processing on the PC clock), so no clock offset
is assumed.  Each metric lists its evidence (file, line, task) so it can be traced back.

Definitions
  select->commit   task_start -> task_commit        (PS clock; mode B: PC perception + planning + network + PS check)
  commit->end      task_commit -> task_end          (PS clock; PL execution incl. waiting for the palm)
  select->end      task_start -> task_end           (PS clock)
  PC processing    target_request -> path_submitted (PC clock, one request)
  PS round trip    target_request -> path_received  (PS clock, same task)
  network RTT est. PS round trip - PC processing
  log-level delivery success: DONE / tasks not ended by an intentional cancel (VISION_FIST or OPERATOR);
                   physical success only from annotations (trial.physical_ok), else NOT_MEASURED
  FIST return: tasks whose cancel source is VISION_FIST; returned = RETURNED_TO_SLOT / TRAY_RETURN /
                   CANCELLED_HOME / CANCELLED_BEFORE_MOTION, HALTED = stopped and held (not returned)
  continuous run: tasks of one PS clock in start order; a streak ends at FAULT or HALTED
PL-internal and arm latencies need PL timestamps / LINE feedback times that S4 v0.1.1 does not log:
NOT_MEASURED unless a PL trace is supplied (pl_trace: CSV cycle,event).
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from stats import NOT_MEASURED, distribution, rate

INTENTIONAL = ("VISION_FIST", "OPERATOR")
RETURNED = ("RETURNED_TO_SLOT", "TRAY_RETURN", "CANCELLED_HOME", "CANCELLED_BEFORE_MOTION")
STOP_STREAK = ("FAULT", "HALTED")


def _intentional(src) -> bool:
    return bool(src) and any(str(src).startswith(p) for p in INTENTIONAL)


def _ev(log, name):
    return [(i, r) for i, r in enumerate(log["records"], start=2) if r["ev"] == name]


def task_rows(ps_logs: list) -> list:
    rows = []
    for log in ps_logs:
        for line, r in _ev(log, "task_end"):
            rows.append({"file": log["file"], "clock_id": log["header"]["clock_id"], "line": line, "task": r["task"],
                         "mode": r.get("mode"), "object": r.get("object"), "outcome": r["outcome"],
                         "cancel_source": r.get("cancel_source"), "fault": r.get("fault"), "held": r.get("held"),
                         "tray": r.get("tray"), "t_start_ns": r.get("t_start_ns"), "t_commit_ns": r.get("t_commit_ns"),
                         "t_end_ns": r.get("t_end_ns")})
    return rows


def _ms(a, b):
    return (b - a) / 1e6


def outcome_metrics(rows: list, annotations: list) -> dict:
    out = {}
    trials = {}
    for a in annotations:
        if a.get("kind") == "trial":                                     # keyed by PS clock_id or PS log file name
            trials[(a.get("run"), a["task"])] = a
    for mode in sorted({r["mode"] for r in rows}):
        mr = [r for r in rows if r["mode"] == mode]
        counts = Counter(r["outcome"] for r in mr)
        eligible = [r for r in mr if not _intentional(r["cancel_source"])]
        done = [r for r in eligible if r["outcome"] == "DONE"]
        fist = [r for r in mr if str(r["cancel_source"] or "").startswith("VISION_FIST")]
        phys = [trials.get((r["clock_id"], r["task"])) or trials.get((r["file"], r["task"])) for r in mr]
        phys = [t for t in phys if t is not None]
        phys_del = [t for t in phys if t.get("intent") == "deliver"]
        phys_can = [t for t in phys if t.get("intent") == "cancel"]
        out[mode] = {
            "tasks": len(mr), "outcomes": dict(counts),
            "delivery_success_log_level": {**rate(len(done), len(eligible)),
                                           "definition": "DONE / tasks not ended by an intentional cancel",
                                           "evidence": [{"file": r["file"], "line": r["line"], "task": r["task"],
                                                         "outcome": r["outcome"]} for r in eligible]},
            "delivery_success_physical": (rate(sum(bool(t.get("physical_ok")) for t in phys_del), len(phys_del))
                                          if phys_del else {"status": NOT_MEASURED, "reason": "no trial annotations"}),
            "fist_return": {
                "fist_cancels": len(fist),
                "returned": rate(sum(r["outcome"] in RETURNED for r in fist), len(fist)),
                "halted_stop_and_hold": sum(r["outcome"] == "HALTED" for r in fist),
                "tray_returns": sum(r["outcome"] == "TRAY_RETURN" for r in fist),
                "by_outcome": dict(Counter(r["outcome"] for r in fist)),
                "physical": (rate(sum(bool(t.get("physical_ok")) for t in phys_can), len(phys_can))
                             if phys_can else {"status": NOT_MEASURED, "reason": "no trial annotations"}),
                "evidence": [{"file": r["file"], "line": r["line"], "task": r["task"], "outcome": r["outcome"]} for r in fist]},
            "cancel_sources": dict(Counter(r["cancel_source"] for r in mr if r["cancel_source"])),
        }
    return out


def latency_metrics(rows: list, runs: list) -> dict:
    """runs: [{"ps": log, "pc": log | None}] - one run = one PS clock and (mode B) the PC log of that session."""

    sel_commit, commit_end, sel_end = defaultdict(list), defaultdict(list), defaultdict(list)
    for r in rows:
        if r["t_start_ns"] is not None and r["t_end_ns"] is not None:
            sel_end[r["mode"]].append(_ms(r["t_start_ns"], r["t_end_ns"]))
        if r["t_commit_ns"] is not None:
            if r["t_start_ns"] is not None:
                sel_commit[r["mode"]].append(_ms(r["t_start_ns"], r["t_commit_ns"]))
            if r["t_end_ns"] is not None:
                commit_end[r["mode"]].append(_ms(r["t_commit_ns"], r["t_end_ns"]))
    out = {"select_to_commit_ms": {m: distribution(v, "ms") for m, v in sel_commit.items()} or {"status": NOT_MEASURED},
           "commit_to_end_ms": {m: distribution(v, "ms") for m, v in commit_end.items()} or {"status": NOT_MEASURED},
           "select_to_end_ms": {m: distribution(v, "ms") for m, v in sel_end.items()} or {"status": NOT_MEASURED}}
    pc_proc, stages, ps_rt, rtt, evidence = [], defaultdict(list), [], [], []
    for run in runs:
        ps, pcl = run["ps"], run.get("pc")
        req = {r["task"]: r["t_ns"] for _l, r in _ev(ps, "target_request")}
        ps_task = {}
        for line, r in _ev(ps, "path_received"):
            if r["task"] in req and r["task"] not in ps_task:
                ps_task[r["task"]] = _ms(req[r["task"]], r["t_ns"])
                ps_rt.append(ps_task[r["task"]])
        if pcl is None:
            continue
        preq = {r["task"]: r["t_ns"] for _l, r in _ev(pcl, "target_request")}
        for line, r in _ev(pcl, "path_submitted"):
            if r["task"] in preq:
                d = _ms(preq[r["task"]], r["t_ns"])
                pc_proc.append(d)
                if r["task"] in ps_task:
                    rtt.append(ps_task[r["task"]] - d)
                    evidence.append({"ps_file": ps["file"], "pc_file": pcl["file"], "task": r["task"],
                                     "ps_round_trip_ms": ps_task[r["task"]], "pc_processing_ms": d})
        for _l, r in _ev(pcl, "pipeline"):
            h = r.get("host_ns") or {}
            for a, b, name in (("start", "frame", "frame_ms"), ("frame", "aligned", "align_ms"),
                               ("aligned", "detected", "detect_ms"), ("detected", "planned", "plan_ms"),
                               ("start", "planned", "pipeline_ms")):
                if a in h and b in h:
                    stages[name].append(_ms(h[a], h[b]))
    out["pc_processing_ms"] = distribution(pc_proc, "ms")
    out["pc_pipeline_stages_host_ms"] = {k: distribution(v, "ms") for k, v in stages.items()} or {"status": NOT_MEASURED}
    out["ps_round_trip_ms"] = distribution(ps_rt, "ms")
    out["network_rtt_estimate_ms"] = ({**distribution(rtt, "ms"), "evidence": evidence} if rtt else
                                      {"status": NOT_MEASURED, "reason": "needs a PS log and the PC log of the same session"})
    out["pl_internal"] = {"status": NOT_MEASURED, "reason": "S4 v0.1.1 has no PL timestamps; supply a PL trace"}
    out["arm_motion"] = {"status": NOT_MEASURED, "reason": "needs LINE feedback arrival times (not logged)"}
    return out


def pl_trace_metrics(path: Path | None) -> dict:
    """Optional CSV 'cycle,event[,task]' from XSim / ILA; latency between named events in clock cycles."""

    if path is None:
        return {"status": NOT_MEASURED, "reason": "no PL trace supplied"}
    rows = list(csv.DictReader(Path(path).read_bytes().decode("utf-8").splitlines()))
    by = defaultdict(dict)
    for i, r in enumerate(rows, start=2):
        by[r.get("task", "0")][r["event"]] = int(r["cycle"])
    pairs = (("selected", "first_move"), ("path_commit", "first_move"), ("fist", "stop"), ("stop", "retrace_start"))
    out = {}
    for a, b in pairs:
        vals = [e[b] - e[a] for e in by.values() if a in e and b in e]
        out[f"{a}_to_{b}_cycles"] = distribution(vals, "cycles")
    return out


def deadline_metrics(rows: list, pc_logs: list, deadlines_ms: dict) -> dict:
    out = {"path_wait_timeouts": sum(1 for r in rows if r["cancel_source"] == "PATH_WAIT_TIMEOUT"),
           "mode_b_tasks": sum(1 for r in rows if r["mode"] == "B_AI_PC")}
    out["pc_deadline_misses"] = sum(1 for log in pc_logs for _l, r in _ev(log, "pipeline") if r.get("outcome") == "DEADLINE")
    configured = {}
    for name, limit in (deadlines_ms or {}).items():
        field = {"select_to_commit_ms": ("t_start_ns", "t_commit_ns"), "commit_to_end_ms": ("t_commit_ns", "t_end_ns"),
                 "select_to_end_ms": ("t_start_ns", "t_end_ns")}.get(name)
        if field is None:
            configured[name] = {"status": "UNKNOWN_METRIC"}
            continue
        vals = [(r, _ms(r[field[0]], r[field[1]])) for r in rows if r[field[0]] is not None and r[field[1]] is not None]
        miss = [(r, v) for r, v in vals if v > limit]
        configured[name] = {"limit_ms": limit, **rate(len(miss), len(vals)),
                            "evidence": [{"file": r["file"], "line": r["line"], "task": r["task"], "value_ms": v}
                                         for r, v in miss]}
    out["configured"] = configured or {"status": "no deadlines configured"}
    return out


def continuous_run_metrics(rows: list) -> dict:
    if not rows:
        return {"status": NOT_MEASURED, "reason": "no task_end record"}
    out = {}
    for clock in sorted({r["file"] for r in rows}):                  # one PS log file = one run on one clock
        rs = sorted((r for r in rows if r["file"] == clock), key=lambda r: r["t_start_ns"] or 0)
        streak = best = 0
        for r in rs:
            streak = 0 if r["outcome"] in STOP_STREAK else streak + 1
            best = max(best, streak)
        span = [r["t_start_ns"] for r in rs if r["t_start_ns"] is not None] + [r["t_end_ns"] for r in rs if r["t_end_ns"]]
        out[clock] = {"tasks": len(rs), "longest_streak_without_fault_or_halt": best,
                      "faults": sum(r["outcome"] == "FAULT" for r in rs), "halts": sum(r["outcome"] == "HALTED" for r in rs),
                      "span_s": (max(span) - min(span)) / 1e9 if span else None}
    return out
