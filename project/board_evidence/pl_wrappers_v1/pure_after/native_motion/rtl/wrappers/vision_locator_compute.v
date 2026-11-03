// Structural wrapper: original instances, parameters and cycles preserved.
`timescale 1ns/1ps
module vision_locator_compute #(
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
    input wire [31:0] camera_read_data,
    input wire  clk_100mhz,
    output wire  locator_busy,
    output wire  locator_done,
    input wire [31:0] locator_frame_id,
    output wire [12:0] locator_input_addr,
    input wire  locator_input_buffer,
    output wire  locator_input_en,
    input wire  locator_start,
    input wire  rst_100mhz_n,
    output wire [31:0] top1_cell,
    output wire [31:0] top1_confidence,
    output wire [31:0] top1_dx,
    output wire [31:0] top1_dy,
    output wire [31:0] top1_height,
    output wire [31:0] top1_width
);
wire [31:0] locator_debug_acc_data_unused;
wire [17:0] locator_debug_acc_index_unused;
wire  locator_debug_acc_valid_unused;
wire [7:0] locator_debug_act_data_unused;
wire [14:0] locator_debug_act_index_unused;
wire  locator_debug_act_valid_unused;
wire [2:0] locator_debug_layer_unused;
wire  locator_input_release_unused;
wire [95:0] locator_model_addr;
wire [255:0] locator_model_data;
wire [7:0] locator_model_en;
wire [11:0] locator_output_addr;
wire [31:0] locator_output_data;
wire  locator_output_we;
wire  locator_stall_unused;
wire [31:0] top1_bank1_cell_unused;
wire [31:0] top1_bank1_conf_unused;
wire [31:0] top1_bank1_dx_unused;
wire [31:0] top1_bank1_dy_unused;
wire [31:0] top1_bank1_height_unused;
wire [31:0] top1_bank1_width_unused;
locator_context_rom_8lane #(.MEM_INIT_FILE(LOCATOR_MODEL_FILE))
    u_locator_model (
        .clk(clk_100mhz), .lane_rd_en(locator_model_en),
        .lane_rd_addr(locator_model_addr), .lane_rd_data(locator_model_data)
    );
locator_cnn_engine_context_8lane u_locator (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n), .start(locator_start),
        .input_buffer_id(locator_input_buffer), .output_buffer_id(1'b0),
        .frame_id(locator_frame_id), .input_bram_en(locator_input_en),
        .input_bram_addr(locator_input_addr), .input_bram_data(camera_read_data),
        .output_bram_we(locator_output_we), .output_bram_addr(locator_output_addr),
        .output_bram_data(locator_output_data), .model_lane_rd_en(locator_model_en),
        .model_lane_rd_addr(locator_model_addr), .model_lane_rd_data(locator_model_data),
        .busy(locator_busy), .done(locator_done),
        .input_release(locator_input_release_unused), .stall(locator_stall_unused),
        .debug_acc_valid(locator_debug_acc_valid_unused),
        .debug_layer(locator_debug_layer_unused),
        .debug_acc_index(locator_debug_acc_index_unused),
        .debug_acc_data(locator_debug_acc_data_unused),
        .debug_act_valid(locator_debug_act_valid_unused),
        .debug_act_index(locator_debug_act_index_unused),
        .debug_act_data(locator_debug_act_data_unused)
    );
locator_top1_reducer u_top1 (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n), .start(locator_start),
        .output_buffer_id(1'b0), .done(locator_done),
        .output_we(locator_output_we), .output_addr(locator_output_addr),
        .output_data(locator_output_data), .top1_cell_0(top1_cell),
        .top1_conf_0(top1_confidence), .top1_dx_0(top1_dx),
        .top1_dy_0(top1_dy), .top1_width_0(top1_width),
        .top1_height_0(top1_height), .top1_cell_1(top1_bank1_cell_unused),
        .top1_conf_1(top1_bank1_conf_unused),
        .top1_dx_1(top1_bank1_dx_unused), .top1_dy_1(top1_bank1_dy_unused),
        .top1_width_1(top1_bank1_width_unused),
        .top1_height_1(top1_bank1_height_unused)
    );
endmodule
