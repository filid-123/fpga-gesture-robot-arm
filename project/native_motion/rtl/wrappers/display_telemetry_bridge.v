// Structural wrapper: original instances, parameters and cycles preserved.
`timescale 1ns/1ps
module display_telemetry_bridge #(parameter integer HD_PREVIEW=0,parameter FONT_FILE="mode_a_font.mem")(
    output wire [7:0] metric_cls,
    output wire [7:0] metric_loc,
    input wire  pixel_clk,
    input wire  pixel_rst_n,
    input wire [93:0] source_ui,
    input wire [31:0] stage_cls_cycles,
    input wire [31:0] stage_loc_cycles,
    input wire  start,
    input wire  sys_clk,
    input wire  sys_rst_n,
    output wire [93:0] ui
);
cycles_to_ms8 loc_units(sys_clk,sys_rst_n,stage_loc_cycles,metric_loc);
cycles_to_ms8 cls_units(sys_clk,sys_rst_n,stage_cls_cycles,metric_cls);
mode_a_display_cdc #(.WIDTH(94)) status_cdc(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.source_data(source_ui),
  .pixel_clk(pixel_clk),.pixel_rst_n(pixel_rst_n),.frame_start(start),.display_data(ui));
endmodule
