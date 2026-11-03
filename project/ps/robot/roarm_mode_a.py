"""RoARM-M3-S Mode A bring-up. PS configures tables and logs; all live decisions remain PL."""
from pathlib import Path
import sys, argparse, json, time, math, hashlib, copy
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'sim/phase3_native_closed_loop'))
import bootstrap
import yaml
import arm_backend as ab
import arm_backend_axi_driver as ad
import planner_axi_driver as pd
import planner_p2p_reference as pr
import s4_task_axi_driver as sd
import s4_task_reference as m
from arm_profile import ArmProfile,sha256_file
from roarm_json_reference import RoArmJsonProtocol
from arm_fixed_point import rad_to_q16_16

POSES=['home','pre_delivery','delivery','delivery_open','retreat','tray_above','tray_drop','tray_open','tray_retreat']
for k in range(1,4): POSES += [f'obj{k}_{s}' for s in ('above','pick','grasp','lift')]
CHECKS=['base_fixed','wiring_verified','power_stop_tested','permit_switch_tested','feedback_rate_verified','limits_measured','all_empty_routes_tested','cube_grasp_tested','tray_route_tested','fixed_hand_height_measured','surrogate_palm_tested','camera_window_measured']
VBASE=0x43c60000
def dump(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def template(path):
    if Path(path).exists():raise FileExistsError('Preserve existing calibration; choose a new session filename')
    dump(path,dict(schema='gesture.roarm_mode_a.calibration.v1',firmware_version=None,serial_number=None,operator=None,
      measured_limits_rad=[None]*6,arrival_tolerance_rad=[0.02]*5+[0.04],poses={p:None for p in POSES},
      palm_window_locator_xyxy=None,palm_max_move_px=3,palm_window_frames=3,
      feedback_evidence=[],verified={k:False for k in CHECKS},period_ms=100,max_velocity_rad_s=0.25,max_accel_rad_s2=0.5))
def query(port,seconds=2):
    import serial
    serial_port=serial.Serial();serial_port.port=port;serial_port.baudrate=115200;serial_port.timeout=.1
    serial_port.dtr=False;serial_port.rts=False;serial_port.open()
    records=[]
    try:
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            serial_port.write(b'{"T":105}\n');deadline=time.monotonic()+.1
            while time.monotonic()<deadline:
                raw=serial_port.readline()
                if not raw:continue
                try:data=json.loads(raw)
                except (ValueError,UnicodeDecodeError):continue
                if data.get('T')==1051 and all(k in data for k in ['b','s','e','t','r','g']):
                    vals=[float(data[k]) for k in ['b','s','e','t','r','g']]
                    if not all(math.isfinite(v) for v in vals):raise ValueError('non-finite feedback')
                    records.append(dict(monotonic_s=time.monotonic(),position_rad=vals,packet=data));break
    finally:serial_port.close()
    if not records:raise RuntimeError('No complete T=1051 six-channel response; do not enable motion')
    return records
def compile_session(path,out,commission=False):
    # A failed recompile must not silently leave an older instance eligible for
    # motion after the user has changed the physical layout or measured poses.
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    pending=out/'COMPILATION_INCOMPLETE'
    pending.write_text('Motion blocked until this instance compiles successfully.\n',encoding='utf-8')
    path=Path(path).resolve();out=Path(out).resolve();c=json.loads(path.read_text(encoding='utf-8'))
    if c['schema']!='gesture.roarm_mode_a.calibration.v1':raise ValueError('calibration schema')
    missing=[k for k in ('firmware_version','serial_number','operator','palm_window_locator_xyxy') if not c.get(k)]
    missing += ['poses.'+k for k in POSES if c['poses'].get(k) is None]
    missing += ['limits'] if any(v is None for v in c['measured_limits_rad']) else []
    required_checks=CHECKS[:6] if commission else CHECKS
    missing += ['verified.'+k for k in required_checks if c['verified'].get(k) is not True]
    if not c.get('feedback_evidence'):missing.append('feedback_evidence')
    if missing:raise ValueError('Calibration incomplete: '+', '.join(missing))
    if not (100<=c['period_ms']<=160):raise ValueError('Bring-up period must be 100..160 ms (24-bit PL timer)')
    if not (0<c['max_velocity_rad_s']<=.25 and 0<c['max_accel_rad_s2']<=.5):raise ValueError('Initial velocity/acceleration cap exceeded')
    limits=c['measured_limits_rad'];vendor=[(-math.pi,math.pi),(-math.pi/2,math.pi/2),(0,math.pi),(-math.pi/2,math.pi/2),(-math.pi,math.pi),(1.08,math.pi)]
    for i,(lo,hi) in enumerate(limits):
        if not all(math.isfinite(v) for v in (lo,hi)) or not vendor[i][0]<=lo<hi<=vendor[i][1]:raise ValueError(f'joint{i} limits outside native documented envelope')
    for name,pose in c['poses'].items():
        if len(pose)!=6 or any(not math.isfinite(v) or not limits[i][0]<=v<=limits[i][1] for i,v in enumerate(pose)):raise ValueError(f'pose {name} violates measured limits')
    win=c['palm_window_locator_xyxy']
    if len(win)!=4 or not(0<win[0]<win[2]<128 and 16<win[1]<win[3]<112):raise ValueError('Palm window must stay inside letterbox content')
    profile=yaml.safe_load((ROOT/'config/arm_profiles/roarm_m3_pro.yaml').read_text(encoding='utf-8'))
    protocol=yaml.safe_load((ROOT/'config/protocols/roarm_m3_s_native_json.yaml').read_text(encoding='utf-8'));protocol['firmware_version']=c['firmware_version']
    out.mkdir(parents=True,exist_ok=True);protocol_path=out/'protocol.yaml';protocol_path.write_text(yaml.safe_dump(protocol,sort_keys=False),encoding='utf-8')
    profile.update(robot_model='RoARM-M3-S',profile_version='0.2.0',serial_number=c['serial_number'],real_output_enabled=True)
    profile['protocol']=dict(file='protocol.yaml',sha256=sha256_file(protocol_path));profile['transport'].update(port='PL_UART_D1_D0',half_duplex=None)
    profile['device_encoding'].update(fraction_digits=4,device_min=-40000,device_max=40000)
    for i,j in enumerate(profile['joints']):
        j.update(zero_device=0,direction=1,device_units_per_rad=10000.0,soft_min_rad=limits[i][0],soft_max_rad=limits[i][1],max_velocity_rad_s=c['max_velocity_rad_s'],max_accel_rad_s2=c['max_accel_rad_s2'],arrival_tolerance_rad=c['arrival_tolerance_rad'][i])
    opened=c['poses']['delivery_open'][5];closed=c['poses']['obj1_grasp'][5]
    if opened>=closed:raise ValueError('Native gripper must decrease to open')
    grip_tol=c['arrival_tolerance_rad'][5]
    for name in ['pre_delivery','delivery','tray_above','tray_drop']+[f'obj{k}_{s}' for k in (1,2,3) for s in ('grasp','lift')]:
        if abs(c['poses'][name][5]-closed)>grip_tol:raise ValueError(f'{name}: shared holding path must preserve calibrated grasp angle')
    for name in ['delivery_open','retreat','tray_open','tray_retreat']+[f'obj{k}_{s}' for k in (1,2,3) for s in ('above','pick')]:
        if abs(c['poses'][name][5]-opened)>grip_tol:raise ValueError(f'{name}: keep calibrated open angle through approach/retreat')
    profile['gripper'].update(open_rad=opened,closed_rad=closed,open_device=round(opened*10000),closed_device=round(closed*10000))
    profile['feedback'].update(required_channels=list(range(6)),arrival_consecutive=3)
    profile['timeouts'].update(command_timeout_ms=c['period_ms'],feedback_timeout_ms=500,overall_timeout_ms=60000,response_timeout_ms=None)
    evidence=out/'calibration_source.json';dump(evidence,c)
    profile['calibration'].update(date=time.strftime('%Y-%m-%d'),method='physical_measurement',operator=c['operator'],source_files=[dict(path=evidence.name,sha256=sha256_file(evidence))])
    profile['notes']=['Native radians, no simulation gripper mapping.','All live A selection, PALM, FIST and paths execute in PL.']
    profile_path=out/'profile.yaml';profile_path.write_text(yaml.safe_dump(profile,sort_keys=False),encoding='utf-8')
    cfg,tables=build_tables(c)
    dump(out/'table_preview.json',dict(keypoints=tables.keypoints,segments=tables.segments,register_writes=sd.table_writes(tables),commissioning_only=commission))
    pending.unlink()
    return dict(result='PASS',profile=str(profile_path),segments=sum(d[1] for d in list(tables.approach.values())+list(tables.grasp.values())+list(tables.lift.values())+[tables.deliver,tables.release,tables.retreat,tables.tray]),commissioning_only=commission)
def build_tables(c):
    q={name:tuple(rad_to_q16_16(v) for v in pose) for name,pose in c['poses'].items()}
    t=m.S4Tables();indices={name:i for i,name in enumerate(POSES)}
    for name,i in indices.items():t.keypoints[i]=q[name]
    p=c['period_ms']/1000;v=math.floor(c['max_velocity_rad_s']*p*65536);a=math.floor(c['max_accel_rad_s2']*p*p*(1<<32))
    offset=0
    def path(names,previous):
        nonlocal offset
        start=offset
        for name,flags in names:
            # A partial stop/retrace is within this commissioned edge's full displacement.
            delta=max(abs(q[name][i]-q[previous][i]) for i in range(6))
            n=max(4,math.ceil(2*delta/max(1,v))+2,math.ceil(2*math.sqrt(delta*65536/max(1,a)))+2);n+=n%2
            if n>65535:raise ValueError('segment N out of range')
            t.segments[offset]=(indices[name],n,n//2,1,flags);offset+=1
            previous=name
        return(start,offset-start)
    for k in range(1,4):
        t.approach[k]=path([(f'obj{k}_above',2),(f'obj{k}_pick',2)],'home')
        t.grasp[k]=path([(f'obj{k}_grasp',3)],f'obj{k}_pick')
        t.lift[k]=path([(f'obj{k}_lift',2),('pre_delivery',2)],f'obj{k}_grasp')
    t.deliver=path([('delivery',2)],'pre_delivery');t.release=path([('delivery_open',2)],'delivery')
    t.retreat=path([('retreat',2),('home',2)],'delivery_open')
    t.tray=path([('tray_above',2),('tray_drop',2),('tray_open',2),('tray_retreat',2),('home',2)],'pre_delivery')
    cfg=m.S4Config(mode_b=False,require_line=True,hold_policy=True,t_palm_hold=1,t_palm_wait=15000,blind_periods=4,
      t_arrival=3000,t_comm=500,move_margin=50,period_cycles=round(p*100000000),stall_cycles=100000000,
      home_kp=indices['home'],predelivery_kp=indices['pre_delivery'],joint_min=tuple(rad_to_q16_16(x[0]) for x in c['measured_limits_rad']),
      joint_max=tuple(rad_to_q16_16(x[1]) for x in c['measured_limits_rad']),vmax=(v,)*6,amax=(a,)*6,tray_exit=True)
    return cfg,t
def board():
    from pynq import MMIO
    arm=ad.ArmBackendAxiDriver.from_pynq(ad.PROPOSED_BASE_ADDRESS);plan=pd.PlannerAxiDriver.from_pynq(pd.PROPOSED_BASE_ADDRESS);task=sd.S4TaskAxiDriver.from_pynq()
    arm.assert_abi();plan.assert_abi();task.assert_abi();vis=MMIO(VBASE,0x1000)
    if vis.read(8)!=0x3503 or vis.read(0x70)!=0x0f350087:raise RuntimeError('Wrong visual model/ABI: this package requires VIS 0x3503 and matching BIT/HWH')
    return arm,plan,task,vis

def camera_diagnostics(vis):
    if vis.read(0x74)!=0x43414d31:raise RuntimeError('Camera diagnostics CAM1 missing')
    bits=vis.read(0x78)
    names=('xclk_locked','init_done','init_error','capture_enabled','fifo_overflow',
      'retained_valid','locator_busy','roi_busy','classifier_busy','snapshot_requested',
      'snapshot_ready','deferred_release')
    result={name:bool(bits&(1<<i)) for i,name in enumerate(names)}
    pipeline=('WAIT_INIT','WAIT_FRAME','START_LOC','WAIT_LOC','TOP1_SETTLE','START_BBOX',
      'WAIT_BBOX','START_ROI','WAIT_ROI','START_CLASS','WAIT_CLASS')
    capture=('WAIT_SOF','TOP_PAD','ACTIVE','BOTTOM_PAD','PUBLISH','HELD')
    ps=(bits>>12)&15;cs=(bits>>16)&7
    result.update(status_hex=hex(bits),pipeline_state=pipeline[ps] if ps<len(pipeline) else ('FATAL' if ps==15 else str(ps)),
      capture_state=capture[cs] if cs<len(capture) else str(cs),
      dropped_while_owned=vis.read(0x7c),format_errors=vis.read(0x80),now_ms=vis.read(0x84),
      retained_frame_id=vis.read(0x48),retained_timestamp_ms=vis.read(0x58),
      result_frame_id=vis.read(0x28),result_events=vis.read(0x2c))
    return result

def take_snapshot(out,timeout=5):
    import struct
    if not math.isfinite(timeout) or not 0<timeout<=60:raise ValueError('Snapshot timeout must be in (0,60] seconds')
    arm,plan,task,vis=board()
    if task.status().state!=m.State.OFF or arm.status().permission:
        raise RuntimeError('Snapshot is calibration-only: S4 OFF and motion permission removed are required')
    if vis.read(0x40)&1:raise RuntimeError('Another snapshot request is active; preserve its owner')
    vis.write(0x40,1)
    try:
        end=time.monotonic()+timeout
        while not(vis.read(0x44)&1):
            bits=vis.read(0x78)
            if bits&((1<<2)|(1<<4)):raise RuntimeError('Camera initialization error or FIFO overflow')
            if time.monotonic()>end:raise TimeoutError('No retained camera frame; see SNAPSHOT_FAILURE camera state')
            time.sleep(.01)
        fid=vis.read(0x48);stamp=vis.read(0x58);vis.write(0x4c,0)
        image=b''.join(struct.pack('<I',vis.read(0x50)) for _ in range(76800))
        if not(vis.read(0x44)&1) or vis.read(0x48)!=fid:raise RuntimeError('Snapshot source ownership changed while reading')
        out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(b'P5\n640 480\n255\n'+image)
        dump(out.with_suffix('.json'),dict(frame_id=fid,acquisition_ms=stamp,width=640,height=480,camera=camera_diagnostics(vis)))
        print(json.dumps(dict(event='SNAPSHOT_SAVED',path=str(out),frame_id=fid,pixel_bytes=len(image))),flush=True)
    except Exception as exc:
        # Capture before finally clears the request; a later status loses this evidence.
        print(json.dumps(dict(event='SNAPSHOT_FAILURE',error=str(exc),camera=camera_diagnostics(vis))),flush=True)
        raise
    finally:vis.write(0x40,0)
def drain_delivered(arm,plan,target,timeout=2):
    deadline=time.monotonic()+timeout
    while True:
        arm.raise_for_error();plan.raise_for_fatal();status=plan.status()
        if not status.planner_pending and not arm.status().engine_busy and plan.last_delivered()==tuple(target):return
        if time.monotonic()>deadline:raise TimeoutError('S2 DONE but final backend delivery not committed')
        time.sleep(.001)

def stop_backend(arm,timeout=1):
    """Finish the in-flight UART frame before changing backend mode."""
    arm.stop();deadline=time.monotonic()+timeout
    while True:
        status=arm.status()
        if status.active_mode==ab.MODE_OFF and not status.engine_busy:return
        if time.monotonic()>deadline:raise TimeoutError('Backend did not reach OFF/idle; keep physical permission removed')
        time.sleep(.001)
def state():
    arm,plan,task,vis=board()
    st=task.status();vs=vis.read(4)
    coherent=False
    for _ in range(4):
        fid=vis.read(0x28);model_margin=vis.read(0x68)
        vision=dict(frame_id=fid,acquisition_ms=vis.read(0x5c),result_ms=vis.read(0x60),latency_ms=vis.read(0x64),
            model_class=(model_margin>>16)&7,margin=model_margin&65535,raw_confidence=sd.s32(vis.read(0x6c)))
        if fid==vis.read(0x28):coherent=True;break
    return dict(host_monotonic_s=time.monotonic(),arm=arm.status().__dict__,planner=plan.status().__dict__,
      task=dict(raw=st.raw,state=st.state.name,phase=st.phase.name,object=st.object,holding=st.holding,released=st.released,fault=st.fault_latched,tray_ok=st.tray_ok),
      vision_status=vs,qualified=vis.read(0x38),candidate_class=(vs>>8)&7,task_class=(vs>>5)&7,palm_window_ok=bool(vs&16),
      **vision,vision_metadata_coherent=coherent,camera=camera_diagnostics(vis),
      counters=dict(done=task.read(sd.CNT_DONE),cancel=task.read(sd.CNT_CANCEL),fault=task.read(sd.CNT_FAULT),refuse=task.read(sd.CNT_REFUSE)),s4_fault=task.read(sd.FAULT))
def readonly_setup():
    # Native protocol units are known. Vendor limits here only configure a read-only mapper; motion is never armed.
    raw=yaml.safe_load((ROOT/'config/arm_profiles/roarm_m3_pro.yaml').read_text(encoding='utf-8'))
    proto_path=ROOT/'config/protocols/roarm_m3_s_native_json.yaml'
    raw['protocol']=dict(file=str(proto_path.resolve()),sha256=sha256_file(proto_path))
    raw['robot_model']='RoARM-M3-S';raw['transport']['port']='PL_UART_D1_D0';raw['device_encoding'].update(fraction_digits=4,device_min=-40000,device_max=40000)
    for j in raw['joints']:j.update(zero_device=0,direction=1,device_units_per_rad=10000.,soft_min_rad=-3.2,soft_max_rad=3.2,arrival_tolerance_rad=.02)
    raw['feedback']['arrival_consecutive']=3;raw['timeouts'].update(command_timeout_ms=100,feedback_timeout_ms=500,overall_timeout_ms=60000)
    # Unit firmware identity is recorded separately; only documented T105 request bytes are emitted.
    profile=ArmProfile.from_mapping(raw,path=ROOT/'config/arm_profiles/roarm_m3_pro.yaml') if hasattr(ArmProfile,'from_mapping') else None
    if profile is None:
        tmp=ROOT/'runs/roarm_readonly_profile.yaml';tmp.parent.mkdir(exist_ok=True);tmp.write_text(yaml.safe_dump(raw),encoding='utf-8');profile=ArmProfile.load(tmp)
    proto=RoArmJsonProtocol.load(ROOT/'config/protocols/roarm_m3_s_native_json.yaml')
    return profile,proto

def readonly_config():
    profile,proto=readonly_setup()
    return ab.build_pl_config(profile,proto,prime_period_ms=100)

def monitor(seconds):
    profile,proto=readonly_setup()
    cfg=ab.build_pl_config(profile,proto,prime_period_ms=100)
    arm,plan,task,vis=board()
    if task.status().owner_s4:raise RuntimeError('Release S4 before monitor')
    arm.stop();arm.load_config(cfg);arm.commit_config()
    # A typed read-only permit cannot arm LINE. Deliberately bypass firmware identity only for documented T105.
    permit=ab.RealOutputPermit('robot_readonly',str(profile.path),proto.protocol_id)
    arm.set_mode(ab.MODE_MONITOR,backend=0,permit=permit)
    end=time.monotonic()+seconds
    try:
        while time.monotonic()<end:print(json.dumps(dict(snapshot=arm.snapshot().__dict__,counters=arm.counters().__dict__),default=str));time.sleep(.1)
    finally:arm.stop()
def require_compiled_instance(instance):
    if (Path(instance)/'COMPILATION_INCOMPLETE').exists():
        raise ValueError('Previous compile failed/incomplete; recompile successfully before motion')

def run(instance,seconds,without_tray=False):
    require_compiled_instance(instance)
    instance=Path(instance);profile=ArmProfile.load(instance/'profile.yaml');proto=RoArmJsonProtocol.load(instance/'protocol.yaml')
    permit=ab.require_real_output(profile,proto,purpose='robot');c=json.loads((instance/'calibration_source.json').read_text(encoding='utf-8'))
    if any(c['verified'].get(k) is not True for k in CHECKS):raise ValueError('Instance safety/calibration checks incomplete')
    cfg,tables=build_tables(c);cfg=replace(cfg,tray_exit=not without_tray);arm,plan,task,vis=board()
    if task.status().state!=m.State.OFF or task.status().owner_s4:raise RuntimeError('Load a fresh overlay before run')
    arm.stop();arm.load_config(ab.build_pl_config(profile,proto,prime_period_ms=c['period_ms']));arm.commit_config()
    arm.set_mode(ab.MODE_MONITOR,backend=0,permit=ab.RealOutputPermit('robot_readonly',str(profile.path),proto.protocol_id))
    time.sleep(1);fb=arm.snapshot();print('FEEDBACK',fb)
    if fb.valid_mask!=63 or fb.age_max_ticks>500 or fb.servo_fault_mask:arm.stop();raise ValueError('Feedback incomplete/stale/faulted')
    actual=tuple(v/10000 for v in fb.fb_dev);home=c['poses']['home']
    if any(abs(a-b)>c['arrival_tolerance_rad'][i] for i,(a,b) in enumerate(zip(actual,home))):arm.stop();raise ValueError('Actual pose differs from taught HOME; manually restore before arming')
    stop_backend(arm);arm.set_mode(ab.MODE_DRY_RUN,backend=0)
    # Initialize LAST_DELIVERED to the measured HOME using a pins-idle zero-distance move.
    plan.select_source(1);homeq=tables.keypoints[cfg.home_kp]
    move=pr.MoveParams(homeq,homeq,1,0,0,cfg.period_cycles,cfg.stall_cycles,cfg.vmax,cfg.amax)
    plan.run_move(move,timeout_s=3)
    drain_delivered(arm,plan,homeq)
    stop_backend(arm);arm.set_mode(ab.MODE_LINE,backend=0,arm=True,permit=permit)
    if not arm.status().permission:arm.stop();raise ValueError('D5/ARM/LINE permission inactive')
    x0,y0,x1,y1=c['palm_window_locator_xyxy'];vis.write(0x10,x0|(x1<<16));vis.write(0x14,y0|(y1<<16));vis.write(0x18,c['palm_max_move_px']);vis.write(0x1c,25000000);vis.write(0xc,3|(c['palm_window_frames']<<8))
    task.load(cfg,tables,vision_sim=False);task.command(m.Cmd.ENABLE)
    end=time.monotonic()+seconds
    try:
        while time.monotonic()<end:
            print(json.dumps(state(),default=str),flush=True)
            if task.status().fault_latched:raise RuntimeError('PL task fault; use physical stop and inspect logs')
            time.sleep(.1)
    finally:
        # Once ending the session, hold safely; do not silently disable UART while a task is moving.
        task.command(m.Cmd.ABORT,check=False);arm.stop()
def route_test(instance,stage,obj):
    require_compiled_instance(instance)
    instance=Path(instance);profile=ArmProfile.load(instance/'profile.yaml');proto=RoArmJsonProtocol.load(instance/'protocol.yaml')
    permit=ab.require_real_output(profile,proto,purpose='robot');c=json.loads((instance/'calibration_source.json').read_text(encoding='utf-8'))
    if any(c['verified'].get(k) is not True for k in CHECKS[:6]):raise ValueError('Commissioning prerequisites incomplete')
    empty_stage=stage in ('empty','empty-tray')
    if not empty_stage and not c['verified']['all_empty_routes_tested']:raise ValueError('Verify empty routes first')
    if stage=='surrogate' and not(c['verified']['cube_grasp_tested'] and c['verified']['tray_route_tested']):raise ValueError('Verify grasp and tray before surrogate delivery')
    if empty_stage and abs(c['poses']['home'][5]-c['poses']['delivery_open'][5])>c['arrival_tolerance_rad'][5]:
        raise ValueError('Teach HOME with the calibrated open gripper before empty routes')
    cfg,tables=build_tables(c);arm,plan,task,vis=board()
    if task.status().state!=m.State.OFF:raise RuntimeError('Fresh overlay required')
    arm.stop();arm.load_config(ab.build_pl_config(profile,proto,prime_period_ms=c['period_ms']));arm.commit_config()
    arm.set_mode(ab.MODE_MONITOR,backend=0,permit=ab.RealOutputPermit('robot_readonly',str(profile.path),proto.protocol_id));time.sleep(1)
    fb=arm.snapshot()
    if fb.valid_mask!=63 or fb.age_max_ticks>500 or fb.servo_fault_mask:arm.stop();raise ValueError('Feedback incomplete/stale/faulted')
    start=tuple(rad_to_q16_16(v/10000) for v in fb.fb_dev);home=tables.keypoints[cfg.home_kp]
    if any(abs(a-b)>rad_to_q16_16(c['arrival_tolerance_rad'][i]) for i,(a,b) in enumerate(zip(start,home))):arm.stop();raise ValueError('Restore taught HOME first')
    stop_backend(arm);arm.set_mode(ab.MODE_DRY_RUN,backend=0);plan.select_source(1)
    plan.run_move(pr.MoveParams(start,start,1,0,0,cfg.period_cycles,cfg.stall_cycles,cfg.vmax,cfg.amax),timeout_s=3)
    drain_delivered(arm,plan,start)
    stop_backend(arm);arm.set_mode(ab.MODE_LINE,backend=0,arm=True,permit=permit)
    if not arm.status().permission:arm.stop();raise ValueError('D5/ARM/LINE permission inactive')
    desc=[tables.approach[obj],tables.grasp[obj],tables.lift[obj]]
    desc += [tables.deliver,tables.release,tables.retreat] if stage in ('empty','surrogate') else [tables.tray]
    try:
        for first,count in desc:
            for index in range(first,first+count):
                kp,n,na,prof,flags=tables.segments[index];target=tables.keypoints[kp]
                if empty_stage:target=tuple(target[:5])+(rad_to_q16_16(c['poses']['delivery_open'][5]),)
                start=plan.last_delivered();print('MOVE',index,'target_rad',[v/65536 for v in target],flush=True)
                delta=max(abs(x-y) for x,y in zip(start,target));v=cfg.vmax[0];a=cfg.amax[0]
                n=max(n,4,math.ceil(2*delta/v)+2,math.ceil(2*math.sqrt(delta*65536/a))+2);n+=n%2;na=n//2
                plan.run_move(pr.MoveParams(start,target,n,na,prof,cfg.period_cycles,cfg.stall_cycles,cfg.vmax,cfg.amax),timeout_s=n*c['period_ms']/1000+5)
                drain_delivered(arm,plan,target)
                deadline=time.monotonic()+3
                while True:
                    arm.raise_for_error();fb=arm.snapshot()
                    if fb.valid_mask!=63 or fb.age_max_ticks>500 or fb.servo_fault_mask:raise ValueError('Feedback lost or faulted')
                    if fb.arrival_mask==63:break
                    if time.monotonic()>deadline:raise TimeoutError('Real joint arrival timeout')
                    time.sleep(.02)
        print('PASS: commissioned route',stage,'object',obj)
    finally:plan.estop();arm.stop()
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('template');a.add_argument('--out',required=True,type=Path)
    a=s.add_parser('usb-query');a.add_argument('--port',required=True);a.add_argument('--seconds',type=float,default=2);a.add_argument('--out',required=True,type=Path)
    a=s.add_parser('capture');a.add_argument('--port',required=True);a.add_argument('--session',required=True,type=Path);a.add_argument('--name',choices=POSES,required=True)
    a=s.add_parser('compile');a.add_argument('--session',required=True,type=Path);a.add_argument('--out',required=True,type=Path);a.add_argument('--commission',action='store_true')
    a=s.add_parser('load');a.add_argument('--bit',required=True,type=Path)
    s.add_parser('status')
    a=s.add_parser('snapshot');a.add_argument('--out',required=True,type=Path);a.add_argument('--timeout',type=float,default=5)
    a=s.add_parser('vision-log');a.add_argument('--seconds',type=float,default=60);a.add_argument('--out',required=True,type=Path)
    a=s.add_parser('monitor');a.add_argument('--seconds',type=float,default=10)
    a=s.add_parser('run');a.add_argument('--instance',required=True,type=Path);a.add_argument('--seconds',type=float,default=3600);a.add_argument('--without-tray',action='store_true',help='Disable the tray exit for a staged surrogate-palm HOLD test; retain all commissioning checks')
    a=s.add_parser('route-test');a.add_argument('--instance',required=True,type=Path);a.add_argument('--stage',choices=['empty','empty-tray','cube','tray','surrogate'],required=True);a.add_argument('--object',choices=[1,2,3],type=int,default=1)
    a=s.add_parser('stop')
    args=p.parse_args(argv)
    if args.cmd=='template':template(args.out)
    elif args.cmd=='usb-query':dump(args.out,dict(readonly=True,records=query(args.port,args.seconds)))
    elif args.cmd=='capture':
        c=json.loads(args.session.read_text(encoding='utf-8'));records=query(args.port);c['poses'][args.name]=records[-1]['position_rad'];c['feedback_evidence'].append(dict(pose=args.name,records=records));dump(args.session,c)
    elif args.cmd=='compile':print(json.dumps(compile_session(args.session,args.out,args.commission)))
    elif args.cmd=='load':
        from pynq import Overlay
        if not args.bit.with_suffix('.hwh').is_file():raise ValueError('Matching HWH required')
        Overlay(str(args.bit),download=True);print(json.dumps(state(),default=str))
    elif args.cmd=='status':print(json.dumps(state(),default=str))
    elif args.cmd=='snapshot':take_snapshot(args.out,args.timeout)
    elif args.cmd=='vision-log':
        args.out.parent.mkdir(parents=True,exist_ok=True);end=time.monotonic()+args.seconds
        with args.out.open('w',encoding='utf-8') as f:
            while time.monotonic()<end:f.write(json.dumps(state(),default=str)+'\n');f.flush();time.sleep(.05)
    elif args.cmd=='monitor':monitor(args.seconds)
    elif args.cmd=='run':run(args.instance,args.seconds,args.without_tray)
    elif args.cmd=='route-test':route_test(args.instance,args.stage,args.object)
    elif args.cmd=='stop':
        arm,plan,task,vis=board();task.command(m.Cmd.ABORT,check=False);arm.stop();print('Commands inhibited; already issued MCU motion requires physical stop.')
if __name__=='__main__':main()
