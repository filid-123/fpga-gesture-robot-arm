"""Cycle-level native route/RAM tests through real AXI and sample handshake."""
from pathlib import Path
import argparse,json,hashlib,subprocess,re
ROOT=Path(__file__).resolve().parents[1]
BENCH=r'''
`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;
reg rst=0,unlock=1,av=0,wv=0,br=1,arv=0,rr=1,cv=0,rev=0,ready=1;
reg[7:0] aa=0,ra=0;reg[31:0]wd=0;reg[3:0]ws=15;reg[2:0]cc=0;reg[15:0]stage=0;
reg[191:0]target=0,last=0;wire awr,wr,bv,arr,rv,cr,cd,ok,sv;wire[1:0]bp,rp;
wire[31:0]rd,err;wire[2:0]st;wire[15:0]ix,spd;wire[7:0]acc;wire grip,committed;
wire[191:0]q;reg pending=0,delivered=0;reg[191:0]buffered;integer outputs=0;
b_route_player #(.MIN_PERIOD(10))dut(.clk(clk),.rst_n(rst),.cfg_unlock(unlock),
.awaddr(aa),.awvalid(av),.awready(awr),.wdata(wd),.wstrb(ws),.wvalid(wv),.wready(wr),.bresp(bp),.bvalid(bv),.bready(br),
.araddr(ra),.arvalid(arv),.arready(arr),.rdata(rd),.rresp(rp),.rvalid(rv),.rready(rr),
.cmd_valid(cv),.cmd_ready(cr),.cmd_code(cc),.cmd_stage(stage),.reverse(rev),.cmd_target(target),.stall_timeout(32'd100),.cmd_done(cd),.cmd_ok(ok),
.state(st),.error(err),.sample_index(ix),.sample_valid(sv),.sample_ready(ready&&!pending),.delivered(delivered),.pending(pending),
.sample_data(q),.last_data(last),.speed(spd),.acceleration(acc),.gripper_only(grip),.committed_out(committed));
always @(posedge clk)begin
 delivered<=0;
 if(sv&&ready&&!pending)begin buffered<=q;pending<=1;end
 if(pending)begin last<=buffered;pending<=0;delivered<=1;outputs<=outputs+1;end
end
task write(input[7:0]a,input[31:0]v,input bit reject);
begin @(negedge clk);aa=a;wd=v;av=1;wv=1;
while(!(awr&&wr))@(negedge clk);@(negedge clk);av=0;wv=0;
while(!bv)@(negedge clk);if((bp!=0)!=reject)$fatal(1,"WRITE %h response %h",a,bp);@(negedge clk);end endtask
task read(input[7:0]a,input[31:0]v);
begin @(negedge clk);ra=a;arv=1;while(!arr)@(negedge clk);@(negedge clk);arv=0;
while(!rv)@(negedge clk);if(rp||rd!==v)$fatal(1,"READ %h=%h expected %h",a,rd,v);@(negedge clk);end endtask
task command(input[2:0]c,input[15:0]s,input bit r);
begin @(negedge clk);cc=c;stage=s;rev=r;cv=1;@(negedge clk);cv=0;
while(!cd)@(negedge clk);if(!ok)$fatal(1,"COMMAND %d rejected st=%d err=%h",c,st,err);@(negedge clk);end endtask
integer b,i,j,k,n;reg[31:0]value;reg[191:0]expectq;integer before_count;
integer test_mode=0,seen=0,test_step=0,nb,lb,hb,wt,li,hi,ev,pp,reverse_from;
always @(posedge clk)if(sv&&ready&&!pending&&test_mode!=0)begin
 if(test_step==64)begin lb=2;hb=2;wt=0;end
 else begin lb=test_step/32;wt=test_step%32;hb=wt==0?lb:lb+1;end
 nb=hb+3;
 pp=test_mode==1?seen:reverse_from-seen;
 if(test_mode==3)begin
  if(!grip||spd!=300||acc!=20||q!==target)$fatal(1,"reverse T106 profile or target");
 end else begin
  for(integer h=0;h<6;h=h+1)begin
   li=pp*(lb+2)/(nb-1);hi=pp*(hb+2)/(nb-1);
   ev=10000*h-30000+(((100*lb+li*10+h-170)*(32-wt)+(100*hb+hi*10+h-170)*wt+16)>>>5);
   if(pp<0)ev=target[h*32+:32];
   if(q[h*32+:32]!==ev)$fatal(1,"Q step=%d frame=%d axis=%d actual=%d expected=%d",test_step,seen,h,q[h*32+:32],ev);
  end
  if(grip||spd!=2640||acc!=254)$fatal(1,"T102 profile");
 end
 seen=seen+1;
end
initial begin
repeat(4)@(negedge clk);rst=1;read(12,32'hb001);write(0,1,0);write(28,2,0);
write(16,7,0);write(20,0,0);for(i=0;i<6;i=i+1)write(128+i*4,10000*i-30000,0);
write(16,6,0);write(20,0,0);
for(b=0;b<3;b=b+1)begin
 for(i=0;i<16;i=i+1)for(j=0;j<4;j=j+1)begin
  value=0;
  if(i==0)case(j)0:value=((b+3)<<16)|(b*8);1:value=40;2:value=(254<<16)|2640;3:value=(254<<16)|2640;endcase
  if(i==1)case(j)0:value=(1<<16)|(b*8+7);1:value=60;2:value=(1<<24)|(5<<16)|40;3:value=(1<<24)|(20<<16)|300;endcase
  write(20,(b*16+i)*4+j,0);write(128,value,0);
 end
end
for(k=0;k<6;k=k+1)begin
 write(16,k,0);
 for(b=0;b<3;b=b+1)begin
  write(20,b*8,0);
  for(i=0;i<b+3;i=i+1)write(128+i*4,100*b+10*i+k-170,0);
  write(20,b*8+7,0);write(128,500+b*100+k,0);
 end
end
write(16,0,0);write(20,0,0);read(128,-170);write(20,16,0);read(128,30);
write(0,2,0);if(!committed)$fatal(1,"Not committed");
$display("PASS: AXI complete-image commit, RAM readback and immutable writes");
for(k=0;k<=64;k=k+1)begin
 @(negedge clk);test_mode=1;seen=0;test_step=k;
 command(7,k<<4,0);wait(st==4);@(negedge clk);test_mode=0;
 n=k==64?5:k%32==0?k/32+3:k/32+4;
 if(seen!=n)$fatal(1,"frame count step=%d actual=%d expected=%d",k,seen,n);
end
$display("PASS: all 65 hand positions, unequal-count integer DDA, signed Q16 bank mixing, SPD/ACC");
@(negedge clk);test_step=32;test_mode=2;seen=0;reverse_from=3;target=0;
command(7,32<<4,1);wait(st==4);@(negedge clk);test_mode=0;
if(seen!=5||last!=0)$fatal(1,"full reverse");
$display("PASS: complete native trajectory reversed to exact previous start");
@(negedge clk);test_mode=1;test_step=32;seen=0;
command(7,32<<4,0);wait(seen==2);command(2,0,0);wait(!pending&&!dut.drain);@(negedge clk);test_mode=0;
reverse_from=dut.last_position;command(4,0,0);
@(negedge clk);seen=0;test_mode=2;target=0;
command(7,32<<4,1);wait(st==4);@(negedge clk);test_mode=0;
if(seen!=reverse_from+2||last!=0)$fatal(1,"partial reverse");
$display("PASS: FIST-style PAUSE, drain, CLEAR, partial reverse uses last accepted index");
@(negedge clk);test_mode=3;seen=0;target=192'h123456789;
command(7,(32<<4)|1,1);wait(st==4);@(negedge clk);test_mode=0;
if(seen!=1||last!=target)$fatal(1,"reverse gripper count");
$display("PASS: T106 reverse open profile and explicit previous grip target");
command(7,32<<4,0);ready=0;repeat(120)@(negedge clk);
if(!err[5]||st!=0||sv)$fatal(1,"Native downstream stall did not stop");
$display("PASS: native downstream backpressure timeout stops emission with a sticky hardware error");
unlock=0;write(0,1,1);if(!committed)$fatal(1,"locked write changed committed program");
$display("PASS: S4 lock rejects configuration mutation and preserves the program");
$finish;
end
initial begin #10000000;$fatal(1,"timeout");end
endmodule
'''
def main(out):
 out.mkdir(parents=True,exist_ok=False);(out/'tb.sv').write_text(BENCH)
 files=[ROOT/'native_motion/rtl/robot/b_route_ram.v',ROOT/'native_motion/rtl/robot/b_route_player.v',out/'tb.sv']
 records=[]
 for label,tool,args in [('compile','xvlog',['-sv',*files]),('elaborate','xelab',['tb','-s','route','-O0','-mt','off']),('run','xsim',['route','-runall'])]:
  cmd=['cmd.exe','/d','/c','E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*map(str,args)]
  p=subprocess.run(cmd,cwd=out,capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
  text=(p.stdout+p.stderr).decode('utf-8',errors='replace');(out/(label+'.txt')).write_text(text);print(label,p.returncode,flush=True)
  records.append(dict(stage=label,exit_code=p.returncode))
  if p.returncode or re.search('(ERROR:|Fatal:|FATAL:|FAIL:)',text):raise RuntimeError(text[-5000:])
 (out/'result.json').write_text(json.dumps(dict(passed=True,checks=[x for x in text.splitlines() if x.startswith('PASS:')],commands=records,
  source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files},hardware_access=False),indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out.resolve())
