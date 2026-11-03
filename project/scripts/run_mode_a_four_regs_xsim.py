from pathlib import Path
import sys,json,subprocess,re,hashlib
R=Path(__file__).resolve().parents[1];o=R/('board_evidence/mode_a_four_regs_'+sys.argv[1]);o.mkdir(parents=True,exist_ok=False)
files=[R/'native_motion/rtl/robot/s4_task_regs.v',R/'native_motion/rtl/robot/hand_align_region_lut.v',R/'native_motion/sim/mode_a_four/tb_four_regs.sv']
for label,tool,args in [('compile','xvlog',['-sv',*map(str,files)]),('elab','xelab',['tb_handalign_regs','-s','regs','-O0','-mt','off']),('run','xsim',['regs','-runall'])]:
 p=subprocess.run(['cmd.exe','/d','/c','E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*args],cwd=o,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
 t=(p.stdout+p.stderr).decode('utf-8',errors='replace');(o/(label+'.txt')).write_text(t);print(label,p.returncode,flush=True)
 if p.returncode or re.search('(ERROR:|Fatal:|FATAL:)',t):raise RuntimeError(t[-4000:])
assert 'PASS:' in t
(o/'RESULT.json').write_text(json.dumps(dict(passed=True,checks=[x for x in t.splitlines() if x.startswith('PASS:')],files={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),indent=2))
