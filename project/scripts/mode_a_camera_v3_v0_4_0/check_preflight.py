"""Inherited fault injection plus continuous-loop/stop/cleanup tests; no hardware."""
from pathlib import Path
import ast,contextlib,hashlib,io,json,threading,signal,tempfile
from unittest.mock import patch
import pc_cases as inherited
import verify_exposure as e
import monitor
H=Path(__file__).resolve().parent

def v2_tests():
 rows=[]
 def result(model=5,task=4,qualified=True,valid=True,fid=1,stamp=100):
  return dict(result_frame_id=fid,acquisition_ms=stamp,model_id=0x022267a9,vision_status=int(valid),
   model_class=model,task_class=task,qualified=qualified,source_age_ms=100,format_errors=0)
 for label,model,task in (('one',1,1),('two',2,2),('three',3,3),('fist',4,5),('palm',5,4)):
  counts=monitor.SampleCounts(label);s=result(model,task)
  assert counts.add(s,0) and not counts.add(s,1)
  bad=result((model+1)%6,task,fid=2,stamp=200);counts.add(bad,12)
  report=counts.report()
  assert report['sampled_distinct_results']==2 and report['model_accuracy_percent']==50
  assert report['confirmed_percent']==50 and report['ten_second_windows'][1]['model_correct']==0
  rows.append(dict(case='label_'+label+'_model_task_mapping_dedup_and_windows',result='PASS_PC_V2'))
 counts=monitor.SampleCounts('palm')
 for i,(qualified,valid) in enumerate(((False,True),(True,False),(True,True))):
  counts.add(result(qualified=qualified,valid=valid,fid=i),i)
 assert counts.correct==3 and counts.confirmed==1
 rows.append(dict(case='qualification_and_fresh_valid_both_required',result='PASS_PC_V2'))
 counts=monitor.SampleCounts('empty')
 for i,s in enumerate((result(0,0),result(7,7,False),result(3,3))):
  s['result_frame_id']=i;counts.add(s,i)
 assert counts.correct==counts.confirmed==2
 rows.append(dict(case='empty_background_nondetection_and_false_gesture',result='PASS_PC_V2'))
 counts=monitor.SampleCounts(None);counts.add(result(),0)
 assert 'model_accuracy_percent' not in counts.report() and counts.report()['accuracy'].startswith('NOT_COMPUTED')
 rows.append(dict(case='unlabelled_never_reports_accuracy',result='PASS_PC_V2'))
 counts=monitor.SampleCounts('palm')
 for fid,stamp in ((0xffffffff,0xfffffff0),(0,10),(1,100)):
  counts.add(result(fid=fid,stamp=stamp),0)
 assert counts.n==3
 rows.append(dict(case='frame_and_acquisition_wrap_kept_as_new_results',result='PASS_PC_V2'))
 # Exercise the real observer including duration, snapshots, wrong model and a stalled result.
 for kind in ('duration','images_before_counts','wrong_model','stalled'):
  tick=[0.0];seen=[];r={'options':dict(seconds=1 if kind!='stalled' else 5,label='palm',images=2 if kind=='images_before_counts' else 0)}
  stop=threading.Event()
  class Fake:
   def read(self,a):return [0x45585031]
  cfg={0x300a:0x56,0x300b:0x40,0x3808:2,0x3809:128,0x380a:1,0x380b:224,0x380e:4,0x380f:0,0x4300:0x30,0x501f:0}
  def state(*args):
   s=result(fid=0 if kind=='stalled' else int(tick[0]*10),stamp=0 if kind=='stalled' else int(tick[0]*1000))
   if kind=='wrong_model':s['model_id']=0x0f350087
   seen.append('state');return s
  def image(b,r,baseline,i,*args):
   r.setdefault('images',[]).append({'index':i});seen.append('image')
  def pause(n):tick[0]+=n
  with contextlib.ExitStack() as ctx:
   for obj,name,replacement in ((e.c,'startup',lambda *a:0),(e,'initial_result',lambda *a:{}),
    (e,'command',lambda b,r,reg:cfg[reg]),(e,'freeze',lambda *a:{'3503':3}),
    (e,'apply',lambda *a:{}),(e,'checked',state),(monitor,'inert',lambda *a:{}),
    (e.c,'image',image),(e.c,'fresh_after_snapshot',lambda *a:seen.append('fresh')),(e,'save',lambda *a:None)):
    ctx.enter_context(patch.object(obj,name,replacement))
   try:
    with contextlib.redirect_stdout(io.StringIO()):monitor.observe(Fake(),r,stop,io.StringIO(),clock=lambda:tick[0],pause=pause)
   except RuntimeError as exc:
    assert (kind=='wrong_model' and 'ID mismatch' in str(exc)) or (kind=='stalled' and 'two seconds' in str(exc))
   else:
    assert kind in ('duration','images_before_counts') and r['observation_ended_by']=='DURATION'
    assert r['statistics']['model_accuracy_percent']==100
    if kind=='images_before_counts':assert seen[:4]==['image','fresh','image','fresh'] and len(r['images'])==2
  rows.append(dict(case='real_observer_'+kind,result='PASS_PC_V2'))
 # Package identity is rejected before relying on its self-declared artifact hashes.
 import verify_camera as c
 with tempfile.TemporaryDirectory(prefix='gesture_v2_wrong_package_') as temp:
  p=Path(temp);(p/'MANIFEST.json').write_text(json.dumps(dict(version='0.4.0',model_id='0F350087')),encoding='utf-8')
  with patch.object(c,'PACKAGE',p):
   try:c.inputs()
   except AssertionError:pass
   else:raise AssertionError('Legacy package accepted')
 rows.append(dict(case='legacy_package_rejected_before_hardware',result='PASS_PC_V2'))
 return rows

