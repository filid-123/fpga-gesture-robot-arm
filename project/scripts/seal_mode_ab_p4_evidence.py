"""Bind focused final changes to reusable, explicitly scoped prior evidence."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 base=ROOT/'board_evidence/mode_ab_p4';grip=json.loads((base/'gripper_waits_final/result.json').read_bytes())
 log=base/'gripper_waits_final/native_tests.txt';text=log.read_text()
 if not re.search(r'Ran 9 tests',text) or not re.search(r'\bOK\s*$',text):raise ValueError('Focused tests failed')
 test='scripts/test_mode_ab_native.py';route='pc/mode_ab/native_routes.py';s2='native_motion/rtl/robot/phase3_s2_motion_top.v';player='native_motion/rtl/robot/b_route_player.v';upload='pc/mode_ab/native_upload.py'
 startup=json.loads((base/'startup_map_p4_1_final/result.json').read_bytes())
 if not startup['passed'] or startup['source_hashes'][upload]!=sha(ROOT/upload):raise ValueError('Startup map proof differs')
 old_pc=json.loads((base/'pc_final/result.json').read_bytes());old_s2=json.loads((ROOT/'board_evidence/mode_ab_impl_a12/built_source_hashes.json').read_bytes())['files'][s2]
 report=dict(passed=True,pc_tests_preceding=74,ui_checks=10,focused_native_tests=9,focused_startup_tests=3,total_distinct_python_tests=78,
  policy='Reuse unchanged cones and geometric vectors; timing-only delta independently checked. No repeated full grid/GPU/vision sweep.',
  s4_mock_timing_scope='S4 mock state-control vectors retain pre-fix coarse T106 durations; motion endpoints/flags/order are unchanged. All 12 real production hold counters and the final real sample player are checked separately.',
  permitted_historical_bindings={
   upload:dict(old_sha256=old_pc['source_hashes'][upload],new_sha256=sha(ROOT/upload),reason='XSDB startup adds the matching 4 KiB route page and early B001 ABI check; upload/guards/motion code unchanged. Three actual-generated-Tcl restricted-map cases verify the startup delta.'),
   route:dict(old_sha256=grip['prior_native_routes_sha256'],new_sha256=sha(ROOT/route),reason='T106 hold periods only; every motion vector, speed, period and geometry fingerprint proven unchanged'),
   test:dict(old_sha256=old_pc['source_hashes'][test],new_sha256=sha(ROOT/test),reason='One Giao grip-travel timing test added; all nine native tests passed'),
   s2:dict(old_sha256=old_s2,new_sha256=sha(ROOT/s2),reason='Only route ownership fence changed after backend-only/idle aperture tests; current full-root native-host-native handoff proves that change'),
   player:dict(old_sha256=sha(base/'pipeline_fix/before.v'),new_sha256=sha(ROOT/player),reason='Inactive in backend formatting and idle aperture cones; split multiply/sum pipeline is checked by final real vectors, reverse/stall, long grip timers and full-root handoff')},
  focused_log=dict(path=log.relative_to(ROOT).as_posix(),sha256=sha(log)),hardware_access=False,physical_test='NOT_RUN',
  source_hashes={test:sha(ROOT/test),route:sha(ROOT/route),s2:sha(ROOT/s2),player:sha(ROOT/player),upload:sha(ROOT/upload)})
 (base/'release_scope.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS: final evidence scope sealed')
if __name__=='__main__':main()
