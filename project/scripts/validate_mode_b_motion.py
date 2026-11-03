"""Reproducible multi-object, variable-endpoint, obstacle and rejection validation."""
from __future__ import annotations
from copy import deepcopy
import argparse
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pc.mode_b.motion.export import write_package
from pc.mode_b.motion.planner import Planner, PlanningError
from pc.mode_b.motion.state_machine import simulate_task


def validate(output, random_per_class=3):
    output.mkdir(parents=True, exist_ok=False)
    c = json.loads((ROOT/"config/ai_pc/mode_b_motion_nominal_v1.json").read_text())
    # Validate the frozen baseline, independently of an edited live target.
    base = json.loads((ROOT/"scripts/fixtures/mode_b_motion_red_request_v1.json").read_text())
    planner = Planner(ROOT, c)
    rng = np.random.default_rng(20261027)
    cases, records = [], []
    for name, spec in c["objects"].items():
        request = deepcopy(base)
        request.update(object_class=name, task_id=name+"_nominal")
        request["pickup"]["centre_mm"][2] = spec["size_mm"][2]/2
        cases.append((request, True, "reference"))
        for index in range(random_per_class):
            request = deepcopy(request)
            request["task_id"] = name+"_random_"+str(index)
            request["pickup"] = {"centre_mm": [float(rng.uniform(535, 625)), float(rng.uniform(250, 300)), spec["size_mm"][2]/2],
                                  "yaw_deg": float(rng.uniform(-35, 35))}
            request["destination"]["support_centre_mm"] = [float(rng.uniform(335, 395)), float(rng.uniform(125, 165)), 25.]
            cases.append((request, None, "randomized_reach_and_complete_path"))
    for label, change in (("outside_pickup", lambda r: r["pickup"].update(centre_mm=[900, 900, 15])),
                          ("unreachable_target", lambda r: r["destination"].update(support_centre_mm=[50, 550, 25])),
                          ("small_support", lambda r: r["destination"].update(size_xy_mm=[10, 10])),
                          ("occupied_source", lambda r: r.update(obstacles=[{"id":"occluder", "centre_mm":[540,280,40], "size_mm":[40,40,80]}])),
                          ("unknown_class", lambda r: r.update(object_class="scissors"))):
        r = deepcopy(base); r["task_id"] = label; change(r)
        cases.append((r, False, "expected_rejection"))
    obstacle_case = deepcopy(base)
    obstacle_case["task_id"] = "red_with_registered_obstacle"
    obstacle_case["obstacles"] = [{"id": "other_visible_object", "centre_mm": [480, 300, 23], "size_mm": [25,25,46]}]
    cases.append((obstacle_case, None, "registered_obstacle"))
    requested = deepcopy(base)
    requested["task_id"] = "historical_target_255_230_25"
    requested["destination"]["support_centre_mm"] = [255,230,25]
    cases.append((requested, None, "historical_requested_target_under_current_tilt_limits"))
    for request, expected, category in cases:
        print("VALIDATING", request["task_id"], flush=True)
        start = time.perf_counter()
        try:
            plan = planner.plan(request)
            package = output/request["task_id"]
            write_package(plan, c, package)
            state = simulate_task(plan)
            (package/"state_machine_simulation.json").write_text(json.dumps(state, indent=2), encoding="utf8")
            result = {"task_id":request["task_id"], "category":category, "accepted":True,
                "expected_acceptance": expected, "state_machine_complete":state["complete"],
                "segments":len(plan["segments"]), "samples":plan["sample_count"], "planning_ms":plan["planning_ms"],
                "motion_seconds_excluding_waits":plan["nominal_motion_seconds"], "search_attempts":plan["search"]["attempts"],
                "sample_sha256":plan["sample_sha256"], "verification":plan["verification"], "request":request,
                "correct":expected is not False and state["complete"]}
        except PlanningError as error:
            result = {"task_id":request["task_id"], "category":category, "accepted":False,
                "expected_acceptance":expected, "reason":str(error), "request":request, "correct":expected is not True}
        result["elapsed_seconds"] = time.perf_counter()-start
        records.append(result)
        print("ACCEPTED" if result["accepted"] else "REJECTED", request["task_id"], round(result["elapsed_seconds"],2), flush=True)
        (output/"case_results.json").write_text(json.dumps(records, indent=2, allow_nan=False), encoding="utf8")
    accepted = [r for r in records if r["accepted"]]
    report = {"schema":"gesture.mode_b.motion_validation.v1", "seed":20261027, "python":platform.python_version(),
        "cases":len(records), "accepted_complete_tasks":len(accepted), "rejected_tasks":len(records)-len(accepted),
        "expected_cases_passed":all(r["correct"] for r in records),
        "accepted_sample_count":sum(r["samples"] for r in accepted),
        "randomized_acceptance_is_not_physical_success_rate":True,
        "npu_target_validation":"NOT_RUN", "rocm_target_validation":"NOT_RUN",
        "physical_execution_allowed":False, "case_results":"case_results.json"}
    (output/"summary.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--random-per-class", type=int, default=3)
    args = parser.parse_args()
    result = validate(args.output, args.random_per_class)
    print(json.dumps(result, indent=2))
    return 0 if result["expected_cases_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
