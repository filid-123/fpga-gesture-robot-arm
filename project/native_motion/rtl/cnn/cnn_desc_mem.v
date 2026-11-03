`timescale 1ns / 1ps

// Descriptor memory with a PS write port and a synchronous CNN read port.
// The memory is initialized for standalone boot/simulation, but may be
// replaced at runtime while the CNN core is idle.
module cnn_desc_mem #(
    parameter MEM_INIT_FILE = "layer_descriptors.mem"
)(
    input  wire        clk,

    input  wire        wr_en,
    input  wire [7:0]  wr_addr,
    input  wire [31:0] wr_data,

    input  wire        rd_en,
    input  wire [7:0]  rd_addr,
    output reg  [31:0] rd_data
);

    (* ram_style = "block" *) reg [31:0] mem [0:255];

    initial begin
        if (MEM_INIT_FILE != "") begin
            $readmemh(MEM_INIT_FILE, mem);
        end
    end

    always @(posedge clk) begin
        if (wr_en) begin
            mem[wr_addr] <= wr_data;
        end
        if (rd_en) begin
            rd_data <= mem[rd_addr];
        end
    end

endmodule
