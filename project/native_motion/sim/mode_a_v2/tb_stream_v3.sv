`timescale 1ns/1ps
module tb_stream_v3;
reg clk=0,pclk=0,c50=0;always #5 clk=~clk;always #10.416667 pclk=~pclk;always #10 c50=~c50;
string root;
reg rst=0,href=0,vsync=1;reg[7:0]data=0;wire tx;
reg[31:0]source[0:76799],expected[0:255];integer frame,x,y,k,writes=0,cycles,valid_cycles=0;reg[31:0]last_id=32'hffffffff;
phase3_roarm_closed_loop_top #(.LOCATOR_MODEL_FILE("model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/locator/model_rom_16k.mem"),
.CLASSIFIER_WEIGHT_FILE("model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/classifier/weights_all.mem"),
.CLASSIFIER_DESC_FILE("model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/classifier/layer_descriptors.mem"),.OV5640_INIT_FILE("native_motion/rtl/autonomous/ov5640_vga_yuyv.mem"),.DEBOUNCE_CYCLES(8),.TIMED_WALKTHROUGH(1),.HANDOVER_V2(1),.HAND_ALIGN(1)) dut(
.clk_100mhz(clk),
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

reg[31:0]negative[0:76799],palm[0:76799],palm_roi[0:255],palm_logits[0:5];
reg[43:0]negative_stream[0:1279],palm_stream[0:1279];
integer source_type[0:63];reg[31:0]source_ts[0:63];reg received[0:63];
integer stimulus_type=0,pub_id,active_type=0,loc_words=0,roi_words=0;
integer results=0,misses=0,classifications=0,overlaps=0,cl_logits=0,cl_id=0;
integer last_result=-1,drain=0;
always @(negedge clk)if(rst)begin
 if(tx!==1'b1 || (dut.u_task.native_valid && dut.u_task.native_code==1))
  $fatal(1,"FAIL: unconfigured streaming test emitted arm command");
 if(dut.u_vision.camera_frame_published)begin
  pub_id=dut.u_vision.camera_latest_frame_id;
  if(pub_id>=64)$fatal(1,"FAIL: unexpected frame id");
  source_type[pub_id]=stimulus_type;
  source_ts[pub_id]=(dut.u_vision.camera_frame_id_0==pub_id)?dut.u_vision.frame_timestamp_ms_0:dut.u_vision.frame_timestamp_ms_1;
 end
 if(dut.u_vision.locator_start)begin
  active_type=source_type[dut.u_vision.locator_frame_id];loc_words=0;
  if(dut.u_vision.classifier_busy)overlaps=overlaps+1;
 end
 if(dut.u_vision.locator_output_we)begin
  if(loc_words>=1280 || {dut.u_vision.locator_output_addr,dut.u_vision.locator_output_data} !==
   (active_type==5?palm_stream[loc_words]:negative_stream[loc_words]))
   $fatal(1,"FAIL: streaming locator word %0d",loc_words);
  loc_words=loc_words+1;
 end
 if(dut.u_vision.roi_start)begin
  roi_words=0;if(source_type[dut.u_vision.roi_tag]!=5)$fatal(1,"FAIL: rejected source generated ROI");
 end
 if(dut.u_vision.roi_word_we)begin
  if(roi_words>=256 || dut.u_vision.roi_word_data!==palm_roi[roi_words])$fatal(1,"FAIL: streaming ROI bytes");
  if(dut.u_vision.classifier_busy && dut.u_vision.roi_write_bank==dut.u_vision.classifier_read_bank)
   $fatal(1,"FAIL: integrated ROI ownership collision");
  roi_words=roi_words+1;
 end
 if(dut.u_vision.classifier_start)begin
  cl_id=dut.u_vision.u_scheduler.metadata[dut.u_vision.classifier_read_bank][198:167];
  if(source_type[cl_id]!=5)$fatal(1,"FAIL: classifier metadata does not describe palm source");
  cl_logits=0;classifications=classifications+1;
 end
 if(dut.u_vision.u_classifier.dense_inst.state==7 && dut.u_vision.u_classifier.layer_is_final)begin
  if(cl_logits>=6 || dut.u_vision.u_classifier.dense_inst.acc!==palm_logits[cl_logits])$fatal(1,"FAIL: streaming logits");
  cl_logits=cl_logits+1;
 end
 if(dut.v_frame_valid)begin
  pub_id=dut.v_frame_id;
  if(pub_id>=64 || received[pub_id] || pub_id<=last_result || dut.v_acq_ms!==source_ts[pub_id])
   $fatal(1,"FAIL: streaming result order/id/acquisition timestamp");
  received[pub_id]=1;last_result=pub_id;results=results+1;
  if(source_type[pub_id]==5)begin
   if(!dut.v_detected || dut.v_candidate!=4 || dut.v_model_class!=5)$fatal(1,"FAIL: streaming PALM class");
  end else begin
   misses=misses+1;if(dut.v_detected || dut.v_candidate!=7)$fatal(1,"FAIL: streaming reject class");
  end
 end
 if(dut.u_vision.fatal_error || dut.u_vision.fifo_overflow || dut.v_format_error_count!=0)
  $fatal(1,"FAIL: legal streaming pixels caused fault");
end
initial begin
 if(!$value$plusargs("ROOT=%s",root))$fatal(1,"FAIL: ROOT argument");
 for(k=0;k<64;k=k+1)begin source_type[k]=-1;source_ts[k]=0;received[k]=0;end
 $readmemh({root,"/00_source.mem"},negative);$readmemh({root,"/05_source.mem"},palm);
 $readmemh("model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/golden_integer/sample_00/locator_output_stream_addr12_data32.mem",negative_stream);
 $readmemh("model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/golden_integer/sample_05/locator_output_stream_addr12_data32.mem",palm_stream);
 $readmemh("model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/golden_integer/sample_05/classifier_input_u8.mem",palm_roi);
 $readmemh("model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/golden_integer/sample_05/classifier_fc2_logits_i32.mem",palm_logits);
 force dut.u_vision.camera_init_done=1'b1;force dut.u_vision.camera_init_error=1'b0;
 repeat(10)@(negedge clk);rst=1;repeat(30)@(negedge pclk);
 for(frame=0;frame<12;frame=frame+1)begin
  stimulus_type=(frame%3==0)?0:5;
  vsync=1;repeat(8)@(negedge pclk);vsync=0;repeat(8)@(negedge pclk);
  for(y=0;y<480;y=y+1)begin
   @(negedge pclk);href=1;
   for(x=0;x<640;x=x+1)begin
    k=y*640+x;data=((stimulus_type==5?palm[k/4]:negative[k/4])>>(8*(k%4)))&255;
    @(negedge pclk);data=128;@(negedge pclk);
   end
   href=0;repeat(20)@(negedge pclk);
  end
  // VGA active+blank input interval about16.67ms. This is a synthetic
  // throughput stimulus, not a claim about the configured real sensor.
  repeat(175000)@(negedge pclk);
 end
 while(!dut.u_vision.u_scheduler.pipeline_idle || |dut.u_vision.camera_buffer_valid)begin
  @(negedge clk);drain=drain+1;if(drain>6000000)$fatal(1,"FAIL: streaming drain timeout");
 end
 repeat(30)@(negedge clk);
 if(results<8 || misses==0 || classifications==0 || overlaps<2)$fatal(1,"FAIL: insufficient streaming coverage %0d/%0d/%0d/%0d",results,misses,classifications,overlaps);
 $display("PASS: STREAM_OVERLAP 12 synthetic VGA frames results=%0d misses=%0d classifications=%0d overlaps=%0d; every locator/ROI/logit/id/time exact; D5 low",results,misses,classifications,overlaps);
 $finish;
end
endmodule
