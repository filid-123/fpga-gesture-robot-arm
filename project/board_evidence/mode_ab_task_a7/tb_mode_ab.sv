`timescale 1ns/1ps
module tb_restock;
wire mode_b;wire[8:0]b_faddr;wire[31:0]b_fdata;wire[5:0]b_fcount;wire b_clear;
wire b_kind;wire[5:0]b_release;wire[15:0]b_selected,b_path_id;wire[1:0]b_object;
reg[31:0]bn[0:511],br[0:511];integer bn_count=15,br_count=27;

reg clk=0;always #5 clk=~clk;
reg rst=0;integer cyc=0,ticks=0;wire tick=(cyc%32)==31;
wire period_pulse=tick && (ticks%2)==1;
always @(posedge clk)begin cyc<=cyc+1;if(tick)ticks<=ticks+1;end
reg vv=1,vc=0,vw=0,estop=1;reg[2:0] cls=0;
reg drop_event=0;reg cv=0;reg[3:0] ci=0;wire cd;wire[3:0] cr;reg[1:0] req=0;reg[143:0] paths=0;
wire[8:0]ka;wire[6:0]sa;wire[31:0]kd,sd;reg[31:0]km[0:2047],sm[0:255];
wire[1:0]kbank;reg[191:0]km_home;
wire[6:0]active_step;reg[6:0]target_step=32;wire mix;
wire rs;wire[47:0]rs_paths;wire[17:0]rs_kps;integer restocks=0,stretch_pos=0;reg[31:0]rs_cfg[0:3],source_words[0:5];reg[191:0]source_open;

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

 end
hand_align_region_lut #(.REGION_COUNT(4))lut(.clk(clk),.rst_n(rst),.task_active(!dut.cfg_unlock),.cfg_write(mw),.cfg_commit(mcommit),.cfg_cell(cfgcell),.cfg_word(cfgword),.cfg_wdata(mdata),.cfg_revision(32'd1),.cfg_mask(16'd2),.cfg_ready(ready),.cfg_error(merr),.committed(committed),.cfg_error_code(ec),.lookup_req(freq),.lookup_x(image_x),.lookup_y(image_y),.lookup_frame_id(frameid),.lookup_timestamp_ms(ticks),.lookup_class(cls),.response_valid(rv),.mapped_valid(mapped),.mapped_cell(mcell),.mapped_bundle(bundle),.mapped_frame_id(fid),.mapped_timestamp_ms(ts),.mapped_revision(rev),.mapped_class(mc));
hand_align_target_core #(.POSITION_ONLY(1),.EXPLICIT_ACCEPT(1),.PIPELINED_FRESHNESS(1)) hc(.accepted_cell_in(accepted_cell),.accepted_revision_in(accepted_revision),.clk(clk),.rst_n(rst),.task_active(!dut.cfg_unlock),.waiting_region(aw),.cancel(dut.cancel_req),.fault(fl),.now_ms(ticks),.max_age_ms(32'd250),.max_gap_ms(32'd250),.hold_ms(16'd80),.min_frames(8'd2),.response_valid(rv),.mapped_valid(mapped),.mapped_cell(mcell),.mapped_bundle(bundle),.mapped_frame_id(fid),.mapped_timestamp_ms(ts),.mapped_revision(rev),.mapped_class(mc),.accept_target(accept),.position_settled(aset),.palm_confirmed(apalm),.target_valid(av),.target_cell(acell),.target_revision(arev),.locked(locked),.delivery_ready(delivery),.locked_cell(lcell));
wire ov;wire[2:0]oc;wire[191:0]ot;wire[15:0]on,on_a;wire opf,ops;
reg blind_watch=0;reg od=0;reg[191:0]last=0,target=0;reg[2:0]ps=0;reg[15:0]seq=0;reg alive=1;
integer cancels=0,scenario=0,trace,forward_count=0,return_index=0,return_moves=0,open_returns=0; reg return_seen=0; reg[191:0]forward_starts[0:255];reg[191:0]slot_open[1:3]; integer reverse_cycles=96;
integer busy=0,moves=0,dones=0,pauses=0,resumes=0,base_moves=0,pre_tick=0,release_tick=0,i,j;
integer bank_case=0,mark_tick=0;integer out_cycles=96,deliver_cycles=3200,release_cycles=96,remaining=0;
integer drain_cycles=0;wire[31:0]plstatus=32'h180|ps|((drain_cycles>0)?32'h20:0);
wire[31:0]status,fault,interaction,timers;wire[15:0]ev;wire owner;
s4_task_fsm #(.SLOT_INVENTORY(1),.PALM_CONTINUITY(1),.TIMED_WALKTHROUGH(1),.HANDOVER_V2(1),.HAND_ALIGN(1),.HAND_ALIGN_REGIONS(4),.HAND_ALIGN_LOCATOR(1),.CONTINUOUS_HAND(1),.AUTO_RESTOCK(1),.DYNAMIC_B(1))dut(
 .cfg_b_restock(b_kind),.cfg_b_release_index(b_release),.selected_task_id(b_selected),
 .cfg_restock_paths(rs_paths),.cfg_restock_release_kps(rs_kps),.restock_task(rs),
 .align_target_step(target_step),.active_step(active_step),.kp_mix_enable(mix),
 .cfg_align_n(16'd59),.cfg_align_na(16'd14),.cfg_banks_ready(4'b1111),.cfg_align_pairs(pair_cfg),.align_target_valid(av),.align_target_cell(acell),.align_target_revision(arev),.align_delivery_ready(delivery),.align_accepted_cell(accepted_cell),.align_accepted_revision(accepted_revision),.align_accept(accept),.align_waiting(aw),.align_settled(aset),.align_palm_confirmed(apalm),.kp_bank(kbank),.align_debug(adebug),
 .clk(clk),.rst_n(rst),.tick(tick),.period_pulse(period_pulse),.vis_valid(vv),.vis_class(cls),.vis_changed(vc),.vis_window_ok(vw),.estop_ok(estop),
 .cmd_valid(cv),.cmd_index(ci),.cmd_done(cd),.cmd_result(cr),.cfg_mode_b(mode_b),.cfg_require_line(1'b1),.cfg_vision_sim(1'b0),.cfg_hold_policy(1'b0),
 .cfg_rearm_mask(8'h81),.cfg_select_mask(8'h0e),.cfg_t_palm_hold(16'd500),.cfg_t_palm_wait(16'd0),.cfg_t_fist_hold(16'd1000),.cfg_t_pre_wait(16'd2000),.cfg_blind_periods(16'd1),
 .cfg_t_arrival(16'd2),.cfg_t_comm(16'd30),.cfg_t_path_wait(16'd1000),.cfg_t_heartbeat(16'd0),.cfg_move_margin(16'd1000),
 .cfg_arrival_mask(6'h00),.cfg_home_kp(6'd0),.cfg_predelivery_kp(6'd15),.cfg_joint_min(192'h0001147bfffcdbc1fffe6de000000000fffe6de0fffcdbc1),.cfg_joint_max(192'h0003243f0003243f00019220000323db000192200003243f),
 .cfg_paths(paths),.cfg_tray_exit(1'b0),.cfg_tray_path(12'd0),.req_object(req),.req_task_id(16'd0),.path_object(b_object),.path_task_id(b_path_id),
 .kp_raddr(ka),.kp_rdata(kd),.seg_raddr(sa),.seg_rdata(sd),.fifo_rdata(b_fdata),.fifo_count(b_fcount),.fifo_raddr(b_faddr),.fifo_clear(b_clear),
 .op_valid(ov),.op_ready(1'b1),.op_code(oc),.op_target(ot),.op_n(on),.op_na(on_a),.op_profile(opf),.op_source(ops),
 .op_done(od),.op_ok(1'b1),.op_timeout(1'b0),.st_s1_status(32'h302d),.st_fb_masks(32'h3f),.st_fb_age({seq,16'd0}),
 .st_pl_status(plstatus),.st_pl_error(32'd0),.st_last(last),.fault_latched(fl),.owner_s4(owner),.status_word(status),.fault_word(fault),.event_set(ev),
 .interaction_status(interaction),.interaction_timers(timers));
always @(posedge clk)begin
 od<=0;
 if(!rst)begin restocks<=0;cancels<=0;forward_count=0;return_moves=0;open_returns=0;return_seen=0;ps<=0;last<=192'h00031553000001f7ffffff3700019eb1ffffff3700000192;target<=192'h00031553000001f7ffffff3700019eb1ffffff3700000192;seq<=0;busy<=0;moves<=0;dones<=0;pauses<=0;resumes<=0;remaining<=0;end
 else begin
  if(drain_cycles>0)drain_cycles<=drain_cycles-1;
  if(ov)begin
   od<=1;
   if(oc==0 && alive)seq<=seq+1;
   if(oc==1)begin
    if(drain_cycles>0)$fatal(1,"MOVE before pending samples drained");
    $fdisplay(trace,"MOVE %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %h %h",scenario,dut.object,dut.st,dut.mv_kind,dut.holding,dut.released,on,on_a,dut.mv_flags,rs,last,ot);
    if(dut.mv_kind==0 && (dut.ph==1 || dut.ph==2))begin forward_starts[forward_count]=last;forward_count=forward_count+1;end
    if(dut.mv_kind==1 && $signed(ot[160+:32])<$signed(last[160+:32]))begin
      if(ot[0+:160]!== (rs?source_open[0+:160]:slot_open[dut.object][0+:160]))$fatal(1,"Opening away from original slot");open_returns=open_returns+1;
    end
    if(dut.mv_kind==4 && ot!==dut.align_origin)$fatal(1,"Anchor target mismatch");
    if(dut.sp>(mode_b?63:23))$fatal(1,"Stack exceeded capacity");
    moves<=moves+1;target<=ot;ps<=2;
    busy<=(dut.mv_kind==3)?out_cycles:((dut.mv_kind!=0)?reverse_cycles:((dut.ph==2)?deliver_cycles:((dut.ph==3)?release_cycles:out_cycles)));
   end
   if(oc==1 && rs && dut.pos==stretch_pos)busy<=64000;
   if(oc==2 && ps==2)begin drain_cycles<=1024;ps<=3;remaining<=busy;busy<=0;pauses<=pauses+1;for(integer a=0;a<6;a=a+1)last[32*a+:32]<=($signed(last[32*a+:32])+$signed(target[32*a+:32]))>>>1;end
   if(oc==3 && ps==3)begin ps<=2;busy<=remaining;resumes<=resumes+1;end
   if(oc==4)begin if(drain_cycles>0)$fatal(1,"CLEAR before pending samples drained");ps<=0;busy<=0;end
   if(oc==5)begin ps<=6;busy<=0;end
  end
  if(busy>0 && !(ov && (oc==2 || oc==4 || oc==5)))begin busy<=busy-1;if(busy==1)begin ps<=4;last<=target;end end
  if(ev[14])begin $fdisplay(trace,"END %0d RESTOCKED",scenario);restocks<=restocks+1;if(last!==km_home)$fatal(1,"Restock completed before HOME");end
  if(rs && (status[3:0]==5 || mix || kbank!=3))$fatal(1,"Restock entered handover/follow/mixed-bank mode");
  if(rs && !mode_b && status[26+dut.object-1])$fatal(1,"Restock stock available before completion");
  if(ev[0])begin dones<=dones+1;$fdisplay(trace,"END %0d DELIVERED",scenario);end
  if(ev[1])begin cancels<=cancels+1;$fdisplay(trace,"END %0d CANCELLED",scenario);end
  if(ev[3])$fdisplay(trace,"END %0d FAULT",scenario);
  if(status[3:0]==9)$fatal(1,"Unexpected HOLD under return policy");
 end
 if(blind_watch && rst && (status[3:0]==5 || status[3:0]==7 || status[3:0]==8 || status[3:0]==9))$fatal(1,"PALM after PRE interrupted blind delivery");
 if(cyc>30_000_000)$fatal(1,"TIMEOUT scenario=%0d bank=%0d same=%b palm=%0d wait=%0d corevalid=%b accepted=%b class=%0d count=%0d inh=%b ready=%b state=%h micro=%0d fault=%h",scenario,kbank,dut.align_same,dut.palm_hold,dut.palm_wait,av,hc.accepted,hc.target_class,hc.count,hc.inhibited,delivery,status,dut.ms,fault);
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
 for(integer z=0;z<4;z=z+1)write_cfg(12'h374+z*4,rs_cfg[z]);
 cmd(0);wait(status[3:0]==1);repeat(5)@(negedge clk);end
endtask
task select_obj(input[1:0]obj);
 begin gesture(0,1,0);wait_ticks(3);gesture(obj,1,0);wait(status[3:0]==4 || fl);if(fl)$fatal(1,"SELECT fault %h",fault);end
endtask
task go_deliver;
 begin select_obj(1);gesture(4,1,1);wait(status[3:0]==5);wait(status[3:0]==4 && status[6:4]==2);wait(busy>0);end
endtask


task returned(input integer obj,input integer expected_open);
 begin
  wait(status[3:0]==1 || fl);if(fl)$fatal(1,"Return fault %h",fault);
  repeat(5)@(negedge clk);
  if(last!==km_home || status[9] || !status[26+obj-1] || cancels!=1 || dones!=0 || return_index!=-1 || return_moves<1)$fatal(1,"Return final/home/inventory failed scenario %0d",scenario);
  if(expected_open && open_returns!=1)$fatal(1,"No single original-slot release");
  $fdisplay(trace,"END %0d RETURNED",scenario);
 end
endtask

reg[11:0]axaddr=0,araddr=0;reg[31:0]axdata=0;reg axvalid=0,arvalid=0;wire aready,wready,bvalid,rvalid;wire[1:0]bresp,rresp;wire[31:0]rdata;
s4_task_regs #(.AUTO_RESTOCK(1),.HAND_ALIGN(1),.HAND_ALIGN_REGIONS(4),.CONTINUOUS_HAND(1),.DYNAMIC_B(1))tables(
 .cfg_mode_b(mode_b),.cfg_b_restock(b_kind),.cfg_b_release_index(b_release),.selected_task_id(b_selected),.path_object(b_object),.path_task_id(b_path_id),.status_word(status),.fifo_raddr(b_faddr),.fifo_rdata(b_fdata),.fifo_count(b_fcount),
 .clk(clk),.rst_n(rst),.s_awaddr(axaddr),.s_awvalid(axvalid),.s_awready(aready),.s_wdata(axdata),.s_wstrb(4'hf),.s_wvalid(axvalid),.s_wready(wready),.s_bresp(bresp),.s_bvalid(bvalid),.s_bready(1'b1),
 .s_araddr(araddr),.s_arvalid(arvalid),.s_arready(),.s_rdata(rdata),.s_rvalid(rvalid),.s_rresp(rresp),.s_rready(1'b1),
 .cfg_unlock(dut.cfg_unlock),.fifo_unlock(dut.fifo_unlock),.cmd_done(cd),.cmd_result(cr),.cmd_done_index(ci),
 .kp_raddr(ka),.kp_bank(kbank),.kp_mix_enable(mix),.active_step(active_step),.target_step(target_step),.kp_rdata(kd),.seg_raddr(sa),.seg_rdata(sd),.restock_task(rs),
 .cfg_restock_paths(rs_paths),.cfg_restock_release_kps(rs_kps),.event_set(ev | (drop_event?16'h0800:16'd0)),.cnt_inc(6'd0),.poll_done(1'b0),.fifo_clear(b_clear));
task write_cfg(input[11:0]a,input[31:0]v);
 begin @(negedge clk);axaddr=a;axdata=v;axvalid=1;wait(aready&&wready);@(negedge clk);axvalid=0;wait(bvalid);if(bresp!=0)$fatal(1,"CFG write %h",a);@(negedge clk);end
endtask
task read_cfg(input[11:0]a,input[31:0]expected);
 begin @(negedge clk);araddr=a;arvalid=1;@(negedge clk);arvalid=0;wait(rvalid);if(rresp!=0 || rdata!==expected)$fatal(1,"CFG read %h got%h want%h",a,rdata,expected);@(negedge clk);end
endtask
task empty_slot(input integer obj);
 begin reset_all();image_y=64;scenario=10+obj;select_obj(obj);gesture(4,1,1);wait(dones==1 || fl);wait(status[3:0]==1 || fl);if(fl || status[26+obj-1])$fatal(1,"Normal delivery must empty selected slot");wait_ticks(3);end
endtask
task restock_select(input integer obj);
 begin select_obj(obj);if(!rs)$fatal(1,"Empty gesture did not select restock");end
endtask
task restock_done(input integer obj);
 begin wait(restocks==1 || fl);wait(status[3:0]==1 || fl);repeat(6)@(negedge clk);if(fl || !status[26+obj-1] || last!==km_home || rs || cancels!=0)$fatal(1,"Restock completion/home/stock failed");read_cfg(12'h388,1);end
endtask

task b_select;
 begin gesture(0,1,0);wait_ticks(3);gesture(1,1,0);wait(status[3:0]==2 || fl);if(fl)$fatal(1,"B select fault");end
endtask
task b_upload(input integer kind,input integer bad_index);
 begin
  cmd(9);
  write_cfg(12'h38c,kind | ((bad_index>=0?bad_index:20)<<8));
  for(integer z=0;z<(kind?br_count:bn_count)*8;z=z+1)write_cfg(12'h068,kind?br[z]:bn[z]);
  if(b_fcount!==(kind?br_count:bn_count))$fatal(1,"FIFO incomplete");
  write_cfg(12'h05c,(b_selected<<16)|1);
 end
endtask
task b_commit;
 begin cmd(8);wait(status[3:0]==4 || status[3:0]==1 || fl);if(fl || status[3:0]!=4)$fatal(1,"B commit refused %h",fault);end
endtask
task rejected_commit;
 begin @(negedge clk);ci=8;cv=1;@(negedge clk);cv=0;wait(cd);if(cr!=2)$fatal(1,"Stale B task identity accepted");@(negedge clk);end
endtask

initial begin
 trace=$fopen("motion_trace.txt","w");
 for(i=0;i<2048;i=i+1)km[i]=0;for(i=0;i<256;i=i+1)sm[i]=0;
 $readmemh("b_normal.mem",bn);$readmemh("b_restock.mem",br);
 $readmemh("keypoints.mem",km);$readmemh("segments.mem",sm);$readmemh("pair_timing.mem",pair_words);$readmemh("restock_cfg.mem",rs_cfg);$readmemh("source_open.mem",source_words);
 for(i=0;i<2048;i=i+1)tables.kp_mem[i]=km[i];for(i=0;i<256;i=i+1)tables.seg_mem[i]=sm[i];
 for(i=0;i<6;i=i+1)source_open[i*32+:32]=source_words[i];
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



 for(integer obj=1;obj<=3;obj=obj+1)begin
  empty_slot(obj);stretch_pos=0;scenario=100+obj;restock_select(obj);
  @(negedge clk);drop_event=1;@(negedge clk);drop_event=0;repeat(3)@(negedge clk);read_cfg(12'h388,0);
  restock_done(obj);
  base_moves=moves;wait_ticks(100);if(moves!=base_moves || dones!=1)$fatal(1,"Held digit retriggered after restock");
  scenario=300+obj;select_obj(obj);gesture(4,1,1);wait(dones==2 || fl);wait(status[3:0]==1 || fl);if(fl || status[26+obj-1] || restocks!=1)$fatal(1,"Refilled slot did not support next delivery");
 end
 $display("PASS: three colors deliver -> empty-digit auto-restock -> HOME/stock -> fresh-digit next delivery; held digit never retriggers");
 for(integer test=0;test<3;test=test+1)begin
  empty_slot(1);stretch_pos=(test==0)?4:((test==1)?11:19);scenario=200+test;restock_select(1);
  wait(rs && dut.pos==stretch_pos && busy>0);gesture(5,1,0);wait(status[3:0]==1 || fl);repeat(6)@(negedge clk);
  if(fl || cancels!=1 || restocks!=0 || status[26] || last!==km_home)$fatal(1,"Restock FIST cancellation failed stage%0d",test);
  if(test>0 && open_returns!=1)$fatal(1,"Held restock must open once at public source");
  read_cfg(12'h388,0);
 end
 $display("PASS: FIST before grasp, during source lift and slot descent drains/retraces public pickup/HOME; destination stays empty");
 empty_slot(2);stretch_pos=22;scenario=400;restock_select(2);wait(rs && dut.released && busy>0);gesture(5,1,0);restock_done(2);
 if(cancels!=0)$fatal(1,"Released restock was wrongly undone");
 $display("PASS: once placement opening commits, FIST follows existing released policy and completes HOME/refill");
 empty_slot(3);stretch_pos=11;scenario=500;restock_select(3);wait(rs && busy>0);write_cfg(12'h374,0);read_cfg(12'h374,rs_cfg[0]);
 wait(dut.holding);estop=0;wait(fl);if(status[28] || restocks!=0)$fatal(1,"D5 fault refilled slot");
 $display("PASS: busy restock configuration locked; D5 fault never marks destination available");
 empty_slot(1);stretch_pos=11;scenario=501;restock_select(1);wait(dut.holding && busy>0);alive=0;wait(fl);
 if(fault[7:0]!=7 || status[26] || restocks!=0)$fatal(1,"Restock feedback fault lost");
 $display("PASS: restock retains feedback-freshness fault and empty stock");
 empty_slot(1);stretch_pos=0;write_cfg(12'h378,(rs_cfg[1]&32'hffc0ffff)|(63<<16));base_moves=moves;
 gesture(0,1,0);wait_ticks(3);gesture(1,1,0);wait(status[3:0]==3);
 wait(status[3:0]==1 || fl);if(fl || moves!=base_moves || fault[23:16]!=6 || status[26])$fatal(1,"Bad restock release descriptor accepted");
 $display("PASS: missing placement release descriptor is refused before any MOVE");
 reset_all();
 @(negedge clk);drop_event=1;@(negedge clk);drop_event=0;repeat(3)@(negedge clk);read_cfg(12'h388,0);
 if(!tables.event_sticky[11] || tables.event_sticky[14])$fatal(1,"PS write-block event collided with restock completion");
 $display("PASS: original PS_WRITE_BLOCKED bit11 never increments independent RESTOCKED bit14 counter in IDLE or running task");

 reset_all();image_y=64;scenario=600;write_cfg(12'h024,1);b_select();
 read_cfg(12'h390,32'h00010001);base_moves=moves;
 // Path table mutation is permitted at the stationary WAIT_PATH boundary.
 write_cfg(12'h12c,3);write_cfg(12'h110,511);write_cfg(12'h114,32'h12345678);
 repeat(2)@(negedge clk);
 if(tables.kp_mem[2047]!==32'h12345678)$fatal(1,"WAIT_PATH table write rejected");
 // Mode and joint envelopes must remain locked at that same boundary.
 write_cfg(12'h024,0);if(!mode_b)$fatal(1,"WAIT_PATH mode write accepted");
 write_cfg(12'h080,32'h55555555);if(tables.cfg_joint_min[31:0]!==32'h80000000)$fatal(1,"WAIT_PATH limit write accepted");
 b_upload(0,-1);write_cfg(12'h05c,1);rejected_commit();
 if(moves!=base_moves || status[3:0]!=2)$fatal(1,"Old task moved");
 write_cfg(12'h05c,(b_selected<<16)|1);cmd(8);
 write_cfg(12'h12c,2);write_cfg(12'h068,32'hfeedbeef);
 if(tables.cfg_bank!=3 || b_fcount!=bn_count)$fatal(1,"COMMIT scan is not immutable");
 gesture(4,1,1);wait(dones==1 || fl);wait(status[3:0]==1 || fl);
 if(fl || last!==km_home || status[28:26]!=7)$fatal(1,"B normal completion changed A inventory/home");
 $display("PASS: dynamic B WAIT_PATH-only tables, immutable COMMIT scan, selected task identity and real PALM/core completion");

 gesture(0,1,0);wait_ticks(3);b_select();if(b_selected!=2)$fatal(1,"B selection sequence not advanced");
 cmd(3);wait(status[3:0]==1);b_select();if(b_selected!=3)$fatal(1,"Cancelled WAIT_PATH reused task identity");
 b_upload(0,-1);write_cfg(12'h05c,(16'd2<<16)|1);rejected_commit();cmd(3);wait(status[3:0]==1);
 $display("PASS: cancelled or timed-out B selections cannot accept an earlier task path");

 reset_all();image_y=64;scenario=700;write_cfg(12'h024,1);b_select();b_upload(1,-1);b_commit();
 wait(restocks==1 || fl);wait(status[3:0]==1 || fl);repeat(6)@(negedge clk);
 if(fl || last!==km_home || status[28:26]!=7 || dones!=0)$fatal(1,"B dynamic restock completion failed");
 base_moves=moves;wait_ticks(100);if(moves!=base_moves)$fatal(1,"Held B digit retriggered");
 $display("PASS: dynamic B restock uses FIFO end-to-end without PALM and preserves separate A inventory");

 reset_all();image_y=64;scenario=701;stretch_pos=11;write_cfg(12'h024,1);b_select();b_upload(1,-1);b_commit();
 wait(rs && dut.holding && dut.pos==stretch_pos && busy>0);gesture(5,1,0);wait(status[3:0]==1 || fl);repeat(6)@(negedge clk);
 if(fl || cancels!=1 || restocks!=0 || last!==km_home || status[28:26]!=7)$fatal(1,"B restock cancel failed");
 $display("PASS: dynamic B held restock drains and retraces its actual public pickup before HOME");

 reset_all();image_y=64;scenario=702;stretch_pos=21;write_cfg(12'h024,1);b_select();b_upload(1,-1);b_commit();
 wait(rs && dut.released && busy>0);gesture(5,1,0);wait(restocks==1 || fl);wait(status[3:0]==1 || fl);
 if(fl || cancels!=0 || last!==km_home)$fatal(1,"B restock release commitment reversed");
 $display("PASS: dynamic B placement opening is a commitment; later FIST completes retreat/HOME");

 reset_all();image_y=64;scenario=703;write_cfg(12'h024,1);b_select();b_upload(1,31);base_moves=moves;cmd(8);
 wait(status[3:0]==1 || fl);repeat(6)@(negedge clk);
 if(fl || moves!=base_moves || restocks!=0)$fatal(1,"B missing release accepted");
 $display("PASS: malformed dynamic B restock release index is refused before any MOVE");

 reset_all();image_y=64;scenario=704;write_cfg(12'h024,1);b_select();cmd(9);
 // Forty repeated safe endpoint segments cross the old 32-entry address boundary.
 for(integer z=0;z<40;z=z+1)
  for(integer w=0;w<8;w=w+1)write_cfg(12'h068,bn[w]);
 for(integer z=8;z<bn_count*8;z=z+1)write_cfg(12'h068,bn[z]);
 write_cfg(12'h05c,(b_selected<<16)|1);b_commit();
 wait(dut.sp>32);gesture(5,1,0);wait(status[3:0]==1 || fl);repeat(6)@(negedge clk);
 if(fl || cancels!=1 || last!==km_home)$fatal(1,"Extended FIFO/stack did not retrace to HOME");
 b_select();cmd(9);
 for(integer z=0;z<64*8;z=z+1)write_cfg(12'h068,bn[z%8]);
 if(b_fcount!=63 || !tables.fifo_overflow)$fatal(1,"FIFO capacity overflow wrapped count or was not rejected");
 cmd(3);wait(status[3:0]==1);
 $display("PASS: B FIFO/return stack crosses entry 32 and rejects the 64th segment without wrap");

 $fclose(trace);$finish;
end
endmodule
