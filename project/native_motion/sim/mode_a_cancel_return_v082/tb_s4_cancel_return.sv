`timescale 1ns/1ps
module tb_s4_cancel_return;
reg clk=0;always #5 clk=~clk;
reg rst=0;integer cyc=0,ticks=0;wire tick=(cyc%32)==31;
wire period_pulse=tick && (ticks%2)==1;
always @(posedge clk)begin cyc<=cyc+1;if(tick)ticks<=ticks+1;end
reg vv=1,vc=0,vw=0,estop=1;reg[2:0] cls=0;
reg cv=0;reg[3:0] ci=0;wire cd;wire[3:0] cr;reg[1:0] req=0;reg[143:0] paths=0;
wire[8:0]ka;wire[6:0]sa;reg[31:0]kd=0,sd=0;reg[31:0]km[0:511],sm[0:127];
always @(posedge clk)begin kd<=km[ka];sd<=sm[sa];end
wire ov;wire[2:0]oc;wire[191:0]ot;wire[15:0]on,on_a;wire opf,ops;
reg blind_watch=0;reg od=0;reg[191:0]last=0,target=0;reg[2:0]ps=0;reg[15:0]seq=0;reg alive=1;
integer cancels=0,scenario=0,trace,forward_count=0,return_index=0,return_moves=0,open_returns=0; reg return_seen=0; reg[191:0]forward_starts[0:63];reg[191:0]slot_open[1:3]; integer reverse_cycles=96;
integer busy=0,moves=0,dones=0,pauses=0,resumes=0,base_moves=0,pre_tick=0,release_tick=0,i,j;
integer out_cycles=96,deliver_cycles=3200,release_cycles=96,remaining=0;
wire[31:0]plstatus=32'h180|ps;
wire[31:0]status,fault,interaction,timers;wire[15:0]ev;wire fl,owner;
s4_task_fsm #(.SLOT_INVENTORY(1),.PALM_CONTINUITY(1),.TIMED_WALKTHROUGH(1),.HANDOVER_V2(1))dut(
 .clk(clk),.rst_n(rst),.tick(tick),.period_pulse(period_pulse),.vis_valid(vv),.vis_class(cls),.vis_changed(vc),.vis_window_ok(vw),.estop_ok(estop),
 .cmd_valid(cv),.cmd_index(ci),.cmd_done(cd),.cmd_result(cr),.cfg_mode_b(1'b0),.cfg_require_line(1'b1),.cfg_vision_sim(1'b0),.cfg_hold_policy(1'b0),
 .cfg_rearm_mask(8'h81),.cfg_select_mask(8'h0e),.cfg_t_palm_hold(16'd500),.cfg_t_palm_wait(16'd0),.cfg_t_fist_hold(16'd1000),.cfg_t_pre_wait(16'd2000),.cfg_blind_periods(16'd1),
 .cfg_t_arrival(16'd2),.cfg_t_comm(16'd30),.cfg_t_path_wait(16'd1000),.cfg_t_heartbeat(16'd0),.cfg_move_margin(16'd1000),
 .cfg_arrival_mask(6'h3f),.cfg_home_kp(6'd0),.cfg_predelivery_kp(6'd15),.cfg_joint_min(192'h0001147bfffcdbc1fffe6de000000000fffe6de0fffcdbc1),.cfg_joint_max(192'h0003243f0003243f00019220000323db000192200003243f),
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
  if(ov)begin
   od<=1;
   if(oc==0 && alive)seq<=seq+1;
   if(oc==1)begin
    $fdisplay(trace,"MOVE %0d %0d %0d %0d %0d %0d %0d %0d %0d %h %h",scenario,dut.object,dut.st,dut.mv_kind,dut.holding,dut.released,on,on_a,dut.mv_flags,last,ot);
    if(dut.mv_kind==0 && (dut.ph==1 || dut.ph==2))begin forward_starts[forward_count]=last;forward_count=forward_count+1;end
    if(dut.mv_kind!=0)begin
      if(!return_seen)begin return_index=forward_count-1;return_seen=1;end
      if(return_index<0 || ot!==forward_starts[return_index])$fatal(1,"Return target/order scenario %0d index %0d",scenario,return_index);
      return_index=return_index-1;return_moves=return_moves+1;
      if($signed(ot[160+:32])<$signed(last[160+:32]))begin
        if(ot[0+:160]!==slot_open[dut.object][0+:160])$fatal(1,"Open return outside original slot");
        open_returns=open_returns+1;
      end
    end
    moves<=moves+1;target<=ot;ps<=2;
    busy<=(dut.mv_kind!=0)?reverse_cycles:((dut.ph==2)?deliver_cycles:((dut.ph==3)?release_cycles:out_cycles));
   end
   if(oc==2 && ps==2)begin ps<=3;remaining<=busy;busy<=0;pauses<=pauses+1;for(integer a=0;a<6;a=a+1)last[32*a+:32]<=($signed(last[32*a+:32])+$signed(target[32*a+:32]))>>>1;end
   if(oc==3 && ps==3)begin ps<=2;busy<=remaining;resumes<=resumes+1;end
   if(oc==4)begin ps<=0;busy<=0;end
   if(oc==5)begin ps<=6;busy<=0;end
  end
  if(busy>0 && !(ov && (oc==2 || oc==4 || oc==5)))begin busy<=busy-1;if(busy==1)begin ps<=4;last<=target;end end
  if(ev[0])dones<=dones+1;if(ev[1])cancels<=cancels+1;
  if(status[3:0]==9)$fatal(1,"Unexpected HOLD under return policy");
 end
 if(blind_watch && rst && (status[3:0]==5 || status[3:0]==7 || status[3:0]==8 || status[3:0]==9))$fatal(1,"PALM after PRE interrupted blind delivery");
 if(cyc>8_000_000)$fatal(1,"TIMEOUT state=%x micro=%0d fault=%x",status,dut.ms,fault);
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
 cmd(0);wait(status[3:0]==1);repeat(5)@(negedge clk);end
endtask
task select_obj(input[1:0]obj);
 begin gesture(0,1,0);wait_ticks(3);gesture(obj,1,0);wait(status[3:0]==4 || fl);if(fl)$fatal(1,"SELECT fault %x",fault);end
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
 for(i=0;i<512;i=i+1)km[i]=0;for(i=0;i<128;i=i+1)sm[i]=0;
 $readmemh("keypoints.mem",km);$readmemh("segments.mem",sm);
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
 paths[108+:12]={6'd4,6'd45};
 paths[120+:12]={6'd1,6'd49};
 paths[132+:12]={6'd5,6'd50};

 reset_all();
 for(i=1;i<=3;i=i+1)begin
  scenario=10+i;select_obj(i);gesture(4,1,1);wait(status[3:0]==5);pre_tick=ticks;
  wait(status[3:0]==4 && status[6:4]==2);if(ticks-pre_tick<2499)$fatal(1,"PRE/PALM timing changed");
  blind_watch=1;gesture(7,0,0);wait(dones==i);blind_watch=0;
  if(fl || status[3:0]!=1)$fatal(1,"Normal color failure");$fdisplay(trace,"END %0d DONE",scenario);
 end
 if(status[28:26]!=0)$fatal(1,"Delivered inventory");
 $display("PASS: actual three-color table normal blind delivery and inventory; PRE2000/PALM500 retained");
 for(i=1;i<=3;i=i+1)begin
  reset_all();scenario=20+i;select_obj(i);wait(status[3:0]==5);
  base_moves=moves;gesture(5,1,0);wait_ticks(600);gesture(0,1,0);wait_ticks(20);gesture(5,1,0);wait_ticks(600);
  if(dut.cancel_req || moves!=base_moves)$fatal(1,"Short FIST cancelled");
  gesture(0,1,0);wait_ticks(5);gesture(5,1,0);wait(status[3:0]==8 || fl);gesture(4,1,1);returned(i,1);
 end
 $display("PASS: each color at PRE returns to its own slot, opens once, reaches HOME, restores inventory; short FIST resets and PALM cannot resume delivery");
 for(i=1;i<=3;i=i+1)begin
  reset_all();scenario=30+i;deliver_cycles=64000;select_obj(i);gesture(4,1,1);wait(status[3:0]==4 && status[6:4]==2);wait(busy>0);
  pre_tick=ticks;gesture(5,1,0);wait(status[3:0]==8 || fl);if(ticks-pre_tick<999)$fatal(1,"FIST shortened");returned(i,1);
 end
 $display("PASS: each color cancelled mid-delivery pauses partial move and reverses exact issued starts through slot release to HOME");
 reset_all();scenario=41;out_cycles=64000;select_obj(1);gesture(5,1,0);wait(status[3:0]==8 || fl);returned(1,0);
 $display("PASS: unheld cancellation returns HOME and restores stock");
 reset_all();scenario=42;select_obj(1);wait(dut.sg_flags[0] && dut.ph==1 && dut.ms==20);out_cycles=64000;wait(busy>0);gesture(5,1,0);wait(status[3:0]==8 || fl);returned(1,1);
 $display("PASS: cancellation during grasp reopens at the original slot and returns HOME");
 reset_all();scenario=43;release_cycles=64000;go_deliver();wait(status[6:4]==3 && status[10]);gesture(5,1,0);wait_ticks(1100);
 if(dut.cancel_req || fl)$fatal(1,"Post-release FIST changed");wait(dones==1);$fdisplay(trace,"END %0d DONE",scenario);
 $display("PASS: ordinary FIST after release commitment remains ignored");
 reset_all();scenario=44;reverse_cycles=64000;select_obj(1);wait(status[3:0]==5);gesture(5,1,0);wait(status[3:0]==8);estop=0;repeat(2)@(negedge clk);if(!fl)$fatal(1,"D5 return protection lost");
 reset_all();scenario=45;reverse_cycles=64000;select_obj(1);wait(status[3:0]==5);gesture(5,1,0);wait(status[3:0]==8);alive=0;wait(fl);if(fault[7:0]!=7)$fatal(1,"COMM return protection lost");
 $display("PASS: D5 and communication faults interrupt return without fabricated successful inventory restoration");
 $fclose(trace);$finish;
end
endmodule
