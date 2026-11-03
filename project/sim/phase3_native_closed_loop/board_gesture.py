"""Explicit operator/injected gestures; does not claim classifier validation."""
import argparse
import bootstrap
from s4_task_axi_driver import S4TaskAxiDriver, MODE_CFG
import s4_task_reference as m

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("gesture", choices=["PALM", "FIST", "BACKGROUND"])
args = parser.parse_args()
driver = S4TaskAxiDriver.from_pynq()
if not driver.read(MODE_CFG) & 8:
    raise RuntimeError("S4 VISION_SIM is not enabled")
driver.vision_sim({"PALM":m.PALM_READY,"FIST":m.FIST_CANCEL,"BACKGROUND":m.BACKGROUND}[args.gesture],
                  window_ok=args.gesture=="PALM")
print(driver.status())
