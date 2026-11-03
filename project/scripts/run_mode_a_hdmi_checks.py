"""Focused HDMI regressions and rendered raster; no hardware access."""
from pathlib import Path
import argparse,hashlib,json,subprocess,shutil,re
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);args=ap.parse_args()
 out=ROOT/('board_evidence/mode_a_hdmi_sim_'+args.attempt);out.mkdir(parents=True,exist_ok=False)
 shutil.copyfile(ROOT/'native_motion/rtl/hdmi/mode_a_font.mem',out/'mode_a_font.mem')
 idx=json.loads((ROOT/'model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/golden_integer/index.json').read_text('utf-8'))['samples']
 num=next(i for i,x in enumerate(idx) if x['class_label']=='palm' and x['pipeline']['classifier']['class']=='palm')
 fixture=ROOT/'evidence/hdmi_fixtures/palm_small.mem'
 if not fixture.exists():fixture=ROOT/'board_evidence/mode_a_follow_vision_a2/fixtures'/f'{num:02d}_small.mem'
 shutil.copyfile(fixture,out/'palm_small.mem')
 hdmi=ROOT/'native_motion/rtl/hdmi'
 sources=list(hdmi.glob('*.v'))+[ROOT/'native_motion/sim/mode_a_hdmi'/n for n in ('tb_display_cdc.sv','tb_framebuffer.sv','tb_renderer.sv')]+[ROOT/'sim/hdmi/tb_tmds_encoder.v',ROOT/'sim/hdmi/tb_video_timing_640x480.v']
 records=[]
 def run(label,tool,argv):
  cmd=['cmd.exe','/d','/c','E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*map(str,argv)]
  r=subprocess.run(cmd,cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=240)
  txt=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/(label+'.txt')).write_text(txt,'utf-8');print(label,r.returncode,flush=True)
  if r.returncode or re.search(r'^(ERROR:|FATAL:|Fatal:|FAIL:)',txt,re.M):raise RuntimeError(txt[-4000:])
  records.append(dict(label=label,exit_code=r.returncode));return txt
 run('compile','xvlog',['-sv','-i',hdmi,*sources])
 checks=[]
 for top in ('tb_display_cdc','tb_framebuffer','tb_renderer','tb_tmds_encoder','tb_video_timing_640x480'):
  run(top+'_elab','xelab',[top,'-s',top,'-O0','-mt','off'])
  txt=run(top,'xsim',[top,'-runall']);passed=[s for s in txt.splitlines() if s.startswith('PASS:')];assert passed;checks+=passed
 from PIL import Image
 raw=(out/'preview.rgb').read_bytes();assert len(raw)==640*480*3
 Image.frombytes('RGB',(640,480),raw).save(out/'HDMI_PREVIEW.png')
 result=dict(passed=True,checks=checks,hardware_access=False,preview='RTL raster, real captured fixture, injected WAIT_PALM status',commands=records,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
 (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
