`timescale 1ns/1ps
module tb_hdmi_final_top;
reg px=0,px5=0;always #6.734007 px=~px;always #1.346801 px5=~px5;
reg clk=0,pclk=0,c50=0;always #5 clk=~clk;always #10.416667 pclk=~pclk;always #10 c50=~c50;
string root;
reg rst=0,href=0,vsync=1;reg[7:0]data=0;wire tx;
reg[31:0]source[0:76799],expected[0:255];integer frame,x,y,k,writes=0,hdwrites=0,ha,hx,hy,hk,hh,hb;reg[31:0]hdgold;integer cycles,valid_cycles=0;reg[31:0]last_id=32'hffffffff;
phase3_roarm_closed_loop_top #(.UPGRADE(1),.ENABLE_HDMI(1),.HDMI_FONT_FILE("native_motion/rtl/hdmi/mode_a_font.mem"),.LOCATOR_MODEL_FILE("model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/locator/model_rom_16k.mem"),
.CLASSIFIER_WEIGHT_FILE("model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/classifier/weights_all.mem"),
.CLASSIFIER_DESC_FILE("model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/classifier/layer_descriptors.mem"),.OV5640_INIT_FILE("native_motion/rtl/autonomous/ov5640_vga_yuyv.mem"),.DEBOUNCE_CYCLES(8),.TIMED_WALKTHROUGH(1),.HANDOVER_V2(1),.HAND_ALIGN(1),.HAND_ALIGN_REGIONS(4),.HAND_ALIGN_LOCATOR(1)) dut(
.clk_100mhz(clk),.hdmi_pixel_clk(px),.hdmi_pixel_clk_5x(px5),.hdmi_pixel_rst_n(rst),
.rst_100mhz_n(rst),
.clk_50mhz(c50),
.rst_50mhz_n(rst),
.pclk(pclk),
.pclk_rst_n(rst),
.dvp_data(data),
.dvp_href(href),
.dvp_vsync(vsync),
.xclk_locked(1'b1),
.camera_reset_n(),
.camera_pwdn(),
.sccb_scl_drive_low(),
.sccb_sda_drive_low(),
.sccb_sda_in(1'b0),
.leds(),
.s_axi_arm_awaddr(1'b0),
.s_axi_arm_awprot(1'b0),
.s_axi_arm_awvalid(1'b0),
.s_axi_arm_awready(),
.s_axi_arm_wdata(1'b0),
.s_axi_arm_wstrb(1'b0),
.s_axi_arm_wvalid(1'b0),
.s_axi_arm_wready(),
.s_axi_arm_bresp(),
.s_axi_arm_bvalid(),
.s_axi_arm_bready(1'b1),
.s_axi_arm_araddr(1'b0),
.s_axi_arm_arprot(1'b0),
.s_axi_arm_arvalid(1'b0),
.s_axi_arm_arready(),
.s_axi_arm_rdata(),
.s_axi_arm_rresp(),
.s_axi_arm_rvalid(),
.s_axi_arm_rready(1'b1),
.s_axi_plan_awaddr(1'b0),
.s_axi_plan_awprot(1'b0),
.s_axi_plan_awvalid(1'b0),
.s_axi_plan_awready(),
.s_axi_plan_wdata(1'b0),
.s_axi_plan_wstrb(1'b0),
.s_axi_plan_wvalid(1'b0),
.s_axi_plan_wready(),
.s_axi_plan_bresp(),
.s_axi_plan_bvalid(),
.s_axi_plan_bready(1'b1),
.s_axi_plan_araddr(1'b0),
.s_axi_plan_arprot(1'b0),
.s_axi_plan_arvalid(1'b0),
.s_axi_plan_arready(),
.s_axi_plan_rdata(),
.s_axi_plan_rresp(),
.s_axi_plan_rvalid(),
.s_axi_plan_rready(1'b1),
.s_axi_s4_awaddr(1'b0),
.s_axi_s4_awprot(1'b0),
.s_axi_s4_awvalid(1'b0),
.s_axi_s4_awready(),
.s_axi_s4_wdata(1'b0),
.s_axi_s4_wstrb(1'b0),
.s_axi_s4_wvalid(1'b0),
.s_axi_s4_wready(),
.s_axi_s4_bresp(),
.s_axi_s4_bvalid(),
.s_axi_s4_bready(1'b1),
.s_axi_s4_araddr(1'b0),
.s_axi_s4_arprot(1'b0),
.s_axi_s4_arvalid(1'b0),
.s_axi_s4_arready(),
.s_axi_s4_rdata(),
.s_axi_s4_rresp(),
.s_axi_s4_rvalid(),
.s_axi_s4_rready(1'b1),
.s_axi_vis_awaddr(1'b0),
.s_axi_vis_awprot(1'b0),
.s_axi_vis_awvalid(1'b0),
.s_axi_vis_awready(),
.s_axi_vis_wdata(1'b0),
.s_axi_vis_wstrb(1'b0),
.s_axi_vis_wvalid(1'b0),
.s_axi_vis_wready(),
.s_axi_vis_bresp(),
.s_axi_vis_bvalid(),
.s_axi_vis_bready(1'b1),
.s_axi_vis_araddr(1'b0),
.s_axi_vis_arprot(1'b0),
.s_axi_vis_arvalid(1'b0),
.s_axi_vis_arready(),
.s_axi_vis_rdata(),
.s_axi_vis_rresp(),
.s_axi_vis_rvalid(),
.s_axi_vis_rready(1'b1),
.irq_arm(),
.irq_plan(),
.irq_s4(),
.arm_uart_tx(tx),
.arm_uart_rx(1'b1),
.motion_enable_in(1'b0));
defparam dut.u_vision.GEOMETRY_EMA=0;
defparam dut.u_vision.GEOMETRY_ALPHA_FILE="native_motion/geometry_alpha_q16.mem";
always @(negedge clk) if(rst)begin
 if(tx!==1'b1)$fatal(1,"FAIL: unconfigured/D5-low final top emitted UART data");
 if(dut.u_task.native_valid && dut.u_task.native_code==1)$fatal(1,"FAIL: inactive task issued unsolicited MOVE");
 if(dut.e_valid)valid_cycles=valid_cycles+1;
 if(dut.preview_we)begin
  ha=dut.preview_addr;if(ha!=hdwrites)$fatal(1,"FAIL: HD write order");
  hdgold=0;
  for(hb=0;hb<4;hb=hb+1)begin
   hk=ha*4+hb;hx=hk%256;hy=hk/256;hh=(hy*5/2)*640+(hx*5/2);
   hdgold[hb*8+:8]=(source[hh/4]>>((hh%4)*8))&255;
  end
  if(dut.preview_data!==hdgold)$fatal(1,"FAIL: true256 source sample");
  hdwrites=hdwrites+1;
 end
 if(dut.u_vision.roi_word_we)begin
  if(writes>=256 || dut.u_vision.roi_word_data!==expected[writes])$fatal(1,"FAIL: final top ROI word %0d",writes);
  writes=writes+1;
 end
end
initial begin
 if(!$value$plusargs("ROOT=%s",root))$fatal(1,"FAIL: ROOT argument");
 $readmemh({root,"/palm_source.mem"},source);$readmemh({root,"/palm_roi.mem"},expected);
 // Only SCCB startup is bypassed here. All pixel/ML/filter/adapter/task/backend RTL is the final production top.
 force dut.u_vision.camera_init_done=1'b1;force dut.u_vision.camera_init_error=1'b0;
 if(dut.u_task.u_regs.ABI!=32'h340a)$fatal(1,"Four region ABI mismatch");
 repeat(10)@(negedge clk);rst=1;repeat(30)@(negedge pclk);
 for(frame=0;frame<12;frame=frame+1)begin
  writes=0;hdwrites=0;vsync=1;repeat(8)@(negedge pclk);vsync=0;repeat(8)@(negedge pclk);
  for(y=0;y<480;y=y+1)begin
   @(negedge pclk);href=1;
   for(x=0;x<640;x=x+1)begin k=y*640+x;data=(source[k/4]>>(8*(k%4)))&255;@(negedge pclk);data=128;@(negedge pclk);end
   href=0;repeat(20)@(negedge pclk);
  end
  cycles=0;while(!dut.v_frame_valid)begin @(negedge clk);cycles=cycles+1;if(cycles>8000000)$fatal(1,"FAIL: final top pipeline timeout");end
  if(!dut.v_detected || writes!=256 || hdwrites!=12288 || (frame>0 && dut.v_frame_id<=last_id))$fatal(1,"FAIL: final top frame/ROI identity");
  if(dut.u_task.hand_x!=((dut.v_raw_x0+dut.v_raw_x1)>>1) || dut.u_task.hand_y!=((dut.v_raw_y0+dut.v_raw_y1)>>1))$fatal(1,"FAIL: Locator raw center was gated by classification or EMA");
  last_id=dut.v_frame_id;repeat(20)@(negedge clk);
  if(dut.u_adapter.last_id!=last_id || dut.u_adapter.last_acq_ms!=dut.v_acq_ms)$fatal(1,"FAIL: final top adapter metadata identity");
  $display("PASS: FOLLOW_FINAL_TOP frame=%0d id=%0d model=%0d task=%0d qualified=%0d event_valid=%0d age_ms=%0d",frame,last_id,dut.v_model_class,dut.v_candidate,dut.v_qualified,dut.e_valid,dut.v_now_ms-dut.v_acq_ms);
 end
 if(valid_cycles==0 || !dut.e_valid || dut.e_class!=dut.v_candidate)$fatal(1,"FAIL: repeated real frames never qualified through final adapter");
 if(dut.v_format_error_count!=0)$fatal(1,"FAIL: legal final top stimulus produced format errors");
 // A held snapshot can need two video boundaries (33.34ms), not just one.
 repeat(4000000)@(negedge clk);
 if(!dut.g_hdmi.u_display.frame.display_valid || dut.g_hdmi.u_display.frame.display_frame_id!=last_id)$fatal(1,"HDMI failed to show final matching image");
 if(dut.g_hdmi.u_display.ui[4:2]!=4 || !dut.g_hdmi.u_display.ui[1])$fatal(1,"HDMI confirmed PALM differs from task input");
 if(dut.measure_cls!=468487 && dut.measure_cls!=468486)$fatal(1,"FAIL: parallel stage cycle count %d",dut.measure_cls);
 if(dut.measure_loc==0 || dut.measure_total<72)$fatal(1,"FAIL: stage trace not active");
 $display("PASS: stage cycle timers, bounded trace and true256x192 samples through production integration");
 $display("PASS: HDMI live frame identity and confirmed PALM snapshot match production adapter");
 $display("PASS: FOLLOW_FINAL_TOP twelve real VGA frames/ML/time-filter/final-adapter identity; unconfigured task and D5-low UART idle");$finish;
end
endmodule
