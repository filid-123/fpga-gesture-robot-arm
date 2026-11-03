"""Load the matched NativeMotion BIT/HWH and perform read-only ABI checks."""
import argparse
import json
from pathlib import Path
import bootstrap
from board_state import read_board_state


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bit", type=Path, required=True)
    args = p.parse_args()
    if not args.bit.with_suffix(".hwh").is_file():
        raise FileNotFoundError("Matching HWH must sit beside the BIT")
    from pynq import Overlay
    import arm_backend_axi_driver as ad
    import planner_axi_driver as pd
    import s4_task_axi_driver as sd
    import s4_task_reference as m
    overlay = Overlay(str(args.bit), download=True)
    arm = ad.ArmBackendAxiDriver.from_pynq(ad.PROPOSED_BASE_ADDRESS)
    plan = pd.PlannerAxiDriver.from_pynq(pd.PROPOSED_BASE_ADDRESS)
    s4 = sd.S4TaskAxiDriver.from_pynq()
    arm.assert_abi(); plan.assert_abi(); s4.assert_abi(sd.ABI_VERSION_TRAY)
    report = read_board_state(arm, plan, s4)
    print(json.dumps(report, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
