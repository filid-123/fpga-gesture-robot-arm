"""Seal the independent V2 board candidate from the immutable first-draft ZIP."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,zipfile
from mode_a_v2_config import ROOT
from mode_a_v2_profile import profile
from prepare_mode_a_v2_bridge import generate
D=Path('D:/FPGA_Projects/Gesture/deliverables')
NAME='Gesture_ModeA_FPGA_v0.9.0_20261028_HandAlign3_Final'
BASE='Gesture_ModeA_ClosedLoop_FirstDraft_20261028'
BASE_SHA='2d8c2f11f1fa4450f4c6b5e64af005fb10246432e0d03c5a75803880cf37b5c2'
P=ROOT/'board_evidence/mode_a_v2_plan_a3';H=ROOT/'board_evidence/mode_a_v2_impl_a2';V=ROOT/'board_evidence/mode_a_v2_vision_a3'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 out=D/NAME;archive=D/(NAME+'.zip')
 if out.exists() or archive.exists():raise FileExistsError(out)
 if sha(D/(BASE+'.zip'))!=BASE_SHA:raise ValueError('First draft archive changed')
 # Every required result must exist and pass before making a deployable directory.
 hw=json.loads((H/'IMPLEMENTATION_SUMMARY.json').read_text('utf-8'))
 assert hw['task_abi']==0x3407 and hw['timing_ns']['WNS']>=0 and hw['timing_ns']['WHS']>=0
 selected=['mode_a_v2_task_a11','mode_a_v2_regs_a2','mode_a_cancel_return_xsim_a8','mode_a_v2_uart_xsim_a1',*[f'mode_a_cancel_shift_s2_xsim_a{i}' for i in (90,91,92,96)]]
 for name in selected:assert json.loads((ROOT/'board_evidence'/name/'RESULT.json').read_text('utf-8'))['passed'],name
 vision=['rtl_classifier_a95','rtl_locator_a95','rtl_pipeline0_a96','rtl_pipeline1_a96','rtl_v2opt_unit_a95','rtl_v2opt_stream_a95','rtl_final_a97','rtl_geometry_a96']
 for name in vision:
  r=json.loads((V/name/'RESULTS.json').read_text('utf-8'));assert r.get('passed') or r.get('result','').startswith('PASS'),name
 out.mkdir(parents=True)
 def cp(src,rel):
  p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,p)
  if sha(src)!=sha(p):raise ValueError('Copy '+rel)
 def dump(rel,obj):
  p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2)+'\n','utf-8')
 with zipfile.ZipFile(D/(BASE+'.zip')) as z:
  assert z.testzip() is None
  for member in z.namelist():
   rel=member.removeprefix(BASE+'/')
   if member.endswith('/') or rel in ('SHA256SUMS','BOARD_MANIFEST.json','FIRST_DRAFT_SEAL.json','README_CN.md','PATH_PLAN_CN.md') or rel.startswith(('candidate/','cancel_replay/','figures/','evidence/')):continue
   p=(out/rel).resolve()
   if not p.is_relative_to(out.resolve()) or 'LOCAL' in rel or rel.startswith('runs/'):raise ValueError('Unsafe parent member')
   p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(member))
 # Overlay complete current sources, excluding tools' caches and local raw evidence.
 for folder in ('native_motion/rtl','native_motion/scripts','native_motion/constraints','native_motion/sim','ps'):
  for p in (ROOT/folder).rglob('*'):
   if p.is_file() and p.name!='tb_stream_overlap_exp.sv' and '__pycache__' not in p.parts and p.suffix in ('.v','.sv','.vh','.tcl','.xdc','.mem','.py','.json'):cp(p,p.relative_to(ROOT).as_posix())
 cp(ROOT/'planning/roarm_m3_nominal.xacro','planning/roarm_m3_nominal.xacro')
 for p in (ROOT/'scripts').glob('*.py'):
  if any(k in p.name for k in ('_v2','mode_a_v3_checks','render_mode_a_delivery_layout')):cp(p,'scripts/'+p.name)
 for name in ('BUILT_SOURCE_HASHES.json','IMPLEMENTATION_SUMMARY.json','BUILD_COMPLETED.json','BUILD_COMMANDS.json','DEVELOPMENT_ATTEMPTS.json'):cp(H/name,'evidence/'+name)
 for p in (H/'implemented_reports').iterdir():
  if p.is_file():cp(p,('hardware/' if p.suffix in ('.bit','.hwh','.xsa') else 'evidence/implemented_reports/')+p.name)
 for p in (H/'inspection_a1').iterdir():
  if p.is_file():cp(p,'evidence/inspection/'+p.name)
 for i in range(3):
  for p in (P/f'bank{i}').iterdir():
   if p.is_file():cp(p,f'candidate/bank{i}/'+p.name)
  for wire,name in ((False,'COPPELIA_RESULT.json'),(True,'COPPELIA_WIRE_RESULT.json')):
   folder=f'mode_a_v2_coppelia_bank{i}_'+('wire_a1' if wire else ('a1' if i==0 else 'exact_a1'))
   src=ROOT/'board_evidence'/folder/'RESULT.json';r=json.loads(src.read_text('utf-8'))
   assert r['passed'] and r['collision_samples']==0 and r['native_plan_sha256']==sha(P/f'bank{i}/PLAN_NATIVE.json')
   cp(src,f'candidate/bank{i}/'+name)
 for name in ('S4_BANKED_CANDIDATE.json',):cp(P/name,'candidate/'+name)
 cp(P/'PATH_PLAN_CN.md','PATH_PLAN_CN.md')
 for p in (P/'figures').iterdir():cp(p,'figures/'+p.name)
 cp(ROOT/'docs/mode_a_v2_v0_9_0/README_CN.md','README_CN.md')
 cp(ROOT/'docs/mode_a_v2_v0_9_0/INTERFACE_CN.md','INTERFACE_CN.md')
 for p in (ROOT/'board_evidence/mode_a_v2_replay_a3').iterdir():
  if p.is_file():cp(p,'cancel_replay/'+p.name)
 for folder,name in [('mode_a_v2_replay_coppelia_a1','COPPELIA_RESULT.json'),('mode_a_v2_replay_wire_coppelia_a1','COPPELIA_WIRE_RESULT.json')]:cp(ROOT/'board_evidence'/folder/'RESULT.json','cancel_replay/'+name)
 for name in selected:
  for p in (ROOT/'board_evidence'/name).iterdir():
   if p.is_file() and p.suffix in ('.json','.txt','.sv','.mem','.f'):cp(p,'evidence/'+name+'/'+p.name)
 cp(V/'INPUT_AUDIT.json','evidence/vision/INPUT_AUDIT.json')
 for name in vision:
  for p in (V/name).iterdir():
   if p.is_file() and p.suffix in ('.txt','.json'):cp(p,'evidence/vision/'+name+'/'+p.name)
 # Bind every implementation input and the unchanged Rain package against the sealed original.
 binding=json.loads((H/'BUILT_SOURCE_HASHES.json').read_text('utf-8'))
 for rel,digest in binding['files'].items():assert sha(ROOT/rel)==digest and sha(out/rel)==digest,rel
 with zipfile.ZipFile(D/(BASE+'.zip')) as z:
  for line in z.read(BASE+'/SHA256SUMS').decode().splitlines():
   digest,rel=line.split('  ',1)
   if rel.startswith('model_package/'):assert sha(out/rel)==digest,rel
 plan=json.loads((P/'bank1/PLAN_NATIVE.json').read_text('utf-8'));table=json.loads((P/'S4_BANKED_CANDIDATE.json').read_text('utf-8'))
 text,meta=generate(plan,table);(out/'scripts/mode_a_board_bridge.tcl').write_text(text,'utf-8');dump('evidence/BRIDGE_GENERATION.json',meta)
 from mode_a_v2_config import default_map
 dump('hand_map_uncalibrated_example.json',default_map())
 summary=dict(result='V2_THREE_BANK_OPTIMIZATION_INTEGRATION_PASS',version='0.9.0',first_draft_tag='mode-a-closed-loop-v1-20261028',optimization_source='88de55d2c7ef392a84eb5a72cf3f79af535a268c',model_id='022267A9',model_changed=False,hardware_rebuilt=True,pc_checks=32,terminal_checks=13,selected_task_uart_s2_runs=len(selected),vision_runs=vision,s2_exact_samples=49330,coppelia_samples=98660,coppelia_collision_samples=0,locator_cycles=1647640,baseline_locator_cycles=2356248,stream_frames=12,stream_overlaps=7,profile=profile(),utilization=hw['utilization'],timing_ns=hw['timing_ns'],physical_hardware_test='NOT_RUN',known_limits=['Discrete X only; requires three image-center samples for camera orientation','Stopped kinematic collision replay; no contact dynamics or real actuator braking model','Two shortened mock PAUSE prefixes conservatively replayed over original N'])
 dump('evidence/VERIFIED_SUMMARY.json',summary)
 source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 manifest=dict(version='0.9.0',hardware_version='0.9.0',task_abi=0x3407,arrival_policy='observe_all',source_commit=source,parent_package_sha256=BASE_SHA,execution_profile=profile(),physical_hardware_test='NOT_RUN',inputs={})
 for folder in ('scripts','ps','hardware','model_package','native_motion','planning','candidate','cancel_replay'):
  for p in (out/folder).rglob('*'):
   if p.is_file() and '__pycache__' not in p.parts:manifest['inputs'][p.relative_to(out).as_posix()]=sha(p)
 for name in ('evidence/BUILT_SOURCE_HASHES.json','evidence/IMPLEMENTATION_SUMMARY.json','evidence/VERIFIED_SUMMARY.json'):manifest['inputs'][name]=sha(out/name)
 dump('BOARD_MANIFEST.json',manifest)
 for script,expected,log in [('test_mode_a_v2.py',32,'PC_TESTS.txt'),('test_mode_a_terminal.py',13,'TERMINAL_TESTS.txt')]:
  p=subprocess.run([sys.executable,'-X','utf8','-B',str(out/'scripts'/script)],cwd=out,capture_output=True)
  txt=(p.stdout+p.stderr).decode('utf-8',errors='replace');(out/'evidence'/log).write_text(txt,'utf-8')
  if p.returncode or f'Ran {expected} tests' not in txt:raise RuntimeError(txt)
 replan=ROOT/'board_evidence/mode_a_v2_packaged_replan_a2'
 proc=subprocess.run(['D:/RobotSim/.venv/Scripts/python.exe','-X','utf8','-B',str(out/'scripts/prepare_mode_a_v2.py'),'--out',str(replan)],cwd=out,capture_output=True)
 if proc.returncode:raise RuntimeError((proc.stdout+proc.stderr).decode('utf-8',errors='replace'))
 names=['S4_BANKED_CANDIDATE.json',*[f'bank{i}/{name}' for i in range(3) for name in ('PLAN_NATIVE.json','SCENE_PLAN.json','S4_NATIVE_CANDIDATE.json','SUMMARY.json','PATH_PREVIEW.json','JOINT_TARGETS_NATIVE.csv')]]
 for name in names:assert sha(replan/name)==sha(out/'candidate'/name),name
 dump('evidence/REPRODUCTION.json',dict(passed=True,files={name:sha(replan/name) for name in names},physical_robot=False))
 from check_mode_a_v2_package import check
 result=check(out);dump('evidence/PACKAGE_CHECK.json',result)
 files=sorted(p for p in out.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
 (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n' for p in files),'utf-8')
 with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in [*files,out/'SHA256SUMS']:z.write(p,(Path(NAME)/p.relative_to(out)).as_posix())
 with zipfile.ZipFile(archive) as z:
  if z.testzip():raise ValueError('ZIP CRC')
  for p in [*files,out/'SHA256SUMS']:
   if hashlib.sha256(z.read((Path(NAME)/p.relative_to(out)).as_posix())).hexdigest()!=sha(p):raise ValueError('ZIP member hash')
 result=dict(result='V2_COMPLETE_SOURCE_MODEL_HARDWARE_REPLAN_SHA_CRC_PASS',directory=str(out),zip=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,files=len(files)+1,source_commit=source,physical_hardware_test='NOT_RUN')
 (H/'PACKAGE_RESULT.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
