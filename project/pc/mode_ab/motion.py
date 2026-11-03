"""Full-window empirical B geometry, with unchanged FPGA timing and limits.

Each class's measured correction is translated once across the pickup window.
Anchor distance is not an admission rule. Every generated trajectory still
requires actual IK and sampled geometry checks. No device I/O occurs here.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys
from functools import lru_cache
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from prepare_mode_b_loaded_route import objects, geometry_check, build_postlift_connection, NAMES
from mode_a_upgrade_profile import segment
from pc.mode_ab.workspace import policy as workspace_policy,validate_source


def read(path):
    return json.loads(Path(path).read_bytes())


def qrow(row):
    return np.array([row[n] for n in NAMES], float)


def home(mode):
    if mode == 'A':
        return read(ROOT/'candidate/bank1/PLAN_NATIVE.json')['home_native_rad']
    q = template('red_cube')['local_scene_config']['home_rad']
    return q[:5]+[3.10]


RED_DEPTH_ANCHOR = [583.7419796330238,252.22010726545997,15.]


def profile_id(name, centre=None):
    if name == 'red_cube':
        return 'red_depth12'
    return name


@lru_cache(maxsize=1)
def boundaries():
    return dict(workspace_xy_mm=[490,690,215,355],height_tolerance_mm=.02,
        red_depth12=dict(reference_mm=RED_DEPTH_ANCHOR,radius_mm=None,depth_mm=12),
        red_legacy=dict(reference_mm=template('red_cube','red_legacy')['request']['pickup']['centre_mm'],radius_mm=None,depth_mm=0),
        eraser=dict(reference_mm=[631.6914227158205,265.6341499003452,7.5],radius_mm=None),
        small_canister=dict(reference_mm=template('small_canister')['request']['pickup']['centre_mm'],radius_mm=None),
        historical_anchor_radius_gate=False,
        note='全取物框：各类实测残差按用户要求推广，不按锚点半径拒绝。关节/碰撞检查保持；实体全域未验证。')


def template(name, selected_profile=None):
    if name not in ('red_cube','eraser','small_canister'):
        raise ValueError('Unsupported physical class')
    selected_profile=selected_profile or profile_id(name)
    legacy=selected_profile=='red_legacy'
    path = (ROOT/'docs/phase3c/mode_b_teammate_handoff_20261028/objects'/name/'evidence/PLAN.json' if legacy else
        ROOT/'docs/phase3c/mode_b_optimized_handoff_20261030/objects'/name/'PLAN.json')
    p = read(path)
    p['ab_source'] = dict(file=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    p['ab_profile_id']=selected_profile
    # The Giao curves are geometry inputs. The exported FPGA timing is always
    # recomputed with A's 1320/66 contract, independent of Giao's TTL speeds.
    speed=read(ROOT/'config/ai_pc/mode_b_transit_speed_20261030_v1.json')
    p['joint_transit_phases']=speed['joint_phases']
    p['phase_speed_multiplier']=speed['phase_speed_multiplier']
    return p


def sparse_indices(arrays, tolerance=.003):
    """Joint-space chord approximation with shared indices for the three banks."""
    size = len(arrays[0]); keep = {0, size-1}
    def split(a,b):
        if b <= a+1:
            return
        u = np.linspace(0,1,b-a+1)[:,None]
        errors = np.max([np.max(abs(x[a:b+1]-(x[a]+u*(x[b]-x[a]))),axis=1) for x in arrays],axis=0)
        k = int(np.argmax(errors))
        if errors[k] > tolerance:
            k += a;keep.add(k);split(a,k);split(k,b)
    split(0,size-1)
    return sorted(keep)


def stage_rows(stage):
    return np.array([qrow(stage['start_firmware_rad'])]+[qrow(f['command_firmware_rad']) for f in stage['stage']['stream_frames']])


def transfer(name, centre, yaw, *, selected_profile=None, grasp_policy=None):
    p = template(name,selected_profile or profile_id(name,centre))
    centre=validate_source(name,centre); old=np.array(p['request']['pickup']['centre_mm'])
    if centre.shape!=(3,) or not np.isfinite(centre).all() or not math.isfinite(yaw):
        raise ValueError('Finite desktop source required')
    symmetry=180 if name=='eraser' else 90
    dyaw=0 if name=='small_canister' else (yaw-p['request']['pickup']['yaw_deg']+symmetry/2)%symmetry-symmetry/2
    r=Rotation.from_euler('z',dyaw,degrees=True).as_matrix()
    robot,world=objects(p); anchor=np.array(p['initial_source_object_pose'])[:3,3]
    delta=centre-old
    motion_policy=grasp_policy or workspace_policy()
    max_raise=float(motion_policy.get('maximum_grasp_tcp_raise_mm',0))
    max_grasp_tilt=float(motion_policy['maximum_additional_grasp_tilt_deg'])
    if not (0<=max_raise<=15 and 0<=max_grasp_tilt<=30):
        raise ValueError('Grasp policy must stay within 15 mm TCP adjustment and 30 degree tilt')
    low_reference=qrow(p['stages'][1]['stage']['target_firmware_rad'])
    low_frames=robot.frames(np.r_[low_reference[:5],0.])
    def box_bottom(frame,link):
        low,high=robot.boxes[link];m=frame[link]
        return float((m[:3,:3]@((low+high)/2)+m[:3,3])[2]-abs(m[2,:3])@((high-low)/2))
    low_floor={link:box_bottom(low_frames,link) for link in ('link5','gripper_link')}
    solved=[]
    newpose=np.array(p['initial_source_object_pose']).copy()
    newpose[:3,:3]=r@newpose[:3,:3];newpose[:3,3]+=delta
    attachment=None
    def solve(q,seed):
        if np.max(abs(delta))<1e-9 and abs(dyaw)<1e-9:
            return q.copy()
        oldtcp=robot.fk(np.r_[q[:5],0.]); target=r@(oldtcp[:3,3]-anchor)+anchor+delta
        oldaxis=(r@oldtcp[:3,:3])[:,0]
        targetyaw=math.atan2(oldaxis[1],oldaxis[0])
        targettilt=math.acos(float(np.clip(oldtcp[2,2],-1,1)))
        tilt_limit=math.radians(30 if target[2]>40 else min(10,max_grasp_tilt))
        flexible=False
        adjust_height=False
        def residual(a):
            ff=robot.frames(np.r_[a,0.]);tcp=ff['grasp']; axis=tcp[:3,0]
            angle=(math.atan2(axis[1],axis[0])-targetyaw+math.pi)%(2*math.pi)-math.pi
            # Retain the demonstrated local tool tilt; yaw uses object symmetry.
            # A cosine residual loses sensitivity near a vertical tool. That
            # allowed ~0.34 degrees of sag at a depth-12 source. Minimize the
            # angle error itself and include table clearance in the solve;
            # the complete sampled validator still enforces every hard bound.
            tilt=math.acos(float(np.clip(tcp[2,2],-1,1)))
            clearance=[]
            for name in ('link5','gripper_link'):
                bottom=box_bottom(ff,name)
                floor=float(world.table_clearance_by_link.get(name,world.margin))+.02
                if adjust_height:floor=max(floor,low_floor[name])
                clearance.append(50*max(0,floor-bottom))
            if attachment is not None and max_raise:
                pose=tcp@attachment
                size=np.array(p['local_scene_config']['objects'][p['request']['object_class']]['size_mm'])
                bottom=pose[2,3]-abs(pose[2,:3])@(size/2)
                clearance.append(50*max(0,.02-bottom))
            tilt_error=max(0,math.pi-tilt-tilt_limit) if flexible else tilt-targettilt
            pe=tcp[:3,3]-target
            if adjust_height:pe[2]=max(0,pe[2]-max_raise)+min(0,pe[2])
            return np.r_[pe,60*angle,40*tilt_error,clearance]
        # Search the mechanical joint envelope, rather than an artificial
        # +/-0.5 rad window around the historical anchor.
        lo=robot.limits[:5,0]+1e-5
        hi=robot.limits[:5,1]-1e-5
        result=least_squares(residual,np.clip(seed[:5],lo+1e-6,hi-1e-6),bounds=(lo,hi),max_nfev=200,
                             ftol=1e-11,xtol=1e-11,gtol=1e-11)
        out=np.r_[result.x,q[5]]
        error=residual(result.x)
        if np.linalg.norm(error[:3])>.05 or abs(error[3])>1 or abs(error[4])>.01 or max(error[5:],default=0)>.01:
            flexible=True
            result=least_squares(residual,result.x,bounds=(lo,hi),max_nfev=400,
                ftol=1e-11,xtol=1e-11,gtol=1e-11)
            out=np.r_[result.x,q[5]];error=residual(result.x)
        if max_raise and (np.linalg.norm(error[:3])>.05 or abs(error[3])>1 or abs(error[4])>.01 or max(error[5:],default=0)>.01):
            # Optional reviewed profile: preserve corrected XY and actual jaw
            # floor, and let the TCP rise only as required by tool inclination.
            adjust_height=True
            candidates=([30] if target[2]>40 else sorted(set([min(10,max_grasp_tilt)]+
                [angle for angle in (15,20,25,30) if angle<=max_grasp_tilt]+[max_grasp_tilt])))
            for angle in candidates:
                tilt_limit=math.radians(angle)
                result=least_squares(residual,result.x,bounds=(lo,hi),max_nfev=400,
                    ftol=1e-11,xtol=1e-11,gtol=1e-11)
                out=np.r_[result.x,q[5]];error=residual(result.x)
                if np.linalg.norm(error[:3])<=.05 and abs(error[3])<=1 and abs(error[4])<=.01 and max(error[5:],default=0)<=.01:
                    break
        if np.linalg.norm(error[:3])>.05 or abs(error[3])>1 or abs(error[4])>.01 or max(error[5:],default=0)>.01:
            raise ValueError('FULL_WORKSPACE_IK: no solution for the residual-corrected target within the tilt/clearance bounds '
                f'(position_error_mm={np.linalg.norm(error[:3]):.3f}, yaw_error_deg={math.degrees(error[3]/60):.3f}, target={target.tolist()}, tilt_error={error[4]:.3f}, clearance={error[5:].tolist()}, q={result.x.tolist()})')
        actual=robot.fk(np.r_[out[:5],0.])
        solved.append(dict(tcp_raise_mm=float(actual[2,3]-target[2]),
            tool_tilt_deg=math.degrees(math.acos(float(np.clip(-actual[2,2],-1,1))))))
        return out
    front=[];seed=None
    for original in p['stages'][:3]:
        rows=stage_rows(original); ids=sparse_indices([rows])
        if original['phase']=='DIRECT_PREGRASP':
            target=solve(rows[-1],rows[-1]);qs=[qrow(p['start_firmware_rad']),target]
        else:
            qs=[]
            for i in ids:
                candidate=(seed.copy() if max_raise and original['phase']=='LIFT' and i==0
                    else solve(rows[i],seed if seed is not None else rows[i]))
                qs.append(candidate);seed=candidate
        seed=qs[-1]
        front.append(dict(phase=original['phase'],carrying=original['carrying'],rows=[q.tolist() for q in qs]))
        if original['phase']=='DESCEND':
            attachment=np.linalg.inv(robot.fk(np.r_[seed[:5],0.]))@newpose
    descend=front[1]['rows'][-1]
    oldlow=qrow(p['stages'][1]['stage']['target_firmware_rad'])
    p['tcp_from_object']=(np.linalg.inv(robot.fk(np.r_[np.array(descend)[:5],0.]))@newpose).tolist()
    p['initial_source_object_pose']=newpose.tolist();p['initial_object_pose']=newpose.tolist()
    p['request']['pickup']=dict(centre_mm=centre.tolist(),yaw_deg=yaw)
    p['request']['destination']['support_centre_mm'][2]=0  # Hand delivery: no stand.
    p['payload_placement_from_support']=False
    p['ab_transfer']=dict(delta_mm=delta.tolist(),yaw_delta_deg=dyaw,correction_policy='ALREADY_EMBODIED_IN_CLASS_ANCHOR')
    p['ab_transfer']['workspace_policy']=motion_policy
    p['ab_transfer']['source_ik_adjustments']=solved
    return p,front


def build_banks(name, centre, yaw, *, use_cache=True, selected_profile=None, grasp_policy=None):
    p,front=transfer(name,centre,yaw,selected_profile=selected_profile,grasp_policy=grasp_policy)
    folder=ROOT/'candidate/mode_ab/profiles'/p['ab_profile_id']
    if use_cache and (folder/'native_bank0.json').exists():
        banks=[]
        for i in range(3):
            plan=read(folder/f'native_bank{i}.json')
            for key in ('request','tcp_from_object','initial_source_object_pose','initial_object_pose','ab_transfer','ab_profile_id','ab_source'):
                plan[key]=deepcopy(p[key])
            plan['request']['destination']['support_centre_mm'][1]=135+60*i
            first=plan['stages'][0]
            first['start_firmware_rad']=dict(zip(NAMES,front[-1]['rows'][-1]))
            first['stage']['stream_frames']=[dict(command_firmware_rad=first['stage']['target_firmware_rad'])]
            plan['ab_transit_policy']='NORMALIZE_TO_CLASS_INNER_THEN_REUSE_CHECKED_HANDOVER_BANKS'
            robot,_=objects(plan)
            placed=qrow(next(s for s in plan['stages'] if s['phase']=='PLACE')['stage']['target_firmware_rad'])
            plan['released_object_pose']=(robot.fk(np.r_[placed[:5],0.])@np.array(plan['tcp_from_object'])).tolist()
            banks.append(plan)
        return banks,front
    banks=[]
    for bank in range(3):
        plan=deepcopy(p);plan['filid_bank']=bank;plan['stages']=[];plan['speed_multiplier']=3
        plan['request']['destination']['support_centre_mm'][1]=135+60*bank
        build_postlift_connection(plan,np.array(front[-1]['rows'][-1]))
        banks.append(plan)
    return banks,front


def compile_banks(banks,front, *, validate=True, validate_tail=True):
    """One dynamic OUT FIFO and three identically indexed handover tables."""
    points=[[] for _ in range(3)];segments=[];fifo=[];checks=0
    cached=[objects(p) for p in banks]
    minimum=float('inf')
    def check(p,q,carrying,phase,cache):
        nonlocal checks,minimum
        stats=geometry_check(p,np.array(q)/65536,carrying,cached=cache,phase='DESCEND' if phase in ('OPEN_SOURCE','GRASP_SOURCE') else phase)
        checks+=3;minimum=min(minimum,stats['minimum_model_clearance_mm'])
    def leg(qs,label,phase,carrying,flags, *, out=False):
        nonlocal checks,minimum
        metas=[]
        for bank,(start,target) in enumerate(qs):
            a=np.rint(np.array(start)*65536).astype(int).tolist();b=np.rint(np.array(target)*65536).astype(int).tolist()
            meta,_=segment(a,b,label,phase);metas.append(meta)
        n=max(m['n'] for m in metas)
        # Quantized tables and exactly the same UQ32 samples as production S2.
        for bank,((start,target),meta) in enumerate(zip(qs,metas)):
            from mode_a_upgrade_profile import scalar
            a=meta['start_q16'];b=meta['target_q16']
            if validate and (out and bank==1 or not out and validate_tail):
                values=[]
                for k in range(0,n+1):
                    s=scalar(k,n);qq=[y if k==n else x+(-1 if y<x else 1)*((abs(y-x)*s+(1<<31))>>32) for x,y in zip(a,b)]
                    values.append(qq)
                from pc.mode_ab.geometry import validate as batch_validate
                stats=batch_validate(banks[bank],np.array(values)/65536,carrying,
                    'DESCEND' if label in ('OPEN_SOURCE','GRASP_SOURCE') else label,cached[bank])
                checks+=stats['samples_checked'];minimum=min(minimum,stats['minimum_model_clearance_mm'])
                wire=batch_validate(banks[bank],np.round(np.array(values)/65536,4),carrying,
                    'DESCEND' if label in ('OPEN_SOURCE','GRASP_SOURCE') else label,cached[bank])
                checks+=wire['samples_checked'];minimum=min(minimum,wire['minimum_model_clearance_mm'])
            if out:
                continue
            points[bank].append(b)
        if out:
            fifo.append(dict(target_q16=metas[0]['target_q16'],n=n,na=n//4,profile=1,flags=flags,label=label,carrying=carrying))
        else:
            segments.append([len(points[0])-1,n,n//4,1,flags])
    q=np.array(front[0]['rows'][0]);opened=json.loads(banks[0]['open_before_descent_wire_json'])['cmd']
    closed=json.loads(banks[0]['close_after_descent_wire_json'])['cmd']
    for st in front:
        label=st['phase']
        if label in ('DESCEND','LIFT'):
            g=opened if label=='DESCEND' else closed;t=q.copy();t[5]=g
            leg([(q,t)]*3,'OPEN_SOURCE' if label=='DESCEND' else 'GRASP_SOURCE','grasp',False,3 if label=='LIFT' else 2,out=True);q=t
        for row in st['rows'][1:]:
            t=np.array(row);t[5]=q[5]
            leg([(q,t)]*3,label,'motion',st['carrying'],2,out=True);q=t
    # Source grasp/lift is dynamic. Transport to central PRE is also in OUT.
    for idx in range(3):
        st=banks[1]['stages'][idx];rows=stage_rows(st)
        # A joint-space shortcut is collision checked at every production tick.
        for a,b in zip(rows[sparse_indices([rows],.06)][:-1],rows[sparse_indices([rows],.06)][1:]):
            leg([(a,b)]*3,st['phase'],'motion',True,2,out=True)
    # Common PRE point index is required by the hand alignment hardware.
    for bank in range(3):
        points[bank].append(np.rint(qrow(banks[bank]['stages'][2]['stage']['target_firmware_rad'])*65536).astype(int).tolist())
    pre_kp=0;desc={}
    previous=[qrow(p['stages'][2]['stage']['target_firmware_rad']) for p in banks]
    for stage_index in range(3,len(banks[0]['stages'])):
        sts=[p['stages'][stage_index] for p in banks];label=sts[0]['phase']
        if label=='RELEASE_CLEARANCE':
            first=len(segments);targets=[]
            for q in previous:
                target=q.copy();target[5]=opened;targets.append(target)
            leg(list(zip(previous,targets)),'RELEASE_HAND','release',False,2);previous=targets
            desc['release']=[first,1]
        rows=[stage_rows(s) for s in sts]
        # Reparameterize dense curves by sample fraction before sharing indices.
        count=max(map(len,rows));u=np.linspace(0,1,count)
        common=[np.array([np.interp(u,np.linspace(0,1,len(x)),x[:,j]) for j in range(6)]).T for x in rows]
        ids=sparse_indices(common,.004 if label in ('PLACE','RELEASE_CLEARANCE') else .035)
        first=len(segments)
        for index in ids[1:]:
            targets=[x[index].copy() for x in common]
            for b,t in enumerate(targets):t[5]=previous[b][5]
            leg(list(zip(previous,targets)),'HANDOVER_'+label if label=='PLACE' else ('HAND_CLEAR_'+label if label in ('RELEASE_CLEARANCE','RETREAT') else label),
                'motion',sts[0]['carrying'],2);previous=targets
        if label=='PLACE':desc['deliver']=[first,len(segments)-first]
    # Close empty gripper at the class-independent low HOME.
    targets=[]
    for q in previous:
        t=q.copy();t[5]=float(json.loads(banks[0]['park_close_wire_json'])['cmd']);targets.append(t)
    leg(list(zip(previous,targets)),'PARK_EMPTY','motion',False,2)
    desc['retreat']=[sum(desc[k][1] for k in ('deliver','release')),len(segments)-sum(desc[k][1] for k in ('deliver','release'))]
    home_kp=len(points[0])-1
    if len(fifo)+desc['deliver'][1]>63 or len(segments)>64 or len(points[0])>64:
        raise ValueError(f'B capacity: FIFO {len(fifo)} + deliver {desc["deliver"][1]}, segments {len(segments)}, points {len(points[0])}')
    return dict(schema='gesture.mode_ab.compiled_b.v1',task_abi=0x340d,fifo=fifo,
                keypoint_banks=points+[deepcopy(points[1])],segments=segments,descriptors=desc,
                predelivery_kp=pre_kp,home_kp=home_kp,
                geometry=dict(samples_checked=checks,minimum_model_clearance_mm=minimum),
                speed=dict(native_spd=1320,native_acc=66,period_ms=20,scalar='A_QUINTIC_UQ32'),
                physical_test='NOT_RUN')


def native_with_front(plan,front):
    p=deepcopy(plan);stages=[]
    for source in front:
        rows=source['rows']
        stages.append(dict(phase=source['phase'],carrying=source['carrying'],
            start_firmware_rad=dict(zip(NAMES,rows[0])),stage=dict(
            stream_frames=[dict(command_firmware_rad=dict(zip(NAMES,q))) for q in rows],
            target_firmware_rad=dict(zip(NAMES,rows[-1])))))
    # Cached transport connectors can contain only their target frame. The
    # frozen return builder reverses stream_frames, so retain the start too.
    for stage in p['stages']:
        frames=stage['stage']['stream_frames'];start=stage['start_firmware_rad']
        if qrow(frames[0]['command_firmware_rad']).tolist()!=qrow(start).tolist():
            frames.insert(0,dict(command_firmware_rad=deepcopy(start)))
        if len(frames)==1:frames.append(deepcopy(frames[0]))
    p['stages']=stages+p['stages'];p['start_firmware_rad']=dict(zip(NAMES,home('B')))
    return p


def restock_native(original,origin_path):
    """Bind to a real PL-completed origin; do not fabricate teammate acceptance."""
    if original.get('ab_profile_id')=='red_depth12':
        # Giao's -12 mm is explicitly PICKUP_ONLY. Preserve the previously
        # checked public +8 mm return strategy, not the deep source attachment.
        pickup=original['request']['pickup']
        banks,front=build_banks('red_cube',pickup['centre_mm'],pickup['yaw_deg'],selected_profile='red_legacy')
        p=restock_native(native_with_front(banks[1],front),origin_path)
        p['ab_return_policy']='LEGACY_PUBLIC8_AND_ORIGINAL_DESKTOP_POSE; NO_DEPTH12_PROPAGATION'
        return p
    from prepare_mode_b_restock import Builder
    origin=read(origin_path)
    record=dict(original_pickup=original['request']['pickup'],original_task_id=str(origin['task_id']),
                grasp_command_firmware_rad=original['stages'][1]['stage']['target_firmware_rad'])
    b=Builder(original,record,Path(origin_path));st={s['phase']:s for s in original['stages']}
    q=lambda phase:qrow(st[phase]['stage']['target_firmware_rad'])
    b.q=np.array(home('B'));b.q[5]=b.opened
    b.append('RESTOCK_INNER_OPEN',[b.q.copy(),q('INNER_HOLD')],carrying=False)
    b.reference('RESTOCK_BUFFER_OPEN',st['BUFFER'],carrying=False)
    height=float(original['request']['pickup']['centre_mm'][2])
    b.cartesian('RESTOCK_PUBLIC_HIGH',[300,200,height+65],carrying=False,axis=[0,0,1])
    descend=b.cartesian('RESTOCK_PUBLIC_DESCEND',[300,200,height+.5],carrying=False,axis=[0,0,1],tighten=True)
    public=b.pose(b.q)
    if original['request']['object_class']=='red_cube':
        # The only measured public depth correction is red's additional 8 mm.
        before=deepcopy(descend);b.p['stages'].pop();b.q=qrow(before['start_firmware_rad'])
        descend=b.cartesian('RESTOCK_PUBLIC_DESCEND',public[:3,3]+[0,0,-8],carrying=False,axis=public[:3,2],tighten=True)
        b.attach=np.linalg.inv(b.robot.fk(np.r_[b.q[:5],0.]))@public
        b.robot.payload_attachment=b.attach.copy();b.p['tcp_from_object']=b.attach.tolist()
        b.p['ab_public_red_depth_mm']=8
    b.p['initial_source_object_pose']=public.tolist();b.p['initial_object_pose']=public.tolist()
    b.q[5]=b.closed
    b.reference('RESTOCK_PUBLIC_LIFT',descend,carrying=True,reverse=True)
    b.reference('RESTOCK_RETURN_BUFFER',next(s for s in b.p['stages'] if s['phase']=='RESTOCK_PUBLIC_HIGH'),carrying=True,reverse=True)
    b.reference('RESTOCK_RETURN_INNER',st['BUFFER'],carrying=True,reverse=True)
    b.reference('RESTOCK_SOURCE_HIGH',st['INNER_HOLD'],carrying=True,reverse=True)
    b.reference('RESTOCK_SOURCE_DESCEND',st['LIFT'],carrying=True,reverse=True)
    desired=np.array(original['initial_source_object_pose'])
    if np.max(abs(b.pose(b.q)-desired))>.002:
        last=b.p['stages'].pop();start=qrow(last['start_firmware_rad'])
        knots=[qrow(f['command_firmware_rad']) for f in last['stage']['stream_frames']][::3]
        knots[0]=start;seed=knots[-1]
        old=b.pose(seed)
        for u in np.linspace(0,1,9)[1:]:
            axis=(1-u)*old[:3,2]+u*desired[:3,2];axis/=np.linalg.norm(axis)
            seed=b.ik((1-u)*old[:3,3]+u*desired[:3,3],axis,seed,0);knots.append(seed)
        b.q=start;b.append('RESTOCK_SOURCE_DESCEND',knots,carrying=True)
    returned=b.pose(b.q)
    if np.linalg.norm(returned[:3,3]-desired[:3,3])>.15:
        raise ValueError('Restock did not preserve the frozen original source centre')
    b.p['released_object_pose']=returned.tolist();b.p['release_after_stage']='RESTOCK_SOURCE_DESCEND'
    b.q[5]=b.opened
    if original.get('ab_transfer',{}).get('workspace_policy',{}).get('maximum_grasp_tcp_raise_mm',0):
        # At a far source the old 8 mm sideways exit can demand extra reach.
        # Reuse the exact already-checked open-jaw descent in reverse instead.
        low=q('DESCEND');low[5]=b.opened
        b.append('RESTOCK_SOURCE_EXIT_CLEARANCE',[b.q.copy(),low],carrying=False)
        b.reference('RESTOCK_SOURCE_EXIT_UP',st['DESCEND'],carrying=False,reverse=True)
        b.p['ab_empty_source_exit']='REVERSE_VALIDATED_OPEN_DESCENT'
    else:
        b.withdraw('RESTOCK_SOURCE_EXIT',high_q=q('DIRECT_PREGRASP'))
    b.reference('RESTOCK_HOME',st['DIRECT_PREGRASP'],carrying=False,reverse=True)
    b.p['stationary_source_phases']=['RESTOCK_INNER_OPEN','RESTOCK_BUFFER_OPEN','RESTOCK_PUBLIC_HIGH','RESTOCK_PUBLIC_DESCEND']
    b.p['event_after_stage']={'RESTOCK_PUBLIC_DESCEND':'GRASP','RESTOCK_SOURCE_DESCEND':'RELEASE'}
    b.p['ab_origin_sha256']=hashlib.sha256(Path(origin_path).read_bytes()).hexdigest()
    return b.p


def compile_restock(p):
    from pc.mode_ab.geometry import validate
    cache=objects(p);current=np.array(home('B'));fifo=[];release=None;checks=0;minimum=float('inf')
    opened=float(json.loads(p['open_before_descent_wire_json'])['cmd'])
    closed=float(json.loads(p['close_after_descent_wire_json'])['cmd'])
    from mode_a_upgrade_profile import scalar
    # Preserve tight descent/clearance knots. At far sources the extra empty
    # withdrawal connector can otherwise consume a 64th FIFO slot. Compact
    # only transit chords, then check every resulting FPGA/wire sample below.
    prepared=[];transit_tolerance=.06
    for tolerance in (.06,.07,.08,.10):
        prepared=[];count=2+len(p['event_after_stage'])
        for stage in p['stages']:
            rows=stage_rows(stage)
            ids=sparse_indices([rows],.004 if ('DESCEND' in stage['phase'] or 'CLEARANCE' in stage['phase']) else tolerance)
            prepared.append((stage,rows,ids));count+=len(ids)-1
        if count<=63:
            transit_tolerance=tolerance;break
    def add(target,label,carrying,flags=2):
        nonlocal current,checks,minimum
        a=np.rint(current*65536).astype(int).tolist();b=np.rint(target*65536).astype(int).tolist()
        m,ss=segment(a,b,label,'release' if label=='RELEASE_SOURCE' else 'motion')
        qs=np.array([a]+ss)/65536
        phase='RESTOCK_PUBLIC_DESCEND' if label=='GRASP_PUBLIC' else ('RESTOCK_SOURCE_EXIT_CLEARANCE' if label=='RELEASE_SOURCE' else label)
        stats=validate(p,qs,carrying,phase,cache);checks+=stats['samples_checked'];minimum=min(minimum,stats['minimum_model_clearance_mm'])
        wire=validate(p,np.round(qs,4),carrying,phase,cache);checks+=wire['samples_checked'];minimum=min(minimum,wire['minimum_model_clearance_mm'])
        fifo.append(dict(target_q16=b,n=m['n'],na=m['na'],profile=1,flags=flags,label=label,carrying=carrying));current=np.array(target)
    target=current.copy();target[5]=opened;add(target,'RESTOCK_INNER_OPEN',False)
    for st,rows,ids in prepared:
        for i in ids[1:]:
            target=rows[i].copy();target[5]=current[5];add(target,st['phase'],st['carrying'])
        event=p['event_after_stage'].get(st['phase'])
        if event:
            target=current.copy();target[5]=closed if event=='GRASP' else opened
            if event=='RELEASE':release=len(fifo)
            add(target,'GRASP_PUBLIC' if event=='GRASP' else 'RELEASE_SOURCE',False,3 if event=='GRASP' else 2)
    add(np.array(home('B')),'RESTOCK_HOME',False)
    if release is None or len(fifo)>63:raise ValueError(f'Restock FIFO capacity: {len(fifo)}')
    return dict(schema='gesture.mode_ab.compiled_b.v1',task_abi=0x340d,fifo=fifo,restock=True,release_index=release,
                geometry=dict(samples_checked=checks,minimum_model_clearance_mm=minimum),
                transit_chord_tolerance_rad=transit_tolerance,physical_test='NOT_RUN')
