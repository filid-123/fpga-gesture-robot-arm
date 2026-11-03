// 4096 x 32 simple dual-port, dual-clock frame memory.
// Keeping each bank in its own canonical inference template prevents the
// display ping/pong selection from degrading the storage into distributed RAM.
`timescale 1ns / 1ps

module hdmi_frame_bram (
    input  wire        write_clk,
    input  wire        write_enable,
    input  wire [11:0] write_addr,
    input  wire [31:0] write_data,
    input  wire        read_clk,
    input  wire [11:0] read_addr,
    output reg  [31:0] read_data
);
    (* ram_style = "block" *) reg [31:0] memory [0:4095];

    always @(posedge write_clk) begin
        if (write_enable)
            memory[write_addr] <= write_data;
    end

    always @(posedge read_clk) begin
        read_data <= memory[read_addr];
    end
endmodule
