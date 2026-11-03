`timescale 1ns/1ps
module tb_phase2_frontend;
reg clk=0,pclk=0,rst=0,href=0,vsync=1;reg[7:0]data=0;reg[1:0]release_mask=0;
always #5 clk=~clk;integer half_ps=10417,scenario=0;
initial begin if($value$plusargs("HALF_PS=%d",half_ps))begin end forever #(half_ps/1000.0)pclk=~pclk;end
wire[1:0]valid;wire[31:0]id0,id1,latest_id,t0,t1,now_ms,drop,fmt;
wire pub,latest,we,overflow;wire[12:0]addr;wire[31:0]word;
ov5640_phase2_frontend dut(.pclk(pclk),.pclk_rst_n(rst),.dvp_data(data),.dvp_href(href),.dvp_vsync(vsync),.capture_enable(1'b1),
.sys_clk(clk),.sys_rst_n(rst),.buffer_release(release_mask),.buffer_valid_mask(valid),.buffer_frame_id_0(id0),.buffer_frame_id_1(id1),
.frame_published(pub),.latest_buffer_id(latest),.latest_frame_id(latest_id),.mem_we(we),.mem_word_addr(addr),.mem_wdata(word),
.buffer_timestamp_ms_0(t0),.buffer_timestamp_ms_1(t1),.now_ms(now_ms),.frame_drop_count(drop),.format_error_count(fmt),.fifo_overflow_sticky(overflow));
wire lr,lpub,ll,lwe;wire[1:0]lv;wire[31:0]li0,li1,llid,lword,ldrop,lfmt;wire[12:0]la;
legacy_letterbox_640x480 legacy(.clk(clk),.rst_n(rst),.pixel_valid(dut.token_valid),.pixel_ready(lr),
.pixel_data(dut.token_data[7:0]),.pixel_x(dut.token_data[17:8]),.pixel_y(dut.token_data[27:18]),.pixel_sof(dut.token_data[28]),
.buffer_release(release_mask),.buffer_valid_mask(lv),.buffer_frame_id_0(li0),.buffer_frame_id_1(li1),.frame_published(lpub),
.latest_buffer_id(ll),.latest_frame_id(llid),.mem_we(lwe),.mem_word_addr(la),.mem_wdata(lword),.frame_drop_count(ldrop),.format_error_count(lfmt));
integer frame=0,writes=0,pubs=0,px,py,x,y,k;reg[31:0]expected,saved_t0,saved_t1;reg[7:0]b;
function[7:0]pixel(input integer xx,yy,ff);pixel=(xx+3*yy+17*ff)&255;endfunction
always @(negedge clk)if(rst)begin
 if({dut.token_ready,valid,id0,id1,pub,latest,latest_id,we,addr,word,drop,fmt}!=={lr,lv,li0,li1,lpub,ll,llid,lwe,la,lword,ldrop,lfmt})
  $fatal(1,"FAIL: timestamp extension changed frozen Phase2 decisions");
 if(scenario==3 && overflow)begin $display("PASS: PHASE2_FRONTEND above-contract 71MHz input reports sticky overflow; no silent pass");$finish;end
 if(overflow||fmt)$fatal(1,"FAIL: Phase2 legal/extra-tail input overflow or format");
 if(we)begin
  if(addr[11:0]!==writes[11:0])$fatal(1,"FAIL: small-buffer word order");
  expected=0;
  for(k=0;k<4;k=k+1)begin px=(addr[4:0]*4+k)*5;py=(addr[11:5]-16)*5;
   if(addr[11:5]>=16 && addr[11:5]<112)b=pixel(px,py,frame);else b=0;expected=expected|({24'd0,b}<<(8*k));end
  if(word!==expected)$fatal(1,"FAIL: independent letterbox pixel word=%0d",addr);
  writes=writes+1;
 end
 if(pub)begin pubs=pubs+1;if(writes!=4096)$fatal(1,"FAIL: incomplete image");end
end
task send_frame(input integer ff);begin
 frame=ff;writes=0;vsync=1;repeat(8)@(negedge pclk);vsync=0;repeat(8)@(negedge pclk);
 for(y=0;y<480;y=y+1)begin @(negedge pclk);href=1;
  for(x=0;x<640;x=x+1)begin data=pixel(x,y,ff);@(negedge pclk);data=128;@(negedge pclk);end
  if(y==94)for(x=0;x<scenario;x=x+1)begin data=77;@(negedge pclk);end
  href=0;repeat(20)@(negedge pclk);
 end
 repeat(100)@(negedge clk);
end endtask
initial begin
 if($value$plusargs("CASE=%d",scenario))begin end
 repeat(20)@(negedge clk);rst=1;repeat(100100)@(negedge clk);
 send_frame(0);if(valid!=1||id0!=0||t0==0||t0>=now_ms)$fatal(1,"FAIL: bank0 valid/id/acquisition");saved_t0=t0;
 send_frame(1);if(valid!=3||id1!=1||t0!=saved_t0||t1<=t0)$fatal(1,"FAIL: bank1 identity/timestamps");saved_t1=t1;
 send_frame(2);if(valid!=3||writes!=0||drop!=1||t0!=saved_t0||t1!=saved_t1)$fatal(1,"FAIL: held ownership changed");
 release_mask=1;@(negedge clk);release_mask=0;repeat(3)@(negedge clk);
 send_frame(3);if(valid!=3||id0!=2||t0<=saved_t1||t1!=saved_t1||pubs!=3)$fatal(1,"FAIL: released bank not reused safely");
 $display("PASS: PHASE2_FRONTEND full DVP/FIFO three publications/12288 exact words/dual-bank ownership/timestamps/frozen-cycle equivalence extra_bytes=%0d half_ps=%0d",scenario,half_ps);$finish;
end
initial begin #200000000;$fatal(1,"FAIL: frontend timeout");end
endmodule
