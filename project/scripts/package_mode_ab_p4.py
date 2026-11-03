"""Assemble/seal the complete ABI340E release while retaining old rollback files."""
import argparse,csv,json,subprocess
from pathlib import Path
from package_mode_ab import ROOT,main as baseline,copy,copy_tree,seal,archive,sha

P4_PROOFS=('pc_final','profiles_release','coverage_release','flows_release','gpu_final',
 'route_pipeline_release','native_vectors_pipeline_final','backend_final','route_aperture_final',
 'reset_warning_release','gripper_waits_final','gripper_pipeline_release','startup_map_p4_1_final')

def main(out,attempt):
 baseline(out,attempt)
 readme=(out/'readme.md').read_text(encoding='utf-8')
 readme=readme.replace('](native_routes_p4.md)','](docs/mode_ab/native_routes_p4.md)').replace('](pl_wrappers.md)','](docs/mode_ab/pl_wrappers.md)')
 (out/'readme.md').write_text(readme,encoding='utf-8')
 scripts=['check_mode_ab_p4.py','package_mode_ab_p4.py','resume_mode_ab_build.py',
  'prepare_mode_ab_p4.py','prepare_mode_ab_native_coverage.py','verify_mode_ab_p4_flows.py',
  'verify_mode_ab_p4_workspace.py','run_mode_ab_native_s2_xsim.py','inspect_mode_ab_p4_netlist.tcl',
  'inspect_mode_a_restock_netlist.tcl','run_mode_a_v3_checks.py','refactor_pl_wrappers.py',
  'verify_pl_wrappers.py','finalize_mode_ab_gripper_waits.py','test_mode_ab_gripper_waits_rtl.py',
  'seal_mode_ab_p4_evidence.py','test_mode_b_route_rtl.py','test_mode_b_full_workspace.py',
  'test_mode_b_full_workspace_install.py','apply_mode_b_full_workspace.py','test_mode_ab_startup_map.py']
 scripts += [p.name for p in (ROOT/'scripts').glob('test_mode_ab_native*.py')]
 scripts += ['test_mode_ab_route_aperture_rtl.py']
 for name in scripts:copy(ROOT/'scripts'/name,out,Path('scripts')/name)
 copy(ROOT/'config/ai_pc/mode_b_full_workspace_20261030.json',out,Path('config/ai_pc/mode_b_full_workspace_20261030.json'))
 for name in P4_PROOFS:
  source=ROOT/'board_evidence/mode_ab_p4'/name
  # Reproducible vectors and benches, without simulator caches or duplicate
  # complete plans from seven scenarios.
  for p in source.iterdir():
   if p.is_file() and p.suffix.lower() in ('.json','.txt','.sv','.mem','.tcl','.f'):
    copy(p,out,Path('board_evidence/mode_ab_p4')/name/p.name)
 copy(ROOT/'board_evidence/mode_ab_p4/release_scope.json',out,Path('board_evidence/mode_ab_p4/release_scope.json'))
 copy(ROOT/'board_evidence/mode_ab_p4/pipeline_fix/before.v',out,Path('board_evidence/mode_ab_p4/pipeline_fix/before.v'))
 for name in ('mode_ab_paths_p4final','mode_a_upgrade_hdmi_abp4final'):
  copy_tree(ROOT/'board_evidence'/name,out,'board_evidence/'+name)
 wrappers=ROOT/'board_evidence/pl_wrappers_v1'
 for name in ('manifest.json','result.json','vision_validation.json'):
  copy(wrappers/name,out,Path('board_evidence/pl_wrappers_v1')/name)
 for name in ('before','pure_after'):copy_tree(wrappers/name,out,'board_evidence/pl_wrappers_v1/'+name)
 for p in (wrappers/'vision_final').rglob('RESULTS.json'):
  copy(p,out,Path('board_evidence/pl_wrappers_v1/vision_final')/p.relative_to(wrappers/'vision_final'))
 for name in ('tb_pipeline_v2.sv',):copy(ROOT/'native_motion/sim/mode_a_v3'/name,out,Path('native_motion/sim/mode_a_v3')/name)
 proof_files=[ROOT/'board_evidence/mode_ab_p4'/name/'result.json' for name in P4_PROOFS]
 proof_files += [ROOT/'board_evidence/mode_ab_paths_p4final/result.json',ROOT/'board_evidence/mode_a_upgrade_hdmi_abp4final/RESULT.json',wrappers/'vision_validation.json']
 for file in proof_files:
  proof=json.loads(file.read_bytes())
  for name,digest in {**proof.get('source_hashes',{}),**proof.get('inputs',{})}.items():
   source=ROOT/name
   # Historical bindings are checked against their explicit delta receipt;
   # never replace a current release source with a historical copy.
   if source.is_file() and sha(source)==digest:copy(source,out,Path(name))
 diagram=Path('D:/FPGA_Projects/Gesture/deliverables/mode_ab_pl_architecture_20261030_final')
 copy_tree(diagram,out,'docs/pl_architecture')
 old=ROOT/'board_evidence/mode_ab_impl_a8'
 for ext in ('bit','hwh','xsa'):copy(old/'implemented_reports'/('roarm_closed_loop.'+ext),out,Path('rollback/p3_a8')/('roarm_closed_loop.'+ext))
 for name in ('built_source_hashes.json','implementation_summary.json'):copy(old/name,out,Path('rollback/p3_a8')/name)
 h=ROOT/('board_evidence/mode_ab_impl_'+attempt);impl=json.loads((h/'implementation_summary.json').read_bytes())
 summary=dict(version='0.1.0-p4',patch_id='native_giao_full_workspace_p4',task_abi=0x340e,route_abi=0xb001,
  release='READY_FOR_STAGED_AB_BOARD_TEST',source_b='3d66aeb8d33b42abf8d82da3c71b1e6276a9a32a',
  source_giao_fast_paths='1d3fa84de81d05b846d2b9f30998e16a84f4eee3',
  completed=dict(distinct_pc_tests=78,startup_map_checks=3,ui_checks=10,real_gpu_frames=9,s4_scenarios=28,
   native_phase_operations=1584,native_six_axis_vectors=49540,production_gripper_timers=12,
   workspace_grid_poses=75,delivery_and_public_restock_cases=7,vision_fixture_pipeline_cases=26,
   hdmi_checks=8,structural_wrappers=12,leaf_instances_grouped=34,
   handover_family='65 targets / 4160 ordered retarget pairs per class and required attachment certificates',
   full_implementation=impl['result']),
  evidence_reuse='See board_evidence/mode_ab_p4/release_scope.json: timing-only gripper fix retains checked geometric vectors and inactive cones are scoped explicitly',
  hardware_test='NOT_RUN',physical_ab_closed_loop='NOT_RUN',physical_full_workspace='NOT_RUN',
  npu_execution='FAILED_COMPILATION_GPU_DEFAULT_USER_ACCEPTED',uart_intermittent_issue='OPEN',
  formal_detection_map='NOT_RUN',formal_segmentation_miou='NOT_RUN',artifact_hashes=impl['artifacts'])
 (out/'evidence/validation_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 manifest=json.loads((out/'mode_ab_manifest.json').read_bytes())
 manifest.update(patch_id=summary['patch_id'],hotfix_id='startup_route_map_p4_1',task_abi=0x340e,route_abi=0xb001,
  source_commit_b=summary['source_b'],source_commit_giao_fast_paths=summary['source_giao_fast_paths'],
  source_checkpoint=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
  hardware_attempt=attempt,hardware_artifacts=impl['artifacts'])
 (out/'mode_ab_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 gpu=json.loads((ROOT/'board_evidence/mode_ab_p4/gpu_final/result.json').read_bytes())
 with (out/'metrics/metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f);w.writerow(['metric','value','unit','condition','evidence'])
  for n in ('physical_task_success','physical_response_latency','communication_rtt_error_rate','formal_AI_quality','continuous_visual_fps'):
   w.writerow([n,'NOT_RUN','','Requires attended physical/independent measurement','evidence/validation_summary.json'])
  w.writerow(['ROCm_pipeline_P50_P95_P99_max',json.dumps(gpu['quantiles_ms']['pipeline_total_ms']),'ms','9 saved frames; warm models; no camera or physical latency claim','board_evidence/mode_ab_p4/gpu_final/result.json'])
  w.writerow(['FPGA_utilization',json.dumps(impl['utilization']),'count','XC7Z020 full implementation','evidence/implementation/implementation_summary.json'])
  w.writerow(['FPGA_timing',json.dumps(impl['timing_ns']),'ns','Full routed setup/hold','evidence/implementation/implemented_reports/build_gate.txt'])
 seal(out);print('P4_COMPLETE_ASSEMBLED_AND_SEALED',out)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--implementation',default='a14');p.add_argument('--archive',action='store_true');a=p.parse_args()
 if a.archive:print(json.dumps(archive(a.out),indent=2))
 else:main(a.out.resolve(),a.implementation)
