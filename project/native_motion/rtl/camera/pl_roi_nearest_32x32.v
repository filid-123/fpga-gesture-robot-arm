// ============================================================================
// Phase 2-L2 streaming ROI extractor.
//
// A descriptor written by PS is accepted at the next source-frame SOF. The
// selected square is resized to 32x32 Gray8 with the exact nearest mapping
//
//     source_index = floor(destination_index * side / 32)
//
// and packed four pixels per little-endian 32-bit word. side>=32 guarantees
// strictly increasing source coordinates, so the transform never stalls the
// live camera stream and never needs to duplicate a source token.
// ============================================================================
`timescale 1ns / 1ps

module pl_roi_nearest_32x32 #(
    parameter integer SOURCE_WIDTH  = 640,
    parameter integer SOURCE_HEIGHT = 480
)(
    input  wire        clk,
    input  wire        rst_n,

    input  wire        pixel_fire,
    input  wire [7:0]  pixel_data,
    input  wire [9:0]  pixel_x,
    input  wire [9:0]  pixel_y,
    input  wire        pixel_sof,

    input  wire        desc_arm,
    input  wire [9:0]  desc_x0,
    input  wire [9:0]  desc_y0,
    input  wire [9:0]  desc_side,
    input  wire [31:0] desc_tag,

    output reg         desc_armed,
    output wire        roi_busy,
    output reg         roi_done_pulse,
    output reg         roi_error_pulse,
    output reg  [31:0] completed_tag,
    output reg  [31:0] completed_source_frame_id,

    output reg         roi_word_we,
    output reg  [7:0]  roi_word_addr,
    output reg  [31:0] roi_word_data
);

    reg [9:0]  pending_x0;
    reg [9:0]  pending_y0;
    reg [9:0]  pending_side;
    reg [31:0] pending_tag;

    reg        active;
    reg [9:0]  active_x0;
    reg [9:0]  active_y0;
    reg [9:0]  active_side;
    reg [31:0] active_tag;
    reg [31:0] active_source_frame_id;

    reg [5:0]  dst_x;
    reg [5:0]  dst_y;
    reg [14:0] x_accumulator;
    reg [14:0] y_accumulator;
    reg [9:0]  target_x;
    reg [9:0]  target_y;
    reg [31:0] pack_data;
    reg [31:0] next_source_frame_id;

    wire pending_geometry_valid =
        (pending_side >= 10'd32) &&
        (pending_x0 < SOURCE_WIDTH) &&
        (pending_y0 < SOURCE_HEIGHT) &&
        ({1'b0, pending_x0} + {1'b0, pending_side} <= SOURCE_WIDTH) &&
        ({1'b0, pending_y0} + {1'b0, pending_side} <= SOURCE_HEIGHT);

    wire launch_now = pixel_fire && pixel_sof && desc_armed &&
                      pending_geometry_valid;
    wire sample_launch = launch_now &&
                         (pixel_x == pending_x0) && (pixel_y == pending_y0);
    wire sample_active = pixel_fire && !pixel_sof && active &&
                         (pixel_x == target_x) && (pixel_y == target_y);
    wire sample_now = sample_launch || sample_active;

    wire [5:0]  sample_dst_x = sample_launch ? 6'd0 : dst_x;
    wire [5:0]  sample_dst_y = sample_launch ? 6'd0 : dst_y;
    wire [9:0]  sample_x0 = sample_launch ? pending_x0 : active_x0;
    wire [9:0]  sample_y0 = sample_launch ? pending_y0 : active_y0;
    wire [9:0]  sample_side = sample_launch ? pending_side : active_side;
    wire [31:0] sample_tag = sample_launch ? pending_tag : active_tag;
    wire [31:0] sample_source_frame_id = sample_launch ?
        next_source_frame_id : active_source_frame_id;
    wire [14:0] sample_x_accumulator = sample_launch ? 15'd0 : x_accumulator;
    wire [14:0] sample_y_accumulator = sample_launch ? 15'd0 : y_accumulator;
    wire [15:0] next_x_accumulator =
        {1'b0, sample_x_accumulator} + {6'd0, sample_side};
    wire [15:0] next_y_accumulator =
        {1'b0, sample_y_accumulator} + {6'd0, sample_side};
    wire [10:0] next_target_x =
        {1'b0, sample_x0} + {6'd0, next_x_accumulator[15:5]};
    wire [10:0] next_target_y =
        {1'b0, sample_y0} + {6'd0, next_y_accumulator[15:5]};

    assign roi_busy = active;

    always @(posedge clk) begin
        if (!rst_n) begin
            pending_x0                <= 10'd0;
            pending_y0                <= 10'd0;
            pending_side              <= 10'd32;
            pending_tag               <= 32'd0;
            desc_armed                <= 1'b0;
            active                    <= 1'b0;
            active_x0                 <= 10'd0;
            active_y0                 <= 10'd0;
            active_side               <= 10'd32;
            active_tag                <= 32'd0;
            active_source_frame_id    <= 32'd0;
            dst_x                     <= 6'd0;
            dst_y                     <= 6'd0;
            x_accumulator             <= 15'd0;
            y_accumulator             <= 15'd0;
            target_x                  <= 10'd0;
            target_y                  <= 10'd0;
            pack_data                 <= 32'd0;
            next_source_frame_id      <= 32'd0;
            completed_tag             <= 32'd0;
            completed_source_frame_id <= 32'd0;
            roi_done_pulse            <= 1'b0;
            roi_error_pulse           <= 1'b0;
            roi_word_we               <= 1'b0;
            roi_word_addr             <= 8'd0;
            roi_word_data             <= 32'd0;
        end else begin
            roi_done_pulse  <= 1'b0;
            roi_error_pulse <= 1'b0;
            roi_word_we     <= 1'b0;

            if (desc_arm) begin
                if (desc_armed || active) begin
                    roi_error_pulse <= 1'b1;
                end else begin
                    pending_x0   <= desc_x0;
                    pending_y0   <= desc_y0;
                    pending_side <= desc_side;
                    pending_tag  <= desc_tag;
                    desc_armed   <= 1'b1;
                end
            end

            if (pixel_fire && pixel_sof) begin
                next_source_frame_id <= next_source_frame_id + 32'd1;

                if (active) begin
                    // A new frame before pixel 1023 means the token geometry or
                    // descriptor did not match the declared source frame.
                    active          <= 1'b0;
                    roi_error_pulse <= 1'b1;
                end

                if (desc_armed) begin
                    desc_armed <= 1'b0;
                    if (!pending_geometry_valid) begin
                        active          <= 1'b0;
                        roi_error_pulse <= 1'b1;
                    end else begin
                        active                 <= 1'b1;
                        active_x0              <= pending_x0;
                        active_y0              <= pending_y0;
                        active_side            <= pending_side;
                        active_tag             <= pending_tag;
                        active_source_frame_id <= next_source_frame_id;
                        dst_x                  <= 6'd0;
                        dst_y                  <= 6'd0;
                        x_accumulator          <= 15'd0;
                        y_accumulator          <= 15'd0;
                        target_x               <= pending_x0;
                        target_y               <= pending_y0;
                        pack_data              <= 32'd0;
                    end
                end
            end

            if (sample_now) begin
                case (sample_dst_x[1:0])
                    2'd0: pack_data[7:0]   <= pixel_data;
                    2'd1: pack_data[15:8]  <= pixel_data;
                    2'd2: pack_data[23:16] <= pixel_data;
                    default: pack_data[31:24] <= pixel_data;
                endcase

                if (sample_dst_x[1:0] == 2'd3) begin
                    roi_word_we   <= 1'b1;
                    roi_word_addr <= {sample_dst_y[4:0], sample_dst_x[4:2]};
                    roi_word_data <= {pixel_data, pack_data[23:0]};
                end

                if ((sample_dst_x == 6'd31) && (sample_dst_y == 6'd31)) begin
                    active                    <= 1'b0;
                    completed_tag             <= sample_tag;
                    completed_source_frame_id <= sample_source_frame_id;
                    roi_done_pulse            <= 1'b1;
                end else if (sample_dst_x == 6'd31) begin
                    dst_x         <= 6'd0;
                    dst_y         <= sample_dst_y + 6'd1;
                    x_accumulator <= 15'd0;
                    y_accumulator <= next_y_accumulator[14:0];
                    target_x      <= sample_x0;
                    target_y      <= next_target_y[9:0];
                end else begin
                    dst_x         <= sample_dst_x + 6'd1;
                    x_accumulator <= next_x_accumulator[14:0];
                    target_x      <= next_target_x[9:0];
                end
            end
        end
    end

endmodule
