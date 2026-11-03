"""Small actual UNISIM serializer regression, separate from long ML replay."""
from pathlib import Path
import argparse,json,subprocess,re,hashlib
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);args=ap.parse_args()
 out=ROOT/('board_evidence/mode_a_hdmi_serializer_'+args.attempt);out.mkdir(parents=True,exist_ok=False)
 sources=[ROOT/'native_motion/rtl/hdmi/tmds_serializer_7series.v',ROOT/'native_motion/sim/mode_a_hdmi/tb_serializer.sv']
 for label,tool,args in [('compile','xvlog',['-sv','E:/Xilinx/2026.1/Vivado/data/verilog/src/glbl.v',*sources]),('elab','xelab',['tb_serializer','glbl','-L','unisims_ver','-L','secureip','-s','serial','-O0','-mt','off']),('run','xsim',['serial','-runall'])]:
  tokens=['E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*map(str,args)]
  cmd='cmd.exe /d /s /c '+chr(34)+' '.join(chr(34)+s+chr(34) for s in tokens)+chr(34)
  r=subprocess.run(cmd,cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=240)
  txt=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/(label+'.txt')).write_text(txt,'utf-8');print(label,r.returncode,flush=True)
  if r.returncode or re.search(r'^(ERROR:|FATAL:|Fatal:|FAIL:)',txt,re.M):raise RuntimeError(txt[-4000:])
 checks=[s for s in txt.splitlines() if s.startswith('PASS:')];assert checks
 (out/'RESULT.json').write_text(json.dumps(dict(passed=True,checks=checks,hardware_access=False,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}),indent=2),'utf-8')
if __name__=='__main__':main()
