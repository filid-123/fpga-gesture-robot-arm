"""ABI3405 motion units and pure S2 preparation, no hardware on import."""
import copy,math
from run_mode_a_walkthrough import quant,waypoint_group,p2p
VERSION='0.7.0';DT=.02;SPEED=200;ACC=6


def profile():
    return dict(version=VERSION,arrival_policy='observe_all',arrival_mask=0,task_abi=0x3405,
        planned_speed_deg_s=14,planned_acceleration_deg_s2=28,handover_speed_deg_s=9,handover_acceleration_deg_s2=18,
        speed_steps_s=SPEED,acceleration_100_steps_s2=ACC,native_speed_deg_s=SPEED*360/4096,native_acceleration_deg_s2=ACC*100*360/4096,
        period_ms=20,settle_regular_s=.352,settle_grasp_s=.8,settle_release_s=.8,operator_ready_timeout_s=None,
        readiness_source='PL_REAL_CNN_PALM_READY',precision_is_not_a_motion_gate=True)


def segment(start,target,label,phase):
    near=label.startswith(('HANDOVER','HAND_CLEAR','RELEASE'))
    v=math.radians(9 if near else 14);a=math.radians(18 if near else 28)
    delta=max(abs(x-y)/65536 for x,y in zip(start,target));n=max(20,math.ceil(max(.4,delta/v*1.5,math.sqrt(delta/a*6))/DT));na=max(1,n//4)
    cfg=p2p.MoveParams(tuple(start),tuple(target),n,na,1,2_000_000,50_000_000,(math.ceil(v*DT*65536)+2,)*6,(math.ceil(a*DT*DT*(1<<32))+2,)*6)
    if not p2p.validate(cfg,last_delivered=cfg.start).ok:raise ValueError('Invalid S2 segment')
    return dict(start_q16=list(start),target_q16=list(target),n=n,na=na,profile=1,period_cycles=2_000_000,seconds=n*DT),p2p.samples(cfg)


def retime(route):
    out=copy.deepcopy(route);out['samples']=[]
    for i,leg in enumerate(out['legs']):
        meta,ss=segment(leg['start_q16'],leg['target_q16'],leg['label'],leg['phase']);leg.update(meta)
        out['samples'].extend(dict(segment=i,tick=k+1,q16=list(q)) for k,q in enumerate(ss))
    out['seconds']=sum(l['seconds'] for l in out['legs']);return out
