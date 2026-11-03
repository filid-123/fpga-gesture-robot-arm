`timescale 1ns/1ps
module tb_s4_handalign;
reg clk=0;always #5 clk=~clk;
reg rst=0;integer cyc=0,ticks=0;wire tick=(cyc%32)==31;
wire period_pulse=tick && (ticks%2)==1;
always @(posedge clk)begin cyc<=cyc+1;if(tick)ticks<=ticks+1;end
reg vv=1,vc=0,vw=0,estop=1;reg[2:0] cls=0;
reg cv=0;reg[3:0] ci=0;wire cd;wire[3:0] cr;reg[1:0] req=0;reg[143:0] paths=0;
wire[8:0]ka;wire[6:0]sa;reg[31:0]kd=0,sd=0;reg[31:0]km[0:2047],sm[0:127];
wire[1:0]kbank;
wire[6:0]active_step;reg[6:0]target_step=32;wire mix;
 reg[31:0]kd0,kd1,kd2;integer lb,wt;reg signed[63:0]loq,hiq,mixq;

wire[3:0]accepted_cell;wire[31:0]accepted_revision;reg[31:0]pair_words[0:15];wire[511:0]pair_cfg;genvar pp;generate for(pp=0;pp<16;pp=pp+1)begin assign pair_cfg[pp*32+:32]=pair_words[pp];end endgenerate
wire fl;wire av,aw,aset,apalm,accept;wire[3:0]acell;wire[31:0]arev,adebug;
wire rv,mapped,ready,committed,merr,locked,delivery;wire[3:0]mcell,ec,lcell;wire[41:0]bundle;wire[31:0]fid,ts,rev;wire[2:0]mc;
reg mw=0,mcommit=0;reg[3:0]cfgcell=0;reg[1:0]cfgword=0;reg[31:0]mdata=0;reg[8:0]image_x=60,image_y=50;reg feed=1;reg[31:0]frameid=0;
wire freq=tick && (ticks%50==0) && feed;
always @(posedge clk)if(freq)frameid<=frameid+1;
 always @(posedge clk)begin
  if(freq && image_x<128 && image_y>=16 && image_y<=111)begin
   if(image_y<=44)target_step<=64;else if(image_y>=84)target_step<=0;else target_step<=((84-image_y)*8+2)/5;
  end
  lb=(active_step<32)?0:1;wt=(active_step<32)?active_step:active_step-32;
  loq=$signed(km[lb*512+ka]);hiq=$signed(km[(lb+1)*512+ka]);mixq=loq+(((hiq-loq)*wt+16)>>>5);
  kd0<=mix?mixq[31:0]:km[kbank*512+ka];kd1<=kd0;kd2<=kd1;kd<=kd2;sd<=sm[sa];
 end
hand_align_region_lut #(.REGION_COUNT(4))lut(.clk(clk),.rst_n(rst),.task_active(!dut.cfg_unlock),.cfg_write(mw),.cfg_commit(mcommit),.cfg_cell(cfgcell),.cfg_word(cfgword),.cfg_wdata(mdata),.cfg_revision(32'd1),.cfg_mask(16'd2),.cfg_ready(ready),.cfg_error(merr),.committed(committed),.cfg_error_code(ec),.lookup_req(freq),.lookup_x(image_x),.lookup_y(image_y),.lookup_frame_id(frameid),.lookup_timestamp_ms(ticks),.lookup_class(cls),.response_valid(rv),.mapped_valid(mapped),.mapped_cell(mcell),.mapped_bundle(bundle),.mapped_frame_id(fid),.mapped_timestamp_ms(ts),.mapped_revision(rev),.mapped_class(mc));
hand_align_target_core #(.POSITION_ONLY(1),.EXPLICIT_ACCEPT(1),.PIPELINED_FRESHNESS(1)) hc(.accepted_cell_in(accepted_cell),.accepted_revision_in(accepted_revision),.clk(clk),.rst_n(rst),.task_active(!dut.cfg_unlock),.waiting_region(aw),.cancel(dut.cancel_req),.fault(fl),.now_ms(ticks),.max_age_ms(32'd250),.max_gap_ms(32'd250),.hold_ms(16'd80),.min_frames(8'd2),.response_valid(rv),.mapped_valid(mapped),.mapped_cell(mcell),.mapped_bundle(bundle),.mapped_frame_id(fid),.mapped_timestamp_ms(ts),.mapped_revision(rev),.mapped_class(mc),.accept_target(accept),.position_settled(aset),.palm_confirmed(apalm),.target_valid(av),.target_cell(acell),.target_revision(arev),.locked(locked),.delivery_ready(delivery),.locked_cell(lcell));
wire ov;wire[2:0]oc;wire[191:0]ot;wire[15:0]on,on_a;wire opf,ops;
reg blind_watch=0;reg od=0;reg[191:0]last=0,target=0;reg[2:0]ps=0;reg[15:0]seq=0;reg alive=1;
integer cancels=0,scenario=0,trace,forward_count=0,return_index=0,return_moves=0,open_returns=0; reg return_seen=0; reg[191:0]forward_starts[0:63];reg[191:0]slot_open[1:3]; integer reverse_cycles=96;
integer busy=0,moves=0,dones=0,pauses=0,resumes=0,base_moves=0,pre_tick=0,release_tick=0,i,j;
integer bank_case=0,mark_tick=0;integer out_cycles=96,deliver_cycles=3200,release_cycles=96,remaining=0;
integer drain_cycles=0;wire[31:0]plstatus=32'h180|ps|((drain_cycles>0)?32'h20:0);
wire[31:0]status,fault,interaction,timers;wire[15:0]ev;wire owner;
s4_task_fsm #(.SLOT_INVENTORY(1),.PALM_CONTINUITY(1),.TIMED_WALKTHROUGH(1),.HANDOVER_V2(1),.HAND_ALIGN(1),.HAND_ALIGN_REGIONS(4),.HAND_ALIGN_LOCATOR(1),.CONTINUOUS_HAND(1))dut(
 .align_target_step(target_step),.active_step(active_step),.kp_mix_enable(mix),
 .cfg_align_n(16'd59),.cfg_align_na(16'd14),.cfg_banks_ready(4'b1111),.cfg_align_pairs(pair_cfg),.align_target_valid(av),.align_target_cell(acell),.align_target_revision(arev),.align_delivery_ready(delivery),.align_accepted_cell(accepted_cell),.align_accepted_revision(accepted_revision),.align_accept(accept),.align_waiting(aw),.align_settled(aset),.align_palm_confirmed(apalm),.kp_bank(kbank),.align_debug(adebug),
 .clk(clk),.rst_n(rst),.tick(tick),.period_pulse(period_pulse),.vis_valid(vv),.vis_class(cls),.vis_changed(vc),.vis_window_ok(vw),.estop_ok(estop),
 .cmd_valid(cv),.cmd_index(ci),.cmd_done(cd),.cmd_result(cr),.cfg_mode_b(1'b0),.cfg_require_line(1'b1),.cfg_vision_sim(1'b0),.cfg_hold_policy(1'b0),
 .cfg_rearm_mask(8'h81),.cfg_select_mask(8'h0e),.cfg_t_palm_hold(16'd500),.cfg_t_palm_wait(16'd0),.cfg_t_fist_hold(16'd1000),.cfg_t_pre_wait(16'd2000),.cfg_blind_periods(16'd1),
 .cfg_t_arrival(16'd2),.cfg_t_comm(16'd30),.cfg_t_path_wait(16'd1000),.cfg_t_heartbeat(16'd0),.cfg_move_margin(16'd1000),
 .cfg_arrival_mask(6'h00),.cfg_home_kp(6'd0),.cfg_predelivery_kp(6'd15),.cfg_joint_min(192'h0001147bfffcdbc1fffe6de000000000fffe6de0fffcdbc1),.cfg_joint_max(192'h0003243f0003243f00019220000323db000192200003243f),
 .cfg_paths(paths),.cfg_tray_exit(1'b0),.cfg_tray_path(12'd0),.req_object(req),.req_task_id(16'd0),.path_object(2'd0),.path_task_id(16'd0),
 .kp_raddr(ka),.kp_rdata(kd),.seg_raddr(sa),.seg_rdata(sd),.fifo_rdata(32'd0),.fifo_count(6'd0),
 .op_valid(ov),.op_ready(1'b1),.op_code(oc),.op_target(ot),.op_n(on),.op_na(on_a),.op_profile(opf),.op_source(ops),
 .op_done(od),.op_ok(1'b1),.op_timeout(1'b0),.st_s1_status(32'h302d),.st_fb_masks(32'h3f),.st_fb_age({seq,16'd0}),
 .st_pl_status(plstatus),.st_pl_error(32'd0),.st_last(last),.fault_latched(fl),.owner_s4(owner),.status_word(status),.fault_word(fault),.event_set(ev),
 .interaction_status(interaction),.interaction_timers(timers));
always @(posedge clk)begin
 od<=0;
 if(!rst)begin cancels<=0;forward_count=0;return_moves=0;open_returns=0;return_seen=0;ps<=0;last<=192'h00031553000001f7ffffff3700019eb1ffffff3700000192;target<=192'h00031553000001f7ffffff3700019eb1ffffff3700000192;seq<=0;busy<=0;moves<=0;dones<=0;pauses<=0;resumes<=0;remaining<=0;end
 else begin
  if(drain_cycles>0)drain_cycles<=drain_cycles-1;
  if(ov)begin
   od<=1;
   if(oc==0 && alive)seq<=seq+1;
   if(oc==1)begin
    if(drain_cycles>0)$fatal(1,"MOVE before pending samples drained");
    $fdisplay(trace,"MOVE %0d %0d %0d %0d %0d %0d %0d %0d %0d %h %h",scenario,dut.object,dut.st,dut.mv_kind,dut.holding,dut.released,on,on_a,dut.mv_flags,last,ot);
    if(dut.mv_kind==0 && (dut.ph==1 || dut.ph==2))begin forward_starts[forward_count]=last;forward_count=forward_count+1;end
    if(dut.mv_kind==1 && $signed(ot[160+:32])<$signed(last[160+:32]))begin
      if(ot[0+:160]!==slot_open[dut.object][0+:160])$fatal(1,"Opening away from original slot");open_returns=open_returns+1;
    end
    if(dut.mv_kind==4 && ot!==dut.align_origin)$fatal(1,"Anchor target mismatch");
    if(dut.sp>23)$fatal(1,"Stack exceeded capacity");
    moves<=moves+1;target<=ot;ps<=2;
    busy<=(dut.mv_kind==3)?out_cycles:((dut.mv_kind!=0)?reverse_cycles:((dut.ph==2)?deliver_cycles:((dut.ph==3)?release_cycles:out_cycles)));
   end
   if(oc==2 && ps==2)begin drain_cycles<=1024;ps<=3;remaining<=busy;busy<=0;pauses<=pauses+1;for(integer a=0;a<6;a=a+1)last[32*a+:32]<=($signed(last[32*a+:32])+$signed(target[32*a+:32]))>>>1;end
   if(oc==3 && ps==3)begin ps<=2;busy<=remaining;resumes<=resumes+1;end
   if(oc==4)begin if(drain_cycles>0)$fatal(1,"CLEAR before pending samples drained");ps<=0;busy<=0;end
   if(oc==5)begin ps<=6;busy<=0;end
  end
  if(busy>0 && !(ov && (oc==2 || oc==4 || oc==5)))begin busy<=busy-1;if(busy==1)begin ps<=4;last<=target;end end
  if(ev[0])dones<=dones+1;if(ev[1])cancels<=cancels+1;
  if(status[3:0]==9)$fatal(1,"Unexpected HOLD under return policy");
 end
 if(blind_watch && rst && (status[3:0]==5 || status[3:0]==7 || status[3:0]==8 || status[3:0]==9))$fatal(1,"PALM after PRE interrupted blind delivery");
 if(cyc>30_000_000)$fatal(1,"TIMEOUT scenario=%0d bank=%0d same=%b palm=%0d wait=%0d corevalid=%b accepted=%b class=%0d count=%0d inh=%b ready=%b state=%image_y micro=%0d fault=%image_y",scenario,kbank,dut.align_same,dut.palm_hold,dut.palm_wait,av,hc.accepted,hc.target_class,hc.count,hc.inhibited,delivery,status,dut.ms,fault);
end
task cmd(input[3:0]c);
 begin @(negedge clk);ci=c;cv=1;@(negedge clk);cv=0;wait(cd);if(cr!=0)$fatal(1,"CMD %0d result %0d",c,cr);@(negedge clk);end
endtask
task wait_ticks(input integer n);
 integer t;begin t=ticks;while(ticks-t<n)@(negedge clk);end
endtask
task gesture(input[2:0]c,input valid,input window);
 begin @(negedge clk);cls=c;vv=valid;vw=window;vc=1;@(negedge clk);vc=0;end
endtask
task reset_all;
 begin blind_watch=0;rst=0;alive=1;estop=1;cls=0;vc=0;vw=0;vv=1;cv=0;reverse_cycles=96;out_cycles=96;deliver_cycles=6400;release_cycles=96;
 repeat(8)@(negedge clk);rst=1;repeat(5)@(negedge clk);
 for(j=1;j<=3;j=j+1)begin req=j;cmd(11);end
 for(integer c=1;c<2;c=c+1)begin
  cfgcell=c;
  for(integer w=0;w<4;w=w+1)begin
   @(negedge clk);cfgword=w;
   case(w)0:mdata=0|(127<<9);1:mdata=16|(111<<9); 2:mdata=32'd146021711;3:mdata=32'd374;endcase
   mw=1;@(negedge clk);mw=0;
  end
 end
 @(negedge clk);mcommit=1;@(negedge clk);mcommit=0;wait(committed);if(merr)$fatal(1,"Map failed");
 cmd(0);wait(status[3:0]==1);repeat(5)@(negedge clk);end
endtask
task select_obj(input[1:0]obj);
 begin gesture(0,1,0);wait_ticks(3);gesture(obj,1,0);wait(status[3:0]==4 || fl);if(fl)$fatal(1,"SELECT fault %image_y",fault);end
endtask
task go_deliver;
 begin select_obj(1);gesture(4,1,1);wait(status[3:0]==5);wait(status[3:0]==4 && status[6:4]==2);wait(busy>0);end
endtask

reg[191:0]km_home;
task returned(input integer obj,input integer expected_open);
 begin
  wait(status[3:0]==1 || fl);if(fl)$fatal(1,"Return fault %h",fault);
  repeat(5)@(negedge clk);
  if(last!==km_home || status[9] || !status[26+obj-1] || cancels!=1 || dones!=0 || return_index!=-1 || return_moves<1)$fatal(1,"Return final/home/inventory failed scenario %0d",scenario);
  if(expected_open && open_returns!=1)$fatal(1,"No single original-slot release");
  $fdisplay(trace,"END %0d RETURNED",scenario);
 end
endtask
initial begin
 trace=$fopen("motion_trace.txt","w");
 for(i=0;i<2048;i=i+1)km[i]=0;for(i=0;i<128;i=i+1)sm[i]=0;
 $readmemh("keypoints.mem",km);$readmemh("segments.mem",sm);$readmemh("pair_timing.mem",pair_words);
 km_home=192'h00031553000001f7ffffff3700019eb1ffffff3700000192;
 slot_open[1]=192'h00019672000001690000df6000016c160000ec6c00003735;
 slot_open[2]=192'h00019672ffff7c0a0000e23b0001674c0000ee5affffb1d7;
 slot_open[3]=192'h00019672ffffbfb200012e740000e6be000122b0fffff57f;
 paths[0+:12]={6'd7,6'd0};
 paths[12+:12]={6'd7,6'd15};
 paths[24+:12]={6'd7,6'd30};
 paths[36+:12]={6'd1,6'd7};
 paths[48+:12]={6'd1,6'd22};
 paths[60+:12]={6'd1,6'd37};
 paths[72+:12]={6'd7,6'd8};
 paths[84+:12]={6'd7,6'd23};
 paths[96+:12]={6'd7,6'd38};
 paths[108+:12]={6'd8,6'd45};
 paths[120+:12]={6'd1,6'd53};
 paths[132+:12]={6'd5,6'd54};


 for(i=1;i<=3;i=i+1)begin
  for(bank_case=0;bank_case<5;bank_case=bank_case+1)begin
   reset_all();scenario=100+i*10+bank_case;image_y=84-bank_case*10;select_obj(i);wait(status[3:0]==5);
   gesture(1,1,0);wait(active_step==bank_case*16 && status[3:0]==5 && dut.align_same);wait_ticks(2600);
   if(locked || dut.ready_latched || status[3:0]!=5)$fatal(1,"Non PALM delivered");
   pre_tick=ticks;gesture(4,1,1);wait(locked);if(ticks-pre_tick<499)$fatal(1,"Early PALM lock");
   if(lcell!=1)$fatal(1,"Wrong locked cell");image_y=127-image_y;gesture(7,0,0);wait(dones==1);
   if(fl || status[3:0]!=1 || last!==km_home)$fatal(1,"Normal bank did not return HOME");$fdisplay(trace,"END %0d DONE",scenario);
  end
 end
 $display("PASS: all three colors in five continuous positions (0/16/32/48/64), PRE2s/PALM500ms, blind lock and HOME/inventory");
 reset_all();scenario=21;image_y=64;select_obj(1);wait(status[3:0]==5);gesture(1,1,0);
 gesture(7,0,0);for(i=0;i<12;i=i+1)begin case(i%6)0:image_y=100;1:image_y=64;2:image_y=44;3:image_y=100;4:image_y=44;5:image_y=64;endcase wait_ticks(3200);if(status[3:0]!=5 || dut.sp!=15)$fatal(1,"Alignment grew stack or stalled");end
 image_y=100;wait_ticks(3200);gesture(5,1,0);wait(status[3:0]==1 || fl);repeat(5)@(negedge clk);
 if(fl || cancels!=1 || open_returns!=1 || !status[26] || last!==km_home)$fatal(1,"Return final after repeated aligns fl=%b cancels=%0d stock=%b home=%b",fl,cancels,status[28:26],last===km_home);
 $fdisplay(trace,"END %0d RETURNED",scenario);
 // X movement alone cannot choose another Y bank.
 reset_all();scenario=26;image_y=64;select_obj(1);wait(status[3:0]==5);gesture(1,1,0);wait_ticks(3500);
 for(i=0;i<4;i=i+1)begin image_x=(i%2)?0:127;wait_ticks(500);if(dut.active_bank!=1 || status[3:0]!=5)$fatal(1,"X selected wrong Y band");end
 image_x=60;
 $display("PASS: X movement leaves continuous Y unchanged");
 $display("PASS: all six directed transitions repeated with unqualified class7 do not accumulate stack; FIST returns held block via central PRE, original slot, HOME and restores stock");
 reset_all();scenario=22;image_y=20;select_obj(2);wait(status[3:0]==5);gesture(1,1,0);wait_ticks(3500);gesture(4,1,1);wait(locked);deliver_cycles=64000;wait(status[6:4]==2 && busy>0);gesture(5,1,0);wait(status[3:0]==1 || fl);repeat(5)@(negedge clk);
 if(fl || cancels!=1 || !status[27] || last!==km_home)$fatal(1,"Mid delivery return");
 $fdisplay(trace,"END %0d RETURNED",scenario);
 $display("PASS: FIST during offset delivery pauses/retraces partial delivery, rejoins central PRE, returns original slot and HOME");
 reset_all();scenario=23;image_y=20;select_obj(3);wait(status[3:0]==5);out_cycles=64000;gesture(1,1,0);wait(dut.mv_kind==3 && busy>0);gesture(5,1,0);wait(status[3:0]==1 || fl);repeat(5)@(negedge clk);
 if(fl || pauses!=1 || cancels!=1 || !status[28] || last!==km_home)$fatal(1,"Mid alignment return");
 $fdisplay(trace,"END %0d RETURNED",scenario);
 $display("PASS: FIST during alignment reverses its partial move before original-slot return");
 reset_all();scenario=27;image_y=100;select_obj(1);wait(status[3:0]==5);out_cycles=32000;gesture(7,0,0);
 wait(dut.mv_kind==3 && busy>0);image_y=44;mark_tick=ticks;
 wait(active_step==64 && pauses>0);if(ticks-mark_tick>300)$fatal(1,"Retarget waited for old segment completion");
 if(dut.align_retargets<1 || dut.sp!=15)$fatal(1,"Retarget count/stack");
 wait(status[3:0]==5);out_cycles=96;gesture(5,1,0);wait(status[3:0]==1 || fl);repeat(5)@(negedge clk);
 if(fl || cancels!=1 || !status[26] || last!==km_home)$fatal(1,"Retarget follow return failed");$fdisplay(trace,"END %0d RETURNED",scenario);
 $display("PASS: independent Locator follows class7/unqualified positions; new coordinate PAUSE/drain/CLEAR retargets before old segment completes, then FIST returns HOME");
 reset_all();scenario=24;image_y=20;select_obj(1);wait(status[3:0]==5);gesture(4,1,1);feed=0;wait_ticks(3000);if(locked || dut.ready_latched)$fatal(1,"Stale observation locked");feed=1;wait(locked);estop=0;repeat(3)@(negedge clk);if(!fl)$fatal(1,"D5 not retained");
 reset_all();scenario=25;image_y=20;reverse_cycles=64000;select_obj(1);wait(status[3:0]==5);gesture(1,1,0);wait_ticks(3500);gesture(5,1,0);wait(status[3:0]==8);alive=0;wait(fl);if(fault[7:0]!=7)$fatal(1,"COMM protection lost on offset return");
 $display("PASS: stale mapped frames cannot lock; D5 and COMM faults retained on offset return");
 $fclose(trace);$finish;
end
endmodule
