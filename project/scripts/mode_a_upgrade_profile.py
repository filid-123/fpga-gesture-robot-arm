"""v0.13 scalar quintic reference, bounded jerk retiming, unchanged anchor geometry."""
import copy,math
from types import SimpleNamespace
from mode_a_hdmi_profile import profile as parent_profile
from mode_a_board_profile import p2p as legacy
SPEED=1320;ACC=66;DT=.02

def profile():
 p=parent_profile();p.update(version='0.13.0',task_abi=0x340a,planner_abi=0x3203,planned_speed_deg_s=72.6,planned_acceleration_deg_s2=239.58,handover_speed_deg_s=29.7,handover_acceleration_deg_s2=130.68,gripper_speed_deg_s=74.25,gripper_acceleration_deg_s2=326.7,release_speed_deg_s=49.5,release_acceleration_deg_s2=217.8,handalign_speed_deg_s=49.5,handalign_acceleration_deg_s2=320,jerk_general_deg_s3=2000,jerk_handover_deg_s3=800,jerk_gripper_deg_s3=3000,jerk_align_deg_s3=2000,scalar_profile='QUINTIC_10u3_15u4_6u5_UQ32',speed_steps_s=SPEED,acceleration_100_steps_s2=ACC,native_speed_deg_s=SPEED*360/4096,native_acceleration_deg_s2=ACC*100*360/4096,handalign_mapping='Fresh raw center; image Y44/64/84 maps H Y255/195/135; clamp16..111',handalign_continuous_steps=64,display='256x192 source Gray8 on640x480 HDMI; one bbox; stage timing footer')
 return p

def scalar(k,n):
 if k==n:return 1<<32
 u=(k<<32)//n;u2=(u*u)>>32;u3=(u2*u)>>32;u4=(u3*u)>>32;u5=(u4*u)>>32
 return max(0,min((1<<32)-1,10*u3-15*u4+6*u5))

def validate(p,last_delivered=None):
 if not legacy.scalars_ok(p):return legacy.Validation(legacy.PlannerError.PARAM_INVALID)
 if p.profile==0:return legacy.validate(p,last_delivered=last_delivered)
 n=p.n_samples;v=n//2;a=n*n//6
 for i,(x,y) in enumerate(zip(p.start,p.target)):
  if last_delivered is not None and x!=last_delivered[i]:return legacy.Validation(legacy.PlannerError.START_MISMATCH,i)
  d=abs(y-x)
  if d>p.vmax_q16[i]*v:return legacy.Validation(legacy.PlannerError.VELOCITY_LIMIT,i)
  if d*65536>p.amax_q32[i]*a:return legacy.Validation(legacy.PlannerError.ACCEL_LIMIT,i)
 return legacy.Validation(None)

def samples(p):
 if p.profile==0:return legacy.samples(p)
 return [tuple(y if k==p.n_samples else x+(-1 if y<x else 1)*((abs(y-x)*scalar(k,p.n_samples)+(1<<31))>>32) for x,y in zip(p.start,p.target)) for k in range(1,p.n_samples+1)]
p2p=SimpleNamespace(MoveParams=legacy.MoveParams,validate=validate,samples=samples)

def steps(delta_deg,v,a,j):
 return max(8,math.ceil(max(2*delta_deg/v,math.sqrt(6*delta_deg/a),(60*delta_deg/j)**(1/3))/DT))

def segment(start,target,label,phase):
 grip=all(abs(start[i]-target[i])<=1 for i in range(5)) and start[5]!=target[5]
 if label=='HANDOVER_ALIGN':v,a,j=49.5,320,2000
 elif grip:v,a,j=(49.5,217.8,1500) if phase=='release' else (74.25,326.7,3000)
 elif label.startswith(('HANDOVER','HAND_CLEAR','RELEASE')):v,a,j=29.7,130.68,800
 else:v,a,j=72.6,239.58,2000
 d=max(abs(y-x)/65536*180/math.pi for x,y in zip(start,target));n=steps(d,v,a,j)
 while True:
  cfg=p2p.MoveParams(tuple(start),tuple(target),n,n//4,1,2000000,50000000,(math.ceil(math.radians(v)*DT*65536)+2,)*6,(math.ceil(math.radians(a)*DT*DT*(1<<32))+2,)*6)
  if validate(cfg,last_delivered=cfg.start).ok:break
  n+=1
 return dict(start_q16=list(start),target_q16=list(target),n=n,na=n//4,profile=1,period_cycles=2000000,seconds=n*DT),samples(cfg)

def retime(route):
 out=copy.deepcopy(route);out['samples']=[]
 for i,l in enumerate(out['legs']):
  meta,ss=segment(l['start_q16'],l['target_q16'],l['label'],l['phase']);l.update(meta)
  out['samples'].extend(dict(segment=i,tick=k+1,q16=list(q)) for k,q in enumerate(ss))
 out['seconds']=sum(l['seconds'] for l in out['legs']);return out

def blend_word(lo,hi,weight):return lo+((hi-lo)*weight+16)//32

def image_step(y):return max(0,min(64,((84-y)*8+2)//5))

BUCKETS=tuple((math.ceil(math.radians(d)*65536),steps(d,49.5,320,2000)) for d in (1,2,4,8,12,20,30,45,90))
def align_steps(delta_q16):return next((n for upper,n in BUCKETS if delta_q16<=upper),512)