def monitor_tests():
 rows=[]
 assert [monitor.led_code(i,True) for i in range(8)]==[8,9,10,11,12,13,14,0]
 assert all(monitor.led_code(i,False)==0 for i in range(8)) and monitor.led_code(7,False,True)==15
 rows.append(dict(case='all_stable_task_LED_codes_invalid_and_fatal',result='PASS_PC_MONITOR'))
 class Fake:
  def __init__(self):self.failed=False;self.closed=False;self.events=[]
  def wait_ready(self):self.events.append('ready')
  def read(self,a):assert a==monitor.BASE+0x94;return [0x45585031]
  def close(self):
   self.events.append('close');self.closed=True
   if self.failed:raise RuntimeError('mock AXI fault restore unconfirmed')
 cfg={0x300a:0x56,0x300b:0x40,0x3808:2,0x3809:128,0x380a:1,0x380b:224,0x380e:4,0x380f:0,0x4300:0x30,0x501f:0}
 # Real loop exits on operator stop and streams samples without acquiring snapshots.
 stop=threading.Event();b=Fake();result={};stream=io.StringIO();count=[0]
 def state(_b,_baseline):
  count[0]+=1
  if count[0]==3:stop.set()
  return dict(result_frame_id=count[0],acquisition_ms=count[0]*100,model_id=0x022267a9,vision_status=1,task_class=3,model_class=3,qualified=True,source_age_ms=150,format_errors=0)
 with contextlib.ExitStack() as ctx:
  ctx.enter_context(patch.object(e.c,'startup',lambda *a:0));ctx.enter_context(patch.object(e,'initial_result',lambda *a:{}))
  ctx.enter_context(patch.object(e,'command',lambda b,r,reg:cfg[reg]));ctx.enter_context(patch.object(e,'freeze',lambda *a:{'3503':3}))
  ctx.enter_context(patch.object(e,'apply',lambda *a:dict(exposure_lines=984,gain_code=80)));ctx.enter_context(patch.object(e,'checked',state))
  ctx.enter_context(patch.object(e,'save',lambda *a:None))
  ctx.enter_context(patch.object(monitor,'inert',lambda b:{'off':True}))
  with contextlib.redirect_stdout(io.StringIO()):monitor.observe(b,result,stop,stream,clock=lambda:count[0],pause=lambda t:None)
 assert result['result']=='LED_MONITOR_STOPPED_BY_OPERATOR' and result['health_samples']==3
 samples=[json.loads(s) for s in stream.getvalue().splitlines()];assert len(samples)==3 and all(s['expected_led_bits']=='1011' for s in samples)
 rows.append(dict(case='real_loop_operator_stop_three_streamed_samples_no_snapshot',result='PASS_PC_MONITOR'))
 # Stop during readiness must restore through the same finally path.
 for kind in ('operator_stop','startup_error','sensor_command_error','sensor_restore_error','AXI_error'):
  b=Fake();r={};events=[]
  def restore(_b,_r):
   assert not _b.failed and not _r.get('sensor_command_fault');events.append('sensor_restore')
   if kind=='sensor_restore_error':raise RuntimeError('mock restore error')
   _r['sensor_restore']='ORIGINAL_VALUES_AND_MODE_VERIFIED'
  def observer(_b,_r,*args):
   if kind in ('operator_stop','sensor_restore_error'):_r['result']='LED_MONITOR_STOPPED_BY_OPERATOR';return
   if kind=='AXI_error':_b.failed=True
   if kind=='sensor_command_error':_r['sensor_command_fault']=True
   raise RuntimeError('mock '+kind)
  with patch.object(e,'restore_sensor',restore):code=monitor.run_session(r,threading.Event(),io.StringIO(),factory=lambda:b,observer=observer)
  assert b.closed and b.events==['ready','close']
  if kind=='operator_stop':assert code==0 and events==['sensor_restore'] and r['shutdown']=='PASS_REVISED_ISOLATED_SHUTDOWN'
  elif kind=='AXI_error':assert code==2 and not events and r['requires_user_power_cycle'] and r['result']=='RESTORE_INCOMPLETE'
  elif kind=='sensor_command_error':assert code==2 and not events and r['requires_user_power_cycle']
  elif kind=='sensor_restore_error':assert code==2 and events==['sensor_restore'] and r['requires_user_power_cycle']
  else:assert code==2 and events==['sensor_restore']
  rows.append(dict(case='cleanup_'+kind,result='PASS_PC_MONITOR'))
 # Exercise the actual installed SIGINT handler without starting subprocesses.
 class Service:
  def __init__(self):self.record={}
  def start(self):pass
  def close(self):self.record['own_services_closed']=True
 saved_handler=signal.getsignal(signal.SIGINT)
 def stopped_session(r,stop,stream):
  signal.raise_signal(signal.SIGINT);assert stop.is_set()
  r.update(result='LED_MONITOR_STOPPED_BY_OPERATOR',shutdown='PASS_REVISED_ISOLATED_SHUTDOWN',sensor_restore='ORIGINAL_VALUES_AND_MODE_VERIFIED')
  return 0
 with tempfile.TemporaryDirectory(prefix='gesture_led_stop_pc_') as temp:
  folder=Path(temp);(folder/'MONITOR_PREFLIGHT.json').write_text(json.dumps(dict(result='PC_PREFLIGHT_PASS_NO_HARDWARE',input_hashes={},source_hashes={})),encoding='utf-8')
  with patch.object(monitor,'HERE',folder),patch.object(e,'inputs',lambda:{}),patch.object(e,'save',lambda *a:None),patch.object(monitor,'OwnedServer',Service),patch.object(monitor,'run_session',stopped_session),contextlib.redirect_stdout(io.StringIO()):
   assert monitor.run()==0
 assert signal.getsignal(signal.SIGINT)==saved_handler
 rows.append(dict(case='actual_SIGINT_handler_requests_stop_cleanup_and_restores_handler',result='PASS_PC_MONITOR'))
 return rows

