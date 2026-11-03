// Structural wrapper: original instances, parameters and cycles preserved.
`timescale 1ns/1ps
module hdmi_phy_pipeline #(parameter integer HD_PREVIEW=0,parameter FONT_FILE="mode_a_font.mem")(
    input wire [7:0] b,
    input wire  de,
    input wire [7:0] g,
    input wire  pixel_clk,
    input wire  pixel_clk_5x,
    input wire  pixel_rst_n,
    input wire [7:0] r,
    input wire  rhs,
    input wire  rvs,
    output wire  tmds_clk_n,
    output wire  tmds_clk_p,
    output wire [2:0] tmds_data_n,
    output wire [2:0] tmds_data_p
);
wire [9:0] tb;
wire [9:0] tg;
wire [9:0] tr;
tmds_encoder eb(.pixel_clk(pixel_clk),.rst_n(pixel_rst_n),.video_data(b),.data_enable(de),.control_0(rhs),.control_1(rvs),.tmds_word(tb));
tmds_encoder eg(.pixel_clk(pixel_clk),.rst_n(pixel_rst_n),.video_data(g),.data_enable(de),.control_0(1'b0),.control_1(1'b0),.tmds_word(tg));
tmds_encoder er(.pixel_clk(pixel_clk),.rst_n(pixel_rst_n),.video_data(r),.data_enable(de),.control_0(1'b0),.control_1(1'b0),.tmds_word(tr));
tmds_serializer_7series serializer(.pixel_clk(pixel_clk),.pixel_clk_5x(pixel_clk_5x),.rst_n(pixel_rst_n),.tmds_blue(tb),.tmds_green(tg),.tmds_red(tr),
  .tmds_clk_p(tmds_clk_p),.tmds_clk_n(tmds_clk_n),.tmds_data_p(tmds_data_p),.tmds_data_n(tmds_data_n));
endmodule
