"""Image-Y three-band configuration on the unchanged ABI3407 hardware."""
from mode_a_v2_config import ROOT,ARM,PLAN,TASK,VIS,backend_config,backend_writes,protocol,vision_writes
from mode_a_v2_config import validate_map as parent_validate,task_writes as parent_writes
from mode_a_v091_profile import profile
H_POINTS=[[240,135,175],[240,155,175],[240,175,175]]

def default_map():
 return dict(schema='gesture.mode_a.handmap.v1',revision=1,calibrated=False,image_axis='Y',desk_axis='Y',physical_H_D_mm=H_POINTS,cells=[dict(bank=i,x0=0,x1=127,y0=16+i*32,y1=47+i*32) for i in range(3)])

def validate_map(m,require_calibrated=False):
 parent_validate(m,require_calibrated)
 if m.get('image_axis')!='Y' or m.get('desk_axis')!='Y' or m.get('physical_H_D_mm')!=H_POINTS:raise ValueError('Use v0.9.1 IMAGE_Y / DESK_Y calibration; old left/right map cannot be reused')
 if any(c['x0']!=0 or c['x1']!=127 for c in m['cells']):raise ValueError('Image-Y cells must span full X0..127')
 return m

def task_writes(plan,t):
 copy=dict(t,hand_map=validate_map(t.get('hand_map',default_map())))
 return parent_writes(plan,copy)
