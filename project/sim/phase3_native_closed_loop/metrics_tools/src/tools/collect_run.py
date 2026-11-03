"""Collect the raw inputs of one evaluation into a run bundle (Phase 3 S8 candidate).

  python src/tools/collect_run.py --out RUN_DIR --run PS_LOG[,PC_LOG] [--run ...] [--annotations FILE]
      [--gesture-eval FILE] [--hw-gate FILE] [--vivado-util FILE --vivado-timing FILE] [--yosys FILE]
      [--pl-trace FILE] [--note TEXT]

Files are COPIED unchanged into RUN_DIR/raw/ and listed in RUN_DIR/run_manifest.json with SHA-256,
size, role, header (clock_id, host, simulation flag), record count and every schema problem found.
Nothing is converted or filtered: the metrics are recomputed from these raw files only.  A run is
one PS log and, optionally, the PC log of the same session.  Refuses to overwrite an existing bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "metrics"))
from log_schema import is_simulation, load_annotations, load_event_log  # noqa: E402

SCHEMA = "gesture.phase3.run_bundle.v1"


def _copy(src: Path, raw: Path, role: str) -> dict:
    dst = raw / f"{role}__{src.name}"
    if dst.exists():
        raise SystemExit(f"duplicate input name {dst.name}")
    shutil.copyfile(src, dst)
    data = dst.read_bytes()
    return {"role": role, "file": dst.name, "source_name": src.name, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--run", action="append", default=[], help="PS_LOG[,PC_LOG]")
    ap.add_argument("--annotations", type=Path)
    ap.add_argument("--gesture-eval", type=Path)
    ap.add_argument("--hw-gate", type=Path, action="append", default=[])
    ap.add_argument("--vivado-util", type=Path)
    ap.add_argument("--vivado-timing", type=Path)
    ap.add_argument("--yosys", type=Path, action="append", default=[])
    ap.add_argument("--pl-trace", type=Path)
    ap.add_argument("--note", default="")
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit(f"{args.out} exists; refusing to overwrite a bundle")
    raw = args.out / "raw"
    raw.mkdir(parents=True)
    files, runs, sim = [], [], False
    for k, spec in enumerate(args.run):
        parts = [Path(p) for p in spec.split(",")]
        entry = {"run": k}
        for role, p in zip(("ps", "pc"), parts):
            f = _copy(p, raw, f"run{k}_{role}")
            log = load_event_log(raw / f["file"])
            f.update(host=log["header"].get("host"), clock=log["header"].get("clock"),
                     clock_id=log["header"].get("clock_id"), simulation=is_simulation(log), records=len(log["records"]),
                     problems=[list(x) for x in log["problems"]])
            sim |= f["simulation"]
            files.append(f)
            entry[role] = f["file"]
        runs.append(entry)
    for role, p in (("annotations", args.annotations), ("gesture_eval", args.gesture_eval), ("pl_trace", args.pl_trace),
                    ("vivado_util", args.vivado_util), ("vivado_timing", args.vivado_timing)):
        if p is not None:
            f = _copy(p, raw, role)
            if role == "annotations":
                a = load_annotations(raw / f["file"])
                f.update(records=len(a["records"]), problems=[list(x) for x in a["problems"]])
            files.append(f)
    for p in args.hw_gate:
        files.append(_copy(p, raw, "hw_gate"))
    for p in args.yosys:
        files.append(_copy(p, raw, "yosys"))
    manifest = {"schema": SCHEMA, "created_utc": datetime.now(timezone.utc).isoformat(), "note": args.note,
                "contains_simulation_data": sim, "runs": runs, "files": files,
                "schema_problems": sum(len(f.get("problems", [])) for f in files)}
    (args.out / "run_manifest.json").write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    print(f"bundle {args.out}: {len(files)} files, {len(runs)} runs, simulation={sim}, "
          f"schema problems {manifest['schema_problems']}")
    return 0 if manifest["schema_problems"] == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
