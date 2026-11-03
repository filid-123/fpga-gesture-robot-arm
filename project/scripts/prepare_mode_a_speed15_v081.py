"""Retime the sealed v070 geometry and compile ABI3406 interaction tables."""
from pathlib import Path
import argparse,json
from prepare_mode_a_board_v07 import RaisedModel
from plan_mode_a_delivery_layout import prepare,ROOT
from mode_a_speed15_profile import profile,retime
from mode_a_board_profile import waypoint_group
from compile_mode_a_sim_tables import compile_plan


def main(out):
    prepare(ROOT/'planning/mode_a_layout_v070.json',out,RaisedModel(),retime,profile(),'0.8.1')
    plan=json.loads((out/'PLAN_NATIVE.json').read_text('utf-8'))
    table=compile_plan(dict(plan,home_sim_rad=plan['home_native_rad']));position=0
    def mark(legs):
        nonlocal position
        for i,leg in enumerate(legs):
            same=i+1<len(legs) and waypoint_group(leg['label'])==waypoint_group(legs[i+1]['label'])
            units=0 if same else (50 if leg['phase'] in ('grasp','release') else 22)
            table['segments'][position][4]|=2|(units<<2);position+=1
    for route in plan['paths']:
        for phase in ('approach','grasp','lift'):mark([l for l in route['legs'] if l['phase']==phase])
    for phase in ('deliver','release','retreat'):mark([l for l in plan['paths'][0]['legs'] if l['phase']==phase])
    assert position==len(table['segments'])
    table.update(schema='gesture.mode_a.native_handover_v2.v1',abi=dict(arm=0x3101,planner=0x3202,task=0x3406,vision=0x3505,model=0x022267a9),
        layout_id=plan['layout_id'],hold_policy=True,tray_exit=False,gripper_semantics='Native RoArm radians',arrival_mask=0,
        segment_flags='bits0 grasp /1 retrace-stop /7:2 fixed settle in16ms units',execution_profile=profile(),physical_validated=False)
    (out/'S4_NATIVE_CANDIDATE.json').write_text(json.dumps(table,indent=2)+'\n','utf-8')
    print('ABI3406 TABLE',table['capacity'])


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();main(a.out)
