`timescale 1ns/1ps
module tb_roarm_sccb;
 reg clk=0,pclk=0,rst=0,locked=1,nack=0;
 always #5 clk=~clk;always #10.416667 pclk=~pclk;
 wire scl_low,sda_low,reset_n,pwdn;
 tri1 sda;wire scl=~scl_low;
 reg ack_drive=0,active=0;integer bit_count=0,byte_count=0,transactions=0,cycles;
 reg [7:0] shift=0;reg [23:0] commands[0:158];reg [7:0] expected;
 assign sda=sda_low?1'b0:1'bz;
 assign sda=ack_drive?1'b0:1'bz;
 gesture_autonomous_top_black #(
  .LOCATOR_MODEL_FILE("model_package/candidates/black_scene_vision_v1_int8_20261013/quantized/locator/model_rom_16k.mem"),
  .CLASSIFIER_DESC_FILE("model_package/candidates/black_scene_vision_v1_int8_20261013/quantized/classifier/layer_descriptors.mem"),
  .CLASSIFIER_WEIGHT_FILE("model_package/candidates/black_scene_vision_v1_int8_20261013/quantized/classifier/weights_all.mem"),
  .OV5640_INIT_FILE("native_motion/rtl/autonomous/ov5640_vga_yuyv.mem"),.GEOMETRY_ALPHA_FILE("native_motion/geometry_alpha_q16.mem")) dut(
  .clk_100mhz(clk),.rst_100mhz_n(rst),.clk_50mhz(clk),.rst_50mhz_n(rst),
  .pclk(pclk),.pclk_rst_n(rst),.dvp_data(8'd0),.dvp_href(1'b0),.dvp_vsync(1'b1),
  .xclk_locked(locked),.camera_reset_n(reset_n),.camera_pwdn(pwdn),
  .sccb_scl_drive_low(scl_low),.sccb_sda_drive_low(sda_low),.sccb_sda_in(sda),
  .snapshot_enable(1'b0),.snapshot_rd_en(1'b0),.snapshot_word_addr(17'd0));
 // Only the long power/stream/retry delays are shortened. Real SCCB remains
 // 100 kHz; every byte of all 159 register writes is checked at the bus pins.
 defparam dut.u_camera_init.POWER_DOWN_CYCLES=20;
 defparam dut.u_camera_init.PWDN_LOW_CYCLES=20;
 defparam dut.u_camera_init.RESET_WAIT_CYCLES=20;
 defparam dut.u_camera_init.SOFT_RESET_CYCLES=20;
 defparam dut.u_camera_init.STREAM_WAIT_CYCLES=20;
 defparam dut.u_camera_init.RETRY_WAIT_CYCLES=20;
 always @(negedge sda) if(rst && scl) begin
  active=1;bit_count=0;byte_count=0;shift=0;
 end
 always @(posedge sda) if(scl) active=0;
 always @(negedge scl) begin
  // Model the sensor's asynchronous output propagation (not aligned to clk).
  #2 ack_drive=active && bit_count==8 && !nack;
 end
 always @(posedge scl) if(active && rst) begin
  if(bit_count<8) begin shift={shift[6:0],sda};bit_count=bit_count+1;end
  else begin
   if(!nack)begin
    case(byte_count)
     0:expected=8'h78;
     1:expected=commands[transactions][23:16];
     2:expected=commands[transactions][15:8];
     3:expected=commands[transactions][7:0];
     default:$fatal(1,"FAIL: extra SCCB byte");
    endcase
    if(shift!==expected)$fatal(1,"FAIL: SCCB transaction %0d byte %0d got %02x expected %02x",transactions,byte_count,shift,expected);
   end
   bit_count=0;byte_count=byte_count+1;
   if(byte_count==4)begin transactions=transactions+1;active=0;end
  end
 end
 task reset_case;
 begin rst=0;ack_drive=0;active=0;bit_count=0;byte_count=0;transactions=0;
  repeat(8)@(negedge clk);rst=1;end
 endtask
 initial begin
  $readmemh("native_motion/rtl/autonomous/ov5640_vga_yuyv.mem",commands);
  reset_case();cycles=0;
  while(!dut.camera_init_done && !dut.camera_init_error && cycles<7000000)begin @(negedge clk);cycles=cycles+1;end
  if(!dut.camera_init_done || dut.camera_init_error || transactions!=159 || !reset_n || pwdn)
   $fatal(1,"FAIL: SCCB init done=%b error=%b writes=%0d",dut.camera_init_done,dut.camera_init_error,transactions);
  $display("PASS: ROARM_SCCB two-stage SDA, all 159 register writes/636 bytes, 100 kHz ACK");
  locked=0;repeat(4)@(negedge clk);
  if(!dut.camera_init_error || dut.camera_init_done || reset_n || !pwdn)$fatal(1,"FAIL: SCCB lost XCLK lock");
  locked=1;nack=1;reset_case();cycles=0;
  while(!dut.camera_init_error && cycles<200000)begin @(negedge clk);cycles=cycles+1;end
  if(!dut.camera_init_error || dut.camera_init_done || reset_n || !pwdn || transactions!=3)
   $fatal(1,"FAIL: SCCB NACK retry/error writes=%0d",transactions);
  $display("PASS: ROARM_SCCB NACK three attempts, fail closed, XCLK loss, reset");
  $finish;
 end
endmodule
