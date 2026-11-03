"""Assemble the complete four-region board release from verified artifacts."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,zipfile
from mode_a_four_config import ROOT,default_map
from mode_a_four_profile import profile
from prepare_mode_a_four_bridge import generate
D=Path('D:/FPGA_Projects/Gesture/deliverables')
BASE='Gesture_ModeA_FPGA_v0.9.1_20261028_ImageY_DeskY'
BASE_SHA='e60a8403181b0282d508ef9602695bf36e6dd3d881066c196064e66fa9b41fcd'
NAME='Gesture_ModeA_FPGA_v0.10.0_20261028_FourZone_FixedThreshold'
P=ROOT/'board_evidence/mode_a_four_plan_a3';H=ROOT/'board_evidence/mode_a_four_a1'
IMPL=ROOT/'board_evidence/mode_a_four_impl_a1';REPLAY=ROOT/'board_evidence/mode_a_four_replay_a3'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 out=D/NAME;archive=Path(str(out)+'.zip')
 if out.exists() or archive.exists():raise FileExistsError(out)
 if sha(D/(BASE+'.zip'))!=BASE_SHA:raise ValueError('Frozen parent ZIP changed')
 selected=['mode_a_four_task_a3','mode_a_four_regs_a1','mode_a_four_units_a1','mode_a_four_uart_xsim_a1','mode_a_cancel_return_xsim_a401',*[f'mode_a_cancel_shift_s2_xsim_a430{i}' for i in range(5)]]
 for n in selected:assert json.loads((ROOT/'board_evidence'/n/'RESULT.json').read_text('utf-8'))['passed'],n
 hw=json.loads((IMPL/'IMPLEMENTATION_SUMMARY.json').read_text('utf-8'))
 assert hw['task_abi']==0x3408 and hw['timing_ns']['WNS']>=0
 out.mkdir(parents=True)
 def dump(rel,obj):
  p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2)+'\n','utf-8')
 def cp(src,rel):
  p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,p);assert sha(src)==sha(p)
 with zipfile.ZipFile(D/(BASE+'.zip')) as z:
  assert z.testzip() is None
  hashes={l.split('  ',1)[1]:l.split('  ',1)[0] for l in z.read(BASE+'/SHA256SUMS').decode().splitlines()}
  parent=json.loads(z.read(BASE+'/BOARD_MANIFEST.json'))
  for rel,digest in hashes.items():
   if rel in ('BOARD_MANIFEST.json','README_CN.md','INTERFACE_CN.md','PATH_PLAN_CN.md','hand_map_uncalibrated_example.json') or rel.startswith(('candidate/','cancel_replay/','figures/','hardware/')):continue
   dst='evidence/v091/'+rel.removeprefix('evidence/') if rel.startswith('evidence/') else rel
   p=(out/dst).resolve();assert p.is_relative_to(out.resolve()) and 'LOCAL' not in rel and not rel.startswith('runs/')
   data=z.read(BASE+'/'+rel);assert hashlib.sha256(data).hexdigest()==digest,rel
   p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 dump('evidence/V091_BOARD_MANIFEST.json',parent)
 binding=json.loads((IMPL/'BUILT_SOURCE_HASHES.json').read_text('utf-8'))
 for name,digest in binding['files'].items():
  assert sha(ROOT/name)==digest,name
  cp(ROOT/name,name)
 for p in (ROOT/'scripts').glob('*four*.py'):cp(p,'scripts/'+p.name)
 for p in (ROOT/'native_motion/sim/mode_a_four').iterdir():cp(p,'native_motion/sim/mode_a_four/'+p.name)
 for n in ('BUILT_SOURCE_HASHES.json','IMPLEMENTATION_SUMMARY.json','BUILD_COMPLETED.json'):cp(IMPL/n,'evidence/'+n)
 for p in (IMPL/'implemented_reports').iterdir():
  if p.suffix in ('.bit','.hwh','.xsa'):cp(p,'hardware/'+p.name)
  elif p.is_file() and p.suffix in ('.rpt','.txt'):cp(p,'evidence/implemented_reports/'+p.name)
 for p in (IMPL/'inspection_a1').iterdir():
  if p.is_file() and p.suffix in ('.rpt','.txt','.json','.tcl'):cp(p,'evidence/inspection/'+p.name)
 coppelia_samples=0
 for i in range(4):
  for p in (P/f'bank{i}').iterdir():
   if p.is_file():cp(p,f'candidate/bank{i}/'+p.name)
  for wire,name in ((False,'COPPELIA_RESULT.json'),(True,'COPPELIA_WIRE_RESULT.json')):
   src=ROOT/'board_evidence'/f'mode_a_four_coppelia_{i}_{"wire" if wire else "exact"}_a3/RESULT.json';r=json.loads(src.read_text('utf-8'))
   assert r['passed'] and r['collision_samples']==0 and r['native_plan_sha256']==sha(P/f'bank{i}/PLAN_NATIVE.json');coppelia_samples+=r['samples_checked'];cp(src,f'candidate/bank{i}/'+name)
 cp(P/'S4_BANKED_CANDIDATE.json','candidate/S4_BANKED_CANDIDATE.json')
 for p in REPLAY.iterdir():
  if p.is_file():cp(p,'cancel_replay/'+p.name)
 for wire,name in ((False,'COPPELIA_RESULT.json'),(True,'COPPELIA_WIRE_RESULT.json')):
  src=ROOT/'board_evidence'/f'mode_a_four_coppelia_4_{"wire" if wire else "exact"}_a3/RESULT.json';r=json.loads(src.read_text('utf-8'))
  assert r['passed'] and r['collision_samples']==0 and r['native_plan_sha256']==sha(REPLAY/'PLAN_NATIVE.json');coppelia_samples+=r['samples_checked'];cp(src,'cancel_replay/'+name)
 cp(P/'PATH_PLAN_CN.md','PATH_PLAN_CN.md')
 for p in (P/'figures').iterdir():cp(p,'figures/'+p.name)
 for n in ('README_CN.md','INTERFACE_CN.md'):cp(ROOT/'docs/mode_a_four_v0_10_0'/n,n)
 for name in selected:
  for p in (ROOT/'board_evidence'/name).rglob('*'):
   if p.is_file() and p.suffix in ('.json','.txt','.mem','.sv','.f') and not any(x in ('xsim.dir','.Xil') for x in p.parts):cp(p,'evidence/'+name+'/'+p.relative_to(ROOT/'board_evidence'/name).as_posix())
 vision=ROOT/'board_evidence/mode_a_four_vision_a1'
 for p in (vision/'rtl_final_a401').iterdir():
  if p.is_file():cp(p,'evidence/final_top/'+p.name)
 cp(vision/'INPUT_AUDIT.json','evidence/final_top/INPUT_AUDIT.json')
 cp(H/'VISION_MODEL_REUSE.json','evidence/VISION_MODEL_REUSE.json')
 frozen={name:d for name,d in hashes.items() if name.startswith('model_package/') or name.startswith(('native_motion/rtl/cnn/','native_motion/rtl/locator/','native_motion/rtl/autonomous/','native_motion/rtl/camera/'))}
 for name,digest in frozen.items():assert sha(out/name)==digest,name
 plan=json.loads((P/'bank1/PLAN_NATIVE.json').read_text('utf-8'));table=json.loads((P/'S4_BANKED_CANDIDATE.json').read_text('utf-8'))
 text,meta=generate(plan,table);(out/'scripts/mode_a_board_bridge.tcl').write_text(text,'utf-8');dump('evidence/BRIDGE_GENERATION.json',meta);dump('fixed_four_region_map.json',default_map())
 s2_samples=sum(json.loads((ROOT/'board_evidence'/f'mode_a_cancel_shift_s2_xsim_a430{i}/RESULT.json').read_text('utf-8'))['samples'] for i in range(5))
 summary=dict(result='FOUR_IMAGE_Y_FIXED_THRESHOLDS_FULL_RELEASE_PASS',version='0.10.0',parent_package_sha256=BASE_SHA,hardware_rebuilt=True,model_changed=False,frozen_vision_model_files=len(frozen),built_input_files=len(binding['files']),pc_checks=33,terminal_checks=13,s2_exact_samples=s2_samples,coppelia_samples=coppelia_samples,coppelia_collision_samples=0,task_normal_colors_banks=12,cancel_replay_routes=16,execution_profile=profile(),bank_capacity=table['capacity'],align_n=table['align_n'],align_na=table['align_na'],align_pairs=table['align_pairs'],utilization=hw['utilization'],timing_ns=hw['timing_ns'],physical_hardware_test='NOT_RUN')
 dump('evidence/VERIFIED_SUMMARY.json',summary)
 source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 manifest=dict(version='0.10.0',hardware_version='0.10.0',task_abi=0x3408,arrival_policy='observe_all',source_commit=source,parent_package_sha256=BASE_SHA,execution_profile=profile(),physical_hardware_test='NOT_RUN',inputs={})
 for folder in ('scripts','ps','hardware','model_package','native_motion','planning','candidate','cancel_replay'):
  for p in (out/folder).rglob('*'):
   if p.is_file() and '__pycache__' not in p.parts:manifest['inputs'][p.relative_to(out).as_posix()]=sha(p)
 for name in ('BUILT_SOURCE_HASHES.json','IMPLEMENTATION_SUMMARY.json','VERIFIED_SUMMARY.json','VISION_MODEL_REUSE.json'):manifest['inputs']['evidence/'+name]=sha(out/'evidence'/name)
 for n in ('README_CN.md','INTERFACE_CN.md','PATH_PLAN_CN.md','fixed_four_region_map.json'):manifest['inputs'][n]=sha(out/n)
 dump('BOARD_MANIFEST.json',manifest)
 for script,expected,name in [('test_mode_a_four.py',33,'PC_TESTS.txt'),('test_mode_a_terminal.py',13,'TERMINAL_TESTS.txt')]:
  r=subprocess.run([sys.executable,'-X','utf8','-B',str(out/'scripts'/script)],cwd=out,capture_output=True);txt=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/'evidence'/name).write_text(txt,'utf-8')
  if r.returncode or f'Ran {expected} tests' not in txt:raise RuntimeError(txt)
 replan=ROOT/'board_evidence/mode_a_four_packaged_replan_a1'
 r=subprocess.run(['D:/RobotSim/.venv/Scripts/python.exe','-X','utf8','-B',str(out/'scripts/prepare_mode_a_four.py'),'--out',str(replan)],cwd=out,capture_output=True)
 if r.returncode:raise RuntimeError((r.stdout+r.stderr).decode('utf-8',errors='replace'))
 names=['S4_BANKED_CANDIDATE.json',*[f'bank{i}/{n}' for i in range(4) for n in ('PLAN_NATIVE.json','S4_NATIVE_CANDIDATE.json','SCENE_PLAN.json','SUMMARY.json','PATH_PREVIEW.json','JOINT_TARGETS_NATIVE.csv')]]
 for n in names:assert sha(replan/n)==sha(out/'candidate'/n),n
 dump('evidence/REPRODUCTION.json',dict(passed=True,files={n:sha(replan/n) for n in names}))
 from check_mode_a_four_package import check
 dump('evidence/PACKAGE_CHECK.json',check(out))
 r=subprocess.run([sys.executable,'-X','utf8','-B',str(out/'scripts/run_mode_a_four.py'),'--check-only'],cwd=out,capture_output=True)
 (out/'evidence/ENTRY_CHECK.txt').write_bytes(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError((r.stdout+r.stderr).decode('utf-8',errors='replace'))
 files=sorted(p for p in out.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
 (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n' for p in files),'utf-8');files.append(out/'SHA256SUMS')
 with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in files:z.write(p,(Path(NAME)/p.relative_to(out)).as_posix())
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for p in files:assert hashlib.sha256(z.read((Path(NAME)/p.relative_to(out)).as_posix())).hexdigest()==sha(p),p
 result=dict(result='FOUR_COMPLETE_NEW_HW_REPLAN_SOURCE_SHA_CRC_PASS',directory=str(out),zip=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),files=len(files),source_commit=source,physical_hardware_test='NOT_RUN')
 for n in ('VERIFIED_SUMMARY.json','REPRODUCTION.json','PACKAGE_CHECK.json'):shutil.copyfile(out/'evidence'/n,H/n)
 (H/'PACKAGE_RESULT.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
