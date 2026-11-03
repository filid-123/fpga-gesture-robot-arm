"""Giao native sampled routes for the ABI340E B-only PL program player.

A keeps its existing P2P quintics. B preserves phase samples, per-phase wire
profiles and 20/40 ms clocks; Q16 offsets compress storage without losing bits.
No camera, transport or actuator access occurs in this module.
"""
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import hashlib,json,math
import numpy as np
from scipy.interpolate import PchipInterpolator
from pc.mode_ab.motion import (ROOT,NAMES,template,transfer,qrow,stage_rows,home,
    build_postlift_connection,native_with_front)
from pc.mode_ab.geometry import validate
from prepare_mode_b_loaded_route import objects

ABI=0x340e
FAST=0x80
DEPTH=2048

def quintic(u):return u*u*u*(10+u*(-15+6*u))

def limit_source_rates(rows,reference,period):
    """Retain the source phase's demonstrated peak rates after translation."""
    def rates(q):
        v=np.diff(q[:,:5],axis=0)/period
        a=np.diff(v,axis=0)/period
        return float(abs(v).max(initial=0)),float(abs(a).max(initial=0))
    rv,ra=rates(reference);v,a=rates(rows)
    # Source adaptations keep the established A acceleration/velocity envelope;
    # exact demonstrated Giao samples are left untouched by the caller.
    factor=max(1,v/max(rv*1.02,math.radians(72.6)),math.sqrt(a/max(ra*1.02,math.radians(320))))
    if factor<=1:return rows
    count=math.ceil((len(rows)-1)*factor)
    if count>1200:raise ValueError('Source motion exceeds bounded native duration/capacity')
    return np.array([np.interp(np.linspace(0,1,count+1),np.linspace(0,1,len(rows)),rows[:,j]) for j in range(6)]).T

@lru_cache(maxsize=3)
def reference_banks(name):
    original=template(name);plans=[]
    folder=ROOT/'candidate/mode_ab/native_profiles'/name;manifest=folder/'reference_manifest.json'
    if manifest.exists():
        record=json.loads(manifest.read_bytes())
        if (record.get('schema')=='gesture.mode_ab.native_reference.v1' and record.get('giao_source')==original['ab_source']
            and record.get('builder_sha256')==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()):
            paths=[folder/f'native_bank{i}.json' for i in range(3)]
            if all(q.exists() and hashlib.sha256(q.read_bytes()).hexdigest()==record['files'].get(q.name) for q in paths):
                return [json.loads(q.read_bytes()) for q in paths]
    for bank in range(3):
        p=deepcopy(original)
        if bank!=1:
            p['stages']=[];p['filid_bank']=bank
            p['request']['destination']['support_centre_mm'][1]=135+60*bank
            build_postlift_connection(p,qrow(original['stages'][2]['stage']['target_firmware_rad']))
        else:p['stages']=p['stages'][3:]
        p['ab_hand_reference_plane_mm']=deepcopy(p['request']['destination']['support_centre_mm'])
        p['request']['destination']['support_centre_mm'][2]=0
        p['ab_delivery_fixture']='PALM_NO_PHYSICAL_STAND'
        plans.append(p)
    return plans

def motion_stage(label,rows,period,wire,carrying):
    wire=deepcopy(wire)
    return dict(phase=label,carrying=carrying,start_firmware_rad=dict(zip(NAMES,rows[0].tolist())),
        stage=dict(period_s=period,stream_frames=[dict(command_firmware_rad=dict(zip(NAMES,q.tolist())),
            wire_json=json.dumps({**wire,**dict(zip(('base','shoulder','elbow','wrist','roll','hand'),q.tolist()))},separators=(',',':')))
            for q in rows[1:]],target_firmware_rad=dict(zip(NAMES,rows[-1].tolist())),nominal_motion_seconds=(len(rows)-1)*period))

