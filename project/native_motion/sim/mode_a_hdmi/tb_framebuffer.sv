`timescale 1ns/1ps
module tb_framebuffer;
reg s=0,p=0,r=0;always #5 s=~s;always #19.84127 p=~p;
reg we=0,pub=0,rv=0,fs=0;reg[12:0]a=0;reg[31:0]d=0,id=0,rid=0;reg[11:0]ra=0;
wire[31:0]rd,fid;wire valid,det;wire[8:0]x0,y0,x1,y1;
mode_a_framebuffer dut(s,r,we,a,d,pub,id,rv,rid,1'b1,9'd20,9'd24,9'd100,9'd128,p,r,fs,ra,rd,valid,det,x0,y0,x1,y1,fid);
task image(input integer num);integer i;begin
 for(i=0;i<4096;i=i+1)begin @(negedge s);we=1;a=i;d=(num<<24)|i;end
 @(negedge s);we=0;id=num;pub=1;@(negedge s);pub=0;
end endtask
task result(input integer num);begin @(negedge s);rid=num;rv=1;@(negedge s);rv=0;end endtask
task vblank;begin repeat(8)@(negedge p);fs=1;@(negedge p);fs=0;repeat(8)@(negedge p);end endtask
integer j;
initial begin repeat(8)@(negedge s);r=1;
 image(1);image(2);result(1);repeat(10)@(negedge s);
 if(valid)$fatal(1,"Image published before frame start");vblank();
 if(!valid || fid!=1 || !det || x0!=20 || y1!=128)$fatal(1,"Frame/box mismatch");
 image(3);image(4);
 for(j=0;j<4096;j=j+137)begin @(negedge p);ra=j;repeat(2)@(negedge p);if(rd!==((1<<24)|j))$fatal(1,"Displayed image overwritten");end
 result(4);vblank();if(fid!=4)$fatal(1,"Latest matched result not displayed");
 result(999);vblank();if(fid!=4)$fatal(1,"Unmatched result changed image");
 $display("PASS: overlapped capture, protected displayed bank, exact frame/box association and unmatched rejection");$finish;
end
endmodule
