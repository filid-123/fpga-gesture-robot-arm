`timescale 1ns/1ps
module tb_a_safety;
reg clk=0;always #5 clk=~clk;reg rst=0,vv=0,vw=0,simv=0;reg[31:0]s1s=32'h1000;reg [2:0] vc=7;
s4_task_fsm #(.TRAY_EXIT(1),.A_TRAY_EXIT(1),.PALM_CONTINUITY(1)) dut(.clk(clk),
.rst_n(rst),
.tick('0),
.period_pulse('0),
.vis_valid(vv),
.vis_class(vc),
.vis_changed('0),
.vis_window_ok(vw),
.estop_ok(1'b1),
.cmd_valid('0),
.cmd_index('0),
.cfg_mode_b('0),
.cfg_require_line('0),
.cfg_vision_sim(simv),
.cfg_hold_policy('0),
.cfg_rearm_mask('0),
.cfg_select_mask('0),
.cfg_t_palm_hold(16'd1),
.cfg_t_palm_wait(16'd15000),
.cfg_blind_periods('0),
.cfg_t_arrival('0),
.cfg_t_comm('0),
.cfg_t_path_wait('0),
.cfg_t_heartbeat('0),
.cfg_move_margin('0),
.cfg_arrival_mask('0),
.cfg_home_kp('0),
.cfg_predelivery_kp('0),
.cfg_joint_min('0),
.cfg_joint_max('0),
.cfg_paths('0),
.cfg_tray_exit('0),
.cfg_tray_path(12'h0c0),
.req_object('0),
.req_task_id('0),
.path_object('0),
.path_task_id('0),
.kp_rdata('0),
.seg_rdata('0),
.fifo_rdata('0),
.fifo_count('0),
.op_ready(1'b1),
.op_done('0),
.op_ok(1'b1),
.op_timeout('0),
.st_s1_status(s1s),
.st_fb_masks('0),
.st_fb_age('0),
.st_pl_status('0),
.st_pl_error('0),
.st_last('0));
task init;begin rst=0;repeat(3)@(negedge clk);rst=1;@(negedge clk);end endtask
initial begin
// Directed boundary seeds exercise the real transition/action logic, independently of the AXI link.
init;dut.st=4;dut.ms=20;dut.ph=3;dut.released=0;dut.holding=1;
@(negedge clk);if(dut.st!=5 || !dut.release_wait || dut.op_valid || dut.released)$fatal(1,"FAIL: missing PALM before release");
init;dut.st=4;dut.ms=21;dut.ph=3;dut.released=0;dut.holding=1;
@(negedge clk);if(dut.st!=5 || dut.op_valid || dut.released)$fatal(1,"FAIL: PALM loss during pre-release POLL");
init;vv=1;vw=1;vc=4;dut.st=4;dut.ms=21;dut.ph=3;dut.released=0;
@(negedge clk);if(!dut.op_valid || dut.op_code!=1 || !dut.released)$fatal(1,"FAIL: qualified PALM release commit");
init;vv=0;vw=0;vc=7;dut.st=5;dut.ms=18;dut.ph=0;dut.holding=1;dut.released=0;dut.cancel_req=1;dut.tray_ok_task=1;dut.sp=0;dut.sp_deliver=0;
@(negedge clk);if(dut.ph!=5 || !dut.tray_active || dut.cancel_req || dut.blind_req)$fatal(1,"FAIL: valid A tray cancellation");
init;dut.st=5;dut.ms=18;dut.ph=0;dut.holding=1;dut.released=0;dut.cancel_req=1;dut.tray_ok_task=0;
@(negedge clk);if(dut.st!=9 || dut.op_valid)$fatal(1,"FAIL: no validated tray must HOLD");
init;dut.st=4;dut.ms=20;dut.ph=1;dut.mv_kind=0;dut.sg_flags=1;
@(negedge clk);if(!dut.holding)$fatal(1,"FAIL: holding conservative before grasp commit");
init;s1s=32'h3025;simv=1;dut.ms=12;
@(negedge clk);if(dut.refuse_code!=3 || !dut.event_set[2])$fatal(1,"FAIL: LINE must reject simulated vision");
$display("PASS: A_SAFETY release before/after POLL, PALM commit, A tray, invalid tray hold, conservative grasp, LINE rejects simulated vision");$finish;
end endmodule
