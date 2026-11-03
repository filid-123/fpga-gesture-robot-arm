"""Offline full-pose IK and S2 tables for a declared CoppeliaSim-only datum.

The URDF, its hand_tcp, desk/base alignment and gripping convention are a
simulation contract. This program cannot produce an authorized physical profile.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'ps/robot'))
import planner_p2p_reference as s2

NAMES = ['base_link_to_link1','link1_to_link2','link2_to_link3',
         'link3_to_link4','link4_to_link5','link5_to_gripper_link']
TCP_LOCAL = np.eye(4)
TCP_LOCAL[:3,:3] = Rotation.from_euler('xyz',[1.5708,-1.5708,0]).as_matrix()
TCP_LOCAL[:3,3] = [0,0,.115428]
DT = .02
VMAX = math.radians(8)
AMAX = math.radians(16)


def numbers(value):
    return [float(x) for x in value.split()]


class Model:
    def __init__(self, path):
        tree = ET.parse(path)
        joints = {e.attrib['name']:e for e in tree.findall('joint')}
        self.chain = []
        self.bounds = []
        for name in NAMES:
            e = joints[name]; origin = e.find('origin')
            mat = np.eye(4)
            mat[:3,:3] = Rotation.from_euler('xyz',numbers(origin.attrib['rpy'])).as_matrix()
            mat[:3,3] = numbers(origin.attrib['xyz'])
            self.chain.append(mat)
            limit = e.find('limit')
            self.bounds.append([float(limit.attrib['lower']),float(limit.attrib['upper'])])
        self.base = np.eye(4)
        self.base[:3,3] = [-.004359642926584199,0,.07109999847412107]
        self.table_z = .0218391456604
        self.base_D = [585,25]

    def fk(self, q):
        t = self.base.copy()
        axes = []
        for origin,angle in zip(self.chain,q):
            t = t@origin
            axes.append(t[:3,3].copy())
            r = np.eye(4);r[:3,:3] = Rotation.from_rotvec([0,0,float(angle)]).as_matrix()
            t = t@r
            if len(axes) == 5:
                return t@TCP_LOCAL, t, axes
        raise ValueError('Short chain')

    def world(self, p):
        return np.array([(p[1]-25)/1000+self.base[0,3],
                         -(p[0]-585)/1000,self.table_z+p[2]/1000])

    def ik(self, p, seed):
        target = self.world(p)
        # Link5 +Z points down; the aperture orientation is fixed in the desk.
        tool_r = np.diag([1.,-1.,-1.])
        desired_r = tool_r@TCP_LOCAL[:3,:3]
        def error(q):
            t,_,_ = self.fk(q)
            return np.r_[(t[:3,3]-target)*1000,
                         Rotation.from_matrix(desired_r.T@t[:3,:3]).as_rotvec()*100]
        lo = np.array(self.bounds[:5])[:,0]+1e-5
        hi = np.array(self.bounds[:5])[:,1]-1e-5
        seeds = [seed[:5],[math.atan2(target[1],target[0]-self.base[0,3]),.4,1.6,1.1,0],
                 [0,.1,2.,1.,1.], [0,.8,1.,1.,-1.]]
        best = None
        for initial in seeds:
            fit = least_squares(error,np.clip(initial,lo,hi),bounds=(lo,hi),
                                xtol=1e-11,ftol=1e-11,gtol=1e-11,max_nfev=250)
            norm = float(np.linalg.norm(error(fit.x)))
            if best is None or norm < best[0]:
                best=(norm,fit.x)
            if norm < .01:
                break
        q = list(best[1])+[float(seed[5])]
        t,tool,_ = self.fk(q)
        pos = float(np.linalg.norm(t[:3,3]-target)*1000)
        rot = float(np.linalg.norm(Rotation.from_matrix(desired_r.T@t[:3,:3]).as_rotvec()))
        if pos > .1 or rot > .002:
            raise ValueError(f'FULL_POSE_IK_FAILED position={pos:.3f}mm rotation={rot:.5f}rad')
        return q, pos, rot


def quantize(q):
    return tuple(int(math.copysign(math.floor(abs(x)*65536+.5),x)) for x in q)


def segment(a,b):
    start,target=quantize(a),quantize(b)
    delta=max(abs(x-y)/65536 for x,y in zip(start,target))
    # Trapezoid with quarter-duration acceleration: peak velocity=4d/(3T),
    # peak acceleration=16d/(3T^2). Extra margin covers fixed-point rounding.
    duration=max(.4,delta/VMAX*1.5,math.sqrt(delta/AMAX*6))
    n=max(20,math.ceil(duration/DT));na=max(1,n//4)
    p=s2.MoveParams(start,target,n,na,1,2_000_000,50_000_000,
                   (math.ceil(VMAX*DT*65536)+2,)*6,
                   (math.ceil(AMAX*DT*DT*(1<<32))+2,)*6)
    result=s2.samples(p)
    assert result[-1]==target
    return dict(start_q16=list(start),target_q16=list(target),n=n,na=na,profile=1,
                period_cycles=2_000_000,seconds=n*DT),result


def plan(model, safe, out):
    points = {'B':[450,215,140],'PRE_HIGH':[430,175,150],
              'PRE':[430,175,150],'H':[410,140,115],'H_CLEAR':[410,140,150]}
    original={'B':[360,285,160],'PRE':[290,175,150],'H':[200,140,115]}
    seed=[0,.4,1.5,1.2,0,1.5]
    review=[]
    for label,p in original.items():
        try:
            q,err,rot=model.ik(p,seed)
            review.append(dict(point=label,xyz_D_mm=p,full_pose_ik=True,joint_rad=q))
        except ValueError as e:
            review.append(dict(point=label,xyz_D_mm=p,full_pose_ik=False,reason=str(e)))
    home,_,_=model.ik([585,225,160],seed)
    common={}
    for label,p in points.items():
        common[label]=model.ik(p,home)[0]
    slots=[(530,250),(650,250),(590,320)]
    paths=[];tables=[];all_samples=[]
    for obj,(x,y) in enumerate(slots,1):
        q=home[:];legs=[];samples=[]
        def add(label,position=None,grip=None,phase='approach',grasp=False):
            nonlocal q
            target=q.copy() if position is None else model.ik(position,q)[0]
            if grip is not None:target[5]=grip
            rec,ss=segment(q,target)
            rec.update(label=label,phase=phase,xyz_D_mm=position,
                       target_sim_rad=target,grasp=grasp,object=obj)
            legs.append(rec);samples.extend(dict(segment=len(legs)-1,q16=list(s)) for s in ss)
            q=target
        # Every Cartesian leg is split in <=10mm increments; S2 moves are
        # validated using their actual joint interpolation, not only endpoints.
        def line(label,start,end,phase):
            # Adapt subdivisions to actual joint-space chord error. Fixed
            # 10mm spacing wastes scarce S4 table entries on near-linear legs.
            splits=[]
            def divide(pa,qa,pb,qb,depth):
                err=0.
                for t in (.25,.5,.75):
                    actual=model.fk(np.array(qa)*(1-t)+np.array(qb)*t)[0][:3,3]
                    expected=model.world(np.array(pa)*(1-t)+np.array(pb)*t)
                    err=max(err,float(np.linalg.norm(actual-expected))*1000)
                if err<=.4:
                    splits.append((pb,qb));return
                if depth>=10:raise ValueError('Adaptive subdivision did not converge')
                pm=(np.array(pa)+np.array(pb))*.5
                qm=model.ik(pm,qa)[0]
                divide(pa,qa,pm,qm,depth+1);divide(pm,qm,pb,qb,depth+1)
            target=model.ik(end,q)[0]
            divide(start,q,end,target,0)
            for k,(p,target) in enumerate(splits,1):
                add(label+f'_{k:02d}',list(p),phase=phase)
        p0=[x,y,100];p3=[x,y,15]
        add('P0',p0)
        line('DESCEND',p0,p3,'approach')
        add('GRASP',grip=0.,phase='grasp',grasp=True)
        line('LIFT',p3,p0,'lift')
        add('INWARD_CLEAR',[585,225,100],phase='lift')
        # shared PRE requires the same grasp convention and full joint entry.
        add('B',points['B'],phase='lift')
        add('PRE_HIGH',points['PRE_HIGH'],phase='lift')
        add('PRE',points['PRE'],phase='lift')
        line('DELIVER',points['PRE'],points['H'],'deliver')
        add('RELEASE',grip=1.5,phase='release')
        line('CLEAR',points['H'],points['H_CLEAR'],'retreat')
        add('HOME',[585,225,160],phase='retreat')
        # Store per-task tables separately if Cartesian subdivision exceeds
        # fixed S4 global storage; never truncate a collision-safe route.
        paths.append(dict(object=obj,legs=legs,samples=samples,
                          duration_s=sum(z['seconds'] for z in legs)))
    counts=[len(p['legs']) for p in paths]
    # Simulation trajectories are deliberately not silently reduced to fit S4.
    result=dict(schema='gesture.mode_a.nominal_plan.v1',status='SIMULATION_ONLY',
        physical_execution_allowed=False,nominal_assumptions=dict(
        base_yaw_axis_D_xy_mm=model.base_D,table_world_z_m=model.table_z,
        desk_forward_axis='+Y maps to URDF +X',tool_reference='URDF hand_tcp is virtual Q',
        native_gripper_mapping='NOT_CALIBRATED; scene open1.5/closed0'),
        original_waypoint_review=review,proposed_points=points,
        candidate_points_require_operator_confirmation=True,home_sim_rad=home,
        period_ms=20,requested_hz=50,vmax_deg_s=8,amax_deg_s2=16,
        capacity=dict(global_segments=sum(counts),per_task_segments=counts,
                      S4_SEG_DEPTH=64,S4_KP_DEPTH=64,S4_STACK_DEPTH=32),paths=paths,
        blocking=['No accepted measured desk/base/tool transform',
                  'Candidate B/PRE/H and HOME require physical datum confirmation',
                  'No native joint/URDF mapping or full-arm physical limit validation',
                  'S4 table capacity must be compiled with path-error-aware subdivision'])
    out.mkdir(parents=True,exist_ok=False)
    (out/'PLAN.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
    with (out/'JOINT_WAYPOINTS_SIM_ONLY.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['object','phase','label','b','s','e','t','r','scene_gripper','n','na'])
        for p in paths:
            for leg in p['legs']:
                w.writerow([p['object'],leg['phase'],leg['label'],*leg['target_sim_rad'],leg['n'],leg['na']])
    print(json.dumps({k:result[k] for k in ['status','period_ms','capacity','original_waypoint_review']}))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--urdf',type=Path,default=ROOT/'planning/roarm_m3_nominal.xacro')
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();plan(Model(args.urdf),False,args.out)


if __name__=='__main__':main()
