"""Bounded shared-SCCB camera calibration; no hardware on import."""
from pathlib import Path
import argparse,datetime,hashlib,json,time,collections
import verify_camera as c
from transport_reused import Bridge,BASE,HERE,inert,exposure_command
inputs=c.inputs
EXPOSURE_REGS=(0x3500,0x3501,0x3502,0x350a,0x350b)
READ_REGS=(0x300a,0x300b,0x3034,0x3035,0x3036,0x3037,0x3108,0x3503,*EXPOSURE_REGS,
 *range(0x3800,0x3816),0x4300,0x4302,0x4303,0x4304,0x4305,0x4740,0x501f,
 0x5000,0x5001,0x4000,0x4001,0x4004,0x4005,0x5580,0x5583,0x5584,0x5586,*range(0x5480,0x5491))
def save(n,v):c.save(n,v)
def command(b,r,reg,value=None):
 if type(reg)!=int or not 0<=reg<=65535:raise ValueError('Sensor address')
 v=(0x80000000 if value is None else 0)|(reg<<8)|(0 if value is None else value)
 if value is not None and (type(value)!=int or not 0<=value<=255):raise ValueError('Sensor byte')
 if not exposure_command(v):raise ValueError('Sensor command whitelist')
 s=b.read(BASE+0x8c)[0]
 if s&1 or not s&8:raise RuntimeError('SCCB not ready/pending')
 seq=((s>>16)+1)&65535
 b.write(BASE+0x88,v);deadline=time.monotonic()+2
 while True:
  s=b.read(BASE+0x8c)[0]
  if (s>>16)==seq and not s&1 and s&2:break
  if time.monotonic()>deadline:r['sensor_command_fault']=True;raise TimeoutError('Sensor completion timeout; no retry')
  time.sleep(.005)
 if s&4:r['sensor_command_fault']=True;raise RuntimeError('Sensor ACK failure; no retry')
 if b.read(BASE+0x88)[0]!=v:r['sensor_command_fault']=True;raise RuntimeError('Sensor command echo mismatch')
 out=b.read(BASE+0x90)[0]
 r.setdefault('sensor_transactions',[]).append(dict(register=f'{reg:04X}',write=value,read=out,sequence=seq))
 return out
def write_checked(b,r,reg,value):
 command(b,r,reg,value)
 if command(b,r,reg)!=value:r['sensor_command_fault']=True;raise RuntimeError('Sensor readback mismatch '+hex(reg))
def read_parameters(b,r):
 d={f'{a:04X}':command(b,r,a) for a in (0x3503,*EXPOSURE_REGS)}
 d.update(exposure_units=((d['3500']&15)<<16)|(d['3501']<<8)|d['3502'],gain_code=((d['350A']&3)<<8)|d['350B'])
 d['exposure_lines']=d['exposure_units']/16;d['gain_nominal_x']=d['gain_code']/16
 return d
def freeze(b,r):
 original_mode=command(b,r,0x3503);write_checked(b,r,0x3503,original_mode|3)
 d=read_parameters(b,r);d['original_mode']=original_mode
 if d['exposure_units']<16 or d['gain_code']<16:raise RuntimeError('Unexpected sensor exposure/gain baseline')
 return d
def apply(b,r,base,lines,gain):
 if type(lines)!=int or not 1<=lines<=r['vts']-8 or type(gain)!=int or not 16<=gain<=1023:raise ValueError('Exposure/gain bounds')
 exp=lines*16
 write_checked(b,r,0x3503,base['3503']|3)
 values={0x3500:(base['3500']&240)|((exp>>16)&15),0x3501:(exp>>8)&255,0x3502:exp&255,
 0x350a:(base['350A']&252)|((gain>>8)&3),0x350b:gain&255}
 for a,v in values.items():write_checked(b,r,a,v)
 result=read_parameters(b,r)
 if result['exposure_units']!=exp or result['gain_code']!=gain:raise RuntimeError('Applied profile readback mismatch')
 return result
