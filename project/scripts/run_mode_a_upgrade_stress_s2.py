"""Check all 159 accelerated legs on actual S2 RTL against independent samples.

Only the testbench sample period is reduced to 512 cycles. Native positions,
N/Na/profile, production global VMAX/AMAX and expected Q16 samples are exact.
"""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
from mode_a_upgrade_backend import ROOT,TASK,task_writes

TB=r'''
`timescale 1ns/1ps
module tb_speed15_s2;
reg clk=0;always #5 clk=~clk;
reg rst_n=0,start=0,clear=0;integer cc=0,held_checks=0,pause_checks=0;always @(posedge clk)cc<=cc+1;wire ready=(cc%257)>50;wire pause=(cc%4096)==1000;wire resume=(cc%4096)==1150;reg pv=0,pr=0;reg[191:0]pd;
reg[15:0] n=0,na=0;
wire[2:0] ch,state,err_code,err_channel;
wire[1:0] field;
reg[31:0] cfg[0:23];wire[31:0] cfg_data=cfg[ch*4+field];
reg[191:0] last=0;
wire valid,computing,err,done,late;
wire[191:0] data;wire[15:0] index;
always @(posedge clk)if(rst_n)begin if(pv && !pr)begin if(data!==pd || !valid)$fatal(1,"FAIL: stalled offer changed");held_checks<=held_checks+1;end pv<=valid;pr<=ready;pd<=data;if(pause)pause_checks<=pause_checks+1;end

reg[31:0] moves[0:8191];reg[31:0] golden[0:131071];
planner_p2p_core #(.SMOOTH_PROFILE(1)) dut(.clk(clk),.rst_n(rst_n),.cmd_start(start),.cmd_pause(pause),.cmd_resume(resume),
 .cmd_estop(1'b0),.cmd_clear(clear),.cfg_n_samples(n),.cfg_accel_samples(na),.cfg_profile(1'b1),
 .cfg_period_cycles(32'd512),.cfg_stall_timeout(32'd50000000),.cfg_ch(ch),.cfg_field(field),.cfg_data(cfg_data),
 .last_delivered(last),.last_valid(1'b1),.m_valid(valid),.m_ready(ready),.m_data(data),.state(state),
 .computing(computing),.sample_index(index),.err_pulse(err),.err_code(err_code),.err_channel(err_channel),
 .done_pulse(done),.late_pulse(late));
integer m,c,k,off=1,g=1,seen=0,cycles,total=0;
initial begin
 $readmemh("moves.mem",moves);$readmemh("golden.mem",golden);
 repeat(10)@(negedge clk);rst_n=1;repeat(5)@(negedge clk);
 for(m=0;m<moves[0];m=m+1)begin
  n=moves[off];na=moves[off+1];off=off+2;
  for(c=0;c<24;c=c+1)begin cfg[c]=moves[off];off=off+1;end
  for(c=0;c<6;c=c+1)last[c*32+:32]=cfg[c*4];
  @(negedge clk);start=1;@(negedge clk);start=0;seen=0;cycles=0;
  while(seen<n)begin
   @(posedge clk);cycles=cycles+1;
   if(err || state==5 || state==6)$fatal(1,"FAIL: move %d S2 error %d channel %d",m,err_code,err_channel);
   if(valid && ready)begin
    if(index!=seen+1)$fatal(1,"FAIL: sample index");
    for(c=0;c<6;c=c+1)begin
     if(data[c*32+:32]!==golden[g])$fatal(1,"FAIL: move %d sample %d ch %d got %h expected %h",m,seen,c,data[c*32+:32],golden[g]);g=g+1;
    end
    last<=data;seen=seen+1;total=total+1;
   end
   if(cycles>n*1024+2000)$fatal(1,"FAIL: move deadline");
  end
  @(negedge clk);cycles=0;
  while(state!=4)begin @(negedge clk);cycles=cycles+1;if(cycles>100)$fatal(1,"FAIL: completion");end
  for(c=0;c<6;c=c+1)if(last[c*32+:32]!==cfg[c*4+1])$fatal(1,"FAIL: exact endpoint");
  clear=1;@(negedge clk);clear=0;repeat(4)@(negedge clk);
 end
 if(held_checks==0 || pause_checks==0)$fatal(1,"FAIL: no stress coverage");
 if(total!=golden[0])$fatal(1,"FAIL: total sample count");
 $display("PASS: quintic/backpressure/pause actual S2 RTL all %0d legs, %0d exact six-axis samples, production VMAX/AMAX and endpoints",moves[0],total);
 $finish;
end
initial begin #1000000000;$fatal(1,"FAIL: global timeout");end
endmodule
'''


