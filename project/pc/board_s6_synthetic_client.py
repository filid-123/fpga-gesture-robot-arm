"""No-arm S6 board replay using synthetic RGB-D and synthetic IK.

Start after the PYNQ path service; run the board OBJECT trigger separately.
This validates the TCP/path/PL chain, not real perception or arm kinematics.
"""

from __future__ import annotations

import argparse
import json

import phase3_link_protocol as lp
import planner_p2p_reference as pr
import synthetic_scene as ss
from detector import ColorBlobDetector
from ik_interface import SyntheticIK
from pc_link_client import PcLinkClient
from pick_pipeline import PickPipeline, TargetRequest


def pipeline() -> PickPipeline:
    cubes = [ss.CubePose(1, 250.0, 80.0), ss.CubePose(2, 350.0, -60.0),
             ss.CubePose(3, 300.0, 120.0)]
    dev = ss.SyntheticRGBDDevice([ss.render_frame(cubes, seed=20260926)])
    dev.open()
    return PickPipeline(dev, ss.synthetic_calibration(), ss.synthetic_scene_config(),
                        ColorBlobDetector(), SyntheticIK(), pr)


def run(host: str, port: int, mode: str) -> dict:
    client = PcLinkClient(host, port).connect()
    try:
        client.hello()
        if client.limits is None or client.limits.status != "BENCH" or client.limits.period_cycles != 2_000_000:
            raise RuntimeError("PS did not publish the S6 board BENCH limits")
        msg = client.wait_for(lambda m: m.type == lp.MsgType.TARGET_REQUEST, 30.0)
        req = TargetRequest.from_message(msg)
        if mode == "drop_waiting":
            return {"result": "PASS", "task_id": req.task_id, "action": "disconnect before PATH_SUBMIT"}
        plan, rep = pipeline().handle(req, client.limits)
        if plan is None:
            raise RuntimeError(f"synthetic pipeline failed: {rep.outcome}")
        client.submit(plan)
        res = client.wait_for(lambda m: m.type == lp.MsgType.PATH_RESULT and
                              m.fields[0] == req.task_id, 10.0)
        result = lp.PathResult(res.fields[1])
        if result is not lp.PathResult.COMMITTED:
            raise RuntimeError(f"PATH_RESULT {result.name}, problem {res.fields[2]}")
        if mode == "drop_committed":
            return {"result": "PASS", "task_id": req.task_id,
                    "action": "disconnect after COMMITTED", "segments": len(plan.segments)}
        done = client.status_until(req.task_id, {lp.TaskState.DONE, lp.TaskState.CANCELLED,
                                                 lp.TaskState.FAULT}, 40.0)
        if lp.TaskState(done.fields[1]) is not lp.TaskState.DONE:
            raise RuntimeError(f"task ended {lp.TaskState(done.fields[1]).name}")
        client.submit(plan)
        duplicate = client.wait_for(lambda m: m.type == lp.MsgType.PATH_RESULT and
                                    m.fields[0] == req.task_id, 5.0)
        if lp.PathResult(duplicate.fields[1]) is not lp.PathResult.DUPLICATE:
            raise RuntimeError("second PATH_SUBMIT was not rejected as DUPLICATE")
        return {"result": "PASS", "task_id": req.task_id, "object": req.object_id,
                "segments": len(plan.segments), "path_result": result.name,
                "terminal": "DONE", "duplicate": "DUPLICATE"}
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=50555)
    parser.add_argument("--mode", choices=("normal", "drop_waiting", "drop_committed"), default="normal")
    args = parser.parse_args()
    print(json.dumps(run(args.host, args.port, args.mode), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
