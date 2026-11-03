`timescale 1ns/1ps
module tb_s4_timed;
reg clk=0;always #5 clk=~clk;
reg rst=0;integer cyc=0,ticks=0;wire tick=(cyc%32)==31;
always @(posedge clk) begin cyc<=cyc+1;if(tick)ticks<=ticks+1;end
reg vv=1,vc=0,vw=0,estop=1;reg[2:0] cls=0;
reg cv=0;reg[3:0] ci=0;wire cd;wire[3:0] cr;
reg[1:0] req=0;reg[143:0] paths=0;
wire[8:0] ka;wire[6:0] sa;reg[31:0] kd=0,sd=0;
reg[31:0] km[0:511],sm[0:127];
always @(posedge clk)begin kd<=km[ka];sd<=sm[sa];end
wire ov;wire[2:0] oc;wire[191:0] ot;wire[15:0] on,on_a;wire opf,ops;
reg od=0;reg[191:0] last=0;reg[2:0] ps=0;reg[15:0] seq=0;reg alive=1;
integer busy=0,moves=0,dones=0,prev_settle=0,done_tick=0,i,j,base_moves;
reg[31:0] plstatus;always @* plstatus=32'h180|ps;
wire[31:0] status,fault;wire[15:0] ev;wire fl,owner;
s4_task_fsm #(.SLOT_INVENTORY(1),.PALM_CONTINUITY(1),.TIMED_WALKTHROUGH(1)) dut(
 .clk(clk),.rst_n(rst),.tick(tick),.period_pulse(1'b0),.vis_valid(vv),.vis_class(cls),.vis_changed(vc),.vis_window_ok(vw),.estop_ok(estop),
 .cmd_valid(cv),.cmd_index(ci),.cmd_done(cd),.cmd_result(cr),.cfg_mode_b(1'b0),.cfg_require_line(1'b1),.cfg_vision_sim(1'b0),.cfg_hold_policy(1'b1),
 .cfg_rearm_mask(8'h81),.cfg_select_mask(8'h0e),.cfg_t_palm_hold(16'd3),.cfg_t_palm_wait(16'd0),.cfg_blind_periods(16'd4),
 .cfg_t_arrival(16'd2),.cfg_t_comm(16'd30),.cfg_t_path_wait(16'd100),.cfg_t_heartbeat(16'd0),.cfg_move_margin(16'd50),
 .cfg_arrival_mask(6'h3f),.cfg_home_kp(6'd0),.cfg_predelivery_kp(6'd7),.cfg_joint_min({6{32'hffff0000}}),.cfg_joint_max({6{32'h00010000}}),
 .cfg_paths(paths),.cfg_tray_exit(1'b0),.cfg_tray_path(12'd0),.req_object(req),.req_task_id(16'd0),.path_object(2'd0),.path_task_id(16'd0),
 .kp_raddr(ka),.kp_rdata(kd),.seg_raddr(sa),.seg_rdata(sd),.fifo_rdata(32'd0),.fifo_count(6'd0),
 .op_valid(ov),.op_ready(1'b1),.op_code(oc),.op_target(ot),.op_n(on),.op_na(on_a),.op_profile(opf),.op_source(ops),
 .op_done(od),.op_ok(1'b1),.op_timeout(1'b0),.st_s1_status(32'h302d),.st_fb_masks(32'h3f),.st_fb_age({seq,16'd0}),
 .st_pl_status(plstatus),.st_pl_error(32'd0),.st_last(last),.fault_latched(fl),.owner_s4(owner),.status_word(status),.fault_word(fault),.event_set(ev));
always @(posedge clk) begin
 od<=0;
 if(!rst)begin ps<=0;last<=0;seq<=0;busy<=0;moves<=0;dones<=0;prev_settle<=0;done_tick<=0;end
 else begin
  if(ov)begin
   od<=1;
   if(oc==0 && alive)seq<=seq+1;
   if(oc==1)begin
    if(moves>0 && ticks-done_tick<prev_settle)$fatal(1,"FIXED_SETTLE_SHORT actual=%0d expected=%0d",ticks-done_tick,prev_settle);
    moves<=moves+1;last<=ot;ps<=2;busy<=3;prev_settle<=dut.mv_flags[7:2]*16;
   end
   if(oc==5)begin ps<=6;busy<=0;end
  end
  if(busy>0)begin busy<=busy-1;if(busy==1)begin ps<=4;done_tick<=ticks;end end
  if(ev[0])begin
   if(ticks-done_tick<prev_settle)$fatal(1,"LAST_SETTLE_SHORT");dones<=dones+1;
  end
 end
 if(cyc>12_000_000)$fatal(1,"TIMEOUT status=%x fault=%x",status,fault);
end
task cmd(input[3:0] c);
 begin @(negedge clk);ci=c;cv=1;@(negedge clk);cv=0;wait(cd);if(cr!=0)$fatal(1,"CMD %0d result %0d",c,cr);@(negedge clk);end
endtask
task reset_all;
 begin rst=0;alive=1;estop=1;cls=0;vc=0;vw=0;cv=0;repeat(8)@(negedge clk);rst=1;repeat(5)@(negedge clk);
 for(j=1;j<=3;j=j+1)begin req=j;cmd(11);end
 cmd(0);wait(status[3:0]==1);repeat(5)@(negedge clk);
 end
endtask
task select_obj(input[1:0] obj);
 begin cls=0;vc=0;vw=0;repeat(5)@(negedge clk);cls=obj;vc=1;@(negedge clk);vc=0;wait(status[3:0]==5 || status[3:0]==10);if(fl)$fatal(1,"PRE fault %x",fault);end
endtask
initial begin
 for(i=0;i<512;i=i+1)km[i]=0;for(i=0;i<128;i=i+1)sm[i]=0;
 for(i=1;i<=9;i=i+1)for(j=0;j<6;j=j+1)km[i*8+j]=i*100;
 for(i=0;i<12;i=i+1)begin
  paths[i*12+:12]={6'd1,i[5:0]};
  if(i<3)sm[i*2]=(8'h1e<<24)|(1<<16)|(i+1);
  else if(i<6)sm[i*2]=(8'hcb<<24)|(1<<16)|(i+1);
  else if(i<9)sm[i*2]=(8'h1e<<24)|(1<<16)|7;
  else if(i==9)sm[i*2]=(8'h1e<<24)|(1<<16)|8;
  else if(i==10)sm[i*2]=(8'hca<<24)|(1<<16)|9;
  else sm[i*2]=(8'h1e<<24)|(1<<16);
  sm[i*2+1]=(1<<16)|4;
 end
 reset_all();
 for(i=1;i<=3;i=i+1)begin
  select_obj(i);
  if(i==1)begin base_moves=moves;repeat(70_000)begin @(negedge clk);if(tick && (status[3:0]!=5 || fl))$fatal(1,"WAIT_INTERRUPTED");end
   // More than65535 *ticks*, exercising the saturated infinite-wait counter.
   base_moves=ticks;while(ticks-base_moves<70_000)begin @(negedge clk);if(status[3:0]!=5 || fl)$fatal(1,"PALM_WAIT_WRAPPED");end
  end
  cls=4;vw=1;vc=1;@(negedge clk);vc=0;wait(dones==i);if(fl || status[3:0]!=1)$fatal(1,"COLOR_INCOMPLETE");
 end
 if(status[28:26]!=0 || moves!=18)$fatal(1,"INVENTORY_OR_MOVE_COUNT %x %0d",status,moves);
 $display("PASS: ABI3405 three colors, actual arrival_mask0 versus configured3f, fixed352/800ms, infinite PALM wait70k ticks, empty slots");
 reset_all();select_obj(1);alive=0;wait(fl);wait(status[3:0]==10);if(fault[7:0]!=7)$fatal(1,"COMM_NOT_RETAINED %x",fault);
 $display("PASS: ABI3405 feedback loss still faults");
 reset_all();select_obj(1);base_moves=moves;@(negedge clk);cls=5;vc=1;@(negedge clk);vc=0;wait(status[3:0]==9 || fl);if(fl || !status[9] || moves!=base_moves)$fatal(1,"FIST_HOLD_FAILED");
 $display("PASS: ABI3405 FIST keeps held object, no automatic release/return");
 reset_all();select_obj(1);estop=0;@(negedge clk);@(negedge clk);if(!fl)$fatal(1,"D5_NOT_IMMEDIATE");
 $display("PASS: ABI3405 D5 immediate fault retained");$finish;
end
endmodule
