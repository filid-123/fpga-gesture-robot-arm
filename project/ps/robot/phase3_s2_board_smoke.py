"""PYNQ-Z2 board smoke for the S2 motion overlay.

Run each step separately, in order, and stop at the first FAIL
(BOARD_TEST_CN.md).  NO robot or servo bus may be connected; the
arm backend stays in DRY_RUN (pins idle) for every step.

    sudo -E python3 phase3_s2_board_smoke.py --step readonly
    sudo -E python3 phase3_s2_board_smoke.py --step dryrun --backend roarm
    sudo -E python3 phase3_s2_board_smoke.py --step dryrun --backend so101

* readonly : load the overlay, read the three ABIs (0x3002 / 0x3101 / 0x3201),
             planner capabilities, SOURCE_SELECT = S1 after load, no errors.
* dryrun   : bench configuration, MODE=DRY_RUN;
             1. S1 compatibility: observe the COMMIT-to-first-sample window
                without issuing an AXI write expected to return SLVERR; then
                pass one golden S1 segment through the mux
                (SOURCE = S1), 32 frames, command equals the S1 model;
             2. SOURCE = planner; trapezoid move from LAST_DELIVERED with the
                bench profile limits, PAUSE after 30 frames (no frame while
                paused), RESUME, DONE: frame count = N, LAST_DELIVERED =
                target, backend command = model;
             3. return move, ESTOP after 20 frames: at most two more frames
                (the frame in flight and the pending sample), state ESTOP,
                ERROR.ESTOP; CLEAR -> IDLE;
             4. SOURCE back to S1; ABIs unchanged.
Output: one JSON object with "result" PASS/FAIL; nothing is written to disk.
"""

from __future__ import annotations

import argparse
import dataclasses
import faulthandler
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import arm_backend as ab  # noqa: E402
import arm_backend_axi_driver as drv  # noqa: E402
import planner_axi_driver as pd  # noqa: E402
import planner_p2p_reference as pr  # noqa: E402
import trajectory_axi_driver as td  # noqa: E402
from arm_bench_tools import load_bench, load_segment  # noqa: E402
from arm_fixed_point import unpack_192  # noqa: E402

TRAJECTORY_BASE = 0x43C2_0000
ARM_BACKEND_BASE = drv.PROPOSED_BASE_ADDRESS
PLANNER_BASE = pd.PROPOSED_BASE_ADDRESS
PERIOD_S = 0.02                              # 20 ms per sample (50 Hz)
STEP_Q16 = 3277                              # 0.05 rad per joint


def wait_until(predicate, timeout_s: float, poll_s: float = 0.005) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(poll_s)
    return predicate()


