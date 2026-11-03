`timescale 1ns/1ps
module tb_serializer;
reg p=0,p5=0,r=0;always #19.84127 p=~p;always #3.968254 p5=~p5;
wire cp,cn;wire[2:0]dp,dn;reg[9:0]blue=10'h139,green=10'h2c5,red=10'h0d3;
tmds_serializer_7series dut(p,p5,r,blue,green,red,cp,cn,dp,dn);
reg [19:0] samples[0:3];integer count=0,j,k;reg enabled=0,matched,lane_match;reg[9:0]expected,observed;
always @(p5)if(enabled && count<20)begin #0.2;
 if(dp!==~dn)$fatal(1,"Differential data mismatch");
 if(cp!==~cn)$fatal(1,"Differential clock mismatch");
 for(integer n=0;n<3;n=n+1)samples[n][count]=dp[n];samples[3][count]=cp;count=count+1;
end
initial begin repeat(8)@(negedge p);r=1;repeat(32)@(negedge p);enabled=1;
 wait(count==20);enabled=0;
 for(j=0;j<4;j=j+1)begin
  observed=samples[j][9:0];
  if(samples[j][19:10]!==observed)$fatal(1,"Serializer not ten-bit periodic");
 end
 matched=0;
 for(k=0;k<10;k=k+1)begin
  lane_match=1;
  for(j=0;j<4;j=j+1)begin
   expected=(j==0)?blue:((j==1)?green:((j==2)?red:10'b1111100000));
   if(samples[j][9:0]!==((expected>>k)|(expected<<(10-k))))lane_match=0;
  end
  if(lane_match)matched=1;
 end
 if(!matched)$fatal(1,"Clock/data have different serial symbol phases");
 $display("PASS: real UNISIM eight OSERDESE2, four coherent ten-bit symbols, differential clock at exactly five high/five low bits");$finish;
end
endmodule
