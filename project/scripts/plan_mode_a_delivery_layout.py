"""Replan original slots to the new camera view using the existing A prior.

Pure offline IK/S2 generation. No serial, board or real robot access.
"""
from pathlib import Path
import argparse,copy,csv,hashlib,json,math
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from plan_mode_a_nominal import ROOT,TCP_LOCAL,quantize
from plan_mode_a_residual import ResidualModel,build,AXES
from run_mode_a_walkthrough import retime_route,profile,waypoint_group
from compile_mode_a_sim_tables import compile_plan


class DeliveryModel(ResidualModel):
    @staticmethod
    def tilt(p):return float(np.clip((450-p[0])/180,0,1)*30)

    def desired_rotation(self,p):
        direction=self.world(p)[:2]-self.base[:2,3]
        direction=direction/np.linalg.norm(direction)
        axis=np.array([direction[1],-direction[0],0.])
        return Rotation.from_rotvec(axis*math.radians(self.tilt(p))).as_matrix()@np.diag([1.,-1.,-1.])@TCP_LOCAL[:3,:3]

    def native_ik(self,p,seed):
        if self.tilt(p)==0:return super().native_ik(p,seed)
        target=self.world(p);desired=self.desired_rotation(p)
        def error(q):
            t=self.fk(q)[0]
            return np.r_[(t[:3,3]-target)*1000,Rotation.from_matrix(desired.T@t[:3,:3]).as_rotvec()*100]
        lo=np.array(self.bounds[:5])[:,0]+1e-5;hi=np.array(self.bounds[:5])[:,1]-1e-5
        best=None
        for start in (self.scene(seed)[:5],self.anchor_nominal[:5],[1.,.6,1.2,1.,1.]):
            fit=least_squares(error,np.clip(start,lo,hi),bounds=(lo,hi),xtol=1e-11,ftol=1e-11,gtol=1e-11,max_nfev=250)
            score=float(np.linalg.norm(error(fit.x)))
            if best is None or score<best[0]:best=(score,fit.x)
            if score<.001:break
        e=error(best[1]);pos=float(np.linalg.norm(e[:3]));rot=float(np.linalg.norm(e[3:])/100)
        if pos>.1 or rot>.002:raise ValueError(f'DELIVERY_POSE_IK_FAILED {p} pos={pos} rot={rot}')
        native=list(best[1]+self.bias)+[seed[5]];self.check(native);return native


def scene_export(plan,model):
    scene=copy.deepcopy(plan)
    for key in ('paths','hover_paths','return_paths'):
        for route in scene[key]:
            for row in route['samples']:row['q16']=list(quantize(model.scene([v/65536 for v in row['q16']])))
            for leg in route['legs']:
                for field in ('start_q16','target_q16'):leg[field]=list(quantize(model.scene([v/65536 for v in leg[field]])))
    scene['schema']='gesture.mode_a.delivery_layout_scene.v1'
    return scene


