"""Real115200 T102200/6 and324-byte T1051 at50Hz on the actual backend RTL."""
from pathlib import Path
import hashlib,json,re,subprocess
from mode_a_board_config import ROOT,backend_writes,ARM


def main():
    out=ROOT/'board_evidence/mode_a_board_uart_xsim_a1';out.mkdir(exist_ok=False)
    plan=json.loads((ROOT/'board_evidence/mode_a_board_plan_v070_a1/PLAN_NATIVE.json').read_text('utf-8'))
    writes=backend_writes(plan);vals=[len(writes)]+[v for a,n in writes for v in (a-ARM,n)]
    (out/'config.mem').write_text(''.join(f'{v:08x}\n' for v in vals),'ascii')
    source=(ROOT/'native_motion/sim/mode_a_v3/tb_roarm_rate.sv').read_text('utf-8').replace('\\"acc\\":10','\\"acc\\":6')
    if source==(ROOT/'native_motion/sim/mode_a_v3/tb_roarm_rate.sv').read_text('utf-8'):raise ValueError('Expected UART template')
    bench=out/'tb_board_uart.sv';bench.write_text(source,'utf-8')
    files=list((ROOT/'native_motion/rtl/robot').glob('*.v'))+[bench];cf=out/'compile.f';cf.write_text('\n'.join(p.as_posix() for p in files)+'\n','utf-8')
    commands=[]
    for label,tool,args in [('compile','xvlog',['-sv','-f',str(cf)]),('elaborate','xelab',['tb_roarm_rate','-s','board_uart','-O0','-mt','off']),('run','xsim',['board_uart','-runall'])]:
        cmd=['cmd.exe','/d','/c',str(Path('E:/Xilinx/2026.1/Vivado/bin')/(tool+'.bat')),*args]
        r=subprocess.run(cmd,cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300);txt=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/(label+'.txt')).write_text(txt,'utf-8')
        commands.append(dict(stage=label,exit_code=r.returncode));print(label,r.returncode,flush=True)
        if r.returncode or re.search(r'(ERROR:|Fatal:|FATAL:|FAIL:)',txt):raise RuntimeError(txt[-5000:])
    if 'PASS:' not in txt:raise ValueError('No UART PASS')
    (out/'RESULT.json').write_text(json.dumps(dict(passed=True,checks=[s for s in txt.splitlines() if s.startswith('PASS:')],commands=commands,physical_robot=False,config_sha256=hashlib.sha256((out/'config.mem').read_bytes()).hexdigest()),indent=2)+'\n','utf-8')
    print('UART200_ACC6_50HZ_PASS')


if __name__=='__main__':main()
