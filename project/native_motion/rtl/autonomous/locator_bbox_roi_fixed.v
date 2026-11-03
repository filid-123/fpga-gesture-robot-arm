// ============================================================================
// Frozen Locator-v16 Top-1 decode, bbox EMA and 18%-per-side square expansion.
//
// Coordinates are Q16.16 pixels in the 128x128 Locator image.  The four
// manifest scales are represented by Q2.30 coefficients, then rounded to
// Q16.16.  The resulting integer ROI matches the frozen PS contract on the
// supplied v16 golden vectors while avoiding floating-point hardware.
// ============================================================================
`timescale 1ns / 1ps

module locator_bbox_roi_fixed #(
    parameter signed [31:0] CONFIDENCE_THRESHOLD = -32'sd1901,
    parameter signed [31:0] DX_PIXELS_Q30         = 32'sd263558,
    parameter signed [31:0] DY_PIXELS_Q30         = 32'sd200659,
    parameter signed [31:0] HALF_WIDTH_Q30        = 32'sd801653,
    parameter signed [31:0] HALF_HEIGHT_Q30       = 32'sd1052752,
    parameter        [31:0] EXPAND_136_Q16        = 32'd89129
)(
    input  wire               clk,
    input  wire               rst_n,
    input  wire               start,
    input  wire [7:0]         cell_index,
    input  wire signed [31:0] confidence_i32,
    input  wire signed [31:0] dx_i32,
    input  wire signed [31:0] dy_i32,
    input  wire signed [31:0] width_i32,
    input  wire signed [31:0] height_i32,

    output wire               busy,
    output reg                done,
    output reg                detected,
    output reg  [9:0]         roi_x0,
    output reg  [9:0]         roi_y0,
    output reg  [9:0]         roi_side
);

    localparam [3:0] ST_IDLE   = 4'd0;
    localparam [3:0] ST_MUL    = 4'd1;
    localparam [3:0] ST_FORM   = 4'd2;
    localparam [3:0] ST_CLAMP  = 4'd3;
    localparam [3:0] ST_EMA0   = 4'd4;
    localparam [3:0] ST_EMA1   = 4'd5;
    localparam [3:0] ST_EMA2   = 4'd6;
    localparam [3:0] ST_EMA3   = 4'd7;
    localparam [3:0] ST_EXPAND = 4'd8;
    localparam [3:0] ST_OUTPUT = 4'd9;

    localparam signed [63:0] LOCATOR_MAX_Q16 = 64'sd8388608; // 128 << 16

    reg [3:0] state;
    reg [3:0] cell_x;
    reg [3:0] cell_y;
    reg signed [31:0] raw_dx;
    reg signed [31:0] raw_dy;
    reg signed [31:0] raw_width;
    reg signed [31:0] raw_height;

    reg signed [63:0] dx_product;
    reg signed [63:0] dy_product;
    reg signed [63:0] width_product;
    reg signed [63:0] height_product;
    reg signed [63:0] center_x_q16;
    reg signed [63:0] center_y_q16;
    reg signed [63:0] half_width_q16;
    reg signed [63:0] half_height_q16;

    reg [31:0] new_x0_q16;
    reg [31:0] new_y0_q16;
    reg [31:0] new_x1_q16;
    reg [31:0] new_y1_q16;
    reg [31:0] ema_x0_q16;
    reg [31:0] ema_y0_q16;
    reg [31:0] ema_x1_q16;
    reg [31:0] ema_y1_q16;
    reg        ema_valid;
    reg [2:0]  miss_count;
    reg [63:0] expand_product_q32;

    wire signed [63:0] raw_x0_q16 = center_x_q16 - half_width_q16;
    wire signed [63:0] raw_y0_q16 = center_y_q16 - half_height_q16;
    wire signed [63:0] raw_x1_q16 = center_x_q16 + half_width_q16;
    wire signed [63:0] raw_y1_q16 = center_y_q16 + half_height_q16;

    wire [31:0] clamp_x0_q16 = clamp_locator_q16(raw_x0_q16);
    wire [31:0] clamp_y0_q16 = clamp_locator_q16(raw_y0_q16);
    wire [31:0] clamp_x1_q16 = clamp_locator_q16(raw_x1_q16);
    wire [31:0] clamp_y1_q16 = clamp_locator_q16(raw_y1_q16);
    wire geometry_valid = (clamp_x1_q16 > clamp_x0_q16) &&
                          (clamp_y1_q16 > clamp_y0_q16);

    wire [31:0] ema_width_q16  = ema_x1_q16 - ema_x0_q16;
    wire [31:0] ema_height_q16 = ema_y1_q16 - ema_y0_q16;
    wire [31:0] ema_max_side_q16 =
        (ema_width_q16 >= ema_height_q16) ? ema_width_q16 : ema_height_q16;

    wire [63:0] rounded_side_wide = round_shift32_unsigned(expand_product_q32);
    wire [7:0] rounded_side =
        (rounded_side_wide < 64'd1)   ? 8'd1 :
        (rounded_side_wide > 64'd128) ? 8'd128 : rounded_side_wide[7:0];
    wire signed [63:0] ema_center_x_q16 =
        $signed({1'b0, ema_x0_q16}) +
        (($signed({1'b0, ema_x1_q16}) - $signed({1'b0, ema_x0_q16})) >>> 1);
    wire signed [63:0] ema_center_y_q16 =
        $signed({1'b0, ema_y0_q16}) +
        (($signed({1'b0, ema_y1_q16}) - $signed({1'b0, ema_y0_q16})) >>> 1);
    wire signed [63:0] left_unclamped = round_q16_signed(
        ema_center_x_q16 - $signed({55'd0, rounded_side, 15'd0}));
    wire signed [63:0] top_unclamped = round_q16_signed(
        ema_center_y_q16 - $signed({55'd0, rounded_side, 15'd0}));
    wire [7:0] max_origin = 8'd128 - rounded_side;
    wire [7:0] clamped_left =
        (left_unclamped < 0) ? 8'd0 :
        (left_unclamped > $signed({56'd0, max_origin})) ? max_origin :
        left_unclamped[7:0];
    wire [7:0] clamped_top =
        (top_unclamped < 0) ? 8'd0 :
        (top_unclamped > $signed({56'd0, max_origin})) ? max_origin :
        top_unclamped[7:0];

    assign busy = state != ST_IDLE;

    function signed [63:0] round_shift14_signed;
        input signed [63:0] value;
        reg [63:0] magnitude;
        reg [63:0] quotient;
        reg [13:0] remainder;
        begin
            magnitude = (value < 0) ? -value : value;
            quotient = magnitude >> 14;
            remainder = magnitude[13:0];
            if ((remainder > 14'h2000) ||
                ((remainder == 14'h2000) && quotient[0]))
                quotient = quotient + 64'd1;
            round_shift14_signed = (value < 0) ? -$signed(quotient) :
                                                   $signed(quotient);
        end
    endfunction

    function [31:0] clamp_locator_q16;
        input signed [63:0] value;
        begin
            if (value < 0)
                clamp_locator_q16 = 32'd0;
            else if (value > LOCATOR_MAX_Q16)
                clamp_locator_q16 = LOCATOR_MAX_Q16[31:0];
            else
                clamp_locator_q16 = value[31:0];
        end
    endfunction

    function [31:0] ema_div10_round_even;
        input [35:0] value;
        reg [35:0] quotient;
        reg [3:0] remainder;
        begin
            quotient = value / 10;
            remainder = value % 10;
            if ((remainder > 4'd5) ||
                ((remainder == 4'd5) && quotient[0]))
                quotient = quotient + 36'd1;
            ema_div10_round_even = quotient[31:0];
        end
    endfunction

    function [63:0] round_shift32_unsigned;
        input [63:0] value;
        reg [63:0] quotient;
        reg [31:0] remainder;
        begin
            quotient = value >> 32;
            remainder = value[31:0];
            if ((remainder > 32'h8000_0000) ||
                ((remainder == 32'h8000_0000) && quotient[0]))
                quotient = quotient + 64'd1;
            round_shift32_unsigned = quotient;
        end
    endfunction

    function signed [63:0] round_q16_signed;
        input signed [63:0] value;
        reg [63:0] magnitude;
        reg [63:0] quotient;
        reg [15:0] remainder;
        begin
            magnitude = (value < 0) ? -value : value;
            quotient = magnitude >> 16;
            remainder = magnitude[15:0];
            if ((remainder > 16'h8000) ||
                ((remainder == 16'h8000) && quotient[0]))
                quotient = quotient + 64'd1;
            round_q16_signed = (value < 0) ? -$signed(quotient) :
                                               $signed(quotient);
        end
    endfunction

    always @(posedge clk) begin
        if (!rst_n) begin
            state              <= ST_IDLE;
            cell_x             <= 4'd0;
            cell_y             <= 4'd0;
            raw_dx             <= 32'sd0;
            raw_dy             <= 32'sd0;
            raw_width          <= 32'sd0;
            raw_height         <= 32'sd0;
            dx_product         <= 64'sd0;
            dy_product         <= 64'sd0;
            width_product      <= 64'sd0;
            height_product     <= 64'sd0;
            center_x_q16       <= 64'sd0;
            center_y_q16       <= 64'sd0;
            half_width_q16     <= 64'sd0;
            half_height_q16    <= 64'sd0;
            new_x0_q16         <= 32'd0;
            new_y0_q16         <= 32'd0;
            new_x1_q16         <= 32'd0;
            new_y1_q16         <= 32'd0;
            ema_x0_q16         <= 32'd0;
            ema_y0_q16         <= 32'd0;
            ema_x1_q16         <= 32'd0;
            ema_y1_q16         <= 32'd0;
            ema_valid          <= 1'b0;
            miss_count         <= 3'd0;
            expand_product_q32 <= 64'd0;
            done               <= 1'b0;
            detected           <= 1'b0;
            roi_x0             <= 10'd0;
            roi_y0             <= 10'd0;
            roi_side           <= 10'd0;
        end else begin
            done <= 1'b0;

            case (state)
                ST_IDLE: begin
                    if (start) begin
                        detected <= 1'b0;
                        if ((confidence_i32 < CONFIDENCE_THRESHOLD) ||
                            (width_i32 <= 0) || (height_i32 <= 0)) begin
                            if (miss_count >= 3'd3) begin
                                ema_valid  <= 1'b0;
                                miss_count <= 3'd4;
                            end else begin
                                miss_count <= miss_count + 3'd1;
                            end
                            done <= 1'b1;
                        end else begin
                            cell_x     <= cell_index[3:0];
                            cell_y     <= cell_index[7:4];
                            raw_dx     <= dx_i32;
                            raw_dy     <= dy_i32;
                            raw_width  <= width_i32;
                            raw_height <= height_i32;
                            state      <= ST_MUL;
                        end
                    end
                end

                ST_MUL: begin
                    dx_product     <= raw_dx * DX_PIXELS_Q30;
                    dy_product     <= raw_dy * DY_PIXELS_Q30;
                    width_product  <= raw_width * HALF_WIDTH_Q30;
                    height_product <= raw_height * HALF_HEIGHT_Q30;
                    state          <= ST_FORM;
                end

                ST_FORM: begin
                    center_x_q16 <= $signed({56'd0, cell_x}) * 64'sd524288 +
                                    64'sd262144 + round_shift14_signed(dx_product);
                    center_y_q16 <= $signed({56'd0, cell_y}) * 64'sd524288 +
                                    64'sd262144 + round_shift14_signed(dy_product);
                    half_width_q16  <= round_shift14_signed(width_product);
                    half_height_q16 <= round_shift14_signed(height_product);
                    state <= ST_CLAMP;
                end

                ST_CLAMP: begin
                    new_x0_q16 <= clamp_x0_q16;
                    new_y0_q16 <= clamp_y0_q16;
                    new_x1_q16 <= clamp_x1_q16;
                    new_y1_q16 <= clamp_y1_q16;
                    if (!geometry_valid) begin
                        if (miss_count >= 3'd3) begin
                            ema_valid  <= 1'b0;
                            miss_count <= 3'd4;
                        end else begin
                            miss_count <= miss_count + 3'd1;
                        end
                        detected <= 1'b0;
                        done     <= 1'b1;
                        state    <= ST_IDLE;
                    end else if (!ema_valid) begin
                        ema_x0_q16 <= clamp_x0_q16;
                        ema_y0_q16 <= clamp_y0_q16;
                        ema_x1_q16 <= clamp_x1_q16;
                        ema_y1_q16 <= clamp_y1_q16;
                        ema_valid  <= 1'b1;
                        miss_count <= 3'd0;
                        state      <= ST_EXPAND;
                    end else begin
                        miss_count <= 3'd0;
                        state <= ST_EMA0;
                    end
                end

                ST_EMA0: begin
                    ema_x0_q16 <= ema_div10_round_even(
                        (new_x0_q16 * 36'd3) + (ema_x0_q16 * 36'd7));
                    state <= ST_EMA1;
                end

                ST_EMA1: begin
                    ema_y0_q16 <= ema_div10_round_even(
                        (new_y0_q16 * 36'd3) + (ema_y0_q16 * 36'd7));
                    state <= ST_EMA2;
                end

                ST_EMA2: begin
                    ema_x1_q16 <= ema_div10_round_even(
                        (new_x1_q16 * 36'd3) + (ema_x1_q16 * 36'd7));
                    state <= ST_EMA3;
                end

                ST_EMA3: begin
                    ema_y1_q16 <= ema_div10_round_even(
                        (new_y1_q16 * 36'd3) + (ema_y1_q16 * 36'd7));
                    state <= ST_EXPAND;
                end

                ST_EXPAND: begin
                    expand_product_q32 <= ema_max_side_q16 * EXPAND_136_Q16;
                    state <= ST_OUTPUT;
                end

                ST_OUTPUT: begin
                    roi_x0   <= {2'd0, clamped_left};
                    roi_y0   <= {2'd0, clamped_top};
                    roi_side <= {2'd0, rounded_side};
                    detected <= 1'b1;
                    done     <= 1'b1;
                    state    <= ST_IDLE;
                end

                default: state <= ST_IDLE;
            endcase
        end
    end

endmodule
