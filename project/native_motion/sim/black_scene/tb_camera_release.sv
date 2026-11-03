`timescale 1ns/1ps
// Real registered frame-valid/release timing with short engine models. This
// tests scheduling/ownership, independently of the CNN arithmetic regressions.
module tb_camera_release;
 reg clk=0;always #5 clk=~clk;
 reg rst=0;reg[1:0]valid=0;reg latest=0;reg[31:0]fid0=0,fid1=0;
 reg[1:0]scenario=0;wire[1:0]release_mask;
 wire loc_start,bbox_start,roi_start,class_start,candidate,fatal;
 wire[31:0]job_fid;wire[2:0]candidate_class;
 reg loc_busy=0,loc_done=0,bbox_busy=0,bbox_done=0;
 reg roi_busy=0,roi_done=0,roi_error=0,class_busy=0,class_done=0;
 integer lc=0,bc=0,rc=0,cc=0,jobs=0,results=0,expected_jobs=1;
 reg[31:0]expected_fid[0:3];
 autonomous_pipeline_ctrl_7c #(.NUM_CLASSES(6),.TASK_CLASS_MAP(1)) dut(
  .clk(clk),.rst_n(rst),.camera_init_done(1'b1),.camera_init_error(1'b0),.fifo_overflow(1'b0),
  .camera_buffer_valid(valid),.camera_latest_buffer(latest),.camera_frame_id_0(fid0),.camera_frame_id_1(fid1),
  .camera_buffer_release(release_mask),.locator_busy(loc_busy),.locator_done(loc_done),
  .locator_start(loc_start),.locator_frame_id(job_fid),
  .top1_cell(32'd0),.top1_confidence(32'd0),.top1_dx(32'd0),.top1_dy(32'd0),.top1_width(32'd0),.top1_height(32'd0),
  .bbox_start(bbox_start),.bbox_busy(bbox_busy),.bbox_done(bbox_done),.bbox_detected(scenario!=0),
  .bbox_roi_x0(10'd0),.bbox_roi_y0(10'd0),.bbox_roi_side(10'd32),
  .roi_start(roi_start),.roi_busy(roi_busy),.roi_done(roi_done),.roi_error(roi_error),
  .classifier_request(class_start),.classifier_request_busy(class_busy),
  .classifier_result_pulse(class_done),.classifier_result_class(9'd4),.classifier_result_margin(16'd123),
  .class_candidate_valid(candidate),.class_candidate(candidate_class),.fatal_error(fatal));
 always @(posedge clk)begin
  if(!rst)begin
   valid<=0;lc<=0;bc<=0;rc<=0;cc<=0;jobs<=0;results<=0;
   loc_busy<=0;loc_done<=0;bbox_busy<=0;bbox_done<=0;
   roi_busy<=0;roi_done<=0;roi_error<=0;class_busy<=0;class_done<=0;
  end else begin
   valid<=valid&~release_mask;
   loc_done<=0;bbox_done<=0;roi_done<=0;roi_error<=0;class_done<=0;
   if(loc_start)begin
    if(jobs>=expected_jobs || job_fid!==expected_fid[jobs])
     $fatal(1,"FAIL: CAMERA_RELEASE duplicate/unexpected job=%0d fid=%0d",jobs,job_fid);
    jobs<=jobs+1;loc_busy<=1;lc<=3;
   end else if(lc>0)begin lc<=lc-1;if(lc==1)begin loc_busy<=0;loc_done<=1;end end
   if(bbox_start)begin bbox_busy<=1;bc<=2;end
   else if(bc>0)begin bc<=bc-1;if(bc==1)begin bbox_busy<=0;bbox_done<=1;end end
   if(roi_start)begin roi_busy<=1;rc<=3;end
   else if(rc>0)begin rc<=rc-1;if(rc==1)begin roi_busy<=0;
    if(scenario==1)roi_error<=1;else roi_done<=1;end end
   if(class_start)begin class_busy<=1;cc<=8;end
   else if(cc>0)begin cc<=cc-1;if(cc==1)begin class_busy<=0;class_done<=1;end end
   if(candidate)begin
    results<=results+1;
    if(candidate_class!==((scenario==2)?3'd5:3'd7))$fatal(1,"FAIL: CAMERA_RELEASE candidate mapping");
   end
   if(fatal)$fatal(1,"FAIL: CAMERA_RELEASE fatal");
  end
 end
 task reset_case(input[1:0]kind,input integer count);begin
  @(negedge clk);rst=0;scenario=kind;expected_jobs=count;
  repeat(4)@(negedge clk);rst=1;repeat(4)@(negedge clk);
 end endtask
 task finish_case(input integer count);integer timeout;begin
  timeout=0;
  while(results<count && timeout<200)begin @(negedge clk);timeout=timeout+1;end
  repeat(30)@(negedge clk);
  if(results!=count || jobs!=count || valid!=0 || loc_busy || roi_busy || class_busy)
   $fatal(1,"FAIL: CAMERA_RELEASE completion jobs=%0d results=%0d valid=%b",jobs,results,valid);
 end endtask
 initial begin
  reset_case(0,1);fid0=11;expected_fid[0]=11;valid=1;finish_case(1);
  $display("PASS: CAMERA_RELEASE locator miss consumes source frame once");
  reset_case(1,1);fid0=12;expected_fid[0]=12;valid=1;finish_case(1);
  $display("PASS: CAMERA_RELEASE ROI error consumes source frame once");
  reset_case(2,2);fid0=13;expected_fid[0]=13;expected_fid[1]=14;valid=1;
  wait(class_busy);@(negedge clk);fid0=14;valid=1;
  if(jobs!=1)$fatal(1,"FAIL: CAMERA_RELEASE new LOC before previous CLASS completed");
  finish_case(2);
  $display("PASS: CAMERA_RELEASE ROI/classifier permits next captured frame, no duplicate IDs");
  reset_case(0,1);fid0=20;fid1=21;latest=1;expected_fid[0]=21;valid=3;finish_case(1);
  $display("PASS: CAMERA_RELEASE ping-pong stale buffer discard and selected buffer release");
  $display("PASS: CAMERA_RELEASE registered source ownership regression");$finish;
 end
endmodule
