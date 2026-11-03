// Integration-only sink. Real TMDS encoder remains active; serializers are
// separately checked against UNISIM and implemented with the production module.
module tmds_serializer_7series(input wire pixel_clk,pixel_clk_5x,rst_n,
 input wire[9:0] tmds_blue,tmds_green,tmds_red,
 output wire tmds_clk_p,tmds_clk_n,output wire[2:0]tmds_data_p,tmds_data_n);
 assign tmds_clk_p=pixel_clk;assign tmds_clk_n=~pixel_clk;
 assign tmds_data_p={tmds_red[0],tmds_green[0],tmds_blue[0]};assign tmds_data_n=~tmds_data_p;
endmodule
