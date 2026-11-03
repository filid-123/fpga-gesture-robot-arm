`timescale 1ns/1ps
module tb_quintic_bounds;
 reg clk=0,rst=0,start=0,estop=0,clear=0;always #5 clk=~clk;
 reg[15:0]n=2;wire[2:0]state;wire error;
 planner_p2p_core #(.SMOOTH_PROFILE(1)) dut(.clk(clk),.rst_n(rst),.cmd_start(start),.cmd_pause(1'b0),.cmd_resume(1'b0),.cmd_estop(estop),.cmd_clear(clear),
  .cfg_n_samples(n),.cfg_accel_samples(16'd1),.cfg_profile(1'b1),.cfg_period_cycles(32'd512),.cfg_stall_timeout(32'd50000000),.cfg_data(32'd0),
  .last_delivered(192'd0),.last_valid(1'b1),.m_ready(1'b1),.state(state),.err_pulse(error));
 integer i,timeout;reg[63:0]square;reg[15:0]values[0:6];
 initial begin
  values[0]=2;values[1]=3;values[2]=8;values[3]=123;values[4]=512;values[5]=32768;values[6]=65535;
  repeat(8)@(negedge clk);rst=1;
  for(i=0;i<7;i=i+1)begin
   n=values[i];square={48'd0,n}*{48'd0,n};@(negedge clk);start=1;@(negedge clk);start=0;timeout=0;
   while(state!=2)begin @(negedge clk);timeout=timeout+1;if(error || timeout>3000)$fatal(1,"Bound setup failed");end
   if(dut.a_const!==square/6 || dut.v_const!=(n>>1) || dut.d_const!=n)$fatal(1,"Exact conservative bounds N=%0d A=%0d expected=%0d",n,dut.a_const,square/6);
   estop=1;@(negedge clk);estop=0;clear=1;@(negedge clk);clear=0;repeat(5)@(negedge clk);
  end
  $display("PASS: exact quintic conservative constants N2..65535, overflow boundary, ESTOP/CLEAR and reuse of scalar datapath");$finish;
 end
endmodule
