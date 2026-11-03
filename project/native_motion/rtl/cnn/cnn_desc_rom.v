`timescale 1ns / 1ps

// Deprecated read-only wrapper retained for legacy testbenches. New designs
// must use cnn_desc_mem so PS can update a complete model package at runtime.
module cnn_desc_rom #(
    parameter MEM_INIT_FILE = "layer_descriptors.mem"
)(
    input  wire        clk,
    input  wire        rd_en,
    input  wire [7:0]  rd_addr,
    output reg  [31:0] rd_data
);

    reg [31:0] rom [0:255];

    initial begin
        $readmemh(MEM_INIT_FILE, rom);
    end

    always @(posedge clk) begin
        if (rd_en) begin
            rd_data <= rom[rd_addr];
        end
    end

endmodule
