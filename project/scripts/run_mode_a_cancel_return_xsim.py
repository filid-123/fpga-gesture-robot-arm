"""Actual S4 FSM, production native table, mock motion link and return scoreboard."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1]


def main(attempt):
    if not re.fullmatch('a[0-9]+',attempt):raise ValueError(attempt)
    out=ROOT/('board_evidence/mode_a_cancel_return_xsim_'+attempt);out.mkdir(parents=True,exist_ok=False)
    p=ROOT/'candidate/PLAN_NATIVE.json'
    if not p.exists():p=ROOT/'board_evidence/mode_a_cancel_shift_v082_plan_a1/PLAN_NATIVE.json'
    table=json.loads(p.with_name('S4_NATIVE_CANDIDATE.json').read_text('utf-8'))
    assert table['hold_policy'] is False and table['abi']['task']==0x3406
    (out/'keypoints.mem').write_text(''.join(f'{v&0xffffffff:08x}\n' for kp in table['keypoints'] for v in kp+[0,0]),'ascii')
    (out/'segments.mem').write_text(''.join(f'{v:08x}\n' for kp,n,na,prof,flags in table['segments'] for v in [(flags<<24)|(prof<<16)|kp,(na<<16)|n]),'ascii')
    files=[ROOT/'native_motion/rtl/robot/s4_task_fsm.v',ROOT/'native_motion/sim/mode_a_cancel_return_v082/tb_s4_cancel_return.sv'];commands=[]
    for stage,tool,args in [('compile','xvlog',['-sv',*map(str,files)]),('elaborate','xelab',['tb_s4_cancel_return','-s','cancel_return','-O0','-mt','off']),('run','xsim',['cancel_return','-runall'])]:
        cmd=['cmd.exe','/d','/c','E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*args]
        r=subprocess.run(cmd,cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
        text=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/(stage+'.txt')).write_text(text,'utf-8')
        commands.append(dict(stage=stage,exit_code=r.returncode));print(stage,r.returncode,flush=True)
        if r.returncode or re.search(r'(ERROR:|Fatal:|FATAL:|FAIL:)',text):raise RuntimeError(text[-5000:])
    assert text.count('PASS:')==7
    result=dict(passed=True,kind='ACTUAL_S4_FSM_NATIVE_TABLE_MOCK_MOTION_LINK',checks=[x for x in text.splitlines() if x.startswith('PASS:')],commands=commands,
        native_plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),source_hashes={f.relative_to(ROOT).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        table_capacity=table['capacity'],production_timers_ms=[1000,2000,500],testbench_tick_cycles=32,physical_robot=False)
    (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',default='a2');main(ap.parse_args().attempt)
