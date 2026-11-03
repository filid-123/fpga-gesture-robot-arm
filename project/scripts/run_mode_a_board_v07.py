"""v0.7.2 preconnected-D5 JTAG setup and autonomous FPGA Mode A.

Only PL classifies gestures, selects tasks, interpolates and emits motion.
PC loads immutable configuration once, displays telemetry and accepts explicit
manual restock/stop. No serial connection or PC per-period motion decisions.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,shutil,signal,sys,threading,time
from mode_a_board_config import ROOT,ARM,PLAN,TASK,VIS,backend_writes,task_writes,vision_writes
from mode_a_board_profile import profile,segment
from mode_a_terminal import ADDRS,decode,line
from arm_feedback import decode_pl_errors


def load(root):
    m=json.loads((root/'BOARD_MANIFEST.json').read_text('utf-8'))
    if m['version']!='0.7.2' or m['task_abi']!=0x3405 or m['arrival_policy']!='observe_all':raise ValueError('Use the complete v0.7.2 board package')
    for rel,digest in m['inputs'].items():
        p=(root/rel).resolve()
        if not p.is_relative_to(root.resolve()) or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:raise ValueError('Changed board input '+rel)
    plan=json.loads((root/'candidate/PLAN_NATIVE.json').read_text('utf-8'));table=json.loads((root/'candidate/S4_NATIVE_CANDIDATE.json').read_text('utf-8'))
    for name in ('COPPELIA_RESULT.json','COPPELIA_WIRE_RESULT.json'):
        c=json.loads((root/'candidate'/name).read_text('utf-8'))
        if not c['passed'] or c['native_plan_sha256']!=hashlib.sha256((root/'candidate/PLAN_NATIVE.json').read_bytes()).hexdigest():raise ValueError('Simulation binding')
    if table['abi']['task']!=0x3405 or table['arrival_mask']!=0:raise ValueError('Wrong table semantics')
    return plan,table,m


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
    b.batch(task_writes(plan,table));b.batch(vision_writes());b.write(ARM+4,3)
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
    print('MODE_A_AUTONOMOUS: PL识别1/2/3选物，PRE等真实PALM；六轴误差只观察。请先移开手/显示背景再选物。',flush=True)
    print('人工补回同色块后按r/y/b确认红/黄/蓝补料；Ctrl+C停止本次会话。',flush=True)


def configure(b,plan,table,alive,observe,*,monitor_only=False):
    prepare_line_queries(b,plan,table,alive,observe)
    if monitor_only:
        print('QUERY_ONLY_COMPLETE: D5预接查询结束，未使能ARM或运动。',flush=True)
        return False
    start_motion(b,plan,alive,observe)
    return True


def math_ceil_velocity():
    import math
    return math.ceil(math.radians(14)*.02*65536)+2


def math_ceil_acceleration():
    import math
    return math.ceil(math.radians(28)*.02**2*(1<<32))+2


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
    ap.add_argument('--monitor-only',action='store_true',help='With D5 already high, query in LINE with ARM=0, then restore and exit')
    args=ap.parse_args()
    if args.monitor_only and not args.run:ap.error('--monitor-only requires --run')
    plan,table,manifest=load(args.root)
    if args.check_only:
        from check_mode_a_board_package import check
        print(json.dumps(check(args.root),ensure_ascii=False));return
    if args.out_dir is None:ap.error('--run requires a new --out-dir')
    import math
    if not math.isfinite(args.seconds) or args.seconds<0:ap.error('--seconds must be finite and nonnegative;0 waits until Ctrl+C')
    args.out_dir.mkdir(parents=True,exist_ok=False)
    stop=threading.Event();previous=signal.signal(signal.SIGINT,lambda *a:stop.set())
    b=service=None;exposure=None;result=dict(version=manifest['version'],result='STARTING',startup_policy='D5_PRECONNECTED_AUTO',
        query_only=args.monitor_only,arrival_policy='observe_all',layout_id=plan['layout_id'],physical_task_pass=None)
    code=2
    def alive():
        if stop.is_set():raise InterruptedError('Operator requested stop')
    try:
        Bridge,Server,exposure=setup_tools(args.root,args.out_dir);service=Server();service.start();b=Bridge();b.wait_ready()
        with (args.out_dir/'telemetry.jsonl').open('x',encoding='utf-8') as log:
            seen_done=None
            def observe(phase='AUTONOMOUS'):
                nonlocal seen_done
                s=decode(b.telemetry(),task_abi=0x3405);s.update(session_phase=phase,arrival_policy='observe_all',physical_task_pass=None)
                arm_status=s['raw'][f'0x{ARM+8:08x}']
                s.update(backend_mode=('OFF','DRY_RUN','MONITOR','LINE')[(arm_status>>12)&3],
                    feedback_live_valid=bool(arm_status&32),feedback_snapshot_valid=bool(arm_status&64),
                    feedback_capture_source='PL_OWNER' if s['owner'] else 'HOST_SNAPSHOT')
                s['done_counter']=s['raw'][f'0x{TASK+0x240:08x}'];hint=''
                if s['object'] in (1,2,3):
                    route=next(r for r in plan['paths'] if r['object']==s['object'])
                    phases={'OUT':('approach','grasp','lift'),'DELIVER':('deliver',),'RELEASE':('release',),'RETREAT':('retreat',)}
                    legs=[l for l in route['legs'] if l['phase'] in phases.get(s['phase'],())]
                    pos=(s['progress_raw']&63)-1
                    leg=legs[pos] if 0<=pos<len(legs) else (next(l for l in route['legs'] if l['label']=='PRE') if s['state']=='WAIT_PALM' else None)
                    if leg is not None:
                        s.update(planned_waypoint=leg['label'],planned_D_mm=leg['target_D_mm']);hint=' waypoint='+leg['label']+' D_mm='+str(leg['target_D_mm'])
                log.write(json.dumps(s,ensure_ascii=False)+'\n');log.flush()
                print(line(s)+' backend='+s['backend_mode']+' fb_packets='+str(s['feedback_packets'])+
                    ' fb_mask='+hex(s['feedback_mask'])+' fb_valid='+str(int(s['feedback_live_valid']))+
                    ' arm_err='+hex(s['arm_errors'])+'['+','.join(e.name for e in decode_pl_errors(s['arm_errors']))+']'+
                    ' snapshot='+s['feedback_capture_source']+' session='+phase+
                    ' palm_window_ok='+str(int(s['palm_window_ok']))+' arrival_policy=OBSERVE_ALL'+hint,flush=True)
                if seen_done is not None and s['done_counter']!=seen_done:print('FPGA_TASK_DONE object='+str(s['object'])+' total='+str(s['done_counter'])+' physical_success=operator_observation',flush=True)
                seen_done=s['done_counter'];return s
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
            while motion_started and not stop.is_set() and (args.seconds==0 or time.monotonic()-start<args.seconds):
                s=observe()
                if s['fault']!='NONE' or s['arm_fault']:raise RuntimeError('PL fault '+s['fault'])
                if msvcrt.kbhit():
                    key=msvcrt.getwch().lower()
                    if key in ('r','y','b'):
                        if s['state'] not in ('OFF','IDLE') or s['holding']:print('RESTOCK_WAIT_IDLE',flush=True)
                        else:
                            obj={'r':1,'y':2,'b':3}[key];b.write(TASK+0x58,obj);b.write(TASK,2048)
                            print('OPERATOR_RESTOCK object='+str(obj),flush=True)
                time.sleep(.1)
            result.update(result='OPERATOR_SESSION_ENDED' if motion_started else 'PRECONNECTED_QUERY_PASS_NO_MOTION',
                completed_tasks=b.read(TASK+0x240)[0]);code=0
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
