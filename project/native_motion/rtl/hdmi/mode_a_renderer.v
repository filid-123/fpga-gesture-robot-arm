// 640x480 presentation: one frame-matched box and three Chinese status cards.
`timescale 1ns/1ps
module mode_a_renderer #(parameter integer HD_PREVIEW=0,parameter integer PREMAPPED_SOURCE=0,parameter FONT_FILE="mode_a_font.mem")(
 input wire pixel_clk,rst_n,input wire [9:0] timing_x,timing_y,
 input wire timing_active,timing_hsync,timing_vsync,
 output wire [13:0] frame_word_addr,input wire [31:0] frame_word_data,
 input wire display_valid,display_detected,input wire [8:0] x0,y0,x1,y1,
 input wire [2:0] gesture,input wire gesture_valid,feedback_online,locator_fresh,
 input wire [31:0] task_status,interaction,
 input wire[7:0]metric_loc,metric_cls,metric_age,
 output reg [7:0] red,green,blue,output reg data_enable,hsync,vsync,
 input wire[7:0]mapped_source_x,mapped_source_y);
 `include "mode_a_ui_text.vh"
 reg [15:0] font[0:2047];initial $readmemh(FONT_FILE,font);
 wire inside_image=timing_x>=24 && timing_x<408 && timing_y>=100 && timing_y<388;
 wire [9:0] dx=timing_x-24,dy=timing_y-100;
 wire [7:0] sx=(PREMAPPED_SOURCE!=0)?mapped_source_x:((HD_PREVIEW!=0)?((dx*2)/3):(dx/3));
 wire [7:0] sy=(PREMAPPED_SOURCE!=0)?mapped_source_y:((HD_PREVIEW!=0)?((dy*2)/3):((dy/3)+16));
 assign frame_word_addr=(HD_PREVIEW!=0)?({sy,6'd0}+{8'd0,sx[7:2]}):({1'b0,sy,5'd0}+{8'd0,sx[7:2]});
 reg [5:0] gesture_msg,command_msg,state_msg;
 wire [3:0] state=task_status[3:0];wire [2:0] phase=task_status[6:4];
 always @*begin
  gesture_msg=5;
  if(gesture_valid)case(gesture)1:gesture_msg=6;2:gesture_msg=7;3:gesture_msg=8;4:gesture_msg=9;5:gesture_msg=10;default:gesture_msg=5;endcase
  command_msg=11;state_msg=22;
  if(state==0)begin command_msg=21;state_msg=33;end
  else if(state==10 || state==9)begin command_msg=20;state_msg=(state==10)?31:33;end
  else if(interaction[8] || state==8)begin command_msg=task_status[29]?45:18;state_msg=29;end
  else if(state==3 || state==2)begin command_msg=19;state_msg=32;end
  else if(state==6 || state==7)begin command_msg=15;state_msg=(state==6)?30:25;end
  else if(state==5)begin command_msg=15;state_msg=24;end
  else if(task_status[29])begin
   command_msg=task_status[19]?48:((task_status[21:20]==1)?38:((task_status[21:20]==2)?39:40));
   state_msg=task_status[10]?44:(task_status[9]?43:42);
  end else if(state==4)begin
   case(phase)
    1:begin command_msg=task_status[19]?47:((task_status[21:20]==1)?12:((task_status[21:20]==2)?13:14));state_msg=23;end
    2:begin command_msg=16;state_msg=26;end
    3:begin command_msg=17;state_msg=27;end
    4:begin command_msg=19;state_msg=28;end
    default:begin command_msg=15;state_msg=25;end
   endcase
  end
 end
 reg text_on,big;reg [5:0] message;reg [9:0] tx,ty;
 always @*begin
  text_on=0;big=0;message=0;tx=0;ty=0;
  if(timing_x>=24 && timing_x<216 && timing_y>=24 && timing_y<56)begin text_on=1;big=1;message=task_status[19]?46:0;tx=timing_x-24;ty=timing_y-24;end
  else if(timing_x>=24 && timing_x<344 && timing_y>=64 && timing_y<80)begin text_on=1;message=37;tx=timing_x-24;ty=timing_y-64;end
  else if(timing_x>=456 && timing_x<600 && timing_y>=40 && timing_y<56)begin text_on=1;message=feedback_online?34:35;tx=timing_x-456;ty=timing_y-40;end
  else if(timing_x>=448 && timing_x<608)begin
   if(timing_y>=112 && timing_y<128)begin text_on=1;message=2;tx=timing_x-448;ty=timing_y-112;end
   else if(timing_y>=140 && timing_y<172)begin text_on=1;big=1;message=gesture_msg;tx=timing_x-448;ty=timing_y-140;end
   else if(timing_y>=212 && timing_y<228)begin text_on=1;message=3;tx=timing_x-448;ty=timing_y-212;end
   else if(timing_y>=240 && timing_y<272)begin text_on=1;big=1;message=command_msg;tx=timing_x-448;ty=timing_y-240;end
   else if(timing_y>=312 && timing_y<328)begin text_on=1;message=4;tx=timing_x-448;ty=timing_y-312;end
   else if(timing_y>=340 && timing_y<372)begin text_on=1;big=1;message=state_msg;tx=timing_x-448;ty=timing_y-340;end
  end else if(timing_x>=24 && timing_x<408 && timing_y>=424 && timing_y<440)begin text_on=1;message=36;tx=timing_x-24;ty=timing_y-424;end
 end
 wire metric_line=(HD_PREVIEW!=0 && timing_y>=456 && timing_y<472 && timing_x>=24 && timing_x<616);
 wire [5:0] metric_column=(timing_x-24)>>4;
 wire [5:0] column=big?tx[9:5]:tx[9:4];
 reg [7:0] metric_glyph;reg[7:0]metric_value;reg[5:0]mc;
 always @*begin
  metric_glyph=0;metric_value=0;mc=metric_column;
  if(mc<11)begin metric_value=metric_loc;if(mc==0)metric_glyph=97;end
  else if(mc<22)begin mc=mc-11;metric_value=metric_cls;if(mc==0)metric_glyph=98;end
  else begin mc=mc-22;metric_value=metric_age;if(mc==0)metric_glyph=99;end
  if(mc==2)metric_glyph=87+metric_value/100;
  if(mc==3)metric_glyph=87+(metric_value/10)%10;
  if(mc==4)metric_glyph=87+metric_value%10;
  if(mc==5)metric_glyph=100;
  if(mc==6)metric_glyph=102;
 end
 wire [7:0] glyph=metric_line?metric_glyph:ui_character(message,column);
 wire [3:0] glyph_row=big?ty[4:1]:ty[3:0];
 reg [15:0] font_row;reg [3:0] font_column;
 reg [9:0] xd,yd;reg ad,hd,vd,imaged,textd,bigd;reg [1:0] byte_d;reg [7:0] sxd,syd;
 always @(posedge pixel_clk)begin
  if(!rst_n)begin font_row<=0;font_column<=0;xd<=0;yd<=0;ad<=0;hd<=1;vd<=1;imaged<=0;textd<=0;bigd<=0;byte_d<=0;sxd<=0;syd<=0;end
  else begin
   font_row<=font[{glyph[6:0],metric_line?timing_y[3:0]-4'd8:glyph_row}];font_column<=metric_line?(timing_x[3:0]-4'd8):(big?tx[4:1]:tx[3:0]);
   xd<=timing_x;yd<=timing_y;ad<=timing_active;hd<=timing_hsync;vd<=timing_vsync;
   imaged<=inside_image;byte_d<=sx[1:0];sxd<=sx;syd<=sy;textd<=text_on || metric_line;bigd<=big;
  end
 end
 wire [7:0] gray=frame_word_data[byte_d*8+:8];
 wire [8:0] left=(HD_PREVIEW!=0)?((x0>127)?255:(x0<<1)):((x0>127)?127:x0);
 wire [8:0] right=(HD_PREVIEW!=0)?((x1>=128)?255:((x1>0)?(x1<<1)-1:0)):((x1>=128)?127:((x1>0)?x1-1:0));
 wire [8:0] top=(HD_PREVIEW!=0)?((y0<16)?0:((y0-16)<<1)):((y0<16)?16:y0);
 wire [8:0] bottom=(HD_PREVIEW!=0)?((y1>112)?191:((y1>16)?((y1-16)<<1)-1:0)):((y1>112)?111:((y1>0)?y1-1:0));
 wire border=display_valid && display_detected && locator_fresh && left<=right && top<=bottom &&
  sxd>=left && sxd<=right && syd>=top && syd<=bottom &&
  (sxd==left || sxd==right || syd==top || syd==bottom);
 reg [23:0] rgb;
 always @*begin
  rgb=24'h0b1421;
  if(xd>=432 && xd<616 && ((yd>=100 && yd<188)||(yd>=200 && yd<288)||(yd>=300 && yd<388)))rgb=24'h172338;
  if(xd>=432 && xd<435 && yd>=100 && yd<188)rgb=24'h3cd6bc;
  if(xd>=432 && xd<435 && yd>=200 && yd<288)rgb=24'h68a7ff;
  if(xd>=432 && xd<435 && yd>=300 && yd<388)rgb=(state==10)?24'hff6b72:24'ha8b7cc;
  if(imaged)rgb=display_valid?{gray,gray,gray}:24'h172338;
  if(imaged && border)rgb=24'h3cd6bc;
  if(xd>=24 && xd<616 && yd==408)rgb=24'h253249;
  if(xd>=440 && xd<446 && yd>=44 && yd<50)rgb=feedback_online?24'h3cd6bc:24'hff6b72;
  if(textd && font_row[15-font_column])rgb=bigd?24'heef4fb:24'h9aacc5;
 end
 always @(posedge pixel_clk)begin
  if(!rst_n)begin red<=0;green<=0;blue<=0;data_enable<=0;hsync<=1;vsync<=1;end
  else begin {red,green,blue}<=ad?rgb:24'd0;data_enable<=ad;hsync<=hd;vsync<=vd;end
 end
endmodule
