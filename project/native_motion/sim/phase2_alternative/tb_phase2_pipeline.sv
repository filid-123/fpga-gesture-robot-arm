`timescale 1ns/1ps
module tb_phase2_pipeline;
 reg clk=0,pclk=0,c50=0;always #5 clk=~clk;always #10.416667 pclk=~pclk;always #10 c50=~c50;
 reg rst=0,href=0,vsync=1;reg [7:0] data=0;
 reg snap=0,sren=0;reg[16:0]saddr=0;wire srdy;wire[31:0]sdata,sfid;
 wire result,det;wire [2:0] cls,model;wire [31:0] fid;wire [9:0] rx,ry,rs;
 reg [31:0] source[0:76799],expected[0:255],configs[0:15];integer n,x,y,k,writes,cycles;reg[31:0]cfg[0:7],small_image[0:4095];integer expected_writes=0;
 string root="D:/FPGA_Projects/Gesture/board_evidence/mode_a_phase2_frontend_20261022_v0_1_0/fixtures/";
 gesture_autonomous_top_black #(
 .LOCATOR_MODEL_FILE("model_package/candidates/black_scene_vision_v1_int8_20261013/quantized/locator/model_rom_16k.mem"),
 .CLASSIFIER_WEIGHT_FILE("model_package/candidates/black_scene_vision_v1_int8_20261013/quantized/classifier/weights_all.mem"),
 .CLASSIFIER_DESC_FILE("model_package/candidates/black_scene_vision_v1_int8_20261013/quantized/classifier/layer_descriptors.mem"),
 .OV5640_INIT_FILE("native_motion/rtl/autonomous/ov5640_vga_yuyv.mem"),
 .GEOMETRY_EMA(0),.GEOMETRY_ALPHA_FILE("native_motion/geometry_alpha_q16.mem")) dut(
 .clk_100mhz(clk),.rst_100mhz_n(rst),.clk_50mhz(c50),.rst_50mhz_n(rst),.pclk(pclk),.pclk_rst_n(rst),
 .dvp_data(data),.dvp_href(href),.dvp_vsync(vsync),.xclk_locked(1'b1),.sccb_sda_in(1'b0),
 .snapshot_enable(snap),.snapshot_rd_en(sren),.snapshot_word_addr(saddr),.snapshot_ready(srdy),.snapshot_data(sdata),.snapshot_frame_id(sfid),
 .debug_result_valid(result),.debug_result_detected(det),.debug_result_frame_id(fid),
 .debug_candidate_class(cls),.debug_model_class(model),.debug_roi_x0(rx),.debug_roi_y0(ry),.debug_roi_side(rs));
 always @(negedge clk) if(rst) begin
  if(dut.roi_word_we) begin
   if(dut.roi_word_data!==expected[writes]) $fatal(1,"FAIL: integrated ROI word=%0d",writes);
   writes=writes+1;
  end
 end
 task byte_out(input [7:0] b);begin @(negedge pclk);data=b;end endtask
 initial begin
  n=0;if($value$plusargs("CASE=%d",n))begin end
  force dut.camera_init_done=1'b1;force dut.camera_init_error=1'b0;
  $readmemh($sformatf("%ssample_%02d_source.mem",root,n),source);
  $readmemh($sformatf("%ssample_%02d_small.mem",root,n),small_image);
  $readmemh($sformatf("%ssample_%02d_config.mem",root,n),cfg);
  if(cfg[7])$readmemh($sformatf("%ssample_%02d_roi.mem",root,n),expected);
  begin
   rst=0;href=0;vsync=1;snap=0;sren=0;repeat(10)@(negedge clk);
   writes=0;rst=1;repeat(30)@(negedge pclk);vsync=0;repeat(8)@(negedge pclk);
   for(y=0;y<480;y=y+1) begin
    @(negedge pclk);href=1;
    for(x=0;x<640;x=x+1) begin k=y*640+x;data=(source[k/4]>>(8*(k%4)))&255;@(negedge pclk);data=128;@(negedge pclk);end
    href=0;repeat(20)@(negedge pclk);
   end
   if(n==0)begin wait(dut.locator_busy);@(negedge clk);snap=1;end
   cycles=0;
   while(!result)begin @(negedge clk);cycles=cycles+1;
    if(srdy && dut.u_scheduler.state!=1)$fatal(1,"FAIL: snapshot raced active pipeline");
    // The tested ROI maximum is 2.882M clocks (side 479), plus locator
    // 2.357M and classifier 0.751M; allow 6M after capture, not old 5M.
    if(cycles>5000000)$fatal(1,"FAIL: integrated pipeline timeout leds=%h scheduler=%d",dut.leds,dut.u_scheduler.state);
   end
   if(det!==cfg[7][0] || writes!=(cfg[7]?256:0))$fatal(1,"FAIL: alternate pipeline ROI/detection");
   if(cfg[7] && (rx!==cfg[0][9:0] || ry!==cfg[1][9:0] || rs!==cfg[2][9:0] || model!==cfg[6][2:0]))
     $fatal(1,"FAIL: independent source geometry/new classifier oracle case=%0d",n);
   if(cfg[7] && cls!==((model==4)?5:(model==5)?4:model))$fatal(1,"FAIL: class map");
   if(!cfg[7] && cls!=7)$fatal(1,"FAIL: locator miss produced actionable class");
   $display("PASS: PHASE2_PIPELINE case=%0d fid=%0d model=%0d task=%0d writes=%0d",n,fid,model,cls,writes);
   if(n==0)begin
    wait(srdy);@(negedge clk);sren=1;
    for(k=0;k<4096;k=k+1)begin
     saddr=k;repeat(3)@(negedge clk);
     if(!srdy || sfid!=fid || sdata!==small_image[k])$fatal(1,"FAIL: snapshot held source word=%0d",k);
    end
    sren=0;snap=0;
    $display("PASS: REAL_PIPELINE snapshot requested during LOC, waits for quiescence, all 16384 small_image-frame bytes exact");
    repeat(100)@(negedge clk);
    if(dut.locator_busy || dut.camera_buffer_valid!=0 || dut.deferred_release!=0)
      $fatal(1,"FAIL: snapshot exit restarted an already consumed source frame");
    $display("PASS: REAL_PIPELINE deferred release retires held frame without duplicate LOC on snapshot exit");
   end
  end
  $display("PASS: REAL_PIPELINE DVP/FIFO/Phase2 pingpong/context/nearest/classifier/scheduler");$finish;
 end
endmodule
