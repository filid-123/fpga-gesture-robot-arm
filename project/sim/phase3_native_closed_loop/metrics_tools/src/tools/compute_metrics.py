"""Compute every Phase 3 metric of one run bundle (Phase 3 S8 candidate).

  python src/tools/compute_metrics.py --bundle RUN_DIR [--deadlines deadlines.json] --out metrics.json

Reads only RUN_DIR/run_manifest.json and RUN_DIR/raw/*; verifies every SHA-256 first (a changed raw
file stops the computation).  Output: one JSON with, per metric, the value(s), n, the rule used and
the evidence (file, line, task).  A metric without data is NOT_MEASURED with the reason; a
percentile without enough samples is INSUFFICIENT_SAMPLES.  If any input log is a simulation the
whole result is marked data_kind = SIMULATION and must not be reported as a measurement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "metrics"))
import gesture_metrics as gm  # noqa: E402
import hw_reports as hw  # noqa: E402
import task_metrics as tm  # noqa: E402
from log_schema import is_simulation, load_annotations, load_event_log  # noqa: E402
from stats import MIN_N, NOT_MEASURED  # noqa: E402

SCHEMA = "gesture.phase3.metrics.v1"


def compute(bundle: Path, deadlines: dict | None = None) -> dict:
    man = json.loads((bundle / "run_manifest.json").read_text(encoding="utf-8"))
    raw = bundle / "raw"
    for f in man["files"]:
        if hashlib.sha256((raw / f["file"]).read_bytes()).hexdigest() != f["sha256"]:
            raise SystemExit(f"raw file {f['file']} changed since collection")
    runs, ps_logs, pc_logs = [], [], []
    for r in man["runs"]:
        ps = load_event_log(raw / r["ps"])
        pc = load_event_log(raw / r["pc"]) if r.get("pc") else None
        runs.append({"ps": ps, "pc": pc})
        ps_logs.append(ps)
        if pc is not None:
            pc_logs.append(pc)
    by_role = {}
    for f in man["files"]:
        by_role.setdefault(f["role"], []).append(raw / f["file"])
    ann = load_annotations(by_role["annotations"][0]) if "annotations" in by_role else {"records": []}
    sim = any(is_simulation(l) for l in ps_logs + pc_logs)
    rows = tm.task_rows(ps_logs)
    selections = [{"t_ns": r["t_ns"], "task": r["task"], "line": i}
                  for log in ps_logs for i, r in enumerate(log["records"], start=2) if r["ev"] == "task_start"]
    intervals = [a for a in ann["records"] if a.get("kind") == "truth_interval"]
    out = {
        "schema": SCHEMA,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "data_kind": "SIMULATION" if sim else ("MEASUREMENT" if ps_logs else "NO_TASK_LOGS"),
        "bundle": {"created_utc": man["created_utc"], "note": man.get("note", ""),
                   "files": [{k: f[k] for k in ("role", "file", "sha256", "bytes")} for f in man["files"]],
                   "schema_problems": man.get("schema_problems", 0)},
        "rules": {"percentiles": "nearest rank", "min_samples": {f"p{q}": n for q, n in MIN_N.items()},
                  "durations": "same-clock differences only; network RTT = PS round trip - PC processing"},
        "gesture": {
            "classification": gm.classification(gm.load_samples(by_role["gesture_eval"][0]))
            if "gesture_eval" in by_role else {"status": NOT_MEASURED, "reason": "no labelled evaluation file"},
            "false_triggers": gm.false_triggers(intervals, selections),
        },
        "tasks": tm.outcome_metrics(rows, ann["records"]) if rows else {"status": NOT_MEASURED, "reason": "no task_end"},
        "latency": tm.latency_metrics(rows, runs) if ps_logs else {"status": NOT_MEASURED, "reason": "no PS task log"},
        "pl_trace": tm.pl_trace_metrics(by_role["pl_trace"][0] if "pl_trace" in by_role else None),
        "deadlines": (tm.deadline_metrics(rows, pc_logs, deadlines or {}) if ps_logs
                      else {"status": NOT_MEASURED, "reason": "no PS task log"}),
        "continuous_runs": tm.continuous_run_metrics(rows),
        "hardware": {
            "vivado_build_gates": [hw.parse_gate_lines(p) for p in by_role.get("hw_gate", [])] or
                                  {"status": NOT_MEASURED, "reason": "no Vivado build result supplied"},
            "vivado_reports": (hw.parse_vivado_reports(by_role.get("vivado_util", [None])[0],
                                                       by_role.get("vivado_timing", [None])[0])
                               if ("vivado_util" in by_role or "vivado_timing" in by_role)
                               else {"status": NOT_MEASURED, "reason": "no Vivado report_utilization / report_timing file"}),
            "estimates_not_results": [hw.parse_yosys_estimate(p) for p in by_role.get("yosys", [])],
            "rule": "per design only; vision and motion resources are never added into a whole-system figure",
        },
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", type=Path, required=True)
    ap.add_argument("--deadlines", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    deadlines = json.loads(args.deadlines.read_text()) if args.deadlines else None
    res = compute(args.bundle, deadlines)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes((json.dumps(res, indent=2, default=str) + "\n").encode("utf-8"))
    print(f"metrics written ({res['data_kind']}): {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
