// ============================================================================
// Timing-clean Locator-v16 Top-1 decode, bbox EMA and 18%-per-side expansion.
// Coordinates use Q16.16 pixels. EMA /10 is exact, iterative and round-to-even.
// The clamped candidate box is registered before geometry/EMA control so that
// coordinate arithmetic cannot feed state/write enables in the same 100-MHz
// cycle.
// ============================================================================
`timescale 1ns / 1ps

module locator_bbox_roi_fixed_v4 #(
    parameter signed [31:0] CONFIDENCE_THRESHOLD = -32'sd3383,
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
    output reg  [9:0]         roi_side,
    output reg  [8:0]         raw_box_x0,
    output reg  [8:0]         raw_box_y0,
    output reg  [8:0]         raw_box_x1,
    output reg  [8:0]         raw_box_y1,
    output reg  [8:0]         ema_box_x0,
    output reg  [8:0]         ema_box_y0,
    output reg  [8:0]         ema_box_x1,
    output reg  [8:0]         ema_box_y1
);

    localparam [3:0] ST_IDLE       = 4'd0;
    localparam [3:0] ST_MUL        = 4'd1;
    localparam [3:0] ST_FORM       = 4'd2;
    localparam [3:0] ST_CLAMP      = 4'd3;
    localparam [3:0] ST_GEOMETRY   = 4'd4;
    localparam [3:0] ST_EMA_PREP   = 4'd5;
    localparam [3:0] ST_EMA_LOAD   = 4'd6;
    localparam [3:0] ST_EMA_DIV    = 4'd7;
    localparam [3:0] ST_EMA_ROUND  = 4'd8;
    localparam [3:0] ST_DIMENSIONS = 4'd9;
    localparam [3:0] ST_MAX_SIDE   = 4'd10;
    localparam [3:0] ST_EXPAND     = 4'd11;
    localparam [3:0] ST_SIDE       = 4'd12;
    localparam [3:0] ST_ORIGIN     = 4'd13;
    localparam [3:0] ST_OUTPUT     = 4'd14;

    localparam signed [63:0] LOCATOR_MAX_Q16 = 64'sd8388608;

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

    reg [1:0]  ema_coordinate;
    reg [27:0] ema_weighted_sum;
    reg [27:0] div_dividend;
    reg [27:0] div_quotient;
    reg [3:0]  div_remainder;
    reg [4:0]  div_bit;

    reg [31:0] ema_width_stage;
    reg [31:0] ema_height_stage;
    reg [31:0] ema_max_side_stage;
    reg [63:0] expand_product_q32;
    reg [7:0]  side_pixels;
    reg signed [63:0] output_center_x_q16;
    reg signed [63:0] output_center_y_q16;
    reg signed [63:0] output_left;
    reg signed [63:0] output_top;

    wire signed [63:0] raw_x0_q16 = center_x_q16 - half_width_q16;
    wire signed [63:0] raw_y0_q16 = center_y_q16 - half_height_q16;
    wire signed [63:0] raw_x1_q16 = center_x_q16 + half_width_q16;
    wire signed [63:0] raw_y1_q16 = center_y_q16 + half_height_q16;
    wire [31:0] clamp_x0_q16 = clamp_locator_q16(raw_x0_q16);
    wire [31:0] clamp_y0_q16 = clamp_locator_q16(raw_y0_q16);
    wire [31:0] clamp_x1_q16 = clamp_locator_q16(raw_x1_q16);
    wire [31:0] clamp_y1_q16 = clamp_locator_q16(raw_y1_q16);
    wire geometry_valid = (new_x1_q16 > new_x0_q16) &&
                          (new_y1_q16 > new_y0_q16);

    wire [31:0] ema_selected_new =
        (ema_coordinate == 2'd0) ? new_x0_q16 :
        (ema_coordinate == 2'd1) ? new_y0_q16 :
        (ema_coordinate == 2'd2) ? new_x1_q16 : new_y1_q16;
    wire [31:0] ema_selected_old =
        (ema_coordinate == 2'd0) ? ema_x0_q16 :
        (ema_coordinate == 2'd1) ? ema_y0_q16 :
        (ema_coordinate == 2'd2) ? ema_x1_q16 : ema_y1_q16;
    wire [35:0] ema_weighted_wide =
        (ema_selected_new * 4'd3) + (ema_selected_old * 4'd7);
    wire [4:0] div_trial = {div_remainder, div_dividend[div_bit]};
    wire ema_round_up = (div_remainder > 4'd5) ||
                        ((div_remainder == 4'd5) && div_quotient[0]);
    wire [27:0] ema_rounded_quotient =
        div_quotient + (ema_round_up ? 28'd1 : 28'd0);

    wire [63:0] rounded_side_wide = round_shift32_unsigned(expand_product_q32);
    wire [7:0] rounded_side_clamped =
        (rounded_side_wide < 64'd1) ? 8'd1 :
        (rounded_side_wide > 64'd128) ? 8'd128 : rounded_side_wide[7:0];
    wire [7:0] max_origin = 8'd128 - side_pixels;
    wire [7:0] clamped_left =
        (output_left < 0) ? 8'd0 :
        (output_left > $signed({1'b0, max_origin})) ? max_origin : output_left[7:0];
    wire [7:0] clamped_top =
        (output_top < 0) ? 8'd0 :
        (output_top > $signed({1'b0, max_origin})) ? max_origin : output_top[7:0];

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
            round_shift14_signed = (value < 0) ? -$signed(quotient) : $signed(quotient);
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
            round_q16_signed = (value < 0) ? -$signed(quotient) : $signed(quotient);
        end
    endfunction

    always @(posedge clk) begin
        if (!rst_n) begin
            state <= ST_IDLE;
            cell_x <= 0; cell_y <= 0;
            raw_dx <= 0; raw_dy <= 0; raw_width <= 0; raw_height <= 0;
            dx_product <= 0; dy_product <= 0;
            width_product <= 0; height_product <= 0;
            center_x_q16 <= 0; center_y_q16 <= 0;
            half_width_q16 <= 0; half_height_q16 <= 0;
            new_x0_q16 <= 0; new_y0_q16 <= 0; new_x1_q16 <= 0; new_y1_q16 <= 0;
            ema_x0_q16 <= 0; ema_y0_q16 <= 0; ema_x1_q16 <= 0; ema_y1_q16 <= 0;
            ema_valid <= 1'b0; miss_count <= 0;
            ema_coordinate <= 0; ema_weighted_sum <= 0;
            div_dividend <= 0; div_quotient <= 0; div_remainder <= 0; div_bit <= 0;
            ema_width_stage <= 0; ema_height_stage <= 0; ema_max_side_stage <= 0;
            expand_product_q32 <= 0; side_pixels <= 1;
            output_center_x_q16 <= 0; output_center_y_q16 <= 0;
            output_left <= 0; output_top <= 0;
            done <= 1'b0; detected <= 1'b0;
            roi_x0 <= 0; roi_y0 <= 0; roi_side <= 0;
            raw_box_x0 <= 0; raw_box_y0 <= 0;
            raw_box_x1 <= 0; raw_box_y1 <= 0;
            ema_box_x0 <= 0; ema_box_y0 <= 0;
            ema_box_x1 <= 0; ema_box_y1 <= 0;
        end else begin
            done <= 1'b0;
            case (state)
                ST_IDLE: begin
                    if (start) begin
                        detected <= 1'b0;
                        if ((confidence_i32 < CONFIDENCE_THRESHOLD) ||
                            (width_i32 <= 0) || (height_i32 <= 0)) begin
                            if (miss_count >= 3'd3) begin
                                ema_valid <= 1'b0;
                                miss_count <= 3'd4;
                            end else begin
                                miss_count <= miss_count + 3'd1;
                            end
                            done <= 1'b1;
                        end else begin
                            cell_x <= cell_index[3:0]; cell_y <= cell_index[7:4];
                            raw_dx <= dx_i32; raw_dy <= dy_i32;
                            raw_width <= width_i32; raw_height <= height_i32;
                            state <= ST_MUL;
                        end
                    end
                end
                ST_MUL: begin
                    dx_product <= raw_dx * DX_PIXELS_Q30;
                    dy_product <= raw_dy * DY_PIXELS_Q30;
                    width_product <= raw_width * HALF_WIDTH_Q30;
                    height_product <= raw_height * HALF_HEIGHT_Q30;
                    state <= ST_FORM;
                end
                ST_FORM: begin
                    center_x_q16 <= $signed({60'd0, cell_x}) * 64'sd524288 +
                                    64'sd262144 + round_shift14_signed(dx_product);
                    center_y_q16 <= $signed({60'd0, cell_y}) * 64'sd524288 +
                                    64'sd262144 + round_shift14_signed(dy_product);
                    half_width_q16 <= round_shift14_signed(width_product);
                    half_height_q16 <= round_shift14_signed(height_product);
                    state <= ST_CLAMP;
                end
                ST_CLAMP: begin
                    new_x0_q16 <= clamp_x0_q16; new_y0_q16 <= clamp_y0_q16;
                    new_x1_q16 <= clamp_x1_q16; new_y1_q16 <= clamp_y1_q16;
                    state <= ST_GEOMETRY;
                end
                ST_GEOMETRY: begin
                    if (!geometry_valid) begin
                        if (miss_count >= 3'd3) begin
                            ema_valid <= 1'b0; miss_count <= 3'd4;
                        end else begin
                            miss_count <= miss_count + 3'd1;
                        end
                        detected <= 1'b0; done <= 1'b1; state <= ST_IDLE;
                    end else if (!ema_valid) begin
                        ema_x0_q16 <= new_x0_q16; ema_y0_q16 <= new_y0_q16;
                        ema_x1_q16 <= new_x1_q16; ema_y1_q16 <= new_y1_q16;
                        ema_valid <= 1'b1; miss_count <= 0; state <= ST_DIMENSIONS;
                    end else begin
                        miss_count <= 0; ema_coordinate <= 0; state <= ST_EMA_PREP;
                    end
                end
                ST_EMA_PREP: begin
                    ema_weighted_sum <= ema_weighted_wide[27:0];
                    state <= ST_EMA_LOAD;
                end
                ST_EMA_LOAD: begin
                    div_dividend <= ema_weighted_sum;
                    div_quotient <= 0;
                    div_remainder <= 0;
                    div_bit <= 5'd27;
                    state <= ST_EMA_DIV;
                end
                ST_EMA_DIV: begin
                    if (div_trial >= 5'd10) begin
                        div_remainder <= div_trial - 5'd10;
                        div_quotient[div_bit] <= 1'b1;
                    end else begin
                        div_remainder <= div_trial[3:0];
                    end
                    if (div_bit == 0)
                        state <= ST_EMA_ROUND;
                    else
                        div_bit <= div_bit - 1'b1;
                end
                ST_EMA_ROUND: begin
                    case (ema_coordinate)
                        2'd0: ema_x0_q16 <= {4'd0, ema_rounded_quotient};
                        2'd1: ema_y0_q16 <= {4'd0, ema_rounded_quotient};
                        2'd2: ema_x1_q16 <= {4'd0, ema_rounded_quotient};
                        default: ema_y1_q16 <= {4'd0, ema_rounded_quotient};
                    endcase
                    if (ema_coordinate == 2'd3) begin
                        state <= ST_DIMENSIONS;
                    end else begin
                        ema_coordinate <= ema_coordinate + 1'b1;
                        state <= ST_EMA_PREP;
                    end
                end
                ST_DIMENSIONS: begin
                    ema_width_stage <= ema_x1_q16 - ema_x0_q16;
                    ema_height_stage <= ema_y1_q16 - ema_y0_q16;
                    state <= ST_MAX_SIDE;
                end
                ST_MAX_SIDE: begin
                    ema_max_side_stage <= (ema_width_stage >= ema_height_stage) ?
                        ema_width_stage : ema_height_stage;
                    state <= ST_EXPAND;
                end
                ST_EXPAND: begin
                    expand_product_q32 <= ema_max_side_stage * EXPAND_136_Q16;
                    state <= ST_SIDE;
                end
                ST_SIDE: begin
                    side_pixels <= rounded_side_clamped;
                    output_center_x_q16 <= $signed({1'b0, ema_x0_q16}) +
                        (($signed({1'b0, ema_x1_q16}) - $signed({1'b0, ema_x0_q16})) >>> 1);
                    output_center_y_q16 <= $signed({1'b0, ema_y0_q16}) +
                        (($signed({1'b0, ema_y1_q16}) - $signed({1'b0, ema_y0_q16})) >>> 1);
                    state <= ST_ORIGIN;
                end
                ST_ORIGIN: begin
                    output_left <= round_q16_signed(output_center_x_q16 -
                        $signed({1'b0, side_pixels, 15'd0}));
                    output_top <= round_q16_signed(output_center_y_q16 -
                        $signed({1'b0, side_pixels, 15'd0}));
                    state <= ST_OUTPUT;
                end
                ST_OUTPUT: begin
                    roi_x0 <= {2'd0, clamped_left};
                    roi_y0 <= {2'd0, clamped_top};
                    roi_side <= {2'd0, side_pixels};
                    raw_box_x0 <= new_x0_q16[24:16];
                    raw_box_y0 <= new_y0_q16[24:16];
                    raw_box_x1 <= new_x1_q16[24:16];
                    raw_box_y1 <= new_y1_q16[24:16];
                    ema_box_x0 <= ema_x0_q16[24:16];
                    ema_box_y0 <= ema_y0_q16[24:16];
                    ema_box_x1 <= ema_x1_q16[24:16];
                    ema_box_y1 <= ema_y1_q16[24:16];
                    detected <= 1'b1; done <= 1'b1; state <= ST_IDLE;
                end
                default: state <= ST_IDLE;
            endcase
        end
    end
endmodule
