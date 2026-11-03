// Structural wrapper: original instances, parameters and cycles preserved.
`timescale 1ns/1ps
module vision_roi_memory_pipeline #(
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
    input wire [13:0] classifier_input_addr,
    input wire [1:0] camera_buffer_valid,
    input wire [31:0] camera_frame_id_0,
    input wire [31:0] camera_frame_id_1,
    input wire  camera_mem_we,
    input wire [12:0] camera_mem_write_addr,
    input wire [31:0] camera_mem_write_data,
    input wire [12:0] camera_read_addr,
    output wire [31:0] camera_read_data,
    input wire  camera_read_en,
    output wire [7:0] classifier_input_data,
    input wire  classifier_input_en,
    input wire  classifier_read_bank,
    input wire  clk_100mhz,
    input wire  locator_busy,
    input wire  roi_buffer_id,
    output wire  roi_busy,
    output wire  roi_done,
    output wire  roi_error,
    output wire [12:0] roi_read_addr,
    output wire  roi_read_en,
    input wire  roi_start,
    input wire [31:0] roi_tag,
    input wire  roi_write_bank,
    input wire  rst_100mhz_n,
    input wire // Map the frozen source-space descriptor onto the Phase2 content grid.
    // The alternative contract is floor(x/5),16+floor(y/5),ceil(side/5).
    // Scheduler inserts a full cycle before ROI start. Register the small
    // descriptor in that existing interval, cutting geometry-to-address CE.
     [9:0] small_side,
    input wire // Map the frozen source-space descriptor onto the Phase2 content grid.
    // The alternative contract is floor(x/5),16+floor(y/5),ceil(side/5).
    // Scheduler inserts a full cycle before ROI start. Register the small
    // descriptor in that existing interval, cutting geometry-to-address CE.
     [9:0] small_x,
    input wire // Map the frozen source-space descriptor onto the Phase2 content grid.
    // The alternative contract is floor(x/5),16+floor(y/5),ceil(side/5).
    // Scheduler inserts a full cycle before ROI start. Register the small
    // descriptor in that existing interval, cutting geometry-to-address CE.
     [9:0] small_y
);
wire [31:0] roi_completed_frame_unused;
wire [31:0] roi_completed_tag_unused;
wire [7:0] roi_word_addr;
wire [31:0] roi_word_data;
wire  roi_word_we;
camera_locator_input_bram #(.ADDR_BITS(13)) u_camera_memory (
        .clk(clk_100mhz), .camera_we(camera_mem_we),
        .camera_word_addr(camera_mem_write_addr), .camera_wdata(camera_mem_write_data),
        .locator_en(camera_read_en), .locator_word_addr(camera_read_addr),
        .locator_rdata(camera_read_data)
    );
same_frame_roi_128x128 u_same_frame_roi (
        .clk(clk_100mhz),.rst_n(rst_100mhz_n),.start(roi_start),.buffer_id(roi_buffer_id),
        .desc_x0(small_x),.desc_y0(small_y),.desc_side(small_side),.desc_tag(roi_tag),
        .buffer_valid_mask(camera_buffer_valid),.buffer_frame_id_0(camera_frame_id_0),.buffer_frame_id_1(camera_frame_id_1),
        .read_grant(!locator_busy),.camera_read_en(roi_read_en),.camera_read_word_addr(roi_read_addr),.camera_read_data(camera_read_data),
        .busy(roi_busy),.done_pulse(roi_done),.error_pulse(roi_error),
        .completed_tag(roi_completed_tag_unused),.completed_source_frame_id(roi_completed_frame_unused),
        .roi_word_we(roi_word_we),.roi_word_addr(roi_word_addr),.roi_word_data(roi_word_data));
classifier_roi_pingpong u_classifier_input (
        .clk(clk_100mhz), .wr_en(roi_word_we),.wr_bank(roi_write_bank),
        .wr_word_addr(roi_word_addr), .wr_data(roi_word_data),
        .rd_en(classifier_input_en),.rd_bank(classifier_read_bank),
        .rd_byte_addr(classifier_input_addr[9:0]), .rd_data(classifier_input_data)
    );
endmodule
