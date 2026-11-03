// Six independent 18 x 2048 true dual-port memories. Q16 offsets retain every
// stored low bit; a per-channel signed base restores the original 32-bit word.
// Port A is shared with configuration readback while the player is idle.
`timescale 1ns/1ps
module b_route_ram(
 input wire clk, input wire [10:0] a_addr,b_addr,
 input wire we, input wire [17:0] wdata,
 output reg [17:0] a_data,b_data
);
 (* ram_style="block" *) reg [17:0] mem[0:2047];
 always @(posedge clk) a_data<=mem[a_addr];
 always @(posedge clk) begin
  if(we) mem[b_addr]<=wdata;
  b_data<=mem[b_addr];
 end
endmodule
