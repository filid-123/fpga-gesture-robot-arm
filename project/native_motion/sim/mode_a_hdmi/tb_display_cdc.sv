`timescale 1ns/1ps
module tb_display_cdc;
reg s=0,p=0,r=0,fs=0;always #5 s=~s;always #19.84127 p=~p;
reg [31:0] n=0;wire[63:0] source={n,~n};wire[63:0] out;
mode_a_display_cdc #(.WIDTH(64)) dut(s,r,source,p,r,fs,out);
always @(posedge s)if(r)n<=n+1;
integer i,seen=0;reg[63:0] prior;reg prev_fs;
always @(posedge p)begin prior=out;prev_fs=fs;#1;if(r)begin
 if(out!=prior && !prev_fs)$fatal(1,"Snapshot changed outside frame boundary");
 if(out!=0 && out[31:0]!==~out[63:32])$fatal(1,"Torn snapshot");
 if(out!=prior)seen=seen+1;
end end
initial begin repeat(8)@(negedge s);r=1;
 for(i=0;i<5000;i=i+1)begin @(negedge p);fs=(i%97==0);end
 if(seen<40)$fatal(1,"CDC stopped updating");$display("PASS: coherent status CDC updates only on frame boundary, %0d snapshots",seen);$finish;end
endmodule
