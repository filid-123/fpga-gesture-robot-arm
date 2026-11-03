// Coherent latest snapshot. Source holds payload until a frame-boundary ack.
`timescale 1ns/1ps
module mode_a_display_cdc #(parameter WIDTH=72)(
 input wire sys_clk,sys_rst_n,input wire [WIDTH-1:0] source_data,
 input wire pixel_clk,pixel_rst_n,frame_start,output reg [WIDTH-1:0] display_data);
 reg [WIDTH-1:0] held;reg request;reg acknowledge;
 (* ASYNC_REG="TRUE" *) reg ack1,ack2,req1,req2;
 (* ASYNC_REG="TRUE" *) reg [WIDTH-1:0] data1,data2;
 always @(posedge sys_clk)begin
  if(!sys_rst_n)begin held<=0;request<=0;ack1<=0;ack2<=0;end
  else begin ack1<=acknowledge;ack2<=ack1;
   if(ack2==request)begin held<=source_data;request<=~request;end
  end
 end
 always @(posedge pixel_clk)begin
  if(!pixel_rst_n)begin acknowledge<=0;req1<=0;req2<=0;data1<=0;data2<=0;display_data<=0;end
  else begin req1<=request;req2<=req1;data1<=held;data2<=data1;
   if(frame_start && req2!=acknowledge)begin display_data<=data2;acknowledge<=req2;end
  end
 end
endmodule
