"""Offline complete v014 contract; no hardware connection."""
from pathlib import Path
import hashlib,json,zipfile
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def check(root):
 root=Path(root).resolve();m=json.loads((root/'BOARD_MANIFEST.json').read_text('utf-8'))
 if (m['version'],m['hardware_version'],m['task_abi'],m['arrival_policy'])!=('0.14.0','0.14.0',0x340b,'observe_all'):raise ValueError('Wrong v014 automatic-restock contract')
 if m.get('display_output')!=[1280,720,60]:raise ValueError('Wrong display output')
 for rel,d in m['inputs'].items():
  p=(root/rel).resolve()
  if not p.is_relative_to(root) or sha(p)!=d:raise ValueError('Changed package input '+rel)
 binding=json.loads((root/'evidence/BUILT_SOURCE_HASHES.json').read_text('utf-8'))
 if binding['parameters'].get('UPGRADE')!=1:raise ValueError('Upgrade not enabled')
 for rel,d in binding['files'].items():
  if sha(root/rel)!=d:raise ValueError('Build input mismatch '+rel)
 h=json.loads((root/'evidence/IMPLEMENTATION_SUMMARY.json').read_text('utf-8'))
 if h['task_abi']!=0x340b or h['timing_ns']['WNS']<0 or h['timing_ns']['WHS']<0:raise ValueError('Implementation timing/ABI')
 for k,c in {'LUT_TOTAL':53200,'FF':106400,'BRAM_TILE':140,'DSP':220}.items():
  if h['utilization'][k]>c*.85:raise ValueError('85 percent exceeded '+k)
 for name,meta in h['artifacts'].items():
  if sha(root/'hardware'/name)!=meta['sha256']:raise ValueError('Artifact mismatch '+name)
 with zipfile.ZipFile(root/'hardware/roarm_closed_loop.xsa') as z:
  if z.testzip():raise ValueError('XSA CRC')
  for ext in ('bit','hwh'):
   name='roarm_closed_loop.'+ext
   if hashlib.sha256(z.read(name)).hexdigest()!=sha(root/'hardware'/name):raise ValueError('XSA member')
 t=json.loads((root/'candidate/S4_BANKED_CANDIDATE.json').read_text('utf-8'))
 if t['abi']!=dict(arm=0x3101,planner=0x3203,task=0x340a,vision=0x3506,model=0x022267a9):raise ValueError('Table ABI')
 if t['arrival_mask']!=0 or t['hold_policy'] is not False or len(t['keypoint_banks'])!=4:raise ValueError('Execution semantics')
 for i in range(4):
  p=root/f'candidate/bank{i}/PLAN_NATIVE.json';plan=json.loads(p.read_text('utf-8'));table=json.loads(p.with_name('S4_NATIVE_CANDIDATE.json').read_text('utf-8'))
  if table['keypoints']!=t['keypoint_banks'][i] or table['segments']!=t['segments']:raise ValueError('Bank table')
  for name in ('COPPELIA_RESULT.json','COPPELIA_WIRE_RESULT.json'):
   r=json.loads(p.with_name(name).read_text('utf-8'))
   if not r['passed'] or r['collision_samples'] or r['native_plan_sha256']!=sha(p):raise ValueError('Coppelia anchor binding')
  if plan['execution_profile']['scalar_profile']!='QUINTIC_10u3_15u4_6u5_UQ32':raise ValueError('Wrong interpolation')
 continuous=json.loads((root/'evidence/continuous/RESULT.json').read_text('utf-8'))
 if not continuous['passed'] or continuous['positions']!=65 or continuous['collision_samples']!=0:raise ValueError('Continuous geometry')
 for i in range(3):
  if continuous['source_anchor_hashes'][f'bank{i}']!=sha(root/f'candidate/bank{i}/PLAN_NATIVE.json'):raise ValueError('Continuous anchor binding')
 from mode_a_restock_config import load_restock
 rs=load_restock(root)
 for name in ('COPPELIA_RESULT.json','COPPELIA_WIRE_RESULT.json'):
  c=json.loads((root/'candidate/restock'/name).read_text('utf-8'))
  if not c['passed'] or c['collision_samples'] or c['native_plan_sha256']!=sha(root/'candidate/restock/PLAN_NATIVE.json'):raise ValueError('Restock geometry binding')
 if binding['parameters'].get('AUTO_RESTOCK')!=1:raise ValueError('Auto-restock not compiled')
 for group,expected in [('restock_core',7),('restock_hdmi',7),('restock_integration',15),('legacy_s4',7)]:
  proof=json.loads((root/'evidence'/group/'RESULT.json').read_text('utf-8'))
  if not proof['passed'] or len(proof['checks'])!=expected:raise ValueError('Missing final proof '+group)
  for rel,d in proof['source_hashes'].items():
   if sha(root/rel)!=d:raise ValueError('Final proof source binding '+group+' '+rel)
 replay=root/'evidence/restock_replay'
 tr=json.loads((root/'evidence/TRACE_REUSE.json').read_text('utf-8'))
 if sha(replay/'S4_MOTION_TRACE.txt')!=tr['final_trace_sha256'] or tr['final_trace_sha256']!=tr['old_trace_sha256']:raise ValueError('S4 replay binding')
 s2=json.loads((root/'evidence/restock_s2/RESULT.json').read_text('utf-8'))
 if not s2['passed'] or s2['native_plan_sha256']!=sha(replay/'PLAN_NATIVE.json') or s2['bench_sha256']!=sha(root/'evidence/restock_s2/tb_speed15_s2.sv'):raise ValueError('S2 replay binding')
 for name in ('COPPELIA_EXACT.json','COPPELIA_WIRE.json'):
  proof=json.loads((replay/name).read_text('utf-8'))
  if not proof['passed'] or proof['collision_samples'] or proof['native_plan_sha256']!=sha(replay/'PLAN_NATIVE.json'):raise ValueError('Actual-command Coppelia binding')

 return dict(result='RESTOCK_PACKAGE_RESOURCE85_FINAL_PROOFS_SOURCE_MODEL_HARDWARE_AND_GEOMETRY_PASS',version=m['version'],files=len(m['inputs']),physical_test='NOT_RUN',hardware_access=False)
