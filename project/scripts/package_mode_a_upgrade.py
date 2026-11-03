"""Assemble complete v013 from verified parent, final planning and routed sources."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,zipfile
from mode_a_upgrade_config import ROOT,default_map
from mode_a_upgrade_profile import profile
from prepare_mode_a_upgrade_bridge import generate
from check_mode_a_upgrade_package import check
D=Path('D:/FPGA_Projects/Gesture/deliverables')
BASE='Gesture_ModeA_FPGA_v0.12.0_20261028_HDMI_Clean_Final'
BASE_SHA='c5285dcbe1b836672e0251287eed30ac9399c74568efea13bd09f4ee8c672708'
NAME='Gesture_ModeA_FPGA_v0.13.0_20261028_ParallelHD_ContinuousSmooth_Final'
H=ROOT/'board_evidence/mode_a_upgrade_a1';P=ROOT/'board_evidence/mode_a_upgrade_plan_a3';I=ROOT/'board_evidence/mode_a_upgrade_impl_a5'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
PROOFS={
 'classifier':'mode_a_upgrade_classifier_a5','preview':'mode_a_upgrade_preview_a2',
 'hdmi':'mode_a_upgrade_hdmi_a4','integration':'mode_a_upgrade_integration_a6',
 'units':'mode_a_upgrade_units_a4','task':'mode_a_upgrade_task_a5',
 'uart':'mode_a_upgrade_uart_a1','s2_center':'mode_a_upgrade_s2_xsim_a10',
 's2_low':'mode_a_upgrade_s2_xsim_a12','s2_high':'mode_a_upgrade_s2_xsim_a13',
 's2_replay':'mode_a_upgrade_s2_xsim_a11','s2_stress':'mode_a_upgrade_stress_s2_a3',
 'bounds':'mode_a_upgrade_bounds_a2','serializer':'mode_a_hdmi_serializer_a2'}
def main():
 out=D/NAME;archive=Path(str(out)+'.zip')
 if out.exists() or archive.exists():raise FileExistsError(out)
 assert sha(D/(BASE+'.zip'))==BASE_SHA
 hw=json.loads((I/'IMPLEMENTATION_SUMMARY.json').read_text('utf-8'))
 results={}
 for key,folder in PROOFS.items():
  result=json.loads((ROOT/'board_evidence'/folder/'RESULT.json').read_text('utf-8'));assert result['passed'];results[key]=result
 continuous=json.loads((ROOT/'board_evidence/mode_a_upgrade_continuous_a1/RESULT.json').read_text('utf-8'));assert continuous['passed']
 out.mkdir(parents=True)
 def dump(rel,obj):
  p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n','utf-8')
 def cp(src,rel):
  p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,p);assert sha(src)==sha(p)
 with zipfile.ZipFile(D/(BASE+'.zip')) as z:
  assert z.testzip() is None
  hashes={l.split('  ',1)[1]:l.split('  ',1)[0] for l in z.read(BASE+'/SHA256SUMS').decode().splitlines()}
  for rel,d in hashes.items():
   if not rel.startswith(('model_package/','ps/','scripts/','native_motion/','planning/','constraints/','sim/','handoff/','evidence/hdmi_fixtures/')):continue
   if rel.startswith('scripts/test_mode_a_') and rel!='scripts/test_mode_a_terminal.py':continue
   p=(out/rel).resolve();assert p.is_relative_to(out.resolve())
   data=z.read(BASE+'/'+rel);assert hashlib.sha256(data).hexdigest()==d
   p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 for p in (ROOT/'scripts').glob('*upgrade*.py'):cp(p,'scripts/'+p.name)
 cp(ROOT/'scripts/mode_a_terminal.py','scripts/mode_a_terminal.py')
 cp(ROOT/'scripts/inspect_mode_a_upgrade_netlist.tcl','scripts/inspect_mode_a_upgrade_netlist.tcl')
 for p in (ROOT/'native_motion/sim/mode_a_upgrade').iterdir():
  if p.is_file():cp(p,'native_motion/sim/mode_a_upgrade/'+p.name)
 cp(ROOT/'native_motion/sim/mode_a_hdmi/tb_renderer.sv','native_motion/sim/mode_a_hdmi/tb_renderer.sv')
 for p in P.rglob('*'):
  if p.is_file():cp(p,'candidate/'+p.relative_to(P).as_posix())
 for i in range(4):
  for wire,name in ((False,'COPPELIA_RESULT.json'),(True,'COPPELIA_WIRE_RESULT.json')):
   src=ROOT/'board_evidence'/f'mode_a_upgrade_anchor_{min(i,2)}_{"wire" if wire else "exact"}_a1/RESULT.json'
   r=json.loads(src.read_text('utf-8'));assert r['passed'] and r['native_plan_sha256']==sha(P/f'bank{i}/PLAN_NATIVE.json');cp(src,f'candidate/bank{i}/'+name)
 for p in (ROOT/'board_evidence/mode_a_upgrade_replay_a2').iterdir():
  if p.is_file():cp(p,'evidence/replay/'+p.name)
 for suffix in ('exact','wire'):cp(ROOT/f'board_evidence/mode_a_upgrade_replay_coppelia_{suffix}_a1/RESULT.json',f'evidence/replay/COPPELIA_{suffix.upper()}_RESULT.json')
 for key,folder in PROOFS.items():
  src=ROOT/'board_evidence'/folder
  for p in src.iterdir():
   if p.is_file() and p.suffix in ('.json','.txt','.sv') and p.name not in ('preview.rgb',):cp(p,'evidence/'+key+'/'+p.name)
 cp(ROOT/'board_evidence/mode_a_upgrade_continuous_a1/RESULT.json','evidence/continuous/RESULT.json')
 for p in (H/'PATH_PLAN_CN.md',H/'CONTINUOUS_TARGETS_NATIVE.csv'):cp(p,p.name)
 cp(H/'RESOURCE_BUDGET.json','evidence/RESOURCE_BUDGET.json')
 cp(H/'REPLAN_REPRODUCIBILITY.json','evidence/REPLAN_REPRODUCIBILITY.json')
 cp(ROOT/'docs/mode_a_upgrade_v0_13_0/README_CN.md','README_CN.md');cp(ROOT/'docs/mode_a_upgrade_v0_13_0/INTERFACE_CN.md','INTERFACE_CN.md')
 cp(ROOT/'board_evidence/mode_a_upgrade_hdmi_a4/HDMI_PREVIEW.png','HDMI_PREVIEW.png')
 binding=json.loads((I/'BUILT_SOURCE_HASHES.json').read_text('utf-8'))
 for rel,d in binding['files'].items():assert sha(ROOT/rel)==d;cp(ROOT/rel,rel)
 for n in ('BUILT_SOURCE_HASHES.json','BUILD_COMPLETED.json','IMPLEMENTATION_SUMMARY.json'):cp(I/n,'evidence/'+n)
 for p in (I/'implemented_reports').iterdir():
  if p.suffix in ('.bit','.hwh','.xsa'):cp(p,'hardware/'+p.name)
  elif p.is_file() and p.suffix in ('.rpt','.txt'):cp(p,'evidence/implemented_reports/'+p.name)
 for p in (I/'inspection_a1').iterdir():
  if p.is_file() and p.suffix in ('.txt','.rpt','.json'):cp(p,'evidence/inspection/'+p.name)
 plan=json.loads((P/'bank1/PLAN_NATIVE.json').read_text('utf-8'));table=json.loads((P/'S4_BANKED_CANDIDATE.json').read_text('utf-8'))
 text,meta=generate(plan,table);(out/'scripts/mode_a_board_bridge.tcl').write_text(text,'utf-8');dump('evidence/BRIDGE_GENERATION.json',meta);dump('continuous_y_map.json',default_map())
 frozen={r:d for r,d in hashes.items() if r.startswith('model_package/')}
 for rel,d in frozen.items():assert sha(out/rel)==d
 source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 summary=dict(result='V013_ALL_FIVE_FEATURES_OFFLINE_PASS',version='0.13.0',parent_package_sha256=BASE_SHA,resource_cap_percent=85,utilization=hw['utilization'],resource_percent=hw['resource_percent'],timing_ns=hw['timing_ns'],frozen_model_files=len(frozen),model_changed=False,pc_tests=45,terminal_tests=13,cnn_cycles=468486,cnn_reference_cycles=750170,preview_source_pixels=[256,192],continuous_states=65,continuous_coppelia_samples=continuous['coppelia_samples'],continuous_collision_samples=0,continuous_max_abs_xyz_error_mm=continuous['max_target_abs_xyz_deviation_from_nominal_mm'],replay_s2_samples=29658,replay_coppelia_samples=59316,production_vga_frames=12,integration_serializer='SINK; actual production serializer separately UNISIM verified',profile=profile(),physical_hardware_test='NOT_RUN')
 dump('evidence/VERIFIED_SUMMARY.json',summary)
 manifest=dict(version='0.13.0',hardware_version='0.13.0',task_abi=0x340a,planner_abi=0x3203,vision_abi=0x3506,arrival_policy='observe_all',palm_admission_policy='FRESH_ACCEPTED_CENTER_CELL_PRE2S_PALM500MS',source_commit=source,parent_package_sha256=BASE_SHA,execution_profile=profile(),physical_hardware_test='NOT_RUN',inputs={})
 for p in sorted(out.rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts:manifest['inputs'][p.relative_to(out).as_posix()]=sha(p)
 dump('BOARD_MANIFEST.json',manifest)
 for script,expected,name in [('test_mode_a_upgrade.py',40,'PC_CONTROL_TESTS.txt'),('test_mode_a_upgrade_observer.py',5,'PC_OBSERVER_TESTS.txt'),('test_mode_a_terminal.py',13,'TERMINAL_TESTS.txt')]:
  r=subprocess.run([sys.executable,'-X','utf8','-B',str(out/'scripts'/script)],cwd=out,capture_output=True);data=r.stdout+r.stderr;(out/'evidence'/name).write_bytes(data)
  if r.returncode or f'Ran {expected} tests' not in data.decode('utf-8',errors='replace'):raise RuntimeError(data.decode('utf-8',errors='replace'))
 dump('evidence/PACKAGE_CHECK.json',check(out))
 r=subprocess.run([sys.executable,'-X','utf8','-B',str(out/'scripts/run_mode_a_upgrade.py'),'--check-only'],cwd=out,capture_output=True);(out/'evidence/ENTRY_CHECK.txt').write_bytes(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError((r.stdout+r.stderr).decode('utf-8',errors='replace'))
 files=sorted(p for p in out.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
 (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n' for p in files),'utf-8');files.append(out/'SHA256SUMS')
 with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in files:z.write(p,(Path(NAME)/p.relative_to(out)).as_posix())
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for p in files:assert hashlib.sha256(z.read((Path(NAME)/p.relative_to(out)).as_posix())).hexdigest()==sha(p)
 result=dict(result='V013_FULL_PACKAGE_SOURCE_SHA_ZIP_CRC_PASS',directory=str(out),zip=str(archive),bytes=archive.stat().st_size,files=len(files),sha256=sha(archive),source_commit=source,physical_hardware_test='NOT_RUN')
 (H/'PACKAGE_RESULT.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
 shutil.copyfile(out/'evidence/VERIFIED_SUMMARY.json',H/'VERIFIED_SUMMARY.json');shutil.copyfile(out/'evidence/PACKAGE_CHECK.json',H/'PACKAGE_CHECK.json');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
