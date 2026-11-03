// Dual-clock 1 KiB ROI memory: camera writes packed words at 100 MHz and the
// existing classifier reads Gray8 pixels at 50 MHz with one-cycle latency.
`timescale 1ns / 1ps

module classifier_roi_bram (
    input  wire        wr_clk,
    input  wire        wr_en,
    input  wire [7:0]  wr_word_addr,
    input  wire [31:0] wr_data,

    input  wire        rd_clk,
    input  wire        rd_en,
    input  wire [9:0]  rd_byte_addr,
    output reg  [7:0]  rd_data
);
    (* ram_style = "block" *) reg [31:0] mem [0:255];
    reg [31:0] rd_word;
    reg [1:0]  rd_lane;

    always @(posedge wr_clk) begin
        if (wr_en)
            mem[wr_word_addr] <= wr_data;
    end

    always @(posedge rd_clk) begin
        if (rd_en) begin
            rd_word <= mem[rd_byte_addr[9:2]];
            rd_lane <= rd_byte_addr[1:0];
        end
    end

    always @(*) begin
        case (rd_lane)
            2'd0: rd_data = rd_word[7:0];
            2'd1: rd_data = rd_word[15:8];
            2'd2: rd_data = rd_word[23:16];
            default: rd_data = rd_word[31:24];
        endcase
    end
endmodule
