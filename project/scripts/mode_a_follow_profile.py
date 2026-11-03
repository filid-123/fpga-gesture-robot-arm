"""Three visible positions, independent Locator and bounded S2 retargeting."""
import copy,math
from mode_a_four_profile import profile as parent_profile
from mode_a_speed15_profile import segment as old_segment
from mode_a_board_profile import p2p
SPEED=660;ACC=33;H_Y=[135,195,255,255]
BUCKETS=[(1144,12),(2288,16),(4576,20),(9151,28),(13726,32),(22877,44),(34315,64),(51472,92),(102944,184)]

def profile():
 p=parent_profile()
 for k in ('planned_speed_deg_s','handover_speed_deg_s','gripper_speed_deg_s','release_speed_deg_s'):p[k]*=1.1
 for k in ('planned_acceleration_deg_s2','handover_acceleration_deg_s2','gripper_acceleration_deg_s2','release_acceleration_deg_s2'):p[k]*=1.1**2
 p.update(version='0.11.0',task_abi=0x3409,handalign_regions=3,handalign_storage_banks=4,handalign_hold_ms=80,handalign_min_frames=2,handalign_settle_ms=48,handalign_mapping='Fresh valid raw Locator, Y54/74; upper image desk+Y',handalign_retarget='PAUSE/drain/CLEAR, restart from LAST_DELIVERED; actual-delta timing',handalign_H_y_mm=H_Y[:3],speed_steps_s=SPEED,acceleration_100_steps_s2=ACC,native_speed_deg_s=SPEED*360/4096,native_acceleration_deg_s2=ACC*100*360/4096,handalign_speed_deg_s=33,handalign_acceleration_deg_s2=160,motion_speed_scale_from_v010=1.1)
 return p

def align_steps(delta):return next((n for upper,n in BUCKETS if delta<=upper),512)

def segment(start,target,label,phase):
 align=label=='HANDOVER_ALIGN'
 if align:n=align_steps(max(abs(a-b) for a,b in zip(start,target)))
 else:
  old,_=old_segment(start,target,label,phase);n=max(8,math.ceil(old['n']/1.1))
 na=max(1,n//4)
 grip=all(abs(start[i]-target[i])<=1 for i in range(5)) and start[5]!=target[5]
 if align:v,a=33,160
 elif grip:v,a=(33,108.9) if phase=='release' else (49.5,163.35)
 elif label.startswith(('HANDOVER','HAND_CLEAR','RELEASE')):v,a=19.8,65.34
 else:v,a=36.3,119.79
 for _ in range(100):
  cfg=p2p.MoveParams(tuple(start),tuple(target),n,na,1,2000000,50000000,(math.ceil(math.radians(v)*.02*65536)+2,)*6,(math.ceil(math.radians(a)*.0004*(1<<32))+2,)*6)
  if p2p.validate(cfg,last_delivered=cfg.start).ok:break
  n+=1;na=max(1,n//4)
 else:raise ValueError('S2 cannot retime '+label)
 return dict(start_q16=list(start),target_q16=list(target),n=n,na=na,profile=1,period_cycles=2000000,seconds=n*.02),p2p.samples(cfg)

def retime(route):
 out=copy.deepcopy(route);out['samples']=[]
 for i,l in enumerate(out['legs']):
  meta,ss=segment(l['start_q16'],l['target_q16'],l['label'],l['phase']);l.update(meta)
  out['samples'].extend(dict(segment=i,tick=k+1,q16=list(q)) for k,q in enumerate(ss))
 out['seconds']=sum(l['seconds'] for l in out['legs']);return out
