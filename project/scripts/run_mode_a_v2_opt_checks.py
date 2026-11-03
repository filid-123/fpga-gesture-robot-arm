import sys,json,shutil
import run_mode_a_v3_checks as v
v.H=v.W/'board_evidence/mode_a_v2_vision_a3';v.ATTEMPT=sys.argv[2]
mode=sys.argv[1];j=v.Job('v2opt_'+mode)
if mode=='unit':
 benches=['native_motion/sim/hw_opt/'+n+'.sv' for n in ('tb_conv_acc_bram','tb_gesture_dwell_exp','tb_hand_align_exp','tb_overlap_ctrl')]
else:
 benches=['native_motion/sim/mode_a_v2/tb_stream_v3.sv']
 for p in (v.PKG/'golden_integer').glob('sample_*/*.mem'):
  dst=j.b/p.relative_to(v.W);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
j.compile(benches+(['native_motion/sim/mode_a_v2/baseline_generic_conv3x3.v'] if mode=='unit' else []))
for p in benches:j.simulate(v.Path(p).stem,['-testplusarg','ROOT='+(v.H/'fixtures').as_posix()])
(j.o/'RESULTS.json').write_text(json.dumps(dict(passed=True,mode=mode,benches=benches,physical_robot=False),indent=2))
