`timescale 1ns/1ps
// Synthetic pixel cells and path indices only. No real robot calibration.
module tb_hand_align_exp;
 reg clk=0;always #5 clk=~clk;
 reg rst=0,active=0,waiting=1,cancel=0,fault=0;
 reg cw=0,commit=0;reg[3:0]cell_index=0;reg[1:0]word_index=0;reg[31:0]data=0;
 reg[15:0]mask=1;reg[31:0]revision=32'h1234;
 wire cfg_ready,cfg_error,committed;wire[3:0]cfg_error_code;
 reg req=0;reg[8:0]x=20,y=40;reg[31:0]fid=0,ts=0,now_ms=0;reg[2:0]cls=1;
 wire response,mapped;wire[3:0]mc;wire[41:0]mb;wire[31:0]mf,mt,mr;wire[2:0]mcls;
 wire valid,locked,delivery;wire[3:0]tc,lc;wire[41:0]tbundle,lbundle;
 wire[31:0]tf,tt,tr,lf,lt,lr;
 reg accept=0,settled=0,palm=0;
 hand_align_region_lut map(
 .clk(clk),.rst_n(rst),.task_active(active),.cfg_write(cw),.cfg_commit(commit),
 .cfg_cell(cell_index),.cfg_word(word_index),.cfg_wdata(data),.cfg_revision(revision),.cfg_mask(mask),
 .cfg_ready(cfg_ready),.cfg_error(cfg_error),.committed(committed),.cfg_error_code(cfg_error_code),.active_revision(),
 .lookup_req(req),.lookup_x(x),.lookup_y(y),.lookup_frame_id(fid),.lookup_timestamp_ms(ts),.lookup_class(cls),
 .response_valid(response),.mapped_valid(mapped),.mapped_cell(mc),.mapped_bundle(mb),
 .mapped_frame_id(mf),.mapped_timestamp_ms(mt),.mapped_revision(mr),.mapped_class(mcls));
 hand_align_target_core core(
 .clk(clk),.rst_n(rst),.task_active(active),.waiting_region(waiting),.cancel(cancel),.fault(fault),
 .now_ms(now_ms),.max_age_ms(32'd250),.max_gap_ms(32'd250),.hold_ms(16'd50),.min_frames(8'd3),
 .response_valid(response),.mapped_valid(mapped),.mapped_cell(mc),.mapped_bundle(mb),
 .mapped_frame_id(mf),.mapped_timestamp_ms(mt),.mapped_revision(mr),.mapped_class(mcls),
 .accept_target(accept),.position_settled(settled),.palm_confirmed(palm),
 .target_valid(valid),.target_cell(tc),.target_bundle(tbundle),.target_frame_id(tf),.target_timestamp_ms(tt),.target_revision(tr),
 .locked(locked),.delivery_ready(delivery),.locked_cell(lc),.locked_bundle(lbundle),
 .locked_frame_id(lf),.locked_timestamp_ms(lt),.locked_revision(lr));
 task write_word(input[3:0]c,input[1:0]w,input[31:0]v);
 begin @(negedge clk);cw=1;cell_index=c;word_index=w;data=v;@(negedge clk);cw=0;#1;end endtask
 task write_cell(input[3:0]c,input[8:0]lo,input[8:0]hi,input[5:0]kp);
 begin
  write_word(c,0,{14'd0,hi,lo});write_word(c,1,{14'd0,9'd50,9'd30});
  write_word(c,2,{2'd0,12'h041,12'h082,kp});write_word(c,3,{20'd0,12'h0c3});
 end endtask
 task do_commit(input bit yes,input[3:0]reason);
 integer cycles;
 begin
  @(negedge clk);commit=1;@(negedge clk);commit=0;
  cycles=0;
  while(!cfg_ready)begin @(negedge clk);cycles=cycles+1;if(cycles>400)$fatal(1,"FAIL: map commit timeout");end
  #1;if(committed!==yes || (!yes && cfg_error_code!=reason))$fatal(1,"FAIL: commit valid=%0d error=%0d",committed,cfg_error_code);
 end endtask
 task observe(input[31:0]time_ms,input[8:0]px,input[2:0]gesture);
 begin
  @(negedge clk);req=1;fid=fid+1;ts=time_ms;now_ms=time_ms+10;x=px;cls=gesture;
  @(negedge clk);req=0;repeat(2)@(negedge clk);#1;
 end endtask
 reg[41:0]frozen_bundle;reg[31:0]frozen_id,frozen_ts;
 initial begin
  repeat(4)@(negedge clk);rst=1;
  mask=0;do_commit(0,2);mask=1;
  revision=0;do_commit(0,2);revision=32'h1234;
  write_word(0,0,{14'd0,9'd30,9'd10});do_commit(0,3);
  write_cell(0,10,128,6'd4);do_commit(0,4);
  write_cell(0,10,30,6'd4);write_word(0,1,{14'd0,9'd50,9'd0});do_commit(0,4);
  write_cell(0,10,30,6'd4);write_word(0,2,{2'd0,12'h001,12'h082,6'd4});do_commit(0,5);
  write_cell(0,10,30,6'd4);write_word(0,3,32'h800000c3);do_commit(0,7);
  write_cell(0,10,30,6'd4);write_cell(1,30,60,6'd5);mask=3;do_commit(0,6);
  write_cell(1,40,60,6'd5);do_commit(1,0);
  active=1;
  write_word(0,0,0);if(!cfg_error || cfg_error_code!=1 || !committed)$fatal(1,"FAIL: active task config mutated");
  observe(100,20,1);observe(150,20,1);if(valid)$fatal(1,"FAIL: early cell confirmation");
  observe(200,20,1);if(!valid || tc!=0 || tbundle[5:0]!=4)$fatal(1,"FAIL: pre-PALM alignment missing");
  @(negedge clk);accept=1;@(negedge clk);accept=0;
  palm=1;observe(250,20,4);if(locked)$fatal(1,"FAIL: moving target locked before settle");
  observe(300,50,1);observe(350,50,1);observe(400,50,1);
  settled=1;observe(450,50,4);if(locked)$fatal(1,"FAIL: unaccepted cell locked");
  @(negedge clk);accept=1;@(negedge clk);accept=0;repeat(3)@(negedge clk);
  if(!locked || !delivery || lc!=1 || lbundle[5:0]!=5 || lt!=450 || lr!=revision)$fatal(1,"FAIL: atomic PALM lock");
  frozen_bundle=lbundle;frozen_id=lf;frozen_ts=lt;
  observe(500,20,4);now_ms=5000;repeat(4)@(negedge clk);
  if(lbundle!==frozen_bundle || lf!=frozen_id || lt!=frozen_ts || !delivery)$fatal(1,"FAIL: late observation changed blind target");
  cancel=1;@(negedge clk);cancel=0;#1;
  if(delivery || lbundle!==frozen_bundle)$fatal(1,"FAIL: cancel allowed delivery or destroyed exit binding");
  active=0;repeat(3)@(negedge clk);active=1;palm=0;settled=0;
  observe(1000,20,1);observe(1050,20,1);observe(1100,20,1);if(!valid)$fatal(1,"FAIL: task reset");
  // Duplicate observations do not refresh an expired target.
  now_ms=ts+251;req=1;repeat(3)@(negedge clk);req=0;#1;if(valid)$fatal(1,"FAIL: duplicate refreshed stale target");
  observe(1400,20,1);observe(1450,20,1);observe(1500,20,1);if(!valid)$fatal(1,"FAIL: reacquisition");
  observe(1550,90,1);if(valid)$fatal(1,"FAIL: out-of-map target remained valid");
  observe(1600,20,1);observe(1650,20,1);observe(1700,20,1);observe(1750,20,0);
  if(valid)$fatal(1,"FAIL: background kept alignment alive");
  observe(1800,20,1);observe(1850,20,1);observe(1900,20,1);
  fault=1;@(negedge clk);fault=0;observe(1950,20,4);
  if(valid || delivery)$fatal(1,"FAIL: fault rearmed within task");
  $display("PASS: HAND_ALIGN_EXP incomplete/overlap/active-write rejection; pre-PALM align; accepted+settled PALM lock; immutable blind path; stale/duplicate/background/outside/cancel/fault/task reset");
  $finish;
 end
endmodule
