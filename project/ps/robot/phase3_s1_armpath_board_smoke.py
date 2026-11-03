"""PYNQ-Z2 board smoke for the S1 arm-path overlay (candidate, never board-run).

Run each step separately, in order, and stop at the first FAIL
(board/BOARD_TEST_CN.md).  NO robot or servo bus may be connected.

    sudo -E python3 phase3_s1_armpath_board_smoke.py --step readonly
    sudo -E python3 phase3_s1_armpath_board_smoke.py --step dryrun --backend roarm
    sudo -E python3 phase3_s1_armpath_board_smoke.py --step dryrun --backend so101
    sudo -E python3 phase3_s1_armpath_board_smoke.py --step loopback --backend roarm --confirm-no-robot
    sudo -E python3 phase3_s1_armpath_board_smoke.py --step emulator --backend so101 --confirm-no-robot

* readonly : load the overlay, read both ABIs, capabilities and status only.
* dryrun   : bench configuration, MODE=DRY_RUN (pins stay idle), one golden
             segment through the PL scheduler; checks frame count, errors and
             the PL-mapped last command against the Python model.
* loopback : RoArm pins, arm_uart_tx jumpered to arm_uart_rx; LINE mode; the
             JSON parser must read the command lines back.
* emulator : SO-ARM101 pins wired to a PC USB-UART running
             ``arm_bench_tools.py emulate-so101``; LINE mode with PRIME and
             READ replies.

The motion-enable input must be HIGH (jumper to 3V3) for loopback/emulator.
Output: one JSON object with "result" PASS/FAIL; nothing is written to disk.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import arm_backend as ab  # noqa: E402
import arm_backend_axi_driver as drv  # noqa: E402
import trajectory_axi_driver as td  # noqa: E402
from arm_bench_tools import load_bench, load_segment  # noqa: E402

TRAJECTORY_BASE = 0x43C2_0000
ARM_BACKEND_BASE = drv.PROPOSED_BASE_ADDRESS
DEFAULT_PERIOD_CYCLES = 2_000_000          # 20 ms per sample (50 Hz)


def run_segment(traj: td.TrajectoryAxiDriver, samples_start, samples_target, period: int) -> None:
    traj.clear_done()
    traj.submit_q16_16(samples_start, samples_target, period, wait_ready=True, timeout_s=1.0)


def wait_until(predicate, timeout_s: float, poll_s: float = 0.005) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(poll_s)
    return predicate()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--step", choices=("readonly", "dryrun", "loopback", "emulator"), required=True)
    parser.add_argument("--backend", choices=("roarm", "so101"), default="roarm")
    parser.add_argument("--bit", type=Path, default=HERE / "phase3_s1_armpath.bit")
    parser.add_argument("--mem", type=Path, default=HERE / "pick_place_phase3_trajectory_q16_16_v1.mem")
    parser.add_argument("--segment", type=int, default=2)
    parser.add_argument("--period-cycles", type=int, default=DEFAULT_PERIOD_CYCLES)
    parser.add_argument("--confirm-no-robot", action="store_true")
    parser.add_argument("--response-timeout-ms", type=float, default=50.0,
                        help="emulator step: PC USB latency needs a long READ timeout")
    parser.add_argument("--no-download", action="store_true", help="overlay already loaded")
    args = parser.parse_args()

    report: dict = {"step": args.step, "backend": args.backend, "physical_robot": False}
    try:
        from pynq import Overlay
    except ImportError:
        print(json.dumps({**report, "result": "FAIL", "reason": "must run on the PYNQ image"}))
        return 2
    if not args.no_download:
        Overlay(str(args.bit), download=True)
    traj = td.TrajectoryAxiDriver.from_pynq(TRAJECTORY_BASE, expected_abi=td.TRAJECTORY_ABI_VERSION_EXT_SINK)
    arm = drv.ArmBackendAxiDriver.from_pynq(ARM_BACKEND_BASE)
    traj.assert_abi()
    arm.assert_abi()
    report["capabilities"] = arm.capabilities()
    report["status_raw"] = f"0x{arm.status().raw:08X}"
    report["errors"] = [e.name for e in arm.errors()]
    if args.step == "readonly":
        report["result"] = "PASS" if not report["errors"] else "FAIL"
        print(json.dumps(report, indent=2))
        return 0 if report["result"] == "PASS" else 1

    profile, protocol, config = load_bench(args.backend, HERE / "config" if (HERE / "config").is_dir() else None)
    if args.step == "emulator":
        cycles = ab.ms_to_cycles(args.response_timeout_ms)
        # PC USB-UART latency (1..16 ms) replaces the servo's return delay:
        # long READ timeout and a 1 s feedback timeout for this bench step only.
        config = dataclasses.replace(config, response_timeout_cycles=cycles,
                                     feedback_timeout_ticks=max(config.feedback_timeout_ticks, 1000))
    samples = load_segment(args.mem, args.segment)
    lines = [l.strip() for l in args.mem.read_text(encoding="ascii").splitlines() if l.strip()]
    from arm_fixed_point import unpack_192
    start = unpack_192(int(lines[args.segment * 32], 16))
    target = unpack_192(int(lines[(args.segment + 1) * 32], 16))
    model = ab.ArmBackendPlModel(config)
    expected_last = [model.process_sample(s) for s in samples][-1].device_values
    if not ab.feedback_refresh_ok(config, args.period_cycles):
        report["warning"] = "period too long for the feedback timeout; expect FEEDBACK_TIMEOUT"

    arm.write(drv.MODE, ab.MODE_OFF | (config.backend_sel << 4))
    arm.clear_errors()
    arm.clear_counters()
    arm.load_config(config)
    arm.commit_config()
    if args.step == "dryrun":
        arm.set_mode(ab.MODE_DRY_RUN, backend=config.backend_sel)
    else:
        permit = ab.require_real_output(profile, protocol, purpose="bench_loopback",
                                        confirm_no_robot=args.confirm_no_robot)
        arm.set_mode(ab.MODE_LINE, backend=config.backend_sel, arm=True, permit=permit)
        if not wait_until(lambda: arm.status().permission, 1.0):
            arm.stop()
            print(json.dumps({**report, "result": "FAIL", "reason": "no permission (motion-enable input low?)"}))
            return 1
        if config.required_mask and not wait_until(lambda: arm.status().feedback_valid, 2.0):
            arm.stop()
            print(json.dumps({**report, "result": "FAIL", "reason": "PRIME did not complete (emulator?)",
                              "errors": [e.name for e in arm.errors()]}))
            return 1
    run_segment(traj, start, target, args.period_cycles)
    timeout_s = 32 * args.period_cycles / 100e6 + 5.0
    done = wait_until(lambda: arm.counters().frames_tx >= 32, timeout_s)
    time.sleep(0.2)
    snap = arm.snapshot()
    counters = arm.counters()
    errors = [e.name for e in arm.errors()]
    arm.stop()
    checks = {
        "frames_tx_32": done and counters.frames_tx == 32,
        "no_errors": not errors,
        "cmd_dev_matches_model": list(snap.cmd_dev) == list(expected_last),
    }
    if args.step == "loopback":
        checks["loopback_feedback"] = list(snap.fb_dev) == list(expected_last) and counters.fb_ok >= 32
    if args.step == "emulator":
        checks["feedback_all_valid"] = snap.valid_mask == 0x3F and counters.resp_timeouts == 0
    report.update(
        checks=checks,
        counters=dataclasses.asdict(counters),
        snapshot=dataclasses.asdict(snap),
        expected_last_cmd_dev=list(expected_last),
        frame_ms_last=counters.frame_cycles_last / 1e5,
        frame_ms_max=counters.frame_cycles_max / 1e5,
        errors=errors,
        result="PASS" if all(checks.values()) else "FAIL",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
