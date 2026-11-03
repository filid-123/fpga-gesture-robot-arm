// ============================================================================
// Block Name : line_buffer_3x3.v (Clean Synthesis Edition)
// Description: 3x3 Convolutional Line Buffer & Sliding Window Generator.
//              Fully clean for Block RAM / SRL inference (No async reset on RAMs).
// Target FPAG : Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk_100mhz
// ============================================================================

`timescale 1ns / 1ps

module line_buffer_3x3 (
    input  wire        clk,
    input  wire        rst_n,
    
    // Control & Frame Dimensions
    input  wire        valid_in,        // Input pixel valid
    input  wire [5:0]  img_w,           // Feature map width (e.g. 32, 16, 8)
    
    // Data Input
    input  wire [7:0]  pixel_in,        // Incoming UINT8 pixel
    
    // Data Outputs (3x3 Window)
    output wire        valid_out,       // 3x3 Window valid
    output reg  [7:0]  w00, w01, w02,   // Line 0 (top row)
    output reg  [7:0]  w10, w11, w12,   // Line 1 (middle row)
    output reg  [7:0]  w20, w21, w22    // Line 2 (bottom row / current input)
);

    // ------------------------------------------------------------------------
    // Memory Arrays (Synchronous read/write, NO async reset for BRAM/SRL inference)
    // ------------------------------------------------------------------------
    (* ram_style = "srl" *) reg [7:0] line0_ram [0:63];
    (* ram_style = "srl" *) reg [7:0] line1_ram [0:63];
    
    reg [5:0] col_cnt;
    reg [5:0] row_cnt;
    
    wire [7:0] line0_pixel = line0_ram[col_cnt];
    wire [7:0] line1_pixel = line1_ram[col_cnt];

    // Local Reset Synchronizer Tree
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

    // Synchronous Memory Access (Clean Synthesis without Async Reset)
    always @(posedge clk) begin
        if (valid_in) begin
            line0_ram[col_cnt] <= line1_pixel;
            line1_ram[col_cnt] <= pixel_in;
        end
    end

    // Address & Control Counters
    always @(posedge clk or negedge rst_n_local) begin
        if (!rst_n_local) begin
            col_cnt <= 6'd0;
            row_cnt <= 6'd0;
        end else if (valid_in) begin
            if (col_cnt == img_w - 1) begin
                col_cnt <= 6'd0;
                row_cnt <= row_cnt + 1;
            end else begin
                col_cnt <= col_cnt + 1;
            end
        end
    end

    // Shift registers for 3x3 window
    always @(posedge clk or negedge rst_n_local) begin
        if (!rst_n_local) begin
            w00 <= 8'd0; w01 <= 8'd0; w02 <= 8'd0;
            w10 <= 8'd0; w11 <= 8'd0; w12 <= 8'd0;
            w20 <= 8'd0; w21 <= 8'd0; w22 <= 8'd0;
        end else if (valid_in) begin
            w00 <= w01; w01 <= w02; w02 <= line0_pixel;
            w10 <= w11; w11 <= w12; w12 <= line1_pixel;
            w20 <= w21; w21 <= w22; w22 <= pixel_in;
        end
    end

    // Valid output condition
    reg [1:0] valid_pipe;
    always @(posedge clk or negedge rst_n_local) begin
        if (!rst_n_local) begin
            valid_pipe <= 2'b0;
        end else begin
            valid_pipe <= {valid_pipe[0], (valid_in && (row_cnt >= 2) && (col_cnt >= 2))};
        end
    end

    assign valid_out = valid_pipe[1];

endmodule
