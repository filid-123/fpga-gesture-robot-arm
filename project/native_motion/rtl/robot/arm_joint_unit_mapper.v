// ============================================================================
// Block Name : arm_joint_unit_mapper
// Description: Six-channel logical Q16.16 rad -> device-unit mapper, contract
//              arm_unit_map_v1 (ps/robot/arm_fixed_point.py):
//                limit = rad < soft_min || rad > soft_max        (before dir)
//                m     = dir_neg ? -rad : rad
//                dev   = sat32(zero + round_away(m * scale / 2^32))
//              scale is UQ16.16 device units per rad.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz)
//
// Resource/timing plan:
// - One channel at a time.  Right-shift multiplier: {hi, lo} starts as
//   {0, scale}; for 32 steps hi += |m| when lo[0], then {hi, lo} >>= 1.
//   Only a 34-bit adder is in the loop (0 DSP48E1), and the multiplier
//   register doubles as the low product half.  round_away = hi + lo[31].
//   6 x (32 + 4) + 1 = 217 cycles per sample (2.2 us at 100 MHz).
// - Per-channel parameters are read through cfg_ch from LUTRAM in
//   arm_backend_axi_top (write-locked while the backend is active).
// - Results are written through dev_we/dev_ch/dev_data into the command
//   LUTRAM of arm_backend_core (one write per channel), so no 192-bit output
//   register or write demultiplexer is needed.
// - joints_q16 must stay stable while busy (the backend maps before it
//   handshakes the trajectory sample, so ready/valid keeps it stable).
// - Every signed extension is explicit.  done is a one-cycle pulse; limit
//   and saturation masks are stable until the next start.  start while busy
//   is ignored (the backend never issues it).
//
// Truth boundary: source candidate.  Supplementary Icarus Verilog run only;
// XSim/synthesis/implementation not run.
// ============================================================================

`timescale 1ns / 1ps

module arm_joint_unit_mapper (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         start,
    input  wire [191:0] joints_q16,
    // Parameters of channel cfg_ch (combinational read, same cycle).
    output wire [2:0]   cfg_ch,
    input  wire signed [31:0] ch_soft_min_q16,
    input  wire signed [31:0] ch_soft_max_q16,
    input  wire signed [31:0] ch_zero_dev,
    input  wire [31:0]  ch_scale_uq16_16,
    input  wire [5:0]   dir_neg,
    output wire         busy,
    output reg          done,
    output reg          dev_we,
    output reg  [2:0]   dev_ch,
    output reg  [31:0]  dev_data,
    output reg  [5:0]   limit_mask,
    output reg  [5:0]   sat_mask
);

    localparam [2:0] ST_IDLE  = 3'd0;
    localparam [2:0] ST_LOAD  = 3'd1;
    localparam [2:0] ST_MUL   = 3'd2;
    localparam [2:0] ST_ROUND = 3'd3;
    localparam [2:0] ST_APPLY = 3'd4;
    localparam [2:0] ST_STORE = 3'd5;

    reg [2:0]  state;
    reg [2:0]  channel;
    reg [4:0]  mul_count;

    reg signed [31:0] zero_reg;
    reg [32:0] magnitude;            // |m| <= 2^31
    reg        negative;
    reg [32:0] hi;                   // upper product bits
    reg [31:0] lo;                   // multiplier, then lower product bits
    reg [32:0] rounded;              // (product + 2^31) >> 32, <= 2^31
    reg signed [33:0] device_sum;

    assign busy   = (state != ST_IDLE);
    assign cfg_ch = channel;

    wire signed [31:0] sel_rad = joints_q16[channel * 32 +: 32];

    // |rad| with an explicit 33-bit extension; INT32_MIN maps to 2^31.
    wire signed [32:0] rad_ext = {sel_rad[31], sel_rad};
    wire [32:0]        rad_abs = rad_ext[32] ? (33'd0 - rad_ext) : rad_ext;

    wire [33:0] hi_sum = {1'b0, hi} + (lo[0] ? {1'b0, magnitude} : 34'd0);

    wire signed [33:0] zero_ext    = {{2{zero_reg[31]}}, zero_reg};
    wire signed [33:0] rounded_ext = {1'b0, rounded};
    wire signed [33:0] device_next = negative ? (zero_ext - rounded_ext) : (zero_ext + rounded_ext);
    wire               sat_high    = (device_sum > 34'sd2147483647);
    wire               sat_low     = (device_sum < -34'sd2147483648);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state      <= ST_IDLE;
            channel    <= 3'd0;
            mul_count  <= 5'd0;
            zero_reg   <= 32'sd0;
            magnitude  <= 33'd0;
            negative   <= 1'b0;
            hi         <= 33'd0;
            lo         <= 32'd0;
            rounded    <= 33'd0;
            device_sum <= 34'sd0;
            done       <= 1'b0;
            dev_we     <= 1'b0;
            dev_ch     <= 3'd0;
            dev_data   <= 32'd0;
            limit_mask <= 6'd0;
            sat_mask   <= 6'd0;
        end else begin
            done   <= 1'b0;
            dev_we <= 1'b0;
            case (state)
                ST_IDLE: begin
                    if (start) begin
                        channel    <= 3'd0;
                        limit_mask <= 6'd0;
                        sat_mask   <= 6'd0;
                        state      <= ST_LOAD;
                    end
                end

                ST_LOAD: begin
                    // Limits use the logical value before the direction flip.
                    if ((sel_rad < ch_soft_min_q16) || (sel_rad > ch_soft_max_q16))
                        limit_mask[channel] <= 1'b1;
                    zero_reg  <= ch_zero_dev;
                    magnitude <= rad_abs;
                    negative  <= (rad_abs != 33'd0) && (sel_rad[31] ^ dir_neg[channel]);
                    hi        <= 33'd0;
                    lo        <= ch_scale_uq16_16;
                    mul_count <= 5'd0;
                    state     <= ST_MUL;
                end

                ST_MUL: begin
                    // hi_sum < 2^34 because hi < 2^32 and |m| <= 2^31.
                    hi        <= hi_sum[33:1];
                    lo        <= {hi_sum[0], lo[31:1]};
                    mul_count <= mul_count + 5'd1;
                    if (mul_count == 5'd31)
                        state <= ST_ROUND;
                end

                ST_ROUND: begin
                    // Magnitude rounding (ties away from zero after the sign).
                    rounded <= hi + {32'd0, lo[31]};
                    state   <= ST_APPLY;
                end

                ST_APPLY: begin
                    device_sum <= device_next;
                    state      <= ST_STORE;
                end

                ST_STORE: begin
                    dev_we <= 1'b1;
                    dev_ch <= channel;
                    if (sat_high) begin
                        dev_data          <= 32'h7fff_ffff;
                        sat_mask[channel] <= 1'b1;
                    end else if (sat_low) begin
                        dev_data          <= 32'h8000_0000;
                        sat_mask[channel] <= 1'b1;
                    end else begin
                        dev_data <= device_sum[31:0];
                    end
                    if (channel == 3'd5) begin
                        done  <= 1'b1;
                        state <= ST_IDLE;
                    end else begin
                        channel <= channel + 3'd1;
                        state   <= ST_LOAD;
                    end
                end

                default: state <= ST_IDLE;
            endcase
        end
    end

endmodule
