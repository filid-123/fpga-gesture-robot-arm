"""P4 standalone release gates: data/binary/proof binding, no devices opened."""
from copy import deepcopy
import hashlib,json,re,tempfile
import numpy as np
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def verify(root,manifest,binding,impl,freeze,current):
 base=root/'board_evidence/mode_ab_p4'
 scope=json.loads((base/'release_scope.json').read_bytes())
 permits=scope['permitted_historical_bindings']
 if not scope['passed']:raise ValueError('Release scope failed')
 def proof(path,allow=()):
  r=json.loads(path.read_bytes())
  if not r.get('passed',False):raise ValueError('Failed proof: '+str(path))
  for name,digest in r.get('source_hashes',{}).items():
   if sha(root/name)==digest:continue
   p=permits.get(name,{})
   if name not in allow or p.get('old_sha256')!=digest or p.get('new_sha256')!=sha(root/name):raise ValueError('Proof source differs: '+str(path)+' '+name)
  return r
 route='pc/mode_ab/native_routes.py';test='scripts/test_mode_ab_native.py';s2='native_motion/rtl/robot/phase3_s2_motion_top.v';player='native_motion/rtl/robot/b_route_player.v'
 proof(base/'release_scope.json')
 pc=proof(base/'pc_final/result.json',(route,test,'pc/mode_ab/native_upload.py'))
 if pc['pc_tests']!=74 or pc['ui_checks']!=10:raise ValueError('PC/UI coverage differs')
 startup=proof(base/'startup_map_p4_1_final/result.json')
 if startup['tests']!=3 or not startup['old_four_page_fault_reproduced']:raise ValueError('Startup mapping proof missing')
 for name in ('profiles_release','coverage_release','flows_release'):
  proof(base/name/'result.json',(route,))
 for name in ('gpu_final','route_pipeline_release','reset_warning_release','gripper_pipeline_release','gripper_waits_final'):
  proof(base/name/'result.json')
 for name in ('backend_final','route_aperture_final'):proof(base/name/'result.json',(s2,player))
 vectors=proof(base/'native_vectors_pipeline_final/result.json')
 s4=proof(root/'board_evidence/mode_ab_paths_p4final/result.json')
 proof(root/'board_evidence/mode_a_upgrade_hdmi_abp4final/result.json')
 proof(root/'board_evidence/pl_wrappers_v1/vision_validation.json')
 grip=json.loads((base/'gripper_waits_final/result.json').read_bytes())
 from pc.mode_ab.native_family import fingerprint,trajectory
 for record in grip['results']:
  name=record['class_name'];folder=root/'candidate/mode_ab/native_profiles'/name
  before=base/'gripper_waits_final'/(name+'_before.json');after=folder/'normal.json'
  if sha(before)!=record['old_sha256'] or sha(after)!=record['new_sha256']:raise ValueError('Grip delta binding')
  a=json.loads(before.read_bytes());b=json.loads(after.read_bytes());ap=a['native_program'];bp=b['native_program']
  for key in ('bases','offsets','labels','points','stage_count','abi','schema'):
   if ap[key]!=bp[key]:raise ValueError('Native geometric vector delta')
  ad=np.array(ap['descriptors']).reshape(3,16,4);bd=np.array(bp['descriptors']).reshape(3,16,4)
  for i in range(16):
   if i in (1,3,9,15):
    if not np.array_equal(ad[:,i,[0,2,3]],bd[:,i,[0,2,3]]) or np.any(bd[:,i,1]<ad[:,i,1]):raise ValueError('Grip event delta')
   elif not np.array_equal(ad[:,i],bd[:,i]):raise ValueError('Giao phase changed')
  if b['task_abi']!=0x340e or bp['points']>2048 or len(b['fifo'])>63:raise ValueError('Native capacity/ABI')
  p=json.loads((folder/'native_bank1.json').read_bytes())
  if fingerprint(a,p)!=fingerprint(b,p):raise ValueError('Native geometry proof changed')
  key=fingerprint(b,p)
  cert=json.loads((folder/'family_certificate.json').read_bytes())
  if not cert['passed'] or cert['fingerprint']!=key:raise ValueError('Family certificate missing')
  source='candidate/mode_ab/native_profiles/'+name+'/normal.json'
  if vectors['inputs'][source]!=sha(after):raise ValueError('Final native vector binding')
  # No slow geometry rerun: decode remains exactly identical by construction.
  if not np.array_equal(trajectory(ap,8,32),trajectory(bp,8,32)):raise ValueError('Native decoder delta')
 for name,digest in vectors['inputs'].items():
  if name.startswith('candidate/mode_ab/native_profiles/'):continue
  if sha(root/name)!=digest:raise ValueError('Native vector input differs: '+name)
 for name,digest in s4['inputs'].items():
  actual=root/name
  if name.startswith('candidate/mode_ab/native_profiles/') and name.endswith('/normal.json'):
   kind=name.split('/')[-2];actual=base/'gripper_waits_final'/(kind+'_before.json')
  if sha(actual)!=digest:raise ValueError('S4 state-control input binding differs: '+name)
 pure=root/'board_evidence/pl_wrappers_v1';r=json.loads((pure/'result.json').read_bytes())
 if not r['passed'] or r['structural_wrappers']!=12:raise ValueError('Wrapper proof failed')
 for name,digest in r['source_hashes'].items():
  if sha(root/r['proof_source_root']/name)!=digest:raise ValueError('Pure wrapper snapshot changed')
 hwh=(root/'hardware/roarm_closed_loop.hwh').read_text(encoding='utf-8-sig')
 if 's_axi_route' not in hwh or '0x43C20000' not in hwh or '<PARAMETER NAME="FAST_B" VALUE="1"/>' not in hwh:raise ValueError('Actual B route hardware aperture missing')
 for line in (root/'sha256sums.txt').read_text().splitlines():
  digest,name=line.split('  ',1)
  if sha(root/name)!=digest:raise ValueError('Member SHA mismatch: '+name)
 for name in list(manifest['inputs'])+['mode_ab_manifest.json','sha256sums.txt']:
  if name!=name.lower() or not all(re.fullmatch('[a-z0-9_.-]+',p) for p in name.split('/')):raise ValueError('Nonportable package name')
 from pc.mode_ab.motion import ROOT
 if ROOT.resolve()!=root:raise ValueError('Development module imported')
 from run_mode_a_restock import setup_tools
 with tempfile.TemporaryDirectory(prefix='mode_ab_factory_') as tmp:
  from pathlib import Path
  bridge,server,exposure=setup_tools(root,Path(tmp))
  if bridge.__name__!='BoardBridge' or not hasattr(exposure,'restore_sensor'):raise ValueError('Incomplete transport factory')
 return dict(result='COMPLETE_PACKAGE_HASH_BINDING_AND_ENTRY_PASS',patch_id=manifest['patch_id'],hotfix_id=manifest.get('hotfix_id'),task_abi='340E',
  input_files=len(manifest['inputs']),built_sources=len(binding['files']),frozen_dependencies=len(freeze['files_sha256']),
  distinct_pc_tests=scope['total_distinct_python_tests'],ui_checks=10,hardware_access=False,physical_test='NOT_RUN')
