// ============================================================================
// Same-frame 128x128 camera-buffer ROI extractor.
//
// The selected camera ping/pong buffer remains owned by PS after Locator
// completes. This engine reuses its idle BRAM read port and writes a 32x32
// Gray8 nearest-neighbour crop into the existing classifier ROI BRAM.
// Mapping: source_index = floor(destination_index * side / 32).
// ============================================================================
`timescale 1ns / 1ps

module same_frame_roi_128x128 (
    input  wire        clk,
    input  wire        rst_n,

    input  wire        start,
    input  wire        buffer_id,
    input  wire [9:0]  desc_x0,
    input  wire [9:0]  desc_y0,
    input  wire [9:0]  desc_side,
    input  wire [31:0] desc_tag,
    input  wire [1:0]  buffer_valid_mask,
    input  wire [31:0] buffer_frame_id_0,
    input  wire [31:0] buffer_frame_id_1,

    input  wire        read_grant,
    output wire        camera_read_en,
    output wire [12:0] camera_read_word_addr,
    input  wire [31:0] camera_read_data,

    output wire        busy,
    output reg         done_pulse,
    output reg         error_pulse,
    output reg  [31:0] completed_tag,
    output reg  [31:0] completed_source_frame_id,

    output reg         roi_word_we,
    output reg  [7:0]  roi_word_addr,
    output reg  [31:0] roi_word_data
);

    localparam [1:0] ST_IDLE    = 2'd0;
    localparam [1:0] ST_ISSUE   = 2'd1;
    localparam [1:0] ST_CAPTURE = 2'd2;

    reg [1:0] state;
    reg       active_buffer_id;
    reg [6:0] active_x0;
    reg [6:0] active_y0;
    reg [7:0] active_side;
    reg [31:0] active_tag;
    reg [5:0] dst_x;
    reg [5:0] dst_y;
    reg [12:0] x_accumulator;
    reg [12:0] y_accumulator;
    reg [31:0] pack_data;

    wire geometry_valid =
        (desc_x0[9:7] == 3'd0) &&
        (desc_y0[9:7] == 3'd0) &&
        (desc_side >= 10'd1) &&
        (desc_side <= 10'd128) &&
        ({1'b0, desc_x0} + {1'b0, desc_side} <= 11'd128) &&
        ({1'b0, desc_y0} + {1'b0, desc_side} <= 11'd128);

    wire [7:0] source_x_full =
        {1'b0, active_x0} + {3'd0, x_accumulator[12:5]};
    wire [7:0] source_y_full =
        {1'b0, active_y0} + {3'd0, y_accumulator[12:5]};
    wire [7:0] source_pixel =
        (source_x_full[1:0] == 2'd0) ? camera_read_data[7:0] :
        (source_x_full[1:0] == 2'd1) ? camera_read_data[15:8] :
        (source_x_full[1:0] == 2'd2) ? camera_read_data[23:16] :
                                               camera_read_data[31:24];

    assign busy = state != ST_IDLE;
    assign camera_read_en = (state == ST_ISSUE) && read_grant;
    assign camera_read_word_addr = {
        active_buffer_id, source_y_full[6:0], source_x_full[6:2]
    };

    always @(posedge clk) begin
        if (!rst_n) begin
            state                     <= ST_IDLE;
            active_buffer_id          <= 1'b0;
            active_x0                 <= 7'd0;
            active_y0                 <= 7'd0;
            active_side               <= 8'd1;
            active_tag                <= 32'd0;
            dst_x                     <= 6'd0;
            dst_y                     <= 6'd0;
            x_accumulator             <= 13'd0;
            y_accumulator             <= 13'd0;
            pack_data                 <= 32'd0;
            done_pulse                <= 1'b0;
            error_pulse               <= 1'b0;
            completed_tag             <= 32'd0;
            completed_source_frame_id <= 32'd0;
            roi_word_we               <= 1'b0;
            roi_word_addr             <= 8'd0;
            roi_word_data             <= 32'd0;
        end else begin
            done_pulse  <= 1'b0;
            error_pulse <= 1'b0;
            roi_word_we <= 1'b0;

            if (start && state != ST_IDLE)
                error_pulse <= 1'b1;

            case (state)
                ST_IDLE: begin
                    if (start) begin
                        if (!geometry_valid || !buffer_valid_mask[buffer_id]) begin
                            error_pulse <= 1'b1;
                        end else begin
                            active_buffer_id <= buffer_id;
                            active_x0        <= desc_x0[6:0];
                            active_y0        <= desc_y0[6:0];
                            active_side      <= desc_side[7:0];
                            active_tag       <= desc_tag;
                            completed_source_frame_id <= buffer_id ?
                                buffer_frame_id_1 : buffer_frame_id_0;
                            dst_x         <= 6'd0;
                            dst_y         <= 6'd0;
                            x_accumulator <= 13'd0;
                            y_accumulator <= 13'd0;
                            pack_data     <= 32'd0;
                            state         <= ST_ISSUE;
                        end
                    end
                end

                ST_ISSUE: begin
                    if (read_grant)
                        state <= ST_CAPTURE;
                end

                ST_CAPTURE: begin
                    case (dst_x[1:0])
                        2'd0: pack_data[7:0]   <= source_pixel;
                        2'd1: pack_data[15:8]  <= source_pixel;
                        2'd2: pack_data[23:16] <= source_pixel;
                        default: pack_data[31:24] <= source_pixel;
                    endcase

                    if (dst_x[1:0] == 2'd3) begin
                        roi_word_we   <= 1'b1;
                        roi_word_addr <= {dst_y[4:0], dst_x[4:2]};
                        roi_word_data <= {source_pixel, pack_data[23:0]};
                    end

                    if ((dst_x == 6'd31) && (dst_y == 6'd31)) begin
                        completed_tag <= active_tag;
                        done_pulse    <= 1'b1;
                        state         <= ST_IDLE;
                    end else if (dst_x == 6'd31) begin
                        dst_x         <= 6'd0;
                        dst_y         <= dst_y + 6'd1;
                        x_accumulator <= 13'd0;
                        y_accumulator <= y_accumulator + {5'd0, active_side};
                        state         <= ST_ISSUE;
                    end else begin
                        dst_x         <= dst_x + 6'd1;
                        x_accumulator <= x_accumulator + {5'd0, active_side};
                        state         <= ST_ISSUE;
                    end
                end

                default: state <= ST_IDLE;
            endcase
        end
    end
endmodule
