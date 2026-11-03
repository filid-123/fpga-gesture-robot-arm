"""Production Q16/quintic handover family, retargeting and source-relative checks."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import numpy as np
from pc.mode_ab.motion import template,build_banks,compile_banks,home,read
from pc.mode_ab.geometry import validate
from prepare_mode_b_loaded_route import objects
from mode_a_upgrade_profile import scalar,align_steps


def samples(a,b,n):
    return [[y if k==n else x+(-1 if y<x else 1)*((abs(y-x)*scalar(k,n)+(1<<31))>>32) for x,y in zip(a,b)] for k in range(n+1)]


def mixed(c,step):
    lo=0 if step<32 else 1;w=step-lo*32
    return [[(a*(32-w)+b*w+16)//32 for a,b in zip(x,y)] for x,y in zip(c['keypoint_banks'][lo],c['keypoint_banks'][lo+1])]


def family(c,banks):
    checked=0;minimum=float('inf');retarget=0
    for step in range(65):
        p=deepcopy(banks[1]);points=mixed(c,step);r=c['descriptors'];di=r['deliver'][0]+r['deliver'][1]-1
        place=np.array(points[c['segments'][di][0]])/65536
        robot,_=objects(p);p['released_object_pose']=(robot.fk(np.r_[place[:5],0.])@np.array(p['tcp_from_object'])).tolist()
        cache=objects(p);current=points[c['predelivery_kp']]
        for i,(kp,n,na,profile,flags) in enumerate(c['segments']):
            target=points[kp];qs=np.array(samples(current,target,n))/65536
            carrying=i<r['release'][0]
            stats=validate(p,qs,carrying,'HANDOVER_PLACE' if carrying else 'HAND_CLEAR',cache)
            wire=validate(p,np.round(qs,4),carrying,'HANDOVER_PLACE_WIRE' if carrying else 'HAND_CLEAR_WIRE',cache)
            checked+=stats['samples_checked']+wire['samples_checked'];minimum=min(minimum,stats['minimum_model_clearance_mm'],wire['minimum_model_clearance_mm'])
            current=target
        assert current==[round(v*65536) for v in home('B')]
    # Every pair of accepted PRE targets, both directions, with the actual
    # bounded quintic alignment timing. Mid-move braking remains the existing A
    # controller; this tests the complete endpoint-to-endpoint target family.
    p=deepcopy(banks[1]);cache=objects(p);batch=[]
    def flush():
        nonlocal retarget,minimum,batch
        if batch:
            st=validate(p,np.array(batch)/65536,True,'HANDOVER_ALIGN',cache)
            retarget+=st['samples_checked'];minimum=min(minimum,st['minimum_model_clearance_mm']);batch=[]
    for a in range(65):
        qa=mixed(c,a)[c['predelivery_kp']]
        for b in range(65):
            if a==b:continue
            qb=mixed(c,b)[c['predelivery_kp']];n=align_steps(max(abs(x-y) for x,y in zip(qa,qb)))
            batch.extend(samples(qa,qb,n))
            if len(batch)>5000:flush()
    flush()
    return dict(handover_steps=65,ordered_retarget_pairs=4160,trajectory_model_samples=checked,
                retarget_model_samples=retarget,minimum_clearance_mm=minimum)


def main(out):
    out.mkdir(parents=True,exist_ok=False);results=[]
    for name in ('red_cube','eraser','small_canister'):
        p=template(name);t=time.perf_counter()
        banks,front=build_banks(name,p['request']['pickup']['centre_mm'],p['request']['pickup']['yaw_deg'])
        c=compile_banks(banks,front);(out/(name+'_compiled.json')).write_text(json.dumps(c))
        stats=family(c,banks)
        variants=[]
        for delta,yaw_delta in [([5,0,0],3),([-5,3,0],-3)]:
            centre=(np.array(p['request']['pickup']['centre_mm'])+delta).tolist()
            b,f=build_banks(name,centre,p['request']['pickup']['yaw_deg']+yaw_delta)
            cc=compile_banks(b,f);variants.append(dict(delta_mm=delta,yaw_delta_deg=yaw_delta,
                normal_fifo=len(cc['fifo']),geometry=cc['geometry']))
        result=dict(class_name=name,family=stats,local_transfer_variants=variants,
                    compilation_s=time.perf_counter()-t,physical_test='NOT_RUN')
        results.append(result);(out/'progress.json').write_text(json.dumps(results,indent=2));print(name,stats,flush=True)
    (out/'result.json').write_text(json.dumps(dict(passed=True,results=results,
        source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'pc/mode_ab/motion.py',ROOT/'pc/mode_ab/geometry.py',ROOT/'scripts/prepare_mode_b_loaded_route.py',Path(__file__)]},
        limitation='Kinematic URDF enclosing boxes and rigid attachment; no friction/contact/physical stopping-distance claim'),indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);main(ap.parse_args().out)
