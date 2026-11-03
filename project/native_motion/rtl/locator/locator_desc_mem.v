// 4 KiB / 1024-word dual-port descriptor memory.
`timescale 1ns / 1ps

module locator_desc_mem (
    input  wire        clk,
    input  wire        wr_en,
    input  wire [9:0]  wr_addr,
    input  wire [31:0] wr_data,
    input  wire        rd_en,
    input  wire [9:0]  rd_addr,
    output reg  [31:0] rd_data
);
    (* ram_style = "block" *) reg [31:0] mem [0:1023];

    always @(posedge clk) begin
        if (wr_en)
            mem[wr_addr] <= wr_data;
        if (rd_en)
            rd_data <= mem[rd_addr];
    end
endmodule
