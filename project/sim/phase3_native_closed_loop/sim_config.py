"""Load the explicitly simulator-only geometry and original S4 tables."""
import json
from pathlib import Path
import bootstrap
import s4_task_reference as m
import planner_p2p_reference as pr
from task_orchestrator import validate_tray_path


def load(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("simulation_only") is not True or data.get("fixture") is not True:
        raise ValueError("Explicit simulation_only / fixture markers are required")
    raw = data["config"]
    for field in ("joint_min", "joint_max", "vmax", "amax"):
        raw[field] = tuple(raw[field])
    cfg = m.S4Config(**raw)
    raw = data["tables"]
    for field in ("approach", "grasp", "lift"):
        raw[field] = {int(k): tuple(v) for k,v in raw[field].items()}
    for field in ("deliver", "release", "retreat", "tray"):
        raw[field] = tuple(raw[field])
    for field in ("keypoints", "segments"):
        raw[field] = [tuple(v) for v in raw[field]]
    tables = m.S4Tables(**raw)
    ok, errors = validate_tray_path(tables, cfg, pr)
    if not ok:
        raise ValueError(errors)
    return data, cfg, tables
