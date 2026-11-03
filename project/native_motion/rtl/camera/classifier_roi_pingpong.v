// EXPERIMENTAL: two independent 1KiB ROI banks, one shared synchronous read.
// Bank ownership belongs to autonomous_overlap_ctrl, not inferred from busy.
`timescale 1ns/1ps
module classifier_roi_pingpong(
 input wire clk,wr_en,wr_bank,
 input wire[7:0]wr_word_addr,
 input wire[31:0]wr_data,
 input wire rd_en,rd_bank,
 input wire[9:0]rd_byte_addr,
 output reg[7:0]rd_data
);
 (* ram_style="block" *) reg[31:0]mem[0:511];
 reg[31:0]rd_word;
 reg[1:0]rd_lane;
 always @(posedge clk)begin
  if(wr_en)mem[{wr_bank,wr_word_addr}]<=wr_data;
  if(rd_en)begin rd_word<=mem[{rd_bank,rd_byte_addr[9:2]}];rd_lane<=rd_byte_addr[1:0];end
 end
 always @(*)begin
  case(rd_lane)
   0:rd_data=rd_word[7:0];1:rd_data=rd_word[15:8];
   2:rd_data=rd_word[23:16];default:rd_data=rd_word[31:24];
  endcase
 end
endmodule
