"""Real LUT/HandAlign core/S4 FSM with native 3-bank tables; mock motion link."""
from pathlib import Path
import argparse,json,re,subprocess,hashlib
ROOT=Path(__file__).resolve().parents[1]
def run(attempt):
 o=ROOT/('board_evidence/mode_a_v2_task_'+attempt);o.mkdir(parents=True,exist_ok=False)
 candidate=ROOT/'candidate/S4_BANKED_CANDIDATE.json'
 if not candidate.exists():candidate=ROOT/'board_evidence/mode_a_v2_plan_a3/S4_BANKED_CANDIDATE.json'
 t=json.loads(candidate.read_text('utf-8'))
 words=[]
 for bank in t['keypoint_banks']:
  a=[v for q in bank for v in q+[0,0]];words+=a+[0]*(512-len(a))
 (o/'keypoints.mem').write_text(''.join(f'{v&0xffffffff:08x}\n' for v in words))
 (o/'segments.mem').write_text(''.join(f'{v:08x}\n' for kp,n,na,p,f in t['segments'] for v in ((f<<24)|(p<<16)|kp,(na<<16)|n)))
 src=ROOT/'native_motion/sim/mode_a_v2/tb_s4_handalign.sv';s=src.read_text()
 keys=[f'{ph}_{obj}' for ph in ('approach','grasp','lift') for obj in (1,2,3)]+['deliver','release','retreat']
 for i,key in enumerate(keys):
  first,count=t['descriptors'][key];s=re.sub(r'paths\['+str(i*12)+r'\+:12\]=.*?;',f"paths[{i*12}+:12]={{6'd{count},6'd{first}}};",s)
 # Map words encode PRE (6 bits), release/deliver (12 each), retreat (12).
 d=lambda k:(t['descriptors'][k][1]<<6)|t['descriptors'][k][0]
 w2=t['predelivery_kp']|(d('release')<<6)|(d('deliver')<<18)
 s=s.replace("mdata=(15)|(12'd557<<6)|(12'd97<<18)",f"mdata=32'd{w2}").replace("mdata=12'd353",f"mdata=32'd{d('retreat')}")
 bench=o/'tb_s4_handalign.sv';bench.write_text(s)
 files=[ROOT/'native_motion/rtl/robot'/n for n in ('s4_task_fsm.v','hand_align_target_core.v','hand_align_region_lut.v')]+[bench]
 commands=[]
 for label,tool,args in [('compile','xvlog',['-sv',*map(str,files)]),('elaborate','xelab',['tb_s4_handalign','-s','handalign','-O0','-mt','off']),('run','xsim',['handalign','-runall'])]:
  r=subprocess.run(['cmd.exe','/d','/c','E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*args],cwd=o,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
  txt=(r.stdout+r.stderr).decode('utf-8',errors='replace');(o/(label+'.txt')).write_text(txt);print(label,r.returncode,flush=True);commands.append(dict(label=label,exit_code=r.returncode))
  if r.returncode or re.search('(ERROR:|Fatal:|FATAL:|FAIL:)',txt):raise RuntimeError(txt[-4000:])
 assert txt.count('PASS:')==5
 result=dict(passed=True,checks=[x for x in txt.splitlines() if x.startswith('PASS:')],physical_robot=False,motion_link='MOCK',tick_cycles=32,production_timers_ms=[200,2000,500,1000],commands=commands,source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
 (o/'RESULT.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);run(ap.parse_args().attempt)