def checked(b,baseline):
 s=c.read_state(b);c.guard(s,baseline)
 if s['source_age_ms']>250:raise c.AgeFault('Live source age exceeds250ms')
 return s
def initial_result(b,baseline,clock=time.monotonic,pause=time.sleep):
 deadline=clock()+5
 while True:
  s=c.read_state(b);c.guard(s,baseline)
  if s['result_events']>0:
   if s['source_age_ms']>250:raise c.AgeFault('Initial completed source age exceeds250ms')
   return s
  if clock()>deadline:raise TimeoutError('No initial completed camera result')
  pause(.05)
def settle(b,r,baseline,seconds=1):
 deadline=time.monotonic()+seconds;rows=[]
 while True:
  rows.append(checked(b,baseline))
  if time.monotonic()>=deadline:break
  time.sleep(.1)
 r.setdefault('live_telemetry',[]).extend(rows)
 return rows
def snapshot(b,r,baseline,label,params):
 settle(b,r,baseline,1)
 index=len(r.get('images',[]))+1;c.image(b,r,baseline,index,time.monotonic,time.sleep)
 c.fresh_after_snapshot(b,r,baseline,time.monotonic,time.sleep)
 im=r['images'][-1];im.update(label=label,sensor_parameters=params)
 raw=(HERE/im['image_name']).with_suffix('.raw').read_bytes();content=raw[16*128:112*128]
 vals=sorted(content);n=len(vals)
 im['content_metrics']=dict(mean=sum(content)/n,p01=vals[int(n*.01)],p10=vals[int(n*.1)],p50=vals[int(n*.5)],p90=vals[int(n*.9)],p95=vals[int(n*.95)],p99=vals[int(n*.99)],fraction_ge235=sum(v>=235 for v in content)/n,fraction_ge250=sum(v>=250 for v in content)/n,fraction_le24=sum(v<=24 for v in content)/n)
 save(im['image_name'].replace('.png','.json'),im);save('SESSION_RESULT.json',r)
