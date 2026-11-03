// Passive nearest-neighbour640x480 ->256x192 tap on accepted sys-clock tokens.
// floor(dst*5/2) gives0,2,5,7,...; no upscale of the Locator input image.
`timescale 1ns/1ps
module preview_gray256(
 input wire clk,rst_n,valid,accept_sof,input wire[31:0]frame_id,
 input wire[7:0]gray,input wire[9:0]x,y,
 output reg we,output reg[13:0]addr,output reg[31:0]data,
 output reg published,output reg[31:0]published_id);
 reg active;reg[31:0]id,pack;reg[1:0]count;
 reg[9:0]next_x,next_y;reg xp,yp;reg[13:0]word_index;
 always @(posedge clk)begin
  if(!rst_n)begin active<=0;id<=0;pack<=0;count<=0;next_x<=0;next_y<=0;xp<=0;yp<=0;word_index<=0;we<=0;addr<=0;data<=0;published<=0;published_id<=0;end
  else begin
   we<=0;published<=0;
   if(accept_sof)begin
    active<=1;id<=frame_id;pack<={24'd0,gray};count<=1;
    next_x<=2;next_y<=0;xp<=1;yp<=0;word_index<=0;
   end else if(active && valid && x==next_x && y==next_y)begin
    case(count)0:pack[7:0]<=gray;1:pack[15:8]<=gray;2:pack[23:16]<=gray;default:pack[31:24]<=gray;endcase
    count<=count+1'b1;
    if(count==3)begin we<=1;addr<=word_index;data<={gray,pack[23:0]};word_index<=word_index+1'b1;end
    if(next_x==637)begin
     next_x<=0;xp<=0;next_y<=next_y+(yp?3:2);yp<=~yp;
     if(next_y==477)begin active<=0;published<=1;published_id<=id;end
    end else begin next_x<=next_x+(xp?3:2);xp<=~xp;end
   end
  end
 end
endmodule