def prepare(layout_path,out,model=None,retime=retime_route,execution_profile=None,version='0.6.0'):
    layout=json.loads(layout_path.read_text('utf-8'));model=model or DeliveryModel()
    if layout['base_axis_D_xy_mm']!=model.base_D:raise ValueError('This layout preserves the original base datum')
    plan,_=build(model,layout['common_D_mm'],[p[:2] for p in layout['slots_D_mm']])
    for key in ('paths','hover_paths','return_paths'):
        plan[key]=[retime(route) for route in plan[key]]
        for route in plan[key]:
            route['layout_id']=layout['layout_id']
            for leg in route['legs']:
                p=leg.get('target_D_mm');leg['tool_tilt_deg']=None if p is None else model.tilt(p)
    count=0;maxv=maxa=maxerr=maxrot=maxchord=0.
    for route in plan['paths']+plan['hover_paths']+plan['return_paths']:
        for i,leg in enumerate(route['legs']):
            vals=np.array([leg['start_q16']]+[r['q16'] for r in route['samples'] if r['segment']==i])/65536
            for q in vals:model.check(q)
            maxv=max(maxv,float(np.abs(np.diff(vals,axis=0)).max())/.02)
            if len(vals)>2:maxa=max(maxa,float(np.abs(np.diff(vals,n=2,axis=0)).max())/.02**2)
            if leg.get('target_D_mm') is not None:
                q=vals[-1];f=model.native_fk(q)[0]
                maxerr=max(maxerr,float(np.linalg.norm(f[:3,3]-model.world(leg['target_D_mm'])))*1000)
                maxrot=max(maxrot,float(np.linalg.norm(Rotation.from_matrix(model.desired_rotation(leg['target_D_mm']).T@f[:3,:3]).as_rotvec())))
            if leg['label'].startswith(('DESCEND','LIFT','RETURN_DESCEND','RETURN_CLEAR','HANDOVER','HAND_CLEAR')):
                pa=np.array(model.desk(vals[0]));pb=np.array(model.desk(vals[-1]));d=pb-pa
                for q in vals:
                    actual=np.array(model.desk(q));u=np.clip(np.dot(actual-pa,d)/max(1e-12,np.dot(d,d)),0,1)
                    maxchord=max(maxchord,float(np.linalg.norm(actual-pa-u*d)))
            count+=len(vals)-1
    active_profile=execution_profile or profile()
    plan.update(version=version,layout=layout,layout_id=layout['layout_id'],layout_sha256=hashlib.sha256(layout_path.read_bytes()).hexdigest(),
        execution_profile=active_profile,arrival_policy='observe_all',vmax_deg_s=active_profile['planned_speed_deg_s'],amax_nominal_deg_s2=active_profile['planned_acceleration_deg_s2'],
        validation=dict(routes=9,samples=count,max_velocity_deg_s=math.degrees(maxv),max_acceleration_difference_deg_s2=math.degrees(maxa),
            max_target_position_after_quantization_mm=maxerr,max_target_orientation_after_quantization_rad=maxrot,max_cartesian_chord_mm=maxchord))
    table=compile_plan(dict(plan,home_sim_rad=plan['home_native_rad']))
    for row in table['segments']:row[4]|=2
    table.update(schema='gesture.mode_a.native_delivery_layout_s4_candidate.v1',hold_policy=True,
        gripper_semantics='Native RoArm radians',layout_id=layout['layout_id'],
        integration_note='Data only. Hardware v0.4.0 does not yet contain this plan or the PC observe-all policy.')
    out.mkdir(parents=True,exist_ok=False)
    def dump(name,data):(out/name).write_text(json.dumps(data,indent=2)+'\n','utf-8')
    dump('PLAN_NATIVE.json',plan);dump('S4_NATIVE_CANDIDATE.json',table);dump('LAYOUT.json',layout)
    dump('SCENE_PLAN.json',scene_export(plan,model))
    with (out/'JOINT_TARGETS_NATIVE.csv').open('x',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f);w.writerow(['object','trial','label','phase','X_mm','Y_mm','Z_mm',*AXES,'seconds','tilt_deg'])
        for route in plan['paths']+plan['hover_paths']+plan['return_paths']:
            for leg in route['legs']:w.writerow([route['object'],route['kind'],leg['label'],leg['phase'],*(leg.get('target_D_mm') or ['','','']),*[v/65536 for v in leg['target_q16']],leg['seconds'],leg['tool_tilt_deg']])
    preview=[]
    for route in plan['paths']:
        rows=[]
        for i,row in enumerate(route['samples']):
            if i%10 and i+1<len(route['samples']) and route['samples'][i+1]['segment']==row['segment']:continue
            q=[v/65536 for v in row['q16']];leg=route['legs'][row['segment']]
            rows.append(dict(interpolation_s=(i+1)*.02,phase=leg['phase'],label=leg['label'],D_mm=model.desk(q),native_rad=q))
        preview.append(dict(object=route['object'],rows=rows))
    dump('PATH_PREVIEW.json',dict(source='Every tenth exact S2 sample plus all leg endpoints; visualization only',paths=preview))
    times=[]
    for route in plan['paths']:
        settle=sum(0 if i+1<len(route['legs']) and waypoint_group(leg['label'])==waypoint_group(route['legs'][i+1]['label']) else (active_profile['settle_grasp_s'] if leg['phase']=='grasp' else (active_profile['settle_release_s'] if leg['phase']=='release' else active_profile['settle_regular_s'])) for i,leg in enumerate(route['legs']))
        times.append(dict(object=route['object'],interpolation_s=route['seconds'],fixed_settle_s=settle,nominal_without_operator_wait_s=route['seconds']+settle))
    summary=dict(result='NEW_VIEW_IK_S2_AND_NATIVE_REFERENCE_PASS',validation=plan['validation'],capacity=table['capacity'],timing=times,
        layout=layout,profile=active_profile,physical_robot=False)
    dump('SUMMARY.json',summary);print(json.dumps(summary,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--layout',type=Path,default=ROOT/'planning/mode_a_layout_v060.json');ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();prepare(a.layout,a.out)
