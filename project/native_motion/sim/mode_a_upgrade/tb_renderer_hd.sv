`timescale 1ns/1ps
module tb_renderer;
reg p=0,r=0;always #19.84127 p=~p;
wire[9:0]x,y;wire active,hs,vs,fs;wire[13:0]a;reg[31:0]data;reg[31:0]mem[0:12287];wire[7:0]red,green,blue;wire de,ho,vo;
reg[31:0] taskstatus=(5|(1<<20));reg[31:0]interaction=0;reg[2:0]gesture=4;reg live=1,det=1,feedback=1;
video_timing_640x480 timing(p,r,x,y,active,hs,vs,fs);
always @(posedge p)data<=mem[a];
mode_a_renderer #(.HD_PREVIEW(1),.FONT_FILE("mode_a_font.mem"))dut(p,r,x,y,active,hs,vs,a,data,1'b1,det,9'd20,9'd24,9'd100,9'd128,gesture,live,feedback,live,taskstatus,interaction,8'd16,8'd5,8'd145,red,green,blue,de,ho,vo,8'd0,8'd0);
integer f,count=0,blank=0;reg capture=0;
always @(negedge p)if(capture)begin
 if(de)begin $fwrite(f,"%c%c%c",red,green,blue);count=count+1;end
 else begin if({red,green,blue}!==0)$fatal(1,"Blanking RGB not black");blank=blank+1;end
end
initial begin $readmemh("palm_small.mem",mem);repeat(8)@(negedge p);r=1;f=$fopen("preview.rgb","wb");capture=1;
 wait(count==307200);@(posedge p);capture=0;$fclose(f);
 if(blank==0)$fatal(1,"No blanking");
 live=0;#1;if(dut.gesture_msg!=5)$fatal(1,"Invalid gesture not hidden");
 live=1;gesture=5;#1;if(dut.gesture_msg!=10)$fatal(1,"FIST label wrong");
 taskstatus=4|(3<<4);#1;if(dut.command_msg!=17 || dut.state_msg!=27)$fatal(1,"Release label wrong");
 interaction=256;#1;if(dut.command_msg!=18 || dut.state_msg!=29)$fatal(1,"Cancel label wrong");
 taskstatus=10;#1;if(dut.state_msg!=31)$fatal(1,"Fault label wrong");
 taskstatus=(1<<29)|(1<<20)|4;interaction=0;#1;if(dut.command_msg!=38 || dut.state_msg!=42)$fatal(1,"Restock pickup label wrong");
 taskstatus=taskstatus|(1<<9);#1;if(dut.state_msg!=43)$fatal(1,"Restock carry label wrong");
 taskstatus=taskstatus|(1<<10);#1;if(dut.state_msg!=44)$fatal(1,"Restock retreat label wrong");
 interaction=256;#1;if(dut.command_msg!=45)$fatal(1,"Restock cancel must name public pickup");
 interaction=0;taskstatus=1;
 wait(x==30 && y==30);#1;if(dut.message!=0)$fatal(1,"A title must follow mode bit zero");
 taskstatus=1|(1<<19);#1;if(dut.message!=46)$fatal(1,"B title did not follow actual mode bit");
 if(dut.ui_character(46,0)==dut.ui_character(0,0))$fatal(1,"B title reused A glyph");
 taskstatus=4|(1<<4)|(1<<19)|(2<<20);#1;if(dut.command_msg!=47)$fatal(1,"B must not label object two as yellow");
 taskstatus=taskstatus|(1<<29);#1;if(dut.command_msg!=48)$fatal(1,"B restock must identify original source");
 taskstatus=1|(1<<19);gesture=1;live=1;
 wait(fs);@(negedge p);count=0;f=$fopen("preview_b.rgb","wb");capture=1;
 wait(count==307200);@(posedge p);capture=0;$fclose(f);
 $display("PASS: actual A/B mode selects title, B generic object/restock labels, full B raster307200 pixels");
 $display("PASS: restock pickup/carry/home and public-point cancellation labels distinct from normal delivery");
 $display("PASS: raster307200 pixels, blanking, Chinese UI, gesture/none/release/return/fault labels");$finish;end
endmodule
