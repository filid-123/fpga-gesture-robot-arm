"""Real S4 FSM/register RAM/core, with mocked motion transport only."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
def run(attempt):
 out=ROOT/('board_evidence/mode_a_restock_task_'+attempt);out.mkdir(parents=True,exist_ok=False)
 normal=ROOT/'candidate/S4_BANKED_CANDIDATE.json'
 if not normal.exists():normal=ROOT/'board_evidence/mode_a_upgrade_plan_a3/S4_BANKED_CANDIDATE.json'
 source=ROOT/'candidate/restock'
 if not source.exists():source=ROOT/'board_evidence/mode_a_restock_plan_a2'
 n=json.loads(normal.read_text('utf-8'));t=json.loads((source/'S4_RESTOCK_CANDIDATE.json').read_text('utf-8'))
 p=json.loads((source/'PLAN_NATIVE.json').read_text('utf-8'))
 banks=n['keypoint_banks'][:3]+[t['keypoints']]
 words=[]
 for bank in banks:
  data=[v for q in bank for v in q+[0,0]];words+=data+[0]*(512-len(data))
 def mem(name,data):(out/name).write_text(''.join(f'{v&0xffffffff:08x}\n' for v in data),'ascii')
 mem('keypoints.mem',words)
 segments=[]
 for bank in (n['segments'],t['segments']):
  data=[v for kp,ns,na,pr,f in bank for v in ((f<<24)|(pr<<16)|kp,(na<<16)|ns)];segments+=data+[0]*(128-len(data))
 mem('segments.mem',segments);mem('pair_timing.mem',[(v['na']<<16)|v['n'] for v in n['align_pairs']])
 desc=lambda d:(d['count']<<8)|d['first']|((d.get('release_kp') or 0)<<16)
 mem('restock_cfg.mem',[desc(t['prefix']),*[desc(d) for d in t['tails']]])
 q=next(l['target_q16'] for l in p['paths'][0]['legs'] if l['label']=='GRASP_SOURCE')[:]
 q[5]=round(p['open_native_rad']*65536);mem('source_open.mem',q)
 sources=[ROOT/'native_motion/rtl/robot'/name for name in ('s4_task_fsm.v','s4_task_regs.v','hand_align_region_lut.v','hand_align_target_core.v')]+[ROOT/'native_motion/sim/mode_a_restock/tb_restock.sv']
 commands=[]
 for label,tool,args in [('compile','xvlog',['-sv',*sources]),('elab','xelab',['tb_restock','-s','restock','-O0','-mt','off']),('run','xsim',['restock','-runall'])]:
  tokens=list(map(str,['E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*args]));cmd='cmd.exe /d /s /c "'+' '.join('"'+v+'"' for v in tokens)+'"'
  r=subprocess.run(cmd,cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
  text=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/(label+'.txt')).write_text(text,'utf-8');print(label,r.returncode,flush=True)
  commands.append(dict(label=label,command=cmd,exit_code=r.returncode))
  if r.returncode or re.search(r'^(ERROR:|FATAL:|Fatal:|FAIL:)',text,re.M):raise RuntimeError(text[-5000:])
 checks=[v for v in text.splitlines() if v.startswith('PASS:')];assert len(checks)==7
 (out/'RESULT.json').write_text(json.dumps(dict(passed=True,checks=checks,motion_transport='MOCK',table_memory='PRODUCTION_S4_REGS',commands=commands,
  source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},physical_test='NOT_RUN'),indent=2)+'\n','utf-8')
 print('\n'.join(checks))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);a=ap.parse_args();run(a.attempt)
