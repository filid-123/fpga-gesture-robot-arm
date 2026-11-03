"""PYNQ S7/S8 -> actual PL UART -> CoppeliaSim test; no physical arm."""
import argparse
from dataclasses import replace, asdict
import json
from pathlib import Path
import time
import bootstrap
import arm_backend as ab
import arm_backend_axi_driver as ad
import planner_axi_driver as pd
import planner_p2p_reference as pr
import s4_task_axi_driver as sd
import s4_task_reference as m
from arm_bench_tools import load_bench
from s4_port import AxiS4Port
from task_orchestrator import TaskOrchestrator, Mode
from orchestrator import SimulatorOrchestrator
from arm_fixed_point import map_joint_vector
from ps_path_service import ServiceConfig, TcpPathServer
from phase3_path_contract import MotionLimits
from phase3_event_log import EventLog
from simulator_service import SimulatorPathService
from sim_config import load
from board_state import read_board_state, require_fresh_overlay, require_planner_startable


def enter_simulator_line(arm, backend, permit, timeout_s=2.0):
    """S1 forbids switching between two non-OFF modes (AXI SLVERR).

    Drain DRY_RUN through OFF before LINE. MODE writes preserve configuration;
    do not reload the config or reset the planner's already accepted HOME.
    """
    arm.set_mode(ab.MODE_OFF, backend=backend)
    deadline = time.monotonic() + timeout_s
    while True:
        status = arm.status()
        if status.fault:
            raise RuntimeError("S1 fault before LINE; reload overlay and inspect initialization")
        if status.active_mode == ab.MODE_OFF and not status.engine_busy:
            if not status.config_valid:
                raise RuntimeError("S1 configuration invalid before LINE")
            break
        if time.monotonic() >= deadline:
            raise TimeoutError("S1 did not reach OFF/idle before LINE")
        time.sleep(.001)
    arm.set_mode(ab.MODE_LINE, backend=backend, arm=True, permit=permit)


