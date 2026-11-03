// ============================================================================
// Block Name : mac_array_32ch.v (Optimized Vector & Adder-Tree Edition)
// Description: 32-Channel Parallel INT8 MAC Array Engine with:
//              1. 32 Parallel INT8 MAC Lanes
//              2. 5-Stage Pipelined Binary Adder Tree for 32-Channel Reduction Sum
// Target FPAG : Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk_100mhz
// ============================================================================

`timescale 1ns / 1ps

module mac_array_32ch (
    input  wire        clk,
    input  wire        rst_n,
    
    // Global Control Signals
    input  wire        clr,                             // Clear accumulator to 0
    input  wire        en,                              // Enable MAC calculation
    
    // Data Inputs (Packed Arrays for Vivado compatibility)
    input  wire [255:0] weight_vec,                     // 32 x Signed INT8 Weights (32 * 8 = 256 bits)
    input  wire [255:0] act_vec,                        // 32 x Unsigned UINT8 Activations (32 * 8 = 256 bits)
    
    // Data Outputs
    output wire [1023:0] acc_vec,                       // 32 x Signed INT32 Accumulators
    output reg  signed [31:0] sum_all_32ch              // Pipelined Sum of All 32 Channels (for Dense/FC Layer)
);

    // Retiming Pipeline Registers to eliminate Setup Time Violations (Fmax > 250 MHz)
    reg [255:0] weight_vec_reg;
    reg [255:0] act_vec_reg;
    reg         clr_reg;
    reg         en_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            weight_vec_reg <= 256'd0;
            act_vec_reg    <= 256'd0;
            clr_reg        <= 1'b0;
            en_reg         <= 1'b0;
        end else begin
            weight_vec_reg <= weight_vec;
            act_vec_reg    <= act_vec;
            clr_reg        <= clr;
            en_reg         <= en;
        end
    end

    // Instantiate 32 MAC Lanes (Driven by Retimed Pipeline Registers)
    genvar i;
    generate
        for (i = 0; i < 32; i = i + 1) begin : gen_mac_lanes
            mac_lane lane_inst (
                .clk(clk),
                .rst_n(rst_n),
                .clr(clr_reg),
                .en(en_reg),
                .weight_in(weight_vec_reg[i*8 +: 8]),
                .act_in(act_vec_reg[i*8 +: 8]),
                .acc_out(acc_vec[i*32 +: 32])
            );
        end
    endgenerate

    // ------------------------------------------------------------------------
    // 5-Stage Pipelined Binary Reduction Adder Tree (32 -> 16 -> 8 -> 4 -> 2 -> 1)
    // ------------------------------------------------------------------------
    reg signed [31:0] tree_lvl1 [0:15];
    reg signed [31:0] tree_lvl2 [0:7];
    reg signed [31:0] tree_lvl3 [0:3];
    reg signed [31:0] tree_lvl4 [0:1];

    integer k;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (k = 0; k < 16; k = k + 1) tree_lvl1[k] <= 32'sd0;
            for (k = 0; k < 8;  k = k + 1) tree_lvl2[k] <= 32'sd0;
            for (k = 0; k < 4;  k = k + 1) tree_lvl3[k] <= 32'sd0;
            for (k = 0; k < 2;  k = k + 1) tree_lvl4[k] <= 32'sd0;
            sum_all_32ch <= 32'sd0;
        end else begin
            // Level 1: 32 -> 16
            for (k = 0; k < 16; k = k + 1)
                tree_lvl1[k] <= $signed(acc_vec[(2*k)*32 +: 32]) + $signed(acc_vec[(2*k+1)*32 +: 32]);
                
            // Level 2: 16 -> 8
            for (k = 0; k < 8; k = k + 1)
                tree_lvl2[k] <= tree_lvl1[2*k] + tree_lvl1[2*k+1];
                
            // Level 3: 8 -> 4
            for (k = 0; k < 4; k = k + 1)
                tree_lvl3[k] <= tree_lvl2[2*k] + tree_lvl2[2*k+1];

            // Level 4: 4 -> 2
            for (k = 0; k < 2; k = k + 1)
                tree_lvl4[k] <= tree_lvl3[2*k] + tree_lvl3[2*k+1];

            // Level 5: 2 -> 1
            sum_all_32ch <= tree_lvl4[0] + tree_lvl4[1];
        end
    end

endmodule
