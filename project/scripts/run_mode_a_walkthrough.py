"""v0.6.0 operator walkthrough: timed progression, all arrival errors observed.

No physical access on import/dry-run. Live serial execution requires --run.
Communication, valid command data and manual stop are retained. No axis error,
HOME proximity, three-sample arrival, or arrival timeout gates progression.
"""
from pathlib import Path
import argparse,copy,datetime,hashlib,json,math,sys,time
from run_mode_a_residual_trial import SerialLink

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ps/robot'))
import planner_p2p_reference as p2p
VERSION='0.6.0';DT=.02;SPEED_STEPS_S=160;ACC_100_STEPS_S2=5


def profile():
    return dict(version=VERSION,arrival_policy='observe_all',arrival_mask=0,
        planned_speed_deg_s=12,planned_acceleration_deg_s2=24,
        handover_speed_deg_s=8,handover_acceleration_deg_s2=16,
        speed_steps_s=SPEED_STEPS_S,acceleration_100_steps_s2=ACC_100_STEPS_S2,
        native_speed_deg_s=SPEED_STEPS_S*360/4096,
        native_acceleration_deg_s2=ACC_100_STEPS_S2*100*360/4096,
        period_ms=20,settle_regular_s=.35,settle_grasp_s=.8,settle_release_s=.8,
        readiness_source='OPERATOR_ENTER_AT_PRE',operator_ready_timeout_s=None,precision_is_not_a_motion_gate=True,
        scheduler_policy='stretch timing on host delay; never burst or skip samples')


def packet(q):
    if len(q)!=6 or any(not math.isfinite(v) for v in q):raise ValueError('Six finite native joints required')
    def fmt(v):return format(math.copysign(math.floor(abs(v)*10000+.5),v)/10000,'.4f')
    fields=','.join('"'+key+'":'+fmt(v) for key,v in zip(('base','shoulder','elbow','wrist','roll','hand'),q))
    return ('{"T":102,'+fields+f',"spd":{SPEED_STEPS_S},"acc":{ACC_100_STEPS_S2}'+'}\n').encode('ascii')


class Link(SerialLink):
    def send(self,q):
        data=packet(q)
        if self.serial.write(data)!=len(data):raise RuntimeError('Partial motion command write')


def quant(q):return tuple(int(math.copysign(math.floor(abs(v)*65536+.5),v)) for v in q)


def segment(start,target,label,phase):
    near_hand=label.startswith(('HANDOVER','HAND_CLEAR','RELEASE'))
    v=math.radians(8 if near_hand else 12);a=math.radians(16 if near_hand else 24)
    delta=max(abs(x-y)/65536 for x,y in zip(start,target))
    n=max(20,math.ceil(max(.4,delta/v*1.5,math.sqrt(delta/a*6))/DT));na=max(1,n//4)
    cfg=p2p.MoveParams(tuple(start),tuple(target),n,na,1,2_000_000,50_000_000,
        (math.ceil(v*DT*65536)+2,)*6,(math.ceil(a*DT*DT*(1<<32))+2,)*6)
    if not p2p.validate(cfg,last_delivered=cfg.start).ok:raise ValueError('Invalid generated S2 segment')
    return dict(start_q16=list(start),target_q16=list(target),n=n,na=na,profile=1,
                period_cycles=2_000_000,seconds=n*DT),p2p.samples(cfg)


def retime_route(source):
    route=copy.deepcopy(source);route['samples']=[]
    for i,leg in enumerate(route['legs']):
        meta,samples=segment(leg['start_q16'],leg['target_q16'],leg['label'],leg['phase']);leg.update(meta)
        route['samples'].extend(dict(segment=i,tick=k+1,q16=list(q)) for k,q in enumerate(samples))
    route['seconds']=sum(l['seconds'] for l in route['legs'])
    return route


def waypoint_group(label):
    if label.endswith('_FROM_FEEDBACK'):label=label[:-len('_FROM_FEEDBACK')]
    return label.rsplit('_',1)[0] if label.rsplit('_',1)[-1].isdigit() else label


def wait_for_operator(kind,pump,key_ready,read_key,pause=time.sleep):
    """No readiness deadline; keep feedback polling until Enter or manual stop."""
    while key_ready():
        if read_key() in ('\x1b','\x03'):raise KeyboardInterrupt('Operator stopped at '+kind)
    while True:
        pump()
        if key_ready():
            key=read_key()
            if key=='\r':return
            if key in ('\x1b','\x03'):raise KeyboardInterrupt('Operator stopped at '+kind)
        pause(.02)


def console_ready(kind,pump):
    import msvcrt
    text='确认木块已夹住、掌心在本版交付点就位后按 Enter；无等待超时，Esc/Ctrl+C 停止保持。' if kind=='PALM_READY' else '观察完成按 Enter 返回；无等待超时，Esc/Ctrl+C 停止。'
    print(text,flush=True)
    wait_for_operator(kind,pump,msvcrt.kbhit,msvcrt.getwch)


def resume_info(route,path):
    if path is None:return dict(index=0,holding=False,source=None)
    rows=[json.loads(v) for v in path.read_text('utf-8').splitlines() if v.strip()]
    if not rows or any(r.get('object')!=route['object'] for r in rows):raise ValueError('Resume log object mismatch')
    if rows[-1].get('event')=='TRIAL_DONE':raise ValueError('This log already completed; select a new trial after replenishment')
    tx=next((r for r in reversed(rows) if r.get('event') in ('TX_COMMAND','STREAM')),None)
    if tx is None:return dict(index=0,holding=False,source=str(path))
    if tx.get('trial')!=route['kind']:raise ValueError('Resume log trial mismatch')
    if route.get('layout_id') and tx.get('layout_id')!=route['layout_id']:
        raise ValueError('Resume log uses a different layout; finish/remove the held object and start a new trial')
    label=tx['label'];labels=[l['label'] for l in route['legs']]
    while label not in labels and label.endswith('_FROM_FEEDBACK'):label=label[:-len('_FROM_FEEDBACK')]
    if label not in labels:raise ValueError('Unknown interrupted waypoint '+label)
    return dict(index=labels.index(label),holding=bool(rows[-1].get('holding',False)),
        source=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),interrupted_label=label)


