"""Offline complete v013 contract; no hardware connection."""
from pathlib import Path
import hashlib,json,zipfile
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def check(root):
 root=Path(root).resolve();m=json.loads((root/'BOARD_MANIFEST.json').read_text('utf-8'))
 if (m['version'],m['hardware_version'],m['task_abi'],m['arrival_policy'])!=('0.13.1','0.13.1',0x340a,'observe_all'):raise ValueError('Wrong v0131 display-fix contract')
 if m.get('display_output')!=[1280,720,60]:raise ValueError('Wrong display output')
 for rel,d in m['inputs'].items():
  p=(root/rel).resolve()
  if not p.is_relative_to(root) or sha(p)!=d:raise ValueError('Changed package input '+rel)
 binding=json.loads((root/'evidence/BUILT_SOURCE_HASHES.json').read_text('utf-8'))
 if binding['parameters'].get('UPGRADE')!=1:raise ValueError('Upgrade not enabled')
 for rel,d in binding['files'].items():
  if sha(root/rel)!=d:raise ValueError('Build input mismatch '+rel)
 h=json.loads((root/'evidence/IMPLEMENTATION_SUMMARY.json').read_text('utf-8'))
 if h['task_abi']!=0x340a or h['timing_ns']['WNS']<0 or h['timing_ns']['WHS']<0:raise ValueError('Implementation timing/ABI')
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
 return dict(result='UPGRADE_PACKAGE_RESOURCE85_SOURCE_MODEL_HARDWARE_AND_CONTINUOUS_GEOMETRY_PASS',version=m['version'],files=len(m['inputs']),physical_test='NOT_RUN',hardware_access=False)
