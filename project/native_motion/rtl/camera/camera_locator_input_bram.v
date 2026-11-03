// Dedicated 32 KiB ping/pong input memory for the PL camera path.
// Camera writes and Locator reads share the 100 MHz domain on separate ports.
`timescale 1ns / 1ps

module camera_locator_input_bram #(
    parameter integer ADDR_BITS = 13
)(
    input  wire        clk,
    input  wire        camera_we,
    input  wire [12:0] camera_word_addr,
    input  wire [31:0] camera_wdata,
    input  wire        locator_en,
    input  wire [12:0] locator_word_addr,
    output reg  [31:0] locator_rdata
);
    (* ram_style = "block" *) reg [31:0] mem [0:(1<<ADDR_BITS)-1];

    always @(posedge clk) begin
        if (camera_we)
            mem[camera_word_addr[ADDR_BITS-1:0]] <= camera_wdata;
        if (locator_en)
            locator_rdata <= mem[locator_word_addr[ADDR_BITS-1:0]];
    end
endmodule
