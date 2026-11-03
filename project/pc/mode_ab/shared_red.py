"""One physical red cube: frozen A-slot macros connected to B's low HOME."""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from pc.mode_ab.motion import ROOT,home

A_SOURCE=[530.,250.,15.]


def at_a_slot(centre,yaw):
    return (np.linalg.norm(np.array(centre)-A_SOURCE)<=3 and
            abs((yaw+45)%90-45)<=3)


def compile_path(restock=False):
    a=ROOT/'candidate/S4_BANKED_CANDIDATE.json';r=ROOT/'candidate/restock/S4_RESTOCK_CANDIDATE.json'
    t=json.loads(a.read_bytes());rt=json.loads(r.read_bytes())
    tr=json.loads((ROOT/'candidate/mode_ab/home_transitions.json').read_bytes())
    def transition(key):
        leg=tr[key]['legs'][0]
        return dict(target_q16=leg['target_q16'],n=leg['n'],na=leg['na'],profile=1,flags=2,label=key,carrying=False)
    fifo=[transition('B_to_A')]
    if restock:
        source=[]
        for d in (rt['prefix'],rt['tails'][0]):source+=rt['segments'][d['first']:d['first']+d['count']]
        release=None
        for kp,n,na,p,f in source:
            if kp==rt['tails'][0]['release_kp']:release=len(fifo)
            fifo.append(dict(target_q16=rt['keypoints'][kp],n=n,na=na,profile=p,flags=f,label='FROZEN_A_RED_RESTOCK',carrying=None))
        fifo.append(transition('A_to_B'))
        # HOME index zero makes the same returned object available to A.
        points=[[round(v*65536) for v in home('B')]]
        return dict(schema='gesture.mode_ab.compiled_b.v1',task_abi=0x340d,restock=True,release_index=release,
                    fifo=fifo,keypoint_banks=[deepcopy(points) for _ in range(4)],home_kp=0,predelivery_kp=0,
                    origin_kind='A_FIXED',source_centre_mm=A_SOURCE,
                    provenance=dict(a_table_sha256=hashlib.sha256(a.read_bytes()).hexdigest(),restock_sha256=hashlib.sha256(r.read_bytes()).hexdigest()),physical_test='NOT_RUN')
    for key in ('approach_1','grasp_1','lift_1'):
        first,count=t['descriptors'][key]
        for kp,n,na,p,f in t['segments'][first:first+count]:
            fifo.append(dict(target_q16=t['keypoint_banks'][1][kp],n=n,na=na,profile=p,flags=f,label='FROZEN_A_RED_'+key,carrying=None))
    points=deepcopy(t['keypoint_banks']);segments=deepcopy(t['segments'])
    end=transition('A_to_B');home_kp=len(points[0])
    for bank in points:bank.append(end['target_q16'])
    segments.append([home_kp,end['n'],end['na'],1,2])
    desc={k:deepcopy(t['descriptors'][k]) for k in ('deliver','release','retreat')};desc['retreat'][1]+=1
    return dict(schema='gesture.mode_ab.compiled_b.v1',task_abi=0x340d,fifo=fifo,keypoint_banks=points,
                segments=segments,descriptors=desc,home_kp=home_kp,predelivery_kp=t['predelivery_kp'],
                origin_kind='A_FIXED',source_centre_mm=A_SOURCE,
                provenance=dict(a_table_sha256=hashlib.sha256(a.read_bytes()).hexdigest()),physical_test='NOT_RUN')
