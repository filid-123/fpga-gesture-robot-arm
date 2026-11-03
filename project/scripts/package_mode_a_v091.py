"""Image-Y / desk-Y release, preserving the entire v090 hardware/model bundle."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,zipfile
from mode_a_v091_config import ROOT,default_map
from mode_a_v091_profile import profile
from prepare_mode_a_v091_bridge import generate
D=Path('D:/FPGA_Projects/Gesture/deliverables');BASE='Gesture_ModeA_FPGA_v0.9.0_20261028_HandAlign3_Final'
BASE_SHA='0b70598458457ab38f929c88fcf339b10ee8789848dd7db2f72f05234fca6745'
NAME='Gesture_ModeA_FPGA_v0.9.1_20261028_ImageY_DeskY'
P=ROOT/'board_evidence/mode_a_v091_plan_a1';H=ROOT/'board_evidence/mode_a_v091_a1';REPLAY=ROOT/'board_evidence/mode_a_v091_replay_a1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 out=D/NAME;archive=Path(str(out)+'.zip')
 if out.exists() or archive.exists():raise FileExistsError(out)
 if sha(D/(BASE+'.zip'))!=BASE_SHA:raise ValueError('Frozen parent ZIP changed')
 selected=['mode_a_v091_task_a1','mode_a_v091_regs_a1',*[f'mode_a_cancel_shift_s2_xsim_a191{i}' for i in range(4)]]
 s2_samples=sum(json.loads((ROOT/'board_evidence'/n/'RESULT.json').read_text('utf-8'))['samples'] for n in selected[2:])
 for n in selected:assert json.loads((ROOT/'board_evidence'/n/'RESULT.json').read_text('utf-8'))['passed'],n
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
   if rel in ('BOARD_MANIFEST.json','README_CN.md','INTERFACE_CN.md','PATH_PLAN_CN.md','hand_map_uncalibrated_example.json') or rel.startswith(('candidate/','cancel_replay/','figures/')):continue
   dst='evidence/v090/'+rel.removeprefix('evidence/') if rel.startswith('evidence/') else rel
   p=(out/dst).resolve();assert p.is_relative_to(out.resolve()) and 'LOCAL' not in rel and not rel.startswith('runs/')
   data=z.read(BASE+'/'+rel);assert hashlib.sha256(data).hexdigest()==digest,rel
   p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 dump('evidence/V090_BOARD_MANIFEST.json',parent)
 for n in ('BUILT_SOURCE_HASHES.json','IMPLEMENTATION_SUMMARY.json'):cp(out/'evidence/v090'/n,'evidence/'+n)
 for name,digest in json.loads((out/'evidence/BUILT_SOURCE_HASHES.json').read_text('utf-8'))['files'].items():assert sha(ROOT/name)==sha(out/name)==digest,name
 for p in (ROOT/'scripts').glob('*v091*.py'):cp(p,'scripts/'+p.name)
 for p in (ROOT/'native_motion/sim/mode_a_v091').iterdir():cp(p,'native_motion/sim/mode_a_v091/'+p.name)
 coppelia_samples=0
 for i in range(3):
  for p in (P/f'bank{i}').iterdir():
   if p.is_file():cp(p,f'candidate/bank{i}/'+p.name)
  for wire,name in ((False,'COPPELIA_RESULT.json'),(True,'COPPELIA_WIRE_RESULT.json')):
   src=ROOT/'board_evidence'/f'mode_a_v091_coppelia_bank{i}_{"wire" if wire else "exact"}_a1/RESULT.json';r=json.loads(src.read_text('utf-8'))
   assert r['passed'] and r['collision_samples']==0 and r['native_plan_sha256']==sha(P/f'bank{i}/PLAN_NATIVE.json');coppelia_samples+=r['samples_checked'];cp(src,f'candidate/bank{i}/'+name)
 cp(P/'S4_BANKED_CANDIDATE.json','candidate/S4_BANKED_CANDIDATE.json')
 for p in REPLAY.iterdir():
  if p.is_file():cp(p,'cancel_replay/'+p.name)
 for wire,name in ((False,'COPPELIA_RESULT.json'),(True,'COPPELIA_WIRE_RESULT.json')):
  src=ROOT/'board_evidence'/f'mode_a_v091_return_{"wire" if wire else "exact"}_a1/RESULT.json';r=json.loads(src.read_text('utf-8'))
  assert r['passed'] and r['collision_samples']==0 and r['native_plan_sha256']==sha(REPLAY/'PLAN_NATIVE.json');coppelia_samples+=r['samples_checked'];cp(src,'cancel_replay/'+name)
 cp(P/'PATH_PLAN_CN.md','PATH_PLAN_CN.md')
 for p in (P/'figures').iterdir():cp(p,'figures/'+p.name)
 cp(ROOT/'docs/mode_a_v091/README_CN.md','README_CN.md')
 for n in ('CHANGE_SUMMARY.json','HARDWARE_REUSE.json'):cp(H/n,'evidence/'+n)
 for name in selected:
  for p in (ROOT/'board_evidence'/name).iterdir():
   if p.is_file() and p.suffix in ('.json','.txt','.mem','.sv','.f'):cp(p,'evidence/'+name+'/'+p.name)
 # All deployed FPGA/model inputs must retain the exact parent bytes.
 frozen={name:d for name,d in hashes.items() if name.startswith(('hardware/','model_package/','native_motion/rtl/','native_motion/constraints/'))}
 for name,d in frozen.items():assert sha(out/name)==d,name
 plan=json.loads((P/'bank1/PLAN_NATIVE.json').read_text('utf-8'));table=json.loads((P/'S4_BANKED_CANDIDATE.json').read_text('utf-8'))
 text,meta=generate(plan,table);(out/'scripts/mode_a_board_bridge.tcl').write_text(text,'utf-8');dump('evidence/BRIDGE_GENERATION.json',meta);dump('hand_map_uncalibrated_example.json',default_map())
 hw=json.loads((out/'evidence/IMPLEMENTATION_SUMMARY.json').read_text('utf-8'))
 summary=dict(result='V091_IMAGE_Y_DESK_Y_THREE_BANKS_PASS',version='0.9.1',parent_package_sha256=BASE_SHA,hardware_rebuilt=False,model_changed=False,frozen_parent_files=len(frozen),built_inputs_identical=74,pc_checks=34,terminal_checks=13,selected_task_regs_s2_runs=len(selected),s2_exact_samples=s2_samples,coppelia_samples=coppelia_samples,coppelia_collision_samples=0,execution_profile=profile(),bank_capacity=table['capacity'],align_n=table['align_n'],align_na=table['align_na'],utilization=hw['utilization'],timing_ns=hw['timing_ns'],inherited_timing_evidence='V090 same BIT/HWH/XSA and all74 build inputs; no new implementation',physical_hardware_test='NOT_RUN')
 dump('evidence/VERIFIED_SUMMARY.json',summary)
 source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 manifest=dict(version='0.9.1',hardware_version='0.9.0',task_abi=0x3407,arrival_policy='observe_all',source_commit=source,parent_package_sha256=BASE_SHA,execution_profile=profile(),physical_hardware_test='NOT_RUN',inputs={})
 for folder in ('scripts','ps','hardware','model_package','native_motion','planning','candidate','cancel_replay'):
  for p in (out/folder).rglob('*'):
   if p.is_file() and '__pycache__' not in p.parts:manifest['inputs'][p.relative_to(out).as_posix()]=sha(p)
 for name in ('BUILT_SOURCE_HASHES.json','IMPLEMENTATION_SUMMARY.json','VERIFIED_SUMMARY.json','HARDWARE_REUSE.json'):manifest['inputs']['evidence/'+name]=sha(out/'evidence'/name)
 dump('BOARD_MANIFEST.json',manifest)
 for script,expected,name in [('test_mode_a_v091.py',34,'PC_TESTS.txt'),('test_mode_a_terminal.py',13,'TERMINAL_TESTS.txt')]:
  r=subprocess.run([sys.executable,'-X','utf8','-B',str(out/'scripts'/script)],cwd=out,capture_output=True);txt=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/'evidence'/name).write_text(txt,'utf-8')
  if r.returncode or f'Ran {expected} tests' not in txt:raise RuntimeError(txt)
 replan=ROOT/'board_evidence/mode_a_v091_packaged_replan_a1'
 r=subprocess.run(['D:/RobotSim/.venv/Scripts/python.exe','-X','utf8','-B',str(out/'scripts/prepare_mode_a_v091.py'),'--out',str(replan)],cwd=out,capture_output=True)
 if r.returncode:raise RuntimeError((r.stdout+r.stderr).decode('utf-8',errors='replace'))
 names=['S4_BANKED_CANDIDATE.json',*[f'bank{i}/{n}' for i in range(3) for n in ('PLAN_NATIVE.json','S4_NATIVE_CANDIDATE.json','SCENE_PLAN.json','SUMMARY.json','PATH_PREVIEW.json','JOINT_TARGETS_NATIVE.csv')]]
 for n in names:assert sha(replan/n)==sha(out/'candidate'/n),n
 dump('evidence/REPRODUCTION.json',dict(passed=True,files={n:sha(replan/n) for n in names}))
 from check_mode_a_v091_package import check
 dump('evidence/PACKAGE_CHECK.json',check(out))
 files=sorted(p for p in out.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
 (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n' for p in files),'utf-8')
 files.append(out/'SHA256SUMS')
 with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in files:z.write(p,(Path(NAME)/p.relative_to(out)).as_posix())
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for p in files:assert hashlib.sha256(z.read((Path(NAME)/p.relative_to(out)).as_posix())).hexdigest()==sha(p),p
 result=dict(result='V091_COMPLETE_FROZEN_HW_REPLAN_SOURCE_SHA_CRC_PASS',directory=str(out),zip=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),files=len(files),source_commit=source,physical_hardware_test='NOT_RUN')
 (H/'PACKAGE_RESULT.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
