// Fit the existing 640x480 UI into a 960x720 central canvas without stretching.
// All 1280 active pixels remain video pixels (side bars are background colour).
// Blanking must never be derived from the smaller canvas or camera window.
`timescale 1ns/1ps
module mode_a_720p_canvas(
 input wire pixel_clk,rst_n,
 input wire[10:0]physical_x,input wire[9:0]physical_y,
 input wire active_in,hsync_in,vsync_in,start_in,
 output wire[9:0]logical_x,logical_y,
 output wire[7:0]source_x,source_y,
 output reg active_out,hsync_out,vsync_out,start_out);
 // Precompute both UI and source-image coordinates. This removes the two
 // dependent divide-by-three operations from the 74.25 MHz RAM address path.
 // The maps are immutable 2048x18 and 1024x18 synchronous ROMs (1.5 BRAM).
 (* rom_style="block" *) reg[17:0]x_map[0:2047];
 (* rom_style="block" *) reg[17:0]y_map[0:1023];
 reg[17:0]x_word,y_word;integer i,l,s;
 initial begin
  for(i=0;i<2048;i=i+1)begin
   l=(i>=160 && i<1120)?((i-160)*2/3):1023;
   s=(((l-24)&1023)*2/3)&255;x_map[i]=(s<<10)|l;
  end
  for(i=0;i<1024;i=i+1)begin
   l=i*2/3;s=(((l-100)&1023)*2/3)&255;y_map[i]=(s<<10)|l;
  end
 end
 always @(posedge pixel_clk)begin x_word<=x_map[physical_x];y_word<=y_map[physical_y];end
 assign logical_x=x_word[9:0];assign logical_y=y_word[9:0];
 assign source_x=x_word[17:10];assign source_y=y_word[17:10];
 always @(posedge pixel_clk)begin
  if(!rst_n)begin active_out<=0;hsync_out<=0;vsync_out<=0;start_out<=0;end
  else begin active_out<=active_in;hsync_out<=hsync_in;vsync_out<=vsync_in;start_out<=start_in;end
 end
endmodule