def profiles(b,r,baseline,label):
 base=freeze(b,r);r.setdefault('frozen_baselines',{})[label]=base
 # Keep gain constant for the first controlled comparison, avoiding two simultaneous variables.
 lines=max(1,min(r['vts']-8,int(base['exposure_lines'])))
 gain=base['gain_code']
 for div in (1,2,4):
  p=apply(b,r,base,max(1,lines//div),gain)
  snapshot(b,r,baseline,f'{label}_EXPOSURE_1_{div}',p)
 r['active_base']=base
 return base
def restore_sensor(b,r):
 d=r.get('original_sensor')
 if not d:return
 write_checked(b,r,0x3503,d['3503']|3)
 for a in EXPOSURE_REGS:write_checked(b,r,a,d[f'{a:04X}'])
 write_checked(b,r,0x3503,d['original_mode'])
 r['sensor_restore']='ORIGINAL_VALUES_AND_MODE_VERIFIED'
def action(d):
 if not isinstance(d,dict) or set(d)-{'op','lines','gain','label'}:raise ValueError('Calibration command fields')
 if d.get('op') not in ('PALM','PROFILE','FINISH','STOP'):raise ValueError('Calibration operation')
 if d['op']=='PROFILE':
  if type(d.get('lines'))!=int or type(d.get('gain'))!=int or not isinstance(d.get('label'),str) or not d['label'].isascii() or not d['label'].replace('_','').isalnum():raise ValueError('Profile command')
 return d
def observe(b,r):
 baseline=c.startup(b,r,time.monotonic,time.sleep)
 if b.read(BASE+0x94)[0]!=0x45585031:raise RuntimeError('EXP1 magic mismatch')
 r['initial_completed_result']=initial_result(b,baseline)
 settle(b,r,baseline,3)
 config={f'{a:04X}':command(b,r,a) for a in READ_REGS};r['initial_sensor_registers']=config
 if config['300A']!=0x56 or config['300B']!=0x40:raise RuntimeError('Sensor chip ID mismatch')
 if (config['3808']<<8|config['3809'],config['380A']<<8|config['380B'])!=(640,480) or config['4300']!=0x30 or config['501F']!=0:raise RuntimeError('Sensor geometry/YUV configuration mismatch')
 r['vts']=config['380E']<<8|config['380F']
 r['original_sensor']=freeze(b,r);save('SESSION_RESULT.json',r)
 profiles(b,r,baseline,'EMPTY')
 restore_sensor(b,r);settle(b,r,baseline,3)
 r['state']='WAIT_PALM';save('SESSION_RESULT.json',r);print('EMPTY_PROFILES_COMPLETE_WAIT_PALM',flush=True)
 count=0;end=time.monotonic()+750;did_palm=False
 while time.monotonic()<end:
  n=HERE/f'COMMAND_{count+1:03d}.json'
  if not n.exists():settle(b,r,baseline,.5);continue
  d=action(json.loads(n.read_text(encoding='utf-8')));count+=1
  r.setdefault('commands',[]).append(d)
  if d['op'] in ('FINISH','STOP'):
   r['result']='EXPOSURE_COMPARISON_COMPLETED' if d['op']=='FINISH' and did_palm else 'EMPTY_ONLY_OR_USER_STOP'
   break
  if d['op']=='PALM':
   if did_palm:raise RuntimeError('Palm baseline already sampled')
   settle(b,r,baseline,3);profiles(b,r,baseline,'PALM');did_palm=True
   r['state']='WAIT_REVIEW';print('PALM_PROFILES_COMPLETE_WAIT_REVIEW',flush=True)
  else:
   if not did_palm or len(r.get('images',[]))>=12:raise RuntimeError('Profile limit or no hand baseline')
   p=apply(b,r,r['active_base'],d['lines'],d['gain']);snapshot(b,r,baseline,d['label'],p)
   r['state']='WAIT_REVIEW';print('EXTRA_PROFILE_COMPLETE_WAIT_REVIEW',flush=True)
  save('SESSION_RESULT.json',r)
 else:raise TimeoutError('Calibration operator window expired')
 r['final_motion_state']=inert(b)
def offline_tests():
 # Fake SCCB/AXI only. No Bridge is constructed.
 from transport_reused import exposure_command,readable
 for v in (0x80350300,0x00350303,0x00350b10):assert exposure_command(v)
 for v in (0x00380001,0x80350301,0x01350303,-1,0x100000000):assert not exposure_command(v)
 assert readable(BASE+0x94) and not readable(BASE+0x98)
 class Fake:
  def __init__(self,case='pass'):self.seq=0;self.status=8;self.echo=0;self.data=0;self.case=case;self.reg={0x3503:0,0x3500:0,0x3501:0x20,0x3502:0,0x350a:0,0x350b:32}
  def read(self,a):return [{BASE+0x8c:self.status,BASE+0x88:self.echo^(1 if self.case=='echo_mismatch' else 0),BASE+0x90:self.data}[a]]
  def write(self,a,v):
   assert a==BASE+0x88 and exposure_command(v);self.echo=v;reg=(v>>8)&65535
   if v>>31:self.data=self.reg.get(reg,0)^(1 if self.case=='readback_mismatch' else 0)
   else:self.reg[reg]=v&255
   self.seq=(self.seq+1)&65535;self.status=((self.seq-1)&65535)<<16|1 if self.case=='timeout' else (self.seq<<16)|10|(4 if self.case=='nack' else 0)
 cases=[]
 for name in ('pass','nack','notready','restore','bounds','actions','seq_wrap','timeout','echo_mismatch','readback_mismatch'):
  b=Fake(name);r={'vts':1080}
  if name=='notready':
   b.status=1
   try:command(b,r,0x3503)
   except RuntimeError:pass
   else:raise AssertionError(name)
  elif name in ('nack','timeout','echo_mismatch','readback_mismatch'):
   try:
    if name=='readback_mismatch':write_checked(b,r,0x3503,3)
    else:command(b,r,0x3503)
   except RuntimeError:pass
   except TimeoutError:pass
   else:raise AssertionError(name)
   assert r['sensor_command_fault']
  elif name=='bounds':
   base=freeze(b,r)
   for lines,gain in ((0,16),(1073,16),(100,15),(100,1024)):
    try:apply(b,r,base,lines,gain)
    except ValueError:pass
    else:raise AssertionError(name)
  elif name=='actions':
   for d in ({'op':'MOTION'},{'op':'PROFILE','lines':1.2,'gain':16,'label':'X'},{'op':'FINISH','address':1}):
    try:action(d)
    except ValueError:pass
    else:raise AssertionError(name)
  elif name=='seq_wrap':b.seq=65535;b.status=(65535<<16)|8;assert command(b,r,0x3503)==0
  else:
   original=dict(b.reg);r['original_sensor']=freeze(b,r);p=apply(b,r,r['original_sensor'],256,16)
   assert p['exposure_units']==4096 and p['gain_code']==16
   restore_sensor(b,r);assert b.reg==original
  cases.append(dict(case=name,result='PASS_PC_EXPOSURE_NO_HARDWARE'))
 old_state,old_guard=c.read_state,c.guard
 try:
  for name in ('initial_result_wait','initial_result_timeout','initial_result_stale'):
   tick=[0.0]
   def now():return tick[0]
   def pause(n):tick[0]+=n
   c.read_state=lambda b:dict(result_events=int(tick[0]>.1 and name!='initial_result_timeout'),source_age_ms=251 if name=='initial_result_stale' else 100)
   c.guard=lambda s,baseline:None
   try:initial_result(None,0,now,pause)
   except (RuntimeError,TimeoutError):assert name!='initial_result_wait'
   else:assert name=='initial_result_wait' and tick[0]>.1
   cases.append(dict(case=name,result='PASS_PC_EXPOSURE_NO_HARDWARE'))
 finally:c.read_state,c.guard=old_state,old_guard
 return cases
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',action='store_true');args=ap.parse_args();hashes=inputs()
 if not args.run:print('INPUT_HASHES_PASS_NO_HARDWARE');return 0
 assert (HERE/'SERVICE_RUN_STARTED.txt').exists()
 for n in ('HARDWARE_RUN_STARTED.txt','HARDWARE_RUN_BLOCKED.json','jtag_actual.log'):assert not (HERE/n).exists()
 checks=json.loads((HERE/'OFFLINE_CHECKS.json').read_text());assert checks['input_hashes']==hashes
 for n,sha in checks['source_hashes'].items():assert hashlib.sha256((HERE/n).read_bytes()).hexdigest()==sha,n
 r=dict(version='0.2.0',result='IN_PROGRESS',source_age_limit_ms=250,format_counter_reset=False,arm_connected=False,d5_low=True,started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),input_hashes=hashes,physical_arm_loop='NOT_RUN')
 b=None;save('SESSION_RESULT.json',r)
 try:b=Bridge();b.wait_ready();observe(b,r)
 except Exception as e:r.update(result='STOPPED_ERROR',error=repr(e))
 finally:
  if b is not None:
   if not b.failed and not r.get('sensor_command_fault'):
    try:restore_sensor(b,r)
    except Exception as e:r.update(result='SENSOR_RESTORE_FAILED',sensor_restore_error=repr(e))
   try:b.close();r['shutdown']='PASS_REVISED_ISOLATED_SHUTDOWN'
   except Exception as e:r.update(result='RESTORE_INCOMPLETE',restore_error=repr(e),requires_user_power_cycle=True)
  r['ended_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save('SESSION_RESULT.json',r)
 print(json.dumps({k:r[k] for k in ('result','shutdown','sensor_restore','error') if k in r}),flush=True)
 return 0 if r['result']=='EXPOSURE_COMPARISON_COMPLETED' and r.get('shutdown')=='PASS_REVISED_ISOLATED_SHUTDOWN' and r.get('sensor_restore')=='ORIGINAL_VALUES_AND_MODE_VERIFIED' else 2
if __name__=='__main__':raise SystemExit(main())
