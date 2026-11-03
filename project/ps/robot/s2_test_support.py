"""Locate the frozen S1 v0.1.1 sources for the S2 tests and tools.

Merged project: S1 and S2 modules sit together in ps/robot, nothing to do.
Version-package layout: set GESTURE_S1_ROOT to the S1 v0.1.1 package (or a
project that contains it) and GESTURE_BASELINE_ROOT to the handoff baseline.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def s1_root() -> Path | None:
    """Directory that mirrors the project root and holds the S1 files."""

    if (HERE / "arm_profile.py").exists():
        return HERE.parents[1]
    env = os.environ.get("GESTURE_S1_ROOT")
    if env:
        root = Path(env)
        for candidate in (root / "src", root):
            if (candidate / "ps" / "robot" / "arm_profile.py").exists():
                return candidate
    return None


def ensure_s1_on_path() -> bool:
    root = s1_root()
    if root is None:
        return False
    ps = str(root / "ps" / "robot")
    if ps not in sys.path:
        sys.path.append(ps)
    return True


def s1_config_root() -> Path | None:
    root = s1_root()
    if root is None:
        return None
    for candidate in (root / "config", root.parent / "config"):
        if (candidate / "arm_profiles").is_dir():
            return candidate
    return None


def baseline_root() -> Path | None:
    env = os.environ.get("GESTURE_BASELINE_ROOT")
    if env and (Path(env) / "sim" / "phase3_robot" / "golden").is_dir():
        return Path(env)
    project = HERE.parents[1]
    if (project / "sim" / "phase3_robot" / "trajectory_contract.py").exists():
        return project
    return None
