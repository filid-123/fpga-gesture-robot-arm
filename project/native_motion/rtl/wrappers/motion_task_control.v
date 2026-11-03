// Structural wrapper: original instances, parameters and cycles preserved.
`timescale 1ns/1ps
module motion_task_control #(
    parameter integer HAS_ROARM          = 1,
    parameter integer HAS_SO101          = 1,
    parameter integer DEBOUNCE_CYCLES    = 1_000_000,
    parameter integer MIN_PERIOD_CYCLES  = 512,
    parameter integer AXI_TIMEOUT_CYCLES = 4096,
    parameter integer VIS_ASYNC          = 1,
    parameter integer TRAY_EXIT          = 0,
    parameter integer A_TRAY_EXIT        = 0,
    parameter integer PALM_CONTINUITY    = 0,
    parameter integer SLOT_INVENTORY     = 0,
    parameter integer TIMED_WALKTHROUGH  = 0,
    parameter integer HANDOVER_V2        = 0,
    parameter integer HAND_ALIGN_REGIONS = 3,
    parameter integer HAND_ALIGN_LOCATOR = 0,
    parameter integer HAND_ALIGN         = 0,
    parameter integer CONTINUOUS_HAND = 0,
    parameter integer AUTO_RESTOCK = 0,
    parameter integer FAST_B = 0,
    parameter integer DYNAMIC_B = 0,
    parameter integer SMOOTH_PROFILE = 0,
    parameter integer ROARM_FEEDBACK_EVERY = 1
)(
    output wire  align_accept,
    output wire [3:0] align_accepted_cell,
    output wire [31:0] align_accepted_revision,
    input wire [31:0] align_cells,
    output wire  align_palm_confirmed,
    output wire  align_settled,
    output wire  align_waiting,
    input wire  any_drop,
    output wire [191:0] cfg_amax,
    output wire  cfg_mode_b,
    output wire [31:0] cfg_period,
    output wire [31:0] cfg_stall,
    output wire [31:0] cfg_tick_prescale,
    output wire  cfg_unlock,
    output wire  cfg_vision_sim,
    output wire [191:0] cfg_vmax,
    input wire  clk,
    input wire [13:0] dropped_info,
    input wire  estop_s2,
    output wire [15:0] event_fsm,
    input wire [15:0] event_set,
    input wire  f_changed,
    input wire [2:0] f_class,
    input wire  f_valid,
    input wire  f_window,
    output wire  fault_latched,
    output wire  fifo_unlock,
    input wire [3:0] ha_cell,
    input wire  ha_ready,
    input wire [31:0] ha_revision,
    input wire  ha_valid,
    output wire [31:0] interaction_status,
    output wire  irq_s4,
    input wire [31:0] map_active_revision,
    output wire [3:0] map_cell,
    output wire  map_commit,
    input wire  map_committed,
    input wire  map_error,
    input wire [3:0] map_error_code,
    input wire  map_locked,
    output wire [15:0] map_mask,
    input wire  map_ready,
    output wire [31:0] map_revision,
    output wire [31:0] map_wdata,
    output wire [1:0] map_word,
    output wire  map_write,
    input wire [31:0] native_age,
    input wire [31:0] native_arm_error,
    input wire [31:0] native_arm_status,
    output wire [2:0] native_code,
    input wire  native_done,
    input wire [31:0] native_frames,
    input wire [191:0] native_last,
    input wire [31:0] native_masks,
    input wire  native_ok,
    input wire [31:0] native_pl_error,
    input wire [31:0] native_pl_index,
    input wire [31:0] native_pl_status,
    input wire  native_ready,
    output wire  native_snap,
    input wire  native_snap_done,
    input wire  native_snap_ready,
    output wire  native_valid,
    output wire [2:0] op_code,
    output wire [15:0] op_n,
    output wire [15:0] op_na,
    output wire  op_profile,
    output wire  op_source,
    output wire [191:0] op_target,
    output wire  op_valid,
    output wire  owner_s4,
    input wire  period_pulse,
    input wire  rst_n,
    input wire [11:0] s_axi_s4_araddr,
    output wire  s_axi_s4_arready,
    input wire  s_axi_s4_arvalid,
    input wire [11:0] s_axi_s4_awaddr,
    output wire  s_axi_s4_awready,
    input wire  s_axi_s4_awvalid,
    input wire  s_axi_s4_bready,
    output wire [1:0] s_axi_s4_bresp,
    output wire  s_axi_s4_bvalid,
    output wire [31:0] s_axi_s4_rdata,
    input wire  s_axi_s4_rready,
    output wire [1:0] s_axi_s4_rresp,
    output wire  s_axi_s4_rvalid,
    input wire [31:0] s_axi_s4_wdata,
    output wire  s_axi_s4_wready,
    input wire [3:0] s_axi_s4_wstrb,
    input wire  s_axi_s4_wvalid,
    output wire  sim_changed,
    output wire [2:0] sim_class,
    output wire  sim_valid,
    output wire  sim_window_ok,
    output wire [31:0] status_fsm,
    input wire [31:0] status_word,
    input wire [6:0] target_step,
    input wire  tick
);
wire [6:0] active_step;
wire [31:0] align_debug;
wire [15:0] cfg_align_n;
wire [15:0] cfg_align_na;
wire [511:0] cfg_align_pairs;
wire [5:0] cfg_arrival_mask;
wire [5:0] cfg_b_release_index;
wire  cfg_b_restock;
wire [HAND_ALIGN_REGIONS-1:0] cfg_banks_ready;
wire [15:0] cfg_blind_periods;
wire  cfg_hold_policy;
wire [5:0] cfg_home_kp;
wire [191:0] cfg_joint_max;
wire [191:0] cfg_joint_min;
wire [15:0] cfg_move_margin;
wire [143:0] cfg_paths;
wire [5:0] cfg_predelivery_kp;
wire [7:0] cfg_rearm_mask;
wire  cfg_require_line;
wire [47:0] cfg_restock_paths;
wire [17:0] cfg_restock_release_kps;
wire [7:0] cfg_select_mask;
wire [15:0] cfg_t_arrival;
wire [15:0] cfg_t_comm;
wire [15:0] cfg_t_fist_hold;
wire [15:0] cfg_t_heartbeat;
wire [15:0] cfg_t_palm_hold;
wire [15:0] cfg_t_palm_wait;
wire [15:0] cfg_t_path_wait;
wire [15:0] cfg_t_pre_wait;
wire  cfg_tray_exit;
wire [11:0] cfg_tray_path;
wire  cmd_done;
wire [3:0] cmd_done_index;
wire [3:0] cmd_index;
wire [3:0] cmd_result;
wire  cmd_valid;
wire [4:0] cnt_fsm;
wire [31:0] fault_word;
wire  fifo_clear;
wire [5:0] fifo_count;
wire [(DYNAMIC_B!=0?9:8)-1:0] fifo_raddr;
wire [31:0] fifo_rdata;
wire [31:0] interaction_timers;
wire [1:0] kp_bank;
wire  kp_mix_enable;
wire [8:0] kp_raddr;
wire [31:0] kp_rdata;
wire [15:0] last_task_id;
wire  op_done;
wire  op_ok;
wire  op_ready;
wire  op_timeout;
wire [1:0] path_object;
wire [15:0] path_task_id;
wire  poll_done;
wire [31:0] progress_word;
wire [1:0] req_object;
wire [15:0] req_task_id;
wire  restock_task;
wire [6:0] seg_raddr;
wire [31:0] seg_rdata;
wire [15:0] selected_task_id;
wire [31:0] st_fb_age;
wire [31:0] st_fb_masks;
wire [31:0] st_frames;
wire [191:0] st_last;
wire [31:0] st_pl_error;
wire [31:0] st_pl_index;
wire [31:0] st_pl_status;
wire [31:0] st_s1_error;
wire [31:0] st_s1_status;
s4_task_regs #(.TRAY_EXIT(TRAY_EXIT),.SLOT_INVENTORY(SLOT_INVENTORY),.TIMED_WALKTHROUGH(TIMED_WALKTHROUGH),.HANDOVER_V2(HANDOVER_V2),.HAND_ALIGN(HAND_ALIGN),.HAND_ALIGN_REGIONS(HAND_ALIGN_REGIONS),.HAND_ALIGN_LOCATOR(HAND_ALIGN_LOCATOR),.CONTINUOUS_HAND(CONTINUOUS_HAND),.AUTO_RESTOCK(AUTO_RESTOCK),.DYNAMIC_B(DYNAMIC_B),.FAST_B(FAST_B)) u_regs (
        .clk(clk), .rst_n(rst_n),
        .s_awaddr(s_axi_s4_awaddr), .s_awvalid(s_axi_s4_awvalid), .s_awready(s_axi_s4_awready),
        .s_wdata(s_axi_s4_wdata), .s_wstrb(s_axi_s4_wstrb), .s_wvalid(s_axi_s4_wvalid), .s_wready(s_axi_s4_wready),
        .s_bresp(s_axi_s4_bresp), .s_bvalid(s_axi_s4_bvalid), .s_bready(s_axi_s4_bready),
        .s_araddr(s_axi_s4_araddr), .s_arvalid(s_axi_s4_arvalid), .s_arready(s_axi_s4_arready),
        .s_rdata(s_axi_s4_rdata), .s_rresp(s_axi_s4_rresp), .s_rvalid(s_axi_s4_rvalid), .s_rready(s_axi_s4_rready),
        .irq(irq_s4),
        .cmd_valid(cmd_valid), .cmd_index(cmd_index), .cmd_done(cmd_done), .cmd_result(cmd_result),
        .cmd_done_index(cmd_done_index), .cfg_unlock(cfg_unlock), .fifo_unlock(fifo_unlock),
        .cfg_b_restock(cfg_b_restock),.cfg_b_release_index(cfg_b_release_index),.selected_task_id(selected_task_id),
        .cfg_mode_b(cfg_mode_b), .cfg_require_line(cfg_require_line), .cfg_hold_policy(cfg_hold_policy),
        .cfg_vision_sim(cfg_vision_sim), .cfg_rearm_mask(cfg_rearm_mask), .cfg_select_mask(cfg_select_mask),
        .cfg_tick_prescale(cfg_tick_prescale), .cfg_t_palm_hold(cfg_t_palm_hold), .cfg_t_palm_wait(cfg_t_palm_wait),
        .cfg_t_fist_hold(cfg_t_fist_hold),.cfg_t_pre_wait(cfg_t_pre_wait),
        .cfg_blind_periods(cfg_blind_periods), .cfg_t_arrival(cfg_t_arrival), .cfg_t_comm(cfg_t_comm),
        .cfg_t_path_wait(cfg_t_path_wait), .cfg_t_heartbeat(cfg_t_heartbeat), .cfg_move_margin(cfg_move_margin),
        .cfg_period(cfg_period), .cfg_stall(cfg_stall), .cfg_arrival_mask(cfg_arrival_mask),
        .cfg_home_kp(cfg_home_kp), .cfg_predelivery_kp(cfg_predelivery_kp), .cfg_joint_min(cfg_joint_min),
        .cfg_joint_max(cfg_joint_max), .cfg_vmax(cfg_vmax), .cfg_amax(cfg_amax), .cfg_paths(cfg_paths),.cfg_restock_paths(cfg_restock_paths),.cfg_restock_release_kps(cfg_restock_release_kps),.restock_task(restock_task),
        .cfg_tray_exit(cfg_tray_exit), .cfg_tray_path(cfg_tray_path),
        .req_object(req_object), .req_task_id(req_task_id), .path_object(path_object), .path_task_id(path_task_id),
        .sim_class(sim_class), .sim_valid(sim_valid), .sim_window_ok(sim_window_ok), .sim_changed(sim_changed),
        .kp_raddr(kp_raddr), .kp_rdata(kp_rdata), .seg_raddr(seg_raddr), .seg_rdata(seg_rdata),
        .fifo_raddr(fifo_raddr), .fifo_rdata(fifo_rdata), .fifo_count(fifo_count), .fifo_clear(fifo_clear),
        .status_word(status_word), .fault_word(fault_word), .progress_word(progress_word),
        .interaction_status(interaction_status),.interaction_timers(interaction_timers),
        .kp_mix_enable(kp_mix_enable),.active_step(active_step),.target_step(target_step),.kp_bank(kp_bank),.cfg_align_pairs(cfg_align_pairs),.cfg_align_n(cfg_align_n),.cfg_align_na(cfg_align_na),.cfg_banks_ready(cfg_banks_ready),
        .map_write(map_write),.map_commit(map_commit),.map_cell(map_cell),.map_word(map_word),.map_wdata(map_wdata),.map_revision(map_revision),.map_mask(map_mask),
        .map_ready(map_ready),.map_committed(map_committed),.map_error(map_error),.map_locked(map_locked),.map_error_code(map_error_code),.map_active_revision(map_active_revision),.align_debug(align_debug),.align_cells(align_cells),
        .event_set(event_set), .cnt_inc({any_drop, cnt_fsm}), .dropped_info(dropped_info), .poll_done(poll_done),
        .last_task_id(last_task_id),
        .t_s1_status(st_s1_status), .t_s1_error(st_s1_error), .t_fb_masks(st_fb_masks), .t_fb_age(st_fb_age),
        .t_frames(st_frames), .t_pl_status(st_pl_status), .t_pl_error(st_pl_error), .t_pl_index(st_pl_index),
        .t_last(st_last));
s4_task_fsm #(.TRAY_EXIT(TRAY_EXIT),.A_TRAY_EXIT(A_TRAY_EXIT),.PALM_CONTINUITY(PALM_CONTINUITY),.SLOT_INVENTORY(SLOT_INVENTORY),.TIMED_WALKTHROUGH(TIMED_WALKTHROUGH),.HANDOVER_V2(HANDOVER_V2),.HAND_ALIGN(HAND_ALIGN),.HAND_ALIGN_REGIONS(HAND_ALIGN_REGIONS),.HAND_ALIGN_LOCATOR(HAND_ALIGN_LOCATOR),.CONTINUOUS_HAND(CONTINUOUS_HAND),.AUTO_RESTOCK(AUTO_RESTOCK),.DYNAMIC_B(DYNAMIC_B),.FAST_B(FAST_B)) u_fsm (
        .clk(clk), .rst_n(rst_n), .tick(tick), .period_pulse(period_pulse),
        .cfg_align_pairs(cfg_align_pairs),.cfg_align_n(cfg_align_n),.cfg_align_na(cfg_align_na),.cfg_banks_ready(cfg_banks_ready),
        .align_target_step(target_step),.active_step(active_step),.kp_mix_enable(kp_mix_enable),
        .align_target_valid(ha_valid && map_committed),.align_target_cell(ha_cell),.align_target_revision(ha_revision),.align_delivery_ready(ha_ready),
        .align_accepted_cell(align_accepted_cell),.align_accepted_revision(align_accepted_revision),.align_accept(align_accept),.align_waiting(align_waiting),.align_settled(align_settled),.align_palm_confirmed(align_palm_confirmed),.kp_bank(kp_bank),.align_debug(align_debug),
        .vis_valid(f_valid), .vis_class(f_class), .vis_changed(f_changed), .vis_window_ok(f_window),
        .estop_ok(estop_s2),
        .cmd_valid(cmd_valid), .cmd_index(cmd_index), .cmd_done(cmd_done), .cmd_result(cmd_result),
        .cmd_done_index(cmd_done_index),
        .cfg_b_restock(cfg_b_restock),.cfg_b_release_index(cfg_b_release_index),.selected_task_id(selected_task_id),
        .cfg_mode_b(cfg_mode_b), .cfg_require_line(cfg_require_line), .cfg_vision_sim(cfg_vision_sim), .cfg_hold_policy(cfg_hold_policy),
        .cfg_rearm_mask(cfg_rearm_mask), .cfg_select_mask(cfg_select_mask), .cfg_t_palm_hold(cfg_t_palm_hold),
        .cfg_t_fist_hold(cfg_t_fist_hold),.cfg_t_pre_wait(cfg_t_pre_wait),
        .cfg_t_palm_wait(cfg_t_palm_wait), .cfg_blind_periods(cfg_blind_periods), .cfg_t_arrival(cfg_t_arrival),
        .cfg_t_comm(cfg_t_comm), .cfg_t_path_wait(cfg_t_path_wait), .cfg_t_heartbeat(cfg_t_heartbeat),
        .cfg_move_margin(cfg_move_margin), .cfg_arrival_mask(cfg_arrival_mask), .cfg_home_kp(cfg_home_kp),
        .cfg_predelivery_kp(cfg_predelivery_kp), .cfg_joint_min(cfg_joint_min), .cfg_joint_max(cfg_joint_max),
        .cfg_paths(cfg_paths),.cfg_restock_paths(cfg_restock_paths),.cfg_restock_release_kps(cfg_restock_release_kps),.restock_task(restock_task), .cfg_tray_exit(cfg_tray_exit), .cfg_tray_path(cfg_tray_path),
        .req_object(req_object), .req_task_id(req_task_id), .path_object(path_object),
        .path_task_id(path_task_id),
        .kp_raddr(kp_raddr), .kp_rdata(kp_rdata), .seg_raddr(seg_raddr), .seg_rdata(seg_rdata),
        .fifo_raddr(fifo_raddr), .fifo_rdata(fifo_rdata), .fifo_count(fifo_count), .fifo_clear(fifo_clear),
        .op_valid(op_valid), .op_ready(op_ready), .op_code(op_code), .op_target(op_target), .op_n(op_n),
        .op_na(op_na), .op_profile(op_profile), .op_source(op_source), .op_done(op_done), .op_ok(op_ok),
        .op_timeout(op_timeout), .st_s1_status(st_s1_status), .st_fb_masks(st_fb_masks), .st_fb_age(st_fb_age),
        .st_pl_status(st_pl_status), .st_pl_error(st_pl_error), .st_last(st_last),
        .fault_latched(fault_latched), .owner_s4(owner_s4), .cfg_unlock(cfg_unlock), .fifo_unlock(fifo_unlock),
        .status_word(status_fsm), .fault_word(fault_word), .progress_word(progress_word),
        .interaction_status(interaction_status),.interaction_timers(interaction_timers),
        .event_set(event_fsm), .cnt_inc(cnt_fsm), .poll_done_pulse(poll_done), .last_task_id(last_task_id));
s4_motion_link #(.TIMEOUT_CYCLES(AXI_TIMEOUT_CYCLES)) u_link (
        .clk(clk), .rst_n(rst_n),
        .op_valid(op_valid), .op_ready(op_ready), .op_code(op_code), .op_target(op_target), .op_n(op_n),
        .op_na(op_na), .op_profile(op_profile), .op_source(op_source), .op_done(op_done), .op_ok(op_ok),
        .op_timeout(op_timeout), .inhibit(fault_latched),
        .cfg_period(cfg_period), .cfg_stall(cfg_stall), .cfg_vmax(cfg_vmax), .cfg_amax(cfg_amax),
        .st_s1_status(st_s1_status), .st_s1_error(st_s1_error), .st_fb_masks(st_fb_masks), .st_fb_age(st_fb_age),
        .st_frames(st_frames), .st_pl_status(st_pl_status), .st_pl_error(st_pl_error), .st_pl_index(st_pl_index),
        .st_last(st_last),
        .native_valid(native_valid), .native_ready(native_ready), .native_code(native_code),
        .native_done(native_done), .native_ok(native_ok), .native_snap(native_snap),
        .native_snap_ready(native_snap_ready), .native_snap_done(native_snap_done),
        .arm_status(native_arm_status), .arm_error(native_arm_error), .fb_masks(native_masks),
        .fb_age(native_age), .frames(native_frames), .pl_status(native_pl_status),
        .pl_error(native_pl_error), .pl_index(native_pl_index), .last_data(native_last));
endmodule