def connect_route(route,actual,resume):
    out=copy.deepcopy(route);first=resume['index'];out['legs']=out['legs'][first:];out['samples']=[]
    for i,leg in enumerate(out['legs']):
        if i==0:
            old=leg['label'];leg['label']=old+'_FROM_FEEDBACK'
            start=quant(actual)
        else:start=tuple(leg['start_q16'])
        meta,samples=segment(start,leg['target_q16'],leg['label'],leg['phase']);leg.update(meta)
        out['samples'].extend(dict(segment=i,tick=k+1,q16=list(q)) for k,q in enumerate(samples))
    out['seconds']=sum(l['seconds'] for l in out['legs']);return out


def load(root,obj,trial):
    m=json.loads((root/'WALKTHROUGH_MANIFEST.json').read_text('utf-8'))
    if m['version']!=VERSION or m['arrival_policy']!='observe_all':raise ValueError('Wrong walkthrough package')
    for name,digest in m['inputs'].items():
        q=(root/name).resolve()
        if not q.is_relative_to(root.resolve()) or hashlib.sha256(q.read_bytes()).hexdigest()!=digest:raise ValueError('Changed input '+name)
    plan=json.loads((root/'candidate/PLAN_NATIVE.json').read_text('utf-8'))
    if plan['layout_id']!=m['layout_id']:raise ValueError('Layout binding')
    for name in ('COPPELIA_RESULT.json','COPPELIA_WIRE_RESULT.json'):
        sim=json.loads((root/'candidate'/name).read_text('utf-8'))
        if not sim['passed'] or sim['native_plan_sha256']!=hashlib.sha256((root/'candidate/PLAN_NATIVE.json').read_bytes()).hexdigest():raise ValueError('Simulation binding '+name)
    key={'hover':'hover_paths','pick-return':'return_paths','handover':'paths'}[trial]
    return plan,next(p for p in plan[key] if p['object']==obj)


