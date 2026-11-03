"""Exact large-N scalar-bound regression on production S2 RTL; no hardware."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
def main(attempt):
 if not re.fullmatch('a[0-9]+',attempt):raise ValueError(attempt)
 out=ROOT/('board_evidence/mode_a_upgrade_bounds_'+attempt);out.mkdir(parents=True,exist_ok=False)
 files=[ROOT/'native_motion/rtl/robot'/n for n in ('planner_p2p_core.v','planner_seq_div.v','planner_seq_mult.v')]+[ROOT/'native_motion/sim/mode_a_upgrade/tb_quintic_bounds.sv'];commands=[]
 for label,tool,args in [('compile','xvlog',['-sv',*map(str,files)]),('elab','xelab',['tb_quintic_bounds','-s','bounds','-O0','-mt','off']),('run','xsim',['bounds','-runall'])]:
  r=subprocess.run(['cmd.exe','/d','/c','E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*args],cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
  txt=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/(label+'.txt')).write_text(txt,'utf-8');commands.append(dict(stage=label,exit_code=r.returncode));print(label,r.returncode,flush=True)
  if r.returncode or re.search('(ERROR:|Fatal:|FATAL:|FAIL:)',txt):raise RuntimeError(txt[-4000:])
 checks=[x for x in txt.splitlines() if x.startswith('PASS:')];assert checks
 (out/'RESULT.json').write_text(json.dumps(dict(passed=True,checks=checks,commands=commands,hardware_access=False,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),indent=2)+'\n','utf-8')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);main(ap.parse_args().attempt)