def main():
    import faulthandler
    faulthandler.enable()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--mode", choices=["A", "B"], required=True)
    parser.add_argument("--object", type=int, choices=[1,2,3], default=1)
    parser.add_argument("--repeat",type=int,choices=[1,2,3],default=1,
                        help="Run up to three different objects without reloading BIT")
    parser.add_argument("--auto-palm",action="store_true",help="Explicit simulator-only PALM injection")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--check-config", action="store_true")
    parser.add_argument("--check-board", action="store_true",
                        help="Read-only ABI/reset-state check; requires a freshly loaded BIT")
    parser.add_argument("--confirm-no-robot", action="store_true")
    args = parser.parse_args()
    data, cfg, tables = load(args.config)
    if args.check_config:
        print(json.dumps({"result":"PASS", "board_access":False, "simulation_only":True}))
        return
    if not args.check_board and not args.confirm_no_robot:
        parser.error("FPGA UART must connect only to the PC simulator: add --confirm-no-robot")
    cfg = replace(cfg, mode_b=args.mode=="B", hold_policy=args.mode=="B", tray_exit=args.mode=="B",
                  require_line=True, t_comm=25, t_arrival=50, t_palm_wait=1500)
    arm = ad.ArmBackendAxiDriver.from_pynq(ad.PROPOSED_BASE_ADDRESS)
    plan = pd.PlannerAxiDriver.from_pynq(pd.PROPOSED_BASE_ADDRESS)
    s4 = sd.S4TaskAxiDriver.from_pynq()
    arm.assert_abi(); plan.assert_abi(); s4.assert_abi(sd.ABI_VERSION_TRAY)
    if args.check_board:
        report = read_board_state(arm, plan, s4)
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out/"BOARD_PREFLIGHT.json").write_text(json.dumps(report, indent=2)+"\n")
        print(json.dumps(report, indent=2), flush=True)
        if report["result"] != "PASS":
            raise SystemExit(1)
        return
    profile, protocol, backend = load_bench("roarm", bootstrap.ROOT/"config")
    # Windows is a soft-real-time executor; allow a conservative 500 ms stale
    # feedback window. This is simulator-only, not a physical-arm profile.
    backend = replace(backend, required_mask=0x3F, feedback_timeout_ticks=500)
    permit = ab.require_real_output(profile, protocol, purpose="bench_loopback", confirm_no_robot=True)
    args.out.mkdir(parents=True, exist_ok=False)
    log = EventLog("ps", args.out/"ps_events.jsonl", meta={"simulation":True, "physical_arm":False,
          "pl":"actual FPGA", "executor":"CoppeliaSim via 3.3V UART", "classifier":"S4 VISION_SIM"})
    server = None
    initialized = False
    try:
        report = read_board_state(arm, plan, s4)
        (args.out/"BOARD_PREFLIGHT.json").write_text(json.dumps(report, indent=2)+"\n")
        print("PREFLIGHT: " + json.dumps(report), flush=True)
        require_fresh_overlay(report)
        initialized = True
        print("INIT: loading and committing S1 configuration", flush=True)
        arm.load_config(backend); arm.commit_config(); arm.clear_errors(); arm.clear_counters()
        arm.set_mode(ab.MODE_DRY_RUN, backend=backend.backend_sel)
        print("INIT: S2 HOME in DRY_RUN", flush=True)
        plan.select_source(pd.SOURCE_S2_PLANNER)
        home = tuple(tables.keypoints[cfg.home_kp])
        start = plan.last_delivered() or home
        n = 4
        while not pr.validate(pr.MoveParams(start, home, n, n//4, 1, cfg.period_cycles,
                             cfg.stall_cycles, cfg.vmax, cfg.amax), start).ok:
            n += 4
            if n > 4096:
                raise ValueError("Cannot seed HOME")
        require_planner_startable(plan)
        plan.run_move(pr.MoveParams(start, home, n, n//4, 1, cfg.period_cycles,
                                   cfg.stall_cycles, cfg.vmax, cfg.amax), timeout_s=n*.02+3)
        deadline = time.monotonic()+2
        while plan.status().planner_pending:
            if time.monotonic()>deadline:
                raise TimeoutError("HOME not accepted")
            time.sleep(.005)
        print("INIT: DRY_RUN -> OFF/idle -> LINE", flush=True)
        enter_simulator_line(arm, backend.backend_sel, permit)
        print("INIT: waiting for live simulator feedback", flush=True)
        deadline = time.monotonic()+3
        while not arm.status().feedback_valid:
            if arm.status().fault or time.monotonic()>deadline:
                raise RuntimeError("No simulator feedback; check executor, D5 and crossed UART")
            time.sleep(.01)
        snap = arm.snapshot()
        expected = list(map_joint_vector(home, backend.channel_maps)[0])
        if snap.valid_mask != 0x3F or any(abs(x-y)>4 for x,y in zip(snap.fb_dev, expected)):
            raise RuntimeError("Live scene is not at the configured HOME; run prepare_scene again")
        s4.load(cfg, tables, vision_sim=True)
        s4.command(m.Cmd.ENABLE)
        s4.wait_state({m.State.IDLE}, 1)
        port = AxiS4Port(s4)
        limits = MotionLimits(cfg.joint_min,cfg.joint_max,cfg.vmax,cfg.amax,
                              cfg.period_cycles,cfg.stall_cycles,"BENCH")
        service = (SimulatorPathService(port, ServiceConfig(home, tables.keypoints[cfg.predelivery_kp],
                    limits, 10000, link_timeout_s=5), pr, log=log, simulation_only=True,
                    fixture=True, confirm_no_robot=True) if args.mode=="B" else None)
        orchestrator = SimulatorOrchestrator(Mode.B if service else Mode.A, port, service, log=log)
        if service:
            server = TcpPathServer(orchestrator, host=args.host, port=args.port).start()
            print(f"READY: mode B listening {args.host}:{args.port}; connect pc_submit.py", flush=True)
            deadline = time.monotonic()+60
            while service.link.name != "SESSION":
                if time.monotonic()>deadline:
                    raise TimeoutError("PC did not establish session")
                time.sleep(.01)
        for iteration in range(args.repeat):
            before=set(orchestrator.records)
            obj=(args.object-1+iteration)%3+1
            s4.vision_sim(m.BACKGROUND); time.sleep(.05)
            s4.vision_sim(obj)
            log.emit('gesture_injected',object=obj,gesture='OBJECT',source='PS_TEST')
            print(f"TASK {iteration+1}/{args.repeat}: OBJECT_{obj} injected",flush=True)
            deadline=time.monotonic()+180
            palm_sent=False
            palm_notice=False
            while True:
                if not service: orchestrator.step()
                snap=s4.status()
                if snap.state==m.State.WAIT_PALM and not palm_notice:
                    print('WAIT_PALM: inject PALM to deliver or FIST to cancel',flush=True)
                    palm_notice=True
                if args.auto_palm and not palm_sent and snap.state==m.State.WAIT_PALM:
                    s4.vision_sim(m.PALM_READY,window_ok=True);palm_sent=True
                    log.emit('gesture_injected',object=obj,gesture='PALM_READY',source='PS_TEST')
                new=[v for k,v in orchestrator.records.items() if k not in before]
                if new and all(v.outcome is not None for v in new):break
                if snap.state==m.State.FAULT or time.monotonic()>deadline:
                    if not service:orchestrator.step()
                    raise RuntimeError(f'Task stopped: status={snap.raw:#x}, fault={s4.fault()}')
                time.sleep(.01)
            s4.wait_state({m.State.IDLE},2)
        if any(r.outcome.value not in ("DONE","TRAY_RETURN","RETURNED_TO_SLOT","CANCELLED_HOME")
               for r in orchestrator.records.values()):
            raise RuntimeError("Task did not finish an accepted normal/cancel exit")
        if arm.status().fault or arm.counters().fb_err:
            raise RuntimeError("S1 reported a fault or malformed feedback")
        # ARM.FB_SNAPSHOT is a write and is blocked while S4 owns motion.
        # Release before collecting it. Old board logs lacked the rejected
        # address, so this fixes a confirmed trigger without attributing all logs.
        if server: server.stop(); server=None
        s4.command(m.Cmd.RELEASE)
        s4.wait_state({m.State.OFF},1)
        result = {"result":"PASS", "simulation":True, "fpga":True,
                  "records":[asdict(r) for r in orchestrator.records.values()],
                  "s1_counters":asdict(arm.counters()), "feedback":asdict(arm.snapshot())}
        (args.out/"BOARD_RESULT.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
        print(json.dumps(result))
    except Exception as exc:
        (args.out/"FAILURE.json").write_text(json.dumps({"error":repr(exc),"simulation":True})+"\n")
        raise
    finally:
        if server: server.stop()
        if initialized:
            if s4.status().state == m.State.IDLE:
                s4.command(m.Cmd.RELEASE)
                s4.wait_state({m.State.OFF},1)
            if not s4.status().owner_s4:
                plan.estop()
                arm.stop()
            else:
                # Existing S4 fault handling inhibits motion and retains owner.
                # Do not issue writes that its PS window must reject.
                log.emit('cleanup_owner_held', action='remove_D5_then_reload_overlay')
        log.close()


if __name__ == "__main__":
    main()
