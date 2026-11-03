"""Public pickup -> original slot; reuse frozen native targets and S2 profile."""
from pathlib import Path
import argparse,contextlib,copy,csv,hashlib,io,json,math
import numpy as np
from prepare_mode_a_follow import LocalModel
from plan_mode_a_delivery_layout import scene_export
from mode_a_upgrade_profile import segment
ROOT=Path(__file__).resolve().parents[1]
PICKUP=[300,200,15]

class RestockModel(LocalModel):
 def __init__(self):super().__init__(350)
 def tilt(self,p):
  if abs(p[0]-300)<.01 and abs(p[1]-200)<.01 and p[2]<=80.01:return max(0.,(p[2]-15)*20/65)
  return super().tilt(p)

def prepare(parent,out):
 out.mkdir(parents=True,exist_ok=False)
 normal=json.loads(parent.read_text('utf-8'))
 with contextlib.redirect_stdout(io.StringIO()):model=RestockModel()
 home=[round(v*65536) for v in normal['home_native_rad']]
 opened=round(normal['open_native_rad']*65536);held=round(normal['hold_native_rad']*65536)
 def same_grip(q,g):return q[:5]+[g]
 reference=normal['paths'][0]['legs']
 byname={l['label']:l for l in reference}
 prefix=[];current=home[:]
 def add(dst,label,target,point,phase,group=None):
  nonlocal current
  meta,ss=segment(current,target,label,phase)
  dst.append(dict(label=label,phase=phase,group=group or label,grasp=phase=='grasp',
   target_D_mm=point,tool_tilt_deg=None if point is None else model.tilt(point),**meta))
  current=target[:]
 add(prefix,'HOME_OPEN',byname['HOME_OPEN']['target_q16'][:],None,'approach')
 inner=same_grip(byname['INNER_FROM_HOME']['target_q16'],opened)
 b=same_grip(byname['B']['target_q16'],opened)
 add(prefix,'INNER_OPEN',inner,[585,225,90],'approach')
 add(prefix,'B_OPEN',b,[360,200,160],'approach')
 points=[[300,200,z] for z in (80,63.75,47.5,31.25,15)]
 source=[];seed=[v/65536 for v in current]
 for i,point in enumerate(points):
  q=model.native_ik(point,seed);q[5]=normal['open_native_rad'];target=[round(v*65536) for v in q]
  source.append(target);add(prefix,'SOURCE_HIGH' if i==0 else f'DESCEND_SOURCE_{i}',target,point,'approach','SOURCE_HIGH' if i==0 else 'DESCEND_SOURCE');seed=q
 add(prefix,'GRASP_SOURCE',same_grip(source[-1],held),PICKUP,'grasp')
 for i,index in enumerate((3,2,1,0),1):add(prefix,f'LIFT_SOURCE_{i}',same_grip(source[index],held),points[index],'lift','LIFT_SOURCE')
 add(prefix,'B_HOLD',same_grip(b,held),[360,200,160],'lift')
 add(prefix,'INNER_HOLD',same_grip(inner,held),[585,225,90],'lift')
 tails=[];routes=[]
 for route in normal['paths']:
  current=prefix[-1]['target_q16'][:];tail=[];old=route['legs'];obj=route['object']
  for l in old:
   if l['label']=='SLOT_HIGH' or l['label'].startswith('DESCEND_'):
    add(tail,l['label']+'_HOLD',same_grip(l['target_q16'],held),l['target_D_mm'],'lift','DESCEND_SLOT' if l['label'].startswith('DESCEND_') else 'SLOT_HIGH')
  at=normal['layout']['slots_D_mm'][obj-1]
  add(tail,'RELEASE_SLOT',same_grip(current,opened),at,'release')
  for l in old:
   if l['label'].startswith('LIFT_'):
    add(tail,l['label']+'_OPEN',same_grip(l['target_q16'],opened),l['target_D_mm'],'retreat','LIFT_SLOT')
  add(tail,'INNER_OPEN',inner,[585,225,90],'retreat')
  add(tail,'HOME',home,None,'retreat')
  tails.append(tail);legs=copy.deepcopy(prefix+tail);samples=[]
  for j,l in enumerate(legs):
   _,ss=segment(l['start_q16'],l['target_q16'],l['label'],l['phase'])
   samples.extend(dict(segment=j,tick=k+1,q16=list(q)) for k,q in enumerate(ss))
  routes.append(dict(object=obj,kind='automatic_restock',legs=legs,samples=samples,seconds=sum(l['seconds'] for l in legs),source_D_mm=PICKUP,target_D_mm=at))
 keypoints=[home];segments=[]
 def compile_legs(legs):
  first=len(segments);release_kp=None
  for i,l in enumerate(legs):
   q=l['target_q16']
   if q not in keypoints:keypoints.append(q)
   kp=keypoints.index(q)
   same=i+1<len(legs) and l['group']==legs[i+1]['group']
   settle=0 if same else (50 if l['phase'] in ('grasp','release') else 22)
   flags=2|(settle<<2)|(1 if l['grasp'] else 0)
   segments.append([kp,l['n'],l['na'],1,flags])
   if l['phase']=='release':release_kp=kp
  return dict(first=first,count=len(legs),release_kp=release_kp)
 prefix_desc=compile_legs(prefix);tail_desc=[compile_legs(t) for t in tails]
 assert len(keypoints)<=64 and len(segments)<=64
 max_chord=max_endpoint=maxv=maxa=0.;total=0
 for route in routes:
  for i,l in enumerate(route['legs']):
   vals=np.array([l['start_q16']]+[s['q16'] for s in route['samples'] if s['segment']==i])/65536
   for q in vals:model.check(q)
   maxv=max(maxv,float(np.max(np.abs(np.diff(vals,axis=0))))/.02)
   if len(vals)>2:maxa=max(maxa,float(np.max(np.abs(np.diff(vals,n=2,axis=0))))/.02**2)
   if l['target_D_mm'] is not None:max_endpoint=max(max_endpoint,math.dist(model.desk(vals[-1]),l['target_D_mm']))
   if l['group'] in ('DESCEND_SOURCE','LIFT_SOURCE','DESCEND_SLOT','LIFT_SLOT'):
    a=np.array(model.desk(vals[0]));b=np.array(model.desk(vals[-1]));d=b-a
    for q in vals:
     actual=np.array(model.desk(q));u=np.clip(np.dot(actual-a,d)/max(1e-12,np.dot(d,d)),0,1)
     max_chord=max(max_chord,float(np.linalg.norm(actual-a-u*d)))
   total+=len(vals)-1
 assert max_endpoint<.1 and max_chord<.5
 plan=copy.deepcopy(normal);plan.update(schema='gesture.mode_a.public_pickup_restock.v1',version='0.14.0',physical_validated=False,
  normal_anchor_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(),pickup_D_mm=PICKUP,paths=routes,hover_paths=[],return_paths=[],
  validation=dict(samples=total,max_endpoint_mm=max_endpoint,max_cartesian_chord_mm=max_chord,max_velocity_deg_s=math.degrees(maxv),max_acceleration_difference_deg_s2=math.degrees(maxa)))
 plan['layout']['pickup_D_mm']=PICKUP
 table=dict(schema='gesture.mode_a.restock_table.v1',task_abi=0x340b,keypoint_bank=3,segment_bank=1,keypoints=keypoints,segments=segments,prefix=prefix_desc,tails=tail_desc,
  pickup_D_mm=PICKUP,normal_anchor_sha256=plan['normal_anchor_sha256'],cancel='RETRACE_TO_PUBLIC_PICKUP_THEN_HOME_EMPTY_SLOT',release_commits_before_open_move=True,arrival_mask=0)
 for name,obj in [('PLAN_NATIVE.json',plan),('SCENE_PLAN.json',scene_export(plan,model)),('S4_RESTOCK_CANDIDATE.json',table)]:
  (out/name).write_text(json.dumps(obj,indent=2)+'\n','utf-8')
 summary=dict(result='RESTOCK_IK_AND_FROZEN_TARGETS_PASS',pickup_D_mm=PICKUP,keypoints=len(keypoints),segments=len(segments),prefix=prefix_desc,tails=tail_desc,
  validation=plan['validation'],seconds=[r['seconds'] for r in routes],physical_test='NOT_RUN')
 (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n','utf-8');print(json.dumps(summary,indent=2))

if __name__=='__main__':
 parent=ROOT/'candidate/bank1/PLAN_NATIVE.json'
 if not parent.exists():parent=ROOT/'board_evidence/mode_a_upgrade_plan_a3/bank1/PLAN_NATIVE.json'
 ap=argparse.ArgumentParser();ap.add_argument('--parent',type=Path,default=parent);ap.add_argument('--out',type=Path,required=True)
 a=ap.parse_args();prepare(a.parent,a.out)
