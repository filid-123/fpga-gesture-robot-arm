"""v0.8.1: compress proven v080 motion times by 1.5 at the same 50 Hz."""
import copy,math
from mode_a_handover_profile import profile as baseline_profile,segment as baseline_segment
from mode_a_board_profile import p2p

DT=.02;SPEED=600;ACC=27;SCALE=1.5


def profile():
    p=baseline_profile()
    for k in ('planned_speed_deg_s','handover_speed_deg_s','gripper_speed_deg_s','release_speed_deg_s'):p[k]*=SCALE
    for k in ('planned_acceleration_deg_s2','handover_acceleration_deg_s2','gripper_acceleration_deg_s2','release_acceleration_deg_s2'):p[k]*=SCALE**2
    p.update(version='0.8.1',baseline_version='0.8.0',motion_speed_scale=SCALE,
        speed_steps_s=SPEED,acceleration_100_steps_s2=ACC,native_speed_deg_s=SPEED*360/4096,
        native_acceleration_deg_s2=ACC*100*360/4096,
        retiming='N=ceil(v080_N/1.5), Na=max(1,N//4); 20ms samples, fixed settle and interaction unchanged')
    return p


def segment(start,target,label,phase):
    old,_=baseline_segment(start,target,label,phase)
    n=(old['n']*2+2)//3;na=max(1,n//4)
    grip=all(abs(start[i]-target[i])<=1 for i in range(5)) and start[5]!=target[5]
    if grip:v,a=(30,90) if phase=='release' else (45,135)
    elif label.startswith(('HANDOVER','HAND_CLEAR','RELEASE')):v,a=18,54
    else:v,a=33,99
    v,a=math.radians(v),math.radians(a)
    cfg=p2p.MoveParams(tuple(start),tuple(target),n,na,1,2_000_000,50_000_000,
        (math.ceil(v*DT*65536)+2,)*6,(math.ceil(a*DT*DT*(1<<32))+2,)*6)
    result=p2p.validate(cfg,last_delivered=cfg.start)
    if not result.ok:raise ValueError('Invalid 1.5x S2 segment '+label+' '+str(result))
    return dict(start_q16=list(start),target_q16=list(target),n=n,na=na,profile=1,period_cycles=2_000_000,seconds=n*DT),p2p.samples(cfg)


def retime(route):
    out=copy.deepcopy(route);out['samples']=[]
    for i,leg in enumerate(out['legs']):
        meta,ss=segment(leg['start_q16'],leg['target_q16'],leg['label'],leg['phase']);leg.update(meta)
        out['samples'].extend(dict(segment=i,tick=k+1,q16=list(q)) for k,q in enumerate(ss))
    out['seconds']=sum(l['seconds'] for l in out['legs']);return out
