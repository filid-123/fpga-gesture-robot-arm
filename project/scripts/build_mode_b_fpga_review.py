"""Build/verify offline FPGA review or compare accepted samples; never connects devices."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pc.mode_b.motion.fpga_review import build_review, compare_samples, verify_review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--output", type=Path, help="Build a new review folder")
    action.add_argument("--verify", type=Path, help="Verify an existing transferred folder")
    action.add_argument("--compare-mem", type=Path, nargs=2, metavar=("EXPECTED", "ACTUAL"))
    parser.add_argument("--examples", type=Path, default=ROOT/"docs/phase3c/mode_b_motion_20261027/continuity_v2_260_160_30/examples")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.output:
        build_review(ROOT, args.examples, args.output)
        result = verify_review(args.output)
    elif args.verify:
        result = verify_review(args.verify)
    else:
        result = compare_samples(*args.compare_mem)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
