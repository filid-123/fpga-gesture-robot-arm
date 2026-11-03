"""Single Phase2 camera session: three full small frames and60s live observation."""
from pathlib import Path
import argparse,datetime,hashlib,json,math,struct,time,zipfile
from transport_reused import Bridge,BASE,HERE,ROOT,PACKAGE,XSA,read_state as original_read_state,inert
from png_helper import gray_png
class FormatFault(RuntimeError):pass
class AgeFault(RuntimeError):pass
def save(name,value):
 (HERE/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
def inputs():
 manifest=json.loads((PACKAGE/'MANIFEST.json').read_text(encoding='utf-8'))
 assert manifest['version']=='0.4.0' and manifest['model_id']=='022267A9'
 assert manifest['physical_motion_authorized'] is False
 assert manifest['snapshot']==dict(abi='3505',width=128,height=128,bytes=16384,words=4096)
 assert manifest['hardware_source_binding_sha256']==json.loads((HERE/'SOURCE_CHECKPOINT.json').read_text(encoding='utf-8'))['hardware_source_binding_sha256']
 hashes={}
 for suffix in ('bit','hwh','xsa'):
  n='roarm_closed_loop.'+suffix;p=PACKAGE/'hardware'/n;sha=hashlib.sha256(p.read_bytes()).hexdigest()
  assert sha==manifest['artifacts'][n]['sha256'];hashes[str(p)]=sha
 with zipfile.ZipFile(XSA) as z:
  for suffix in ('bit','hwh'):assert hashlib.sha256(z.read('roarm_closed_loop.'+suffix)).hexdigest()==manifest['artifacts']['roarm_closed_loop.'+suffix]['sha256']
 return hashes

def read_state(b):
 s=original_read_state(b);c=s['camera_status']
 s.update(phase2_marker=bool(c&(1<<21)),valid_mask=(c>>16)&3,snapshot_bank=(c>>20)&1,source_age_ms=(s['now_ms']-s['acquisition_ms'])&0xffffffff)
 return s
def health(c):
 if not c&(1<<21) or c&0x14 or c&0xb!=0xb:raise RuntimeError('Camera init/clock/capture/overflow/Phase2 marker invalid: '+hex(c))
def guard(s,baseline):
 if not s['coherent']:raise RuntimeError('No coherent camera telemetry')
 health(s['camera_status'])
 if s['vision_status']&4:raise RuntimeError('Vision fatal')
 if s['format_errors']!=baseline:raise FormatFault('Format grew; original cumulative baseline is not reset')
def startup(b,r,clock,pause):
 r['initial_motion_state']=inert(b)
 if b.read(BASE+8)[0]!=0x3505 or b.read(BASE+0x70)[0]!=0x022267a9 or b.read(BASE+0x74)[0]!=0x43414d31:raise RuntimeError('Phase2 ABI/model/CAM1 mismatch')
 deadline=clock()+12
 while True:
  s=read_state(b);r.setdefault('startup_samples',[]).append(s)
  if s['init_error'] or s['fifo_overflow'] or s['vision_status']&4:raise RuntimeError('Initialization/overflow/fatal error')
  if s['init_done'] and s['xclk_locked'] and s['capture_enabled']:
   baseline=s['format_errors'];r['format_baseline']=baseline;guard(s,baseline);return baseline
  if clock()>deadline:raise TimeoutError('Camera initialization timeout')
  pause(.05)
def image(b,r,baseline,index,clock,pause):
 guard(read_state(b),baseline)
 if b.read(BASE+0x40)[0]:raise RuntimeError('Snapshot already owned')
 b.write(BASE+0x40,1);r['snapshot_enable_attempted']=True
 try:
  deadline=clock()+10
  while not b.read(BASE+0x44)[0]&1:
   guard(read_state(b),baseline)
   if clock()>deadline:raise TimeoutError('Snapshot did not become ready')
   pause(.02)
  fid=b.read(BASE+0x48)[0];stamp=b.read(BASE+0x58)[0]
  if b.read(BASE+0x54)[0]!=0x00800080:raise RuntimeError('Snapshot dimensions must be128x128')
  b.write(BASE+0x4c,0);data=bytearray();start=clock()
  for _ in range(16):
   data.extend(struct.pack('<256I',*b.stream(256)))
   c,d,e,now=b.read(BASE+0x78,4);health(c)
   if e!=baseline:raise FormatFault('Format grew during frozen image transfer')
  if len(data)!=16384 or b.read(BASE+0x4c)[0]!=4096:raise RuntimeError('Incomplete image or incorrect final pointer')
  if not b.read(BASE+0x44)[0]&1 or b.read(BASE+0x48)[0]!=fid or b.read(BASE+0x58)[0]!=stamp:raise RuntimeError('Snapshot identity/ownership changed')
  name=f'camera_{index:02d}_128x128'
  (HERE/(name+'.raw')).write_bytes(data)
  (HERE/(name+'.pgm')).write_bytes(b'P5\n128 128\n255\n'+data)
  (HERE/(name+'.png')).write_bytes(gray_png(data,128,128))
  hist=[data.count(i) for i in range(256)];content=data[16*128:112*128]
  m=dict(index=index,width=128,height=128,format='GRAY8_PHASE2_SELECTED_Y',bytes=16384,words=4096,frame_id=fid,acquisition_ms=stamp,sha256=hashlib.sha256(data).hexdigest(),
   min=min(data),max=max(data),distinct=sum(v>0 for v in hist),entropy_bits=-sum((v/len(data))*math.log2(v/len(data)) for v in hist if v),
   content_min=min(content),content_max=max(content),content_distinct=len(set(content)),padding_16_rows_exact_zero=not any(data[:2048]+data[-2048:]),
   transfer_wall_s=clock()-start,frame_identity_stable=True,scene='UNARRANGED',image_name=name+'.png')
  r.setdefault('images',[]).append(m);save(name+'.json',m);save('SESSION_RESULT.json',r)
  print('REAL_CAMERA_IMAGE_SAVED '+name+' FRAME_ID '+str(fid),flush=True)
  if not m['padding_16_rows_exact_zero']:raise RuntimeError('Phase2 padding rows corrupted')
  if len(r['images'])>1 and (fid,stamp)==(r['images'][-2]['frame_id'],r['images'][-2]['acquisition_ms']):raise RuntimeError('No new acquired snapshot')
  r['snapshot_release_now_ms']=b.read(BASE+0x84)[0];r['snapshot_prior_result_id']=read_state(b)['result_frame_id']
 finally:
  if not b.failed:b.write(BASE+0x40,0);r['snapshot_released']=True
def fresh_after_snapshot(b,r,baseline,clock,pause):
 deadline=clock()+5;release=r['snapshot_release_now_ms'];prior=r['snapshot_prior_result_id']
 while True:
  s=read_state(b);guard(s,baseline)
  if s['result_frame_id']!=prior and ((s['acquisition_ms']-release)&0xffffffff)<0x80000000:
   if s['source_age_ms']>250:raise AgeFault('New post-snapshot source age exceeds250ms')
   return s
  if clock()>deadline:raise TimeoutError('No new acquired result after snapshot release')
  pause(.05)
def live(b,r,baseline,seconds,clock,pause,stream):
 start=clock();deadline=start+seconds;first=True;segment=[]
 while True:
  s=read_state(b);s['observation_wall_s']=clock()-start
  r.setdefault('telemetry',[]).append(s);segment.append(s);stream.write(json.dumps(s)+'\n');stream.flush()
  guard(s,baseline)
  if s['source_age_ms']>250:raise AgeFault('Live source age exceeds original250ms limit')
  if clock()>=deadline:break
  pause(.1)
 ids={s['result_frame_id'] for s in segment}
 if len(ids)<2:raise RuntimeError('No continuing frames')
 r.setdefault('live_segments',[]).append(dict(requested_s=seconds,wall_s=clock()-start,samples=len(segment),unique_result_ids=len(ids)))
def observe(b,r,clock=time.monotonic,pause=time.sleep,segment_seconds=30):
 assert 0<segment_seconds<=30
 baseline=startup(b,r,clock,pause);save('SESSION_RESULT.json',r)
 with (HERE/'telemetry.jsonl').open('x',encoding='utf-8') as stream:
  for i in range(3):
   image(b,r,baseline,i,clock,pause);fresh_after_snapshot(b,r,baseline,clock,pause)
   if i<2:live(b,r,baseline,segment_seconds,clock,pause,stream)
   save('SESSION_RESULT.json',r)
 rows=r['telemetry'];ages=sorted(s['source_age_ms'] for s in rows)
 r['stability']=dict(live_seconds=sum(s['wall_s'] for s in r['live_segments']),samples=len(rows),unique_observed_result_ids=len({s['result_frame_id'] for s in rows}),
  format_start=baseline,format_end=rows[-1]['format_errors'],source_age_ms=dict(min=ages[0],p50=ages[len(ages)//2],p95=ages[min(len(ages)-1,int(len(ages)*.95))],max=ages[-1]))
 r['final_motion_state']=inert(b)
 r['result']='CAMERA_THREE_IMAGES_AND_60S_LIVE_PASS_PENDING_VISUAL_REVIEW'
# Helper only. The single hardware entry point is verify_exposure.py via run_board.py.
