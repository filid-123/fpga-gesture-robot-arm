"""Replay AB package paths on production S2 RTL with exact six-axis samples."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from run_mode_a_upgrade_s2_xsim import TB
from verify_mode_ab_motion import mixed,samples
from pc.mode_ab.motion import home


def main(attempt):
    out=ROOT/('board_evidence/mode_ab_s2_'+attempt);out.mkdir(exist_ok=False)
    moves=[];gold=[];count=0;inputs={}
    def add(a,b,n,na):
        nonlocal count
        count+=1;moves.extend([n,na])
        for ch in range(6):
            v=74.25 if ch==5 else 72.6;a_limit=326.7 if ch==5 else 320
            moves.extend([a[ch],b[ch],math.ceil(math.radians(v)*.02*65536)+2,
                          math.ceil(math.radians(a_limit)*.02**2*(1<<32))+2])
        for q in samples(a,b,n)[1:]:gold.extend(q)
    for name in ('red_depth12','red_legacy','eraser','small_canister','shared_red'):
        for kind in ('normal','restock'):
            folder=ROOT/'candidate/mode_ab'/('shared_red' if name=='shared_red' else 'profiles/'+name)
            path=folder/(kind+'.json');c=json.loads(path.read_bytes())
            inputs[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
            a=[round(v*65536) for v in home('B')]
            for row in c['fifo']:
                b=row['target_q16'];add(a,b,row['n'],row['na']);a=b
            if kind=='normal':
                for step in (0,16,32,48,64):
                    points=mixed(c,step);a=points[c['predelivery_kp']]
                    for kp,n,na,profile,flags in c['segments']:
                        b=points[kp];add(a,b,n,na);a=b
    path=ROOT/'candidate/mode_ab/home_transitions.json';inputs[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    for transition in json.loads(path.read_bytes()).values():
        for leg in transition['legs']:add(leg['start_q16'],leg['target_q16'],leg['n'],leg['na'])
    for name,words in [('moves.mem',[count]+moves),('golden.mem',[len(gold)//6]+gold)]:
        (out/name).write_text(''.join(f'{x&0xffffffff:08x}\n' for x in words))
    bench=out/'tb.sv';bench.write_text(TB.replace('moves[0:8191]',f'moves[0:{len(moves)}]').replace('golden[0:131071]',f'golden[0:{len(gold)}]').replace('#1000000000;',"#(64'd4000000000);"))
    files=[ROOT/'native_motion/rtl/robot'/n for n in ('planner_p2p_core.v','planner_seq_div.v','planner_seq_mult.v')]+[bench]
    records=[]
    for stage,tool,args in [('compile','xvlog',['-sv',*files]),('elaborate','xelab',['tb_speed15_s2','-s','ab_s2','-O0','-mt','off']),('run','xsim',['ab_s2','-runall'])]:
        cmd=['cmd.exe','/d','/c','E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*map(str,args)]
        r=subprocess.run(cmd,cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=600)
        text=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/(stage+'.txt')).write_text(text)
        records.append(dict(stage=stage,exit_code=r.returncode));print(stage,r.returncode,flush=True)
        if r.returncode or re.search('(ERROR:|Fatal:|FATAL:|FAIL:)',text):raise RuntimeError(text[-3500:])
    if 'PASS:' not in text:raise RuntimeError('No positive S2 result')
    result=dict(passed=True,legs=count,samples=len(gold)//6,axes=6,commands=records,inputs=inputs,
                sources={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                production_period_cycles=2000000,testbench_period_cycles=512,physical_execution=False)
    (out/'result.json').write_text(json.dumps(result,indent=2));print('PASS',count,'legs',len(gold)//6,'samples',flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);main(ap.parse_args().attempt)
