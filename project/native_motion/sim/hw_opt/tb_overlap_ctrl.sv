`timescale 1ns/1ps
module tb_overlap_ctrl;
 reg clk=0;always #5 clk=~clk;
 reg rst=0,pause_new=0,init_error=0;
 reg[1:0]cam_valid=0;reg latest=0;
 reg[31:0]fid0=0,fid1=0,ts0=0,ts1=0;
 wire[1:0]release_mask;wire capture,idle,fatal;
 wire loc_start,loc_buffer,box_start,roi_start,roi_buffer,wr_bank,cls_start,rd_bank;
 wire[31:0]loc_id,loc_ts,roi_tag,result_id,result_ts;
 wire[9:0]roi_x,roi_y,roi_side,result_rx,result_ry,result_rs;
 reg loc_busy=0,loc_done=0,box_busy=0,box_done=0,roi_busy=0,roi_done=0,roi_error=0;
 reg cls_busy=0,cls_done=0;reg[8:0]cls_code=0;reg[15:0]cls_margin=0;
 wire valid,det;wire[2:0]candidate,model;wire[15:0]margin;
 wire[8:0]raw_x,raw_y,raw_x1,raw_y1,ema_x,ema_y,ema_x1,ema_y1;
 wire signed[31:0]result_conf;
 wire[8:0]x=loc_id[8:0],y=x+9'd1,x1=x+9'd2,y1=x+9'd3;
 wire[8:0]ex=x+9'd4,ey=x+9'd5,ex1=x+9'd6,ey1=x+9'd7;
 wire[9:0]bx=loc_id[9:0]<<1,by=bx+10'd1;
 wire signed[31:0]confidence=32'd1000+loc_id;
 autonomous_overlap_ctrl dut(
 .clk(clk),.rst_n(rst),.camera_init_done(1'b1),.camera_init_error(init_error),.fifo_overflow(1'b0),.pause_new_jobs(pause_new),
 .camera_buffer_valid(cam_valid),.camera_latest_buffer(latest),.camera_frame_id_0(fid0),.camera_frame_id_1(fid1),
 .camera_timestamp_0(ts0),.camera_timestamp_1(ts1),.capture_enable(capture),.camera_buffer_release(release_mask),
 .locator_busy(loc_busy),.locator_done(loc_done),.locator_start(loc_start),.locator_input_buffer(loc_buffer),
 .locator_frame_id(loc_id),.locator_timestamp_ms(loc_ts),.top1_cell(loc_id),.top1_confidence(confidence),
 .top1_dx(32'sd0),.top1_dy(32'sd0),.top1_width(32'sd1),.top1_height(32'sd1),
 .bbox_start(box_start),.bbox_busy(box_busy),.bbox_done(box_done),.bbox_detected(loc_id!=13),
 .bbox_cell(),.bbox_confidence(),.bbox_dx(),.bbox_dy(),.bbox_width(),.bbox_height(),
 .bbox_roi_x0(bx),.bbox_roi_y0(by),.bbox_roi_side(10'd9),
 .bbox_raw_x0(x),.bbox_raw_y0(y),.bbox_raw_x1(x1),.bbox_raw_y1(y1),
 .bbox_ema_x0(ex),.bbox_ema_y0(ey),.bbox_ema_x1(ex1),.bbox_ema_y1(ey1),
 .roi_busy(roi_busy),.roi_done(roi_done),.roi_error(roi_error),.roi_start(roi_start),.roi_buffer_id(roi_buffer),
 .roi_write_bank(wr_bank),.roi_x0(roi_x),.roi_y0(roi_y),.roi_side(roi_side),.roi_tag(roi_tag),
 .classifier_request_busy(cls_busy),.classifier_result_pulse(cls_done),.classifier_request(cls_start),
 .classifier_read_bank(rd_bank),.classifier_result_class(cls_code),.classifier_result_margin(cls_margin),
 .class_candidate_valid(valid),.class_candidate(candidate),.result_model_class(model),.class_candidate_margin(margin),
 .result_frame_id(result_id),.result_timestamp_ms(result_ts),.result_detected(det),
 .result_raw_x0(raw_x),.result_raw_y0(raw_y),.result_raw_x1(raw_x1),.result_raw_y1(raw_y1),
 .result_ema_x0(ema_x),.result_ema_y0(ema_y),.result_ema_x1(ema_x1),.result_ema_y1(ema_y1),
 .result_roi_x0(result_rx),.result_roi_y0(result_ry),.result_roi_side(result_rs),.result_confidence(result_conf),
 .fatal_error(fatal),.pipeline_idle(idle),.state_debug());
 integer lc=0,bc=0,rc=0,cc=0,results=0,overlaps=0,cycles=0;
 reg[31:0]bank_tag[0:1];reg[31:0]class_tag=0;reg class_bank=0;
 always @(posedge clk)if(!rst)begin
  loc_busy<=0;loc_done<=0;box_busy<=0;box_done<=0;roi_busy<=0;roi_done<=0;roi_error<=0;
  cls_busy<=0;cls_done<=0;lc<=0;bc<=0;rc<=0;cc<=0;
 end else begin
  cam_valid<=cam_valid & ~release_mask;
  loc_done<=0;box_done<=0;roi_done<=0;roi_error<=0;cls_done<=0;
  if(loc_start)begin
   if(loc_busy || pause_new)$fatal(1,"FAIL: illegal front-end start");
   loc_busy<=1;lc<=2;if(cls_busy)overlaps<=overlaps+1;
  end else if(lc!=0)begin lc<=lc-1;if(lc==1)begin loc_busy<=0;loc_done<=1;end end
  if(box_start)begin box_busy<=1;bc<=2;end
  else if(bc!=0)begin bc<=bc-1;if(bc==1)begin box_busy<=0;box_done<=1;end end
  if(roi_start)begin
   if(cls_busy && wr_bank==class_bank)$fatal(1,"FAIL: ROI overwrites active classifier bank");
   if(roi_tag!=loc_id || roi_x!=bx || roi_y!=by || roi_side!=9)$fatal(1,"FAIL: ROI descriptor identity");
   roi_busy<=1;rc<=2;
  end else if(rc!=0)begin rc<=rc-1;if(rc==1)begin
   roi_busy<=0;roi_done<=1;roi_error<=roi_tag==14;bank_tag[wr_bank]<=roi_tag;
  end end
  if(cls_start)begin
   if(cls_busy)$fatal(1,"FAIL: classifier reentered");
   class_tag<=bank_tag[rd_bank];class_bank<=rd_bank;cls_busy<=1;
   cc<=bank_tag[rd_bank]==10?50:25;
  end else if(cc!=0)begin
   if(rd_bank!=class_bank)$fatal(1,"FAIL: classifier read bank changed while active");
   cc<=cc-1;if(cc==1)begin
    cls_busy<=0;cls_done<=1;cls_margin<=700+class_tag;
    case(class_tag)10:cls_code<=1;11:cls_code<=5;12:cls_code<=4;default:cls_code<=0;endcase
   end
  end
 end
 always @(negedge clk)if(rst)begin
  cycles=cycles+1;if(cycles>2000)$fatal(1,"FAIL: overlap timeout");
  if(dut.job_count>2)$fatal(1,"FAIL: job credit overflow");
  if(valid)begin
   if(result_id!=10+results || result_ts!=result_id*10+5)$fatal(1,"FAIL: result order/time id=%0d index=%0d",result_id,results);
   if(raw_x!=result_id || raw_y!=result_id+1 || raw_x1!=result_id+2 || raw_y1!=result_id+3 ||
      ema_x!=result_id+4 || ema_y!=result_id+5 || ema_x1!=result_id+6 || ema_y1!=result_id+7 ||
      result_conf!=1000+result_id || result_rx!=result_id*2 || result_ry!=result_id*2+1 || result_rs!=9)
     $fatal(1,"FAIL: metadata mixed across overlapping frames");
   case(result_id)
    10:if(candidate!=1 || model!=1)$fatal(1,"FAIL: object mapping");
    11:if(candidate!=4 || model!=5)$fatal(1,"FAIL: PALM mapping");
    12:if(candidate!=5 || model!=4)$fatal(1,"FAIL: FIST mapping");
    13,14:if(candidate!=7 || model!=7 || margin!=0)$fatal(1,"FAIL: ordered miss/error");
   endcase
   if(result_id<13 && margin!=700+result_id)$fatal(1,"FAIL: margin identity");
   if(det!==(result_id!=13))$fatal(1,"FAIL: detection identity");
   results=results+1;
  end
 end
 task publish(input bit bank,input[31:0]fid);
 begin
  while(cam_valid[bank])@(negedge clk);
  @(negedge clk);cam_valid[bank]=1;latest=bank;
  if(bank)begin fid1=fid;ts1=fid*10+5;end else begin fid0=fid;ts0=fid*10+5;end
 end endtask
 task accepted(input[31:0]fid);
 begin while(!(loc_start && loc_id==fid))@(negedge clk);end endtask
 initial begin
  repeat(4)@(negedge clk);rst=1;
  publish(0,10);accepted(10);wait(cls_busy);
  publish(1,11);accepted(11);
  @(negedge clk);pause_new=1;publish(0,12);
  wait(idle);repeat(8)@(negedge clk);
  if(results!=2 || !cam_valid[0])$fatal(1,"FAIL: snapshot pause/drain contract");
  pause_new=0;accepted(12);
  publish(1,13);accepted(13);publish(0,14);accepted(14);
  wait(results==5);wait(idle);repeat(3)@(negedge clk);
  if(overlaps<1)$fatal(1,"FAIL: no actual LOC/classifier overlap");
  publish(1,15);accepted(15);@(negedge clk);init_error=1;
  repeat(5)@(negedge clk);
  if(!fatal || capture || valid)$fatal(1,"FAIL: fatal did not inhibit publication/capture");
  rst=0;init_error=0;cam_valid=0;repeat(3)@(negedge clk);rst=1;repeat(12)@(negedge clk);
  if(!idle || fatal || valid || cls_start || loc_start)$fatal(1,"FAIL: reset retained a stale job");
  $display("PASS: OVERLAP ordered five results/identity/2slot ownership/miss/ROIerror/snapshot drain/fatal/reset overlaps=%0d",overlaps);
  $finish;
 end
endmodule

module tb_roi_pingpong;
 reg clk=0;always #5 clk=~clk;
 reg we=0,wb=0,re=0,rb=0;reg[7:0]wa=0;reg[9:0]ra=0;reg[31:0]wd=0;wire[7:0]rd;
 integer bank,k,b;
 classifier_roi_pingpong dut(.clk(clk),.wr_en(we),.wr_bank(wb),.wr_word_addr(wa),.wr_data(wd),
 .rd_en(re),.rd_bank(rb),.rd_byte_addr(ra),.rd_data(rd));
 function[31:0]pattern(input bit bank,input integer word_index);
 begin pattern={8'(word_index+3+bank*71),8'(word_index+2+bank*71),8'(word_index+1+bank*71),8'(word_index+bank*71)};end endfunction
 initial begin
  for(bank=0;bank<2;bank=bank+1)for(k=0;k<256;k=k+1)begin
   @(negedge clk);we=1;wb=bank;wa=k;wd=pattern(bank,k);
  end
  @(negedge clk);we=0;
  for(bank=0;bank<2;bank=bank+1)for(k=0;k<1024;k=k+1)begin
   @(negedge clk);re=1;rb=bank;ra=k;
   // Simultaneously rewrite the other bank, never the reader's bank.
   we=1;wb=!bank;wa=k/4;wd=pattern(!bank,k/4);
   @(negedge clk);#1;
   if(rd!==8'((k/4)+(k%4)+bank*71))$fatal(1,"FAIL: ROI bank/lane address=%0d/%0d",bank,k);
  end
  $display("PASS: ROI_PINGPONG all 2048 bytes and independent simultaneous bank access");$finish;
 end
endmodule
