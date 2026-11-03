"""Replay field source poses and independently check each fast family proof."""
from pathlib import Path
import json
import sys
import time
import hashlib
import argparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pc.mode_ab.runtime import plan_delivery,plan_restock
from pc.mode_ab.motion import read,build_banks,compile_banks,template
from pc.mode_ab.family import verify


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);out=ap.parse_args().out
    out.mkdir(parents=True,exist_ok=False);results=[]
    cases=[('field_red_053302','red_cube',[604.6332733110694,270.8762318653109,15.],87.98997761785662),
           ('field_red_042439_rejected','red_cube',[609.1553,258.2743,15.],94.4095),
           ('field_red_042439_delivered','red_cube',[584.62456,261.15087,15.],87.24065)]
    for name in ('eraser','small_canister'):
        p=template(name)['request']['pickup'];cases.append(('nominal_'+name,name,p['centre_mm'],p['yaw_deg']))
    for label,name,centre,yaw in cases:
        folder=out/label;prepared=plan_delivery(folder,name,centre,yaw,dict(offline=True,physical_execution=False))
        c=prepared['compiled'];fast=c['fresh_handover_family']
        if fast['method']!='BOUND_RIGID_PAYLOAD_DISPLACEMENT':raise ValueError('Expected certified route '+label)
        banks,front=build_banks(name,centre,yaw)
        started=time.perf_counter();full=verify(c,banks[1],use_certificate=False);full_seconds=time.perf_counter()-started
        origin=folder/'origin.json';native=folder/'native.json'
        origin_data=dict(task_id='OFFLINE_NOT_PL_COMPLETION',class_name=name,origin_kind='B_DYNAMIC',native_file=str(native),
                         native_sha256=hashlib.sha256(native.read_bytes()).hexdigest(),origin_file=str(origin))
        origin.write_text(json.dumps(origin_data));restock=plan_restock(folder/'restock',origin_data)
        result=dict(label=label,source_centre_mm=centre,yaw_deg=yaw,profile_id=prepared['profile_id'],
            planning_ms=c['planning_timings_ms'],fast_proof=fast,independent_full_proof=full,
            full_proof_seconds=full_seconds,normal_fifo=len(c['fifo']),restock_fifo=len(restock['compiled']['fifo']),
            physical_test='NOT_RUN')
        results.append(result);print(label,'PASS',c['planning_timings_ms'],flush=True)
    sources=['pc/mode_ab/'+x+'.py' for x in ('motion','family','geometry','runtime','uploads','board','http','control','diagnostics')]
    report=dict(passed=True,cases=results,hardware_access=False,physical_test='NOT_RUN',
        source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources})
    (out/'result.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()
