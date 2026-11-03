from pathlib import Path
import sys,json,subprocess,re,hashlib
R=Path(__file__).resolve().parents[1];o=R/('board_evidence/mode_a_four_units_'+sys.argv[1]);o.mkdir(parents=True,exist_ok=False)
files=[R/'native_motion/rtl/robot/hand_align_region_lut.v',R/'native_motion/rtl/robot/hand_align_target_core.v',R/'native_motion/sim/mode_a_four/tb_accept_race.sv',R/'native_motion/sim/hw_opt/tb_hand_align_exp.sv']
for label,tool,args in [('compile','xvlog',['-sv',*map(str,files)]),('race_elab','xelab',['tb_accept_race','-s','race','-O0','-mt','off']),('race','xsim',['race','-runall']),('legacy_elab','xelab',['tb_hand_align_exp','-s','legacy','-O0','-mt','off']),('legacy','xsim',['legacy','-runall'])]:
 p=subprocess.run(['cmd.exe','/d','/c','E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*args],cwd=o,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
 t=(p.stdout+p.stderr).decode('utf-8',errors='replace');(o/(label+'.txt')).write_text(t);print(label,p.returncode,flush=True)
 if p.returncode or re.search('(ERROR:|Fatal:|FATAL:)',t):raise RuntimeError(t[-4000:])
(o/'RESULT.json').write_text(json.dumps(dict(passed=True,physical=False,source_hashes={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),indent=2))
