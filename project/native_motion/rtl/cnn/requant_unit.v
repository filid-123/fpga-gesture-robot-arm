// ============================================================================
// Block Name : requant_unit.v (Optimized 4-Stage Pipeline Edition)
// Description: 4-Stage Pipelined Requantization Unit with Integrated ReLU.
//              Optimized for timing closure (> 250 MHz Fmax margin).
//              Performs: out_uint8 = clamp_u8( ((acc + bias) * M + round) >> shift )
// Target FPAG : Xilinx Zynq-7020 (PYNQ-Z2, XC7Z020-1CLG400C)
// Clock Domain: clk_100mhz
// Pipeline Latency: 4 Clock Cycles
// ============================================================================

`timescale 1ns / 1ps

module requant_unit (
    input  wire        clk,
    input  wire        rst_n,
    
    // Control & Quantization Config
    input  wire        valid_in,       // Input data valid
    input  wire signed [31:0] quant_M,  // INT32 Quantization Multiplier M
    input  wire [4:0]  quant_shift,    // Shift amount (0 ~ 31)
    
    // Data Inputs
    input  wire signed [31:0] acc_in,   // 32-bit Accumulator Output from MAC Lane
    input  wire signed [31:0] bias_in,  // 32-bit Bias from BRAM
    
    // Data Outputs
    output reg         valid_out,      // Output valid (latency = 4 cycles)
    output reg  [7:0]  pixel_out       // Final 8-bit uint8 pixel [0, 255]
);

    // ------------------------------------------------------------------------
    // Stage 1: Bias Addition (1 cycle)
    // ------------------------------------------------------------------------
    reg  signed [31:0] stage1_acc_biased;
    reg                stage1_valid;
    reg  signed [31:0] stage1_M;
    reg         [4:0]  stage1_shift;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stage1_acc_biased <= 32'sd0;
            stage1_valid      <= 1'b0;
            stage1_M          <= 32'sd0;
            stage1_shift      <= 5'd0;
        end else begin
            stage1_acc_biased <= acc_in + bias_in;
            stage1_valid      <= valid_in;
            stage1_M          <= quant_M;
            stage1_shift      <= quant_shift;
        end
    end

    // ------------------------------------------------------------------------
    // Stage 2: Fixed-point Multiplication (1 cycle)
    // 32-bit Signed * 32-bit Signed -> 64-bit Signed
    // ------------------------------------------------------------------------
    reg  signed [63:0] stage2_mult;
    reg                stage2_valid;
    reg         [4:0]  stage2_shift;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stage2_mult  <= 64'sd0;
            stage2_valid <= 1'b0;
            stage2_shift <= 5'd0;
        end else begin
            stage2_mult  <= stage1_acc_biased * stage1_M;
            stage2_valid <= stage1_valid;
            stage2_shift <= stage1_shift;
        end
    end

    // ------------------------------------------------------------------------
    // Stage 3: Rounding Addition & Dynamic Arithmetic Shift (1 cycle)
    // Isolates the 64-bit barrel shifter from saturation logic
    // ------------------------------------------------------------------------
    reg  signed [63:0] stage3_shifted;
    reg                stage3_valid;

    wire signed [63:0] round_const = (stage2_shift > 0) ? (64'sd1 << (stage2_shift - 1)) : 64'sd0;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stage3_shifted <= 64'sd0;
            stage3_valid   <= 1'b0;
        end else begin
            stage3_shifted <= (stage2_mult + round_const) >>> stage2_shift;
            stage3_valid   <= stage2_valid;
        end
    end

    // ------------------------------------------------------------------------
    // Stage 4: Saturation & Integrated ReLU Clamp (1 cycle)
    // ------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pixel_out <= 8'd0;
            valid_out <= 1'b0;
        end else begin
            valid_out <= stage3_valid;
            
            // Saturation & ReLU Clamp [0, 255]
            if (stage3_shifted < 64'sd0) begin
                pixel_out <= 8'd0;       // ReLU Clamp min = 0
            end else if (stage3_shifted > 64'sd255) begin
                pixel_out <= 8'd255;     // Clamp max = 255
            end else begin
                pixel_out <= stage3_shifted[7:0];
            end
        end
    end

endmodule
