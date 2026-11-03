"""Validate every handover target and retarget pair for a fresh B attachment."""
from copy import deepcopy
import hashlib
import itertools
import json
import numpy as np
from scipy.spatial.transform import Rotation
from pc.mode_ab.motion import ROOT
from pc.mode_ab.geometry import validate
from prepare_mode_b_loaded_route import objects
from mode_a_upgrade_profile import scalar,align_steps


def samples(a,b,n):
    return np.array([[y if k==n else x+(-1 if y<x else 1)*((abs(y-x)*scalar(k,n)+(1<<31))>>32) for x,y in zip(a,b)] for k in range(n+1)],dtype=np.int64)


def mixed(c,step):
    lo=0 if step<32 else 1;w=step-lo*32
    a=np.array(c['keypoint_banks'][lo]);b=np.array(c['keypoint_banks'][lo+1])
    return (a*(32-w)+b*w+16)//32


def fingerprint(c,plan):
    """Bind a proof to every trajectory, model and collision input it uses."""
    robot,world=objects(plan)
    def array(value):return np.asarray(value).tolist()
    model=dict(urdf=robot.sha256,limits=array(robot.limits),world=array(robot.world),
        bias=array(robot.bias),grasp=array(robot.grasp),tool=array(robot.tool_residual),
        boxes={k:[array(a) for a in v] for k,v in robot.boxes.items()},
        origins={k:array(v) for k,v in robot.origins.items()},
        axes={k:array(v) for k,v in robot.axes.items()},parents=robot.parents,children=robot.children)
    value=dict(model=model,scene=plan['local_scene_config'],adapter=plan.get('object_adapter'),
        class_name=plan['request']['object_class'],profile=plan.get('ab_profile_id'),
        stationary_source_phases=plan.get('stationary_source_phases',[]),
        obstacles=[dict(name=o.name,centre=array(o.centre),axes=array(o.axes),half=array(o.half))
                   for o in world.obstacles+([world.support] if world.support else [])],
        self_pairs=world.self_pairs,margin=world.margin,table=world.table_clearance_by_link,
        tilt=plan['commissioning_tolerance_profile']['loaded_pitch_limit_from_vertical_deg'],
        tables={k:c[k] for k in ('keypoint_banks','segments','descriptors','predelivery_kp','home_kp')},
        algorithms={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
            ('pc/mode_ab/family.py','pc/mode_ab/geometry.py','scripts/mode_a_upgrade_profile.py',
             'pc/mode_b/motion/kinematics.py','pc/mode_b/motion/collision.py','scripts/prepare_mode_b_loaded_route.py')})
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def certificate(c,plan):
    """Rigid corner-displacement bound; fall back if any premise differs.

    All 65 targets and 4160 retargets share the same grasp frames after PRE.
    Moving every payload vertex by at most d preserves each reference separating
    plane and height inequality with spare clearance > d. Robot geometry and
    joint limits are unchanged. The relative rotation bounds the loaded tilt.
    Fresh source/connector FIFO samples are always checked separately.
    """
    path=ROOT/'candidate/mode_ab/profiles'/plan['ab_profile_id']/'family_certificate.json'
    if not path.exists():return None
    cert=json.loads(path.read_bytes())
    proof=cert.get('proof',{})
    if (cert.get('schema')!='gesture.mode_ab.family_certificate.v1' or cert.get('fingerprint')!=fingerprint(c,plan)
        or not proof.get('passed') or proof.get('method')!='FULL_GEOMETRY'
        or proof.get('handover_steps')!=65 or proof.get('ordered_retarget_pairs')!=4160
        or proof.get('native_rounding_checked') is not True):return None
    old=np.asarray(cert['tcp_from_object']);new=np.asarray(plan['tcp_from_object'])
    for a in (old,new):
        if a.shape!=(4,4) or not np.isfinite(a).all() or not np.allclose(a[3],[0,0,0,1],atol=1e-10):return None
        if not np.allclose(a[:3,:3].T@a[:3,:3],np.eye(3),atol=1e-8) or np.linalg.det(a[:3,:3])<.999999:return None
    from prepare_mode_b_loaded_route import payload_spec
    corners=np.array(list(itertools.product((-1,1),repeat=3)))*np.array(payload_spec(plan)['size_mm'])/2
    d=float(np.linalg.norm(corners@(new[:3,:3]-old[:3,:3]).T+new[:3,3]-old[:3,3],axis=1).max())
    angle=float(np.degrees(Rotation.from_matrix(new[:3,:3]@old[:3,:3].T).magnitude()))
    if not np.isfinite([proof['payload_margin_mm'],proof['loaded_tilt_margin_deg']]).all():return None
    if d+1e-6>=proof['payload_margin_mm'] or angle+1e-6>=proof['loaded_tilt_margin_deg']:return None
    return dict(passed=True,method='BOUND_RIGID_PAYLOAD_DISPLACEMENT',fingerprint=cert['fingerprint'],
        reference_model_samples=proof['model_samples_checked'],model_samples_checked=0,
        handover_steps=65,ordered_retarget_pairs=4160,native_rounding_checked=True,
        payload_displacement_bound_mm=d,remaining_payload_margin_mm=proof['payload_margin_mm']-d,
        attachment_rotation_deg=angle,remaining_tilt_margin_deg=proof['loaded_tilt_margin_deg']-angle,
        physical_test='NOT_RUN')


