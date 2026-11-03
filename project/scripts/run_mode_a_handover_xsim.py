"""Targeted ABI3406 FSM XSim; no actual hardware."""
from pathlib import Path
import subprocess,hashlib,json,re,time,argparse
ROOT=Path(__file__).resolve().parents[1]


def main(attempt):
    if not re.fullmatch('a[0-9]+',attempt):raise ValueError(attempt)
    out=ROOT/('board_evidence/mode_a_handover_v080_xsim_'+attempt);out.mkdir(parents=True,exist_ok=False)
    files=[ROOT/'native_motion/rtl/robot/s4_task_fsm.v',ROOT/'native_motion/sim/mode_a_handover_v080/tb_s4_handover.sv'];rows=[]
    for label,tool,args in [('compile','xvlog',['-sv',*map(str,files)]),('elaborate','xelab',['tb_s4_handover','-s','timed','-O0','-mt','off']),('run','xsim',['timed','-runall'])]:
        cmd=['cmd.exe','/d','/c',str(Path('E:/Xilinx/2026.1/Vivado/bin')/(tool+'.bat')),*args];t=time.monotonic()
        r=subprocess.run(cmd,cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
        (out/(label+'.txt')).write_bytes(r.stdout+r.stderr);text=(r.stdout+r.stderr).decode('utf-8',errors='replace')
        rows.append(dict(stage=label,exit_code=r.returncode,wall_s=time.monotonic()-t));print(label,r.returncode,flush=True)
        if r.returncode or re.search(r'(FATAL:|Fatal:|FAIL:|ERROR:)',text):raise RuntimeError(text[-5000:])
    result=dict(passed=True,kind='XSIM_FSM_WITH_MOCK_MOTION_LINK',checks=[s for s in text.splitlines() if s.startswith('PASS:')],commands=rows,
        source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files},physical_robot=False)
    (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',default='a1');main(ap.parse_args().attempt)
