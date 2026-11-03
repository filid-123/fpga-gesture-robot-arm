// Structural wrapper: original instances, parameters and cycles preserved.
`timescale 1ns/1ps
module display_scan_pipeline #(parameter integer HD_PREVIEW=0,parameter FONT_FILE="mode_a_font.mem")(
    output wire  active,
    output wire  hs,
    input wire  pixel_clk,
    input wire  pixel_rst_n,
    output wire [7:0] source_x,
    output wire [7:0] source_y,
    output wire  start,
    output wire  vs,
    output wire [9:0] x,
    output wire [9:0] y
);
wire  pa;
wire  ph;
wire [10:0] physical_x;
wire [9:0] physical_y;
wire  ps;
wire  pv;
video_timing_720p timing(.pixel_clk(pixel_clk),.rst_n(pixel_rst_n),.x(physical_x),.y(physical_y),.active_video(pa),.hsync(ph),.vsync(pv),.frame_start(ps));
mode_a_720p_canvas canvas(.pixel_clk(pixel_clk),.rst_n(pixel_rst_n),.physical_x(physical_x),.physical_y(physical_y),.logical_x(x),.logical_y(y),
  .source_x(source_x),.source_y(source_y),.active_in(pa),.hsync_in(ph),.vsync_in(pv),.start_in(ps),.active_out(active),.hsync_out(hs),.vsync_out(vs),.start_out(start));
endmodule
