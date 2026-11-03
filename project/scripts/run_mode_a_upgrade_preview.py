"""Exact source-sampling preview test, no camera or board access."""
from pathlib import Path
import argparse,subprocess,json,re,hashlib
ROOT=Path(__file__).resolve().parents[1]
def main():
 a=argparse.ArgumentParser();a.add_argument('--attempt',required=True);o=ROOT/('board_evidence/mode_a_upgrade_preview_'+a.parse_args().attempt);o.mkdir(parents=True,exist_ok=False)
 sources=[ROOT/'native_motion/rtl/camera'/n for n in ('preview_gray256.v','pl_letterbox_640x480.v')]+[ROOT/'native_motion/sim/mode_a_upgrade/tb_preview256.sv']
 for label,tool,args in [('compile','xvlog',['-sv',*sources]),('elab','xelab',['tb_preview256','-s','preview','-O0','-mt','off']),('run','xsim',['preview','-runall'])]:
  tokens=['E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*map(str,args)];cmd='cmd.exe /d /s /c '+chr(34)+' '.join(chr(34)+x+chr(34) for x in tokens)+chr(34)
  r=subprocess.run(cmd,cwd=o,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=240);t=(r.stdout+r.stderr).decode('utf-8',errors='replace');(o/(label+'.txt')).write_text(t,'utf-8');print(label,r.returncode,flush=True)
  if r.returncode or re.search(r'^(ERROR:|Fatal:|FATAL:|FAIL:)',t,re.M):raise RuntimeError(t[-4000:])
 checks=[x for x in t.splitlines() if x.startswith('PASS:')];assert checks
 (o/'RESULT.json').write_text(json.dumps(dict(passed=True,checks=checks,hardware_access=False,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}),indent=2),'utf-8')
if __name__=='__main__':main()
