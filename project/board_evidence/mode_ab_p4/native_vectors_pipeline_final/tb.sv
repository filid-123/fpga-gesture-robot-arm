
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
.cmd_valid(cv),.cmd_ready(cr),.cmd_code(cc),.cmd_stage(stage),.reverse(rev),.cmd_target(target),.stall_timeout(32'd50000000),.cmd_done(cd),.cmd_ok(ok),
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

reg[31:0] config_words[0:43155],op_words[0:14259],gold_words[0:297240];

integer cp=0,op=0,gp=0,count=0,seen=0,expected=0,profile=0,group_id,base_output;
reg checking=0;reg[191:0]held;reg stalled=0;reg[15:0]lfsr=16'hface;
always @(negedge clk)begin lfsr={lfsr[14:0],lfsr[15]^lfsr[13]^lfsr[12]^lfsr[10]};ready=lfsr[3:0]!=0;end
always @(posedge clk)begin
 if(checking&&sv&&ready&&!pending)begin
  for(integer axis=0;axis<6;axis=axis+1)if(q[axis*32+:32]!==gold_words[gp+axis])$fatal(1,"Native actual vector sample=%d axis=%d actual=%h expected=%h",gp/6,axis,q[axis*32+:32],gold_words[gp+axis]);
  if(spd!==profile[15:0]||acc!==profile[23:16]||grip!==profile[24])$fatal(1,"Native phase profile differs");
  gp=gp+6;seen=seen+1;
 end
 if(stalled&&(!sv||q!==held))$fatal(1,"Native sample changed under downstream backpressure");
 stalled=sv&&!(ready&&!pending);held=q;
end
initial begin
 $readmemh("cfg.mem",config_words);$readmemh("ops.mem",op_words);$readmemh("gold.mem",gold_words);
 repeat(5)@(negedge clk);rst=1;
 for(group_id=0;group_id<3;group_id=group_id+1)begin
  count=config_words[cp];cp=cp+1;
  for(integer j=0;j<count;j=j+1)begin write(config_words[cp],config_words[cp+1],0);cp=cp+2;end
  if(!committed)$fatal(1,"Actual program not committed");
  count=op_words[op];op=op+1;base_output=outputs;
  for(integer j=0;j<count;j=j+1)begin
   @(negedge clk);expected=op_words[op+1];profile=op_words[op+2];seen=0;
   for(integer axis=0;axis<6;axis=axis+1)target[axis*32+:32]=op_words[op+3+axis];
   checking=1;command(7,op_words[op],0);wait(st==4);@(negedge clk);checking=0;
   if(seen!=expected||last!==target)$fatal(1,"Native sample count or phase endpoint differs");op=op+9;
  end
  $display("PASS: real class program %d: %d PL phases, all 65 hand positions, %d backend-accepted vectors",group_id,count,outputs-base_output);
 end
 $finish;
end
initial begin #(64'd2000000000);$fatal(1,"Native vector timeout");end
endmodule
