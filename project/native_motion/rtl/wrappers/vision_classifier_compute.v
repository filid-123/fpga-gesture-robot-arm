// Structural wrapper: original instances, parameters and cycles preserved.
`timescale 1ns/1ps
module vision_classifier_compute #(
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
    output wire  classifier_busy,
    output wire [8:0] classifier_class,
    output wire  classifier_done,
    output wire [13:0] classifier_input_addr,
    input wire [7:0] classifier_input_data,
    output wire  classifier_input_en,
    output wire [15:0] classifier_margin,
    input wire  classifier_start,
    input wire  clk_100mhz,
    input wire  rst_100mhz_n
);
wire [7:0] classifier_desc_addr;
wire [31:0] classifier_desc_data;
wire  classifier_desc_en;
wire [15:0] classifier_weight2_addr;
wire [7:0] classifier_weight2_data;
wire  classifier_weight2_en;
wire [15:0] classifier_weight_addr;
wire [7:0] classifier_weight_data;
wire  classifier_weight_en;
cnn_desc_mem #(.MEM_INIT_FILE(CLASSIFIER_DESC_FILE)) u_classifier_desc (
        .clk(clk_100mhz), .wr_en(1'b0), .wr_addr(8'd0), .wr_data(32'd0),
        .rd_en(classifier_desc_en), .rd_addr(classifier_desc_addr),
        .rd_data(classifier_desc_data)
    );
cnn_weight_rom_compact #(.MEM_INIT_FILE(CLASSIFIER_WEIGHT_FILE),.WORDS(9872),.READ_PORTS(CLASSIFIER_LANES)) u_classifier_weights (
        .clk(clk_100mhz), .we_a(1'b0), .addr_a(16'd0), .din_a(32'd0),
        .dout_a(), .en_b(classifier_weight_en), .addr_b(classifier_weight_addr),
        .dout_b(classifier_weight_data),.en_c(classifier_weight2_en),.addr_c(classifier_weight2_addr),.dout_c(classifier_weight2_data)
    );
cnn_core_7c #(.CONV_LANES(CLASSIFIER_LANES),.DENSE_PIPELINED_REQUANT(1),.FIXED_SHIFT31(1)) u_classifier (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n), .start(classifier_start),
        .busy(classifier_busy), .done(classifier_done),
        .desc_bram_en(classifier_desc_en), .desc_bram_addr(classifier_desc_addr),
        .desc_bram_data(classifier_desc_data), .w_bram_en(classifier_weight_en),
        .w_bram_addr(classifier_weight_addr), .w_bram_data(classifier_weight_data),
        .w2_bram_en(classifier_weight2_en),.w2_bram_addr(classifier_weight2_addr),.w2_bram_data(classifier_weight2_data),
        .in_bram_en(classifier_input_en), .in_bram_addr(classifier_input_addr),
        .in_bram_data(classifier_input_data), .final_class_id(classifier_class),
        .final_margin(classifier_margin)
    );
endmodule
