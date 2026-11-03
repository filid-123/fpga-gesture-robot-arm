"""Offline Tcl/host error injection; no connection, driver or hardware import."""
from pathlib import Path
import ast,contextlib,hashlib,io,json,struct,tempfile,tkinter
import verify_camera as host
import verify_exposure
H=Path(__file__).resolve().parent
def tcl_case(case):
 t=tkinter.Tcl();t.call('source',str(H/'mock_xsdb.tcl'));t.setvar('sim_case',case)
 if case=='check_only':
  t.eval('rename exit record_exit;proc exit {n} {record_exit $n;error EXPECTED_PC_EXIT}')
  t.setvar('argv',t.call('list','--check-only'))
  try:t.call('source',str(H/'jtag_bridge.tcl'))
  except tkinter.TclError as e:assert str(e)=='EXPECTED_PC_EXIT'
  assert int(t.getvar('sim_exit'))==0 and not t.splitlist(t.getvar('sim_events'))
  return dict(case=case,result='PASS_PC_TCL_NO_HARDWARE')
 t.eval('''
  dict set sim_registers 0x43C60040 0;dict set sim_registers 0x43C60044 3;dict set sim_registers 0x43C6004C 0
  set mock_requests [list "1 W 0x43c60040 1" "2 W 0x43c6004c 0" "3 S 0x43c60050 256" "4 W 0x43c60040 0" "5 CLOSE"]
  if {$sim_case eq "motion_write_denied"} {set mock_requests [list "1 W 0x43C30004 1"]}
  if {$sim_case eq "diagnostic_write_denied"} {set mock_requests [list "1 W 0x43C6008C 1"]}
  if {$sim_case eq "diagnostic_read_denied"} {set mock_requests [list "1 R 0x43C60098 1"]}
  if {$sim_case eq "stream_without_owner"} {set mock_requests [list "1 S 0x43C60050 8"]}
  if {$sim_case eq "stream_overrun"} {dict set sim_registers 0x43C6004C 4095;set mock_requests [list "1 W 0x43C60040 1" "2 S 0x43C60050 2"]}
  rename gets old_gets
  proc gets {channel name} {
   if {![llength $::mock_requests]} {return -1}
   upvar 1 $name line;set line [lindex $::mock_requests 0];set ::mock_requests [lrange $::mock_requests 1 end]
   if {[lindex $line 1] eq "CLOSE"} {set ::sim_close_seen 1;lappend ::sim_events HOST_CLOSE}
   return [string length $line]
  }
  rename mrd original_mrd
  proc mrd {args} {
   set a [format 0x%08X [expr {[lindex $args end-1]}]]
   if {$::sim_faulted} {incr ::sim_after_fault_accesses;error "Access after fault"}
   if {$::sim_case eq "malformed_word" && $a eq "0x43C30010"} {return INVALID_WORD}
   if {$a eq "0x43C60050"} {
    if {$::sim_case eq "snapshot_read_fault"} {sim_fail SNAPSHOT_READ}
    set v [dict get $::sim_registers 0x43C6004C];dict incr ::sim_registers 0x43C6004C
    lappend ::sim_events [list READ $a];return $v
   }
   return [original_mrd {*}$args]
  }
  rename mwr original_mwr
  proc mwr {args} {
   set a [format 0x%08X [expr {[lindex $args end-1]}]];set v [expr {[lindex $args end]}]
   if {$a in {0x43C60040 0x43C6004C}} {
    if {$::sim_faulted} {incr ::sim_after_fault_accesses;error "Write after fault"}
    dict set ::sim_registers $a $v;lappend ::sim_events [list WRITE $a $v];return
   }
   original_mwr {*}$args
  }
 ''')
 with tempfile.TemporaryDirectory(prefix='gesture_phase2_tcl_pc_') as out:
  t.setvar('argv',t.call('list','--run',str(host.PACKAGE/'hardware/roarm_closed_loop.bit'),str(host.XSA),out));t.call('source',str(H/'jtag_bridge.tcl'))
 code=int(t.getvar('sim_exit'));lines=list(t.splitlist(t.getvar('sim_lines')))
 assert int(t.getvar('sim_after_fault_accesses'))==int(t.getvar('sim_target_queries_after_fault'))==0
 if case=='pass':assert code==0 and 'RESTORE_COMPLETE' in lines
 elif case in ('first_id_timeout','snapshot_read_fault','malformed_word'):assert code==2 and 'RESTORE_COMPLETE' not in lines
 elif case in ('reset_readback_fault','cpu_read_fault'):assert code==3 and 'RESTORE_COMPLETE' not in lines
 else:assert code==2 and 'RESTORE_COMPLETE' in lines
 return dict(case=case,result='PASS_PC_TCL_SIMULATION',exit=code,no_queries_after_fault=True)
