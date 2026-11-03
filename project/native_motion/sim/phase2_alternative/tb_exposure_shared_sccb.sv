`timescale 1ns/1ps
module tb_exposure_shared_sccb;
reg clk=0,pclk=0,rst=0;always #5 clk=~clk;always #10.416667 pclk=~pclk;
reg start=0,readcmd=0,nack=0;reg[15:0]addr=0;reg[7:0]data=0,reply=8'h02;
wire ready,busy,done,err;wire[7:0]readback;wire scllow,sdalow;
reg sensor_data;
wire sdain=sdalow?1'b0:sensor_data;
integer bytes=0,runtime_bytes=0;reg[7:0]observed[0:7];
gesture_autonomous_top_black #(.CAMERA_CONTROL(1),
.LOCATOR_MODEL_FILE("model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/locator/model_rom_16k.mem"),
.CLASSIFIER_WEIGHT_FILE("model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/classifier/weights_all.mem"),
.CLASSIFIER_DESC_FILE("model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/classifier/layer_descriptors.mem"),
.OV5640_INIT_FILE("native_motion/rtl/autonomous/ov5640_vga_yuyv.mem"),.GEOMETRY_ALPHA_FILE("native_motion/geometry_alpha_q16.mem")) dut(
.clk_100mhz(clk),.rst_100mhz_n(rst),.clk_50mhz(clk),.rst_50mhz_n(rst),
.pclk(pclk),.pclk_rst_n(rst),.dvp_data(8'd0),.dvp_href(1'b0),.dvp_vsync(1'b1),.xclk_locked(1'b1),
.sccb_scl_drive_low(scllow),.sccb_sda_drive_low(sdalow),.sccb_sda_in(sdain),
.camera_cmd_start(start),.camera_cmd_read(readcmd),.camera_cmd_addr(addr),.camera_cmd_data(data),
.camera_cmd_ready(ready),.camera_cmd_busy(busy),.camera_cmd_done(done),.camera_cmd_error(err),.sensor_read_data(readback),
.snapshot_enable(1'b0),.snapshot_rd_en(1'b0),.snapshot_word_addr(17'd0));
defparam dut.u_camera_init.POWER_DOWN_CYCLES=20;
defparam dut.u_camera_init.PWDN_LOW_CYCLES=20;
defparam dut.u_camera_init.RESET_WAIT_CYCLES=20;
defparam dut.u_camera_init.SOFT_RESET_CYCLES=20;
defparam dut.u_camera_init.STREAM_WAIT_CYCLES=20;
defparam dut.u_camera_init.RETRY_WAIT_CYCLES=20;
// Sensor drives data for the entire low/high half periods; top includes the real two-stage SDA sync.
always @* begin
 sensor_data=1;
 if(dut.u_sccb.state==4 || dut.u_sccb.state==5) sensor_data=nack;
 else if(dut.u_sccb.state==9 || dut.u_sccb.state==10) sensor_data=reply[dut.u_sccb.bit_index];
end
always @(posedge clk) if(rst && dut.u_sccb.half_tick && dut.u_sccb.state==5)begin
 if(dut.camera_init_done)begin observed[runtime_bytes]=dut.u_sccb.shift_byte;runtime_bytes=runtime_bytes+1;end
 else bytes=bytes+1;
end
task issue(input r,input[15:0]a,input[7:0]v);
begin
 wait(ready);@(negedge clk);runtime_bytes=0;readcmd=r;addr=a;data=v;start=1;
 @(negedge clk);start=0;wait(done);@(negedge clk);
 if(runtime_bytes!=4||observed[0]!==8'h78||observed[1]!==a[15:8]||observed[2]!==a[7:0]||observed[3]!==(r?8'h79:v))
 $fatal(1,"FAIL: shared SCCB framing/ownership");
 if(!dut.camera_init_done||dut.camera_init_error)$fatal(1,"FAIL: runtime response corrupted init");
end endtask
initial begin
 repeat(4)@(negedge clk);rst=1;repeat(20)@(negedge clk);
 if(ready||done)$fatal(1,"FAIL: runtime port enabled during initialization");
 wait(ready);if(bytes!=636)$fatal(1,"FAIL: not all original init bytes");
 issue(1,'h3503,0);if(err||readback!==2)$fatal(1,"FAIL: synchronized read");
 issue(0,'h3503,3);if(err)$fatal(1,"FAIL: manual write");
 reply=3;issue(1,'h3503,0);if(err||readback!==3)$fatal(1,"FAIL: runtime readback");
 nack=1;issue(0,'h350b,'h10);if(!err)$fatal(1,"FAIL: NACK hidden");
 rst=0;repeat(4)@(negedge clk);if(ready||busy||done)$fatal(1,"FAIL: reset ownership");
 $display("PASS: SHARED_SCCB original159 writes, runtime handoff/read/write/readback/NACK/two-stageSDA/reset; single master100kHz");$finish;
end
initial begin #80000000;$fatal(1,"FAIL: shared SCCB watchdog");end
endmodule
