// ============================================================================
// Block Name : planner_seq_mult
// Description: Unsigned sequential multiplier shared by the Phase 3 S2
//              planner: product = a * b, a < 2^33, b < 2^32 (32 steps).
//              Reference: planner_p2p_reference.py (exact integers).
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz)
//
// Resource/timing plan: right-shift structure {hi, lo}: lo starts as b; for
// 32 steps hi += a when lo[0], then {hi, lo} >>= 1.  One 34-bit adder, no
// DSP48E1, 32 cycles + 1 (done pulse).  a and b must stay stable while busy
// (the planner core drives them from its own registers).
//
// Truth boundary: source candidate.  Supplementary Icarus Verilog run only;
// XSim/synthesis/implementation not run.
// ============================================================================

`timescale 1ns / 1ps

module planner_seq_mult (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    input  wire [32:0] a,
    input  wire [31:0] b,
    output reg         busy,
    output reg         done,
    output wire [64:0] product
);

    reg [32:0] hi;
    reg [31:0] lo;
    reg [5:0]  count;

    wire [33:0] sum = {1'b0, hi} + (lo[0] ? {1'b0, a} : 34'd0);

    assign product = {hi, lo};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            hi    <= 33'd0;
            lo    <= 32'd0;
            count <= 6'd0;
            busy  <= 1'b0;
            done  <= 1'b0;
        end else begin
            done <= 1'b0;
            if (start && !busy) begin
                hi    <= 33'd0;
                lo    <= b;
                count <= 6'd32;
                busy  <= 1'b1;
            end else if (busy) begin
                hi    <= sum[33:1];
                lo    <= {sum[0], lo[31:1]};
                count <= count - 6'd1;
                if (count == 6'd1) begin
                    busy <= 1'b0;
                    done <= 1'b1;
                end
            end
        end
    end

endmodule
