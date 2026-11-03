`timescale 1ns/1ps
module tb_preview256;
reg clk=0,rst=0;always #5 clk=~clk;
reg v=0,sof=0;reg[7:0]gray=0;reg[9:0]x=0,y=0;reg[1:0]release_mask=0;
wire ready,accept,pub,hdwe,hdpub;wire[31:0]fid,hddata,hdid;wire[13:0]ha;wire lwe;wire[12:0]la;wire[31:0]ld;wire[1:0]valids;
pl_letterbox_640x480 box(.clk(clk),.rst_n(rst),.pixel_valid(v),.pixel_ready(ready),.pixel_data(gray),.pixel_x(x),.pixel_y(y),.pixel_sof(sof),.buffer_release(release_mask),.buffer_valid_mask(valids),.preview_accept_sof(accept),.preview_frame_id(fid),.mem_we(lwe),.mem_word_addr(la),.mem_wdata(ld));
preview_gray256 hd(clk,rst,v&&ready,accept,fid,gray,x,y,hdwe,ha,hddata,hdpub,hdid);
integer xx,yy,fr,hwords=0,lwords=0,hframes=0;reg[31:0]expected;integer px,py;
function[7:0] value(input integer ax,ay);value=(ax*3+ay*7)&255;endfunction
always @(negedge clk)if(rst)begin
 if(hdwe)begin
  for(integer j=0;j<4;j=j+1)begin px=((ha%64)*4+j)*5/2;py=(ha/64)*5/2;expected[j*8+:8]=value(px,py);end
  if(ha!=(hwords%12288) || hddata!==expected)$fatal(1,"HD sample/packing/address mismatch %0d",ha);hwords=hwords+1;
 end
 if(lwe)begin
  for(integer j=0;j<4;j=j+1)expected[j*8+:8]=(la[11:0]<512 || la[11:0]>=3584)?0:value(((la%32)*4+j)*5,((la%4096)/32-16)*5);
  if(ld!==expected)$fatal(1,"Locator preprocessing altered %0d",la);lwords=lwords+1;
 end
 if(hdpub)begin if(hdid!=hframes)$fatal(1,"HD frame ID mismatch");hframes=hframes+1;end
end
initial begin repeat(8)@(negedge clk);rst=1;
 for(fr=0;fr<3;fr=fr+1)begin
  for(yy=0;yy<480;yy=yy+1)for(xx=0;xx<640;xx=xx+1)begin
   @(negedge clk);v=1;sof=(xx==0 && yy==0);x=xx;y=yy;gray=value(xx,yy);
   @(posedge clk);while(!ready)@(posedge clk);
  end
  @(negedge clk);v=0;sof=0;repeat(1024)@(negedge clk);
 end
 if(hframes!=2 || hwords!=24576 || lwords!=8192 || valids!=3)$fatal(1,"Frame/drop counts %0d %0d %0d",hframes,hwords,lwords);
 $display("PASS: 256x192 exact nearest source samples/12288-word packing, frame IDs, full-buffer drop; original Locator128x128 unchanged");$finish;
end
endmodule
