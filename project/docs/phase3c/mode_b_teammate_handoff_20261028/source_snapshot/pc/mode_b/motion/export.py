"""Full task export and an explicitly non-deployable FPGA adapter draft."""
from __future__ import annotations
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path

from .planner import digest, plan_digest
from .trajectory import regenerate, sample_digest


def verify_task(plan, config):
    """Rebuild every normal/cancel PL sample before trusting an exported task."""
    if plan_digest(plan) != plan["plan_sha256"] or digest(config) != plan["config_sha256"]:
        raise ValueError("Task/config integrity mismatch")
    if plan["period_s"] != config["period_s"]:
        raise ValueError("Task/config period mismatch")
    for path in (plan, *plan["cancel_branches"].values()):
        rows = []
        for segment, samples in regenerate(path["start_q16"], path["segments"], config):
            if segment["period_cycles"] != round(config["period_s"]*config["clock_hz"]):
                raise ValueError("Segment/config period mismatch")
            if segment["sample_offset"] != len(rows):
                raise ValueError("Segment sample offset mismatch")
            rows.extend(samples)
        if len(rows) != path["sample_count"] or sample_digest(rows) != path["sample_sha256"]:
            raise ValueError("Task/branch sample count or digest mismatch")
        if path["segments"][-1]["target_q16"] != plan["start_q16"]:
            raise ValueError("Task/branch does not end at nominal HOME")


def load_package(task_path: Path):
    """Load a local simulation package, checking file hashes and the full task."""
    task_path = Path(task_path)
    manifest = json.loads((task_path.parent/"manifest.json").read_text(encoding="utf8"))
    required = {"complete_task.json", "config_snapshot.json", "fpga_adapter_draft.json", "trajectory.csv"}
    if task_path.name != "complete_task.json" or not required <= manifest.keys():
        raise ValueError("Incomplete task package manifest")
    for name, expected in manifest.items():
        if Path(name).name != name or name in (".", ".."):
            raise ValueError("Manifest entries must be local filenames")
        if hashlib.sha256((task_path.parent/name).read_bytes()).hexdigest() != expected:
            raise ValueError("Package file integrity mismatch: "+name)
    plan = json.loads(task_path.read_text(encoding="utf8"))
    config = json.loads((task_path.parent/"config_snapshot.json").read_text(encoding="utf8"))
    verify_task(plan, config)
    return plan, config


def write_package(plan, config, output: Path):
    verify_task(plan, config)
    output.mkdir(parents=True, exist_ok=False)
    all_rows = []
    for _, rows in regenerate(plan["start_q16"], plan["segments"], config):
        all_rows.extend(rows)
    if sample_digest(all_rows) != plan["sample_sha256"]:
        raise ValueError("Complete task sample digest mismatch")
    document = deepcopy(plan)
    document.pop("sample_rows")
    for branch in document["cancel_branches"].values():
        branch.pop("sample_rows")
    (output/"complete_task.json").write_text(json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf8")
    (output/"config_snapshot.json").write_text(json.dumps(config, indent=2, allow_nan=False), encoding="utf8")
    with (output/"trajectory.csv").open("w", newline="", encoding="utf8") as f:
        writer = csv.writer(f)
        writer.writerow(["sample_index", "time_s", "segment", "phase", "b_q16", "s_q16", "e_q16", "t_q16", "r_q16", "g_q16"])
        for seg_index, (segment, rows) in enumerate(regenerate(plan["start_q16"], plan["segments"], config)):
            for j, row in enumerate(rows):
                i = segment["sample_offset"]+j
                writer.writerow([i, (i+1)*config["period_s"], seg_index, segment["phase"], *row])
    chunks = []
    start = plan["start_q16"]
    # Preserve every event boundary. These are load blocks for a NEW task
    # adapter; they are not legal legacy PATH_SUBMIT messages.
    for offset in range(0, len(plan["segments"]), 32):
        segments = deepcopy(plan["segments"][offset:offset+32])
        chunks.append({"index": len(chunks), "start_q16": start, "segments": segments,
                       "requires_previous_chunk_done": bool(chunks)})
        start = segments[-1]["target_q16"]
    adapter = {"schema": "gesture.mode_b.fpga_task_adapter_draft.v1", "task_id": plan["task_id"],
        "status": "REQUIRES_FPGA_TEAM_ADAPTER_REVIEW_NOT_LEGACY_PATH_SUBMIT",
        "physical_execution_allowed": False, "joint_mapping": "UNVERIFIED_URDF_TO_DEVICE",
        "mode_a_tables_changed": False, "whole_task_atomic_validation_required": True,
        "chunks": chunks, "cancel_branches": document["cancel_branches"],
        "sample_sha256": plan["sample_sha256"], "config_sha256": plan["config_sha256"],
        "required_events": ["GRASP_VERIFIED", "PALM_READY", "SUPPORT_VERIFIED", "SOURCE_VACANT",
                            "PLACEMENT_AND_EMPTY_HOME_VERIFIED"],
        "ready_expiry_and_fault_hold_required": True}
    (output/"fpga_adapter_draft.json").write_text(json.dumps(adapter, indent=2, allow_nan=False), encoding="utf8")
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
    (output/"manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
    return output/"complete_task.json"
