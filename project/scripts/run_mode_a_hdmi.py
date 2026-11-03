"""v0.12.0 preconnected-D5 JTAG setup and autonomous FPGA Mode A.

Only PL classifies gestures, selects tasks, interpolates and emits motion.
PC loads immutable configuration once, displays telemetry and accepts explicit
manual restock/stop. No serial connection or PC per-period motion decisions.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,shutil,signal,sys,threading,time
from mode_a_palmfix_config import ROOT,ARM,PLAN,TASK,VIS,backend_writes,task_writes,vision_writes
from mode_a_hdmi_profile import profile,segment
from mode_a_terminal import ADDRS as BASE_ADDRS,decode,line
ADDRS=BASE_ADDRS+[TASK+v for v in (0x260,0x264,0x12c,0x130,0x314,0x318,0x31c,0x320)]+[VIS+0x20,VIS+0x24]
from arm_feedback import decode_pl_errors


def decode_v2(raw):
    s=decode(raw,task_abi=0x3409);r={int(k,0) if isinstance(k,str) else k:v for k,v in raw.items()}
    a=r[TASK+0x31c];c=r[TASK+0x320];p=r[VIS+0x20];q=r[VIS+0x24]
    s.update(align_bank=(a>>2)&3,align_waiting=bool(a&256),align_ready=bool(a&512),align_same=bool(a&1024),align_return_anchor_pending=bool(a&2048),align_candidate_cell=(c>>8)&15,align_locked_cell=(c>>16)&15,align_locked=bool(c>>31),align_candidate_valid=bool(c&(1<<30)),align_retarget_count=(a>>24)&255,locator_detected=bool(r[VIS+4]&(1<<11)),hand_map_revision=r[TASK+0x318],bbox_center_px=[((p&511)+(q&511))//2,(((p>>16)&511)+((q>>16)&511))//2])
    from mode_a_palmfix_config import preview_band
    s['image_band_preview']=preview_band(s['bbox_center_px'])
    s['image_band_preview_source']='HOST_DISPLAY_ONLY_NOT_MOTION_DECISION'
    return s


def load(root):
    m=json.loads((root/'BOARD_MANIFEST.json').read_text('utf-8'))
    if m['version']!='0.12.0' or m['task_abi']!=0x3409 or m['arrival_policy']!='observe_all':raise ValueError('Use the complete v0.12.0 board package')
    for rel,digest in m['inputs'].items():
        p=(root/rel).resolve()
        if not p.is_relative_to(root.resolve()) or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:raise ValueError('Changed board input '+rel)
    plan=json.loads((root/'candidate/bank1/PLAN_NATIVE.json').read_text('utf-8'));table=json.loads((root/'candidate/S4_BANKED_CANDIDATE.json').read_text('utf-8'))
    for bank in range(4):
        for name in ('COPPELIA_RESULT.json','COPPELIA_WIRE_RESULT.json'):
            c=json.loads((root/'candidate'/('bank'+str(bank))/name).read_text('utf-8'))
            if not c['passed'] or c['native_plan_sha256']!=hashlib.sha256((root/'candidate'/('bank'+str(bank))/'PLAN_NATIVE.json').read_bytes()).hexdigest():raise ValueError('Simulation binding')
    if table['abi']['task']!=0x3409 or table['arrival_mask']!=0 or table.get('hold_policy') is not False:raise ValueError('Wrong table semantics')
    if table['execution_profile'].get('handalign_image_axis')!='Y' or table['execution_profile'].get('handalign_desk_axis')!='Y':raise ValueError('Wrong alignment axes')
    return plan,table,m


def cancel_return_view(s,plan):
    if s['state']=='STOPPING' and s['cancel_pending']:
        s['software_status_explanation']='CANCEL_BRAKING_BEFORE_RETURN'
    elif s['state']=='RETRACE' and s['cancel_pending']:
        s['software_status_explanation']='CANCEL_RETURN_TO_SLOT_THEN_HOME'
        route=next(r for r in plan['paths'] if r['object']==s['object'])
        legs=[l for l in route['legs'] if l['phase'] in ('approach','grasp','lift','deliver')]
        depth=(s['progress_raw']>>24)&63;s['return_stack_depth']=depth
        leg=legs[min(depth,len(legs)-1)]
        s['planned_waypoint']='RETURN_'+leg['label']+'_START'
        s['planned_D_mm']=next((x['target_D_mm'] for x in reversed(legs[:depth]) if x['target_D_mm'] is not None),None)
    return s


def setup_tools(root,out):
    tools=out/'tools';tools.mkdir()
    for name in ('transport_reused.py','monitor.py','service_owner.py','verify_camera.py','verify_exposure.py','png_helper.py'):
        shutil.copyfile(root/'scripts/mode_a_camera_v3_v0_4_0'/name,tools/name)
    shutil.copyfile(root/'scripts/mode_a_board_bridge.tcl',tools/'jtag_bridge.tcl')
    sys.path.insert(0,str(tools))
    import transport_reused as t
    t.HERE=tools;t.ROOT=root;t.PACKAGE=root;t.XSA=root/'hardware/roarm_closed_loop.xsa'
    import monitor,verify_exposure
    class BoardBridge(t.Bridge):
        def read(self,a,count=1):
            values=self.call(f'R {a} {count}').split()
            if len(values)!=count:raise RuntimeError('Short register read')
            return [int(v,0) for v in values]
        def write(self,a,v):self.call(f'W {int(a)} {int(v)&0xffffffff}')
        def batch(self,rows):
            for i in range(0,len(rows),64):self.call('B '+' '.join(f'{a} {v&0xffffffff}' for a,v in rows[i:i+64]))
        def telemetry(self):
            values=self.call('T').split()
            if len(values)!=len(ADDRS):raise RuntimeError('Short telemetry')
            return dict(zip(ADDRS,(int(v,0) for v in values)))
    return BoardBridge,monitor.OwnedServer,verify_exposure


def check_feedback(s,phase):
    if s['arm_errors'] or s['arm_fault']:raise RuntimeError(phase+': '+backend_error(s['arm_errors']))
    if not s['feedback_live_valid'] or s['feedback_mask']!=63 or s['feedback_age_at_snapshot_ms']>500:
        raise RuntimeError(phase+': native feedback stale/incomplete; no motion started')


def backend_error(errors,status=None):
    names=','.join(e.name for e in decode_pl_errors(errors)) or 'NONE'
    return 'backend error=0x%08x [%s]'%(errors,names)+(' status=0x%08x'%status if status is not None else '')


def prepare_line_queries(b,plan,table,alive,observe):
    if not b.read(ARM+8)[0]&8:
        raise RuntimeError('D5 is not high at launch; exit and connect D5 before the next run')
    b.batch(backend_writes(plan));b.write(ARM,1)
    deadline=time.monotonic()+2
    while not b.read(ARM+8)[0]&1:
        alive()
        if time.monotonic()>deadline:raise RuntimeError('Backend configuration commit failed')
        time.sleep(.01)
    b.batch(task_writes(plan,table));b.batch(vision_writes())
    deadline=time.monotonic()+2
    while True:
        flags=b.read(TASK+0x314)[0]
        if flags&8:raise RuntimeError('PL hand-map rejected, error='+str((flags>>12)&15))
        if flags&3==3:break
        alive()
        if time.monotonic()>deadline:raise RuntimeError('PL hand-map commit timeout')
        time.sleep(.01)
    if (b.read(TASK+0x12c)[0]>>2)&15!=15:raise RuntimeError('Four keypoint banks not ready')
    expected=[(p['na']<<16)|p['n'] for p in table['align_pairs']]
    if b.read(TASK+0x330,16)!=expected:raise RuntimeError('Pair timing configuration mismatch')
    b.write(ARM+4,3)
    print('PRECHECK_LINE_UNARMED: D5已接好；只查询反馈，ARM=0，不发送运动。',flush=True)
    wait_backend(b,alive,3,fresh=True)
    # Keep RX enabled continuously: OFF would discard an in-flight response.
    # Position errors are never compared during this communication precheck.
    sequences=set();deadline=time.monotonic()+3
    while len(sequences)<3:
        alive();s=observe('PRECHECK_LINE_UNARMED');check_feedback(s,'PRECHECK')
        if not s['D5_ok']:raise RuntimeError('D5 removed during precheck')
        if s['motion_frames']:raise RuntimeError('Unexpected motion frame during precheck')
        sequences.add(s['feedback_seq'])
        if time.monotonic()>deadline:raise RuntimeError('Precheck feedback sequence did not advance')
        time.sleep(.1)
    print('PRECHECK_PASS_D5_PRECONNECTED: 3个新反馈、tx=0；无需插线或按Enter。',flush=True)


def wait_backend(b,alive,mode,*,fresh=False,timeout=3):
    deadline=time.monotonic()+timeout
    while True:
        alive();status=b.read(ARM+8)[0]
        errors=b.read(ARM+12)[0]
        if status&16 or errors:raise RuntimeError(backend_error(errors,status))
        if not status&8:raise RuntimeError('D5 removed before motion startup')
        if ((status>>12)&3)==mode and (bool(status&32) if fresh else not status&2):return
        if time.monotonic()>deadline:raise RuntimeError('Backend transition/feedback timeout mode='+str(mode))
        time.sleep(.01)


def start_motion(b,plan,alive,observe):
    # ARM changes within the same LINE mode. Never interrupt its receiver
    # between communication precheck and motion, including mid-response.
    alive();wait_backend(b,alive,3,fresh=True)
    print('LINE_READY_CONTINUOUS_RX: 保持LINE接收，准备从当前反馈接HOME。',flush=True)
    alive();b.write(ARM,4);fb=b.read(ARM+0x200,8)
    if fb[6]&63!=63 or fb[7]&65535>500:raise RuntimeError('Feedback stale/incomplete before startup')
    actual=[(v-(1<<32) if v&(1<<31) else v)/10000 for v in fb[:6]]
    if any(not lo<=v<=hi for v,(lo,hi) in zip(actual,plan['native_limits_rad'])):raise ValueError('Invalid native feedback envelope')
    from run_mode_a_walkthrough import quant
    move,_=segment(quant(actual),quant(plan['home_native_rad']),'START_HOME','approach')
    v=math_ceil_velocity();a=math_ceil_acceleration()
    writes=[(PLAN+0x40,move['n']),(PLAN+0x44,move['na']),(PLAN+0x48,1),(PLAN+0x4c,2_000_000),(PLAN+0x50,50_000_000)]
    for ch in range(6):writes +=[(PLAN+0x100+32*ch,move['start_q16'][ch]&0xffffffff),(PLAN+0x104+32*ch,move['target_q16'][ch]&0xffffffff),(PLAN+0x108+32*ch,v),(PLAN+0x10c+32*ch,a)]
    b.batch(writes);b.write(ARM+4,259);b.write(PLAN,1)
    deadline=time.monotonic()+move['seconds']+10
    while True:
        alive();s=observe('PL_START_FROM_FEEDBACK')
        if s['arm_errors'] or s['planner_errors']:raise RuntimeError('Startup PL error')
        ps=s['raw'][f'0x{PLAN+4:08x}']
        if ps&7==4 and not ps&32:break
        if time.monotonic()>deadline:raise RuntimeError('Startup command execution timeout')
        time.sleep(.1)
    # Real feedback position errors do not gate startup or any task waypoint.
    for obj in (1,2,3):b.write(TASK+0x58,obj);b.write(TASK,2048)
    b.write(TASK,1)
    print('MODE_A_AUTONOMOUS: PL识别1/2/3选物，PRE按新鲜Locator中心Y三档跟随；位置跟随不要求固定分类手形，PALM锁定后盲交付；六轴误差只观察。请先移开手/显示背景再选物。',flush=True)
    print('人工补回同色块后按r/y/b确认红/黄/蓝补料；Ctrl+C停止本次会话。',flush=True)


def configure(b,plan,table,alive,observe,*,monitor_only=False):
    prepare_line_queries(b,plan,table,alive,observe)
    if monitor_only:
        print('QUERY_ONLY_CAPTURE: D5预接只查询和采集视觉，未使能ARM；按本次秒数保存手位置。',flush=True)
        return False
    start_motion(b,plan,alive,observe)
    return True


def math_ceil_velocity():
    import math
    return math.ceil(math.radians(profile()['gripper_speed_deg_s'])*.02*65536)+2


def math_ceil_acceleration():
    import math
    return math.ceil(math.radians(profile()['gripper_acceleration_deg_s2'])*.02**2*(1<<32))+2


def stop_motion(b):
    s=b.read(TASK+4)[0]
    if s&128:
        if s&15!=10:b.write(TASK,64)
        deadline=time.monotonic()+2
        while b.read(TASK+4)[0]&15 not in (1,9,10):
            if time.monotonic()>deadline:raise RuntimeError('Task did not stop; remove D5/power')
            time.sleep(.02)
        b.write(TASK,2)
        deadline=time.monotonic()+2
        while b.read(TASK+4)[0]&128:
            if time.monotonic()>deadline:raise RuntimeError('Ownership release failed')
            time.sleep(.02)
    b.write(ARM+4,0)


def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',type=Path,default=ROOT)
    g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--run',action='store_true');g.add_argument('--check-only',action='store_true')
    ap.add_argument('--out-dir',type=Path);ap.add_argument('--seconds',type=float,default=0)
    # The fixed image-Y map is part of the versioned package.
    ap.add_argument('--monitor-only',action='store_true',help='With D5 already high, query in LINE with ARM=0, then restore and exit')
    args=ap.parse_args()
    if args.monitor_only and not args.run:ap.error('--monitor-only requires --run')
    plan,table,manifest=load(args.root)
    plans=[json.loads((args.root/'candidate'/('bank'+str(i))/'PLAN_NATIVE.json').read_text('utf-8')) for i in range(4)]
    if args.check_only:
        from check_mode_a_hdmi_package import check
        print(json.dumps(check(args.root),ensure_ascii=False));return
    from mode_a_palmfix_config import validate_map,default_map
    table['hand_map']=default_map()
    if args.monitor_only and args.seconds==0:args.seconds=8
    if args.out_dir is None:ap.error('--run requires a new --out-dir')
    import math
    if not math.isfinite(args.seconds) or args.seconds<0:ap.error('--seconds must be finite and nonnegative;0 waits until Ctrl+C')
    args.out_dir.mkdir(parents=True,exist_ok=False)
    stop=threading.Event();previous=signal.signal(signal.SIGINT,lambda *a:stop.set())
    b=service=None;exposure=None;result=dict(version=manifest['version'],result='STARTING',startup_policy='D5_PRECONNECTED_AUTO',
        query_only=args.monitor_only,hand_map=table.get('hand_map',default_map()),arrival_policy='observe_all',layout_id=plan['layout_id'],physical_task_pass=None)
    code=2
    def alive():
        if stop.is_set():raise InterruptedError('Operator requested stop')
    try:
        Bridge,Server,exposure=setup_tools(args.root,args.out_dir);service=Server();service.start();b=Bridge();b.wait_ready()
        with (args.out_dir/'telemetry.jsonl').open('x',encoding='utf-8') as log:
            seen_done=None;seen_cancel=None
            def observe(phase='AUTONOMOUS'):
                nonlocal seen_done,seen_cancel
                s=decode_v2(b.telemetry());s.update(session_phase=phase,arrival_policy='observe_all',physical_task_pass=None)
                arm_status=s['raw'][f'0x{ARM+8:08x}']
                s.update(backend_mode=('OFF','DRY_RUN','MONITOR','LINE')[(arm_status>>12)&3],
                    feedback_live_valid=bool(arm_status&32),feedback_snapshot_valid=bool(arm_status&64),
                    feedback_capture_source='PL_OWNER' if s['owner'] else 'HOST_SNAPSHOT')
                ix=s['raw'][f'0x{TASK+0x260:08x}'];it=s['raw'][f'0x{TASK+0x264:08x}']
                s.update(fist_hold_ms=ix>>16,palm_hold_ms=it>>16,palm_wait_ms=it&65535,
                    blind_delivery=bool(ix&8),palm_trigger_latched=bool(ix&16),pre_minimum_wait=bool(ix&32),cancel_pending=bool(ix&256))
                if s['state']=='HALT' and s['holding']:s['software_status_explanation']='CANCELLED_HOLDING_MANUAL_RESTART'
                elif s['blind_delivery']:s['software_status_explanation']='BLIND_DELIVERY_PALM_NOT_REQUIRED'
                elif s['pre_minimum_wait']:s['software_status_explanation']='PRE_FIXED_WAIT'
                s['done_counter']=s['raw'][f'0x{TASK+0x240:08x}'];s['cancelled_counter']=s['raw'][f'0x{TASK+0x244:08x}'];hint=''
                if s['object'] in (1,2,3):
                    active_plan=plans[s['align_bank']]
                    route=next(r for r in active_plan['paths'] if r['object']==s['object'])
                    phases={'OUT':('approach','grasp','lift'),'DELIVER':('deliver',),'RELEASE':('release',),'RETREAT':('retreat',)}
                    legs=[l for l in route['legs'] if l['phase'] in phases.get(s['phase'],())]
                    pos=(s['progress_raw']&63)-1
                    leg=legs[pos] if 0<=pos<len(legs) else (next(l for l in route['legs'] if l['label']=='PRE') if s['state']=='WAIT_PALM' else None)
                    if leg is not None:
                        s.update(planned_waypoint=leg['label'],planned_D_mm=leg['target_D_mm']);hint=' waypoint='+leg['label']+' D_mm='+str(leg['target_D_mm'])
                cancel_return_view(s,plan)
                if s['state']=='RUN' and s['phase']=='NONE' and s['holding']:
                    s.update(software_status_explanation='ALIGN_TO_REGION_PRE',planned_waypoint='ALIGN_PRE_BANK_'+str(s['align_bank']),planned_D_mm=plans[s['align_bank']]['layout']['common_D_mm']['PRE'])
                    hint=' waypoint='+s['planned_waypoint']+' D_mm='+str(s['planned_D_mm'])
                if s['cancel_pending'] and s['align_return_anchor_pending']:
                    s.update(planned_waypoint='RETURN_OFFSET_TO_CENTRAL_PRE_THEN_ORIGINAL_SLOT',planned_D_mm=None)
                if s['state']=='RETRACE':hint=' waypoint='+s['planned_waypoint']+' D_mm='+str(s['planned_D_mm'])
                log.write(json.dumps(s,ensure_ascii=False)+'\n');log.flush()
                print(line(s)+' backend='+s['backend_mode']+' fb_packets='+str(s['feedback_packets'])+
                    ' fb_mask='+hex(s['feedback_mask'])+' fb_valid='+str(int(s['feedback_live_valid']))+
                    ' arm_err='+hex(s['arm_errors'])+'['+','.join(e.name for e in decode_pl_errors(s['arm_errors']))+']'+
                    ' fist_ms='+str(s['fist_hold_ms'])+'/1000 palm_hold_ms='+str(s['palm_hold_ms'])+'/500'+
                    ' pre_wait_ms='+str(s['palm_wait_ms'])+'/2000 snapshot='+s['feedback_capture_source']+' session='+phase+
                    ' image_band_preview='+str(s['image_band_preview'])+' align_axis=RAW_LOCATOR_Y/DESK_Y_3 align_bank='+str(s['align_bank'])+' target_cell='+str(s['align_candidate_cell'])+' locked_cell='+str(s['align_locked_cell'])+' lock='+str(int(s['align_locked']))+' bbox_center='+str(s['bbox_center_px'])+' palm_window_ok='+str(int(s['palm_window_ok']))+' arrival_policy=OBSERVE_ALL'+hint,flush=True)
                if seen_done is not None and s['done_counter']!=seen_done:print('FPGA_TASK_DONE object='+str(s['object'])+' total='+str(s['done_counter'])+' physical_success=operator_observation',flush=True)
                if seen_cancel is not None and s['cancelled_counter']!=seen_cancel:print('FPGA_TASK_CANCELLED_RETURNED object='+str(s['object'])+' cancelled_total='+str(s['cancelled_counter'])+' physical_return=operator_observation',flush=True)
                seen_done=s['done_counter'];seen_cancel=s['cancelled_counter'];return s
            # Sensor initialization/exposure is reused, not retrained or changed.
            deadline=time.monotonic()+12
            while not b.read(VIS+0x78)[0]&2:
                alive()
                if time.monotonic()>deadline:raise RuntimeError('Camera init incomplete')
                time.sleep(.1)
            result['vts']=(exposure.command(b,result,0x380e)<<8)|exposure.command(b,result,0x380f)
            result['original_sensor']=exposure.freeze(b,result)
            result['selected_sensor']=exposure.apply(b,result,result['original_sensor'],984,80)
            motion_started=configure(b,plan,table,alive,observe,monitor_only=args.monitor_only);start=time.monotonic()
            import msvcrt
            while (motion_started or args.monitor_only) and not stop.is_set() and (args.seconds==0 or time.monotonic()-start<args.seconds):
                s=observe()
                if s['fault']!='NONE' or s['arm_fault']:raise RuntimeError('PL fault '+s['fault'])
                if motion_started and msvcrt.kbhit():
                    key=msvcrt.getwch().lower()
                    if key in ('r','y','b'):
                        if s['state'] not in ('OFF','IDLE') or s['holding']:print('RESTOCK_WAIT_IDLE',flush=True)
                        else:
                            obj={'r':1,'y':2,'b':3}[key];b.write(TASK+0x58,obj);b.write(TASK,2048)
                            print('OPERATOR_RESTOCK object='+str(obj),flush=True)
                time.sleep(.1)
            result.update(result='OPERATOR_SESSION_ENDED' if motion_started else 'PRECONNECTED_QUERY_PASS_NO_MOTION',
                completed_tasks=b.read(TASK+0x240)[0],cancelled_tasks=b.read(TASK+0x244)[0]);code=0
    except InterruptedError as exc:result.update(result='OPERATOR_STOPPED',reason=str(exc));code=0
    except Exception as exc:result.update(result='STOPPED_ERROR',error=repr(exc));print('STOPPED_ERROR '+repr(exc),flush=True)
    finally:
        if b is not None:
            try:
                if b.ready and not b.failed:
                    stop_motion(b);result['motion_shutdown']='OWNERSHIP_RELEASED_BACKEND_OFF'
                    exposure.restore_sensor(b,result)
                b.close();result['PS_CPU_restore']='CONFIRMED'
            except Exception as exc:result.update(shutdown_error=repr(exc),requires_user_power_cycle=True);code=2
        if service is not None:
            try:service.close();result['own_services_closed']=service.record.get('own_services_closed',False)
            except Exception as exc:result['service_close_error']=repr(exc);code=2
        result['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        (args.out_dir/'SESSION_RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
        signal.signal(signal.SIGINT,previous)
    print(json.dumps(result,ensure_ascii=False),flush=True);return code


if __name__=='__main__':raise SystemExit(main())
