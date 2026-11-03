"""Full 1.5x release using exact hardware/model/dependencies from sealed v080."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,zipfile
from mode_a_speed15_config import ROOT
from mode_a_speed15_profile import profile
from prepare_mode_a_speed15_bridge import generate

D=Path('D:/FPGA_Projects/Gesture/deliverables')
PARENT='Gesture_ModeA_FPGA_v0.8.0_20261027_BlindHandover'
PARENT_SHA='d59164f96edbf4603e415c85fd14d43a0f6326f087b726d9fe3ec4689dcbd09c'
NAME='Gesture_ModeA_FPGA_v0.8.1_20261027_Speed1p5'
H=ROOT/'board_evidence/mode_a_speed15_v081_a1';P=ROOT/'board_evidence/mode_a_speed15_v081_plan_a1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base-zip',type=Path,default=D/(PARENT+'.zip'))
    ap.add_argument('--out',type=Path,default=D/NAME);a=ap.parse_args();out=a.out.resolve();archive=Path(str(out)+'.zip')
    if out.exists() or archive.exists():raise FileExistsError('Preserve previous release '+str(out))
    if sha(a.base_zip)!=PARENT_SHA:raise ValueError('Frozen v080 archive changed')
    out.mkdir(parents=True)
    def write(rel,data):
        p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2)+'\n','utf-8')
    def cp(src,rel):
        p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,p)
        if sha(src)!=sha(p):raise ValueError('Copy '+rel)
    with zipfile.ZipFile(a.base_zip) as z:
        if z.testzip():raise ValueError('Parent ZIP CRC')
        prefix=PARENT+'/';rows=z.read(prefix+'SHA256SUMS').decode('utf-8').splitlines()
        hashes={r.split('  ',1)[1]:r.split('  ',1)[0] for r in rows}
        parent=json.loads(z.read(prefix+'BOARD_MANIFEST.json'))
        for name,digest in hashes.items():
            if name=='BOARD_MANIFEST.json':continue
            rel='evidence/v080/'+name[len('evidence/'):] if name.startswith('evidence/') else name
            p=(out/rel).resolve()
            if not p.is_relative_to(out) or 'LOCAL' in name or name.startswith('runs/'):raise ValueError('Unsafe member '+name)
            data=z.read(prefix+name)
            if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Parent member '+name)
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    write('evidence/V080_BOARD_MANIFEST.json',parent)
    for name in ('BUILT_SOURCE_HASHES.json','IMPLEMENTATION_SUMMARY.json'):
        cp(out/'evidence/v080'/name,'evidence/'+name)
    binding=json.loads((out/'evidence/BUILT_SOURCE_HASHES.json').read_text('utf-8'))
    for name,digest in binding['files'].items():
        if sha(ROOT/name)!=digest or sha(out/name)!=digest:raise ValueError('Hardware source changed '+name)
    scripts=['mode_a_speed15_profile.py','mode_a_speed15_config.py','prepare_mode_a_speed15_v081.py',
        'prepare_mode_a_speed15_bridge.py','run_mode_a_speed15_v081.py','check_mode_a_speed15_package.py',
        'test_mode_a_speed15_v081.py','run_mode_a_speed15_uart_xsim.py','run_mode_a_speed15_s2_xsim.py',
        'package_mode_a_speed15_v081.py','write_mode_a_path_report.py']
    for name in scripts:cp(ROOT/'scripts'/name,'scripts/'+name)
    for p in P.iterdir():
        if p.is_file() and (p.suffix=='.json' or p.name=='JOINT_TARGETS_NATIVE.csv'):cp(p,'candidate/'+p.name)
    for folder,name in [('mode_a_speed15_v081_coppelia_a2','COPPELIA_RESULT.json'),('mode_a_speed15_v081_wire_coppelia_a1','COPPELIA_WIRE_RESULT.json')]:
        src=ROOT/'board_evidence'/folder/'RESULT.json';d=json.loads(src.read_text('utf-8'))
        assert d['passed'] and d['samples_checked']==11595 and d['collision_samples']==0 and d['native_plan_sha256']==sha(P/'PLAN_NATIVE.json')
        cp(src,'candidate/'+name)
    cp(ROOT/'docs/mode_a_speed15_v0_8_1/README_CN.md','README_CN.md');cp(P/'PATH_PLAN_CN.md','PATH_PLAN_CN.md')
    for p in (P/'figures').iterdir():
        if p.is_file():cp(p,'figures/'+p.name)
    for name in ('SPEED_CHANGE_SUMMARY.json','BASELINE_FIELD_SUMMARY.json','COPPELIA_SUMMARY.json','COPPELIA_WIRE_SUMMARY.json','DEVELOPMENT_ATTEMPTS.json'):
        cp(H/name,'evidence/'+name)
    for folder,key in [('mode_a_speed15_s2_xsim_a1','SPEED15_S2'),('mode_a_speed15_uart_xsim_a1','SPEED15_UART')]:
        src=ROOT/'board_evidence'/folder;d=json.loads((src/'RESULT.json').read_text('utf-8'));assert d['passed']
        cp(src/'RESULT.json','evidence/XSIM_'+key+'.json')
        for p in src.iterdir():
            if p.is_file() and p.suffix in ('.sv','.txt','.mem','.f'):cp(p,'evidence/'+key+'/'+p.name)
    frozen={}
    for folder in ('hardware','model_package','native_motion/rtl','native_motion/constraints','planning'):
        for p in (out/folder).rglob('*'):
            if p.is_file():frozen[p.relative_to(out).as_posix()]=sha(p)
    if any(hashes.get(name)!=digest for name,digest in frozen.items()):raise ValueError('Frozen model/hardware/layout changed')
    plan=json.loads((P/'PLAN_NATIVE.json').read_text('utf-8'));table=json.loads((P/'S4_NATIVE_CANDIDATE.json').read_text('utf-8'))
    text,meta=generate(plan,table);(out/'scripts/mode_a_board_bridge.tcl').write_text(text,'utf-8');write('evidence/BRIDGE_GENERATION.json',meta)
    summary=dict(result='V081_SPEED15_PC_RTL_COPPELIA_AND_FROZEN_HARDWARE_PASS',version='0.8.1',baseline_version='0.8.0',
        baseline_operator_report='TEST_PASSED',parent_sha256=PARENT_SHA,hardware_rebuilt=False,model_changed=False,
        frozen_file_count=len(frozen),hardware_built_inputs=70,pc_checks=25,terminal_checks=13,new_passed_xsim_runs=2,
        actual_coppelia_samples=23190,s2_rtl_exact_samples=11595,profile=profile(),physical_v081='NOT_RUN')
    write('evidence/SPEED15_VERIFIED_SUMMARY.json',summary)
    manifest=dict(parent,version='0.8.1',hardware_version='0.8.0',source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        parent_package_sha256=PARENT_SHA,execution_profile=profile(),pc_checks=25,terminal_regression_checks=13,
        selected_passed_xsim_runs=2,inherited_passed_xsim_runs=parent['selected_passed_xsim_runs'],actual_coppelia_samples=23190,
        additional_empty_hand_startup_samples=0,physical_hardware_test='NOT_RUN',speed_change=summary,inputs={})
    for rel in parent['inputs']:
        if (out/rel).is_file():manifest['inputs'][rel]=sha(out/rel)
    for folder in ('candidate','hardware'):
        for p in (out/folder).iterdir():
            if p.is_file():manifest['inputs'][p.relative_to(out).as_posix()]=sha(p)
    for name in [*['scripts/'+n for n in scripts],'scripts/mode_a_board_bridge.tcl']:
        manifest['inputs'][name]=sha(out/name)
    write('BOARD_MANIFEST.json',manifest)
    for script,log,expected in [('test_mode_a_speed15_v081.py','PC_TESTS.txt',25),('test_mode_a_terminal.py','TERMINAL_TESTS.txt',13)]:
        r=subprocess.run([sys.executable,'-X','utf8','-E','-B',str(out/'scripts'/script)],cwd=out,capture_output=True)
        t=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/'evidence'/log).write_text(t,'utf-8')
        if r.returncode or f'Ran {expected} tests' not in t:raise RuntimeError(t)
    replan=ROOT/'board_evidence/mode_a_speed15_packaged_replan_a1'
    r=subprocess.run(['D:/RobotSim/.venv/Scripts/python.exe','-E','-B',str(out/'scripts/prepare_mode_a_speed15_v081.py'),'--out',str(replan)],cwd=out,capture_output=True)
    if r.returncode or any(sha(replan/n)!=sha(P/n) for n in ('PLAN_NATIVE.json','S4_NATIVE_CANDIDATE.json')):raise RuntimeError('Replan '+(r.stdout+r.stderr).decode('utf-8',errors='replace'))
    write('evidence/REPRODUCTION.json',dict(result='PACKAGED_PLAN_AND_S4_TABLE_BYTE_IDENTICAL',native_plan_sha256=sha(P/'PLAN_NATIVE.json'),table_sha256=sha(P/'S4_NATIVE_CANDIDATE.json')))
    files=sorted(p for p in out.rglob('*') if p.is_file())
    (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n' for p in files),'utf-8')
    r=subprocess.run([sys.executable,'-E','-B',str(out/'scripts/run_mode_a_speed15_v081.py'),'--check-only'],cwd=out,capture_output=True)
    if r.returncode:raise RuntimeError((r.stdout+r.stderr).decode('utf-8',errors='replace'))
    print(r.stdout.decode('utf-8',errors='replace'),flush=True)
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():z.write(p,(Path(out.name)/p.relative_to(out)).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise ValueError('ZIP CRC')
        for p in out.rglob('*'):
            if p.is_file() and hashlib.sha256(z.read((Path(out.name)/p.relative_to(out)).as_posix())).hexdigest()!=sha(p):raise ValueError('ZIP member SHA')
    result=dict(result='V081_SPEED15_PACKAGE_SOURCE_MODEL_XSA_REPLAN_SHA_CRC_PASS',directory=str(out),zip=str(archive),bytes=archive.stat().st_size,
        sha256=sha(archive),files=sum(p.is_file() for p in out.rglob('*')),source_commit=manifest['source_commit'],checks=summary,physical_test='NOT_RUN')
    (H/'PACKAGE_RESULT.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
