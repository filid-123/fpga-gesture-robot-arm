"""Bit-exact dual-channel classifier with true dual-read ROM, no hardware."""
from pathlib import Path
import argparse,json,subprocess,shutil,re,hashlib
from run_mode_a_v3_checks import source_list,PKG
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);a=ap.parse_args()
 out=ROOT/('board_evidence/mode_a_upgrade_classifier_'+a.attempt);out.mkdir(parents=True,exist_ok=False)
 for p in PKG.rglob('*.mem'):
  d=out/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,d)
 sources=source_list()+[ROOT/'native_motion/sim/mode_a_upgrade/tb_classifier_parallel.sv']
 for label,tool,args in [('compile','xvlog',['-sv','-i',ROOT/'native_motion/rtl/autonomous',*sources]),('elab','xelab',['tb_classifier_parallel','-s','classifier','-O0','-mt','off']),('run','xsim',['classifier','-runall'])]:
  tokens=['E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*map(str,args)];cmd='cmd.exe /d /s /c '+chr(34)+' '.join(chr(34)+v+chr(34) for v in tokens)+chr(34)
  r=subprocess.run(cmd,cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=1200)
  text=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/(label+'.txt')).write_text(text,'utf-8');print(label,r.returncode,flush=True)
  if r.returncode or re.search(r'^(ERROR:|Fatal:|FATAL:|FAIL:)',text,re.M):raise RuntimeError(text[-5000:])
 checks=[x for x in text.splitlines() if x.startswith('PASS:')];assert len(checks)==27
 cycles=list(map(int,re.findall('cycles=([0-9]+)',text)))
 result=dict(passed=True,samples=26,checks=checks,cycles=cycles,baseline_cycles=750170,hardware_access=False,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
 (out/'RESULT.json').write_text(json.dumps(result,indent=2),'utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
