"""Real UNISIM serializer -> independent TMDS receiver -> complete RGB raster."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);args=ap.parse_args()
 out=ROOT/('board_evidence/mode_a_tmds_raster_'+args.attempt);out.mkdir(parents=True,exist_ok=False)
 hd=ROOT/'native_motion/rtl/hdmi'
 shutil.copyfile(hd/'mode_a_font.mem',out/'mode_a_font.mem')
 sources=[hd/n for n in ('video_timing_640x480.v','video_timing_720p.v','mode_a_720p_canvas.v','mode_a_renderer.v','tmds_encoder.v','tmds_serializer_7series.v')]+[ROOT/'native_motion/sim/mode_a_hdmi/tb_tmds_720p.sv']
 commands=[]
 for label,tool,argv in [('compile','xvlog',['-sv','-i',hd,'E:/Xilinx/2026.1/Vivado/data/verilog/src/glbl.v',*sources]),('elab','xelab',['tb_tmds_720p','glbl','-L','unisims_ver','-L','secureip','-s','receiver','-O0','-mt','off']),('run','xsim',['receiver','-runall'])]:
  tokens=list(map(str,['E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*argv]));cmd='cmd.exe /d /s /c "'+' '.join('"'+t+'"' for t in tokens)+'"'
  started=time.monotonic();r=subprocess.run(cmd,cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=1200)
  txt=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/(label+'.txt')).write_text(txt,'utf-8')
  commands.append(dict(label=label,command=cmd,exit_code=r.returncode,wall_s=time.monotonic()-started));print(label,r.returncode,flush=True)
  if r.returncode or re.search(r'^(ERROR:|FATAL:|Fatal:|FAIL:)',txt,re.M):raise RuntimeError(txt[-5000:])
 checks=[s for s in txt.splitlines() if s.startswith('PASS:')];assert checks
 from PIL import Image
 data=(out/'receiver.rgb').read_bytes();assert len(data)==1280*720*3
 Image.frombytes('RGB',(1280,720),data).save(out/'RECEIVER_PREVIEW.png')
 import numpy as np
 legacy=ROOT/'board_evidence/mode_a_tmds_raster_baseline_a1/receiver.rgb'
 if not legacy.exists():legacy=ROOT/'evidence/display_baseline/receiver.rgb'
 old=np.frombuffer(legacy.read_bytes(),dtype=np.uint8).reshape(480,640,3)
 want=np.tile(np.array([11,20,33],dtype=np.uint8),(720,1280,1))
 want[:,160:1120,:]=old[np.arange(720)*2//3][:,np.arange(960)*2//3]
 actual=np.frombuffer(data,dtype=np.uint8).reshape(720,1280,3)
 assert np.array_equal(actual,want),f'Canvas pixel mismatches: {np.count_nonzero(actual!=want)}'
 checks.append('PASS: 1280x720 received frame equals full legacy UI scaled 3/2 and centered at x160, pixel exact; no horizontal wrap')
 result=dict(passed=True,checks=checks,hardware_access=False,commands=commands,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
 (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print('PHYSICAL_SERIAL_RASTER_PASS',flush=True)
if __name__=='__main__':main()
