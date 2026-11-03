// ============================================================================
// Block Name : planner_seq_div
// Description: Restoring divider of the Phase 3 S2 planner:
//              quotient = floor(num * 2^32 / den), 0 <= num < den < 2^31.
//              Computes the shared path fraction s_frac once per sample.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz)
//
// Resource/timing plan: one 32-bit compare/subtract, 32 cycles + 1 (done
// pulse), no DSP.  The remainder stays below den (< 2^31), so the shifted
// remainder fits in 32 bits.  num and den must stay stable while busy.
//
// Truth boundary: source candidate.  Supplementary Icarus Verilog run only;
// XSim/synthesis/implementation not run.
// ============================================================================

`timescale 1ns / 1ps

module planner_seq_div (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    input  wire [30:0] num,
    input  wire [30:0] den,
    output reg         busy,
    output reg         done,
    output reg  [31:0] quotient
);

    reg [30:0] rem;
    reg [5:0]  count;

    wire [31:0] shifted = {rem, 1'b0};
    wire        fits    = (shifted >= {1'b0, den});
    wire [31:0] reduced = shifted - {1'b0, den};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rem      <= 31'd0;
            count    <= 6'd0;
            busy     <= 1'b0;
            done     <= 1'b0;
            quotient <= 32'd0;
        end else begin
            done <= 1'b0;
            if (start && !busy) begin
                rem      <= num;
                quotient <= 32'd0;
                count    <= 6'd32;
                busy     <= 1'b1;
            end else if (busy) begin
                rem      <= fits ? reduced[30:0] : shifted[30:0];
                quotient <= {quotient[30:0], fits};
                count    <= count - 6'd1;
                if (count == 6'd1) begin
                    busy <= 1'b0;
                    done <= 1'b1;
                end
            end
        end
    end

endmodule
