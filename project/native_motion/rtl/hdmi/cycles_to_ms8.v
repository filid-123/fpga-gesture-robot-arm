// Saturating floor(cycles/100000),8 compare/subtract stages, one input per clock.
// 80ns conversion latency avoids a 32-bit constant divider before UI CDC.
`timescale 1ns/1ps
module cycles_to_ms8(input wire clk,rst_n,input wire[31:0]cycles,output wire[7:0]ms);
 reg[24:0]remainder[0:8];reg[7:0]quotient[0:8];
 always @(posedge clk)begin
  if(!rst_n)begin remainder[0]<=0;quotient[0]<=0;end
  else if(cycles>=32'd25500000)begin remainder[0]<=0;quotient[0]<=255;end
  else begin remainder[0]<=cycles[24:0];quotient[0]<=0;end
 end
 genvar i;generate for(i=0;i<8;i=i+1)begin:stages
  localparam[24:0]THRESHOLD=(128>>i)*100000;
  always @(posedge clk)begin
   if(!rst_n)begin remainder[i+1]<=0;quotient[i+1]<=0;end
   else if(remainder[i]>=THRESHOLD)begin remainder[i+1]<=remainder[i]-THRESHOLD;quotient[i+1]<=quotient[i]|(8'h80>>i);end
   else begin remainder[i+1]<=remainder[i];quotient[i+1]<=quotient[i];end
  end
 end endgenerate
 assign ms=quotient[8];
endmodule
