"""Reproduce the v0.7.0 mode fault and verify v0.7.1 on actual backend RTL."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
from mode_a_board_config import ROOT,ARM,backend_writes


def bench_source():
    text=(ROOT/'native_motion/sim/mode_a_v3/tb_roarm_rate.sv').read_text('utf-8')
    text=text.replace('\\"acc\\":10','\\"acc\\":6')
    text=text.replace('task wr(input [11:0] addr,input [31:0] data);',
        'task wr_checked(input [11:0] addr,input [31:0] data,input [1:0] expected_response);')
    text=text.replace('if(bresp!==0)$fatal(1,"FAIL: write %03h response %d",addr,bresp);',
        'if(bresp!==expected_response)$fatal(1,"FAIL: write %03h response %d expected %d",addr,bresp,expected_response);')
    marker='  task rd(input [11:0] addr,output [31:0] data);'
    text=text.replace(marker,'''  task wr(input [11:0] addr,input [31:0] data);
    begin wr_checked(addr,data,2'b00);end
  endtask
'''+marker)
    old='''    wr(12'h004,0);repeat(100)@(negedge clk);
    permit=1;repeat(100)@(negedge clk);wr(12'h004,32'h3);'''
    new='''    wr(12'h000,4);rd(12'h218,value);
    if((value&63)!=63)$fatal(1,"FAIL: snapshot mask before D5");
    rd(12'h200,value);if(value!=1000)$fatal(1,"FAIL: snapshot native base");
    rd(12'h21c,ignored);if(ignored[31:16]==0)$fatal(1,"FAIL: first snapshot sequence");
    wait(query_count>=2);wait(rx_busy);wait(!rx_busy);repeat(5000)@(negedge clk);
    wr(12'h000,4);rd(12'h21c,value);
    if(value[31:16]<=ignored[31:16])$fatal(1,"FAIL: refreshed snapshot sequence");
    if(motion_count!=0 || permit!=0)$fatal(1,"FAIL: STEP1 emitted motion");
    $display("PASS: D5-low MONITOR native feedback and refreshed six-axis snapshots, zero T102");
    permit=1;repeat(1_000_000)@(negedge clk);
    rd(12'h008,value);if(!(value&8))$fatal(1,"FAIL: D5 not recognized");
    if(motion_count!=0)$fatal(1,"FAIL: D5 alone emitted motion");
    wr_checked(12'h004,32'h103,2'b10);
    rd(12'h00c,value);if(!(value&32'h4000))$fatal(1,"FAIL: missing legacy CONTROL error");
    $display("PASS: exact v070 MONITOR->LINE|ARM request returns AXI SLVERR / CONTROL error");
    wr(12'h004,0);guard=0;rd(12'h008,value);
    while(((value>>12)&3)!=0 || (value&2))begin
      rd(12'h008,value);guard=guard+1;if(guard>100000)$fatal(1,"FAIL: OFF acknowledgement");
    end
    wr(12'h000,2);rd(12'h00c,value);if(value!=0)$fatal(1,"FAIL: recovery of expected legacy error");
    wr(12'h004,32'h3);'''
    if old not in text:raise ValueError('UART bench mode sequence changed')
    text=text.replace(old,new)
    text=text.replace('    baseline_requests=query_count;',
        '    $display("PASS: acknowledged MONITOR->OFF->LINE unarmed prime->LINE|ARM, no AXI error");\n    baseline_requests=query_count;')
    return text


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    candidate=ROOT/'candidate/PLAN_NATIVE.json'
    if not candidate.exists():candidate=ROOT/'board_evidence/mode_a_board_plan_v070_a1/PLAN_NATIVE.json'
    plan=json.loads(candidate.read_text('utf-8'));writes=backend_writes(plan)
    words=[len(writes)]+[v for addr,data in writes for v in (addr-ARM,data)]
    (out/'config.mem').write_text(''.join(f'{v:08x}\n' for v in words),'ascii')
    bench=out/'tb_startup.sv';bench.write_text(bench_source(),'utf-8')
    cf=out/'compile.f';cf.write_text('\n'.join(p.as_posix() for p in [*list((ROOT/'native_motion/rtl/robot').glob('*.v')),bench])+'\n','utf-8')
    commands=[]
    for label,tool,args in [('compile','xvlog',['-sv','-f',str(cf)]),('elaborate','xelab',['tb_roarm_rate','-s','startup_v071','-O0','-mt','off']),('run','xsim',['startup_v071','-runall'])]:
        cmd=['cmd.exe','/d','/c',str(Path('E:/Xilinx/2026.1/Vivado/bin')/(tool+'.bat')),*args]
        p=subprocess.run(cmd,cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
        text=(p.stdout+p.stderr).decode('utf-8',errors='replace');(out/(label+'.txt')).write_text(text,'utf-8')
        commands.append(dict(stage=label,exit_code=p.returncode));print(label,p.returncode,flush=True)
        if p.returncode or re.search(r'(ERROR:|Fatal:|FATAL:|FAIL:)',text):raise RuntimeError(text[-5000:])
    checks=[line for line in text.splitlines() if line.startswith('PASS:')]
    if len(checks)!=4:raise ValueError('Missing startup regression assertions')
    result=dict(passed=True,version='0.7.1',checks=checks,commands=commands,physical_robot=False,
        config_sha256=hashlib.sha256((out/'config.mem').read_bytes()).hexdigest(),
        bench_sha256=hashlib.sha256(bench.read_bytes()).hexdigest())
    (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
