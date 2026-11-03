// ============================================================================
// Block Name : trajectory_smoothstep_q16_16
// Description: Six-channel, bit-exact Q16.16 cubic-smoothstep interpolator.
//              Development v1 intentionally supports 32 ticks per segment,
//              matching phase3_trajectory_q16_16_v1 golden vectors.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (planned 100 MHz system domain)
//
// Truth boundary:
// - This is an isolated trajectory leaf, not an AXI/UART/servo interface.
// - One output sample is produced every seven clocks; the physical sample period
//   is owned by a future tick-enable wrapper and is not frozen here.
// - start_while_busy and arithmetic_overflow are sticky until reset.
// ============================================================================

`timescale 1ns / 1ps

module trajectory_smoothstep_q16_16 (
    input  wire clk,
    input  wire rst_n,
    input  wire start,

    input  wire signed [31:0] start_ch0,
    input  wire signed [31:0] start_ch1,
    input  wire signed [31:0] start_ch2,
    input  wire signed [31:0] start_ch3,
    input  wire signed [31:0] start_ch4,
    input  wire signed [31:0] start_ch5,
    input  wire signed [31:0] target_ch0,
    input  wire signed [31:0] target_ch1,
    input  wire signed [31:0] target_ch2,
    input  wire signed [31:0] target_ch3,
    input  wire signed [31:0] target_ch4,
    input  wire signed [31:0] target_ch5,

    output reg  busy,
    output reg  sample_valid,
    output reg  [5:0] sample_index,
    output reg  signed [31:0] joint_ch0,
    output reg  signed [31:0] joint_ch1,
    output reg  signed [31:0] joint_ch2,
    output reg  signed [31:0] joint_ch3,
    output reg  signed [31:0] joint_ch4,
    output reg  signed [31:0] joint_ch5,
    output reg  done,
    output reg  error_start_while_busy,
    output reg  error_arithmetic_overflow
);

    localparam [2:0] ST_IDLE   = 3'd0;
    localparam [2:0] ST_PHASE  = 3'd1;
    localparam [2:0] ST_SQUARE = 3'd2;
    localparam [2:0] ST_CUBE   = 3'd3;
    localparam [2:0] ST_BLEND  = 3'd4;
    localparam [2:0] ST_APPLY  = 3'd5;
    localparam [2:0] ST_ROUND  = 3'd6;
    localparam [2:0] ST_OUTPUT = 3'd7;

    reg [2:0] state;
    reg [5:0] tick_count;

    reg signed [31:0] start_reg0, start_reg1, start_reg2;
    reg signed [31:0] start_reg3, start_reg4, start_reg5;
    reg signed [31:0] target_reg0, target_reg1, target_reg2;
    reg signed [31:0] target_reg3, target_reg4, target_reg5;

    // UQ0.16 with 1.0 represented by 17'd65536.
    reg [16:0] phase_q16;
    reg [16:0] phase_sq_q16;
    reg [16:0] phase_cube_q16;
    reg [16:0] blend_q16;

    // Signed delta (33 bits) times non-negative blend (18-bit signed wrapper).
    (* use_dsp = "yes" *) reg signed [50:0] scaled_product0;
    (* use_dsp = "yes" *) reg signed [50:0] scaled_product1;
    (* use_dsp = "yes" *) reg signed [50:0] scaled_product2;
    (* use_dsp = "yes" *) reg signed [50:0] scaled_product3;
    (* use_dsp = "yes" *) reg signed [50:0] scaled_product4;
    (* use_dsp = "yes" *) reg signed [50:0] scaled_product5;
    // Pipeline boundary between DSP multiplication and rounding/addition. This
    // keeps the standalone block timing-clean at the planned 100 MHz clock.
    reg signed [32:0] increment_reg0, increment_reg1, increment_reg2;
    reg signed [32:0] increment_reg3, increment_reg4, increment_reg5;


    wire [33:0] phase_square_full = phase_q16 * phase_q16;
    wire [33:0] phase_cube_full = phase_sq_q16 * phase_q16;
    wire [18:0] blend_full = (phase_sq_q16 * 3) - (phase_cube_q16 * 2);

    wire signed [32:0] delta0 =
        $signed({target_reg0[31], target_reg0}) -
        $signed({start_reg0[31], start_reg0});
    wire signed [32:0] delta1 =
        $signed({target_reg1[31], target_reg1}) -
        $signed({start_reg1[31], start_reg1});
    wire signed [32:0] delta2 =
        $signed({target_reg2[31], target_reg2}) -
        $signed({start_reg2[31], start_reg2});
    wire signed [32:0] delta3 =
        $signed({target_reg3[31], target_reg3}) -
        $signed({start_reg3[31], start_reg3});
    wire signed [32:0] delta4 =
        $signed({target_reg4[31], target_reg4}) -
        $signed({start_reg4[31], start_reg4});
    wire signed [32:0] delta5 =
        $signed({target_reg5[31], target_reg5}) -
        $signed({start_reg5[31], start_reg5});
    wire signed [17:0] blend_signed = $signed({1'b0, blend_q16});

    function [16:0] round_uq16;
        input [33:0] value;
        reg [34:0] biased;
        begin
            biased = {1'b0, value} + 35'd32768;
            round_uq16 = biased[32:16];
        end
    endfunction

    function signed [32:0] round_sq16;
        input signed [50:0] value;
        reg signed [51:0] magnitude;
        reg signed [51:0] rounded_magnitude;
        begin
            if (value >= 0) begin
                round_sq16 = ($signed({1'b0, value}) + 52'sd32768) >>> 16;
            end else begin
                magnitude = -$signed({value[50], value});
                rounded_magnitude = (magnitude + 52'sd32768) >>> 16;
                round_sq16 = -rounded_magnitude[32:0];
            end
        end
    endfunction

    wire signed [33:0] sum0 = $signed({start_reg0[31], start_reg0}) + increment_reg0;
    wire signed [33:0] sum1 = $signed({start_reg1[31], start_reg1}) + increment_reg1;
    wire signed [33:0] sum2 = $signed({start_reg2[31], start_reg2}) + increment_reg2;
    wire signed [33:0] sum3 = $signed({start_reg3[31], start_reg3}) + increment_reg3;
    wire signed [33:0] sum4 = $signed({start_reg4[31], start_reg4}) + increment_reg4;
    wire signed [33:0] sum5 = $signed({start_reg5[31], start_reg5}) + increment_reg5;

    wire overflow0 = (sum0[33:31] != {3{sum0[31]}});
    wire overflow1 = (sum1[33:31] != {3{sum1[31]}});
    wire overflow2 = (sum2[33:31] != {3{sum2[31]}});
    wire overflow3 = (sum3[33:31] != {3{sum3[31]}});
    wire overflow4 = (sum4[33:31] != {3{sum4[31]}});
    wire overflow5 = (sum5[33:31] != {3{sum5[31]}});

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state                     <= ST_IDLE;
            tick_count                <= 6'd0;
            busy                      <= 1'b0;
            sample_valid              <= 1'b0;
            sample_index              <= 6'd0;
            joint_ch0                 <= 32'sd0;
            joint_ch1                 <= 32'sd0;
            joint_ch2                 <= 32'sd0;
            joint_ch3                 <= 32'sd0;
            joint_ch4                 <= 32'sd0;
            joint_ch5                 <= 32'sd0;
            done                      <= 1'b0;
            error_start_while_busy    <= 1'b0;
            error_arithmetic_overflow <= 1'b0;
            start_reg0                <= 32'sd0;
            start_reg1                <= 32'sd0;
            start_reg2                <= 32'sd0;
            start_reg3                <= 32'sd0;
            start_reg4                <= 32'sd0;
            start_reg5                <= 32'sd0;
            target_reg0               <= 32'sd0;
            target_reg1               <= 32'sd0;
            target_reg2               <= 32'sd0;
            target_reg3               <= 32'sd0;
            target_reg4               <= 32'sd0;
            target_reg5               <= 32'sd0;
            phase_q16                 <= 17'd0;
            phase_sq_q16              <= 17'd0;
            phase_cube_q16            <= 17'd0;
            blend_q16                 <= 17'd0;
            scaled_product0           <= 51'sd0;
            scaled_product1           <= 51'sd0;
            scaled_product2           <= 51'sd0;
            scaled_product3           <= 51'sd0;
            scaled_product4           <= 51'sd0;
            scaled_product5           <= 51'sd0;
            increment_reg0            <= 33'sd0;
            increment_reg1            <= 33'sd0;
            increment_reg2            <= 33'sd0;
            increment_reg3            <= 33'sd0;
            increment_reg4            <= 33'sd0;
            increment_reg5            <= 33'sd0;
        end else begin
            sample_valid <= 1'b0;
            done         <= 1'b0;

            if (start && (state != ST_IDLE))
                error_start_while_busy <= 1'b1;

            case (state)
                ST_IDLE: begin
                    busy <= 1'b0;
                    if (start) begin
                        start_reg0  <= start_ch0;
                        start_reg1  <= start_ch1;
                        start_reg2  <= start_ch2;
                        start_reg3  <= start_ch3;
                        start_reg4  <= start_ch4;
                        start_reg5  <= start_ch5;
                        target_reg0 <= target_ch0;
                        target_reg1 <= target_ch1;
                        target_reg2 <= target_ch2;
                        target_reg3 <= target_ch3;
                        target_reg4 <= target_ch4;
                        target_reg5 <= target_ch5;
                        tick_count  <= 6'd1;
                        busy        <= 1'b1;
                        state       <= ST_PHASE;
                    end
                end

                ST_PHASE: begin
                    // 65536 / 32 = 2048 exactly; tick 32 maps to 65536.
                    phase_q16 <= {tick_count, 11'b0};
                    state <= ST_SQUARE;
                end

                ST_SQUARE: begin
                    phase_sq_q16 <= round_uq16(phase_square_full);
                    state <= ST_CUBE;
                end

                ST_CUBE: begin
                    phase_cube_q16 <= round_uq16(phase_cube_full);
                    state <= ST_BLEND;
                end

                ST_BLEND: begin
                    blend_q16 <= blend_full[16:0];
                    state <= ST_APPLY;
                end

                ST_APPLY: begin
                    scaled_product0 <= delta0 * blend_signed;
                    scaled_product1 <= delta1 * blend_signed;
                    scaled_product2 <= delta2 * blend_signed;
                    scaled_product3 <= delta3 * blend_signed;
                    scaled_product4 <= delta4 * blend_signed;
                    scaled_product5 <= delta5 * blend_signed;
                    state <= ST_ROUND;
                end

                ST_ROUND: begin
                    increment_reg0 <= round_sq16(scaled_product0);
                    increment_reg1 <= round_sq16(scaled_product1);
                    increment_reg2 <= round_sq16(scaled_product2);
                    increment_reg3 <= round_sq16(scaled_product3);
                    increment_reg4 <= round_sq16(scaled_product4);
                    increment_reg5 <= round_sq16(scaled_product5);
                    state <= ST_OUTPUT;
                end

                ST_OUTPUT: begin
                    // The final tick is forced to the latched target so the
                    // endpoint is exact even if intermediate arithmetic changes.
                    if (tick_count == 6'd32) begin
                        joint_ch0 <= target_reg0;
                        joint_ch1 <= target_reg1;
                        joint_ch2 <= target_reg2;
                        joint_ch3 <= target_reg3;
                        joint_ch4 <= target_reg4;
                        joint_ch5 <= target_reg5;
                    end else begin
                        joint_ch0 <= sum0[31:0];
                        joint_ch1 <= sum1[31:0];
                        joint_ch2 <= sum2[31:0];
                        joint_ch3 <= sum3[31:0];
                        joint_ch4 <= sum4[31:0];
                        joint_ch5 <= sum5[31:0];
                        if (overflow0 || overflow1 || overflow2 ||
                            overflow3 || overflow4 || overflow5)
                            error_arithmetic_overflow <= 1'b1;
                    end
                    sample_index <= tick_count;
                    sample_valid <= 1'b1;
                    if (tick_count == 6'd32) begin
                        done <= 1'b1;
                        busy <= 1'b0;
                        state <= ST_IDLE;
                    end else begin
                        tick_count <= tick_count + 1'b1;
                        state <= ST_PHASE;
                    end
                end

                default: begin
                    state <= ST_IDLE;
                    busy <= 1'b0;
                    error_arithmetic_overflow <= 1'b1;
                end
            endcase
        end
    end

endmodule
