"""Complete v014 from verified v0131, preserving frozen normal plans/models."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,zipfile
from check_mode_a_restock_package import check
from prepare_mode_a_restock_bridge import generate
from mode_a_restock_config import load_restock,profile
ROOT=Path(__file__).resolve().parents[1];D=Path('D:/FPGA_Projects/Gesture/deliverables')
BASE='Gesture_ModeA_FPGA_v0.13.1_20261029_HDMI720p_DisplayFix_Final'
BASE_SHA='5648c8978f7be9f3dd0961866af96081795d21da34eea7dbb4b9cc38c58fecf4'
NAME='Gesture_ModeA_FPGA_v0.14.0_20261029_AutoRestock_Final'
H=ROOT/'board_evidence/mode_a_restock_a1';I=ROOT/'board_evidence/mode_a_restock_impl_a2';P=ROOT/'board_evidence/mode_a_restock_plan_a2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 out=D/NAME;archive=D/(NAME+'.zip')
 if out.exists() or archive.exists():raise FileExistsError(out)
 assert sha(D/(BASE+'.zip'))==BASE_SHA
 hw=json.loads((I/'IMPLEMENTATION_SUMMARY.json').read_text('utf-8'));assert hw['version']=='0.14.0'
 out.mkdir()
 def cp(src,rel):
  p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,p);assert sha(src)==sha(p)
 def dump(rel,obj):
  p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n','utf-8')
 with zipfile.ZipFile(D/(BASE+'.zip')) as z:
  assert z.testzip() is None
  hashes={l.split('  ',1)[1]:l.split('  ',1)[0] for l in z.read(BASE+'/SHA256SUMS').decode().splitlines()}
  for rel,d in hashes.items():
   # Keep inherited RTL evidence labelled as the actual tested baseline.
   target=rel
   if rel.startswith('evidence/') and not rel.startswith(('evidence/hdmi_fixtures/','evidence/continuous/','evidence/display_baseline/')):
    target='evidence/v0131_baseline/'+rel[len('evidence/'):]
   p=(out/target).resolve();assert p.is_relative_to(out.resolve());data=z.read(BASE+'/'+rel);assert hashlib.sha256(data).hexdigest()==d
   p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 for p in (ROOT/'scripts').glob('*restock*.py'):cp(p,'scripts/'+p.name)
 cp(ROOT/'scripts/inspect_mode_a_restock_netlist.tcl','scripts/inspect_mode_a_restock_netlist.tcl')
 for p in (ROOT/'native_motion/sim/mode_a_restock').iterdir():
  if p.is_file():cp(p,'native_motion/sim/mode_a_restock/'+p.name)
 cp(ROOT/'native_motion/sim/mode_a_upgrade/tb_renderer_hd.sv','native_motion/sim/mode_a_upgrade/tb_renderer_hd.sv')
 for p in P.iterdir():
  if p.is_file():cp(p,'candidate/restock/'+p.name)
 for kind,name in [('exact','COPPELIA_RESULT.json'),('wire','COPPELIA_WIRE_RESULT.json')]:
  cp(ROOT/f'board_evidence/mode_a_restock_coppelia_{kind}_a1/RESULT.json','candidate/restock/'+name)
 for name in ('README_CN.md','INTERFACE_CN.md','RESTOCK_PATH_CN.md'):
  cp(ROOT/'docs/mode_a_restock_v0_14_0'/name,name)
 cp(H/'JOINT_TARGETS_RESTOCK.csv','JOINT_TARGETS_RESTOCK.csv')
 for name in ('CURRENT_PROJECT_CONTEXT.md','PROJECT_LOG.md'):cp(ROOT/name,name)
 for p in (ROOT/'docs/mode_a_restock_v0_14_0').iterdir():
  if p.is_file():cp(p,'docs/mode_a_restock_v0_14_0/'+p.name)
 for name in ('RESOURCE_BUDGET.json','HDMI_REUSE.json','BUILD_WARNING_REVIEW.json','REPLAN_REPRODUCIBILITY.json','TRACE_REUSE.json','SOURCE_PC_TESTS.json','VALIDATED_OFFLINE.json'):cp(H/name,'evidence/'+name)
 for p in (ROOT/'board_evidence/mode_a_restock_replay_a1').iterdir():
  if p.is_file():cp(p,'evidence/restock_replay/'+p.name)
 cp(ROOT/'board_evidence/mode_a_restock_task_a5/motion_trace.txt','evidence/restock_replay/S4_MOTION_TRACE.txt')
 for kind in ('exact','wire'):cp(ROOT/f'board_evidence/mode_a_restock_replay_coppelia_{kind}_a1/RESULT.json','evidence/restock_replay/COPPELIA_'+kind.upper()+'.json')
 proofs={'restock_core':'mode_a_restock_task_a5','restock_s2':'mode_a_restock_s2_xsim_a1',
  'restock_hdmi':'mode_a_upgrade_hdmi_restock_a1','restock_integration':'mode_a_restock_integration_a4','legacy_s4':'mode_a_upgrade_task_restock_legacy_a2'}
 for key,folder in proofs.items():
  src=ROOT/'board_evidence'/folder;r=json.loads((src/'RESULT.json').read_text('utf-8'));assert r['passed']
  for p in src.iterdir():
   if p.is_file() and p.suffix in ('.json','.txt'):cp(p,'evidence/'+key+'/'+p.name)
 cp(ROOT/'board_evidence/mode_a_upgrade_task_restock_legacy_a2/tb_continuous_task.sv','board_evidence/mode_a_upgrade_task_restock_legacy_a2/tb_continuous_task.sv')
 cp(ROOT/'board_evidence/mode_a_restock_s2_xsim_a1/tb_speed15_s2.sv','evidence/restock_s2/tb_speed15_s2.sv')
 binding=json.loads((I/'BUILT_SOURCE_HASHES.json').read_text('utf-8'))
 for rel,d in binding['files'].items():assert sha(ROOT/rel)==d;cp(ROOT/rel,rel)
 for n in ('BUILT_SOURCE_HASHES.json','BUILD_COMPLETED.json','IMPLEMENTATION_SUMMARY.json'):cp(I/n,'evidence/'+n)
 for p in (I/'implemented_reports').iterdir():
  if p.suffix in ('.bit','.hwh','.xsa'):cp(p,'hardware/'+p.name)
  elif p.is_file() and p.suffix in ('.rpt','.txt'):cp(p,'evidence/implemented_reports/'+p.name)
 for p in (I/'inspection_a1').iterdir():
  if p.is_file() and p.suffix in ('.rpt','.txt','.json'):cp(p,'evidence/inspection/'+p.name)
 changed={'native_motion/rtl/'+p for p in ('robot/s4_task_fsm.v','robot/s4_task_regs.v','robot/phase3_s4_task_top.v','integration/phase3_roarm_closed_loop_top.v','hdmi/mode_a_renderer.v','hdmi/mode_a_font.mem','hdmi/mode_a_ui_text.vh')}
 frozen={r:d for r,d in hashes.items() if r.startswith(('model_package/','candidate/')) or (r.startswith('native_motion/rtl/') and r not in changed)}
 for rel,d in frozen.items():assert sha(out/rel)==d,rel
 reuse=dict(result='V0131_MODEL_NORMAL_PLANS_AND_EXECUTION_ENGINES_BYTE_IDENTICAL',files=len(frozen),changed_rtl=sorted(changed),hashes=frozen)
 dump('evidence/BASELINE_REUSE.json',reuse);(H/'BASELINE_REUSE.json').write_text(json.dumps(reuse,indent=2)+'\n','utf-8')
 plan=json.loads((out/'candidate/bank1/PLAN_NATIVE.json').read_text('utf-8'));table=json.loads((out/'candidate/S4_BANKED_CANDIDATE.json').read_text('utf-8'))
 table['restock']=load_restock(out);table['abi']['task']=0x340b
 text,meta=generate(plan,table);(out/'scripts/mode_a_board_bridge.tcl').write_text(text,'utf-8');dump('evidence/BRIDGE_GENERATION.json',meta)
 source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 summary=dict(result='V014_AUTO_RESTOCK_OFFLINE_PASS',version='0.14.0',source_commit=source,parent_package_sha256=BASE_SHA,
  pickup_D_mm=[300,200,15],restock_keypoints=46,restock_segments=51,core_cases=7,pc_tests=57,terminal_tests=13,
  nominal_coppelia_samples=136310,actual_s4_s2_legs=176,actual_s4_s2_samples=8776,actual_replay_coppelia_samples=17552,
  model_changed=False,normal_path_changed=False,planner_uart_changed=False,resource_cap_percent=85,
  utilization=hw['utilization'],resource_percent=hw['resource_percent'],timing_ns=hw['timing_ns'],profile=profile(),
  production_vga_frames=12,physical_hardware_test='NOT_RUN')
 dump('evidence/VERIFIED_SUMMARY.json',summary)
 old=json.loads((out/'BOARD_MANIFEST.json').read_text('utf-8'))
 old.update(version='0.14.0',hardware_version='0.14.0',task_abi=0x340b,source_commit=source,parent_package_sha256=BASE_SHA,
  execution_profile=profile(),empty_slot_action='AUTO_RESTOCK_FROM_PUBLIC_PICKUP',public_pickup_D_mm=[300,200,15],physical_hardware_test='NOT_RUN')
 post={'BOARD_MANIFEST.json','SHA256SUMS','evidence/PACKAGE_CHECK.json','evidence/ENTRY_CHECK.txt','evidence/PC_CONTROL_TESTS.txt','evidence/PC_OBSERVER_TESTS.txt','evidence/TERMINAL_TESTS.txt','evidence/PC_RESTOCK_TESTS.txt'}
 old['inputs']={p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.relative_to(out).as_posix() not in post and '__pycache__' not in p.parts}
 dump('BOARD_MANIFEST.json',old)
 for name,num,log in [('test_mode_a_upgrade.py',41,'PC_CONTROL_TESTS.txt'),('test_mode_a_upgrade_observer.py',5,'PC_OBSERVER_TESTS.txt'),('test_mode_a_terminal.py',13,'TERMINAL_TESTS.txt'),('test_mode_a_restock.py',11,'PC_RESTOCK_TESTS.txt')]:
  r=subprocess.run([sys.executable,'-X','utf8','-B',str(out/'scripts'/name)],cwd=out,capture_output=True);text=r.stdout+r.stderr
  (out/'evidence'/log).write_bytes(text);assert r.returncode==0 and f'Ran {num} tests' in text.decode('utf-8',errors='replace'),text.decode('utf-8',errors='replace')
 dump('evidence/PACKAGE_CHECK.json',check(out))
 r=subprocess.run([sys.executable,'-X','utf8','-B',str(out/'scripts/run_mode_a_restock.py'),'--check-only'],cwd=out,capture_output=True)
 (out/'evidence/ENTRY_CHECK.txt').write_bytes(r.stdout+r.stderr);assert r.returncode==0,(r.stdout+r.stderr)
 files=sorted(p for p in out.rglob('*') if p.is_file() and p!=out/'SHA256SUMS' and '__pycache__' not in p.parts)
 (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n' for p in files),'utf-8');files.append(out/'SHA256SUMS')
 with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in files:z.write(p,(Path(NAME)/p.relative_to(out)).as_posix())
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for p in files:assert hashlib.sha256(z.read((Path(NAME)/p.relative_to(out)).as_posix())).hexdigest()==sha(p)
 result=dict(result='V014_COMPLETE_PACKAGE_CHECK_SOURCE_SHA_AND_ZIP_CRC_PASS',directory=str(out),zip=str(archive),files=len(files),bytes=archive.stat().st_size,sha256=sha(archive),source_commit=source,physical_hardware_test='NOT_RUN')
 for name,obj in [('PACKAGE_RESULT.json',result),('VERIFIED_SUMMARY.json',summary)]:
  (H/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n','utf-8')
 shutil.copyfile(out/'evidence/PACKAGE_CHECK.json',H/'PACKAGE_CHECK.json');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
