`timescale 1ns/1ps
module tb_canvas;
 reg p=0,r=0;always #5 p=~p;
 reg[10:0]px;reg[9:0]py;reg a,h,v,f;
 wire[9:0]x,y;wire[7:0]sx,sy;wire ao,ho,vo,fo;
 mode_a_720p_canvas dut(p,r,px,py,a,h,v,f,x,y,sx,sy,ao,ho,vo,fo);
 integer n,lx,ly,ex,ey;
 initial begin
  px=0;py=0;a=0;h=0;v=0;f=0;
  repeat(3)@(negedge p);r=1;
  for(n=0;n<2048;n=n+1)begin
   @(negedge p);px=n;py=n%1024;a=n%2;h=(n/2)%2;v=(n/4)%2;f=(n/8)%2;
   lx=(n>=160 && n<1120)?((n-160)*2/3):1023;ly=(n%1024)*2/3;
   ex=(((lx-24)&1023)*2/3)&255;ey=(((ly-100)&1023)*2/3)&255;
   // Output still belongs to the preceding input until the clock edge.
   @(posedge p);#0.1;
   if({x,y,sx,sy}!=={10'(lx),10'(ly),8'(ex),8'(ey)})$fatal(1,"Map mismatch x=%0d y=%0d",n,n%1024);
   if({ao,ho,vo,fo}!=={a,h,v,f})$fatal(1,"Coordinate/control pipeline mismatch");
  end
  @(negedge p);r=0;@(posedge p);#0.1;
  if({ao,ho,vo,fo}!==0)$fatal(1,"Reset must suppress active/control/start");
  $display("PASS: all2048 X and1024 Y ROM entries equal floor coordinate and legacy source mapping, one-cycle DE/HS/VS/start alignment and reset");$finish;
 end
endmodule