def build(name,centre,yaw):
    anchor=template(name);p,front=transfer(name,centre,yaw)
    exact=np.max(abs(np.asarray(centre)-anchor['request']['pickup']['centre_mm']))<1e-9 and abs(p['ab_transfer']['yaw_delta_deg'])<1e-9
    dense_front=[]
    for original,f in zip(anchor['stages'][:3],front):
        old=stage_rows(original);knots=np.asarray(f['rows'])
        if exact:rows=old
        else:
            # Follow the reviewed transferred source knots using Giao's PCHIP
            # and monotone quintic time law, with the same phase period.
            if f['phase']=='DIRECT_PREGRASP':
                u=quintic(np.linspace(0,1,len(old)));rows=knots[0]+u[:,None]*(knots[-1]-knots[0])
            else:
                # Knots were selected in original sample time, so preserve
                # their timing rather than applying a second quintic warp.
                from pc.mode_ab.motion import sparse_indices
                ids=sparse_indices([old]);rows=np.array([np.interp(np.arange(len(old)),ids,knots[:,j]) for j in range(6)]).T
        period=original['stage']['period_s'];wire=json.loads(original['stage']['stream_frames'][0]['wire_json'])
        if not exact:rows=limit_source_rates(rows,old,period)
        if f['phase']=='DESCEND':rows[:,5]=json.loads(anchor['open_before_descent_wire_json'])['cmd']
        if f['phase']=='LIFT':rows[:,5]=json.loads(anchor['close_after_descent_wire_json'])['cmd']
        dense_front.append(motion_stage(f['phase'],rows,period,wire,f['carrying']))
    banks=deepcopy(reference_banks(name))
    connector_stage=None
    if not exact:
        reference=banks[1]['stages'][0]
        start=qrow(dense_front[-1]['stage']['target_firmware_rad']);target=qrow(reference['stage']['target_firmware_rad'])
        start[5]=target[5];delta=abs(target[:5]-start[:5]).max()
        seconds=max(reference['stage']['nominal_motion_seconds'],1.875*delta/math.radians(72.6),math.sqrt(5.774*delta/math.radians(320)))
        count=math.ceil(seconds/.02);rows=start+quintic(np.linspace(0,1,count+1))[:,None]*(target-start)
        command=json.loads(reference['stage']['stream_frames'][0]['wire_json'])
        connector_stage=motion_stage('INNER_HOLD',rows,.02,command,True)
    for bank,tail in enumerate(banks):
        for key in ('tcp_from_object','initial_source_object_pose','initial_object_pose','ab_transfer','ab_profile_id','ab_source'):
            tail[key]=deepcopy(p[key])
        tail['request']['pickup']=deepcopy(p['request']['pickup'])
        if not exact:
            # The source-to-INNER connector is regenerated with Giao's actual
            # curve builder. Canonical handover geometry remains class-specific.
            tail['stages'][0]=deepcopy(connector_stage)
        robot,_=objects(tail)
        place=next(s for s in tail['stages'] if s['phase']=='PLACE')
        tail['released_object_pose']=(robot.fk(np.r_[qrow(place['stage']['target_firmware_rad'])[:5],0.])@np.array(tail['tcp_from_object'])).tolist()
    native=deepcopy(banks[1]);native['stages']=deepcopy(dense_front)+native['stages']
    native['start_firmware_rad']=dict(zip(NAMES,home('B')))
    native['ab_route_policy']='GIAO_NATIVE_SAMPLES_PHASE_SPEEDS_AND_CORRECTED_CLASS_HANDOVER'
    return banks,dense_front,native

def stages_with_events(plan,front):
    """16 PL stages: original 12 motion phases and the four native T106 events."""
    rows=[];current=np.array(home('B'));opened=json.loads(plan['open_before_descent_wire_json'])
    close=json.loads(plan['close_after_descent_wire_json']);release=json.loads(plan['release_wire_json'])
    park=json.loads(plan['park_close_wire_json'])
    def event(name,command,carrying):
        nonlocal current
        q=current.copy();q[5]=command['cmd']
        # Giao execution.json: step travel / speed plus one second, then
        # fresh feedback. One PL descriptor is shared by forward/retrace;
        # cover the slower of their two explicit T106 speed profiles.
        reverse_speed=100 if name=='OPEN_SOURCE' else 300
        seconds=abs(q[5]-current[5])*4096/(2*math.pi)/min(command['spd'],reverse_speed)+1
        rows.append(dict(label=name,rows=np.rint(q[None,:]*65536).astype(np.int64),period=seconds,
            wire=command,carrying=carrying));current=q
    def motion(stage):
        nonlocal current
        q=np.array([qrow(f['command_firmware_rad']) for f in stage['stage']['stream_frames']])
        if stage['phase']!='DIRECT_PREGRASP':q[:,5]=current[5]
        wire=json.loads(stage['stage']['stream_frames'][0]['wire_json'])
        rows.append(dict(label=stage['phase'],rows=np.rint(q*65536).astype(np.int64),period=stage['stage']['period_s'],
            wire=wire,carrying=stage['carrying']));current=q[-1].copy()
    for stage in front:
        if stage['phase']=='DESCEND':event('OPEN_SOURCE',opened,False)
        if stage['phase']=='LIFT':event('GRASP_SOURCE',close,True)
        motion(stage)
    for stage in plan['stages']:
        if stage['phase']=='RELEASE_CLEARANCE':event('RELEASE_HAND',release,False)
        motion(stage)
    event('PARK_EMPTY',park,False)
    if len(rows)!=16:raise ValueError('Expected Giao 12 motion phases + 4 gripper events')
    return rows