def verify(c,plan, *, wire=True, use_certificate=True):
    if use_certificate and wire:
        result=certificate(c,plan)
        if result:return result
    p=deepcopy(plan);cache=objects(p);robot=cache[0]
    checked=0;minimum=float('inf');payload_margin=float('inf');tilt_margin=float('inf');loaded=[];unloaded=[];poses=[]
    release=c['descriptors']['release'][0];deliver_last=release-1
    for step in range(65):
        points=mixed(c,step);place=points[c['segments'][deliver_last][0]]/65536
        pose=robot.fk(np.r_[place[:5],0.])@np.array(p['tcp_from_object'])
        current=points[c['predelivery_kp']]
        for i,(kp,n,na,profile,flags) in enumerate(c['segments']):
            target=points[kp];q=samples(current,target,n)/65536
            if i<release:loaded.append(q)
            else:
                unloaded.append(q);poses.append(np.broadcast_to(pose,(len(q),4,4)))
            current=target
    def batches(qs,carrying,phase,static=None,rounding=False):
        nonlocal checked,minimum,payload_margin,tilt_margin
        for start in range(0,len(qs),4096):
            x=qs[start:start+4096]
            if rounding:x=np.round(x,4)
            if static is not None:p['_ab_static_object_poses']=static[start:start+4096]
            stats=validate(p,x,carrying,phase,cache)
            checked+=stats['samples_checked'];minimum=min(minimum,stats['minimum_model_clearance_mm'])
            payload_margin=min(payload_margin,stats['payload_margin_mm']);tilt_margin=min(tilt_margin,stats['loaded_tilt_margin_deg'])
        p.pop('_ab_static_object_poses',None)
    a=np.concatenate(loaded);b=np.concatenate(unloaded);static=np.concatenate(poses)
    batches(a,True,'HANDOVER_FAMILY');batches(b,False,'HAND_CLEAR_FAMILY',static)
    if wire:
        batches(a,True,'HANDOVER_FAMILY_WIRE',rounding=True)
        batches(b,False,'HAND_CLEAR_FAMILY_WIRE',static,rounding=True)
    pre=[mixed(c,i)[c['predelivery_kp']] for i in range(65)]
    blocks=[];length=0
    for i,qa in enumerate(pre):
        for j,qb in enumerate(pre):
            if i==j:continue
            n=align_steps(int(abs(qa-qb).max()));q=samples(qa,qb,n)/65536
            blocks.append(q);length+=len(q)
            if length>4096:
                batches(np.concatenate(blocks),True,'HANDOVER_ALIGN');blocks=[];length=0
    if blocks:batches(np.concatenate(blocks),True,'HANDOVER_ALIGN')
    return dict(passed=True,method='FULL_GEOMETRY',handover_steps=65,ordered_retarget_pairs=4160,model_samples_checked=checked,
                payload_margin_mm=payload_margin,loaded_tilt_margin_deg=tilt_margin,
                minimum_clearance_mm=minimum,native_rounding_checked=wire,physical_test='NOT_RUN')
