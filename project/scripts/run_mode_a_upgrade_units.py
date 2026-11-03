from pathlib import Path
import argparse,hashlib,json,subprocess,re,shutil
ROOT=Path(__file__).resolve().parents[1]
def main(attempt):
 out=ROOT/('board_evidence/mode_a_upgrade_units_'+attempt);out.mkdir(parents=True,exist_ok=False)
 candidate=ROOT/'candidate/S4_BANKED_CANDIDATE.json'
 if not candidate.exists():candidate=ROOT/'board_evidence/mode_a_upgrade_plan_a3/S4_BANKED_CANDIDATE.json'
 table=json.loads(candidate.read_text('utf-8'));words=[]
 for bank in table['keypoint_banks']:
  values=[v for q in bank for v in q+[0,0]];words+=values+[0]*(512-len(values))
 (out/'keypoints.mem').write_text(''.join(f'{v&0xffffffff:08x}\n' for v in words),'ascii')
 files=[ROOT/p for p in ('native_motion/rtl/hdmi/cycles_to_ms8.v','native_motion/rtl/robot/hand_y_step_map.v','native_motion/rtl/robot/s4_task_regs.v','native_motion/rtl/integration/mode_a_observer.v','native_motion/sim/mode_a_upgrade/tb_upgrade_units.sv')]
 records=[]
 for label,tool,args in [('compile','xvlog',['-sv',*map(str,files)]),('elab','xelab',['tb_upgrade_units','-s','units','-O0','-mt','off']),('run','xsim',['units','-runall'])]:
  r=subprocess.run(['cmd.exe','/d','/c','E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*args],cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
  txt=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/(label+'.txt')).write_text(txt);print(label,r.returncode,flush=True);records.append(dict(label=label,exit_code=r.returncode))
  if r.returncode or re.search('(ERROR:|Fatal:|FATAL:|FAIL:)',txt):raise RuntimeError(txt[-4000:])
 checks=[x for x in txt.splitlines() if x.startswith('PASS:')];assert len(checks)==4
 (out/'RESULT.json').write_text(json.dumps(dict(passed=True,checks=checks,commands=records,hardware_access=False,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),indent=2)+'\n');print(checks)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);main(ap.parse_args().attempt)
