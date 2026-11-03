"""Send one complete simulator IK path to a PYNQ simulator-only service."""
import argparse
from dataclasses import replace
from pathlib import Path
import bootstrap
import phase3_link_protocol as lp
import s4_task_reference as m
from pc_link_client import PcLinkClient
from phase3_event_log import EventLog
from sim_config import load
from run_closed_loop import plan_for


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", required=True)
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--repeat",type=int,choices=[1,2,3],default=1)
    p.add_argument("--log", type=Path, required=True)
    args = p.parse_args()
    data,cfg,tables = load(args.config)
    paths = {int(k):[m.Segment(tuple(s["target"]),s["n"],s["na"],s["profile"],s["flags"])
                    for s in v] for k,v in data["paths"].items()}
    args.log.parent.mkdir(parents=True,exist_ok=True)
    log = EventLog("pc",args.log,meta={"simulation":True,"physical_arm":False})
    client = PcLinkClient(args.host,args.port,log=log,link_timeout_s=5)
    try:
        client.connect(); client.hello()
        for iteration in range(args.repeat):
            request = client.wait_for(lambda r:r.type==lp.MsgType.TARGET_REQUEST,60)
            tid,obj = request.fields[:2]
            plan,limits = plan_for(tid,obj,paths,cfg,tables)
            if client.limits != limits:
                raise RuntimeError("PC and board limits differ")
            client.submit(plan)
            reply = client.wait_for(lambda r:r.type==lp.MsgType.PATH_RESULT,10)
            if lp.PathResult(reply.fields[1]) != lp.PathResult.COMMITTED:
                raise RuntimeError(f"Commit refused: {reply.fields}")
            print("COMMITTED: PL owns path; inject PALM / FIST with board_gesture.py",flush=True)
            print(client.status_until(tid,{lp.TaskState.DONE,lp.TaskState.CANCELLED,lp.TaskState.FAULT},180))
    finally:
        client.close(); log.close()


if __name__ == "__main__":
    main()
