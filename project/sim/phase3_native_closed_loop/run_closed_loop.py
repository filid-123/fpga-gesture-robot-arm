"""Live Python S4/S2/S1 -> virtual UART -> CoppeliaSim -> feedback -> S8.

The S8 TCP service and contracts are frozen originals. Python reference models
stand in for PL; injected stable classes stand in for the pending 7-class model.
Neither simulated IK nor the bench limits are approved for a physical arm.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import bootstrap
import planner_p2p_reference as pr
import phase3_link_protocol as lp
import phase3_path_contract as pc
import s4_task_reference as m
from s4_port import ModelS4Port
from ps_path_service import PathServiceCore, ServiceConfig, TcpPathServer
from task_orchestrator import TaskOrchestrator, Mode
from orchestrator import SimulatorOrchestrator
from pc_link_client import PcLinkClient
from phase3_event_log import EventLog
from arm_backend import ArmBackendPlModel
from executor import CoppeliaScene, ExecutorServer, FixtureCodec, VirtualUartClient, q16
from roarm_controller import JOINT_LIMITS_RAD
from ik_position_test import solve_position_ik

SCHEMA = "gesture.phase3.coppelia_closed_loop.v1"
PERIOD_S = 0.02


def distance(a, b):
    return math.sqrt(sum((x-y)**2 for x, y in zip(a, b)))


class FeedbackTaskModel(m.S4TaskModel):
    @property
    def feedback_checks(self):
        # Virtual backend remains BENCH/DRY_RUN for the original physical-output
        # gate. Only this simulation subclass enables the original arrival and
        # communication monitors against its genuine virtual-device feedback.
        return True


class MotionPlant(m.Plant):
    def __init__(self, cfg, client, codec, log):
        super().__init__(s1_mode=m.S1_MODE_DRY_RUN, home=cfg._home if hasattr(cfg, "_home") else (0,)*6,
                         prescale=cfg.tick_prescale, validate_fn=m.planner_validate_fn(pr))
        self.permission = self.feedback_valid = True
        self.client, self.codec, self.log = client, codec, log
        self.backend = ArmBackendPlModel(codec.config)
        self.samples = []
        self.index = 0
        self.feedback = None
        self.target = self.last
        self.frames = 0

    def move(self, target, n, na, profile, cfg):
        accepted = super().move(target, n, na, profile, cfg)
        if accepted and self.pl_state == m.PL_RUN:
            self.target = tuple(target)
            move = pr.MoveParams(self.last, self.target, n, na, profile, cfg.period_cycles,
                                 cfg.stall_cycles, cfg.vmax, cfg.amax)
            self.samples, self.index = pr.samples(move), 0
            self.log.emit("planner_move", target=self.target, n=n, na=na, profile=profile)
        return accepted

    def command(self, name):
        if name == "CLEAR":
            if self.pl_state in (m.PL_RUN, m.PL_VALIDATE):
                return False
            self.samples = []
            self.pl_state, self.pl_error, self._move = m.PL_IDLE, 0, None
            # Preserve the last actually transmitted sample on partial cancel.
            return True
        return super().command(name)

    def tick(self):
        if self.pl_state == m.PL_RUN and self.index < len(self.samples):
            sample = self.samples[self.index]
            frame = self.backend.process_sample(sample, permitted=self.permission)
            if frame.fault:
                self.s1_fault = True
                return
            if not frame.accepted:
                return
            feedback = self.client.exchange(frame.cmd + frame.req)
            self.last, self.last_valid = tuple(sample), True
            self.index += 1
            self.frames += 1
            self.log.emit("sample_accepted", index=self.index, target=sample,
                          feedback=feedback, bytes=len(frame.cmd + frame.req))
            if self.index == len(self.samples):
                self.pl_state = m.PL_DONE
        else:
            feedback = self.client.exchange(b'{"type":7}\n')
        if feedback is not None:
            self.feedback = tuple(feedback)
            self.fb_seq = (self.fb_seq + 1) & 0xFFFF
            self.feedback_valid = True
            self.arrival = sum((1 << i) for i, (x, target, j) in enumerate(
                zip(self.feedback, self.target, self.codec.profile.joints))
                if abs(x-target/65536) <= j.arrival_tolerance_rad)


def build_geometry(scene, codec):
    original = scene.controller.get_joint_positions()
    home_rad = (0.0,1.2,0.5,0.0,0.0,1.5)
    scene.controller.set_joint_positions(home_rad)
    tcp = tuple(scene.sim.getObjectPosition(scene.descriptor["tcp"], scene.sim.handle_world))
    ik = scene.controller.client.require("simIK")
    # Imported base mesh has a translated origin; use its actual lower bound.
    import itertools
    base=scene.sim.getObject('/base_link_visual')
    mat=scene.sim.getObjectMatrix(base,scene.sim.handle_world)
    bounds=[(scene.sim.getObjectFloatParam(base,getattr(scene.sim,'objfloatparam_objbbox_min_'+axis)),
             scene.sim.getObjectFloatParam(base,getattr(scene.sim,'objfloatparam_objbbox_max_'+axis))) for axis in 'xyz']
    support_z=min(sum(mat[8+i]*v[i] for i in range(3))+mat[11] for v in itertools.product(*bounds))
    center_z=support_z+0.008
    pick=[(0.25,0.0,center_z),(0.25,-0.045,center_z),(0.25,0.045,center_z)]
    delivery=(0.32,0.09,center_z)
    tray=(0.22,-0.10,center_z)
    scene.add_support(support_z)
    above = lambda p: (p[0], p[1], p[2]+0.03)
    def pose(p, grip):
        solution = solve_position_ik(scene.controller, ik, p)
        return tuple(q16(x) for x in solution.joint_positions_rad[:5]) + (q16(grip),)
    home = tuple(q16(x) for x in home_rad)
    pre = pose(above(delivery), 0)
    vmax = tuple(math.floor(j.max_velocity_rad_s*PERIOD_S*65536) for j in codec.profile.joints)
    amax = tuple(math.floor(j.max_accel_rad_s2*PERIOD_S**2*2**32) for j in codec.profile.joints)
    cfg = m.S4Config(tick_prescale=2_000_000, period_cycles=2_000_000,
                     stall_cycles=50_000_000, joint_min=tuple(q16(x[0]) for x in JOINT_LIMITS_RAD),
                     joint_max=tuple(q16(x[1]) for x in JOINT_LIMITS_RAD), vmax=vmax, amax=amax,
                     t_palm_hold=5, t_palm_wait=100, t_arrival=12, t_comm=6,
                     t_path_wait=100000, blind_periods=2048, move_margin=100)
    tables = m.S4Tables()
    tables.keypoints[0], tables.keypoints[1] = home, pre
    cursor, kp_cursor = 0, 2
    def path(start, targets):
        nonlocal cursor, kp_cursor
        first = cursor
        out = []
        for target, flags in targets:
            n = 16
            while n <= 4096:
                move = pr.MoveParams(start, target, n, n//4, 1, cfg.period_cycles,
                                     cfg.stall_cycles, cfg.vmax, cfg.amax)
                if pr.validate(move, start).ok:
                    break
                n += 4
            if n > 4096 or kp_cursor >= 64 or cursor >= 64:
                raise ValueError("Cannot build a bounded S4/S2 simulated path")
            kp = 0 if target == home else 1 if target == pre else kp_cursor
            tables.keypoints[kp] = target
            tables.segments[cursor] = (kp, n, n//4, 1, flags)
            out.append(m.Segment(target, n, n//4, 1, flags))
            start = target
            cursor, kp_cursor = cursor+1, kp_cursor+1
        return (first, cursor-first), out
    outs = {}
    for obj, p in enumerate(pick, 1):
        ap, ap_segs = path(home, [(pose(above(p), 1.5), m.F_STOP_ON_CANCEL),
                                  (pose(p, 1.5), m.F_STOP_ON_CANCEL)])
        tables.approach[obj] = ap
        gr, gr_segs = path(ap_segs[-1].target, [(pose(p, 0), m.F_GRASP)])
        tables.grasp[obj] = gr
        lift, lift_segs = path(gr_segs[-1].target,
                              [(pose(above(p), 0), m.F_STOP_ON_CANCEL), (pre, m.F_STOP_ON_CANCEL)])
        tables.lift[obj] = lift
        outs[obj] = ap_segs + gr_segs + lift_segs
    tables.deliver, ds = path(pre, [(pose(delivery, 0), m.F_STOP_ON_CANCEL)])
    tables.release, rs = path(ds[-1].target, [(pose(delivery, 1.5), 0)])
    tables.retreat, _ = path(rs[-1].target, [(pose(above(delivery), 1.5), 0), (home, 0)])
    tables.tray, _ = path(pre, [(pose(above(tray), 0), 0), (pose(tray, 0), 0),
                               (pose(tray, 1.5), 0), (pose(above(tray), 1.5), 0), (home, 0)])
    scene.add_payloads(pick)
    return cfg, tables, outs, {"support_z_m":support_z,"payload_side_m":0.016,"home_rad": home_rad, "pick_m": pick,
                              "delivery_m": delivery, "tray_m": tray, "pre_delivery_q16": pre}


def plan_for(task_id, obj, outs, cfg, tables):
    lim = pc.MotionLimits(cfg.joint_min, cfg.joint_max, cfg.vmax, cfg.amax,
                          cfg.period_cycles, cfg.stall_cycles, "BENCH")
    segs = tuple(pc.Segment(tuple(s.target), s.n, s.na, s.profile, s.flags) for s in outs[obj])
    samples, errors = pc.interpolate(segs, tuple(tables.keypoints[0]), lim, pr)
    if errors:
        raise ValueError(errors)
    plan = pc.PathPlan(task_id, obj, tuple(tables.keypoints[0]), segs, 0, pc.IKKind.SYNTHETIC,
                       pc.digest_of(samples))
    report = pc.check(plan, lim, tables.keypoints[0], tables.keypoints[1], pr)
    if not report.ok:
        raise ValueError(report.problems)
    return plan, lim


def run_case(scene, codec, geometry, cfg, tables, outs, case, out, realtime=False):
    from dataclasses import replace
    mode, obj, scenario = case
    out.mkdir()
    meta = {"simulation": True, "physical_arm": False, "classifier": "injected_stable_class",
            "executor": "live CoppeliaSim 4.10 kinematic", "realtime_pacing": realtime,
            "pl": "Python S4/S2/S1 reference; no FPGA in this run"}
    logs = {host: EventLog(host, out/(host+"_events.jsonl"), meta=meta)
            for host in ("ps", "pc", "sim")}
    scene.reset(geometry["home_rad"], geometry["pick_m"])
    executor = ExecutorServer(scene.descriptor, codec, logs["sim"]).start()
    uart = VirtualUartClient(executor.address, codec)
    plant = MotionPlant(cfg, uart, codec, logs["ps"])
    plant.last = plant.target = tuple(tables.keypoints[0])
    cfg_case = replace(cfg, mode_b=mode == "B", hold_policy=mode == "B", tray_exit=mode == "B")
    model = FeedbackTaskModel(cfg_case, tables, plant)
    port = ModelS4Port(model)
    plant.tick()  # Initial live feedback; no target-echo precondition.
    if plant.feedback is None:
        raise RuntimeError("No initial Coppelia feedback")
    if port.command(m.Cmd.ENABLE) != m.CmdReject.ACCEPTED:
        raise RuntimeError("S4 ENABLE refused")
    plan, limits = plan_for(1, obj, outs, cfg, tables)
    service = None
    if mode == "B":
        service = PathServiceCore(port, ServiceConfig(tuple(tables.keypoints[0]),
                                  tuple(tables.keypoints[1]), limits, 10000,
                                  link_timeout_s=5), pr, log=logs["ps"])
    orchestrator = SimulatorOrchestrator(Mode.B if mode == "B" else Mode.A, port, service, log=logs["ps"])
    injected = {"selected": False, "palm": False, "fist": False, "silence": False}
    error = []
    next_tick = [time.perf_counter()]
    if scenario == "arrival_fault":
        executor.endpoint.blocked_joint = 2  # shoulder, measured pose stays behind target
    def step():
        if realtime and time.perf_counter() < next_tick[0]:
            return
        next_tick[0] = time.perf_counter() + PERIOD_S
        try:
            with port.lock:
                if scenario == "cancel" and model.holding and model.phase == m.Phase.OUT and not injected["fist"]:
                    model.vision(True, m.FIST_CANCEL, changed=True)
                    logs["ps"].emit("synthetic_gesture", label="FIST_CANCEL")
                    injected["fist"] = True
                elif model.state == m.State.WAIT_PALM and scenario != "palm_timeout":
                    model.vision(True, m.PALM_READY, changed=not injected["palm"], palm_window_ok=True)
                    injected["palm"] = True
                if scenario == "feedback_loss" and model.holding and not injected["silence"]:
                    executor.endpoint.suppress_feedback = True
                    injected["silence"] = True
                port.advance(1)
        except Exception as exc:
            error.append(repr(exc))
            server.stop_event.set()
    server = TcpPathServer(orchestrator, board_step=step, loop_period_s=0.0002).start()
    client = None
    duplicate = None
    started = time.perf_counter()
    try:
        if mode == "B":
            client = PcLinkClient(*server.address, log=logs["pc"], link_timeout_s=5).connect()
            client.hello()
        with port.lock:
            model.vision(True, m.BACKGROUND, changed=True)
            port.advance(1)
            model.vision(True, obj, changed=True)
            port.advance(1)
            logs["ps"].emit("synthetic_gesture", label=f"OBJECT_{obj}")
            injected["selected"] = True
        if client is not None:
            req = client.wait_for(lambda msg: msg.type == lp.MsgType.TARGET_REQUEST, 10)
            tid = req.fields[0]
            plan, _ = plan_for(tid, obj, outs, cfg, tables)
            logs["pc"].emit("target_request", tid, object=obj)
            logs["pc"].emit("pipeline", tid, outcome="SIMULATION_PLAN",
                           ik="CoppeliaSim numerical position IK, not physical calibration")
            client.submit(plan)
            committed = client.wait_for(lambda msg: msg.type == lp.MsgType.PATH_RESULT, 10)
            if lp.PathResult(committed.fields[1]) != lp.PathResult.COMMITTED:
                raise RuntimeError(f"Path commit refused: {committed.fields}")
            terminal = client.status_until(tid, {lp.TaskState.DONE, lp.TaskState.CANCELLED, lp.TaskState.FAULT},
                                           180 if realtime else 60)
            if scenario == "normal":
                client.submit(plan)
                dup = client.wait_for(lambda msg: msg.type == lp.MsgType.PATH_RESULT, 5)
                duplicate = lp.PathResult(dup.fields[1]).name
        else:
            deadline = time.monotonic() + (180 if realtime else 60)
            while not orchestrator.records or all(r.outcome is None for r in orchestrator.records.values()):
                if error or executor.error:
                    raise RuntimeError(error or executor.error)
                if time.monotonic() > deadline:
                    raise TimeoutError(f"Task stalled: {model.state.name}, {model.phase.name}, {model.fault.name}")
                time.sleep(0.002)
        # Server emits terminal STATUS before the orchestrator closes its record.
        deadline = time.monotonic()+2
        while any(r.outcome is None for r in orchestrator.records.values()) and time.monotonic()<deadline:
            time.sleep(0.002)
        record = next(iter(orchestrator.records.values()))
        observed = executor.endpoint.observations[-1]
        selected_position = observed["objects"][obj-1]
        expected = (geometry["tray_m"] if mode == "B" else geometry["pick_m"][obj-1])
        if scenario == "normal":
            expected = geometry["delivery_m"]
        endpoint_error = distance(selected_position, expected)
        grasp_seen = any(o.get("event") == "grasp" and o.get("attached") == obj for o in executor.endpoint.observations)
        release_seen = any(o.get("event") == "release" for o in executor.endpoint.observations)
        home_error = max(abs(x-y) for x, y in zip(observed["joints"], geometry["home_rad"]))
        expected_outcome = "DONE" if scenario == "normal" else "TRAY_RETURN" if scenario == "cancel" and mode == "B" else "RETURNED_TO_SLOT"
        checks = {"no_executor_error": not executor.error and not error, "live_feedback": plant.fb_seq > 1,
                  "model_terminal": record.outcome is not None}
        if scenario in ("arrival_fault", "feedback_loss"):
            expected_fault = m.Fault.ARRIVAL_TIMEOUT if scenario == "arrival_fault" else m.Fault.COMM_TIMEOUT
            checks.update(fault=record.outcome.value == "FAULT" and model.fault == expected_fault,
                          no_release=not release_seen, motion_stopped=plant.pl_state == m.PL_ESTOP)
            if scenario == "arrival_fault":
                checks["measured_mismatch"] = max(abs(x-y/65536) for x,y in zip(plant.feedback, plant.target)) > 0.01
        else:
            checks.update(outcome=record.outcome.value == expected_outcome,
                          payload_position=endpoint_error <= 0.002, detached=observed["attached"] == 0,
                          grasp_observed=grasp_seen, release_observed=release_seen, home=home_error <= 0.00035)
            if scenario == "normal" and mode == "B":
                checks["duplicate_rejected"] = duplicate == "DUPLICATE"
        result = {"schema": SCHEMA, "mode": mode, "object": obj, "scenario": scenario,
                  "simulation": True, "passed": all(checks.values()), "checks": checks,
                  "outcome": record.outcome.value, "fault": model.fault.name,
                  "frames": plant.frames, "feedback_records": plant.fb_seq,
                  "payload_error_m": endpoint_error, "home_error_rad": home_error,
                  "observed_payload_m": selected_position, "grasp_seen": grasp_seen,
                  "release_seen": release_seen, "duplicate": duplicate,
                  "wall_seconds": time.perf_counter()-started, "logical_seconds": model.tick_count*PERIOD_S,
                  "executor_rpc_rtt_max_ms": max(uart.roundtrips_ms, default=0),
                  "injected": injected, "model_actions": model.actions}
        (out/"RESULT.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
        return result
    finally:
        if client is not None:
            client.close()
        server.stop()
        uart.close()
        executor.stop()
        for log in logs.values():
            log.close()


def run_metrics(case_dir):
    tools = bootstrap.HERE/"metrics_tools/src/tools"
    bundle = case_dir/"s8_bundle"
    commands = [[sys.executable, str(tools/"collect_run.py"), "--out", str(bundle),
                 "--run", str(case_dir/"ps_events.jsonl")+","+str(case_dir/"pc_events.jsonl"),
                 "--note", "SIMULATION: Python PL reference and live stopped-state CoppeliaSim; injected classes"],
                [sys.executable, str(tools/"compute_metrics.py"), "--bundle", str(bundle), "--out", str(bundle/"metrics.json")],
                [sys.executable, str(tools/"render_report.py"), "--metrics", str(bundle/"metrics.json"), "--out", str(bundle/"REPORT.md")]]
    for cmd in commands:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f"S8 failed: {result.stdout} {result.stderr}")
    metrics = json.loads((bundle/"metrics.json").read_text(encoding="utf-8"))
    if metrics.get("data_kind") != "SIMULATION":
        raise RuntimeError("S8 incorrectly classified simulation as hardware measurement")
    return {"data_kind": metrics["data_kind"], "schema_problems": metrics["bundle"]["schema_problems"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--realtime", action="store_true")
    parser.add_argument("--case", choices=["all", "A1_normal", "B1_normal"], default="all")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output directory exists; choose a new run directory")
    args.out.mkdir(parents=True)
    codec = FixtureCodec()
    scene = CoppeliaScene()
    results = []
    try:
        cfg, tables, outs, geometry = build_geometry(scene, codec)
        configuration = {"schema": SCHEMA, "simulation_only": True, "fixture": True,
                         "config": asdict(cfg), "tables": asdict(tables), "geometry": geometry,
                         "paths": {str(k): [asdict(s) for s in v] for k,v in outs.items()}}
        (args.out/"SIMULATION_CONFIG.json").write_text(json.dumps(configuration, indent=2)+"\n", encoding="utf-8")
        cases = [(mode, obj, "normal") for mode in ("A", "B") for obj in (1,2,3)]
        cases += [("A",1,"cancel"), ("B",2,"cancel"), ("A",1,"palm_timeout"),
                  ("A",1,"feedback_loss"), ("A",1,"arrival_fault")]
        if args.case != "all":
            cases = [(args.case[0], int(args.case[1]), "normal")]
        for case in cases:
            case_name = f"{case[0]}{case[1]}_{case[2]}"
            result = run_case(scene, codec, geometry, cfg, tables, outs, case,
                              args.out/case_name, args.realtime)
            result["s8"] = run_metrics(args.out/case_name)
            results.append(result)
            print(json.dumps({"case":case_name, "passed":result["passed"], "outcome":result["outcome"],
                              "fault":result["fault"], "frames":result["frames"], "s8":result["s8"]}), flush=True)
    except Exception as error:
        (args.out/"FAILURE.json").write_text(json.dumps({"schema":SCHEMA, "simulation":True,
            "error":repr(error), "completed_cases":results}, indent=2)+"\n", encoding="utf-8")
        raise
    finally:
        scene.close()
    summary = {"schema":SCHEMA, "version":"0.1.0", "simulation":True,
               "passed":len(results)>0 and all(r["passed"] for r in results), "cases":results,
               "limitations":["Python reference models replace PL", "injected stable classes; 7-class model pending",
                              "position-only simulator IK", "geometric grasp attachment, no contact dynamics",
                              "no board/FPGA/physical-arm test in this run"]}
    (args.out/"SUMMARY.json").write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
