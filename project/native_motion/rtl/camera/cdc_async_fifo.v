// ============================================================================
// Dual-clock asynchronous FIFO for the OV5640 pixel path.
// Binary pointers stay local to each clock domain; only Gray-coded pointers
// cross the CDC boundary through two ASYNC_REG stages.
// ============================================================================
`timescale 1ns / 1ps

module cdc_async_fifo #(
    parameter integer DATA_WIDTH = 29,
    parameter integer ADDR_WIDTH = 10
)(
    input  wire                  wr_clk,
    input  wire                  wr_rst_n,
    input  wire                  wr_en,
    input  wire [DATA_WIDTH-1:0] wr_data,
    output wire                  wr_full,
    output reg                   wr_overflow,

    input  wire                  rd_clk,
    input  wire                  rd_rst_n,
    input  wire                  rd_en,
    output reg  [DATA_WIDTH-1:0] rd_data,
    output reg                   rd_valid,
    output wire                  rd_empty,
    output reg                   rd_underflow
);

    localparam integer PTR_WIDTH = ADDR_WIDTH + 1;

    (* ram_style = "block" *) reg [DATA_WIDTH-1:0] mem [0:(1 << ADDR_WIDTH)-1];

    reg [PTR_WIDTH-1:0] wr_bin;
    reg [PTR_WIDTH-1:0] wr_gray;
    reg [PTR_WIDTH-1:0] rd_bin;
    reg [PTR_WIDTH-1:0] rd_gray;

    (* ASYNC_REG = "TRUE" *) reg [PTR_WIDTH-1:0] rd_gray_wr_sync1;
    (* ASYNC_REG = "TRUE" *) reg [PTR_WIDTH-1:0] rd_gray_wr_sync2;
    (* ASYNC_REG = "TRUE" *) reg [PTR_WIDTH-1:0] wr_gray_rd_sync1;
    (* ASYNC_REG = "TRUE" *) reg [PTR_WIDTH-1:0] wr_gray_rd_sync2;

    reg wr_full_reg;
    reg rd_empty_reg;
    wire wr_take = wr_en && !wr_full_reg;
    wire rd_take = rd_en && !rd_empty_reg;

    wire [PTR_WIDTH-1:0] wr_bin_next = wr_bin + {{(PTR_WIDTH-1){1'b0}}, wr_take};
    wire [PTR_WIDTH-1:0] rd_bin_next = rd_bin + {{(PTR_WIDTH-1){1'b0}}, rd_take};
    wire [PTR_WIDTH-1:0] wr_gray_next = (wr_bin_next >> 1) ^ wr_bin_next;
    wire [PTR_WIDTH-1:0] rd_gray_next = (rd_bin_next >> 1) ^ rd_bin_next;

    // Full when the next write pointer equals the synchronized read pointer
    // with its two most-significant Gray bits inverted.
    wire [PTR_WIDTH-1:0] rd_gray_full_compare = {
        ~rd_gray_wr_sync2[PTR_WIDTH-1:PTR_WIDTH-2],
         rd_gray_wr_sync2[PTR_WIDTH-3:0]
    };

    wire wr_full_next = (wr_gray_next == rd_gray_full_compare);
    wire rd_empty_next = (rd_gray_next == wr_gray_rd_sync2);

    assign wr_full  = wr_full_reg;
    assign rd_empty = rd_empty_reg;

    // Keep the memory array in reset-free clocked processes so Vivado can map
    // the dual-clock storage to block RAM. Valid/empty state protects rd_data
    // until the first legal read, so the data register itself needs no reset.
    always @(posedge wr_clk) begin
        if (wr_take)
            mem[wr_bin[ADDR_WIDTH-1:0]] <= wr_data;
    end

    always @(posedge rd_clk) begin
        if (rd_take)
            rd_data <= mem[rd_bin[ADDR_WIDTH-1:0]];
    end

    always @(posedge wr_clk) begin
        if (!wr_rst_n) begin
            wr_bin      <= {PTR_WIDTH{1'b0}};
            wr_gray     <= {PTR_WIDTH{1'b0}};
            wr_full_reg <= 1'b0;
            wr_overflow <= 1'b0;
        end else begin
            wr_full_reg <= wr_full_next;
            wr_overflow <= wr_en && wr_full;
            if (wr_take) begin
                wr_bin  <= wr_bin_next;
                wr_gray <= wr_gray_next;
            end
        end
    end

    always @(posedge rd_clk) begin
        if (!rd_rst_n) begin
            rd_bin       <= {PTR_WIDTH{1'b0}};
            rd_gray      <= {PTR_WIDTH{1'b0}};
            rd_empty_reg <= 1'b1;
            rd_valid     <= 1'b0;
            rd_underflow <= 1'b0;
        end else begin
            rd_empty_reg <= rd_empty_next;
            rd_valid     <= 1'b0;
            rd_underflow <= rd_en && rd_empty;
            if (rd_take) begin
                rd_valid <= 1'b1;
                rd_bin   <= rd_bin_next;
                rd_gray  <= rd_gray_next;
            end
        end
    end

    always @(posedge wr_clk) begin
        if (!wr_rst_n) begin
            rd_gray_wr_sync1 <= {PTR_WIDTH{1'b0}};
            rd_gray_wr_sync2 <= {PTR_WIDTH{1'b0}};
        end else begin
            rd_gray_wr_sync1 <= rd_gray;
            rd_gray_wr_sync2 <= rd_gray_wr_sync1;
        end
    end

    always @(posedge rd_clk) begin
        if (!rd_rst_n) begin
            wr_gray_rd_sync1 <= {PTR_WIDTH{1'b0}};
            wr_gray_rd_sync2 <= {PTR_WIDTH{1'b0}};
        end else begin
            wr_gray_rd_sync1 <= wr_gray;
            wr_gray_rd_sync2 <= wr_gray_rd_sync1;
        end
    end

endmodule