def compile_routes(banks,front,*,validate_geometry=True):
    stages=[stages_with_events(p,front) for p in banks]
    # Prefix to PRE uses central path; other banks become active only at PRE.
    pre=next(i for i,s in enumerate(stages[1]) if s['label']=='PREPLACE')
    pre_points=[sequence[pre]['rows'][-1].tolist() for sequence in stages]
    place=pre+1;release=place+1
    for bank in (0,2):
        for i in range(pre+1):stages[bank][i]=deepcopy(stages[1][i])
    words=[];descriptors=[0]*192;checks=0;minimum=float('inf');periods=[]
    caches=[objects(p) for p in banks]
    for bank,sequence in enumerate(stages):
        for i,s in enumerate(sequence):
            q=s['rows'];command=s['wire'];grip=command['T']==106
            if command['T'] not in (102,106) or not(0<command['spd']<=3960 and 0<command['acc']<=254):raise ValueError('Native profile outside supported bounds')
            base=len(words);words.extend(q.tolist())
            # Prefix banks share one physical address range.
            if bank and i<=pre:
                words=words[:-len(q)];base=descriptors[i*4]&2047
            n=len(q);period=round(s['period']*100_000_000)
            if n==0 or base+n>DEPTH or not 2_000_000<=period<=(0xffffffff if grip else 100_000_000):raise ValueError('Native route memory/period capacity')
            profile=int(command['spd'])|(int(command['acc'])<<16)|(int(grip)<<24)
            reverse=profile
            if grip:reverse=(100 if s['label']=='OPEN_SOURCE' else 300)|20<<16|1<<24
            descriptors[(bank*16+i)*4:(bank*16+i)*4+4]=[base|(n<<16),period,profile,reverse]
            if bank==1:periods.append(n*s['period'])
            if validate_geometry and (bank==1 or i>pre):
                phase='DESCEND' if s['label'] in ('OPEN_SOURCE','GRASP_SOURCE') else s['label']
                carrying=s['carrying'] and s['label']!='GRASP_SOURCE'
                for values in (q/65536,np.round(q/65536,4)):
                    stats=validate(banks[bank],values,carrying,phase,caches[bank]);checks+=stats['samples_checked'];minimum=min(minimum,stats['minimum_model_clearance_mm'])
    data=np.array(words,dtype=np.int64);low=data.min(0);high=data.max(0);bases=(low+high)//2
    offsets=data-bases
    if offsets.min()<-(1<<17) or offsets.max()>=(1<<17):raise ValueError('Native Q16 channel span exceeds lossless 18-bit storage')
    points=[[] for _ in range(3)];fifo=[];segments=[]
    def duration(i):return max(math.ceil(len(stages[b][i]['rows'])*stages[b][i]['period']/.02) for b in range(3))
    for i in range(pre+1):
        s=stages[1][i];fifo.append(dict(target_q16=s['rows'][-1].tolist(),n=duration(i),na=i,profile=0,
            flags=FAST|2|(s['label']=='GRASP_SOURCE'),label=s['label'],carrying=s['carrying']))
    for b in range(3):
        points[b].append(pre_points[b])
    for i in range(place,16):
        for b in range(3):points[b].append(stages[b][i]['rows'][-1].tolist())
        segments.append([len(points[0])-1,duration(i),i,0,FAST|2])
    compiled=dict(schema='gesture.mode_ab.compiled_b.v2',task_abi=ABI,fifo=fifo,keypoint_banks=points+[deepcopy(points[1])],
        segments=segments,descriptors=dict(deliver=[0,1],release=[1,1],retreat=[2,len(segments)-2]),
        predelivery_kp=0,home_kp=len(points[0])-1,geometry=dict(samples_checked=checks,minimum_model_clearance_mm=minimum),
        native_program=dict(schema='gesture.mode_ab.native_program.v1',abi=0xb001,bases=bases.tolist(),
            offsets=offsets.tolist(),descriptors=descriptors,stage_count=16,points=len(words),labels=[s['label'] for s in stages[1]]),
        speed=dict(policy='GIAO_PER_PHASE_NATIVE',nominal_motion_seconds=sum(n*s['period'] for s in stages[1] if s['wire']['T']==102 for n in [len(s['rows'])]),
            nominal_with_gripper_waits_seconds=sum(periods),periods_ms=[20,40],scalar='GIAO_PCHIP_OR_JOINT_QUINTIC'),physical_test='NOT_RUN')
    return compiled

def program_hash(program):return hashlib.sha256(json.dumps(program,sort_keys=True,separators=(',',':')).encode()).hexdigest()
