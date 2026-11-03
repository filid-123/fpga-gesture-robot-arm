`timescale 1ns/1ps
module tb_s4_handover;
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
integer busy=0,moves=0,dones=0,pauses=0,resumes=0,base_moves=0,pre_tick=0,release_tick=0,i,j;
integer out_cycles=96,deliver_cycles=3200,release_cycles=96,remaining=0;
wire[31:0]plstatus=32'h180|ps;
wire[31:0]status,fault,interaction,timers;wire[15:0]ev;wire fl,owner;
s4_task_fsm #(.SLOT_INVENTORY(1),.PALM_CONTINUITY(1),.TIMED_WALKTHROUGH(1),.HANDOVER_V2(1))dut(
 .clk(clk),.rst_n(rst),.tick(tick),.period_pulse(period_pulse),.vis_valid(vv),.vis_class(cls),.vis_changed(vc),.vis_window_ok(vw),.estop_ok(estop),
 .cmd_valid(cv),.cmd_index(ci),.cmd_done(cd),.cmd_result(cr),.cfg_mode_b(1'b0),.cfg_require_line(1'b1),.cfg_vision_sim(1'b0),.cfg_hold_policy(1'b1),
 .cfg_rearm_mask(8'h81),.cfg_select_mask(8'h0e),.cfg_t_palm_hold(16'd50),.cfg_t_palm_wait(16'd0),.cfg_t_fist_hold(16'd100),.cfg_t_pre_wait(16'd200),.cfg_blind_periods(16'd1),
 .cfg_t_arrival(16'd2),.cfg_t_comm(16'd30),.cfg_t_path_wait(16'd1000),.cfg_t_heartbeat(16'd0),.cfg_move_margin(16'd1000),
 .cfg_arrival_mask(6'h3f),.cfg_home_kp(6'd0),.cfg_predelivery_kp(6'd7),.cfg_joint_min({6{32'hffff0000}}),.cfg_joint_max({6{32'h00010000}}),
 .cfg_paths(paths),.cfg_tray_exit(1'b0),.cfg_tray_path(12'd0),.req_object(req),.req_task_id(16'd0),.path_object(2'd0),.path_task_id(16'd0),
 .kp_raddr(ka),.kp_rdata(kd),.seg_raddr(sa),.seg_rdata(sd),.fifo_rdata(32'd0),.fifo_count(6'd0),
 .op_valid(ov),.op_ready(1'b1),.op_code(oc),.op_target(ot),.op_n(on),.op_na(on_a),.op_profile(opf),.op_source(ops),
 .op_done(od),.op_ok(1'b1),.op_timeout(1'b0),.st_s1_status(32'h302d),.st_fb_masks(32'h3f),.st_fb_age({seq,16'd0}),
 .st_pl_status(plstatus),.st_pl_error(32'd0),.st_last(last),.fault_latched(fl),.owner_s4(owner),.status_word(status),.fault_word(fault),.event_set(ev),
 .interaction_status(interaction),.interaction_timers(timers));
always @(posedge clk)begin
 od<=0;
 if(!rst)begin ps<=0;last<=0;target<=0;seq<=0;busy<=0;moves<=0;dones<=0;pauses<=0;resumes<=0;remaining<=0;end
 else begin
  if(ov)begin
   od<=1;
   if(oc==0 && alive)seq<=seq+1;
   if(oc==1)begin moves<=moves+1;target<=ot;ps<=2;
    busy<=(dut.ph==2)?deliver_cycles:((dut.ph==3)?release_cycles:out_cycles);
   end
   if(oc==2 && ps==2)begin ps<=3;remaining<=busy;busy<=0;pauses<=pauses+1;for(integer a=0;a<6;a=a+1)last[32*a+:32]<=(last[32*a+:32]+target[32*a+:32])>>1;end
   if(oc==3 && ps==3)begin ps<=2;busy<=remaining;resumes<=resumes+1;end
   if(oc==4)begin ps<=0;busy<=0;end
   if(oc==5)begin ps<=6;busy<=0;end
  end
  if(busy>0 && !(ov && (oc==2 || oc==4 || oc==5)))begin busy<=busy-1;if(busy==1)begin ps<=4;last<=target;end end
  if(ev[0])dones<=dones+1;
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
 begin blind_watch=0;rst=0;alive=1;estop=1;cls=0;vc=0;vw=0;vv=1;cv=0;out_cycles=96;deliver_cycles=6400;release_cycles=96;
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
initial begin
 for(i=0;i<512;i=i+1)km[i]=0;for(i=0;i<128;i=i+1)sm[i]=0;
 for(i=1;i<=9;i=i+1)for(j=0;j<6;j=j+1)km[i*8+j]=i*100;
 for(i=0;i<12;i=i+1)begin
  paths[i*12+:12]={6'd1,i[5:0]};
  if(i<3)sm[i*2]=(2<<24)|(1<<16)|(i+1);
  else if(i<6)sm[i*2]=(3<<24)|(1<<16)|(i+1);
  else if(i<9)sm[i*2]=(2<<24)|(1<<16)|7;
  else if(i==9)sm[i*2]=(2<<24)|(1<<16)|8;
  else if(i==10)sm[i*2]=(2<<24)|(1<<16)|9;
  else sm[i*2]=(2<<24)|(1<<16);
  sm[i*2+1]=(1<<16)|4;
 end
 reset_all();
 for(i=1;i<=3;i=i+1)begin
  select_obj(i);gesture(4,1,1);wait(status[3:0]==5);pre_tick=ticks;
  wait(status[3:0]==4 && status[6:4]==2);if(ticks-pre_tick<249)$fatal(1,"PRE wait or palm hold skipped %0d",ticks-pre_tick);
  blind_watch=1;gesture(7,0,0);
  wait(dones==i);blind_watch=0;if(fl || status[3:0]!=1)$fatal(1,"COLOR did not complete without PALM after PRE");
 end
 if(status[28:26]!=0)$fatal(1,"DELIVERED slots not empty");
 $display("PASS: three colors complete; PRE minimum/hold retained, PALM removed immediately after trigger still releases/retreats, empty inventory");

 reset_all();select_obj(1);wait(status[3:0]==5);base_moves=moves;
 gesture(5,1,0);wait_ticks(60);gesture(0,1,0);wait_ticks(10);gesture(5,1,0);wait_ticks(60);
 if(status[3:0]!=5 || dut.cancel_req)$fatal(1,"SHORT FIST cancelled");
 gesture(0,1,0);wait_ticks(2);pre_tick=ticks;gesture(5,1,0);wait(status[3:0]==9 || fl);
 if(fl || ticks-pre_tick<99 || !status[9] || status[10] || moves!=base_moves)$fatal(1,"SUSTAINED FIST hold failed");
 gesture(4,1,1);wait_ticks(500);if(status[3:0]!=9 || resumes!=0)$fatal(1,"PALM resumed cancelled FIST");
 $display("PASS: separated short FIST bursts reset; sustained FIST cancels held task once; PALM never resumes its HALT");

 reset_all();deliver_cycles=64000;go_deliver();blind_watch=1;
 gesture(3,1,0);wait_ticks(400);gesture(5,1,0);wait_ticks(60);gesture(0,1,0);wait_ticks(100);gesture(7,0,0);
 wait(dones==1);blind_watch=0;if(fl || status[3:0]!=1 || pauses!=0 || resumes!=0)$fatal(1,"BLIND delivery incomplete");
 $display("PASS: prolonged THREE/BG/NO_DETECTION and short FIST after PRE do not pause/cancel blind delivery; release completes");

 reset_all();deliver_cycles=64000;go_deliver();pre_tick=ticks;gesture(5,1,0);
 wait(status[3:0]==9 || fl);if(fl || ticks-pre_tick<99 || !dut.cancel_req || !status[9] || status[10])$fatal(1,"FIST during blind delivery failed");
 gesture(4,1,1);wait_ticks(500);if(status[3:0]!=9)$fatal(1,"PALM resumed cancelled blind delivery");
 $display("PASS: sustained FIST still cancels blind delivery and holds without PALM auto-resume");

 reset_all();out_cycles=6400;select_obj(1);gesture(5,1,0);wait(status[3:0]==8 || status[3:0]==9 || fl);
 if(status[3:0]==9 || fl)$fatal(1,"UNHELD FIST incorrectly held/faulted");
 wait(status[3:0]==1);if(!status[26] || status[9])$fatal(1,"UNHELD cancellation did not return inventory");
 $display("PASS: sustained FIST before grasp retraces and restores selected slot");

 reset_all();go_deliver();estop=0;@(negedge clk);@(negedge clk);if(!fl)$fatal(1,"D5 not immediate");
 reset_all();select_obj(1);alive=0;wait(fl);if(fault[7:0]!=7)$fatal(1,"COMM fault lost");
 $display("PASS: D5 immediate and real feedback-loss faults retained");$finish;
end
endmodule
