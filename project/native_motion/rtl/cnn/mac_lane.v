// ============================================================================
// Block Name : mac_lane.v (Optimized Edition)
// Description: Single-channel INT8 MAC Lane with:
//              1. Local Reset Tree (Fanout Reduction)
//              2. Dynamic Zero-Skipping / Clock Gating (act_in == 0 -> skip mult)
//              3. DSP48E1 Pipelining (* use_dsp = "yes" *)
// Target FPAG : Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk_100mhz
// ============================================================================

`timescale 1ns / 1ps

module mac_lane (
    input  wire        clk,
    input  wire        rst_n,
    
    // Control Signals
    input  wire        clr,         // Clear accumulator to 0
    input  wire        en,          // Enable MAC operation
    
    // Data Inputs
    input  wire signed [7:0]  weight_in,      // Signed INT8 Weight [-128, 127]
    input  wire        [7:0]  act_in,         // Unsigned UINT8 Activation [0, 255]
    
    // Data Output
    output reg  signed [31:0] acc_out         // Signed INT32 Accumulator Result
);

    // ------------------------------------------------------------------------
    // 1. Local Reset Synchronizer Tree (Fanout Reduction)
    // ------------------------------------------------------------------------
    reg rst_n_sync1, rst_n_local;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rst_n_sync1 <= 1'b0;
            rst_n_local <= 1'b0;
        end else begin
            rst_n_sync1 <= 1'b1;
            rst_n_local <= rst_n_sync1;
        end
    end

    // ------------------------------------------------------------------------
    // 2. Stage 1: Zero-Skipping Gating & DSP Multiplier Pipelining
    // ------------------------------------------------------------------------
    wire signed [8:0]  act_signed = {1'b0, act_in};
    (* use_dsp = "yes" *) reg signed [17:0] mult_reg;
    reg mult_valid_reg;

    always @(posedge clk or negedge rst_n_local) begin
        if (!rst_n_local) begin
            mult_reg       <= 18'sd0;
            mult_valid_reg <= 1'b0;
        end else if (en) begin
            // Zero-Skipping: If activation == 0, gate multiplier to save energy
            if (act_in == 8'd0) begin
                mult_reg       <= 18'sd0;
                mult_valid_reg <= 1'b0;
            end else begin
                mult_reg       <= weight_in * act_signed;
                mult_valid_reg <= 1'b1;
            end
        end else begin
            mult_valid_reg <= 1'b0;
        end
    end

    // ------------------------------------------------------------------------
    // 3. Stage 2: Accumulation
    // ------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n_local) begin
        if (!rst_n_local) begin
            acc_out <= 32'sd0;
        end else if (clr) begin
            acc_out <= 32'sd0;
        end else if (mult_valid_reg) begin
            acc_out <= acc_out + mult_reg;
        end
    end

endmodule
