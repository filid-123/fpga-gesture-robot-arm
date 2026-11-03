"""PRE shift and return-to-slot release; frozen v081 hardware/model dependencies."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,zipfile
from mode_a_cancel_shift_config import ROOT
from mode_a_cancel_shift_profile import profile
from prepare_mode_a_cancel_shift_bridge import generate

D=Path('D:/FPGA_Projects/Gesture/deliverables')
PARENT='Gesture_ModeA_FPGA_v0.8.1_20261027_Speed1p5'
PARENT_SHA='8d2f39507732bb96a031bbc989e10203b7b9f5a49696dfc3566fc28f6d987f03'
NAME='Gesture_ModeA_FPGA_v0.8.2_20261028_CancelReturn_PRE320'
H=ROOT/'board_evidence/mode_a_cancel_shift_v082_a1';P=ROOT/'board_evidence/mode_a_cancel_shift_v082_plan_a1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base-zip',type=Path,default=D/(PARENT+'.zip'))
    ap.add_argument('--out',type=Path,default=D/NAME);a=ap.parse_args();out=a.out.resolve();archive=Path(str(out)+'.zip')
    if out.exists() or archive.exists():raise FileExistsError('Preserve previous release '+str(out))
    if sha(a.base_zip)!=PARENT_SHA:raise ValueError('Frozen v081 archive changed')
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
            rel='evidence/v081/'+name[len('evidence/'):] if name.startswith('evidence/') else name
            p=(out/rel).resolve()
            if not p.is_relative_to(out) or 'LOCAL' in name or name.startswith('runs/'):raise ValueError('Unsafe member '+name)
            data=z.read(prefix+name)
            if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Parent member '+name)
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    write('evidence/V081_BOARD_MANIFEST.json',parent)
    for name in ('BUILT_SOURCE_HASHES.json','IMPLEMENTATION_SUMMARY.json'):
        cp(out/'evidence/v081'/name,'evidence/'+name)
    binding=json.loads((out/'evidence/BUILT_SOURCE_HASHES.json').read_text('utf-8'))
    for name,digest in binding['files'].items():
        if sha(ROOT/name)!=digest or sha(out/name)!=digest:raise ValueError('Hardware source changed '+name)
    scripts=['mode_a_cancel_shift_profile.py','mode_a_cancel_shift_config.py','prepare_mode_a_cancel_shift_v082.py',
        'prepare_mode_a_cancel_shift_bridge.py','run_mode_a_cancel_shift_v082.py','check_mode_a_cancel_shift_package.py',
        'test_mode_a_cancel_shift_v082.py','export_mode_a_cancel_replay.py','run_mode_a_cancel_return_xsim.py','run_mode_a_cancel_shift_s2_xsim.py',
        'package_mode_a_cancel_shift_v082.py','write_mode_a_path_report.py']
    for name in scripts:cp(ROOT/'scripts'/name,'scripts/'+name)
    cp(ROOT/'planning/mode_a_layout_v082.json','planning/mode_a_layout_v082.json')
    cp(ROOT/'native_motion/sim/mode_a_cancel_return_v082/tb_s4_cancel_return.sv','native_motion/sim/mode_a_cancel_return_v082/tb_s4_cancel_return.sv')
    for p in P.iterdir():
        if p.is_file() and (p.suffix=='.json' or p.name=='JOINT_TARGETS_NATIVE.csv'):cp(p,'candidate/'+p.name)
    for folder,name in [('mode_a_cancel_shift_v082_coppelia_a1','COPPELIA_RESULT.json'),('mode_a_cancel_shift_v082_wire_coppelia_a1','COPPELIA_WIRE_RESULT.json')]:
        src=ROOT/'board_evidence'/folder/'RESULT.json';d=json.loads(src.read_text('utf-8'))
        assert d['passed'] and d['samples_checked']==11925 and d['collision_samples']==0 and d['native_plan_sha256']==sha(P/'PLAN_NATIVE.json')
        cp(src,'candidate/'+name)
    cp(ROOT/'docs/mode_a_cancel_shift_v0_8_2/README_CN.md','README_CN.md');cp(P/'PATH_PLAN_CN.md','PATH_PLAN_CN.md')
    for p in (P/'figures').iterdir():
        if p.is_file():cp(p,'figures/'+p.name)
    replay=ROOT/'board_evidence/mode_a_cancel_shift_v082_replay_a1'
    for p in replay.iterdir():
        if p.is_file():cp(p,'cancel_replay/'+p.name)
    for folder,name in [('mode_a_cancel_shift_v082_return_coppelia_a1','COPPELIA_RESULT.json'),('mode_a_cancel_shift_v082_return_wire_coppelia_a1','COPPELIA_WIRE_RESULT.json')]:
        src=ROOT/'board_evidence'/folder/'RESULT.json';d=json.loads(src.read_text('utf-8'))
        assert d['passed'] and d['samples_checked']==20132 and d['native_plan_sha256']==sha(replay/'PLAN_NATIVE.json')
        cp(src,'cancel_replay/'+name)
    for name in ('CHANGE_SUMMARY.json','FIELD_REVIEW_SUMMARY.json','COPPELIA_SUMMARY.json','COPPELIA_WIRE_SUMMARY.json','RETURN_COPPELIA_SUMMARY.json','RETURN_COPPELIA_WIRE_SUMMARY.json','DEVELOPMENT_ATTEMPTS.json'):
        cp(H/name,'evidence/'+name)
    for folder,key in [('mode_a_cancel_shift_s2_xsim_a1','S2_NORMAL'),('mode_a_cancel_shift_s2_xsim_a2','S2_RETURN'),('mode_a_cancel_return_xsim_a3','S4_RETURN')]:
        src=ROOT/'board_evidence'/folder;d=json.loads((src/'RESULT.json').read_text('utf-8'));assert d['passed']
        cp(src/'RESULT.json','evidence/XSIM_'+key+'.json')
        for p in src.iterdir():
            if p.is_file() and p.suffix in ('.sv','.txt','.mem','.f'):cp(p,'evidence/'+key+'/'+p.name)
    frozen={}
    for folder in ('hardware','model_package','native_motion/rtl','native_motion/constraints','planning'):
        for p in (out/folder).rglob('*'):
            if p.is_file() and p.relative_to(out).as_posix()!='planning/mode_a_layout_v082.json':frozen[p.relative_to(out).as_posix()]=sha(p)
    if any(hashes.get(name)!=digest for name,digest in frozen.items()):raise ValueError('Frozen model/hardware/layout changed')
    plan=json.loads((P/'PLAN_NATIVE.json').read_text('utf-8'));table=json.loads((P/'S4_NATIVE_CANDIDATE.json').read_text('utf-8'))
    text,meta=generate(plan,table);(out/'scripts/mode_a_board_bridge.tcl').write_text(text,'utf-8');write('evidence/BRIDGE_GENERATION.json',meta)
    summary=dict(result='V082_PRE_SHIFT_CANCEL_RETURN_FROZEN_HARDWARE_PASS',version='0.8.2',baseline_version='0.8.1',
        baseline_operator_report='TEST_PASSED',parent_sha256=PARENT_SHA,hardware_rebuilt=False,model_changed=False,
        frozen_file_count=len(frozen),hardware_built_inputs=70,pc_checks=28,terminal_checks=13,new_passed_xsim_runs=3,
        actual_coppelia_samples=64114,s2_rtl_exact_samples=32057,profile=profile(),physical_v082='NOT_RUN')
    write('evidence/CANCEL_SHIFT_VERIFIED_SUMMARY.json',summary)
    manifest=dict(parent,version='0.8.2',hardware_version='0.8.0',source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        parent_package_sha256=PARENT_SHA,execution_profile=profile(),pc_checks=28,terminal_regression_checks=13,
        selected_passed_xsim_runs=3,inherited_passed_xsim_runs=parent['selected_passed_xsim_runs']+parent.get('inherited_passed_xsim_runs',0),actual_coppelia_samples=64114,
        additional_empty_hand_startup_samples=0,physical_hardware_test='NOT_RUN',cancel_shift=summary,inputs={})
    for rel in parent['inputs']:
        if (out/rel).is_file():manifest['inputs'][rel]=sha(out/rel)
    for folder in ('candidate','hardware'):
        for p in (out/folder).iterdir():
            if p.is_file():manifest['inputs'][p.relative_to(out).as_posix()]=sha(p)
    for name in [*['scripts/'+n for n in scripts],'scripts/mode_a_board_bridge.tcl','planning/mode_a_layout_v082.json']:
        manifest['inputs'][name]=sha(out/name)
    for p in (out/'cancel_replay').iterdir():
        if p.is_file():manifest['inputs'][p.relative_to(out).as_posix()]=sha(p)
    manifest.pop('speed_change',None)
    write('BOARD_MANIFEST.json',manifest)
    for script,log,expected in [('test_mode_a_cancel_shift_v082.py','PC_TESTS.txt',28),('test_mode_a_terminal.py','TERMINAL_TESTS.txt',13)]:
        r=subprocess.run([sys.executable,'-X','utf8','-E','-B',str(out/'scripts'/script)],cwd=out,capture_output=True)
        t=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/'evidence'/log).write_text(t,'utf-8')
        if r.returncode or f'Ran {expected} tests' not in t:raise RuntimeError(t)
    replan=ROOT/'board_evidence/mode_a_cancel_shift_packaged_replan_a1'
    r=subprocess.run(['D:/RobotSim/.venv/Scripts/python.exe','-E','-B',str(out/'scripts/prepare_mode_a_cancel_shift_v082.py'),'--out',str(replan)],cwd=out,capture_output=True)
    if r.returncode or any(sha(replan/n)!=sha(P/n) for n in ('PLAN_NATIVE.json','S4_NATIVE_CANDIDATE.json')):raise RuntimeError('Replan '+(r.stdout+r.stderr).decode('utf-8',errors='replace'))
    write('evidence/REPRODUCTION.json',dict(result='PACKAGED_PLAN_AND_S4_TABLE_BYTE_IDENTICAL',native_plan_sha256=sha(P/'PLAN_NATIVE.json'),table_sha256=sha(P/'S4_NATIVE_CANDIDATE.json')))
    files=sorted(p for p in out.rglob('*') if p.is_file())
    (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n' for p in files),'utf-8')
    r=subprocess.run([sys.executable,'-E','-B',str(out/'scripts/run_mode_a_cancel_shift_v082.py'),'--check-only'],cwd=out,capture_output=True)
    if r.returncode:raise RuntimeError((r.stdout+r.stderr).decode('utf-8',errors='replace'))
    print(r.stdout.decode('utf-8',errors='replace'),flush=True)
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():z.write(p,(Path(out.name)/p.relative_to(out)).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise ValueError('ZIP CRC')
        for p in out.rglob('*'):
            if p.is_file() and hashlib.sha256(z.read((Path(out.name)/p.relative_to(out)).as_posix())).hexdigest()!=sha(p):raise ValueError('ZIP member SHA')
    result=dict(result='V082_CANCEL_RETURN_PACKAGE_SOURCE_MODEL_XSA_REPLAN_SHA_CRC_PASS',directory=str(out),zip=str(archive),bytes=archive.stat().st_size,
        sha256=sha(archive),files=sum(p.is_file() for p in out.rglob('*')),source_commit=manifest['source_commit'],checks=summary,physical_test='NOT_RUN')
    (H/'PACKAGE_RESULT.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
