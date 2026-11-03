"""Focused production-width T106 hold timer test; no physical devices."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from test_mode_b_route_rtl import BENCH

def main(out):
 out.mkdir(parents=True,exist_ok=False);periods=[];inputs={}
 for name in ('red_cube','eraser','small_canister'):
  p=ROOT/'candidate/mode_ab/native_profiles'/name/'normal.json';c=json.loads(p.read_bytes())
  inputs[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
  periods.extend(c['native_program']['descriptors'][(16+i)*4+1] for i in (1,3,9,15))
 t=BENCH[:BENCH.index('integer b,i,j,k,n;')]
 t+='\nreg[31:0] periods[0:11];integer i,j,b,k;reg[31:0]v;\n'
 t+=r'''
initial begin
 $readmemh("periods.mem",periods);repeat(4)@(negedge clk);rst=1;
 for(k=0;k<12;k=k+1)begin
  write(0,1,0);write(28,1,0);write(16,7,0);write(20,0,0);
  for(i=0;i<6;i=i+1)write(128+i*4,0,0);
  for(i=0;i<6;i=i+1)begin write(16,i,0);write(20,0,0);write(128,0,0);end
  write(16,6,0);
  for(i=0;i<192;i=i+1)begin
   v=0;
   if((i%64)<4)case(i%4)0:v=1<<16;1:v=periods[k];2:v=(1<<24)|(5<<16)|40;3:v=(1<<24)|(20<<16)|300;endcase
   write(20,i,0);write(128,v,0);
  end
  write(0,2,0);command(7,32<<4,0);
  wait(dut.countdown>100000000&&!dut.drain);
  repeat(500)@(negedge clk);
  if(st!=2||err||dut.countdown<periods[k]-1000)$fatal(1,"Long grip timer truncated or incorrectly treated as downstream stall");
  // Skip elapsed wall time only after proving the full-width load/decrement.
  // No synthesizable code or production timer constant is changed.
  @(negedge clk);dut.countdown=3;wait(st==4);@(negedge clk);
 end
 $display("PASS: all 12 actual production T106 waits exceed one second, retain full 32-bit cycle counts, finish and do not trigger downstream-stall protection");$finish;
end
initial begin #10000000;$fatal(1,"Grip timer test timeout");end
endmodule
'''
 (out/'tb.sv').write_text(t);(out/'periods.mem').write_text(''.join(f'{v:08x}\n' for v in periods))
 files=[ROOT/'native_motion/rtl/robot'/n for n in ('b_route_ram.v','b_route_player.v')]+[out/'tb.sv'];records=[]
 for label,tool,args in [('compile','xvlog',['-sv',*files]),('elaborate','xelab',['tb','-s','grip_waits','-O0','-mt','off']),('run','xsim',['grip_waits','-runall'])]:
  p=subprocess.run(['cmd.exe','/d','/c','E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*map(str,args)],cwd=out,capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
  text=(p.stdout+p.stderr).decode('utf-8',errors='replace');(out/(label+'.txt')).write_text(text);records.append(dict(stage=label,exit_code=p.returncode))
  if p.returncode or re.search('(ERROR:|Fatal:|FATAL:|FAIL:)',text):raise RuntimeError(text[-4000:])
 result=dict(passed=True,checks=[x for x in text.splitlines() if x.startswith('PASS:')],production_period_cycles=periods,
  commands=records,inputs=inputs,source_hashes={f.relative_to(ROOT).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in files},hardware_access=False)
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS: 12 production-width grip timers')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out.resolve())
