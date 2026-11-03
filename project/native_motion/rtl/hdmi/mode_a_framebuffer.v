// Four private Gray8 banks mirror camera writes, without camera backpressure.
// Three non-displayed banks tolerate the overlapped two-frame inference path.
// Only a complete image with exactly matching inference frame_id is published.
`timescale 1ns/1ps
module mode_a_framebuffer #(parameter integer FRAME_WORDS=4096)(
 input wire sys_clk,sys_rst_n,camera_we,input wire [13:0] camera_word_addr,
 input wire [31:0] camera_wdata,input wire camera_frame_published,
 input wire [31:0] camera_latest_frame_id,input wire result_valid,
 input wire [31:0] result_frame_id,input wire result_detected,
 input wire [8:0] box_x0,box_y0,box_x1,box_y1,
 input wire pixel_clk,pixel_rst_n,frame_start,input wire [13:0] read_addr,
 output wire [31:0] read_data,output reg display_valid,display_detected,
 output reg [8:0] x0,y0,x1,y1,output reg [31:0] display_frame_id);
 localparam AW=(FRAME_WORDS==12288)?14:12;
 reg capture;reg [1:0] cap_bank,displayed,round_robin;
 reg [3:0] complete;reg [31:0] ids[0:3];
 reg request,pending,acknowledge;reg [1:0] requested_bank;
 reg [70:0] payload;
 (* ASYNC_REG="TRUE" *) reg ack1,ack2,req1,req2;
 (* ASYNC_REG="TRUE" *) reg [70:0] data1,data2;
 reg [1:0] read_bank;
 integer k,idx,nfree,nmatch;reg found;reg [1:0] free_bank;
 always @*begin
  found=0;free_bank=0;
  for(nfree=0;nfree<4;nfree=nfree+1)begin
   idx=(round_robin+nfree)&3;
   if(!found && idx!=displayed && !(pending && idx==requested_bank))begin found=1;free_bank=idx;end
  end
 end
 wire first_word=camera_we && camera_word_addr[AW-1:0]==0;
 wire start_capture=first_word && !capture && found;
 wire write_enable=camera_we && (capture || start_capture);
 wire [1:0] write_bank=capture?cap_bank:free_bank;
 wire [31:0] words[0:3];genvar b,g;reg[1:0]read_part;
 always @(posedge pixel_clk)read_part<=read_addr[13:12];
 generate for(b=0;b<4;b=b+1)begin:banks
  wire[31:0]part[0:FRAME_WORDS/4096-1];
  for(g=0;g<FRAME_WORDS/4096;g=g+1)begin:parts
   hdmi_frame_bram ram(.write_clk(sys_clk),.write_enable(write_enable && write_bank==b && ((FRAME_WORDS==4096) || camera_word_addr[13:12]==g)),
    .write_addr(camera_word_addr[11:0]),.write_data(camera_wdata),.read_clk(pixel_clk),.read_addr(read_addr[11:0]),.read_data(part[g]));
  end
  if(FRAME_WORDS==4096)assign words[b]=part[0];
  else assign words[b]=(read_part==0)?part[0]:((read_part==1)?part[1]:part[2]);
 end endgenerate
 assign read_data=words[read_bank];
 reg match_found;reg [1:0] match_bank;
 always @*begin
  match_found=0;match_bank=0;
  for(nmatch=0;nmatch<4;nmatch=nmatch+1)begin
   if(complete[nmatch] && ids[nmatch]==result_frame_id && nmatch!=displayed &&
      !(capture && nmatch==cap_bank) && !(start_capture && nmatch==free_bank))begin
    match_found=1;match_bank=nmatch;
   end
  end
 end
 always @(posedge sys_clk)begin
  if(!sys_rst_n)begin
   capture<=0;cap_bank<=0;displayed<=0;round_robin<=1;complete<=0;
   request<=0;pending<=0;ack1<=0;ack2<=0;requested_bank<=0;payload<=0;
   for(k=0;k<4;k=k+1)ids[k]<=0;
  end else begin
   ack1<=acknowledge;ack2<=ack1;
   if(start_capture)begin capture<=1;cap_bank<=free_bank;complete[free_bank]<=0;round_robin<=free_bank+1'b1;end
   if(camera_frame_published && capture)begin capture<=0;complete[cap_bank]<=1;ids[cap_bank]<=camera_latest_frame_id;end
   if(result_valid && match_found && !pending)begin
    requested_bank<=match_bank;
    payload<={match_bank,result_detected,box_x0,box_y0,box_x1,box_y1,result_frame_id};
    pending<=1;request<=~request;
   end
   if(pending && ack2==request)begin pending<=0;displayed<=requested_bank;end
  end
 end
 always @(posedge pixel_clk)begin
  if(!pixel_rst_n)begin
   req1<=0;req2<=0;data1<=0;data2<=0;acknowledge<=0;read_bank<=0;
   display_valid<=0;display_detected<=0;x0<=0;y0<=0;x1<=0;y1<=0;display_frame_id<=0;
  end else begin
   req1<=request;req2<=req1;data1<=payload;data2<=data1;
   if(frame_start && req2!=acknowledge)begin
    {read_bank,display_detected,x0,y0,x1,y1,display_frame_id}<=data2;
    display_valid<=1;acknowledge<=req2;
   end
  end
 end
endmodule
