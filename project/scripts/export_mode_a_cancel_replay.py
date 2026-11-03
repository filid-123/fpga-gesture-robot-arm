"""Replay native MOVE targets actually issued by the S4 return testbench.

Mock PAUSE reports a joint midpoint. The stopped forward prefix is replayed
conservatively over its original N; return targets and N/Na are unchanged.
This is stopped kinematics, not a model of actuator braking dynamics.
"""
from pathlib import Path
import argparse,copy,json,math,shutil
from mode_a_cancel_shift_config import ROOT,TASK,task_writes
from mode_a_board_profile import p2p
from plan_mode_a_delivery_layout import scene_export
from prepare_mode_a_cancel_shift_v082 import ShiftedPreModel


def unpack(s):
    x=int(s,16);out=[]
    for i in range(6):
        v=(x>>(32*i))&0xffffffff;out.append(v-(1<<32) if v&0x80000000 else v)
    return out


def main(candidate,trace,out):
    plan=json.loads((candidate/'PLAN_NATIVE.json').read_text('utf-8'));table=json.loads((candidate/'S4_NATIVE_CANDIDATE.json').read_text('utf-8'))
    writes=dict(task_writes(plan,table));groups={};ends={}
    for row in trace.read_text('utf-8').splitlines():
        fields=row.split()
        if fields[0]=='MOVE':
            sc,obj,st,kind,hold,released,n,na,flags=map(int,fields[1:10]);start,target=map(unpack,fields[10:12])
            groups.setdefault(sc,[]).append(dict(object=obj,state=st,kind=kind,hold=hold,released=released,n=n,na=na,flags=flags,start_q16=start,target_q16=target))
        elif fields[0]=='END':ends[int(fields[1])]=fields[2]
    result=copy.deepcopy(plan);routes=[];shortened=0
    model=ShiftedPreModel()
    for sc,completion in ends.items():
        commands=groups[sc];legs=[];samples=[]
        for i,cmd in enumerate(commands):
            if i+1<len(commands) and cmd['target_q16']!=commands[i+1]['start_q16']:
                assert cmd['kind']==0;cmd['target_q16']=commands[i+1]['start_q16'];shortened+=1
            start,target=cmd['start_q16'],cmd['target_q16']
            cfg=p2p.MoveParams(tuple(start),tuple(target),cmd['n'],cmd['na'],1,2_000_000,50_000_000,
                tuple(writes[TASK+0xb0+4*c] for c in range(6)),tuple(writes[TASK+0xc8+4*c] for c in range(6)))
            assert p2p.validate(cfg,last_delivered=cfg.start).ok
            if cmd['kind']:
                phase='release' if target[5]<start[5] else ('lift' if cmd['hold'] else 'retreat')
            else:
                phase=('release' if target[5]<start[5] else 'retreat') if cmd['released'] else ('grasp' if cmd['flags']&1 else ('lift' if cmd['hold'] else 'approach'))
            leg=dict(start_q16=start,target_q16=target,n=cmd['n'],na=cmd['na'],profile=1,period_cycles=2_000_000,
                label=f'S4_{sc}_{i}_K{cmd["kind"]}',phase=phase,grasp=bool(cmd['flags']&1),seconds=cmd['n']*.02,
                target_D_mm=model.desk([q/65536 for q in target]),source_kind=cmd['kind'])
            legs.append(leg)
            samples.extend(dict(segment=i,tick=k+1,q16=list(q)) for k,q in enumerate(p2p.samples(cfg)))
        routes.append(dict(object=commands[0]['object'],kind='cancel' if completion=='RETURNED' else 'handover',scenario=sc,
            completion=completion,legs=legs,samples=samples,seconds=sum(l['seconds'] for l in legs)))
    assert len(routes)==12
    result.update(paths=routes,hover_paths=[],return_paths=[],replay_scope=__doc__,source_trace=str(trace.name))
    out.mkdir(parents=True,exist_ok=False)
    for name,data in [('PLAN_NATIVE.json',result),('SCENE_PLAN.json',scene_export(result,model))]:
        (out/name).write_text(json.dumps(data,indent=2)+'\n','utf-8')
    shutil.copyfile(candidate/'S4_NATIVE_CANDIDATE.json',out/'S4_NATIVE_CANDIDATE.json')
    summary=dict(result='ACTUAL_S4_TARGETS_TO_EXACT_S2_RETURN_REPLAY',routes=len(routes),returned_scenarios=sum(r['completion']=='RETURNED' for r in routes),
        legs=sum(len(r['legs']) for r in routes),samples=sum(len(r['samples']) for r in routes),conservatively_retimed_stopped_prefixes=shortened,
        return_targets_and_durations_changed=False,physical_robot=False)
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n','utf-8');print(json.dumps(summary,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--trace',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();main(a.candidate,a.trace,a.out)
