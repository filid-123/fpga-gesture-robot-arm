// Forward a dedicated 24 MHz clock to the OV5640 through an output DDR flop.
// ODDR keeps the output duty cycle independent of fabric data-path routing.
`timescale 1ns / 1ps

module ov5640_xclk_forward (
    input  wire clk_24mhz,
    output wire ov5640_xclk
);
    ODDR #(
        .DDR_CLK_EDGE("SAME_EDGE"),
        .INIT(1'b0),
        .SRTYPE("SYNC")
    ) u_xclk_oddr (
        .Q(ov5640_xclk),
        .C(clk_24mhz),
        .CE(1'b1),
        .D1(1'b1),
        .D2(1'b0),
        .R(1'b0),
        .S(1'b0)
    );
endmodule
