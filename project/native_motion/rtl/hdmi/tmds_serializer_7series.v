// Four matched 10:1 TMDS serializers for 7-series.
// Serializing the fixed clock word through the same MASTER/SLAVE structure as
// RGB keeps its phase/latency tied to the data word, including after reset.
`timescale 1ns / 1ps

module tmds_serializer_7series (
    input  wire       pixel_clk,
    input  wire       pixel_clk_5x,
    input  wire       rst_n,
    input  wire [9:0] tmds_blue,
    input  wire [9:0] tmds_green,
    input  wire [9:0] tmds_red,
    output wire       tmds_clk_p,
    output wire       tmds_clk_n,
    output wire [2:0] tmds_data_p,
    output wire [2:0] tmds_data_n
);
    wire [39:0] words = {10'b1111100000, tmds_red, tmds_green, tmds_blue};
    wire [3:0] serial_data;
    genvar channel;

    generate
        for (channel = 0; channel < 4; channel = channel + 1) begin : g_tmds
            wire shift_1;
            wire shift_2;

            OSERDESE2 #(
                .DATA_RATE_OQ("DDR"),
                .DATA_RATE_TQ("SDR"),
                .DATA_WIDTH(10),
                .SERDES_MODE("MASTER"),
                .TRISTATE_WIDTH(1)
            ) u_master (
                .OFB(), .OQ(serial_data[channel]),
                .SHIFTOUT1(), .SHIFTOUT2(),
                .TBYTEOUT(), .TFB(), .TQ(),
                .CLK(pixel_clk_5x), .CLKDIV(pixel_clk),
                .D1(words[channel*10 + 0]),
                .D2(words[channel*10 + 1]),
                .D3(words[channel*10 + 2]),
                .D4(words[channel*10 + 3]),
                .D5(words[channel*10 + 4]),
                .D6(words[channel*10 + 5]),
                .D7(words[channel*10 + 6]),
                .D8(words[channel*10 + 7]),
                .OCE(1'b1), .RST(!rst_n),
                .SHIFTIN1(shift_1), .SHIFTIN2(shift_2),
                .T1(1'b0), .T2(1'b0), .T3(1'b0), .T4(1'b0),
                .TBYTEIN(1'b0), .TCE(1'b0)
            );

            OSERDESE2 #(
                .DATA_RATE_OQ("DDR"),
                .DATA_RATE_TQ("SDR"),
                .DATA_WIDTH(10),
                .SERDES_MODE("SLAVE"),
                .TRISTATE_WIDTH(1)
            ) u_slave (
                .OFB(), .OQ(),
                .SHIFTOUT1(shift_1), .SHIFTOUT2(shift_2),
                .TBYTEOUT(), .TFB(), .TQ(),
                .CLK(pixel_clk_5x), .CLKDIV(pixel_clk),
                .D1(1'b0), .D2(1'b0),
                .D3(words[channel*10 + 8]),
                .D4(words[channel*10 + 9]),
                .D5(1'b0), .D6(1'b0), .D7(1'b0), .D8(1'b0),
                .OCE(1'b1), .RST(!rst_n),
                .SHIFTIN1(1'b0), .SHIFTIN2(1'b0),
                .T1(1'b0), .T2(1'b0), .T3(1'b0), .T4(1'b0),
                .TBYTEIN(1'b0), .TCE(1'b0)
            );

          if(channel<3)begin : g_data
            OBUFDS #(.IOSTANDARD("TMDS_33"), .SLEW("FAST")) u_data_out (
                .I(serial_data[channel]),
                .O(tmds_data_p[channel]),
                .OB(tmds_data_n[channel])
            );
          end else begin : g_clock
            OBUFDS #(.IOSTANDARD("TMDS_33"), .SLEW("FAST")) u_clock_out (
                .I(serial_data[channel]),.O(tmds_clk_p),.OB(tmds_clk_n)
            );
          end
        end
    endgenerate

endmodule