def small_target(profile, start):
    """start +/- 0.05 rad per joint, inside the profile soft limits."""

    target = []
    for joint in profile.joints:
        ch = joint.logical_channel
        up = start[ch] + STEP_Q16
        target.append(up if up <= joint.soft_max_rad * 65536 else start[ch] - STEP_Q16)
    return tuple(target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--step", choices=("readonly", "dryrun"), required=True)
    parser.add_argument("--backend", choices=("roarm", "so101"), default="roarm")
    parser.add_argument("--bit", type=Path, default=HERE / "phase3_s2_motion.bit")
    parser.add_argument("--mem", type=Path, default=HERE / "pick_place_phase3_trajectory_q16_16_v1.mem")
    parser.add_argument("--segment", type=int, default=2)
    parser.add_argument("--no-download", action="store_true", help="overlay already loaded")
    args = parser.parse_args()
    faulthandler.enable()  # preserve a Python stack in C2/C3.log if MMIO raises SIGBUS

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
    plan = pd.PlannerAxiDriver.from_pynq(PLANNER_BASE)
    traj.assert_abi()
    arm.assert_abi()
    plan.assert_abi()
    status = plan.status()
    report.update(planner_capabilities=plan.capabilities(), planner_status_raw=f"0x{status.raw:08X}",
                  planner_errors=[e.name for e in plan.errors()], arm_errors=[e.name for e in arm.errors()])
    checks = {
        "source_is_s1_after_load": status.source == pd.SOURCE_S1_TRAJECTORY,
        "planner_idle": status.state is pr.PlannerState.IDLE,
        "no_errors": not report["planner_errors"] and not report["arm_errors"],
        "min_period_512": report["planner_capabilities"]["min_period_cycles"] == pr.MIN_PERIOD_CYCLES,
    }
    if args.step == "readonly":
        report.update(checks=checks, result="PASS" if all(checks.values()) else "FAIL")
        print(json.dumps(report, indent=2))
        return 0 if report["result"] == "PASS" else 1

    profile, _protocol, config = load_bench(args.backend, HERE / "config" if (HERE / "config").is_dir() else None)
    period_cycles = pr.seconds_to_cycles(PERIOD_S)
    arm.write(drv.MODE, ab.MODE_OFF | (config.backend_sel << 4))
    arm.clear_errors()
    arm.clear_counters()
    arm.load_config(config)
    arm.commit_config()
    arm.set_mode(ab.MODE_DRY_RUN, backend=config.backend_sel)
    try:
        # 1. S1 compatibility through the mux
        samples = load_segment(args.mem, args.segment)
        lines = [l.strip() for l in args.mem.read_text(encoding="ascii").splitlines() if l.strip()]
        seg_start = unpack_192(int(lines[args.segment * 32], 16))
        seg_target = unpack_192(int(lines[(args.segment + 1) * 32], 16))
        model = ab.ArmBackendPlModel(config)
        s1_last_dev = [model.process_sample(s) for s in samples][-1].device_values
        traj.clear_done()
        s1_period_s = 0.1  # leave a clear window before the first S1 sample
        traj.submit_q16_16(seg_start, seg_target, pr.seconds_to_cycles(s1_period_s),
                           wait_ready=True, timeout_s=1.0)
        checks["s1_pre_first_guard_window"] = wait_until(lambda: traj.status().busy, 1.0) and not traj.status().sample_valid
        if not checks["s1_pre_first_guard_window"]:
            raise RuntimeError("S1 COMMIT-to-first-sample window was not observed")
        # The negative SOURCE_SELECT case is covered by XSim. On PYNQ, its
        # intentional AXI SLVERR can become a process-fatal SIGBUS.
        checks["s1_frames_32"] = wait_until(lambda: arm.counters().frames_tx >= 32, 32 * s1_period_s + 5.0)
        time.sleep(0.2)
        checks["s1_cmd_matches_model"] = list(arm.snapshot().cmd_dev) == list(s1_last_dev)
        checks["s1_last_delivered"] = plan.last_delivered() == tuple(seg_target)

        # 2. planner move with PAUSE/RESUME
        plan.select_source(pd.SOURCE_S2_PLANNER)
        start = plan.last_delivered()
        target = small_target(profile, start)
        vmax, amax = pr.limits_from_profile(profile, PERIOD_S)
        move = pr.plan_move(start, target, duration_s=2.0, period_s=PERIOD_S, profile_kind="trapezoid",
                            accel_time_s=0.5, vmax_q16=vmax, amax_q32=amax)
        problems = pr.check_soft_limits(profile, (start, target))
        if problems or not pr.validate(move, start).ok:
            raise RuntimeError(f"smoke move refused by the golden model: {problems or pr.validate(move, start)}")
        move_dev = [model.process_sample(s) for s in pr.samples(move)][-1].device_values
        planner_frames_base = arm.counters().frames_tx
        plan.load_move(move)
        plan.start()
        if not wait_until(lambda: arm.counters().frames_tx >= planner_frames_base + 30,
                          30 * PERIOD_S + 2.0):
            raise TimeoutError("planner did not deliver 30 DRY_RUN frames")
        if plan.status().state is not pr.PlannerState.RUN:
            raise RuntimeError("planner left RUN before PAUSE")
        plan.pause()
        time.sleep(3 * PERIOD_S)
        paused_frames = arm.counters().frames_tx
        time.sleep(0.3)
        checks["no_frame_while_paused"] = (arm.counters().frames_tx == paused_frames
                                           and plan.status().state is pr.PlannerState.PAUSED)
        if plan.status().state is not pr.PlannerState.PAUSED:
            raise RuntimeError("planner did not enter PAUSED")
        plan.resume()
        final = plan.wait_state({pr.PlannerState.DONE, pr.PlannerState.ERROR, pr.PlannerState.ESTOP},
                                move.n_samples * PERIOD_S + 5.0)
        time.sleep(0.2)
        checks["planner_done"] = final.state is pr.PlannerState.DONE
        if not checks["planner_done"]:
            raise RuntimeError(f"planner ended in {final.state.name}, not DONE")
        checks["planner_frames_n"] = arm.counters().frames_tx - planner_frames_base == move.n_samples
        checks["planner_last_delivered"] = plan.last_delivered() == move.target
        checks["planner_cmd_matches_model"] = list(arm.snapshot().cmd_dev) == list(move_dev)
        report["late_count"] = plan.read(pd.LATE_COUNT)

        # 3. return move, ESTOP
        back = pr.plan_move(move.target, move.start, duration_s=2.0, period_s=PERIOD_S, profile_kind="trapezoid",
                            accel_time_s=0.5, vmax_q16=vmax, amax_q32=amax)
        back_samples = pr.samples(back)
        return_frames_base = arm.counters().frames_tx
        plan.load_move(back)
        plan.start()
        if not wait_until(lambda: arm.counters().frames_tx >= return_frames_base + 20,
                          20 * PERIOD_S + 2.0):
            raise TimeoutError("return move did not deliver 20 DRY_RUN frames")
        plan.estop()
        at_estop = arm.counters().frames_tx - return_frames_base
        time.sleep(0.5)
        after = arm.counters().frames_tx - return_frames_base
        checks["estop_state"] = plan.status().state is pr.PlannerState.ESTOP
        checks["estop_error"] = pr.PlannerError.ESTOP in plan.errors()
        checks["estop_frames_stop"] = after <= at_estop + 2 and after < back.n_samples
        checks["estop_last_is_move_sample"] = plan.last_delivered() in back_samples
        if plan.status().state is not pr.PlannerState.ESTOP:
            raise RuntimeError("planner did not enter ESTOP before CLEAR")
        plan.clear()
        checks["clear_idle"] = plan.status().state is pr.PlannerState.IDLE and not plan.errors()
        if not checks["clear_idle"] or plan.status().planner_pending:
            raise RuntimeError("planner is not idle and drained before source switch")

        # 4. back to S1
        plan.select_source(pd.SOURCE_S1_TRAJECTORY)
        traj.assert_abi()
        arm.assert_abi()
        checks["arm_no_errors"] = not arm.errors()
        report["arm_errors_final"] = [e.name for e in arm.errors()]
        report["counters"] = dataclasses.asdict(arm.counters())
    finally:
        arm.stop()
    report.update(checks=checks, result="PASS" if all(checks.values()) else "FAIL")
    print(json.dumps(report, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
