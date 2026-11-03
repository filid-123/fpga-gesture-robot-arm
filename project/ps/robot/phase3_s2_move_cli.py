"""S2 point-to-point move CLI (PC or PYNQ PS).

Offline (no hardware, works on the PC):

    python phase3_s2_move_cli.py plan    <request.json> --profile <arm_profile.yaml> [--current-q16 ...]
        validate a gesture.phase3.s2_move_request.v1 request with the golden
        model and print N, Na, limits, peak steps and the samples (JSON).

On the PYNQ with the S2 overlay loaded:

    sudo -E python3 phase3_s2_move_cli.py status
    sudo -E python3 phase3_s2_move_cli.py apply  <request.json> --profile <yaml> [--start]
    sudo -E python3 phase3_s2_move_cli.py pause | resume | estop | clear
    sudo -E python3 phase3_s2_move_cli.py source {s1,s2}

``apply`` takes the start from LAST_DELIVERED (current commanded position),
refuses soft-limit violations and TBD profile limits, writes the move and
starts it only with ``--start``.  The planner itself never drives a pin: the
S1 arm backend's MODE/ARM/permission and RealOutputPermit rules still decide
whether samples reach RoArm-M3 / SO-ARM101.  ``apply --start`` refuses while
the arm backend is in LINE mode unless ``--confirm-arm-motion`` is given.
A PC can send a request over SSH, e.g.
``ssh xilinx@pynq "sudo -E python3 phase3_s2_move_cli.py apply - --profile p.yaml --start" < move.json``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

import planner_p2p_reference as pr

PLANNER_BASE = 0x43C4_0000
ARM_BACKEND_BASE = 0x43C3_0000
ARM_MODE_REG = 0x004           # S1 arm backend MODE, bits [1:0]
ARM_MODE_LINE = 3


def _load_request(arg: str) -> dict:
    if arg == "-":
        return json.loads(sys.stdin.read())
    return pr.load_request(arg)


def _load_profile(path: Path):
    from arm_profile import ArmProfile

    return ArmProfile.load(path)


def cmd_plan(request: dict, profile, current: Sequence[int] | None) -> dict:
    move, problems = pr.move_from_request(request, profile, current)
    result = pr.validate(move, current)
    report = {
        "contract": pr.CONTRACT,
        "n_samples": move.n_samples,
        "accel_samples": move.accel_samples,
        "profile": move.profile,
        "period_cycles": move.period_cycles,
        "vmax_q16": list(move.vmax_q16),
        "amax_q32": list(move.amax_q32),
        "soft_limit_problems": problems,
        "validation": None if result.ok else {"error": result.error.name, "channel": result.channel},
    }
    if result.ok:
        report["peak_step_q16"] = list(pr.max_step(move))
        report["samples_q16"] = [list(s) for s in pr.samples(move)]
    return report


def _drivers():
    import planner_axi_driver as drv

    planner = drv.PlannerAxiDriver.from_pynq(PLANNER_BASE)
    planner.assert_abi()
    return drv, planner


def _arm_mode() -> int:
    from pynq import MMIO

    return int(MMIO(ARM_BACKEND_BASE, 0x1000).read(ARM_MODE_REG)) & 0x3


def _refused(**fields) -> int:
    print(json.dumps({"result": "REFUSED", **fields}, indent=2))
    return 3


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("request")
    plan.add_argument("--profile", type=Path, required=True)
    plan.add_argument("--current-q16", type=int, nargs=6)
    apply = sub.add_parser("apply")
    apply.add_argument("request")
    apply.add_argument("--profile", type=Path, required=True)
    apply.add_argument("--start", action="store_true")
    apply.add_argument("--confirm-arm-motion", action="store_true")
    for name in ("status", "pause", "resume", "estop", "clear"):
        sub.add_parser(name)
    source = sub.add_parser("source")
    source.add_argument("which", choices=("s1", "s2"))
    args = parser.parse_args(argv)

    if args.command == "plan":
        try:
            report = cmd_plan(_load_request(args.request), _load_profile(args.profile),
                              tuple(args.current_q16) if args.current_q16 else None)
        except pr.MoveRequestError as exc:
            return _refused(reason=str(exc))
        print(json.dumps(report, indent=2))
        return 0 if report["validation"] is None and not report["soft_limit_problems"] else 3

    drv, planner = _drivers()
    if args.command == "status":
        status = planner.status()
        print(json.dumps({"state": status.state.name, "source": status.source, "done": status.done,
                          "planner_pending": status.planner_pending, "errors": [e.name for e in planner.errors()],
                          "error_channel": status.error_channel, "last_delivered_q16": planner.last_delivered()},
                         indent=2))
        return 0
    if args.command in ("pause", "resume", "estop", "clear"):
        getattr(planner, args.command)()
        print(json.dumps({"command": args.command, "state": planner.status().state.name}))
        return 0
    if args.command == "source":
        planner.select_source(drv.SOURCE_S1_TRAJECTORY if args.which == "s1" else drv.SOURCE_S2_PLANNER)
        print(json.dumps({"source": args.which}))
        return 0

    # apply
    profile = _load_profile(args.profile)
    status = planner.status()
    if status.source != drv.SOURCE_S2_PLANNER:
        return _refused(reason="SOURCE_SELECT is S1; run 'source s2' first")
    current = planner.last_delivered()
    try:
        move, problems = pr.move_from_request(_load_request(args.request), profile, current)
    except pr.MoveRequestError as exc:
        return _refused(reason=str(exc))
    if problems:
        return _refused(soft_limit_problems=problems)
    result = pr.validate(move, current)
    if not result.ok:
        return _refused(error=result.error.name, channel=result.channel)
    if args.start and _arm_mode() == ARM_MODE_LINE and not args.confirm_arm_motion:
        return _refused(reason="arm backend is in LINE mode; add --confirm-arm-motion")
    planner.load_move(move)
    if args.start:
        planner.start()
    print(json.dumps({"result": "LOADED" if not args.start else "STARTED", "n_samples": move.n_samples,
                      "accel_samples": move.accel_samples, "period_cycles": move.period_cycles}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
