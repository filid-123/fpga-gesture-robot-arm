
`timescale 1ns/1ps
module tb_speed15_s2;
reg clk=0;always #5 clk=~clk;
reg rst_n=0,start=0,clear=0;
reg[15:0] n=0,na=0;
wire[2:0] ch,state,err_code,err_channel;
wire[1:0] field;
reg[31:0] cfg[0:23];wire[31:0] cfg_data=cfg[ch*4+field];
reg[191:0] last=0;
wire valid,computing,err,done,late;
wire[191:0] data;wire[15:0] index;
reg[31:0] moves[0:4602];reg[31:0] golden[0:56538];
planner_p2p_core #(.SMOOTH_PROFILE(1)) dut(.clk(clk),.rst_n(rst_n),.cmd_start(start),.cmd_pause(1'b0),.cmd_resume(1'b0),
 .cmd_estop(1'b0),.cmd_clear(clear),.cfg_n_samples(n),.cfg_accel_samples(na),.cfg_profile(1'b1),
 .cfg_period_cycles(32'd512),.cfg_stall_timeout(32'd50000000),.cfg_ch(ch),.cfg_field(field),.cfg_data(cfg_data),
 .last_delivered(last),.last_valid(1'b1),.m_valid(valid),.m_ready(1'b1),.m_data(data),.state(state),
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
   if(valid)begin
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
 if(total!=golden[0])$fatal(1,"FAIL: total sample count");
 $display("PASS: quintic actual S2 RTL all %0d legs, %0d exact six-axis samples, production VMAX/AMAX and endpoints",moves[0],total);
 $finish;
end
initial begin #1000000000;$fatal(1,"FAIL: global timeout");end
endmodule
