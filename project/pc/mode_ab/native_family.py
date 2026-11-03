"""Exhaustive native B handover family plus source-independent cached proof."""
from copy import deepcopy
import hashlib,json,itertools,inspect
import numpy as np
from scipy.spatial.transform import Rotation
from pc.mode_ab.native_routes import ROOT
from pc.mode_ab.geometry import validate
from pc.mode_ab.family import samples
from mode_a_upgrade_profile import align_steps
from prepare_mode_b_loaded_route import objects,payload_spec

def trajectory(program,stage,step):
    b=2 if step==64 else step//32;w=0 if step==64 else step%32
    hi=b+(w!=0);d=np.array(program['descriptors']).reshape(3,16,4)
    nlo=d[b,stage,0]>>16;nhi=d[hi,stage,0]>>16;n=max(nlo,nhi)
    def index(count):return np.zeros(1,dtype=np.int64) if n==1 else np.arange(n)*(count-1)//(n-1)
    data=np.array(program['offsets'],dtype=np.int64)+program['bases']
    a=data[(d[b,stage,0]&2047)+index(nlo)];z=data[(d[hi,stage,0]&2047)+index(nhi)]
    return (a*(32-w)+z*w+16)//32

def wire(q):
    return np.sign(q)*((abs(q)*10000+32768)//65536)/10000

def fingerprint(c,p):
    robot,world=objects(p)
    value=dict(urdf=robot.sha256,scene=p['local_scene_config'],grasp=robot.grasp.tolist(),
        world=robot.world.tolist(),bias=robot.bias.tolist(),tool=robot.tool_residual.tolist(),
        limits=robot.limits.tolist(),table=world.table_clearance_by_link,margin=world.margin,
        obstacles=[dict(name=o.name,centre=o.centre.tolist(),axes=o.axes.tolist(),half=o.half.tolist()) for o in world.obstacles],
        program_tail=[trajectory(c['native_program'],s,k).tolist() for k in range(65) for s in range(8,16)],
        pre_points=[b[0] for b in c['keypoint_banks'][:3]],
        algorithms={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
            ('pc/mode_ab/geometry.py','scripts/mode_a_upgrade_profile.py')},
        native_sampling_sha256=hashlib.sha256((inspect.getsource(trajectory)+inspect.getsource(wire)).encode()).hexdigest())
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def bound(cert,c,p,key):
    if not cert or cert.get('fingerprint')!=key or not cert.get('passed'):return None
    old=np.array(cert['tcp_from_object']);new=np.array(p['tcp_from_object'])
    corners=np.array(list(itertools.product((-1,1),repeat=3)))*np.array(payload_spec(p)['size_mm'])/2
    d=np.linalg.norm(corners@(new[:3,:3]-old[:3,:3]).T+new[:3,3]-old[:3,3],axis=1).max()
    angle=np.degrees(Rotation.from_matrix(new[:3,:3]@old[:3,:3].T).magnitude())
    if d+1e-6>=cert['payload_margin_mm'] or angle+1e-6>=cert['loaded_tilt_margin_deg']:return None
    return dict(passed=True,method='BOUND_RIGID_PAYLOAD_DISPLACEMENT_NATIVE',fingerprint=key,
        handover_steps=65,ordered_retarget_pairs=4160,payload_displacement_bound_mm=float(d),
        remaining_payload_margin_mm=float(cert['payload_margin_mm']-d),reference_model_samples=cert['model_samples_checked'],
        physical_test='NOT_RUN')

_proofs={}
def verify(c,p,*,use_cache=True):
    key=fingerprint(c,p)
    if use_cache:
        candidates=list(_proofs.get(key,[]))
        profile='red_cube' if p['ab_profile_id']=='red_depth12' else p['ab_profile_id']
        folder=ROOT/'candidate/mode_ab/native_profiles'/profile
        for path in sorted(folder.glob('family_certificate*.json')):
            candidates.append(json.loads(path.read_bytes()))
        hits=[hit for cert in candidates if (hit:=bound(cert,c,p,key)) is not None]
        if hits:return max(hits,key=lambda hit:hit['remaining_payload_margin_mm'])
    plan=deepcopy(p);cache=objects(plan);robot=cache[0];checked=0
    minimum=float('inf');payload_margin=float('inf');tilt_margin=float('inf')
    def check(q,carrying,label,static=None):
        nonlocal checked,minimum,payload_margin,tilt_margin
        for a in range(0,len(q),2048):
            chunk=q[a:a+2048]
            if static is not None:plan['_ab_static_object_poses']=static[a:a+2048]
            for values in (chunk/65536,wire(chunk)):
                stats=validate(plan,values,carrying,label,cache);checked+=stats['samples_checked']
                minimum=min(minimum,stats['minimum_model_clearance_mm']);payload_margin=min(payload_margin,stats['payload_margin_mm']);tilt_margin=min(tilt_margin,stats['loaded_tilt_margin_deg'])
        plan.pop('_ab_static_object_poses',None)
    loaded=[];empty=[];poses=[];pre=[]
    for step in range(65):
        q=trajectory(c['native_program'],8,step);loaded.append(q)
        op=robot.fk(np.r_[q[-1,:5]/65536,0.])@np.array(plan['tcp_from_object'])
        for s in range(9,16):
            q=trajectory(c['native_program'],s,step);empty.append(q);poses.append(np.broadcast_to(op,(len(q),4,4)))
        bank=0 if step<32 else 1;weight=step-bank*32
        if step==64:bank=1;weight=32
        a=np.array(c['keypoint_banks'][bank][0]);b=np.array(c['keypoint_banks'][bank+1][0]);pre.append((a*(32-weight)+b*weight+16)//32)
    check(np.concatenate(loaded),True,'HANDOVER_FAMILY')
    check(np.concatenate(empty),False,'HAND_CLEAR_FAMILY',np.concatenate(poses))
    align=[]
    for a in pre:
        for b in pre:
            if np.array_equal(a,b):continue
            align.append(samples(a,b,align_steps(int(abs(a-b).max()))))
    if align:check(np.concatenate(align),True,'HANDOVER_ALIGN')
    result=dict(passed=True,method='FULL_NATIVE_GEOMETRY',handover_steps=65,ordered_retarget_pairs=4160,
        model_samples_checked=checked,minimum_model_clearance_mm=minimum,payload_margin_mm=payload_margin,
        loaded_tilt_margin_deg=tilt_margin,fingerprint=key,tcp_from_object=plan['tcp_from_object'],
        exact_native_q16_and_wire_rounding=True,physical_test='NOT_RUN')
    _proofs.setdefault(key,[]).append(result)
    return result
