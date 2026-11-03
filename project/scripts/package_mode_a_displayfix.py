"""Seal v0131 display candidate from the exact verified v013 parent ZIP."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,zipfile
from check_mode_a_upgrade_package import check
ROOT=Path(__file__).resolve().parents[1]
D=Path('D:/FPGA_Projects/Gesture/deliverables')
BASE='Gesture_ModeA_FPGA_v0.13.0_20261028_ParallelHD_ContinuousSmooth_Final'
BASE_SHA='805fc1da0383e9c99c2b02d22931c7eb3f4b70b3bb3ad2e0682a5ffae8089173'
NAME='Gesture_ModeA_FPGA_v0.13.1_20261029_HDMI720p_DisplayFix_Final'
H=ROOT/'board_evidence/mode_a_hdmi_fix_a1'
I=ROOT/'board_evidence/mode_a_displayfix_impl_a2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 out=D/NAME;archive=D/(NAME+'.zip')
 if out.exists() or archive.exists():raise FileExistsError(out)
 assert sha(D/(BASE+'.zip'))==BASE_SHA
 hw=json.loads((I/'IMPLEMENTATION_SUMMARY.json').read_text('utf-8'))
 assert hw['version']=='0.13.1'
 out.mkdir()
 def cp(src,rel):
  p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,p);assert sha(src)==sha(p)
 def dump(rel,obj):
  p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n','utf-8')
 with zipfile.ZipFile(D/(BASE+'.zip')) as z:
  assert z.testzip() is None
  hashes={l.split('  ',1)[1]:l.split('  ',1)[0] for l in z.read(BASE+'/SHA256SUMS').decode().splitlines()}
  for rel,d in hashes.items():
   p=(out/rel).resolve();assert p.is_relative_to(out.resolve())
   data=z.read(BASE+'/'+rel);assert hashlib.sha256(data).hexdigest()==d
   p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 runtime=['run_mode_a_upgrade.py','check_mode_a_upgrade_package.py','test_mode_a_upgrade.py',
  'build_mode_a_displayfix.py','inspect_mode_a_displayfix.py','inspect_mode_a_displayfix_netlist.tcl',
  'summarize_mode_a_displayfix_impl.py','run_mode_a_tmds_raster.py','run_mode_a_upgrade_hdmi.py','package_mode_a_displayfix.py']
 for name in runtime:cp(ROOT/'scripts'/name,'scripts/'+name)
 for name in ['tb_serializer.sv','tb_tmds_raster.sv','tb_tmds_720p.sv','tb_canvas.sv']:cp(ROOT/'native_motion/sim/mode_a_hdmi'/name,'native_motion/sim/mode_a_hdmi/'+name)
 cp(ROOT/'native_motion/sim/mode_a_hdmi/tb_renderer.sv','native_motion/sim/mode_a_hdmi/tb_renderer.sv')
 cp(ROOT/'native_motion/sim/mode_a_upgrade/tb_renderer_hd.sv','native_motion/sim/mode_a_upgrade/tb_renderer_hd.sv')
 cp(ROOT/'native_motion/sim/mode_a_upgrade/tb_upgrade_final_top.sv','native_motion/sim/mode_a_upgrade/tb_upgrade_final_top.sv')
 binding=json.loads((I/'BUILT_SOURCE_HASHES.json').read_text('utf-8'))
 for rel,d in binding['files'].items():assert sha(ROOT/rel)==d;cp(ROOT/rel,rel)
 for n in ['BUILT_SOURCE_HASHES.json','BUILD_COMPLETED.json','IMPLEMENTATION_SUMMARY.json']:cp(I/n,'evidence/'+n)
 for p in (I/'implemented_reports').iterdir():
  if p.suffix in ('.bit','.hwh','.xsa'):cp(p,'hardware/'+p.name)
  elif p.is_file() and p.suffix in ('.rpt','.txt'):cp(p,'evidence/implemented_reports/'+p.name)
 for p in (I/'inspection_a1').iterdir():
  if p.is_file() and p.suffix in ('.rpt','.txt','.json'):cp(p,'evidence/inspection/'+p.name)
 tests={'display_serial':'mode_a_tmds_raster_hd720_a2','display_units':'mode_a_upgrade_hdmi_displayfix_a3',
  'display_integration':'mode_a_upgrade_integration_displayfix_a2','display_serializer':'mode_a_hdmi_serializer_displayfix_a1'}
 for key,folder in tests.items():
  src=ROOT/'board_evidence'/folder;r=json.loads((src/'RESULT.json').read_text('utf-8'));assert r['passed']
  for p in src.iterdir():
   if p.is_file() and p.suffix in ('.txt','.json'):cp(p,'evidence/'+key+'/'+p.name)
 cp(ROOT/'board_evidence/mode_a_tmds_raster_baseline_a1/receiver.rgb','evidence/display_baseline/receiver.rgb')
 cp(ROOT/'board_evidence/mode_a_tmds_raster_baseline_a1/RESULT.json','evidence/display_baseline/RESULT.json')
 cp(ROOT/'board_evidence/mode_a_legacy_clock_phase_a1/RESULT.json','evidence/display_baseline/LEGACY_CLOCK_PHASE.json')
 cp(H/'HDMI_PREVIEW.png','HDMI_PREVIEW.png')
 cp(ROOT/'docs/mode_a_displayfix_v0_13_1/README_CN.md','README_CN.md')
 cp(ROOT/'docs/mode_a_displayfix_v0_13_1/INTERFACE_CN.md','INTERFACE_CN.md')
 cp(H/'DIAGNOSIS.json','evidence/DISPLAY_DIAGNOSIS.json')
 cp(H/'BUILD_WARNING_REVIEW.json','evidence/BUILD_WARNING_REVIEW.json')
 # Prove that the display patch did not change any model, path or control RTL.
 frozen={r:d for r,d in hashes.items() if r.startswith(('model_package/','candidate/')) or (r.startswith('native_motion/rtl/') and not r.startswith('native_motion/rtl/hdmi/'))}
 for rel,d in frozen.items():assert sha(out/rel)==d,rel
 reuse=dict(result='V0131_MODEL_ALL_PATHS_AND_NON_HDMI_RTL_BYTE_IDENTICAL',parent_sha256=BASE_SHA,files=len(frozen),hashes=frozen)
 dump('evidence/CONTROL_MOTION_REUSE.json',reuse)
 (H/'CONTROL_MOTION_REUSE.json').write_text(json.dumps(reuse,indent=2)+'\n','utf-8')
 source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 summary=dict(result='V0131_HDMI720P_FULL_SERIAL_AND_INTEGRATION_PASS',version='0.13.1',source_commit=source,
  parent_package_sha256=BASE_SHA,output=[1280,720,60],logical_canvas=[640,480],physical_canvas=[160,0,960,720],
  model_changed=False,motion_rtl_changed=False,path_changed=False,resource_cap_percent=85,
  resource_percent=hw['resource_percent'],utilization=hw['utilization'],timing_ns=hw['timing_ns'],
  pc_tests=46,terminal_tests=13,serial_words=1237500,serial_exact_rgb_pixels=921600,
  display_test='NOT_RUN_ON_PHYSICAL_MONITOR',physical_hardware_test='NOT_RUN')
 dump('evidence/VERIFIED_SUMMARY.json',summary)
 old=json.loads((out/'BOARD_MANIFEST.json').read_text('utf-8'))
 old.update(version='0.13.1',hardware_version='0.13.1',source_commit=source,parent_package_sha256=BASE_SHA,
  display_output=[1280,720,60],physical_hardware_test='NOT_RUN')
 post={'BOARD_MANIFEST.json','SHA256SUMS','evidence/PACKAGE_CHECK.json','evidence/ENTRY_CHECK.txt',
  'evidence/PC_CONTROL_TESTS.txt','evidence/PC_OBSERVER_TESTS.txt','evidence/TERMINAL_TESTS.txt'}
 old['inputs']={p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.relative_to(out).as_posix() not in post and '__pycache__' not in p.parts}
 dump('BOARD_MANIFEST.json',old)
 for name,num,log in [('test_mode_a_upgrade.py',41,'PC_CONTROL_TESTS.txt'),('test_mode_a_upgrade_observer.py',5,'PC_OBSERVER_TESTS.txt'),('test_mode_a_terminal.py',13,'TERMINAL_TESTS.txt')]:
  r=subprocess.run([sys.executable,'-X','utf8','-B',str(out/'scripts'/name)],cwd=out,capture_output=True)
  text=r.stdout+r.stderr;(out/'evidence'/log).write_bytes(text)
  assert r.returncode==0 and f'Ran {num} tests' in text.decode('utf-8',errors='replace'),text.decode('utf-8',errors='replace')
 dump('evidence/PACKAGE_CHECK.json',check(out))
 r=subprocess.run([sys.executable,'-X','utf8','-B',str(out/'scripts/run_mode_a_upgrade.py'),'--check-only'],cwd=out,capture_output=True)
 (out/'evidence/ENTRY_CHECK.txt').write_bytes(r.stdout+r.stderr);assert r.returncode==0,(r.stdout+r.stderr)
 files=sorted(p for p in out.rglob('*') if p.is_file() and p!=out/'SHA256SUMS' and '__pycache__' not in p.parts)
 (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n' for p in files),'utf-8');files.append(out/'SHA256SUMS')
 with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in files:z.write(p,(Path(NAME)/p.relative_to(out)).as_posix())
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for p in files:assert hashlib.sha256(z.read((Path(NAME)/p.relative_to(out)).as_posix())).hexdigest()==sha(p)
 result=dict(result='V0131_FULL_PACKAGE_SOURCE_SHA_ZIP_CRC_PASS',directory=str(out),zip=str(archive),
  files=len(files),bytes=archive.stat().st_size,sha256=sha(archive),source_commit=source,physical_hardware_test='NOT_RUN')
 for name,obj in [('PACKAGE_RESULT.json',result),('VERIFIED_SUMMARY.json',summary)]:
  (H/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n','utf-8')
 shutil.copyfile(out/'evidence/PACKAGE_CHECK.json',H/'PACKAGE_CHECK.json');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
