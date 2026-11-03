"""Plan/export a complete Mode B task without opening camera or robot connections."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pc.mode_b.motion.planner import Planner
from pc.mode_b.motion.export import write_package
from pc.mode_b.motion.state_machine import simulate_task


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT/"config/ai_pc/mode_b_motion_nominal_v1.json")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf8"))
    request = json.loads(args.request.read_text(encoding="utf8"))
    plan = Planner(ROOT, config).plan(request)
    path = write_package(plan, config, args.output)
    state = simulate_task(plan)
    (args.output/"state_machine_simulation.json").write_text(json.dumps(state, indent=2), encoding="utf8")
    print(json.dumps({"task": str(path), "segments": len(plan["segments"]), "samples": plan["sample_count"],
        "nominal_motion_seconds_excluding_waits": plan["nominal_motion_seconds"],
        "state_machine_complete": state["complete"], "physical_execution_allowed": False,
        "npu_target_acceptance": "PENDING_REAL_AMD_MACHINE"}, indent=2))
    return 0 if state["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
