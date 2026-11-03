"""Seal the full v080 package from a hash-verified v072 dependency archive.

No board access. Never copies field runs, LOCAL poses, old hardware or old evidence.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,zipfile
from mode_a_handover_config import ROOT
from mode_a_handover_profile import profile
from prepare_mode_a_handover_bridge import generate

DELIVERY=Path('D:/FPGA_Projects/Gesture/deliverables')
PARENT_NAME='Gesture_ModeA_FPGA_v0.7.2_20261027_D5Preconnected'
PARENT_SHA='be07540d149f533ec7865b23f3d16d36742242b2f9db611d402631d3c9df0c2c'
NAME='Gesture_ModeA_FPGA_v0.8.0_20261027_BlindHandover'
H=ROOT/'board_evidence/mode_a_handover_v080_a1'
P=ROOT/'board_evidence/mode_a_handover_v080_plan_a2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=DELIVERY/NAME)
    ap.add_argument('--base-zip',type=Path,default=DELIVERY/(PARENT_NAME+'.zip'));a=ap.parse_args()
    out=a.out.resolve();archive=Path(str(out)+'.zip')
    if out.exists() or archive.exists():raise FileExistsError('Preserve previous output '+str(out))
    if sha(a.base_zip)!=PARENT_SHA:raise ValueError('Wrong frozen v072 parent')
    impl=json.loads((H/'IMPLEMENTATION_SUMMARY.json').read_text('utf-8'))
    assert impl['result']=='IMPLEMENTATION_NETLIST_IOB_CDC_SKEW_AND_XSA_PASS' and impl['task_abi']==0x3406
    out.mkdir(parents=True)
    def cp(src,name):
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,target)
        if sha(src)!=sha(target):raise ValueError('Copy '+name)
    def write(name,data):
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2)+'\n','utf-8')
    # Only frozen dependencies; field logs and earlier package metadata never enter this release.
    prefixes=('model_package/','native_motion/','ps/','sim/','scenes/','handoff/','planning/','scripts/')
    with zipfile.ZipFile(a.base_zip) as z:
        if z.testzip():raise ValueError('Parent ZIP CRC')
        rows=z.read(PARENT_NAME+'/SHA256SUMS').decode('utf-8').splitlines()
        parent_hashes={r.split('  ',1)[1]:r.split('  ',1)[0] for r in rows}
        for name,digest in parent_hashes.items():
            if not name.startswith(prefixes):continue
            target=(out/name).resolve()
            if not target.is_relative_to(out) or 'LOCAL' in name or '/runs/' in name:raise ValueError('Unsafe parent member '+name)
            data=z.read(PARENT_NAME+'/'+name)
            if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Parent member '+name)
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    binding=json.loads((H/'BUILT_SOURCE_HASHES.json').read_text('utf-8'))
    for name,digest in binding['files'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Built input changed '+name)
        cp(ROOT/name,name)
    scripts=['mode_a_handover_profile.py','mode_a_handover_config.py','prepare_mode_a_handover_v08.py',
        'prepare_mode_a_handover_bridge.py','run_mode_a_handover_v08.py','check_mode_a_handover_package.py',
        'test_mode_a_handover_v08.py','build_mode_a_handover_v08.py','inspect_mode_a_handover_v08.py',
        'summarize_mode_a_handover_impl.py','package_mode_a_handover_v08.py','run_mode_a_handover_xsim.py',
        'run_mode_a_handover_uart_xsim.py','run_mode_a_motion_checks.py','write_mode_a_path_report.py']
    for name in scripts:cp(ROOT/'scripts'/name,'scripts/'+name)
    for p in (ROOT/'native_motion/sim/mode_a_handover_v080').iterdir():
        if p.is_file() and p.suffix in ('.sv','.v','.vh'):cp(p,p.relative_to(ROOT).as_posix())
    for ext in ('bit','hwh','xsa'):cp(H/'implemented_reports'/('roarm_closed_loop.'+ext),'hardware/roarm_closed_loop.'+ext)
    for name in ('PLAN_NATIVE.json','S4_NATIVE_CANDIDATE.json','JOINT_TARGETS_NATIVE.csv','SCENE_PLAN.json','LAYOUT.json','PATH_PREVIEW.json','SUMMARY.json'):
        cp(P/name,'candidate/'+name)
    for folder,name in [('mode_a_handover_v080_coppelia_a1','COPPELIA_RESULT.json'),('mode_a_handover_v080_wire_coppelia_a1','COPPELIA_WIRE_RESULT.json')]:
        data=json.loads((ROOT/'board_evidence'/folder/'RESULT.json').read_text('utf-8'))
        assert data['passed'] and data['samples_checked']==17286 and data['collision_samples']==0
        assert data['native_plan_sha256']==sha(P/'PLAN_NATIVE.json')
        cp(ROOT/'board_evidence'/folder/'RESULT.json','candidate/'+name)
    cp(ROOT/'docs/mode_a_handover_v0_8_0/README_CN.md','README_CN.md');cp(P/'PATH_PLAN_CN.md','PATH_PLAN_CN.md')
    for p in (P/'figures').iterdir():
        if p.is_file():cp(p,'figures/'+p.name)
    for name in ('IMPLEMENTATION_SUMMARY.json','BUILT_SOURCE_HASHES.json','FIELD_REVIEW_SUMMARY.json','STARTUP_COPPELIA_SUMMARY.json','GEOMETRY_REUSE_SUMMARY.json'):
        cp(H/name,'evidence/'+name)
    cp(ROOT/'native_motion/reports/roarm_model_audit.json','evidence/MODEL_INTEGER_AUDIT.json')
    for p in (H/'implemented_reports').iterdir():
        if p.is_file() and p.suffix in ('.rpt','.txt'):cp(p,'evidence/implementation/'+p.name)
    for p in (H/'inspection_a1').iterdir():
        if p.is_file() and p.suffix in ('.rpt','.txt','.json'):cp(p,'evidence/inspection/'+p.name)
    tests={}
    for key,folder in [('handover_fsm','mode_a_handover_v080_xsim_a3'),('integration','mode_a_handover_integration_a7'),
                       ('uart_rate','mode_a_handover_uart_xsim_a1'),('legacy_fsm','mode_a_board_timed_xsim_v080_legacy_a1')]:
        data=json.loads((ROOT/'board_evidence'/folder/'RESULT.json').read_text('utf-8'))
        assert data['passed'] is True;tests[key]=data;write('evidence/XSIM_'+key+'.json',data)
    # Integration benches and logs reproduce the exact external-vision stimulus, including PALM removal.
    for p in (ROOT/'board_evidence/mode_a_handover_integration_a7').iterdir():
        if p.is_file() and p.suffix in ('.v','.vh','.txt','.json','.f'):cp(p,'evidence/integration/'+p.name)
    for folder,key in [('mode_a_handover_v080_xsim_a3','handover_fsm'),('mode_a_handover_uart_xsim_a1','uart_rate'),
                       ('mode_a_board_timed_xsim_v080_legacy_a1','legacy_fsm')]:
        for p in (ROOT/'board_evidence'/folder).iterdir():
            if p.is_file() and p.suffix in ('.txt','.sv','.mem','.f'):cp(p,'evidence/'+key+'/'+p.name)
    plan=json.loads((P/'PLAN_NATIVE.json').read_text('utf-8'));table=json.loads((P/'S4_NATIVE_CANDIDATE.json').read_text('utf-8'))
    bridge,meta=generate(plan,table);(out/'scripts/mode_a_board_bridge.tcl').write_text(bridge,'utf-8')
    write('evidence/BRIDGE_GENERATION.json',meta)
    frozen={p.relative_to(out).as_posix():sha(p) for p in (out/'model_package').rglob('*') if p.is_file()}
    if any(parent_hashes.get(name)!=digest for name,digest in frozen.items()):raise ValueError('Model changed')
    manifest=dict(schema='gesture.mode_a.board_package.v1',version='0.8.0',task_abi=0x3406,arrival_policy='observe_all',
        startup_policy='D5_PRECONNECTED_AUTO',model_id='022267A9',model_commit='022267a939c892d73ae278ceddee1a3e856a8dee',
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),parent_package_sha256=PARENT_SHA,
        artifacts=impl['artifacts'],hardware_source_binding_sha256=sha(H/'BUILT_SOURCE_HASHES.json'),
        execution_profile=profile(),layout_id=plan['layout_id'],pc_checks=23,terminal_regression_checks=13,
        selected_passed_xsim_runs=7,actual_coppelia_samples=34572,additional_empty_hand_startup_samples=227,
        capacity=table['capacity'],physical_hardware_test='NOT_RUN',implementation=impl,inputs={})
    for folder in ('candidate','hardware'):
        for p in (out/folder).iterdir():
            if p.is_file():manifest['inputs'][p.relative_to(out).as_posix()]=sha(p)
    for name in [*['scripts/'+n for n in scripts],'scripts/mode_a_board_bridge.tcl','planning/mode_a_layout_v070.json']:
        manifest['inputs'][name]=sha(out/name)
    write('BOARD_MANIFEST.json',manifest)
    (out/'requirements-board.txt').write_text('PyYAML\n# Planning/simulation: NumPy, SciPy, coppeliasim-zmqremoteapi-client; see README.\n','utf-8')
    for script,log,expected in [('test_mode_a_handover_v08.py','PC_TESTS.txt',23),('test_mode_a_terminal.py','TERMINAL_TESTS.txt',13)]:
        r=subprocess.run([sys.executable,'-X','utf8','-E','-B',str(out/'scripts'/script)],cwd=out,capture_output=True)
        text=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/'evidence'/log).write_text(text,'utf-8')
        if r.returncode or f'Ran {expected} tests' not in text:raise RuntimeError(text)
    replan=ROOT/'board_evidence/mode_a_handover_packaged_replan_a1'
    r=subprocess.run(['D:/RobotSim/.venv/Scripts/python.exe','-E','-B',str(out/'scripts/prepare_mode_a_handover_v08.py'),'--out',str(replan)],cwd=out,capture_output=True)
    if r.returncode or any(sha(replan/n)!=sha(P/n) for n in ('PLAN_NATIVE.json','S4_NATIVE_CANDIDATE.json')):
        raise RuntimeError('Packaged replan '+(r.stdout+r.stderr).decode('utf-8',errors='replace'))
    write('evidence/REPRODUCTION.json',dict(result='PACKAGED_PLAN_AND_S4_TABLE_BYTE_IDENTICAL',native_plan_sha256=sha(P/'PLAN_NATIVE.json'),table_sha256=sha(P/'S4_NATIVE_CANDIDATE.json')))
    write('evidence/DEVELOPMENT_ATTEMPTS.json',dict(selected_passed_xsim_runs=7,
        notes=['Earlier FSM iterations tested a recoverable PALM-loss pause; superseded by the user PRE-only blind-delivery rule. Final FSM a3 and integration a7 test the final policy.',
        'Integration a1/a2 used superseded resume behavior. a3/a4 incorrectly injected PS vision while the physical policy intentionally requires external PL vision. Final a7 drives the real external vision input and removes it after PRE triggering; exact normal actions and S2 samples remain checked.',
        'Legacy COMM action oracle was arrival-dependent. Timed operation retains final COMM fault/counters and postfault cutoff; normal DRY_RUN/LINE retain exact golden actions and samples.'],
        raw_field_poses_included=False,physical_test='NOT_RUN'))
    write('evidence/FROZEN_MODEL.json',dict(files=len(frozen),parent_sha256=PARENT_SHA,model_changed=False))
    files=sorted(p for p in out.rglob('*') if p.is_file())
    (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n' for p in files),'utf-8')
    r=subprocess.run([sys.executable,'-E','-B',str(out/'scripts/run_mode_a_handover_v08.py'),'--check-only'],cwd=out,capture_output=True)
    if r.returncode:raise RuntimeError((r.stdout+r.stderr).decode('utf-8',errors='replace'))
    print(r.stdout.decode('utf-8',errors='replace'),flush=True)
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():z.write(p,(Path(out.name)/p.relative_to(out)).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise ValueError('New ZIP CRC')
        for p in out.rglob('*'):
            if p.is_file() and hashlib.sha256(z.read((Path(out.name)/p.relative_to(out)).as_posix())).hexdigest()!=sha(p):raise ValueError('ZIP member SHA')
    result=dict(result='ABI3406_BOARD_PACKAGE_SHA_CRC_SOURCE_MODEL_XSA_AND_REPLAN_PASS',directory=str(out),zip=str(archive),
        bytes=archive.stat().st_size,sha256=sha(archive),files=sum(p.is_file() for p in out.rglob('*')),
        pc_checks=23,terminal_regression_checks=13,selected_passed_xsim_runs=7,physical_hardware_test='NOT_RUN',source_commit=manifest['source_commit'])
    (H/'PACKAGE_RESULT.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