def main():
 for n in ('HARDWARE_RUN_STARTED.txt','SERVICE_RUN_STARTED.txt','HARDWARE_RUN_BLOCKED.json','jtag_actual.log'):assert not (H/n).exists()
 inputs=e.inputs()
 with contextlib.redirect_stdout(io.StringIO()):
  tc=[inherited.tcl_case(n) for n in ('check_only','pass','legacy_model_id','first_id_timeout','snapshot_read_fault','malformed_word','reset_readback_fault','cpu_read_fault','id_mismatch','configuration_status_error','startup_incomplete','motion_write_denied','diagnostic_write_denied','diagnostic_read_denied','stream_without_owner','stream_overrun')]
  hc=[inherited.host_case(n) for n in ('pass','bad_abi','legacy_model_id','snapshot_timeout','snapshot_dimensions','snapshot_identity','snapshot_axi_timeout','format_image','format_live','age251','no_fresh_frame','init_error','clock_lost','fatal','incoherent','padding_corrupt','D5_high')]
  ec=e.offline_tests();mc=monitor_tests();vc=v2_tests()
 current=(H/'jtag_bridge.tcl').read_text(encoding='utf-8');prev=(H/'PS_STARTUP_BASELINE.tcl').read_text(encoding='utf-8')
 start='    connect -url tcp:127.0.0.1:3121';end='    say "ALL_FOUR_ABIS_AND_MODEL_ID_PASS"'
 assert current.split(start,1)[1].split(end,1)[0]==prev.split(start,1)[1].split(end,1)[0]
 assert current.split('proc restore {} {',1)[1].split('proc host_read_guard',1)[0]==prev.split('proc restore {} {',1)[1].split('proc host_read_guard',1)[0]
 assert current[current.index('if {$bus_fault} {'):]==prev[prev.index('if {$bus_fault} {'):]
 names=('monitor.py','check_preflight.py','pc_cases.py','service_owner.py','transport_reused.py','verify_camera.py','verify_exposure.py','png_helper.py','mock_xsdb.tcl','jtag_bridge.tcl','SOURCE_CHECKPOINT.json','SELECTED_PROFILE.json','AUTHORIZATION.json','PS_STARTUP_BASELINE.tcl')
 launcher=H.parents[1]/'scripts/run_mode_a_camera_v3.py'
 tree=ast.parse(launcher.read_text(encoding='utf-8'))
 values=[ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FILES' for t in n.targets)]
 assert len(values)==1 and set(values[0])==set(names)
 for n in names:
  if n.endswith('.py'):ast.parse((H/n).read_text(encoding='utf-8'))
 report=dict(result='PC_PREFLIGHT_PASS_NO_HARDWARE',input_hashes=inputs,logic=dict(tcl_cases=tc,camera_host_cases=hc,exposure_cases=ec,monitor_cases=mc,v2_cases=vc),source_hashes={n:hashlib.sha256((H/n).read_bytes()).hexdigest() for n in names},proven_PS_startup_restore_fault_dispatcher_identical_except_expected_model_ID=True,hardware_access=False,new_launcher_hardware_test='NOT_RUN')
 (H/'MONITOR_PREFLIGHT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps(dict(result=report['result'],tcl_cases=len(tc),camera_host_cases=len(hc),exposure_cases=len(ec),monitor_cases=len(mc),v2_cases=len(vc))))
if __name__=='__main__':main()
