// ============================================================================
// Adapter between locator_top word-addressed native ports and Vivado Block
// Memory Generator's 32-bit byte-addressed Port B used in the Phase 2-L1 BD.
// ============================================================================
`timescale 1ns / 1ps

module locator_bram_adapter (
    input  wire        locator_input_en,
    input  wire [12:0] locator_input_word_addr,
    output wire        input_mem_en,
    output wire [31:0] input_mem_byte_addr,
    output wire [3:0]  input_mem_we,
    output wire [31:0] input_mem_wdata,

    input  wire        locator_output_we,
    input  wire [11:0] locator_output_word_addr,
    input  wire [31:0] locator_output_wdata,
    output wire        output_mem_en,
    output wire [31:0] output_mem_byte_addr,
    output wire [3:0]  output_mem_we,
    output wire [31:0] output_mem_wdata
);

    assign input_mem_en        = locator_input_en;
    assign input_mem_byte_addr = {17'd0, locator_input_word_addr, 2'b00};
    assign input_mem_we        = 4'b0000;
    assign input_mem_wdata     = 32'd0;

    assign output_mem_en        = locator_output_we;
    assign output_mem_byte_addr = {18'd0, locator_output_word_addr, 2'b00};
    assign output_mem_we        = {4{locator_output_we}};
    assign output_mem_wdata     = locator_output_wdata;

endmodule
