"""Compile the three nominal routes to one real-sized S4 SIMULATION table."""
from pathlib import Path
import argparse
import json
import sys

from plan_mode_a_nominal import ROOT,quantize
sys.path.insert(0,str(ROOT/'sim/phase3_native_closed_loop/s8_baseline'))
import s4_task_reference as m


def compile_plan(plan):
    if plan['physical_execution_allowed'] is not False:raise ValueError('Expected simulation provenance')
    keypoints=[list(quantize(plan['home_sim_rad']))];segments=[];desc={}
    def path(legs):
        first=len(segments)
        for leg in legs:
            q=leg['target_q16']
            if q not in keypoints:keypoints.append(q)
            segments.append([keypoints.index(q),leg['n'],leg['na'],leg['profile'],int(leg['grasp'])])
        return [first,len(legs)]
    for route in plan['paths']:
        for phase in ('approach','grasp','lift'):
            desc[f'{phase}_{route["object"]}']=path([l for l in route['legs'] if l['phase']==phase])
    for phase in ('deliver','release','retreat'):
        chosen=[[l for l in route['legs'] if l['phase']==phase] for route in plan['paths']]
        # Starts and targets, including grip, must agree at the shared suffix.
        keys=lambda ls:[(l['start_q16'],l['target_q16'],l['n'],l['na'],l['profile']) for l in ls]
        if not all(keys(v)==keys(chosen[0]) for v in chosen[1:]):
            raise ValueError(f'Shared {phase} does not have the same six-channel entry')
        desc[phase]=path(chosen[0])
    if len(keypoints)>64 or len(segments)>64:raise ValueError('S4 global table overflow')
    stack=max(sum(desc[f'{p}_{o}'][1] for p in ('approach','grasp','lift'))+desc['deliver'][1] for o in (1,2,3))
    if stack>32:raise ValueError('S4 retrace stack overflow')
    pre=plan['paths'][0]['legs'][desc['approach_1'][1]+desc['grasp_1'][1]+desc['lift_1'][1]-1]['target_q16']
    return dict(schema='gesture.mode_a.simulation_s4_tables.v1',physical_execution_allowed=False,
                gripper_semantics='URDF scene radians; NEVER the native RoArm hand angle',
                abi=dict(arm=0x3101,planner=0x3202,task=0x3404,vision=0x3505,model=0x022267a9),
                keypoints=keypoints,segments=segments,descriptors=desc,home_kp=0,
                predelivery_kp=keypoints.index(pre),period_cycles=2_000_000,
                hold_policy=False,tray_exit=False,select_mask=14,rearm_mask=129,
                capacity=dict(keypoints=len(keypoints),segments=len(segments),stack_max=stack))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plan',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    result=compile_plan(json.loads(args.plan.read_text('utf-8')))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result['capacity']))
