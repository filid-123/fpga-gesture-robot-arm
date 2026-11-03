"""A-anchored native-angle trial candidate; no hardware access.

The single-point, constant joint-residual hypothesis is an extrapolation prior,
not an identified encoder calibration. Native angles are distinct from scene
angles. Physical trials are performed by the operator after simulation.
"""
from pathlib import Path
import argparse,csv,hashlib,json,math,sys
import numpy as np

from plan_mode_a_nominal import Model,ROOT,quantize,segment,s2,DT,VMAX,AMAX
from compile_mode_a_sim_tables import compile_plan

AXES=('b','s','e','t','r','g')
PKG=ROOT/'handoff/giao_9504e60e/docs/phase3c/mode1_red_fpga_handoff_20261027'
OLD=ROOT/'handoff/giao_427c805c/docs/phase3c'
OPEN=1.587670115
HOLD=2.6
NATIVE_LIMITS=[[-math.pi,math.pi],[-math.pi/2,math.pi/2],[0,3.1400586728019073],[-math.pi/2,math.pi/2],[-math.pi,math.pi],[1.08,math.pi]]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


class ResidualModel(Model):
    def __init__(self):
        super().__init__(ROOT/'planning/roarm_m3_nominal.xacro')
        high=json.loads((OLD/'mode1_red_trial_20261026/HIGH_LIFT_SUCCESS_151815.json').read_text('utf-8'))
        measurements=json.loads((OLD/'mode1_remaining_route_20261027/MEASUREMENTS.json').read_text('utf-8'))
        self.anchor_native=[high['final_joint_rad'][k] for k in AXES]
        self.anchor_D=[*measurements['cube_centre_projection_D_mm'],measurements['cube_bottom_height_mm']+15]
        # Solve the declared top-down/yaw-zero nominal pose. The measured anchor
        # supplies position and native angles, not independently measured RPY.
        self.bias=np.zeros(5)
        nominal=super().ik(self.anchor_D,self.anchor_native)[0]
        self.bias=np.array(self.anchor_native[:5])-nominal[:5]
        self.original_bounds=[v[:] for v in self.bounds]
        for i in range(5):
            self.bounds[i]=[max(self.bounds[i][0],NATIVE_LIMITS[i][0]-self.bias[i]),
                            min(self.bounds[i][1],NATIVE_LIMITS[i][1]-self.bias[i])]
        self.bounds[5]=NATIVE_LIMITS[5][:]
        self.anchor_nominal=list(map(float,nominal))

    def scene(self,native):
        return [float(v-b) for v,b in zip(native[:5],self.bias)]+[float(np.clip((HOLD-native[5])/(HOLD-OPEN)*1.5,0,1.5))]

    def native_fk(self,native):return super().fk(self.scene(native))

    def native_ik(self,p,seed):
        q,err,rot=super().ik(p,self.scene(seed))
        native=[float(v+b) for v,b in zip(q[:5],self.bias)]+[seed[5]]
        self.check(native)
        return native

    @staticmethod
    def check(q):
        if len(q)!=6 or any(not math.isfinite(v) or v<lo-1/65536 or v>hi+1/65536 for v,(lo,hi) in zip(q,NATIVE_LIMITS)):
            raise ValueError('Native reference limit violation '+str(q))

    def desk(self,q):
        p=self.native_fk(q)[0][:3,3]
        return [585-p[1]*1000,25+(p[0]-self.base[0,3])*1000,(p[2]-self.table_z)*1000]


