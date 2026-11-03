"""UART-in-flight regression and preconnected D5 on unchanged real RTL."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
from mode_a_board_config import ROOT,ARM,backend_writes
from run_mode_a_startup_xsim import bench_source as previous_bench


def bench_source():
    text=previous_bench()
    text=text.replace('  reg rx_drive=1;', '  reg legacy_case=1,continuous_rx=0; reg [1:0] startup_mode=2;\n  reg rx_drive=1;')
    text=text.replace('if(rx_busy)$fatal(1,"FAIL: overlapping feedback requests at 50Hz");',
        'if(rx_busy && !legacy_case)$fatal(1,"FAIL: overlapping feedback requests at 50Hz");')
    text=text.replace("      wr(12'h004,2);", "      wr(12'h004,{30'd0,startup_mode});")
    start=text.index('    configure(2);');end=text.index('    sample_data=',start)
    sequence='''    // A second reply is actively arriving when the old host disables RX.
    // Slow JTAG turnaround is modelled by an OFF gap within the 324B reply.
    permit=1;startup_mode=2;configure(2);
    wait(query_count>=1);wait(rx_busy);wait(!rx_busy);
    wait(query_count>=2);wait(rx_busy);repeat(61_000)@(negedge clk);
    wr(12'h004,0);repeat(123_457)@(negedge clk);wr(12'h004,3);
    wait(!rx_busy);repeat(5000)@(negedge clk);rd(12'h00c,value);
    if(!(value&32'h40))$fatal(1,"FAIL: old OFF gap did not reproduce UART_FRAMING %h",value);
    $display("PASS: v071 OFF/re-enable during an in-flight 324B response reproduces UART_FRAMING 0x40");
    wr(12'h004,0);repeat(1000)@(negedge clk);

    // Cold configuration with D5 already high; LINE is initially unarmed.
    legacy_case=0;startup_mode=3;query_count=0;motion_count=0;configure(2);
    continuous_rx=1;
    sample_data=192'h000166660000000000000000000191ec000033330000199a;sample_valid=1;
    wait(query_count>=1);wait(rx_busy);wait(!rx_busy);repeat(5000)@(negedge clk);
    wr(12'h000,4);rd(12'h218,value);if((value&63)!=63)$fatal(1,"FAIL: preconnected snapshot mask");
    rd(12'h200,value);if(value!=1000)$fatal(1,"FAIL: preconnected snapshot native base");
    rd(12'h21c,value);if(value[31:16]==0)$fatal(1,"FAIL: preconnected snapshot sequence");
    rd(12'h008,value);if(!(value&8))$fatal(1,"FAIL: preconnected D5 not high");
    rd(12'h004,value);if(value!=3)$fatal(1,"FAIL: query stage was armed");
    if(motion_count!=0 || sample_ready)$fatal(1,"FAIL: unarmed LINE accepted motion despite pending sample");
    $display("PASS: preconnected D5 through reset/configuration, LINE ARM=0, native snapshot valid, queued sample blocked");

    wait(query_count>=2);wait(rx_busy);repeat(DIV*30)@(negedge clk);
    sample_valid=0;wr(12'h004,32'h103);
    if(!rx_busy)$fatal(1,"FAIL: ARM change did not exercise in-flight feedback");
    rd(12'h00c,value);if(value!=0)$fatal(1,"FAIL: error while arming within LINE");
    $display("PASS: LINE ARM=0->1 while response is in-flight, no OFF or receiver interruption");
    baseline_requests=query_count;
    // The real S2 planner offers its first sample one configured period
    // after RUN (planner_p2p_core.v); model that 20ms startup interval.
    repeat(2_000_000)@(negedge clk);

'''
    text=text[:start]+sequence+text[end:]
    text=text.replace('    wr(12\'h004,0);\n    $display("PASS: real',
        '    continuous_rx=0;wr(12\'h004,0);\n    $display("PASS: real')
    text=text.replace('  initial begin #800000000;', '''  always @(posedge clk) if(continuous_rx && rst_n && !dut.u_core.u_uart_rx.enable)
    $fatal(1,"FAIL: UART receiver disabled between precheck and motion");
  initial begin #800000000;''')
    return text


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    candidate=ROOT/'candidate/PLAN_NATIVE.json'
    if not candidate.exists():candidate=ROOT/'board_evidence/mode_a_board_plan_v070_a1/PLAN_NATIVE.json'
    plan=json.loads(candidate.read_text('utf-8'));writes=backend_writes(plan)
    words=[len(writes)]+[v for addr,data in writes for v in (addr-ARM,data)]
    (out/'config.mem').write_text(''.join(f'{v:08x}\n' for v in words),'ascii')
    bench=out/'tb_prewired.sv';bench.write_text(bench_source(),'utf-8')
    cf=out/'compile.f';cf.write_text('\n'.join(p.as_posix() for p in [*list((ROOT/'native_motion/rtl/robot').glob('*.v')),bench])+'\n','utf-8')
    commands=[]
    for label,tool,args in [('compile','xvlog',['-sv','-f',str(cf)]),('elaborate','xelab',['tb_roarm_rate','-s','prewired_v072','-O0','-mt','off']),('run','xsim',['prewired_v072','-runall'])]:
        cmd=['cmd.exe','/d','/c',str(Path('E:/Xilinx/2026.1/Vivado/bin')/(tool+'.bat')),*args]
        p=subprocess.run(cmd,cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
        text=(p.stdout+p.stderr).decode('utf-8',errors='replace');(out/(label+'.txt')).write_text(text,'utf-8')
        commands.append(dict(stage=label,exit_code=p.returncode));print(label,p.returncode,flush=True)
        if p.returncode or re.search(r'(ERROR:|Fatal:|FATAL:|FAIL:)',text):raise RuntimeError(text[-5000:])
    checks=[line for line in text.splitlines() if line.startswith('PASS:')]
    if len(checks)!=4:raise ValueError('Missing preconnected startup assertions')
    result=dict(passed=True,version='0.7.2',checks=checks,commands=commands,physical_robot=False,
        config_sha256=hashlib.sha256((out/'config.mem').read_bytes()).hexdigest(),
        bench_sha256=hashlib.sha256(bench.read_bytes()).hexdigest())
    (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
