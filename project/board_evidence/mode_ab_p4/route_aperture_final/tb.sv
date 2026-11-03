
`timescale 1ns/1ps
module tb;
reg clk=0,c50=0,pclk=0;always #5 clk=~clk;always #10 c50=~c50;always #10.416 pclk=~pclk;
reg rst=0,av=0,wv=0,arv=0;reg[7:0]aa=0,ra=0;reg[31:0]wd=0;wire awr,wr,bv,arr,rv;wire[31:0]rd;wire[1:0]bp,rp;
phase3_roarm_closed_loop_top #(.FAST_B(1),.DYNAMIC_B(1),.AUTO_RESTOCK(1),.UPGRADE(1),.HAND_ALIGN(1),.HAND_ALIGN_REGIONS(4),.HAND_ALIGN_LOCATOR(1),.HANDOVER_V2(1),.TIMED_WALKTHROUGH(1),.DEBOUNCE_CYCLES(4),
.LOCATOR_MODEL_FILE("C:/redacted_user/.codex/worktrees/mode-ab-integration-20261029/Gesture/model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/locator/model_rom_16k.mem"),.CLASSIFIER_WEIGHT_FILE("C:/redacted_user/.codex/worktrees/mode-ab-integration-20261029/Gesture/model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/classifier/weights_all.mem"),.CLASSIFIER_DESC_FILE("C:/redacted_user/.codex/worktrees/mode-ab-integration-20261029/Gesture/model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/classifier/layer_descriptors.mem"),.OV5640_INIT_FILE("C:/redacted_user/.codex/worktrees/mode-ab-integration-20261029/Gesture/native_motion/rtl/autonomous/ov5640_vga_yuyv.mem"))dut(
.clk_100mhz(clk),.rst_100mhz_n(rst),.clk_50mhz(c50),.rst_50mhz_n(rst),.pclk(pclk),.pclk_rst_n(rst),.dvp_data(8'd0),.dvp_href(1'b0),.dvp_vsync(1'b1),.xclk_locked(1'b1),.sccb_sda_in(1'b1),.arm_uart_rx(1'b1),.motion_enable_in(1'b0),
.s_axi_route_awaddr(aa),.s_axi_route_awprot(3'd0),.s_axi_route_awvalid(av),.s_axi_route_awready(awr),
.s_axi_route_wdata(wd),.s_axi_route_wstrb(4'hf),.s_axi_route_wvalid(wv),.s_axi_route_wready(wr),.s_axi_route_bresp(bp),.s_axi_route_bvalid(bv),.s_axi_route_bready(1'b1),
.s_axi_route_araddr(ra),.s_axi_route_arprot(3'd0),.s_axi_route_arvalid(arv),.s_axi_route_arready(arr),.s_axi_route_rdata(rd),.s_axi_route_rresp(rp),.s_axi_route_rvalid(rv),.s_axi_route_rready(1'b1),
.s_axi_arm_awvalid(1'b0),.s_axi_arm_wvalid(1'b0),.s_axi_arm_arvalid(1'b0),.s_axi_arm_bready(1'b1),.s_axi_arm_rready(1'b1),
.s_axi_plan_awvalid(1'b0),.s_axi_plan_wvalid(1'b0),.s_axi_plan_arvalid(1'b0),.s_axi_plan_bready(1'b1),.s_axi_plan_rready(1'b1),
.s_axi_s4_awvalid(1'b0),.s_axi_s4_wvalid(1'b0),.s_axi_s4_arvalid(1'b0),.s_axi_s4_bready(1'b1),.s_axi_s4_rready(1'b1),
.s_axi_vis_awvalid(1'b0),.s_axi_vis_wvalid(1'b0),.s_axi_vis_arvalid(1'b0),.s_axi_vis_bready(1'b1),.s_axi_vis_rready(1'b1));
task write(input[7:0]a,input[31:0]v);
begin @(negedge clk);aa=a;wd=v;av=1;wv=1;while(!(awr&&wr))@(negedge clk);@(negedge clk);av=0;wv=0;
while(!bv)@(negedge clk);if(bp)$fatal(1,"Root route write failed %h",a);@(negedge clk);end endtask
task read(input[7:0]a,input[31:0]v);
begin @(negedge clk);ra=a;arv=1;while(!arr)@(negedge clk);@(negedge clk);arv=0;
while(!rv)@(negedge clk);if(rp||rd!==v)$fatal(1,"Root route read %h=%h expected %h",a,rd,v);@(negedge clk);end endtask
initial begin
 repeat(8)@(negedge clk);rst=1;repeat(8)@(negedge clk);
 read(12,32'hb001);write(0,1);write(28,16);
 for(integer plane=0;plane<6;plane=plane+1)begin write(16,plane);write(20,0);write(128,-100-plane);read(128,-100-plane);end
 write(16,7);write(20,0);for(integer i=0;i<6;i=i+1)write(128+4*i,1234+i);
 write(16,6);
 for(integer i=0;i<192;i=i+1)begin write(20,i);write(128,0);end
 write(0,2);read(4,3);
 if(dut.ui_task[3:0]!==0||dut.ui_frames!==0)$fatal(1,"Configuration unexpectedly started motion");
 $display("PASS: complete root route AXI port crosses the real S4 ownership window and reaches all six native RAMs");
 $display("PASS: configuration and readback with D5 low never arm or start a task");$finish;
end
initial begin #10000000;$fatal(1,"Root route AXI timeout");end
endmodule