def build(model=None,common=None,slots=None):
    model=model or ResidualModel()
    home_rec=json.loads((PKG/'HOME.json').read_text('utf-8'))
    home_source=json.loads((PKG/'RED_ROUTE_CANDIDATE.json').read_text('utf-8'))['keypoints'][0]['joint_rad']
    home=[home_source[k] for k in AXES]
    common=common or {'INNER':[585,225,90],'B':[450,215,100],'PRE':[430,175,110],
            'H':[410,140,115],'H_CLEAR':[410,140,135]}
    slots=slots or [(530,250),(650,250),(590,320)]
    seed=home[:];solved={}
    for name,p in common.items():solved[name]=model.native_ik(p,seed);seed=solved[name]
    paths=[];hover=[];returns=[];checks=[]

    def make_route(obj,xy,kind):
        q=home[:];legs=[];samples=[]
        def add(label,p=None,g=None,phase='approach',grasp=False,target=None):
            nonlocal q
            goal=list(target) if target is not None else (q[:] if p is None else model.native_ik(p,q))
            if g is not None:goal[5]=g
            model.check(goal)
            # Adaptive Cartesian subdivision uses the corrected model and
            # checks joint chords; starts/targets remain native Q16.16.
            origin=model.desk(q)
            knots=[]
            def split(a,b,pa,pb,depth=0):
                error=0.
                for u in (.125,.25,.375,.5,.625,.75,.875):
                    actual=model.desk([x+u*(y-x) for x,y in zip(a,b)])
                    expected=[x+u*(y-x) for x,y in zip(pa,pb)]
                    error=max(error,math.dist(actual,expected))
                if error<=.35:knots.append((b,pb));return
                if depth>=10:raise ValueError('Cartesian split depth')
                mid=[(x+y)/2 for x,y in zip(pa,pb)];qm=model.native_ik(mid,a);qm[5]=a[5]+.5*(b[5]-a[5])
                split(a,qm,pa,mid,depth+1);split(qm,b,mid,pb,depth+1)
            # HOME transitions change tool pose. They are checked as swept
            # joint paths, not falsely described as Cartesian/downward legs.
            if p is not None and label in ('DESCEND','LIFT','RETURN_DESCEND','RETURN_CLEAR','HANDOVER','HAND_CLEAR'):
                split(q,goal,origin,list(p))
            else:knots=[(goal,p)]
            for j,(nextq,point) in enumerate(knots):
                leg,points=segment(q,nextq);leg.update(label=label+(f'_{j+1}' if len(knots)>1 else ''),
                    phase=phase,grasp=bool(grasp),target_D_mm=point)
                index=len(legs);legs.append(leg)
                for k,value in enumerate(points):samples.append(dict(segment=index,tick=k+1,q16=list(value)))
                q=nextq
        add('HOME_OPEN',g=OPEN)
        add('INNER_FROM_HOME',p=common['INNER'],g=OPEN)
        add('SLOT_HIGH',p=[*xy,80],g=OPEN)
        if kind!='hover':
            add('DESCEND',p=[*xy,15],g=OPEN)
            add('GRASP',g=HOLD,phase='grasp',grasp=True)
            add('LIFT',p=[*xy,80],g=HOLD,phase='lift')
            if kind=='return':
                add('RETURN_DESCEND',p=[*xy,15],g=HOLD,phase='deliver')
                add('RETURN_RELEASE',g=OPEN,phase='release')
                add('RETURN_CLEAR',p=[*xy,80],g=OPEN,phase='retreat')
            else:
                add('INNER_HOLD',p=common['INNER'],g=HOLD,phase='lift')
                add('B',p=common['B'],g=HOLD,phase='lift')
                add('PRE',p=common['PRE'],g=HOLD,phase='lift')
                add('HANDOVER',p=common['H'],g=HOLD,phase='deliver')
                add('RELEASE',g=OPEN,phase='release')
                add('HAND_CLEAR',p=common['H_CLEAR'],g=OPEN,phase='retreat')
        add('INNER_RETURN',p=common['INNER'],g=OPEN,phase='retreat')
        armhome=home[:];armhome[5]=OPEN
        add('HOME_ARM',target=armhome,phase='retreat')
        add('HOME_CLOSE',target=home,phase='retreat')
        return dict(object=obj,kind=kind,slot_D_mm=[*xy,15],legs=legs,samples=samples,
                    seconds=sum(l['seconds'] for l in legs))

    for obj,xy in enumerate(slots,1):
        paths.append(make_route(obj,xy,'handover'))
        hover.append(make_route(obj,xy,'hover'))
        returns.append(make_route(obj,xy,'return'))
    allroutes=paths+hover+returns
    maxv=maxa=maxerr=0.;count=0
    for route in allroutes:
        for i,leg in enumerate(route['legs']):
            p=s2.MoveParams(tuple(leg['start_q16']),tuple(leg['target_q16']),leg['n'],leg['na'],1,2_000_000,50_000_000,
                (math.ceil(VMAX*DT*65536)+2,)*6,(math.ceil(AMAX*DT*DT*(1<<32))+2,)*6)
            result=s2.validate(p,last_delivered=p.start)
            if not result.ok:raise ValueError(result)
            values=[p.start]+[tuple(r['q16']) for r in route['samples'] if r['segment']==i]
            if values[1:]!=s2.samples(p):raise ValueError('S2 exact mismatch')
            a=np.array(values)/65536
            for q in a:model.check(q)
            maxv=max(maxv,float(np.abs(np.diff(a,axis=0)).max())/DT)
            if len(a)>2:maxa=max(maxa,float(np.abs(np.diff(a,n=2,axis=0)).max())/DT**2)
            if leg['label'].startswith(('DESCEND','LIFT','RETURN_DESCEND','RETURN_CLEAR')):
                pa=np.array(model.desk(a[0]));pb=np.array(model.desk(a[-1]));d=pb-pa
                for q in a:
                    actual=np.array(model.desk(q));u=np.clip(np.dot(actual-pa,d)/max(1e-12,np.dot(d,d)),0,1)
                    maxerr=max(maxerr,float(np.linalg.norm(actual-(pa+u*d))))
            count+=len(values)-1
    plan=dict(schema='gesture.mode_a.anchor_residual_native_candidate.v1',version='0.5.0',
        physical_execution_allowed=False,operator_supervised_trial_candidate=True,physical_validated=False,
        residual_hypothesis='constant additive native joint residual from ONE historic A high pose; assumed nominal top-down, yaw-zero tool frame; not an identified zero calibration',
        anchor_D_mm=model.anchor_D,anchor_native_rad=model.anchor_native,
        anchor_nominal_rad=model.anchor_nominal,residual_rad=model.bias.tolist(),
        residual_deg=np.degrees(model.bias).tolist(),anchor_reconstruction_error_mm=math.dist(model.desk(model.anchor_native),model.anchor_D),
        native_limits_rad=NATIVE_LIMITS,home_native_rad=home,open_native_rad=OPEN,hold_native_rad=HOLD,
        common_D_mm=common,period_ms=20,vmax_deg_s=8,amax_nominal_deg_s2=16,
        paths=paths,hover_paths=hover,return_paths=returns,
        validation=dict(routes=len(allroutes),samples=count,max_velocity_deg_s=math.degrees(maxv),
            max_acceleration_difference_deg_s2=math.degrees(maxa),max_vertical_chord_mm=maxerr),
        inputs={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in [
            OLD/'mode1_red_trial_20261026/HIGH_LIFT_SUCCESS_151815.json',
            OLD/'mode1_remaining_route_20261027/MEASUREMENTS.json',PKG/'HOME.json',PKG/'RED_ROUTE_CANDIDATE.json',ROOT/'planning/roarm_m3_nominal.xacro']})
    table=compile_plan(dict(plan,home_sim_rad=home))
    for row in table['segments']:row[4]|=2  # retain normal retrace markers
    table.update(schema='gesture.mode_a.native_residual_s4_candidate.v1',
        gripper_semantics='Native RoArm radians; open=1.587670115, hold target=2.6',hold_policy=True,
        operator_supervised_trial_candidate=True,physical_validated=False)
    return plan,table


