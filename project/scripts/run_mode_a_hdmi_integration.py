"""Ten real VGA inputs through production HDMI+vision+task integration."""
from pathlib import Path
import argparse,hashlib,json,subprocess,shutil,re
from run_mode_a_v3_checks import source_list,PKG
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);a=ap.parse_args()
 out=ROOT/('board_evidence/mode_a_hdmi_integration_'+a.attempt);out.mkdir(parents=True,exist_ok=False)
 paths=[ROOT/'native_motion/geometry_alpha_q16.mem',ROOT/'native_motion/rtl/autonomous/ov5640_vga_yuyv.mem',ROOT/'native_motion/rtl/hdmi/mode_a_font.mem']+[PKG/'quantized'/f for f in ('locator/model_rom_16k.mem','classifier/weights_all.mem','classifier/layer_descriptors.mem')]
 for p in paths:
  q=out/p.relative_to(ROOT);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
 bench=ROOT/'native_motion/sim/mode_a_hdmi/tb_hdmi_final_top.sv';sources=source_list()+[p for p in (ROOT/'native_motion/rtl/hdmi').glob('*.v') if p.name!='tmds_serializer_7series.v']+[ROOT/'native_motion/sim/mode_a_hdmi/serializer_sink.v',bench]
 fixtures=ROOT/'evidence/hdmi_fixtures'
 if not fixtures.exists():fixtures=ROOT/'board_evidence/mode_a_follow_vision_a2/fixtures'
 records=[]
 for label,tool,args in [('compile','xvlog',['E:/Xilinx/2026.1/Vivado/data/verilog/src/glbl.v','-sv','-i',ROOT/'native_motion/rtl/autonomous','-i',ROOT/'native_motion/rtl/hdmi',*sources]),('elab','xelab',['tb_hdmi_final_top','glbl','-L','unisims_ver','-L','secureip','-s','final','-O0','-mt','off']),('run','xsim',['final','-runall','-testplusarg','ROOT='+fixtures.as_posix()])]:
  tokens=['E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*map(str,args)]
  cmd='cmd.exe /d /s /c '+chr(34)+' '.join(chr(34)+t+chr(34) for t in tokens)+chr(34)
  r=subprocess.run(cmd,cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=1200)
  txt=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/(label+'.txt')).write_text(txt,'utf-8');print(label,r.returncode,flush=True)
  if r.returncode or re.search(r'^(ERROR:|FATAL:|Fatal:|FAIL:)',txt,re.M):raise RuntimeError(txt[-4000:])
  records.append(dict(label=label,exit_code=r.returncode))
 checks=[s for s in txt.splitlines() if s.startswith('PASS:')];assert len(checks)==12
 (out/'RESULT.json').write_text(json.dumps(dict(passed=True,checks=checks,hardware_access=False,serializer='INTEGRATION_SINK; real serializer validated separately with UNISIM',commands=records,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}),indent=2)+'\n','utf-8')
 print('PASS: production HDMI/vision/task integration')
if __name__=='__main__':main()
