`timescale 1ns/1ps
module tb_gate_v2;
 reg clk=0;always #5 clk=~clk;reg rst=0,go=0;reg signed[31:0] conf=-11749;wire done,det,busy;wire[9:0]x,y,s;
 locator_bbox_roi_black #(.USE_EMA(0),.ALPHA_FILE("native_motion/geometry_alpha_q16.mem")) dut(
 .clk(clk),.rst_n(rst),.start(go),.timestamp_ms(32'd100),.cell_index(8'd136),.confidence_i32(conf),
 .dx_i32(32'sd0),.dy_i32(32'sd0),.width_i32(32'sd59144),.height_i32(32'sd37743),
 .busy(busy),.done(done),.detected(det),.roi_x0(x),.roi_y0(y),.roi_side(s));
 integer k,cycles;
 initial begin
  repeat(4)@(negedge clk);rst=1;
  for(k=0;k<4;k=k+1)begin
   case(k)0:conf=-11749;1:conf=-11748;2:conf=-11747;3:conf=-11749;endcase
   go=1;@(negedge clk);go=0;cycles=0;
   while(!done)begin @(negedge clk);cycles=cycles+1;if(cycles>1000)$fatal(1,"FAIL: gate timeout");end
   if(det!==((k==1)||(k==2)))$fatal(1,"FAIL: signed >= gate boundary");
   if(!det && (x!=0 || y!=0 || s!=1))$fatal(1,"FAIL: rejected frame retained actionable ROI");
   repeat(4)@(negedge clk);
  end
  $display("PASS: V2_GATE signed -11749 reject/-11748 accept/-11747 accept/reject-after-accept clears ROI");$finish;
 end
endmodule