def main(attempt,candidate=None):
    if not re.fullmatch('a[0-9]+',attempt):raise ValueError(attempt)
    out=ROOT/('board_evidence/mode_a_upgrade_stress_s2_'+attempt);out.mkdir(parents=True,exist_ok=False)
    p=candidate or ROOT/'candidate/bank1/PLAN_NATIVE.json'
    if not p.exists():p=ROOT/'board_evidence/mode_a_upgrade_plan_a3/bank1/PLAN_NATIVE.json'
    plan=json.loads(p.read_text('utf-8'));t=p.with_name('S4_NATIVE_CANDIDATE.json')
    writes=dict(task_writes(plan,json.loads(t.read_text('utf-8'))))
    moves=[];gold=[];count=0
    for key in ('paths','hover_paths','return_paths'):
        for route in plan[key]:
            for i,leg in enumerate(route['legs']):
                count+=1;moves.extend([leg['n'],leg['na']])
                for ch in range(6):moves.extend([leg['start_q16'][ch],leg['target_q16'][ch],writes[TASK+0xb0+4*ch],writes[TASK+0xc8+4*ch]])
                rows=[r for r in route['samples'] if r['segment']==i];assert len(rows)==leg['n']
                for r in rows:gold.extend(r['q16'])
    samples=len(gold)//6
    for name,words in [('moves.mem',[count]+moves),('golden.mem',[samples]+gold)]:
        (out/name).write_text(''.join(f'{x&0xffffffff:08x}\n' for x in words),'ascii')
    bench=out/'tb_speed15_s2.sv';bench.write_text(TB.replace('moves[0:8191]',f'moves[0:{len(moves)}]').replace('golden[0:131071]',f'golden[0:{len(gold)}]'),'utf-8')
    files=[ROOT/'native_motion/rtl/robot'/n for n in ('planner_p2p_core.v','planner_seq_div.v','planner_seq_mult.v')]+[bench]
    cf=out/'compile.f';cf.write_text('\n'.join(p.as_posix() for p in files)+'\n','utf-8');commands=[]
    for stage,tool,args in [('compile','xvlog',['-sv','-f',str(cf)]),('elaborate','xelab',['tb_speed15_s2','-s','speed15_s2','-O0','-mt','off']),('run','xsim',['speed15_s2','-runall'])]:
        cmd=['cmd.exe','/d','/c','E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*args]
        r=subprocess.run(cmd,cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
        text=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/(stage+'.txt')).write_text(text,'utf-8')
        commands.append(dict(stage=stage,exit_code=r.returncode));print(stage,r.returncode,flush=True)
        if r.returncode or re.search(r'(ERROR:|Fatal:|FATAL:|FAIL:)',text):raise RuntimeError(text[-4000:])
    assert 'PASS:' in text
    result=dict(passed=True,legs=count,samples=samples,axes=6,checks=[x for x in text.splitlines() if x.startswith('PASS:')],commands=commands,
        native_plan_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bench_sha256=hashlib.sha256(bench.read_bytes()).hexdigest(),
        production_period_cycles=2000000,testbench_period_cycles=512,physical_robot=False)
    (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',default='a1');ap.add_argument('--candidate',type=Path);a=ap.parse_args();main(a.attempt,a.candidate)
