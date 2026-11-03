"""v0.8.0 timing: same geometry, faster transport/grip, explicit handover."""
import copy,math
from mode_a_board_profile import p2p

DT=.02;SPEED=400;ACC=12


def profile():
    return dict(version='0.8.0',arrival_policy='observe_all',arrival_mask=0,task_abi=0x3406,
        planned_speed_deg_s=22,planned_acceleration_deg_s2=44,handover_speed_deg_s=12,handover_acceleration_deg_s2=24,
        gripper_speed_deg_s=30,gripper_acceleration_deg_s2=60,release_speed_deg_s=20,release_acceleration_deg_s2=40,
        speed_steps_s=SPEED,acceleration_100_steps_s2=ACC,native_speed_deg_s=SPEED*360/4096,
        native_acceleration_deg_s2=ACC*100*360/4096,period_ms=20,
        settle_regular_s=.352,settle_grasp_s=.8,settle_release_s=.8,operator_ready_timeout_s=None,
        fist_hold_ms=1000,predelivery_wait_ms=2000,palm_hold_ms=500,palm_loss_periods=0,blind_after_pre_palm=True,
        readiness_source='PL_REAL_CNN_PALM_READY',precision_is_not_a_motion_gate=True)


def segment(start,target,label,phase):
    grip=all(abs(start[i]-target[i])<=1 for i in range(5)) and start[5]!=target[5]
    if grip:v,a=(20,40) if phase=='release' else (30,60)
    elif label.startswith(('HANDOVER','HAND_CLEAR','RELEASE')):v,a=12,24
    else:v,a=22,44
    v=math.radians(v);a=math.radians(a)
    delta=max(abs(x-y)/65536 for x,y in zip(start,target))
    n=max(20,math.ceil(max(.4,delta/v*1.5,math.sqrt(delta/a*6))/DT));na=max(1,n//4)
    cfg=p2p.MoveParams(tuple(start),tuple(target),n,na,1,2_000_000,50_000_000,
        (math.ceil(v*DT*65536)+2,)*6,(math.ceil(a*DT*DT*(1<<32))+2,)*6)
    if not p2p.validate(cfg,last_delivered=cfg.start).ok:raise ValueError('Invalid faster S2 segment')
    return dict(start_q16=list(start),target_q16=list(target),n=n,na=na,profile=1,period_cycles=2_000_000,seconds=n*DT),p2p.samples(cfg)


def retime(route):
    out=copy.deepcopy(route);out['samples']=[]
    for i,leg in enumerate(out['legs']):
        meta,ss=segment(leg['start_q16'],leg['target_q16'],leg['label'],leg['phase']);leg.update(meta)
        out['samples'].extend(dict(segment=i,tick=k+1,q16=list(q)) for k,q in enumerate(ss))
    out['seconds']=sum(l['seconds'] for l in out['legs']);return out
