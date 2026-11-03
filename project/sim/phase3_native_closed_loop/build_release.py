"""Final packaging entry point; use native_motion/scripts/package_native_motion.py."""
import runpy
from pathlib import Path
if __name__=="__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[2]/"native_motion/scripts/package_native_motion.py"),run_name="__main__")
