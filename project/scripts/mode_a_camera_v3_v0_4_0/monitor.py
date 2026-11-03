"""Reusable black-scene v2 camera-only observation; no motion writes."""
from pathlib import Path
import argparse,datetime,hashlib,json,signal,subprocess,sys,threading,time
import verify_exposure as e
from transport_reused import Bridge,BASE,HERE,inert
import service_owner as owner

MODEL=('BACKGROUND','ONE','TWO','THREE','FIST','PALM','GATED','NO_DETECTION')
TASK=('BACKGROUND','ONE','TWO','THREE','PALM','FIST','GATED','NO_DETECTION')
OPTIONS=dict(seconds=120,label=None,images=0)

class SampleCounts:
 """One entry per sampled result identity; never claim all physical frames."""
 def __init__(self,label):
  self.label=label;self.last=None;self.n=0;self.correct=0;self.confirmed=0;self.hist=[0]*8;self.windows={}
 def add(self,s,elapsed):
  identity=(s['result_frame_id'],s['acquisition_ms'])
  if identity==self.last:return False
  self.last=identity;self.n+=1;self.hist[s['model_class']]+=1
  w=self.windows.setdefault(int(elapsed//10),dict(samples=0,model_correct=0,confirmed_correct=0))
  w['samples']+=1
  if self.label is None:return True
  model=dict(one=1,two=2,three=3,fist=4,palm=5)
  if self.label=='empty':
   ok=s['model_class'] in (0,7)
   confirmed=not s['qualified'] or s['task_class'] in (0,7)
  else:
   expected=model[self.label];task=4 if expected==5 else 5 if expected==4 else expected
   ok=s['model_class']==expected
   confirmed=ok and s['qualified'] and bool(s['vision_status']&1) and s['task_class']==task
  self.correct+=int(ok);self.confirmed+=int(confirmed)
  w['model_correct']+=int(ok);w['confirmed_correct']+=int(confirmed)
  return True
 def report(self):
  result=dict(ground_truth=self.label,sampled_distinct_results=self.n,model_histogram=dict(zip(MODEL,self.hist)),ten_second_windows=self.windows)
  if self.label is not None:
   result.update(model_correct=self.correct,model_accuracy_percent=100*self.correct/self.n if self.n else None,
    confirmed_correct=self.confirmed,confirmed_percent=100*self.confirmed/self.n if self.n else None,
    confirmed_definition='empty: no qualified gesture; gestures: model and qualified fresh task both correct')
  else:result['accuracy']='NOT_COMPUTED_WITHOUT_FIXED_GROUND_TRUTH'
  return result

def led_code(task,qualified,fatal=False):
 if fatal:return 15
 return (8|task) if qualified and task!=7 else 0

def observe(b,r,stop,stream,clock=time.monotonic,pause=time.sleep):
 options=r.get('options',OPTIONS)
 baseline=e.c.startup(b,r,clock,pause)
 if b.read(BASE+0x94)[0]!=0x45585031:raise RuntimeError('EXP1 mismatch')
 r['initial_completed_result']=e.initial_result(b,baseline,clock,pause)
 cfg={f'{a:04X}':e.command(b,r,a) for a in (0x300a,0x300b,0x3808,0x3809,0x380a,0x380b,0x380e,0x380f,0x4300,0x501f)}
 if cfg['300A']!=0x56 or cfg['300B']!=0x40 or ((cfg['3808']<<8)|cfg['3809'],(cfg['380A']<<8)|cfg['380B'])!=(640,480) or cfg['4300']!=0x30 or cfg['501F']!=0:raise RuntimeError('Sensor ID/geometry/YUV mismatch')
 r['initial_sensor_registers']=cfg;r['vts']=cfg['380E']<<8|cfg['380F']
 r['original_sensor']=e.freeze(b,r);r['fixed_profile']=e.apply(b,r,r['original_sensor'],984,80)
 r['result']='LED_MONITOR_RUNNING'
 print('CAMERA_V2_READY | model=022267A9 exposure=984lines gain_code=80 | Ctrl+C to stop safely',flush=True)
 print('LED order: LD3 LD2 LD1 LD0 | ONE1001 TWO1010 THREE1011 PALM1100 FIST1101',flush=True)
 # Snapshots deliberately precede statistics: freezing the bank pauses live results.
 for i in range(options['images']):
  if stop.is_set():break
  inert(b);e.c.image(b,r,baseline,i,clock,pause);e.c.fresh_after_snapshot(b,r,baseline,clock,pause)
  r['images'][-1]['ground_truth']=options['label']
  e.save(f'camera_{i:02d}_128x128.json',r['images'][-1])
 print('LIVE_RECORDING_STARTED | hold one gesture only for labelled runs',flush=True)
 started=clock();last_new=started;counts=SampleCounts(options['label'])
 last_print=-float('inf');last_motion=-float('inf');samples=0;age_min=0xffffffff;age_max=0
 while not stop.is_set():
  s=e.checked(b,baseline);now=clock()
  if s['model_id']!=0x022267a9:raise RuntimeError('Live model ID mismatch')
  if now-last_motion>=1:inert(b);last_motion=now
  samples+=1;age_min=min(age_min,s['source_age_ms']);age_max=max(age_max,s['source_age_ms'])
  s['expected_led_bits']=format(led_code(s['task_class'],s['qualified']), '04b')
  s['observation_wall_s']=now-started;s['ground_truth']=options['label']
  if counts.add(s,now-started):last_new=now
  if now-last_new>2:raise RuntimeError('No new completed camera result in two seconds')
  r['statistics']=counts.report()
  stream.write(json.dumps(s)+'\n');stream.flush()
  if now-last_print>=1:
   print(f"fid={s['result_frame_id']} model={MODEL[s['model_class']]} stable={TASK[s['task_class']]} qualified={int(s['qualified'])} LED_expected={s['expected_led_bits']} age={s['source_age_ms']}ms format={s['format_errors']} samples={counts.n}",flush=True)
   e.save('SESSION_RESULT.json',r)
   last_print=now
  r.update(health_samples=samples,source_age_min_ms=age_min,source_age_max_ms=age_max,last_state=s)
  if options['seconds'] and now-started>=options['seconds']:break
  pause(.2)
 r['final_motion_state']=inert(b);r['result']='LED_MONITOR_STOPPED_BY_OPERATOR'
 r['observation_ended_by']='OPERATOR' if stop.is_set() else 'DURATION'

def run_session(r,stop,stream,factory=Bridge,observer=observe):
 b=None
 try:
  b=factory();b.wait_ready();observer(b,r,stop,stream)
 except Exception as exc:r.update(result='STOPPED_ERROR',error=repr(exc))
 finally:
  if b is not None:
   if not b.failed and not r.get('sensor_command_fault'):
    try:e.restore_sensor(b,r)
    except Exception as exc:r.update(result='SENSOR_RESTORE_FAILED',sensor_restore_error=repr(exc),requires_user_power_cycle=True)
   elif r.get('sensor_command_fault'):
    r.update(sensor_restore='NOT_ATTEMPTED_AFTER_SENSOR_COMMAND_FAULT',requires_user_power_cycle=True)
   try:b.close();r['shutdown']='PASS_REVISED_ISOLATED_SHUTDOWN'
   except Exception as exc:r.update(result='RESTORE_INCOMPLETE',restore_error=repr(exc),requires_user_power_cycle=True)
 return 0 if r['result']=='LED_MONITOR_STOPPED_BY_OPERATOR' and r.get('shutdown')=='PASS_REVISED_ISOLATED_SHUTDOWN' and r.get('sensor_restore')=='ORIGINAL_VALUES_AND_MODE_VERIFIED' else 2

class OwnedServer:
 def __init__(self):self.service=None;self.pid=None;self.log=None;self.record={}
 def save(self):e.save('DEBUG_SERVICE_RECORD.json',self.record)
 def start(self):
  if owner.listeners():raise RuntimeError('Port3121 is already owned by another service; close your existing hardware tools first')
  self.record=dict(owned=True,started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
  self.log=(HERE/'hw_server_stdout.txt').open('xb',buffering=0)
  cmd=owner.command(['E:/Xilinx/2026.1/Vivado/bin/hw_server.bat','-s','tcp::3121'])
  self.service=subprocess.Popen(cmd,cwd=HERE,stdout=self.log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
  self.record.update(launcher_pid=self.service.pid,server_command=cmd);self.save();deadline=time.monotonic()+15
  while time.monotonic()<deadline:
   if self.service.poll() is not None:raise RuntimeError('Owned hw_server launcher exited')
   active=owner.listeners()
   if active:
    if len(active)!=1 or active[0]['Name'].lower()!='hw_server.exe':raise RuntimeError('Unexpected listener')
    chain=owner.ancestry(active[0]['ProcessId'])
    if not any(p['ProcessId']==self.service.pid for p in chain):raise RuntimeError('Listener is not owned')
    if not active[0]['ExecutablePath'].lower().startswith('e:\\xilinx\\2026.1\\vivado\\'):raise RuntimeError('Unexpected server binary')
    self.pid=active[0]['ProcessId'];self.record.update(server_pid=self.pid,listener=active[0],ancestry=chain);self.save();return
   time.sleep(.25)
  raise TimeoutError('Owned hw_server did not listen in time')
 def close(self):
  try:
   if self.pid is not None and self.service is not None:
    active=owner.listeners()
    if any(p['ProcessId']==self.pid for p in active) and any(p['ProcessId']==self.service.pid for p in owner.ancestry(self.pid)):
     owner.ps(f'Stop-Process -Id {int(self.pid)} -Force -ErrorAction Stop');self.record['owned_server_stopped']=True
   if self.service is not None:
    try:self.service.wait(timeout=5)
    except subprocess.TimeoutExpired:subprocess.run(['taskkill.exe','/PID',str(self.service.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    self.record['launcher_returncode']=self.service.poll()
   self.record['listeners_after_close']=owner.listeners()
   self.record['own_services_closed']=not self.record['listeners_after_close'] and (self.service is None or self.service.poll() is not None)
  finally:
   if self.log:self.log.close()
   self.record['ended_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();self.save()

def run():
 checks=json.loads((HERE/'MONITOR_PREFLIGHT.json').read_text(encoding='utf-8'))
 if checks['result']!='PC_PREFLIGHT_PASS_NO_HARDWARE' or checks['input_hashes']!=e.inputs():raise RuntimeError('Preflight/input mismatch')
 for n,sha in checks['source_hashes'].items():
  if hashlib.sha256((HERE/n).read_bytes()).hexdigest()!=sha:raise RuntimeError('Source hash mismatch: '+n)
 for n in ('SERVICE_RUN_STARTED.txt','HARDWARE_RUN_STARTED.txt','jtag_actual.log','HARDWARE_RUN_BLOCKED.json'):
  if (HERE/n).exists():raise RuntimeError('Used/blocked session; launch again using the top-level launcher')
 (HERE/'SERVICE_RUN_STARTED.txt').write_text('Operator-started LED-only continuous session; no retry\n',encoding='utf-8')
 stop=threading.Event()
 def request_stop(signum,frame):
  stop.set();print('\nSTOP_REQUESTED: wait for sensor/PS/CPU restoration and SERVICES_CLOSED',flush=True)
 previous=signal.signal(signal.SIGINT,request_stop)
 r=dict(version='0.4.0',hardware_version='0.4.0',result='STARTING',model_id='022267A9',options=dict(OPTIONS),arm_disconnected_required=True,d5_low_required=True,snapshots=OPTIONS['images'],source_age_limit_ms=250,format_counter_reset=False,physical_arm_loop='NOT_RUN',input_hashes=e.inputs(),started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
 service=OwnedServer();code=2
 print('SESSION_DIRECTORY '+str(HERE),flush=True)
 try:
  service.start()
  with (HERE/'telemetry.jsonl').open('x',encoding='utf-8') as stream:code=run_session(r,stop,stream)
 except Exception as exc:r.update(result='STOPPED_ERROR',error=repr(exc))
 finally:
  try:
   service.close();r['own_services_closed']=service.record.get('own_services_closed',False)
  except Exception as exc:r.update(service_close_error=repr(exc),own_services_closed=False)
  r['ended_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();e.save('SESSION_RESULT.json',r)
  signal.signal(signal.SIGINT,previous)
 if not r.get('own_services_closed'):code=2
 print(json.dumps({k:r.get(k) for k in ('result','shutdown','sensor_restore','own_services_closed','requires_user_power_cycle','error')}),flush=True)
 if r.get('requires_user_power_cycle'):print('STOPPED: keep arm disconnected and D5 low; fully power off the board before another attempt.',flush=True)
 if r.get('own_services_closed'):print('SERVICES_CLOSED',flush=True)
 if 'statistics' in r:print('SAMPLED_RESULTS '+json.dumps(r['statistics']),flush=True)
 return code

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',action='store_true');args=ap.parse_args()
 raise SystemExit(run() if args.run else 0)
