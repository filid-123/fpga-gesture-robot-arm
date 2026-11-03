"""Check complete V2 package offline; no board access."""
from pathlib import Path
import hashlib,json,zipfile
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def check(root):
 root=Path(root).resolve();m=json.loads((root/'BOARD_MANIFEST.json').read_text('utf-8'))
 if m['version']!='0.11.0' or m['task_abi']!=0x3409 or m['arrival_policy']!='observe_all':raise ValueError('Wrong V2 contract')
 for rel,digest in m['inputs'].items():
  p=(root/rel).resolve()
  if not p.is_relative_to(root) or sha(p)!=digest:raise ValueError('Changed input '+rel)
 for rel,digest in json.loads((root/'evidence/BUILT_SOURCE_HASHES.json').read_text('utf-8'))['files'].items():
  if sha(root/rel)!=digest:raise ValueError('Build binding '+rel)
 h=json.loads((root/'evidence/IMPLEMENTATION_SUMMARY.json').read_text('utf-8'))
 if h['task_abi']!=0x3409 or h['timing_ns']['WNS']<0 or h['timing_ns']['WHS']<0:raise ValueError('Invalid implementation')
 for n,meta in h['artifacts'].items():
  if sha(root/'hardware'/n)!=meta['sha256']:raise ValueError('Hardware binding '+n)
 with zipfile.ZipFile(root/'hardware/roarm_closed_loop.xsa') as z:
  if z.testzip():raise ValueError('XSA CRC')
  for ext in ('bit','hwh'):
   name='roarm_closed_loop.'+ext
   if hashlib.sha256(z.read(name)).hexdigest()!=sha(root/'hardware'/name):raise ValueError('XSA member '+name)
 t=json.loads((root/'candidate/S4_BANKED_CANDIDATE.json').read_text('utf-8'))
 if t['execution_profile'].get('handalign_image_axis')!='Y' or t['execution_profile'].get('handalign_desk_axis')!='Y':raise ValueError('Alignment axes')
 if len(t['keypoint_banks'])!=4 or t['arrival_mask']!=0 or t['hold_policy'] is not False:raise ValueError('Wrong bank semantics')
 for i in range(4):
  p=root/f'candidate/bank{i}/PLAN_NATIVE.json';plan=json.loads(p.read_text('utf-8'))
  table=json.loads(p.with_name('S4_NATIVE_CANDIDATE.json').read_text('utf-8'))
  if table['keypoints']!=t['keypoint_banks'][i] or table['segments']!=t['segments']:raise ValueError('Table bank mismatch')
  for name in ('COPPELIA_RESULT.json','COPPELIA_WIRE_RESULT.json'):
   r=json.loads(p.with_name(name).read_text('utf-8'))
   if not r['passed'] or r['collision_samples'] or r['native_plan_sha256']!=sha(p):raise ValueError('Simulation binding')
  points=plan['layout']['common_D_mm']
  if points['H']!=[285,[135,195,255,255][i],175] or points['PRE']!=[350,[155,215,275,275][i],180] or points['H_CLEAR']!=[285,[135,195,255,255][i],195]:raise ValueError('Geometry contract')
 return dict(result='LOCATOR_THREE_INDEPENDENT_RETARGET_PACKAGE_SOURCE_MODEL_HARDWARE_BANKS_COPPELIA_PASS',files=len(m['inputs']),version=m['version'],physical_test='NOT_RUN',hardware_access=False)
