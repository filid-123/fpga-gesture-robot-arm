"""Resolve the frozen S8 dependency set and the existing robot contracts."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (ROOT / "sim/phase3_robot", ROOT / "ps/robot", HERE / "s8_baseline"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Native ABI adapters take precedence over frozen S8 contracts.
sys.path.insert(0, str(HERE / 'adapters'))
