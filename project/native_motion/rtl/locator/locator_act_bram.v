`timescale 1ns / 1ps

// 32 KiB byte-wide activation store.  Source and destination layers use
// separate instances so one read and one write can proceed every clock.
module locator_act_bram (
    input  wire        clk,
    input  wire        wr_en,
    input  wire [14:0] wr_addr,
    input  wire [7:0]  wr_data,
    input  wire        rd_en,
    input  wire [14:0] rd_addr,
    output reg  [7:0]  rd_data
);

    (* ram_style = "block" *) reg [7:0] mem [0:32767];

    always @(posedge clk) begin
        if (wr_en)
            mem[wr_addr] <= wr_data;
        if (rd_en)
            rd_data <= mem[rd_addr];
    end

endmodule
