"""Replan a recorded B source offline, including the full family and return path."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pc.mode_ab.runtime import plan_delivery,plan_restock


def main(session,out):
    out.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    log=session/'tasks.jsonl'
    event=next(json.loads(line) for line in log.read_text('utf-8').splitlines()
               if json.loads(line).get('event')=='planning_started')
    task=event['task'];name=task['class_name'];frame=task['frame']
    row=next(r for r in frame['localizations'] if r['class_name']==name and r.get('geometry_gate_pass'))
    centre=row['object_centre_desktop_xyz_mm'];yaw=row['top']['long_axis_yaw_mod180_deg']
    delivery=plan_delivery(out/'delivery',name,centre,yaw,frame)
    native=Path(delivery['folder'])/'native.json';origin_file=out/'offline_origin.json'
    origin=dict(task_id='OFFLINE_REPLAY_NO_HARDWARE_COMPLETION',origin_kind=delivery['origin_kind'],
        source_centre_mm=centre,source_yaw_deg=yaw,native_file=str(native),
        native_sha256=hashlib.sha256(native.read_bytes()).hexdigest(),origin_file=str(origin_file),
        evidence_kind='SYNTHETIC_ORIGIN_FOR_OFFLINE_RETURN_GEOMETRY_ONLY')
    origin_file.write_text(json.dumps(origin,indent=2)+'\n')
    restock=plan_restock(out/'restock',origin)
    result=dict(passed=True,source_log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),class_name=name,
        delivery_geometry=delivery['compiled'].get('geometry'),
        delivery_fifo=len(delivery['compiled']['fifo']),delivery_segments=len(delivery['compiled'].get('segments',[])),
        family=delivery['compiled'].get('fresh_handover_family'),restock_geometry=restock['compiled']['geometry'],
        restock_fifo=len(restock['compiled']['fifo']),seconds=time.monotonic()-started,
        source_hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['pc/mode_ab/motion.py','pc/mode_ab/runtime.py']},
        hardware_access=False,physical_success=None,physical_test='NOT_RUN')
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.session,a.out)
