// Frozen Rain FC1: clamp_u8((signed32 accumulator * signed32 M + 2^30) >>> 31).
// Four independent 16-bit partial products and registered recombination.
// Accumulator already includes the bias. No dynamic shift or long DSP/carry chain.
`timescale 1ns/1ps
module requant_fixed31_pipeline(input wire clk,rst_n,valid_in,
 input wire signed [31:0] acc_in,quant_M,output reg valid_out,output reg [7:0] pixel_out);
 reg v1,v2,v3,v4;
 reg [31:0] ll;
 reg signed [31:0] hh;
 reg signed [32:0] lh,hl;
 reg signed [33:0] cross_sum;
 reg signed [63:0] base,product,shifted;
 wire signed [63:0] cross_extended={{30{cross_sum[33]}},cross_sum};
 always @(posedge clk)begin
  if(!rst_n)begin v1<=0;v2<=0;v3<=0;v4<=0;valid_out<=0;pixel_out<=0;end
  else begin
   v1<=valid_in;v2<=v1;v3<=v2;v4<=v3;valid_out<=v4;
   if(valid_in)begin
    ll<=$unsigned(acc_in[15:0])*$unsigned(quant_M[15:0]);
    hh<=$signed(acc_in[31:16])*$signed(quant_M[31:16]);
    lh<=$signed({1'b0,acc_in[15:0]})*$signed(quant_M[31:16]);
    hl<=$signed(acc_in[31:16])*$signed({1'b0,quant_M[15:0]});
   end
   if(v1)begin cross_sum<=$signed({lh[32],lh})+$signed({hl[32],hl});base<=$signed({hh,ll});end
   if(v2)product<=base+(cross_extended<<<16);
   if(v3)shifted<=(product+64'sd1073741824)>>>31;
   if(v4)begin
    if(shifted<0)pixel_out<=0;else if(shifted>255)pixel_out<=255;else pixel_out<=shifted[7:0];
   end
  end
 end
endmodule
