// Standard 1280x720 progressive timing: 74.25 MHz / (1650*750) = 60 Hz.
// Active video starts at (0,0); horizontal/vertical sync are positive.
`timescale 1ns/1ps
module video_timing_720p(
 input wire pixel_clk,rst_n,
 output reg[10:0]x,output reg[9:0]y,
 output wire active_video,hsync,vsync,frame_start);
 assign active_video=(x<11'd1280 && y<10'd720);
 assign hsync=(x>=11'd1390 && x<11'd1430);
 assign vsync=(y>=10'd725 && y<10'd730);
 assign frame_start=(x==0 && y==0);
 always @(posedge pixel_clk)begin
  if(!rst_n)begin x<=0;y<=0;end
  else if(x==11'd1649)begin x<=0;if(y==10'd749)y<=0;else y<=y+1'b1;end
  else x<=x+1'b1;
 end
endmodule
