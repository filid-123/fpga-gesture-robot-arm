"""Windows native serial commissioning of residual candidates, never on import.

This is a PC motion trial, not FPGA-autonomous Mode A. --dry-run needs no port.
--run explicitly selects one object and hover, pick/return or full handover.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,math,threading,time

AXES=('b','s','e','t','r','g')
WIRE=('base','shoulder','elbow','wrist','roll','hand')
ROOT=Path(__file__).resolve().parents[1]
VERSION='0.5.1'
STEPS_PER_REV=4096
SPEED_STEPS_S=100
ACC_100_STEPS_S2=3


def execution_profile():
    return dict(speed_steps_s=SPEED_STEPS_S,acceleration_100_steps_s2=ACC_100_STEPS_S2,
        speed_deg_s=SPEED_STEPS_S*360/STEPS_PER_REV,
        acceleration_deg_s2=ACC_100_STEPS_S2*100*360/STEPS_PER_REV,
        planned_velocity_deg_s=8,planned_acceleration_deg_s2=16,
        sample_acceleration_difference_bound_deg_s2=17.5,
        source='https://docs.waveshare.net/RoArm-M3/JSON-Command-Control/')


def packet(q):
    if len(q)!=6 or any(not math.isfinite(v) for v in q):raise ValueError('six finite joints required')
    def rounded(v):return math.copysign(math.floor(abs(v)*10000+.5),v)/10000
    fields=','.join('"'+k+'":'+format(rounded(v),'.4f') for k,v in zip(WIRE,q))
    return ('{"T":102,'+fields+f',"spd":{SPEED_STEPS_S},"acc":{ACC_100_STEPS_S2}'+'}\n').encode('ascii')


def feedback(raw):
    p=json.loads(raw)
    if p.get('T')!=1051:return None
    q=[float(p[k]) for k in AXES]
    if any(not math.isfinite(v) for v in q):raise ValueError('nonfinite feedback')
    return q


def load(root,trial,obj):
    m=json.loads((root/'TRIAL_MANIFEST.json').read_text('utf-8'))
    if m['version']!=VERSION or m['physical_validated'] is not False:raise ValueError('Wrong trial identity/provenance')
    for name,digest in m['trial_inputs'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:raise ValueError('Changed trial input '+name)
    plan=json.loads((root/'candidate/PLAN_NATIVE.json').read_text('utf-8'))
    result=json.loads((root/'candidate/COPPELIA_RESULT.json').read_text('utf-8'))
    if not result['passed'] or result['collision_samples']!=0:raise ValueError('Candidate simulation failed')
    if result['native_plan_sha256']!=hashlib.sha256((root/'candidate/PLAN_NATIVE.json').read_bytes()).hexdigest():
        raise ValueError('Simulation belongs to another native plan')
    paths=plan['hover_paths'] if trial=='hover' else (plan['paths'] if trial=='handover' else plan['return_paths'])
    route=next(p for p in paths if p['object']==obj)
    for leg in route['legs']:
        q=[v/65536 for v in leg['target_q16']]
        if any(not lo<=v<=hi for v,(lo,hi) in zip(q,plan['native_limits_rad'])):raise ValueError('Candidate limit')
    return plan,route


class SerialLink:
    def __init__(self,port):
        import serial
        self.serial=serial.Serial();self.serial.port=port;self.serial.baudrate=115200
        self.serial.timeout=.02;self.serial.write_timeout=.1
        self.serial.dtr=False;self.serial.rts=False
        self.lock=threading.Lock();self.last=None;self.seq=0;self.stamp=0.;self.error=None;self.stop=False
        self.serial.open()
        self.worker=threading.Thread(target=self.receive,daemon=True);self.worker.start()
    def receive(self):
        data=bytearray()
        try:
            while not self.stop:
                b=self.serial.read(1)
                if not b:continue
                if b==b'\n':
                    raw=bytes(data);data.clear()
                    try:q=feedback(raw)
                    except (ValueError,KeyError,TypeError,UnicodeError):continue
                    if q is not None:
                        with self.lock:self.last=q;self.seq+=1;self.stamp=time.monotonic()
                else:
                    data.extend(b)
                    if len(data)>1024:raise RuntimeError('Feedback line exceeds1024 bytes')
        except BaseException as exc:self.error=str(exc)
    def status(self):
        if self.error:raise RuntimeError('Serial reader: '+self.error)
        with self.lock:return self.seq,None if self.last is None else self.last[:],self.stamp
    def send(self,q):
        data=packet(q)
        if self.serial.write(data)!=len(data):raise RuntimeError('Partial motion command write')
    def query(self):self.serial.write(b'{"T":105}\n')
    def close(self):
        self.stop=True;self.worker.join(timeout=1);self.serial.close()


def runtime_start(route,actual):
    """Regenerate HOME_OPEN from fresh joints, including a partly open hand."""
    if not route['legs'] or route['legs'][0]['label']!='HOME_OPEN':return route
    import copy,sys
    sys.path.insert(0,str(ROOT/'ps/robot'))
    import planner_p2p_reference as p
    def quant(v):return int(math.copysign(math.floor(abs(v)*65536+.5),v))
    start=tuple(map(quant,actual));target=tuple(route['legs'][0]['target_q16'])
    delta=max(abs(a-b)/65536 for a,b in zip(start,target))
    duration=max(.4,delta/math.radians(8)*1.5,math.sqrt(delta/math.radians(16)*6))
    n=max(20,math.ceil(duration/.02));na=max(1,n//4)
    cfg=p.MoveParams(start,target,n,na,1,2_000_000,50_000_000,
        (math.ceil(math.radians(8)*.02*65536)+2,)*6,
        (math.ceil(math.radians(16)*.02**2*(1<<32))+2,)*6)
    if not p.validate(cfg,last_delivered=start).ok:raise ValueError('Runtime bridge exceeds S2 limits')
    out=copy.deepcopy(route)
    out['legs'][0].update(label='HOME_OPEN_FROM_FEEDBACK',start_q16=list(start),n=n,na=na,seconds=n*.02)
    out['samples']=[dict(segment=0,tick=k+1,q16=list(q)) for k,q in enumerate(p.samples(cfg))]+[r for r in out['samples'] if r['segment']!=0]
    out['seconds']=sum(l.get('seconds',0) for l in out['legs'])
    return out


def arrival_errors(actual,target,shoulder_policy):
    errors=[a-b for a,b in zip(actual,target)]
    if shoulder_policy=='observe' and abs(errors[1])>.15:
        raise RuntimeError('Shoulder gross error >0.15rad; observation policy does not suppress this fault')
    mask=0x3f if shoulder_policy=='strict' else 0x3d
    tol=[.02]*5+[.04]
    return all(abs(e)<=tol[i] for i,e in enumerate(errors) if mask&(1<<i)),errors,mask


def console_ready(kind,pump):
    """Keep feedback polling while the operator confirms the stopped pose."""
    import msvcrt
    text='确认木块已夹住，掌心在固定交付位置就位后按 Enter 继续；Esc/Ctrl+C 停止保持。' if kind=='PALM_READY' else '悬停观察完成后按 Enter 返回；Esc/Ctrl+C 停止。'
    print(text,flush=True)
    while msvcrt.kbhit():
        if msvcrt.getwch() in ('\x1b','\x03'):raise KeyboardInterrupt('Operator stopped at '+kind)
    end=time.monotonic()+120
    while time.monotonic()<end:
        pump()
        if msvcrt.kbhit():
            key=msvcrt.getwch()
            if key=='\r':return
            if key in ('\x1b','\x03'):raise KeyboardInterrupt('Operator stopped at '+kind)
        time.sleep(.02)
    raise TimeoutError('Operator readiness timeout at '+kind)


def drive(link,plan,route,emit,clock=time.monotonic,pause=time.sleep,dwell=None,*,shoulder_policy='observe',confirm=console_ready):
    dt=.02;tol=[.02]*5+[.04];last=None;holding=False;query_stamp=-1.;last_emit=-1.
    def query():
        nonlocal query_stamp
        if clock()-query_stamp>=.06:link.query();query_stamp=clock()
    def fresh(required=True):
        seq,q,stamp=link.status()
        if required and (q is None or clock()-stamp>.5):raise RuntimeError('Feedback missing/stale >500ms')
        return seq,q,stamp
    def report(kind,label,q=None,**extra):
        seq,actual,stamp=fresh(False)
        errors=None if q is None or actual is None else [a-b for a,b in zip(actual,q)]
        emit(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),host_monotonic_s=clock(),source='PC_NATIVE_COMMISSIONING_NOT_FPGA_A',
            event=kind,object=route['object'],trial=route['kind'],label=label,command_rad=q,
            feedback_rad=actual,feedback_seq=seq,feedback_age_ms=None if actual is None else round((clock()-stamp)*1000,1),
            holding=holding,physical_validated=False,wire_speed_steps_s=SPEED_STEPS_S,wire_acceleration_100_steps_s2=ACC_100_STEPS_S2,
            shoulder_policy=shoulder_policy,arrival_mask=0x3d if shoulder_policy=='observe' else 0x3f,
            snapshot_error_rad=errors,shoulder_outside_precise_tolerance=False if errors is None else abs(errors[1])>.02,**extra))
    try:
        # Read three distinct stable samples. A partially open hand is allowed;
        # the first segment is regenerated from the real pose, not old HOME g.
        end=clock()+2
        seen=-1;stable=0;previous=None
        while clock()<end:
            query();seq,q,_=fresh(False)
            if q is not None and seq!=seen:
                stable=stable+1 if previous is not None and max(abs(a-b) for a,b in zip(previous,q))<.01 else 1
                previous=q[:];seen=seq
                if stable>=3:break
            pause(.01)
        if stable<3:raise RuntimeError('No three stable startup feedback samples')
        _,q,_=fresh()
        home=plan['home_native_rad'];home_tol=[math.radians(v) for v in [1.5,4.5,2.5,3,1.5,2.5]]
        if any(abs(a-b)>t for a,b,t in zip(q[:5],home[:5],home_tol[:5])):raise RuntimeError('Arm not near recorded HOME; no motion sent')
        bounds=plan.get('native_limits_rad',[[-math.pi,math.pi],[-math.pi/2,math.pi/2],[0,math.pi],[-math.pi/2,math.pi/2],[-math.pi,math.pi],[1.08,math.pi]])
        if any(not math.isfinite(v) or not lo<=v<=hi for v,(lo,hi) in zip(q,bounds)):raise RuntimeError('Startup feedback outside native envelope')
        route=runtime_start(route,q)
        report('START_NEAR_HOME','MEASURED_START',q,execution_profile=execution_profile(),runtime_first_segment=route['legs'][0])
        frame=0
        for i,leg in enumerate(route['legs']):
            if leg['grasp']:holding=True
            rows=[r for r in route['samples'] if r['segment']==i]
            start=clock()
            for j,row in enumerate(rows):
                target=start+j*dt
                if clock()<target:pause(target-clock())
                if clock()-target>.04:raise RuntimeError('Host scheduler >40ms late; refusing burst catch-up')
                _,actual,_=fresh();last=[v/65536 for v in row['q16']]
                if shoulder_policy=='observe' and abs(actual[1]-last[1])>.15:raise RuntimeError('Shoulder gross error >0.15rad')
                link.send(last);frame+=1
                report('TX_COMMAND',leg['label'],last,wire_command=packet(last).decode('ascii').strip())
                if frame%3==0:query()
                if clock()-last_emit>=.2:report('STREAM',leg['label'],last);last_emit=clock()
            holding=holding or bool(leg['grasp'])
            if leg['phase']=='release':holding=False
            # Shoulder is observable-only by this user's request. Other five
            # axes retain their original tolerances, including the hand.
            seen=fresh()[0];consecutive=0;deadline=clock()+3
            while clock()<deadline:
                query();seq,actual,_=fresh()
                if seq!=seen:
                    seen=seq;ok,_,_=arrival_errors(actual,last,shoulder_policy)
                    consecutive=consecutive+1 if ok else 0
                    if consecutive>=3:break
                pause(.01)
            if consecutive<3:raise RuntimeError('Arrival failed at '+leg['label']+'; thresholds unchanged')
            report('ARRIVED' if shoulder_policy=='strict' else 'STEP_ACCEPTED_SHOULDER_OBSERVED',leg['label'],last)
            wait_report=[clock()]
            def pump():
                query();fresh()
                if clock()-wait_report[0]>=.5:
                    report('WAIT_FEEDBACK',leg['label'],last);wait_report[0]=clock()
            if route['kind']=='hover' and leg['label']=='SLOT_HIGH':
                # A stopped, open-gripper observation. Controller retains target.
                # Reader still runs while operator inspects the candidate.
                report('HOVER_OBSERVE','SLOT_HIGH',last)
                dwell() if dwell is not None else confirm('HOVER_OBSERVE',pump)
                query();pause(.07);fresh()
            if route['kind']=='handover' and leg['phase']=='lift' and (i+1==len(route['legs']) or route['legs'][i+1]['phase']!='lift'):
                report('WAIT_OPERATOR_PALM_READY','PRE',last)
                confirm('PALM_READY',pump)
                report('OPERATOR_PALM_READY','PRE',last)
        report('TRIAL_DONE','HOME',last,slot_after_trial='EMPTY' if route['kind']=='handover' else ('RESTORED' if route['kind']=='return' else 'UNCHANGED'))
    except BaseException as exc:
        # One bounded hold request only when measured joints are fresh. Preserve
        # the commanded grip under load; never automatically open/retrace.
        try:
            _,q,stamp=link.status()
            if last is not None and q is not None and clock()-stamp<=.2:
                stop=q[:]
                if holding:stop[5]=last[5]
                link.send(stop)
                report('STOP_HOLD_COMMAND_SENT',str(exc),stop,wire_command=packet(stop).decode('ascii').strip())
            report('STOP_NO_AUTOMATIC_RETURN',str(exc),last)
        finally:raise


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=ROOT);ap.add_argument('--object',type=int,choices=[1,2,3],required=True)
    ap.add_argument('--trial',choices=['hover','pick-return','handover'],default='handover')
    ap.add_argument('--shoulder-policy',choices=['observe','strict'],default='observe')
    mode=ap.add_mutually_exclusive_group(required=True);mode.add_argument('--dry-run',action='store_true');mode.add_argument('--run',action='store_true')
    ap.add_argument('--port');ap.add_argument('--out',type=Path);a=ap.parse_args()
    plan,route=load(a.root,a.trial,a.object)
    if a.dry_run:
        for leg in route['legs']:print(leg['label'],packet([v/65536 for v in leg['target_q16']]).decode().strip())
        print(json.dumps(dict(source='DRY_RUN_NO_HARDWARE',object=a.object,trial=a.trial,seconds=route['seconds'],samples=len(route['samples']),
            shoulder_policy=a.shoulder_policy,execution_profile=execution_profile())));return
    if not a.port or not a.out:ap.error('--run needs explicit --port COMx and a new --out log')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as log:
        def emit(row):
            log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush()
            if row['event']!='TX_COMMAND':
                print(f"{row['event']} object={row['object']} stage={row['label']} cmd={row['command_rad']} actual={row['feedback_rad']} age={row['feedback_age_ms']}ms shoulder_error={None if row['snapshot_error_rad'] is None else row['snapshot_error_rad'][1]} speed={row['wire_speed_steps_s']} acc={row['wire_acceleration_100_steps_s2']}",flush=True)
        link=SerialLink(a.port)
        try:drive(link,plan,route,emit,shoulder_policy=a.shoulder_policy)
        finally:link.close()


if __name__=='__main__':main()
