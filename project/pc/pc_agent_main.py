"""LEGACY colour-baseline S7 task agent. Neural entry: pc/neural_agent_main.py.

  python pc_agent_main.py --host <pynq> --port 50555 --recording <rgbd recording dir> --calibration <file>
                          --scene <scene json> [--log pc_events.jsonl] [--seconds 60]

Uses the RECORDED RGB-D device (the vendor camera adapter is BLOCKED_EXTERNAL_INPUT) and the IK
chosen by --ik: "unavailable" (default: every plan fails with IK_UNAVAILABLE -> CANCEL) or
"synthetic" (TEST DOUBLE, only for bench / DRY_RUN; the PS refuses it in LINE).
run_agent() is also used by the localhost test with any socket and device.
"""

from __future__ import annotations

import argparse
import socket
import sys
import time
from pathlib import Path

import phase3_link_protocol as lp


def run_agent(sock: socket.socket, agent, stop, poll_s: float = 0.005) -> None:
    """Pump one TCP connection through a PcTaskAgent until stop() is True or the link closes."""

    parser = lp.FrameParser()
    seq = [0]

    def send(msgs):
        for mtype, fields in msgs:
            seq[0] += 1
            sock.sendall(lp.encode(mtype, seq[0], fields))

    sock.settimeout(poll_s)
    send(agent.on_connect())
    try:
        while not stop():
            try:
                data = sock.recv(65536)
                if not data:
                    raise lp.LinkError("PS closed the connection")
                for msg in parser.feed(data):
                    send(agent.on_message(msg))
            except socket.timeout:
                pass
            send(agent.step())
    except (lp.LinkError, OSError) as exc:
        agent.on_disconnect(str(exc))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--legacy-color-baseline', action='store_true',
                    help='Explicitly opt in to the historical HSV comparison, excluded from neural acceptance')
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, default=50555)
    ap.add_argument("--recording", type=Path, required=True)
    ap.add_argument("--calibration", type=Path, required=True)
    ap.add_argument("--scene", type=Path, required=True)
    ap.add_argument("--ik", choices=("unavailable", "synthetic"), default="unavailable")
    ap.add_argument("--log", type=Path, default=None)
    ap.add_argument("--seconds", type=float, default=0.0)
    args = ap.parse_args()
    if not args.legacy_color_baseline:
        ap.error('HSV baseline requires --legacy-color-baseline. Use pc/neural_agent_main.py for neural perception.')
    import planner_p2p_reference as pr
    from calibration import CalibrationSet
    from detector import ColorBlobDetector
    from ik_interface import SyntheticIK, UnavailableIK
    from pc_task_agent import AgentConfig, PcTaskAgent
    from phase3_event_log import EventLog
    from rgbd_device import RecordedRGBDDevice
    from scene_config import SceneConfig
    from scene_pipeline import ScenePipeline
    dev = RecordedRGBDDevice(args.recording)
    dev.open()
    pipe = ScenePipeline(dev, CalibrationSet.load(args.calibration), SceneConfig.load(args.scene), ColorBlobDetector(),
                         SyntheticIK() if args.ik == "synthetic" else UnavailableIK(), pr)
    agent = PcTaskAgent(pipe, AgentConfig(), EventLog("pc", args.log))
    sock = socket.create_connection((args.host, args.port), timeout=3)
    t0 = time.monotonic()
    run_agent(sock, agent, stop=lambda: bool(args.seconds) and time.monotonic() - t0 > args.seconds)
    sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
