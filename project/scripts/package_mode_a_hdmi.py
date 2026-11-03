"""Build v0.12.0 HDMI release from the frozen v0.11.1 ZIP and new routed hardware."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from mode_a_palmfix_config import ROOT
from mode_a_hdmi_profile import profile
from prepare_mode_a_hdmi_bridge import generate

D = Path('D:/FPGA_Projects/Gesture/deliverables')
BASE = 'Gesture_ModeA_FPGA_v0.11.1_20261028_PalmCenterGate_Final'
BASE_SHA = 'a9307055f98a21e3469434a2ac9c7b7a8d7f934260a20e996b77098fc5f0bc0b'
NAME = 'Gesture_ModeA_FPGA_v0.12.0_20261028_HDMI_Clean_Final'
H = ROOT/'board_evidence/mode_a_hdmi_a1'
IMPL = ROOT/'board_evidence/mode_a_hdmi_impl_a3'
INTEGRATION=ROOT/'board_evidence/mode_a_hdmi_integration_a8'
SIM = ROOT/'board_evidence/mode_a_hdmi_sim_a3'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    out = D/NAME
    archive = Path(str(out)+'.zip')
    if out.exists() or archive.exists():
        raise FileExistsError(out)
    assert sha(D/(BASE+'.zip')) == BASE_SHA
    sim = json.loads((SIM/'RESULT.json').read_text('utf-8'))
    assert sim['passed'] and len(sim['checks']) == 5
    assert json.loads((INTEGRATION/'RESULT.json').read_text('utf-8'))['passed']
    assert json.loads((ROOT/'board_evidence/mode_a_hdmi_serializer_a1/RESULT.json').read_text('utf-8'))['passed']
    out.mkdir(parents=True)
    def dump(rel, obj):
        p = out/rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, indent=2)+'\n', 'utf-8')
    def cp(src, rel):
        p = out/rel
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, p)
        assert sha(src) == sha(p)
    with zipfile.ZipFile(D/(BASE+'.zip')) as z:
        assert z.testzip() is None
        hashes = {l.split('  ', 1)[1]:l.split('  ', 1)[0]
                  for l in z.read(BASE+'/SHA256SUMS').decode().splitlines()}
        for rel, digest in hashes.items():
            destination='evidence/V0111_HARDWARE_MOTION_REUSE.json' if rel=='evidence/HARDWARE_MOTION_REUSE.json' else rel
            p = (out/destination).resolve()
            assert p.is_relative_to(out.resolve()) and not rel.startswith('runs/')
            data = z.read(BASE+'/'+rel)
            assert hashlib.sha256(data).hexdigest() == digest, rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
    # Retain the parent's own results under explicit versioned names.
    for n in ('BOARD_MANIFEST.json', 'README_CN.md'):
        cp(out/n, 'evidence/V0111_'+n)
    for n in ('VERIFIED_SUMMARY.json', 'PACKAGE_CHECK.json', 'ENTRY_CHECK.txt',
              'PC_TESTS.txt', 'TERMINAL_TESTS.txt', 'BRIDGE_GENERATION.json',
              'FIELD_DIAG_SUMMARY.json'):
        cp(out/'evidence'/n, 'evidence/V0111_'+n)
    for n in ('BUILT_SOURCE_HASHES.json','IMPLEMENTATION_SUMMARY.json'):
        cp(out/'evidence'/n,'evidence/V0111_'+n)
    for p in (ROOT/'scripts').glob('*hdmi*.py'):
        cp(p, 'scripts/'+p.name)
    cp(ROOT/'scripts/analyze_mode_a_palm_window.py', 'scripts/analyze_mode_a_palm_window.py')
    for p in (ROOT/'native_motion/sim/mode_a_hdmi').iterdir():
        if p.is_file():
            cp(p, 'native_motion/sim/mode_a_hdmi/'+p.name)
    cp(ROOT/'docs/mode_a_hdmi_v0_12_0/README_CN.md', 'README_CN.md')
    cp(ROOT/'docs/mode_a_hdmi_v0_12_0/INTERFACE_CN.md','INTERFACE_CN.md')
    cp(H/'CONTROL_TAP_EQUIVALENCE.json','evidence/CONTROL_TAP_EQUIVALENCE.json')
    cp(ROOT/'scripts/inspect_mode_a_hdmi_netlist.tcl','scripts/inspect_mode_a_hdmi_netlist.tcl')
    for n in ('tb_tmds_encoder.v','tb_video_timing_640x480.v'):cp(ROOT/'sim/hdmi'/n,'sim/hdmi/'+n)
    cp(ROOT/'board_evidence/mode_a_palmfix_a1/FIELD_DIAG_SUMMARY.json', 'evidence/FIELD_DIAG_SUMMARY.json')
    for p in SIM.iterdir():
        if p.is_file() and p.suffix in ('.json', '.txt', '.sv', '.mem'):
            cp(p, 'evidence/hdmi_sim/'+p.name)
    for p in (ROOT/'board_evidence/mode_a_hdmi_serializer_a1').iterdir():
        if p.is_file() and p.suffix in ('.json','.txt'):cp(p,'evidence/hdmi_serializer/'+p.name)
    for p in INTEGRATION.iterdir():
        if p.is_file() and p.suffix in ('.json','.txt'):
            cp(p,'evidence/hdmi_integration/'+p.name)
    binding=json.loads((IMPL/'BUILT_SOURCE_HASHES.json').read_text('utf-8'))
    for rel,digest in binding['files'].items():
        assert sha(ROOT/rel)==digest,rel
        cp(ROOT/rel,rel)
    for n in ('BUILT_SOURCE_HASHES.json','BUILD_COMPLETED.json','IMPLEMENTATION_SUMMARY.json'):
        cp(IMPL/n,'evidence/'+n)
    for p in (IMPL/'implemented_reports').iterdir():
        if p.suffix in ('.bit','.hwh','.xsa'):cp(p,'hardware/'+p.name)
        elif p.is_file() and p.suffix in ('.rpt','.txt'):cp(p,'evidence/implemented_reports/'+p.name)
    for p in (IMPL/'inspection_a1').iterdir():
        if p.is_file() and p.suffix in ('.txt','.rpt','.json'):cp(p,'evidence/inspection/'+p.name)
    cp(SIM/'HDMI_PREVIEW.png','HDMI_PREVIEW.png')
    fixture=ROOT/'board_evidence/mode_a_follow_vision_a2/fixtures'
    for n in ('palm_source.mem','palm_roi.mem'):cp(fixture/n,'evidence/hdmi_fixtures/'+n)
    idx=json.loads((ROOT/'model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/golden_integer/index.json').read_text('utf-8'))['samples']
    num=next(i for i,x in enumerate(idx) if x['class_label']=='palm' and x['pipeline']['classifier']['class']=='palm')
    cp(fixture/f'{num:02d}_small.mem','evidence/hdmi_fixtures/palm_small.mem')
    plan = json.loads((out/'candidate/bank1/PLAN_NATIVE.json').read_text('utf-8'))
    table = json.loads((out/'candidate/S4_BANKED_CANDIDATE.json').read_text('utf-8'))
    text, meta = generate(plan, table)
    (out/'scripts/mode_a_board_bridge.tcl').write_text(text, 'utf-8')
    dump('evidence/BRIDGE_GENERATION.json', meta)
    # New hardware is bound separately; model, control primitives and motion are frozen.
    prefixes = ('model_package/',
                'candidate/', 'cancel_replay/', 'figures/', 'constraints/')
    frozen = {rel:d for rel, d in hashes.items()
              if rel.startswith(prefixes) or rel in ('PATH_PLAN_CN.md', 'fixed_three_region_map.json')}
    changed_tops={'native_motion/rtl/integration/phase3_roarm_closed_loop_top.v','native_motion/rtl/robot/phase3_s4_task_top.v'}
    frozen.update({r:d for r,d in hashes.items() if r.startswith('native_motion/rtl/') and r not in changed_tops})
    for rel, digest in frozen.items():
        assert sha(out/rel) == digest, rel
    binding = json.loads((out/'evidence/BUILT_SOURCE_HASHES.json').read_text('utf-8'))
    for rel, digest in binding['files'].items():
        assert sha(out/rel) == digest and sha(ROOT/rel) == digest, rel
    hw = json.loads((out/'evidence/IMPLEMENTATION_SUMMARY.json').read_text('utf-8'))
    reuse = dict(passed=True, parent_package_sha256=BASE_SHA,
                 hardware_rebuilt=True, motion_replanned=False, model_changed=False,
                 frozen_file_count=len(frozen), built_input_files=len(binding['files']),
                 frozen_groups={s:sum(n.startswith(s) for n in frozen) for s in prefixes},
                 hardware=hw['artifacts'], timing_ns=hw['timing_ns'],
                 motion_profile='EXACT_V0.11.1_660_33_50HZ',
                 parent_s2_and_coppelia='REUSED_UNCHANGED_TARGETS_TIMING_AND_MOTION_RTL',
                 new_physical_test='NOT_RUN')
    dump('evidence/CONTROL_MOTION_REUSE.json', reuse)
    summary = dict(result='HDMI_DISPLAY_INTEGRATION_OFFLINE_PASS', version='0.12.0',
                   parent_package_sha256=BASE_SHA, hardware_version='0.12.0', hardware_rebuilt=True,
                   motion_replanned=False, model_changed=False, pc_checks=48, terminal_checks=13,
                   hdmi_focused_sims=5, serializer_unisim_checks=1, integration_serializer_model='SINK; production serializer separately UNISIM verified', production_vga_frames=10, display_is_passive=True,
                   execution_profile=profile(), timing_ns=hw['timing_ns'],
                   inherited_s2_exact_samples=57285, inherited_coppelia_samples=114570,
                   physical_hardware_test='NOT_RUN')
    dump('evidence/VERIFIED_SUMMARY.json', summary)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    manifest = dict(version='0.12.0', hardware_version='0.12.0', task_abi=0x3409,
                    arrival_policy='observe_all', source_commit=source,
                    parent_package_sha256=BASE_SHA, execution_profile=profile(),
                    palm_admission_policy='FRESH_ACCEPTED_CENTER_CELL_PRE2S_PALM500MS',
                    physical_hardware_test='NOT_RUN', inputs={})
    for folder in ('scripts', 'ps', 'hardware', 'model_package', 'native_motion',
                   'planning', 'candidate', 'cancel_replay'):
        for p in (out/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:
                manifest['inputs'][p.relative_to(out).as_posix()] = sha(p)
    for rel in ('README_CN.md', 'INTERFACE_CN.md', 'PATH_PLAN_CN.md', 'fixed_three_region_map.json',
                'evidence/BUILT_SOURCE_HASHES.json', 'evidence/IMPLEMENTATION_SUMMARY.json',
                'evidence/VERIFIED_SUMMARY.json', 'evidence/CONTROL_MOTION_REUSE.json'):
        manifest['inputs'][rel] = sha(out/rel)
    dump('BOARD_MANIFEST.json', manifest)
    for script, expected, name in [('test_mode_a_hdmi.py', 48, 'PC_TESTS.txt'),
                                   ('test_mode_a_terminal.py', 13, 'TERMINAL_TESTS.txt')]:
        r = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(out/'scripts'/script)],
                           cwd=out, capture_output=True)
        txt = (r.stdout+r.stderr).decode('utf-8', errors='replace')
        (out/'evidence'/name).write_text(txt, 'utf-8')
        if r.returncode or f'Ran {expected} tests' not in txt:
            raise RuntimeError(txt)
    from check_mode_a_hdmi_package import check
    dump('evidence/PACKAGE_CHECK.json', check(out))
    r = subprocess.run([sys.executable, '-X', 'utf8', '-B',
                        str(out/'scripts/run_mode_a_hdmi.py'), '--check-only'],
                       cwd=out, capture_output=True)
    (out/'evidence/ENTRY_CHECK.txt').write_bytes(r.stdout+r.stderr)
    if r.returncode:
        raise RuntimeError((r.stdout+r.stderr).decode('utf-8', errors='replace'))
    files = sorted(p for p in out.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n'
                                        for p in files), 'utf-8')
    files.append(out/'SHA256SUMS')
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in files:
            z.write(p, (Path(NAME)/p.relative_to(out)).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for p in files:
            assert hashlib.sha256(z.read((Path(NAME)/p.relative_to(out)).as_posix())).hexdigest() == sha(p)
    result = dict(result='HDMI_FULL_PACKAGE_SHA_CRC_PASS', directory=str(out),
                  zip=str(archive), bytes=archive.stat().st_size, files=len(files),
                  sha256=sha(archive), source_commit=source, physical_hardware_test='NOT_RUN')
    for n in ('VERIFIED_SUMMARY.json', 'CONTROL_MOTION_REUSE.json', 'PACKAGE_CHECK.json'):
        shutil.copyfile(out/'evidence'/n, H/n)
    (H/'PACKAGE_RESULT.json').write_text(json.dumps(result, indent=2)+'\n', 'utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
