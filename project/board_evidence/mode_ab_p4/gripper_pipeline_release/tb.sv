
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

reg[31:0] periods[0:11];integer i,j,b,k;reg[31:0]v;

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
