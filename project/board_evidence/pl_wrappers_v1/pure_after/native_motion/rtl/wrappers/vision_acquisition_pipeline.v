// Structural wrapper: original instances, parameters and cycles preserved.
`timescale 1ns/1ps
module vision_acquisition_pipeline #(
    parameter LOCATOR_MODEL_FILE     = "model_rom_16k.mem",
    parameter CLASSIFIER_WEIGHT_FILE = "weights_all.mem",
    parameter CLASSIFIER_DESC_FILE   = "layer_descriptors.mem",
    parameter GEOMETRY_ALPHA_FILE="geometry_alpha_q16.mem",
    parameter integer HD_PREVIEW=0,
    parameter integer CLASSIFIER_LANES=1,
    parameter integer GEOMETRY_EMA=1,
    parameter integer CAMERA_CONTROL=0,
    parameter integer OBJECT_HOLD_MS=200,PALM_HOLD_MS=300,FIST_HOLD_MS=80,
    parameter OV5640_INIT_FILE       = "ov5640_vga_yuyv.mem",
    parameter [31:0] CONFIRM_COUNTS = {4'd3, 4'd2, 4'd2, 4'd2, 4'd2, 4'd2, 4'd2, 4'd3},
    parameter [7:0]  GATED_CODES    = 8'b0011_1110,
    parameter [15:0] MARGIN_MIN     = 16'd0
)(
    output wire [1:0] camera_buffer_valid,
    input wire [15:0] camera_cmd_addr,
    input wire [7:0] camera_cmd_data,
    input wire  camera_cmd_read,
    input wire  camera_cmd_start,
    output wire [31:0] camera_frame_id_0,
    output wire [31:0] camera_frame_id_1,
    output wire  camera_frame_published,
    output wire  camera_init_done,
    output wire  camera_init_error,
    output wire  camera_latest_buffer,
    output wire [31:0] camera_latest_frame_id,
    output wire  camera_mem_we,
    output wire [12:0] camera_mem_write_addr,
    output wire [31:0] camera_mem_write_data,
    output wire  camera_pwdn,
    output wire  camera_reset_n,
    input wire  capture_enable,
    input wire  clk_100mhz,
    output wire [13:0] debug_preview_addr,
    output wire [31:0] debug_preview_data,
    output wire [31:0] debug_preview_id,
    output wire  debug_preview_published,
    output wire  debug_preview_we,
    input wire [7:0] dvp_data,
    input wire  dvp_href,
    input wire  dvp_vsync,
    input wire [1:0] effective_release,
    output wire  fifo_overflow,
    output wire [31:0] format_error_count,
    output wire [31:0] frame_drop_count,
    output wire [31:0] frame_timestamp_ms_0,
    output wire [31:0] frame_timestamp_ms_1,
    input wire  init_cmd_ready,
    output wire  master_ready,
    output wire [31:0] now_ms,
    input wire  pclk,
    input wire  pclk_rst_n,
    input wire  rst_100mhz_n,
    input wire  runtime_select,
    output wire  sccb_ack_error,
    output wire  sccb_busy_unused,
    output wire  sccb_done,
    output wire [7:0] sccb_read_data_unused,
    output wire  sccb_scl_drive_low,
    output wire  sccb_sda_drive_low,
    input wire  sccb_sda_sync,
    input wire  xclk_locked
);
wire  init_cmd_read;
wire  init_cmd_valid;
wire [6:0] init_device_addr;
wire [15:0] init_register_addr;
wire [7:0] init_write_data;
ov5640_init_fsm #(.INIT_FILE(OV5640_INIT_FILE)) u_camera_init (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n), .xclk_locked(xclk_locked),
        .camera_reset_n(camera_reset_n), .camera_pwdn(camera_pwdn),
        .cmd_valid(init_cmd_valid), .cmd_ready(init_cmd_ready),
        .cmd_read(init_cmd_read), .device_addr(init_device_addr),
        .register_addr(init_register_addr), .write_data(init_write_data),
        .cmd_done(sccb_done), .cmd_ack_error(sccb_ack_error),
        .init_done(camera_init_done), .init_error(camera_init_error)
    );
sccb_master_sync u_sccb (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n),
        .cmd_valid(runtime_select ? camera_cmd_start : init_cmd_valid), .cmd_ready(master_ready),
        .cmd_read(runtime_select ? camera_cmd_read : init_cmd_read), .device_addr(init_device_addr),
        .register_addr(runtime_select ? camera_cmd_addr : init_register_addr),
        .write_data(runtime_select ? camera_cmd_data : init_write_data),
        .read_data(sccb_read_data_unused), .busy(sccb_busy_unused),
        .done(sccb_done), .ack_error(sccb_ack_error),
        .scl_drive_low(sccb_scl_drive_low),
        .sda_drive_low(sccb_sda_drive_low), .sda_in(sccb_sda_sync)
    );
ov5640_phase2_frontend #(.HD_PREVIEW(HD_PREVIEW),
        .Y_BYTE_PHASE(0),.VSYNC_ACTIVE_HIGH(1),.FIFO_ADDR_WIDTH(10)
    ) u_camera_frontend (
        .preview_we(debug_preview_we),.preview_addr(debug_preview_addr),.preview_data(debug_preview_data),.preview_published(debug_preview_published),.preview_id(debug_preview_id),
        .pclk(pclk),.pclk_rst_n(pclk_rst_n),.dvp_data(dvp_data),
        .dvp_href(dvp_href),.dvp_vsync(dvp_vsync),.capture_enable(capture_enable),
        .sys_clk(clk_100mhz),.sys_rst_n(rst_100mhz_n),.buffer_release(effective_release),
        .buffer_valid_mask(camera_buffer_valid),.buffer_frame_id_0(camera_frame_id_0),
        .buffer_frame_id_1(camera_frame_id_1),.frame_published(camera_frame_published),
        .latest_buffer_id(camera_latest_buffer),.latest_frame_id(camera_latest_frame_id),
        .mem_we(camera_mem_we),.mem_word_addr(camera_mem_write_addr),.mem_wdata(camera_mem_write_data),
        .buffer_timestamp_ms_0(frame_timestamp_ms_0),.buffer_timestamp_ms_1(frame_timestamp_ms_1),.now_ms(now_ms),
        .frame_drop_count(frame_drop_count),.format_error_count(format_error_count),.fifo_overflow_sticky(fifo_overflow)
    );
endmodule