def host_case(case):
 class Clock:
  t=0
  def now(self):return self.t
  def pause(self,n):self.t+=n
 c=Clock()
 class Fake:
  def __init__(self):self.failed=False;self.owned=False;self.released=False;self.pointer=0;self.captures=0;self.events=[]
  def write(self,a,v):
   assert not self.failed;self.events.append(('W',a,v))
   if a==host.BASE+0x40:
    self.owned=bool(v)
    if v:self.captures+=1;self.released=False
    else:self.released=True
   elif a==host.BASE+0x4c:self.pointer=v
   else:raise AssertionError((a,v))
  def stream(self,n):
   assert not self.failed;self.events.append(('S',n))
   if case=='snapshot_axi_timeout':self.failed=True;raise RuntimeError('Simulated MMIO error')
   data=bytes((i+self.captures)&255 for i in range(96*128));data=b'\0'*2048+data+b'\0'*2048
   if case=='padding_corrupt':data=b'\x01'+data[1:]
   ans=list(struct.unpack('<'+str(n)+'I',data[self.pointer*4:(self.pointer+n)*4]));self.pointer+=n;return ans
  def read(self,a,n=1):
   assert not self.failed;self.events.append(('R',a,n));off=a-host.BASE
   if off==8:return [0 if case=='bad_abi' else 0x3505]
   if off==0x70:return [0x0f350087 if case=='legacy_model_id' else 0x022267a9]
   if off==0x74:return [0x43414d31]
   if off==0x40:return [int(self.owned)]
   if off==0x44:return [0 if case=='snapshot_timeout' else 3]
   if off==0x48:return [self.captures-1+(1 if case=='snapshot_identity' and self.pointer==4096 else 0)]
   if off==0x58:return [self.captures*100]
   if off==0x54:return [0 if case=='snapshot_dimensions' else 0x00800080]
   if off==0x4c:return [self.pointer]
   if off==0x78 and n==4:return [0x20000b,0,2 if case=='format_image' else 1,1000+int(c.t*1000)]
   if off==0x84:return [1000+int(c.t*1000)]
   raise AssertionError((hex(a),n))
 b=Fake();r={};saved=(host.HERE,host.read_state,host.inert)
 def state(_):
  now=1000+int(c.t*1000);acq=now-(251 if case=='age251' else 100)
  return dict(coherent=case!='incoherent',camera_status=0x20000b if case!='clock_lost' else 0x20000a,init_done=True,init_error=case=='init_error',fifo_overflow=False,xclk_locked=True,capture_enabled=True,
   vision_status=4 if case=='fatal' else 0,format_errors=2 if case=='format_live' and b.released else 1,acquisition_ms=0 if case=='no_fresh_frame' else acq,now_ms=now,
   source_age_ms=(now-acq)&0xffffffff,result_frame_id=int(c.t*10),result_events=int(c.t*10))
 host.read_state=state
 def no_motion(_):
  if case=='D5_high':raise RuntimeError('D5 is high')
  return dict(arm_status=32,arm_error=0,planner_error=0,task_status=4096,task_fault=0)
 host.inert=no_motion
 expected={'bad_abi','legacy_model_id','snapshot_timeout','snapshot_dimensions','snapshot_identity','snapshot_axi_timeout','format_image','format_live','age251','no_fresh_frame','init_error','clock_lost','fatal','incoherent','padding_corrupt','D5_high'}
 try:
  with tempfile.TemporaryDirectory(prefix='gesture_phase2_host_pc_') as out:
   host.HERE=Path(out)
   try:host.observe(b,r,clock=c.now,pause=c.pause,segment_seconds=.25)
   except (RuntimeError,TimeoutError):assert case in expected,case
   else:
    assert case=='pass' and len(r['images'])==3 and r['images'][0]['frame_id']==0
    assert r['result']=='CAMERA_THREE_IMAGES_AND_60S_LIVE_PASS_PENDING_VISUAL_REVIEW'
    for i in range(3):assert (Path(out)/f'camera_{i:02d}_128x128.raw').stat().st_size==16384
   if case in ('init_error','fatal','bad_abi','legacy_model_id','D5_high','incoherent','clock_lost'):assert not any(v[0]=='W' for v in b.events)
   if case=='snapshot_axi_timeout':assert b.events[-1]==('S',256) and not r.get('snapshot_released')
   if case=='format_image':assert sum(v[0]=='S' for v in b.events)==1 and b.events[-1]==('W',host.BASE+0x40,0)
   if case=='snapshot_timeout':assert c.t<=10.1 and not any(v[0]=='S' for v in b.events)
 finally:host.HERE,host.read_state,host.inert=saved
 return dict(case=case,result='PASS_PC_HOST_SIMULATION',requests=len(b.events),clock_s=c.t)
