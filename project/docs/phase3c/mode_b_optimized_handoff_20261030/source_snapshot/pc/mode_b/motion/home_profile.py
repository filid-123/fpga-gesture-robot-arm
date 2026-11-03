"""Resolve the current simulation HOME without modifying frozen task evidence."""
import hashlib
import json
from pathlib import Path


def simulation_config_path(root):
    root = Path(root).resolve()
    profile = json.loads((root/"config/ai_pc/robot_home_current.json").read_bytes())
    if (profile.get("schema") != "gesture.roarm.current_home.v1"
            or profile.get("physical_pose_operator_accepted") is not True):
        raise ValueError("Current physical HOME has not been accepted")
    path = (root/profile["simulation_motion_config"]).resolve()
    if not path.is_relative_to(root):
        raise ValueError("HOME simulation config must stay within the project")
    if hashlib.sha256(path.read_bytes()).hexdigest() != profile["simulation_motion_config_sha256"]:
        raise ValueError("Current HOME simulation config hash mismatch")
    config = json.loads(path.read_bytes())
    if config.get("physical_execution_allowed") is not False:
        raise ValueError("A HOME pose does not authorize an uncalibrated simulation trajectory")
    return path
