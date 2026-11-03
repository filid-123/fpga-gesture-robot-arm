
`timescale 1ns/1ps
module tb;
reg clk=0,c50=0,pclk=0;always #5 clk=~clk;always #10 c50=~c50;always #10.416 pclk=~pclk;
reg rst=0,av=0,wv=0,arv=0;reg[11:0]aa=0,ra=0;reg[1:0]bus=0;reg[31:0]wd=0;wire awr,wr,bv,arr,rv;wire[31:0]rd;wire[1:0]bp,rp;wire[2:0]awrs,wrs,bvs,arrs,rvs;wire[95:0]rds;wire[5:0]bps,rps;assign awr=awrs[bus];assign wr=wrs[bus];assign bv=bvs[bus];assign arr=arrs[bus];assign rv=rvs[bus];assign rd=rds[bus*32+:32];assign bp=bps[bus*2+:2];assign rp=rps[bus*2+:2];
phase3_roarm_closed_loop_top #(.FAST_B(1),.DYNAMIC_B(1),.AUTO_RESTOCK(1),.UPGRADE(1),.HAND_ALIGN(1),.HAND_ALIGN_REGIONS(4),.HAND_ALIGN_LOCATOR(1),.HANDOVER_V2(1),.TIMED_WALKTHROUGH(1),.DEBOUNCE_CYCLES(4),
.LOCATOR_MODEL_FILE("C:/redacted_user/.codex/worktrees/mode-ab-integration-20261029/Gesture/model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/locator/model_rom_16k.mem"),.CLASSIFIER_WEIGHT_FILE("C:/redacted_user/.codex/worktrees/mode-ab-integration-20261029/Gesture/model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/classifier/weights_all.mem"),.CLASSIFIER_DESC_FILE("C:/redacted_user/.codex/worktrees/mode-ab-integration-20261029/Gesture/model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/classifier/layer_descriptors.mem"),.OV5640_INIT_FILE("C:/redacted_user/.codex/worktrees/mode-ab-integration-20261029/Gesture/native_motion/rtl/autonomous/ov5640_vga_yuyv.mem"))dut(
.clk_100mhz(clk),.rst_100mhz_n(rst),.clk_50mhz(c50),.rst_50mhz_n(rst),.pclk(pclk),.pclk_rst_n(rst),.dvp_data(8'd0),.dvp_href(1'b0),.dvp_vsync(1'b1),.xclk_locked(1'b1),.sccb_sda_in(1'b1),.arm_uart_rx(1'b1),.motion_enable_in(1'b1),
.s_axi_route_awaddr(aa[7:0]),.s_axi_route_awprot(3'd0),.s_axi_route_awvalid(av&&bus==0),.s_axi_route_awready(awrs[0]),
.s_axi_route_wdata(wd),.s_axi_route_wstrb(4'hf),.s_axi_route_wvalid(wv&&bus==0),.s_axi_route_wready(wrs[0]),.s_axi_route_bresp(bps[1:0]),.s_axi_route_bvalid(bvs[0]),.s_axi_route_bready(1'b1),
.s_axi_route_araddr(ra[7:0]),.s_axi_route_arprot(3'd0),.s_axi_route_arvalid(arv&&bus==0),.s_axi_route_arready(arrs[0]),.s_axi_route_rdata(rds[31:0]),.s_axi_route_rresp(rps[1:0]),.s_axi_route_rvalid(rvs[0]),.s_axi_route_rready(1'b1),
.s_axi_arm_awaddr(aa),.s_axi_arm_awprot(3'd0),.s_axi_arm_awvalid(av&&bus==1),.s_axi_arm_awready(awrs[1]),.s_axi_arm_wdata(wd),.s_axi_arm_wstrb(4'hf),.s_axi_arm_wvalid(wv&&bus==1),.s_axi_arm_wready(wrs[1]),.s_axi_arm_bresp(bps[2+:2]),.s_axi_arm_bvalid(bvs[1]),.s_axi_arm_bready(1'b1),.s_axi_arm_araddr(ra),.s_axi_arm_arprot(3'd0),.s_axi_arm_arvalid(arv&&bus==1),.s_axi_arm_arready(arrs[1]),.s_axi_arm_rdata(rds[32+:32]),.s_axi_arm_rresp(rps[2+:2]),.s_axi_arm_rvalid(rvs[1]),.s_axi_arm_rready(1'b1),
.s_axi_plan_awaddr(aa),.s_axi_plan_awprot(3'd0),.s_axi_plan_awvalid(av&&bus==2),.s_axi_plan_awready(awrs[2]),.s_axi_plan_wdata(wd),.s_axi_plan_wstrb(4'hf),.s_axi_plan_wvalid(wv&&bus==2),.s_axi_plan_wready(wrs[2]),.s_axi_plan_bresp(bps[4+:2]),.s_axi_plan_bvalid(bvs[2]),.s_axi_plan_bready(1'b1),.s_axi_plan_araddr(ra),.s_axi_plan_arprot(3'd0),.s_axi_plan_arvalid(arv&&bus==2),.s_axi_plan_arready(arrs[2]),.s_axi_plan_rdata(rds[64+:32]),.s_axi_plan_rresp(rps[4+:2]),.s_axi_plan_rvalid(rvs[2]),.s_axi_plan_rready(1'b1),
.s_axi_s4_awvalid(1'b0),.s_axi_s4_wvalid(1'b0),.s_axi_s4_arvalid(1'b0),.s_axi_s4_bready(1'b1),.s_axi_s4_rready(1'b1),
.s_axi_vis_awvalid(1'b0),.s_axi_vis_wvalid(1'b0),.s_axi_vis_arvalid(1'b0),.s_axi_vis_bready(1'b1),.s_axi_vis_rready(1'b1));
task write(input[11:0]a,input[31:0]v);
begin @(negedge clk);aa=a;wd=v;av=1;wv=1;while(!(awr&&wr))@(negedge clk);@(negedge clk);av=0;wv=0;
while(!bv)@(negedge clk);if(bps[1:0])$fatal(1,"Root route write failed %h",a);@(negedge clk);end endtask
task read(input[11:0]a,input[31:0]v);
begin @(negedge clk);ra=a;arv=1;while(!arr)@(negedge clk);@(negedge clk);arv=0;
while(!rv)@(negedge clk);if(rp||rd!==v)$fatal(1,"Root route read %h=%h expected %h",a,rd,v);@(negedge clk);end endtask

reg cv=0;reg[2:0]cc=0;reg[191:0]target=0;
reg[31:0]setup[0:4095];integer n=0,limit=0;
task native_cmd(input[2:0]c);
begin @(negedge clk);cc=c;cv=1;while(!dut.u_task.native_ready)@(negedge clk);@(negedge clk);cv=0;
while(!dut.u_task.native_done)@(negedge clk);if(!dut.u_task.native_ok)$fatal(1,"Native ownership command rejected %d",c);@(negedge clk);end endtask
initial begin
 $readmemh("setup.mem",setup);repeat(8)@(negedge clk);rst=1;repeat(8)@(negedge clk);
 force dut.u_task.native_valid=cv;force dut.u_task.native_code=cc;force dut.u_task.op_target=target;
 force dut.u_task.op_na=16'd0;force dut.u_task.op_n=16'd16;force dut.u_task.op_profile=1'b0;
 bus=1;for(integer i=0;i<setup[0];i=i+1)write(setup[1+2*i],setup[2+2*i]);
 write(12'h020,16);write(12'h038,91<<8);write(0,1);limit=0;
 while(!dut.u_task.u_motion.u_actuator.u_arm_backend.config_valid)begin @(negedge clk);limit=limit+1;if(limit>10000)$fatal(1,"Backend commit failed");end
 write(4,1);repeat(8)@(negedge clk);
 bus=0;write(0,1);write(28,16);
 for(integer plane=0;plane<6;plane=plane+1)begin write(16,plane);write(20,0);write(128,0);end
 write(16,7);write(20,0);
 for(integer i=0;i<6;i=i+1)begin target[i*32+:32]=setup[4000+i];write(128+4*i,setup[4000+i]);end
 write(16,6);
 for(integer i=0;i<192;i=i+1)begin write(20,i);case(i%4)0:write(128,65536);1:write(128,512);default:write(128,(254<<16)|2640);endcase end
 write(0,2);native_cmd(7);wait(dut.u_task.native_pl_status[2:0]==4);
 if(dut.u_task.native_last!==target)$fatal(1,"Native B did not reach endpoint");
 native_cmd(6);repeat(3)@(negedge clk);
 if(dut.u_task.u_motion.route_selected!==0)$fatal(1,"B ownership fence failed to restore host P2P source");
 bus=2;write(12'h040,16);write(12'h044,4);write(12'h048,1);write(12'h04c,512);write(12'h050,50000000);
 for(integer i=0;i<6;i=i+1)begin
  write(12'h100+i*32,target[i*32+:32]);write(12'h104+i*32,target[i*32+:32]+(i==0?656:0));
  write(12'h108+i*32,1701);write(12'h10c+i*32,9795948);
 end
 target[31:0]=target[31:0]+656;write(0,1);limit=0;
 while(dut.u_task.native_pl_status[2:0]!=4||dut.u_task.native_last!==target)begin @(negedge clk);limit=limit+1;if(limit>1000000)$fatal(1,"Host HOME transition stuck error=%h status=%h last=%h target=%h sel=%d core=%d armerr=%h armstate=%h owner=%d",dut.u_task.native_pl_error,dut.u_task.native_pl_status,dut.u_task.native_last,target,dut.u_task.u_motion.route_selected,dut.u_task.u_motion.u_planner.core_state,dut.u_task.u_motion.u_actuator.u_arm_backend.error_status,dut.u_task.u_motion.u_actuator.u_arm_backend.u_core.state,dut.u_task.owner_s4);end
 $display("PASS: full root native B completes, ownership fence acknowledges and restores host P2P HOME transition");
 native_cmd(6);native_cmd(7);wait(dut.u_task.native_pl_status[2:0]==4);
 if(dut.u_task.native_last[31:0]!==32'd0)$fatal(1,"Native B could not resume after host P2P");
 $display("PASS: host P2P returns ownership to native B with the same immutable program");
 // Audit REQP-1839 at the real asynchronously reset elastic-buffer boundary.
 force dut.u_task.u_motion.u_actuator.u_mux.m_ready=1'b0;
 native_cmd(7);wait(dut.u_task.u_motion.u_actuator.u_mux.buf_valid);
 #2;rst=0;#1;
 if(dut.u_task.u_motion.u_actuator.u_mux.buf_valid!==0)$fatal(1,"Async buffer reset did not close the output");
 repeat(3)@(negedge clk);
 if(dut.u_task.u_motion.g_b_program.u_player.committed!==0||dut.u_task.u_motion.g_b_program.u_player.base_mask!==0||dut.u_task.u_motion.g_b_program.u_player.desc_mask!==0)$fatal(1,"Reset retained a trusted RAM image");
 if(dut.u_task.u_motion.u_actuator.u_arm_backend.config_valid!==0)$fatal(1,"Reset retained backend configuration");
 rst=1;release dut.u_task.u_motion.u_actuator.u_mux.m_ready;repeat(6)@(negedge clk);
 bus=0;read(4,2);
 @(negedge clk);cc=7;cv=1;@(negedge clk);cv=0;
 while(!dut.u_task.native_done)@(negedge clk);
 if(dut.u_task.native_ok!==0)$fatal(1,"Motion accepted before complete program reload");
 $display("PASS: asynchronous reset drains the real elastic output, invalidates route/backend configuration and rejects motion before complete RAM reload");$finish;
end
initial begin #10000000;$fatal(1,"Native/host ownership handoff timeout");end
endmodule