def drive(link,plan,route,emit,clock=time.monotonic,pause=time.sleep,confirm=console_ready,resume=None):
    holding=bool((resume or {}).get('holding',False));last=None;label='START';query_at=-1.;printed=-1.
    def query():
        nonlocal query_at
        if clock()-query_at>=.06:link.query();query_at=clock()
    def fresh(required=True):
        seq,q,stamp=link.status()
        if required and (q is None or clock()-stamp>.5):raise RuntimeError('Feedback missing/stale >500ms')
        return seq,q,stamp
    def report(event,command=None,**extra):
        seq,q,stamp=fresh(False)
        errors=None if q is None or command is None else [a-b for a,b in zip(q,command)]
        warnings=0 if errors is None else sum((1<<i) for i,e in enumerate(errors) if abs(e)>(.04 if i==5 else .02))
        emit(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),host_monotonic_s=clock(),
            source='PC_NATIVE_WALKTHROUGH',event=event,label=label,object=route['object'],trial=route['kind'],layout_id=plan.get('layout_id'),
            command_rad=command,feedback_rad=q,feedback_seq=seq,feedback_age_ms=None if q is None else round((clock()-stamp)*1000,1),
            snapshot_error_rad=errors,precision_warning_mask=warnings,arrival_policy='observe_all',arrival_mask=0,
            holding=holding,physical_task_pass=None,speed_steps_s=SPEED_STEPS_S,acceleration_100_steps_s2=ACC_100_STEPS_S2,**extra))
    def wait(seconds):
        nonlocal printed
        end=clock()+seconds
        while clock()<end:
            query();fresh()
            if clock()-printed>=.2:report('OBSERVE',last);printed=clock()
            pause(min(.02,max(0,end-clock())))
    def readiness(kind):
        report('WAIT_OPERATOR_'+kind,last)
        def pump():
            nonlocal printed
            query();fresh()
            if clock()-printed>=.5:report('WAIT_FEEDBACK',last);printed=clock()
        confirm(kind,pump);report('OPERATOR_'+kind,last)
    try:
        deadline=clock()+2
        while clock()<deadline:
            query();_,actual,_=fresh(False)
            if actual is not None:break
            pause(.01)
        _,actual,_=fresh()
        # Absolute native command validity is retained; no proximity/arrival
        # comparison with HOME is used by this walkthrough controller.
        if len(actual)!=6 or any(not math.isfinite(v) or not lo<=v<=hi for v,(lo,hi) in zip(actual,plan['native_limits_rad'])):
            raise ValueError('Invalid native starting data')
        resume=resume or dict(index=0,holding=False,source=None)
        route=connect_route(route,actual,resume)
        report('START_FROM_FEEDBACK',actual,execution_profile=profile(),resume=resume,
               runtime_first_segment=route['legs'][0],remaining_legs=len(route['legs']))
        if holding and route['legs'][0]['phase'] in ('deliver','release'):readiness('PALM_READY')
        frame=0;next_send=clock()
        for i,leg in enumerate(route['legs']):
            label=leg['label']
            if leg['grasp']:holding=True
            rows=[r for r in route['samples'] if r['segment']==i]
            next_send=max(next_send,clock())
            for j,row in enumerate(rows):
                if clock()<next_send:pause(next_send-clock())
                if clock()-next_send>.04:
                    report('HOST_LATE_STRETCH',last,late_ms=round((clock()-next_send)*1000,1));next_send=clock()
                fresh();last=[v/65536 for v in row['q16']];link.send(last);frame+=1
                next_send+=DT
                report('TX_COMMAND',last,wire_command=packet(last).decode('ascii').strip())
                if frame%3==0:query()
                if clock()-printed>=.2:report('STREAM',last);printed=clock()
            same_waypoint=i+1<len(route['legs']) and waypoint_group(leg['label'])==waypoint_group(route['legs'][i+1]['label'])
            settle=0 if same_waypoint else (.8 if leg['phase'] in ('grasp','release') else .35)
            wait(settle)
            if leg['phase']=='release':holding=False
            report('WAYPOINT_FINISHED_OBSERVED',last,progress_condition='planned samples and fixed settle elapsed; precision not required',
                fixed_settle_s=settle,waypoint_D_mm=leg.get('target_D_mm'))
            if route['kind']=='hover' and leg['label'].startswith('SLOT_HIGH'):readiness('HOVER_OBSERVE')
            if route['kind']=='handover' and leg['phase']=='lift' and (i+1==len(route['legs']) or route['legs'][i+1]['phase']!='lift'):
                readiness('PALM_READY')
        label='HOME';report('TRIAL_DONE',last,meaning='Commanded full sequence finished; physical task outcome requires operator observation',
            slot_after_trial='EMPTY' if route['kind']=='handover' else ('RESTORED' if route['kind']=='return' else 'UNCHANGED'))
    except BaseException as exc:
        try:
            _,q,stamp=link.status()
            if last is not None and q is not None and clock()-stamp<=.2:
                stop=q[:]
                if holding:stop[5]=last[5]
                link.send(stop);report('STOP_HOLD_COMMAND_SENT',stop,wire_command=packet(stop).decode('ascii').strip())
            report('STOP_NO_AUTOMATIC_RETURN',last,reason=str(exc))
        finally:raise


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',type=Path,default=ROOT)
    ap.add_argument('--object',type=int,choices=[1,2,3],required=True);ap.add_argument('--trial',choices=['handover','hover','pick-return'],default='handover')
    mode=ap.add_mutually_exclusive_group(required=True);mode.add_argument('--run',action='store_true');mode.add_argument('--dry-run',action='store_true')
    ap.add_argument('--resume-log',type=Path);ap.add_argument('--port');ap.add_argument('--out',type=Path);a=ap.parse_args()
    plan,route=load(a.root,a.object,a.trial);resume=resume_info(route,a.resume_log)
    if a.dry_run:
        for l in route['legs'][resume['index']:]:print(l['label'],packet([v/65536 for v in l['target_q16']]).decode().strip())
        print(json.dumps(dict(source='DRY_RUN_NO_HARDWARE',resume=resume,execution_profile=profile())));return
    if not a.port or not a.out:ap.error('--run needs explicit --port and a new --out')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as log:
        print('WALKTHROUGH v'+VERSION+': 六轴误差仅记录，arrival_mask=0；普通转运12deg/s，T102 spd=160 acc=5；PRE等待无超时。',flush=True)
        def emit(row):
            log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush()
            if row['event']!='TX_COMMAND':
                hint='' if row.get('waypoint_D_mm') is None else ' D_mm='+str(row['waypoint_D_mm'])
                print(f"{row['event']} obj={row['object']} stage={row['label']} cmd={row['command_rad']} actual={row['feedback_rad']} error={row['snapshot_error_rad']} age={row['feedback_age_ms']}ms speed={SPEED_STEPS_S} acc={ACC_100_STEPS_S2}"+hint,flush=True)
        link=Link(a.port)
        try:drive(link,plan,route,emit,resume=resume)
        finally:link.close()


if __name__=='__main__':main()
