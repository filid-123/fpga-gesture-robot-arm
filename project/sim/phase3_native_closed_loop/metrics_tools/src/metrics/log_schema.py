"""Minimal Phase 3 log format for the metrics (Phase 3 S8 candidate) and its validation.

Event logs: gesture.phase3.event_log.v1 (common/phase3_event_log.py of S6).  Header line:
  {"schema", "host", "clock", "clock_id", "wall_utc_at_start", "meta": {"simulation": bool, ...}}
Records used by the metrics (other records are kept but not required):
  host ps  task_start{task, mode, object}  task_commit{task}  task_end{task, mode, object, outcome,
           cancel_source, fault, refuse, held, tray, t_start_ns, t_commit_ns, t_end_ns}
           target_request{task, object}  path_received{task, segments, bytes}  path_result{task, result}
  host pc  target_request{task, object}  pipeline{task, attempt, outcome, host_ns{start, frame, aligned,
           detected, planned}}  path_submitted{task}  pc_cancel{task, reason}  status{task, task_state}
every record: {"t_ns": int, "ev": str, "task": int | null}
Annotations (human ground truth): gesture.phase3.annotations.v1, header {"schema", "ps_clock_id"},
  records {"kind": "trial", "run": <ps clock_id>, "task", "intent": "deliver" | "cancel", "physical_ok": bool,
           "note"} and {"kind": "truth_interval", "start_ns", "end_ns", "label"} (PS clock).
Gesture evaluation: CSV/JSONL sample_id,truth,pred[,session] (gesture_metrics.py).
"""

from __future__ import annotations

import json
from pathlib import Path

EVENT_SCHEMA = "gesture.phase3.event_log.v1"
ANN_SCHEMA = "gesture.phase3.annotations.v1"
REQUIRED = {
    ("ps", "task_start"): ("task", "mode", "object"),
    ("ps", "task_commit"): ("task",),
    ("ps", "task_end"): ("task", "mode", "outcome", "t_start_ns", "t_end_ns"),
    ("ps", "target_request"): ("task",),
    ("ps", "path_received"): ("task",),
    ("pc", "target_request"): ("task",),
    ("pc", "path_submitted"): ("task",),
    ("pc", "pipeline"): ("task", "outcome"),
}
HEADER_KEYS = ("schema", "host", "clock", "clock_id")


def load_event_log(path: Path) -> dict:
    """{"file", "header", "records", "problems"}; a problem is (line, text).  Never raises on content."""

    path = Path(path)
    lines = path.read_bytes().decode("utf-8").splitlines()
    problems = []
    if not lines:
        return {"file": path.name, "header": {}, "records": [], "problems": [(0, "empty file")]}
    try:
        header = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        return {"file": path.name, "header": {}, "records": [], "problems": [(1, f"header not JSON: {exc}")]}
    if header.get("schema") != EVENT_SCHEMA:
        problems.append((1, f"schema {header.get('schema')!r}, expected {EVENT_SCHEMA}"))
    for k in HEADER_KEYS:
        if k not in header:
            problems.append((1, f"header lacks {k}"))
    records, last_t = [], None
    for ln, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append((ln, f"not JSON: {exc}"))
            continue
        if not isinstance(r.get("t_ns"), int) or "ev" not in r:
            problems.append((ln, "record without integer t_ns / ev"))
            continue
        if last_t is not None and r["t_ns"] < last_t:
            problems.append((ln, "t_ns goes backwards (one clock per file)"))
        last_t = r["t_ns"]
        for f in REQUIRED.get((header.get("host"), r["ev"]), ()):
            if f not in r:
                problems.append((ln, f"{r['ev']} lacks {f}"))
        records.append(r)
    return {"file": path.name, "header": header, "records": records, "problems": problems}


def load_annotations(path: Path) -> dict:
    path = Path(path)
    lines = path.read_bytes().decode("utf-8").splitlines()
    header = json.loads(lines[0]) if lines else {}
    problems = [] if header.get("schema") == ANN_SCHEMA else [(1, "not an annotation file")]
    recs = []
    for ln, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("kind") == "trial" and not {"task", "intent", "physical_ok"} <= r.keys():
            problems.append((ln, "trial needs task, intent, physical_ok"))
        elif r.get("kind") == "truth_interval" and not {"start_ns", "end_ns", "label"} <= r.keys():
            problems.append((ln, "truth_interval needs start_ns, end_ns, label"))
        elif r.get("kind") not in ("trial", "truth_interval"):
            problems.append((ln, f"unknown kind {r.get('kind')!r}"))
        r["line"] = ln
        recs.append(r)
    return {"file": path.name, "header": header, "records": recs, "problems": problems}


def is_simulation(log: dict) -> bool:
    return bool((log.get("header") or {}).get("meta", {}).get("simulation")) or \
        (log.get("header") or {}).get("clock") == "sim_ns"
