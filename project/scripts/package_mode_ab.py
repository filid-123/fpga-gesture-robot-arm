"""Assemble a complete local AB package from frozen A, pinned B and reviewed HW."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile
ROOT=Path(__file__).resolve().parents[1]
BASE=Path('D:/FPGA_Projects/Gesture/deliverables/Gesture_ModeA_FPGA_v0.14.0_20261029_AutoRestock_Final')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
SKIP={'.git','.xil','__pycache__','xsim.dir','.pytest_cache','runs'}


def payload_files(out):
    return sorted(p for p in out.rglob('*') if p.is_file()
                  and not any(x.lower() in SKIP or x.lower().startswith('.venv-')
                              for x in p.relative_to(out).parts)
                  and p.relative_to(out).as_posix() not in ('mode_ab_manifest.json','sha256sums.txt'))


def seal(out):
    manifest=json.loads((out/'mode_ab_manifest.json').read_bytes())
    manifest['inputs']={p.relative_to(out).as_posix():sha(p) for p in payload_files(out)}
    (out/'mode_ab_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    sums=dict(manifest['inputs']);sums['mode_ab_manifest.json']=sha(out/'mode_ab_manifest.json')
    (out/'sha256sums.txt').write_text(''.join(d+'  '+name+'\n' for name,d in sorted(sums.items())))
    return manifest


def archive(out,target=None):
    manifest=json.loads((out/'mode_ab_manifest.json').read_bytes())
    members=dict(manifest['inputs']);members['mode_ab_manifest.json']=sha(out/'mode_ab_manifest.json')
    members['sha256sums.txt']=sha(out/'sha256sums.txt')
    if set(manifest['inputs'])!={p.relative_to(out).as_posix() for p in payload_files(out)}:
        raise ValueError('Payload member list changed after seal')
    for name,digest in members.items():
        if name!=name.lower() or sha(out/name)!=digest:raise ValueError('Invalid sealed member '+name)
    target=Path(target) if target is not None else out.with_suffix('.zip')
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in sorted(members):z.write(out/name,name)
    with zipfile.ZipFile(target) as z:
        if z.testzip() or set(z.namelist())!=set(members):raise ValueError('Archive member/CRC failure')
        for name,digest in members.items():
            if hashlib.sha256(z.read(name)).hexdigest()!=digest:raise ValueError('Archive SHA mismatch '+name)
    return dict(result='SEALED_ZIP_ALL_MEMBERS_SHA_AND_CRC_PASS',path=str(target),
                bytes=target.stat().st_size,sha256=sha(target),members=len(members),
                runtime_environment_included=False,physical_test='NOT_RUN')


def copy_tree(source,out,prefix=''):
    for p in source.rglob('*'):
        if not p.is_file() or any(x.lower() in SKIP for x in p.relative_to(source).parts):continue
        copy(p,out,Path(prefix)/p.relative_to(source))


def copy(source,out,relative):
    target=out/relative.as_posix().lower();target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target)


def main(out,implementation='a8'):
    expected=Path('D:/FPGA_Projects/Gesture/deliverables').resolve()
    out=out.resolve()
    if not out.is_relative_to(expected) or out==expected:raise ValueError('Use a new named local deliverables directory')
    out.mkdir(parents=True,exist_ok=False)
    # This is a local deliverable, not a Git upload of private Mode-A teaching data.
    for p in BASE.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(BASE)
        if any(v.lower() in SKIP for v in rel.parts):continue
        if rel.name.lower() in ('sha256sums','sha256sums.txt'):continue
        if rel.parts[0].lower()=='evidence':rel=Path('evidence/a_baseline')/Path(*rel.parts[1:])
        if len(rel.parts)==1 and rel.name.lower() in ('board_manifest.json','readme_cn.md','project_log.md','current_project_context.md'):
            rel=Path('evidence/a_baseline')/rel.name
        copy(p,out,rel)
    imported=json.loads((ROOT/'board_evidence/mode_ab_v0_1_0/upstream_import.json').read_bytes())
    for name,digest in imported['source_files'].items():
        p=ROOT/name
        if sha(p)!=digest:raise ValueError('Pinned upstream import changed: '+name)
        copy(p,out,Path(name))
    for directory in ('pc/mode_ab','docs/mode_ab','web/mode-ab','candidate/mode_ab'):
        copy_tree(ROOT/directory,out,directory)
    own=['scripts/import_mode_b_giao.py','scripts/build_mode_ab.py','scripts/review_mode_ab_impl.py','scripts/inspect_mode_ab_impl.py',
         'scripts/prepare_mode_ab_home.py','scripts/prepare_mode_ab_candidates.py','scripts/verify_mode_ab_motion.py',
         'scripts/run_mode_ab_task_xsim.py','scripts/run_mode_ab_paths_xsim.py','scripts/run_mode_ab_s2_xsim.py',
         'scripts/run_mode_ab.py','scripts/check_mode_ab_gpu.py','scripts/test_mode_ab_control.py',
         'scripts/test_mode_ab_http.py','scripts/test_mode_ab_shared_red.py','scripts/test_mode_ab_snapshot.py','scripts/set_mode_ab_camera_profile.ps1',
         'scripts/test_mode_ab_planning.py','scripts/verify_mode_ab_planning.py','scripts/generate_mode_ab_font.py',
         'scripts/import_mode_b_updates.py','scripts/prepare_mode_ab_p3.py','scripts/verify_mode_ab_p3.py','scripts/verify_mode_ab_pc.py',
         'scripts/test_mode_ab_uploads.py','scripts/test_mode_ab_family.py','scripts/test_mode_ab_diagnostics.py','scripts/test_mode_ab_ui.cjs',
         'scripts/run_mode_a_upgrade_hdmi.py','native_motion/sim/mode_a_upgrade/tb_renderer_hd.sv',
         'scripts/summarize_mode_ab_session.py','scripts/package_mode_ab.py','scripts/check_mode_ab_package.py',
         'scripts/probe_mode_ab_npu.py','start_mode_ab.ps1','setup_mode_ab.ps1',
         'requirements_mode_ab.txt','requirements_mode_ab_lock.txt','requirements-mode-ab-rocm-constraints.txt']
    for name in own:copy(ROOT/name,out,Path(name))
    h=ROOT/('board_evidence/mode_ab_impl_'+implementation);binding=json.loads((h/'built_source_hashes.json').read_bytes())
    for name,digest in binding['files'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Hardware input changed: '+name)
        copy(ROOT/name,out,Path(name))
    for ext in ('bit','hwh','xsa'):copy(h/'implemented_reports'/('roarm_closed_loop.'+ext),out,Path('hardware')/('roarm_closed_loop.'+ext))
    copy_tree(h,out,'evidence/implementation')
    proofs=['mode_a_restock_task_ab_legacy_a1','mode_ab_task_a7','mode_ab_paths_a5','mode_ab_s2_a4',
            'mode_ab_v0_1_0/gpu_a3','mode_ab_v0_1_0/geometry_a3','mode_ab_v0_1_0/bridge_a1']
    for name in proofs:copy_tree(ROOT/'board_evidence'/name,out,'board_evidence/'+name)
    for name in ('environment.json','upstream_import.json','fresh_family_batch_a1.json'):
        copy(ROOT/'board_evidence/mode_ab_v0_1_0'/name,out,Path('evidence')/name)
    copy_tree(ROOT/'board_evidence/mode_ab_p2',out,'evidence/planning_hdmi_p2')
    copy_tree(ROOT/'board_evidence/mode_a_upgrade_hdmi_abp2a1',out,'evidence/hdmi_p2')
    for name in ('profiles.json','upstream_update.json','diagnosis.json'):
        copy(ROOT/'board_evidence/mode_ab_p3'/name,out,Path('evidence/planning_ux_giao_p3')/name)
    for name in ('pc_final_a4','replay_a4','gpu_a1'):
        copy_tree(ROOT/'board_evidence/mode_ab_p3'/name,out,'evidence/planning_ux_giao_p3/'+name)
    for name in ('mode_ab_paths_p3a2','mode_ab_s2_p3a2'):
        copy_tree(ROOT/'board_evidence'/name,out,'board_evidence/'+name)
    preview=ROOT/'board_evidence/mode_ab_preview_a1/console_b.png'
    if preview.exists():copy(preview,out,Path('evidence/console_b.png'))
    copy(ROOT/'docs/mode_ab/readme_cn.md',out,Path('readme.md'))
    copy(ROOT/'docs/mode_ab/interface.md',out,Path('docs/interface.md'))
    copy(ROOT/'docs/mode_ab/hardware_setup.md',out,Path('docs/hardware_setup.md'))
    pdf=Path('C:/redacted_user/Downloads/8c7a809f-f0b8-42e4-996a-3a5f2f132288.pdf')
    if pdf.exists():copy(pdf,out,Path('docs/mode_ab/specification.pdf'))
    rollback=BASE.parent/(BASE.name+'.zip')
    copy(rollback,out,Path('rollback/mode_a_v014_original.zip'))
    impl=json.loads((h/'implementation_summary.json').read_bytes())
    gpu=json.loads((ROOT/'board_evidence/mode_ab_p3/gpu_a1/result.json').read_bytes())
    summary=dict(version='0.1.0',patch_id='planning_ux_giao_p3',task_abi=0x340d,release='READY_FOR_STAGED_AB_BOARD_TEST',
        a_baseline_commit='0e827fe4',b_source_commit=imported['source_commit'],shared_red=True,
        completed=dict(pc_unit_tests=55,ui_checks=10,real_gpu_reference_frames=9,s4_scenarios=25,
                       s2_legs=1253,s2_six_axis_samples=48498,geometry='65 handover targets and 4160 ordered retarget pairs per B profile; source checks plus bound family proof or full fallback',
                       full_implementation=impl['result']),
        hardware_test='NOT_RUN',physical_ab_closed_loop='NOT_RUN',npu_execution='FAILED_COMPILATION_GPU_DEFAULT_USER_ACCEPTED',
        formal_detection_map='NOT_RUN_INDEPENDENT_LABELLED_SET_NOT_INCLUDED',formal_segmentation_miou='NOT_RUN',
        artifact_hashes=impl['artifacts'],historical_a_zip_sha256=sha(rollback),
        source_snapshot='Current package files are bound below; historical proof paths retain original provenance')
    (out/'evidence/validation_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    metrics=out/'metrics';metrics.mkdir(exist_ok=True)
    rows=[['任务闭环成功率','核心','NOT_RUN','%','新AB现场；逐项人工确认','0','runs/operator_observations.jsonl'],
          ['传感到执行器物理响应P50/P95/P99/max','核心','NOT_RUN','ms','独立视频或仪器测量','0','runs/physical_latency.jsonl'],
          ['检测mAP@0.5:0.95 / 分割mIoU','核心','NOT_RUN','ratio','需要独立标注；九张回放不是通用效果评测','0','evidence/validation_summary.json'],
          ['ROCm总感知延迟P50/P95/P99/max','核心',json.dumps(gpu['quantiles_ms']['pipeline_total_ms']),'ms','9张原实测图回放；batch=1；warm模型；不是物理响应延迟','9','evidence/planning_ux_giao_p3/gpu_a1/result.json'],
          ['FPGA量化贡献现场延迟/控制抖动','核心','NOT_RUN','ms','新AB片上trace和外部仪器','0','runs/pl_trace.json'],
          ['PC-FPGA RTT / 错误率','核心','NOT_RUN','ms/ratio','JTAG请求至回包；同一PC单调时钟','0','runs/communication.jsonl'],
          ['LUT/FF/BRAM/DSP','专项',json.dumps(impl['utilization']),'count','XC7Z020整机实现；资源最高80.714%','1','evidence/implementation/implementation_summary.json'],
          ['目标时钟 / WNS / WHS','专项',f"100 / {impl['timing_ns']['WNS']} / {impl['timing_ns']['WHS']}",'MHz/ns/ns','Vivado2026.1整机实现；不是外部抖动实测','1','evidence/implementation/implemented_reports/build_gate.txt'],
          ['持续视觉FPS / 稳定会话时长','专项','NOT_RUN','fps/s','现场长时运行，汇总脚本生成','0','runs/vision.jsonl']]
    with (metrics/'metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['指标名称','类别','数值','单位','测量条件','测试次数或时长','证据文件']);w.writerows(rows)
    inputs={p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    manifest=dict(version='0.1.0',patch_id='planning_ux_giao_p3',task_abi=0x340d,inputs=inputs,source_commit_a='0e827fe4',source_commit_b=imported['source_commit'],
                  physical_test='NOT_RUN',hardware_artifacts=impl['artifacts'],runtime_backend='ROCM_HIP_NO_CPU_FALLBACK',shared_red=True)
    (out/'mode_ab_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    sums=dict(inputs);sums['mode_ab_manifest.json']=sha(out/'mode_ab_manifest.json')
    (out/'sha256sums.txt').write_text(''.join(d+'  '+name+'\n' for name,d in sorted(sums.items())))
    print(json.dumps(dict(result='PACKAGE_ASSEMBLED_REQUIRES_CHECK',path=str(out),files=len(inputs)+2,bytes=sum(p.stat().st_size for p in out.rglob('*') if p.is_file())),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--implementation',default='a8')
    p.add_argument('--archive-out',type=Path,help='New ZIP path; an existing archive is never replaced')
    modes=p.add_mutually_exclusive_group();modes.add_argument('--seal-existing',action='store_true');modes.add_argument('--archive',action='store_true')
    a=p.parse_args()
    if a.seal_existing:print(json.dumps(dict(result='PACKAGE_RESEALED',files=len(seal(a.out)['inputs']))))
    elif a.archive:print(json.dumps(archive(a.out,a.archive_out),indent=2))
    else:main(a.out,a.implementation)