def write(out):
    if out.exists():raise FileExistsError('Preserve previous attempt: '+str(out))
    out.mkdir(parents=True)
    plan,table=build()
    (out/'PLAN_NATIVE.json').write_text(json.dumps(plan,indent=2)+'\n','utf-8')
    (out/'S4_NATIVE_CANDIDATE.json').write_text(json.dumps(table,indent=2)+'\n','utf-8')
    with (out/'JOINT_TARGETS_NATIVE.csv').open('x',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f);writer.writerow(['object','trial','label','phase','X_mm','Y_mm','Z_mm',*AXES,'seconds'])
        for r in plan['paths']+plan['hover_paths']+plan['return_paths']:
            for l in r['legs']:writer.writerow([r['object'],r['kind'],l['label'],l['phase'],*(l['target_D_mm'] or ['','','']),*[v/65536 for v in l['target_q16']],l['seconds']])
    # Scene export preserves timing but explicitly converts the five arm zero
    # assumptions and the native hand convention; it is never a native loader.
    model=ResidualModel();scene=json.loads(json.dumps(plan))
    for r in scene['paths']+scene['hover_paths']+scene['return_paths']:
        for row in r['samples']:row['q16']=list(quantize(model.scene([v/65536 for v in row['q16']])))
        for l in r['legs']:
            for key in ('start_q16','target_q16'):l[key]=list(quantize(model.scene([v/65536 for v in l[key]])))
    scene['schema']='gesture.mode_a.residual_scene_export.v1';scene['scene_angle_rule']='q_scene[:5]=q_native[:5]-residual; hand remapped to0..1.5'
    (out/'SCENE_PLAN.json').write_text(json.dumps(scene,indent=2)+'\n','utf-8')
    print(json.dumps(dict(result='NATIVE_RESIDUAL_S2_PASS',validation=plan['validation'],capacity=table['capacity'],residual_deg=plan['residual_deg'],durations=[p['seconds'] for p in plan['paths']]),indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();write(a.out)
