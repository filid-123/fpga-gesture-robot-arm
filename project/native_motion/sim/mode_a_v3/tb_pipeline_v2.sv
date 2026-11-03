`timescale 1ns/1ps
// Simulation only: real deployed RTL, synthetic VGA yielding exact saved128 input.
module tb_pipeline_v2;
 reg clk=0,pclk=0,c50=0; always #5 clk=~clk;always #10.416667 pclk=~pclk;always #10 c50=~c50;
 reg rst=0,href=0,vsync=1;reg[7:0] data=0;
 wire result,det;wire[2:0] cls,model;wire[31:0] fid;wire[9:0] rx,ry,rs;
 reg[31:0] source[0:76799],small_image[0:4095];
 integer n=0,x,y,k,cycles,writes=0,outputs=0,roiwords=0,logits=0;
 integer finput,floc,froi,flog,fmeta;string root,outdir;
 gesture_autonomous_top_black #(
 .LOCATOR_MODEL_FILE("model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/locator/model_rom_16k.mem"),
 .CLASSIFIER_WEIGHT_FILE("model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/classifier/weights_all.mem"),
 .CLASSIFIER_DESC_FILE("model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/classifier/layer_descriptors.mem"),
 .GEOMETRY_EMA(0),
 .OV5640_INIT_FILE("native_motion/rtl/autonomous/ov5640_vga_yuyv.mem"),
 .GEOMETRY_ALPHA_FILE("native_motion/geometry_alpha_q16.mem")) dut(
 .clk_100mhz(clk),.rst_100mhz_n(rst),.clk_50mhz(c50),.rst_50mhz_n(rst),.pclk(pclk),.pclk_rst_n(rst),
 .dvp_data(data),.dvp_href(href),.dvp_vsync(vsync),.xclk_locked(1'b1),.sccb_sda_in(1'b0),
 .snapshot_enable(1'b0),.snapshot_rd_en(1'b0),.snapshot_word_addr(17'd0),
 .camera_cmd_start(1'b0),.camera_cmd_read(1'b0),.camera_cmd_addr(16'd0),.camera_cmd_data(8'd0),
 .debug_result_valid(result),.debug_result_detected(det),.debug_result_frame_id(fid),
 .debug_candidate_class(cls),.debug_model_class(model),.debug_roi_x0(rx),.debug_roi_y0(ry),.debug_roi_side(rs));
 always @(negedge clk) if(rst) begin
  if(dut.camera_mem_we)begin
   if(dut.camera_mem_write_data!==small_image[dut.camera_mem_write_addr[11:0]])
    $fatal(1,"FAIL: frontend byte data word=%0d",dut.camera_mem_write_addr);
   $fdisplay(finput,"%03x %08x",dut.camera_mem_write_addr,dut.camera_mem_write_data);writes=writes+1;
  end
  if(dut.u_locator_compute.locator_output_we)begin $fdisplay(floc,"%08x",dut.u_locator_compute.locator_output_data);outputs=outputs+1;end
  if(dut.u_pipeline_control.bbox_done) $fdisplay(fmeta,"BBOX %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
    dut.top1_cell,$signed(dut.top1_confidence),$signed(dut.top1_dx),$signed(dut.top1_dy),$signed(dut.top1_width),$signed(dut.top1_height),det,rx,ry,rs,dut.small_x,dut.small_y,dut.small_side);
  if(dut.roi_start)$fdisplay(fmeta,"SMALL %0d %0d %0d",dut.small_x,dut.small_y,dut.small_side);
  if(dut.u_roi_memory.roi_word_we)begin
   if(dut.u_roi_memory.roi_word_addr!==roiwords[7:0])$fatal(1,"FAIL: ROI word order");
   for(integer b=0;b<4;b=b+1)$fdisplay(froi,"%02x",(dut.u_roi_memory.roi_word_data>>(8*b))&255);roiwords=roiwords+1;
  end
  if(dut.u_classifier_compute.u_classifier.dense_inst.state==7 && dut.u_classifier_compute.u_classifier.layer_is_final)begin
   if(dut.u_classifier_compute.u_classifier.dense_inst.cur_co!=logits)$fatal(1,"FAIL: logit order");
   $fdisplay(flog,"%08x",dut.u_classifier_compute.u_classifier.dense_inst.acc);logits=logits+1;
  end
  if(dut.fatal_error || dut.fifo_overflow || dut.format_error_count!=0)$fatal(1,"FAIL: pipeline fault");
 end
 initial begin
  if(!$value$plusargs("CASE=%d",n) || !$value$plusargs("ROOT=%s",root) || !$value$plusargs("OUT=%s",outdir))$fatal(1,"FAIL: missing args");
  finput=$fopen({outdir,"/camera_words.txt"},"w");floc=$fopen({outdir,"/locator_output.mem"},"w");
  froi=$fopen({outdir,"/classifier_input.mem"},"w");flog=$fopen({outdir,"/classifier_logits.mem"},"w");fmeta=$fopen({outdir,"/metadata.txt"},"w");
  if(!finput || !floc || !froi || !flog || !fmeta)$fatal(1,"FAIL: dump file open");
  $readmemh($sformatf("%s/%02d_source.mem",root,n),source);$readmemh($sformatf("%s/%02d_small.mem",root,n),small_image);
  // Bypass only the external SCCB slave; camera initialization tested separately.
  force dut.camera_init_done=1'b1;force dut.camera_init_error=1'b0;
  repeat(10)@(negedge clk);rst=1;repeat(30)@(negedge pclk);vsync=0;repeat(8)@(negedge pclk);
  for(y=0;y<480;y=y+1)begin
   @(negedge pclk);href=1;
   for(x=0;x<640;x=x+1)begin k=y*640+x;data=(source[k/4]>>(8*(k%4)))&255;@(negedge pclk);data=128;@(negedge pclk);end
   href=0;repeat(20)@(negedge pclk);
  end
  cycles=0;while(!result)begin @(negedge clk);cycles=cycles+1;if(cycles>6000000)$fatal(1,"FAIL: pipeline timeout");end
  if(writes!=4096 || outputs!=1280 || roiwords!=(det?256:0) || logits!=(det?6:0))$fatal(1,"FAIL: counts %0d %0d %0d %0d",writes,outputs,roiwords,logits);
  $fdisplay(fmeta,"RESULT %0d %0d %0d %0d %0d %0d %0d",det,model,cls,fid,rx,ry,rs);
  $fclose(finput);$fclose(floc);$fclose(froi);$fclose(flog);$fclose(fmeta);
  $display("PASS: V2_PIPELINE real RTL case=%0d camera=%0d raw=%0d ROIwords=%0d logits=%0d model=%0d",n,writes,outputs,roiwords,logits,model);$finish;
 end
endmodule
