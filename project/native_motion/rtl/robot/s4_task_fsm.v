// ============================================================================
// Block Name : s4_task_fsm
// Description: Task state machine of the Phase 3 S4 PL task controller.  Event-
//              level equivalent of ps/robot/s4_task_reference.py (S4TaskModel);
//              the same names are used for the decision points:
//   M_NEXT  = next_action(): the single decision after every completed or
//             stopped move (retrace / partial retrace / HALT / next segment /
//             next phase / done);
//   M_MON   = the per-tick monitor on a fresh POLL (faults in the model's
//             order, heartbeat, FIST_CANCEL, blind window, WAIT_PALM, STOPPING,
//             check_done);
//   M_PRE*  = precheck (e-stop, poll, S1/planner status, HOME, table scan);
//   M_FETCH = segment fetch from the keypoint/segment tables or the FIFO.
// Every MOVE is preceded by a POLL, so the link writes START = LAST_DELIVERED of
// that poll and the retrace stack stores exactly that start pose.
// A fault (any source) sets fault_latched at once: motion_enable (top) drops in
// the same cycle, the link refuses MOVE/RESUME and suppresses a START that was
// not yet written; the FSM then sends planner ESTOP (not for AXI_ERROR) and
// stays in FAULT until RELEASE (ownership back to the PS) and FAULT_CLEAR.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz)
// Tray-exit patch (TRAY_EXIT = 1 only; see ps/robot/s4_task_reference.py "Tray exit"): in mode B,
// with cfg_tray_exit and a PATH_TRAY path that passed the PATH_COMMIT scan, a cancel while holding
// finishes the committed OUT path to PRE_DELIVERY (or retraces DELIVER back to it) and then runs the
// fixed tray path (PH_TRAY) to HOME -> TASK_CANCELLED.  TRAY_EXIT = 0: v0.1.1 logic.
// Truth boundary: source candidate; supplementary Icarus run only.
// ============================================================================

`timescale 1ns / 1ps

module s4_task_fsm #(
    parameter integer TRAY_EXIT = 0,
    parameter integer A_TRAY_EXIT = 0,
    parameter integer PALM_CONTINUITY = 0,
    parameter integer SLOT_INVENTORY = 0,
    parameter integer TIMED_WALKTHROUGH = 0,
    parameter integer HANDOVER_V2 = 0,
    parameter integer HAND_ALIGN_REGIONS = 3,
    parameter integer HAND_ALIGN_LOCATOR = 0,
    parameter integer CONTINUOUS_HAND = 0,
    parameter integer AUTO_RESTOCK = 0,
    parameter integer FAST_B = 0,
    parameter integer DYNAMIC_B = 0,
    parameter integer HAND_ALIGN = 0
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         tick,
    input  wire         period_pulse,
    // vision (same clock, already synchronized)
    input  wire         vis_valid,
    input  wire [2:0]   vis_class,
    input  wire         vis_changed,
    input  wire         vis_window_ok,
    input  wire         estop_ok,
    input wire [511:0] cfg_align_pairs,
    input wire [15:0] cfg_align_n,cfg_align_na,
    input wire [HAND_ALIGN_REGIONS-1:0] cfg_banks_ready,
    input wire align_target_valid,align_delivery_ready,
    input wire [3:0] align_target_cell,
    input wire [6:0] align_target_step,
    output reg [6:0] active_step,
    output wire kp_mix_enable,
    input wire [31:0] align_target_revision,
    output reg align_accept,
    output wire[3:0]align_accepted_cell,
    output wire[31:0]align_accepted_revision,
    output wire align_waiting,align_settled,align_palm_confirmed,
    output wire [1:0] kp_bank,
    output wire [31:0] align_debug,
    // PS commands
    input  wire         cmd_valid,
    input  wire [3:0]   cmd_index,
    output reg          cmd_done,
    output reg  [3:0]   cmd_result,
    output reg  [3:0]   cmd_done_index,
    // configuration
    input  wire         cfg_mode_b,
    input wire[47:0] cfg_restock_paths,
    input wire[17:0] cfg_restock_release_kps,
    output wire restock_task,
    input  wire         cfg_require_line,
    input  wire         cfg_vision_sim,
    input  wire         cfg_hold_policy,
    input  wire [7:0]   cfg_rearm_mask,
    input  wire [7:0]   cfg_select_mask,
    input  wire [15:0]  cfg_t_palm_hold,
    input  wire [15:0]  cfg_t_fist_hold,
    input  wire [15:0]  cfg_t_pre_wait,
    input  wire [15:0]  cfg_t_palm_wait,
    input  wire [15:0]  cfg_blind_periods,
    input  wire [15:0]  cfg_t_arrival,
    input  wire [15:0]  cfg_t_comm,
    input  wire [15:0]  cfg_t_path_wait,
    input  wire [15:0]  cfg_t_heartbeat,
    input  wire [15:0]  cfg_move_margin,
    input  wire [5:0]   cfg_arrival_mask,
    input  wire [5:0]   cfg_home_kp,
    input  wire [5:0]   cfg_predelivery_kp,
    input  wire [191:0] cfg_joint_min,
    input  wire [191:0] cfg_joint_max,
    input  wire [143:0] cfg_paths,
    input  wire         cfg_tray_exit,        // tray-exit patch (ignored when TRAY_EXIT = 0)
    input  wire [11:0]  cfg_tray_path,        // tray-exit patch: {count[11:6], first[5:0]}
    input  wire [1:0]   req_object,
    input  wire [15:0]  req_task_id,
    input  wire [1:0]   path_object,
    input  wire [15:0]  path_task_id,
    input  wire         cfg_b_restock,
    input  wire [5:0]   cfg_b_release_index,
    output wire [15:0]  selected_task_id,
    // tables
    output reg  [8:0]   kp_raddr,
    input  wire [31:0]  kp_rdata,
    output reg  [6:0]   seg_raddr,
    input  wire [31:0]  seg_rdata,
    output reg  [(DYNAMIC_B!=0?9:8)-1:0] fifo_raddr,
    input  wire [31:0]  fifo_rdata,
    input  wire [5:0]   fifo_count,
    output reg          fifo_clear,
    // motion link
    output reg          op_valid,
    input  wire         op_ready,
    output reg  [2:0]   op_code,
    output reg  [191:0] op_target,
    output reg  [15:0]  op_n,
    output reg  [15:0]  op_na,
    output reg          op_profile,
    output reg          op_source,
    input  wire         op_done,
    input  wire         op_ok,
    input  wire         op_timeout,
    input  wire [31:0]  st_s1_status,
    input  wire [31:0]  st_fb_masks,
    input  wire [31:0]  st_fb_age,
    input  wire [31:0]  st_pl_status,
    input  wire [31:0]  st_pl_error,
    input  wire [191:0] st_last,
    // outputs
    output reg          fault_latched,
    output reg          owner_s4,
    output wire         cfg_unlock,
    output wire         fifo_unlock,
    output wire [31:0]  status_word,
    output wire [31:0]  fault_word,
    output wire [31:0]  progress_word,
    output wire [31:0]  interaction_status,
    output wire [31:0]  interaction_timers,
    output reg  [15:0]  event_set,
    output reg  [4:0]   cnt_inc,
    output reg          poll_done_pulse,
    output reg  [15:0]  last_task_id
);

    localparam integer PALM_ENABLED=(PALM_CONTINUITY!=0)&&(HANDOVER_V2==0);
    localparam integer REAL_PALM_REQUIRED=(PALM_CONTINUITY!=0)||(HANDOVER_V2!=0);

    // ---------------------------------------------------------------- encodings (= model)
    localparam [3:0] S_OFF = 4'd0, S_IDLE = 4'd1, S_WAIT_PATH = 4'd2, S_PRECHECK = 4'd3, S_RUN = 4'd4,
                     S_WAIT_PALM = 4'd5, S_PAUSED = 4'd6, S_STOPPING = 4'd7, S_RETRACE = 4'd8, S_HALT = 4'd9,
                     S_FAULT = 4'd10;
    localparam [2:0] PH_NONE = 3'd0, PH_OUT = 3'd1, PH_DELIVER = 3'd2, PH_RELEASE = 3'd3, PH_RETREAT = 3'd4,
                     PH_TRAY = 3'd5;
    localparam [7:0] F_ESTOP_INPUT = 8'd1, F_S1_FAULT = 8'd2, F_S1_PERMISSION = 8'd3, F_PLANNER = 8'd4,
                     F_MOVE_TIMEOUT = 8'd5, F_ARRIVAL = 8'd6, F_COMM = 8'd7, F_AXI = 8'd8, F_MISMATCH = 8'd9,
                     F_ABORT = 8'd10;
    localparam [7:0] R_ESTOP = 8'd1, R_S1_NOT_READY = 8'd2, R_S1_MODE = 8'd3, R_PLANNER = 8'd4,
                     R_NOT_HOME = 8'd5, R_TABLE = 8'd6, R_RANGE = 8'd7, R_DUPLICATE = 8'd8, R_PATH = 8'd9,
                     R_LINK = 8'd10, R_EMPTY_SLOT = 8'd11;
    localparam integer E_DONE = 0, E_CANCELLED = 1, E_REFUSED = 2, E_FAULT = 3, E_SELECTED = 4,
                       E_PATH_OK = 5, E_PATH_BAD = 6, E_CANCEL_IGN = 7, E_BLIND = 8, E_PALM_TMO = 9,
                       E_HALTED = 10, E_CMD_REJ = 12, E_HB_TMO = 13, E_PATH_TMO = 15;
    localparam [3:0] C_ENABLE = 4'd0, C_RELEASE = 4'd1, C_START = 4'd2, C_CANCEL = 4'd3, C_PAUSE = 4'd4,
                     C_RESUME = 4'd5, C_ABORT = 4'd6, C_FCLEAR = 4'd7, C_COMMIT = 4'd8, C_PRESET = 4'd9,
                     C_HEARTBEAT = 4'd10, C_RESTOCK = 4'd11, C_SHARED_RED_EMPTY = 4'd12;
    localparam [3:0] CR_OK = 4'd0, CR_STATE = 4'd2, CR_FAULT = 4'd3, CR_ESTOP = 4'd4, CR_SOURCE = 4'd5;
    localparam [2:0] OP_POLL = 3'd0, OP_MOVE = 3'd1, OP_PAUSE = 3'd2, OP_RESUME = 3'd3, OP_CLEAR = 3'd4,
                     OP_ESTOP = 3'd5, OP_SOURCE = 3'd6;
    localparam [2:0] PL_IDLE = 3'd0, PL_VALIDATE = 3'd1, PL_RUN = 3'd2, PL_PAUSED = 3'd3, PL_DONE = 3'd4,
                     PL_ERROR = 3'd5, PL_ESTOP = 3'd6;
    localparam [2:0] VC_PALM = 3'd4, VC_FIST = 3'd5;
    localparam [2:0] K_FWD=0,K_RETRACE=1,K_PARTIAL=2,K_ALIGN=3,K_ANCHOR=4;
    localparam [7:0] SF_GRASP = 8'h01, SF_STOP = 8'h02;

    // micro states
    localparam [5:0] M_IDLE = 6'd0, M_OPWAIT = 6'd1, M_FAULT = 6'd2, M_FAULT_DONE = 6'd3,
                     M_ENABLE_DONE = 6'd4, M_RELEASE_DONE = 6'd5, M_PAUSE_DONE = 6'd6, M_RESUME_DONE = 6'd7,
                     M_STOP_DONE = 6'd8, M_CLEAR_DONE = 6'd9, M_MON = 6'd10, M_PRE = 6'd11,
                     M_PRE_POLLED = 6'd12, M_HOME = 6'd13, M_SCAN = 6'd14, M_SCAN_SEG = 6'd15,
                     M_SCAN_CHECK = 6'd16, M_SCAN_END = 6'd17, M_NEXT = 6'd18, M_FETCH = 6'd19,
                     M_PREMOVE = 6'd20, M_PREMOVE_DONE = 6'd21, M_MOVE_DONE = 6'd22, M_BEGIN = 6'd23,
                     M_START_RUN = 6'd25, M_ALIGN_FETCH=6'd26, M_ALIGN_TIME=6'd27;

    // ---------------------------------------------------------------- state
    reg  [3:0]   st;
    reg  [2:0]   ph;
    reg  [5:0]   ms, ms_ret;
    reg          armed, holding, released, ready_latched, cancel_req, blind_req;
    reg  [7:0]   fault_code, fault_detail, refuse_code;
    reg          fault_pending;
    reg  [1:0]   object;
    // Runtime inventory belongs to PL. Reset requires explicit operator restock.
    // Background/rearm, RELEASE and FAULT_CLEAR never refill a slot.
    reg  [2:0]   slot_available;
    reg restocking;
    reg[5:0] sc_restock_releases;
    assign restock_task=(AUTO_RESTOCK!=0)&&restocking;
    reg  [15:0]  task_id;
    reg  [15:0]  b_selection_seq;
    assign selected_task_id=task_id;
    reg          last_task_valid;
    reg          mode_b_task;          // mode latched at task start
    reg          cmd_pend;
    reg  [3:0]   cmd_idx;
    reg          tick_pend;
    reg          fist_evt;
    reg [15:0]   fist_hold;
    reg          fist_sent;
    reg  [15:0]  palm_hold, palm_wait, path_wait, hb_age, fb_age, mv_done_ticks;
    reg  [15:0]  fb_seen;
    reg  [15:0]  blind_cnt, mv_periods;
    reg  [7:0]   moves_issued;
    // phase iteration
    reg  [5:0]   pos, ph_count;
    reg  [5:0]   out_fifo_count;
    reg  [15:0]  rel_n_total;
    reg  [5:0]   deliver_count;
    // current move
    reg          mv_active, mv_stopped, mv_push;
    reg  [2:0]   mv_kind;
    reg  [191:0] mv_target, mv_start;
    reg  [15:0]  mv_n, mv_na;
    reg          mv_prof;
    reg  [7:0]   mv_flags;
    // retrace stack
    (* ram_style = "distributed" *) reg [232:0] stack_mem [0:(DYNAMIC_B!=0?63:31)];
    reg  [5:0]   sp, sp_deliver;
    wire [232:0] stack_top = stack_mem[(DYNAMIC_B!=0?sp-6'd1:{1'b0,sp[4:0]-5'd1})];
    // poses read at precheck
    reg  [191:0] home_pose, pre_pose;
    // POLL's coherent snapshot is stable when M_OPWAIT consumes op_done.
    // Register six independent joint comparisons on that existing wait cycle;
    // M_PRE_POLLED/M_MON consume them on the next cycle. This cuts the wide
    // pose comparison out of the priority/fault chain without another FSM
    // state, stale snapshots, or changing the operation handshake.
    reg [5:0] last_home_equal_q, last_target_equal_q;
    genvar pose_joint;
    generate for (pose_joint=0; pose_joint<6; pose_joint=pose_joint+1) begin: g_pose_equal
        always @(posedge clk) begin
            if (!rst_n) begin
                last_home_equal_q[pose_joint] <= 1'b0;
                last_target_equal_q[pose_joint] <= 1'b0;
            end else if (ms == M_OPWAIT && op_done) begin
                last_home_equal_q[pose_joint] <=
                    st_last[pose_joint*32+:32] == home_pose[pose_joint*32+:32];
                last_target_equal_q[pose_joint] <=
                    st_last[pose_joint*32+:32] == mv_target[pose_joint*32+:32];
            end
        end
    end endgenerate

    reg [1:0] scan_bank,active_bank;
    reg [31:0] align_revision;
    reg [191:0] align_origin;
    reg align_dirty;
    reg[31:0] align_move_timing;
    reg align_retarget;
    reg[7:0]align_retargets;
    reg[31:0]align_delta;
    reg signed[32:0]align_diff_q;reg[31:0]align_abs_q;reg[1:0]align_time_stage;
    function[15:0]align_steps(input[31:0]d);
    begin
        if(CONTINUOUS_HAND!=0)begin
        if(d<=1144)align_steps=16;
        else if(d<=2288)align_steps=20;
        else if(d<=4576)align_steps=25;
        else if(d<=9151)align_steps=32;
        else if(d<=13726)align_steps=36;
        else if(d<=22877)align_steps=43;
        else if(d<=34315)align_steps=61;
        else if(d<=51472)align_steps=91;
        else if(d<=102944)align_steps=182;
        else align_steps=512;
        end else begin
        if(d<=1144)align_steps=12;else if(d<=2288)align_steps=16;
        else if(d<=4576)align_steps=20;else if(d<=9151)align_steps=28;
        else if(d<=13726)align_steps=32;else if(d<=22877)align_steps=44;
        else if(d<=34315)align_steps=64;else if(d<=51472)align_steps=92;
        else if(d<=102944)align_steps=184;else align_steps=512;
        end
    end endfunction
    reg release_wait;
    wire pre_min_wait;
    wire [6:0] step_delta=(align_target_step>active_step)?align_target_step-active_step:active_step-align_target_step;
    wire position_changed=(CONTINUOUS_HAND!=0)?(step_delta>2):(align_target_cell!=active_bank);
    assign kp_mix_enable=(st!=S_PRECHECK)&&!restock_task;
    wire align_same=align_target_valid && align_target_cell<HAND_ALIGN_REGIONS && !position_changed && align_target_revision==align_revision;
    // fetch
    reg  [3:0]   fstep;
    reg          f_fifo;             // source of the fetched segment: FIFO (1) or segment table (0)
    reg  [5:0]   f_idx;
    reg  [5:0]   sg_kp;
    reg  [7:0]   sg_flags;
    reg          sg_prof;
    reg  [15:0]  sg_n, sg_na;
    reg  [191:0] sg_target;
    reg          f_scan;             // fetch belongs to the table scan
    // scan
    reg  [2:0]   sc_r;
    reg  [5:0]   sc_i;
    reg          sc_path_check;      // mode B commit (PATH_* events) vs mode A precheck
    reg          sc_table_bad, sc_range_bad;
    // tray-exit patch
    reg          sc_tray_bad;        // PATH_TRAY empty, out of range or not ending at HOME
    reg          tray_ok_task;       // this task has a validated tray exit
    reg          tray_active;        // PH_TRAY running
    reg  [5:0]   sc_grasps, sc_out_total;
    reg  [15:0]  sc_rel_n;
    localparam integer KP_EXTRA=(CONTINUOUS_HAND!=0)?3:0;
    reg  [3:0] hstep;
    wire signed[32:0]align_diff=$signed(mv_target[hstep*32+:32])-$signed(st_last[hstep*32+:32]);
    wire[31:0]align_abs=align_diff[32]?-align_diff:align_diff;


    // ---------------------------------------------------------------- helpers (combinational)
    wire         active = (st == S_RUN) || (st == S_WAIT_PALM) || (st == S_PAUSED) || (st == S_STOPPING) ||
                          (st == S_RETRACE) || (st == S_HALT);
    wire [1:0]   s1_mode = st_s1_status[13:12];
    wire         line_mode = (s1_mode == 2'd3);
    wire [2:0]   pl_state = st_pl_status[2:0];
    wire         pl_pending = st_pl_status[5];
    wire [15:0]  fb_seq = st_fb_age[31:16];
    wire [5:0]   arrival = st_fb_masks[13:8];
    assign cfg_unlock = (st == S_OFF) || (st == S_IDLE);
    assign fifo_unlock = cfg_unlock || ((st == S_WAIT_PATH) &&
        ((DYNAMIC_B==0) || (ms==M_IDLE && !cmd_pend)));

    // path descriptors: {count[11:6], first[5:0]}.  cfg_paths is an argument (not read as a
    // module variable) so that the continuous assignments below follow every change of it.
    function [11:0] pdesc;
        input [143:0] paths;
        input [3:0]   k;
        begin
            pdesc = paths[k * 12 +: 12];
        end
    endfunction
    wire [3:0]   obj_off = {2'b00, object} - 4'd1;        // 0..2
    wire[11:0] rs_prefix=cfg_restock_paths[11:0];
    wire[11:0] rs_tail=cfg_restock_paths[(obj_off+1)*12+:12];
    wire[5:0] rs_release_kp=cfg_restock_release_kps[obj_off*6+:6];
    wire [11:0]  d_app = pdesc(cfg_paths, 4'd0 + obj_off), d_grp = pdesc(cfg_paths, 4'd3 + obj_off),
                 d_lift = pdesc(cfg_paths, 4'd6 + obj_off);
    wire [11:0]  d_del = pdesc(cfg_paths, 4'd9), d_rel = pdesc(cfg_paths, 4'd10), d_ret = pdesc(cfg_paths, 4'd11);
    wire [11:0]  d_tray = (TRAY_EXIT != 0) ? cfg_tray_path : 12'd0;     // folds away when TRAY_EXIT = 0
    // tray exit applies: validated exit of this task, object held, not yet released
    wire         tray_applies = (TRAY_EXIT != 0) && tray_ok_task && holding && !released;
    wire         keep_out = tray_applies && (ph == PH_OUT);        // finish the committed OUT path
    wire         tray_running = (TRAY_EXIT != 0) && tray_active;
    wire         scan_tray = (TRAY_EXIT != 0) && cfg_tray_exit &&
        (sc_path_check || (A_TRAY_EXIT!=0 && !mode_b_task));
    wire palm_current = vis_valid && vis_class==VC_PALM && vis_window_ok;
    assign pre_min_wait = (HANDOVER_V2!=0) && st==S_WAIT_PALM && !release_wait && palm_wait<cfg_t_pre_wait;
    assign align_accepted_cell={2'd0,active_bank};
    assign align_accepted_revision=align_revision;
    assign kp_bank=restock_task?2'd3:((HAND_ALIGN!=0)?((st==S_PRECHECK)?scan_bank:active_bank):2'd0);
    assign align_waiting=(HAND_ALIGN!=0)&&(st==S_WAIT_PALM || (HAND_ALIGN_REGIONS==4 && st==S_RUN && mv_kind==K_ALIGN) || (HAND_ALIGN_LOCATOR!=0 && st==S_STOPPING && align_retarget))&&!release_wait&&!cancel_req&&!fault_latched;
    assign align_settled=(st==S_WAIT_PALM) && align_waiting && align_same && !pre_min_wait;
    assign align_palm_confirmed=align_settled && palm_current && palm_hold>=cfg_t_palm_hold;
    assign align_debug={align_retargets,align_revision[7:0],4'd0,align_dirty,align_same,align_delivery_ready,align_waiting,4'd0,active_bank,scan_bank};
    assign interaction_status = {fist_hold,6'd0,blind_req,cancel_req,2'd0,pre_min_wait,ready_latched,(ready_latched && (ph==PH_DELIVER || ph==PH_RELEASE)),
                                 fist_sent,(vis_valid && vis_class==VC_FIST),palm_current};
    assign interaction_timers = {palm_hold,palm_wait};
    // scan range r: 0 approach / FIFO, 1 grasp, 2 lift, 3 deliver, 4 release, 5 retreat
    reg  [5:0]   r_first, r_count;
    reg          r_fifo;
    always @(*) begin
        r_fifo = 1'b0; r_first = 6'd0; r_count = 6'd0;
        if(restock_task && mode_b_task && DYNAMIC_B!=0)begin
            r_fifo=1'b1;if(sc_r==0)r_count=out_fifo_count;
        end else if(restock_task)begin
            if(sc_r==0)begin r_first=rs_prefix[5:0];r_count=rs_prefix[11:6];end
            else if(sc_r==1)begin r_first=rs_tail[5:0];r_count=rs_tail[11:6];end
        end else case (sc_r)
            3'd0: if (mode_b_task) begin r_fifo = 1'b1; r_first = 6'd0; r_count = out_fifo_count; end
                  else begin r_first = d_app[5:0]; r_count = d_app[11:6]; end
            3'd1: if (!mode_b_task) begin r_first = d_grp[5:0]; r_count = d_grp[11:6]; end
            3'd2: if (!mode_b_task) begin r_first = d_lift[5:0]; r_count = d_lift[11:6]; end
            3'd3: begin r_first = d_del[5:0]; r_count = d_del[11:6]; end
            3'd4: begin r_first = d_rel[5:0]; r_count = d_rel[11:6]; end
            3'd6: begin r_first = d_tray[5:0]; r_count = d_tray[11:6]; end   // tray-exit patch (scan_tray only)
            default: begin r_first = d_ret[5:0]; r_count = d_ret[11:6]; end
        endcase
    end
    // segment of phase position pos (execution)
    reg          x_fifo;
    reg  [5:0]   x_idx;
    always @(*) begin
        x_fifo = 1'b0; x_idx = 6'd0;
        if(restock_task && mode_b_task && DYNAMIC_B!=0)begin
            x_fifo=1'b1;x_idx=pos;
        end else if(restock_task)begin
            if(pos<rs_prefix[11:6])x_idx=rs_prefix[5:0]+pos;
            else x_idx=rs_tail[5:0]+(pos-rs_prefix[11:6]);
        end else case (ph)
            PH_OUT: if (mode_b_task) begin x_fifo = 1'b1; x_idx = pos; end
                    else if (pos < d_app[11:6]) x_idx = d_app[5:0] + pos;
                    else if (pos < d_app[11:6] + d_grp[11:6]) x_idx = d_grp[5:0] + (pos - d_app[11:6]);
                    else x_idx = d_lift[5:0] + (pos - d_app[11:6] - d_grp[11:6]);
            PH_DELIVER: x_idx = d_del[5:0] + pos;
            PH_RELEASE: x_idx = d_rel[5:0] + pos;
            PH_TRAY:    x_idx = d_tray[5:0] + pos;
            default:    x_idx = d_ret[5:0] + pos;
        endcase
    end
    function [5:0] phase_count;
        input [2:0] p;
        begin
            if(restock_task && mode_b_task && DYNAMIC_B!=0)phase_count=out_fifo_count;
            else if(restock_task)phase_count=rs_prefix[11:6]+rs_tail[11:6];
            else case (p)
                PH_OUT:     phase_count = mode_b_task ? out_fifo_count : d_app[11:6] + d_grp[11:6] + d_lift[11:6];
                PH_DELIVER: phase_count = d_del[11:6];
                PH_RELEASE: phase_count = d_rel[11:6];
                PH_TRAY:    phase_count = d_tray[11:6];
                default:    phase_count = d_ret[11:6];
            endcase
        end
    endfunction
    // pose range check of a fetched target
    reg          tgt_in_range;
    integer      q;
    always @(*) begin
        tgt_in_range = 1'b1;
        for (q = 0; q < 6; q = q + 1)
            if (($signed(sg_target[q * 32 +: 32]) < $signed(cfg_joint_min[q * 32 +: 32])) ||
                ($signed(sg_target[q * 32 +: 32]) > $signed(cfg_joint_max[q * 32 +: 32])))
                tgt_in_range = 1'b0;
    end

    assign status_word = {2'd0,restock_task, (SLOT_INVENTORY != 0) ? slot_available : 3'd0,
                          tray_running, (TRAY_EXIT != 0) && tray_ok_task, 1'b0, mv_active,
                          object, cfg_mode_b, !op_ready, blind_req, cancel_req, ready_latched,
                          line_mode, estop_ok, !fault_latched, fault_latched, released, holding, armed, owner_s4,
                          ph, st};
    assign fault_word = {8'd0, refuse_code, fault_detail, fault_code};
    assign progress_word = {2'd0, sp, moves_issued, 2'd0, ph_count, 2'd0, pos};

    // ---------------------------------------------------------------- tasks (all in the clocked block)
    task start_op;
        input [2:0] code;
        input [5:0] ret;
        begin
            op_valid <= 1'b1; op_code <= code; ms_ret <= ret; ms <= M_OPWAIT;
        end
    endtask

    task raise_fault;
        input [7:0] code;
        input [7:0] detail;
        begin
            if (!fault_latched) begin
                fault_latched <= 1'b1; fault_code <= code; fault_detail <= detail; fault_pending <= 1'b1;
                event_set[E_FAULT] <= 1'b1; cnt_inc[2] <= 1'b1;
            end
        end
    endtask

    task to_idle;
        begin
            st <= S_IDLE; ph <= PH_NONE; mv_active <= 1'b0; armed <= 1'b0;restocking<=0;
            holding <= 1'b0; released <= 1'b0; ready_latched <= 1'b0; cancel_req <= 1'b0; blind_req <= 1'b0;
            release_wait<=0;
            sp <= 6'd0; ms <= M_IDLE;
            tray_ok_task <= 1'b0; tray_active <= 1'b0;
        end
    endtask

    task refuse;
        input [7:0] code;
        begin
            refuse_code <= code; cnt_inc[3] <= 1'b1; event_set[E_REFUSED] <= 1'b1;
            to_idle;
        end
    endtask

    task cancelled;
        begin
            if (SLOT_INVENTORY != 0 && !mode_b_task && !released && object != 0 && !restock_task)
                slot_available[object - 1'b1] <= 1'b1;
            cnt_inc[1] <= 1'b1; event_set[E_CANCELLED] <= 1'b1;
            to_idle;
        end
    endtask

    task finish_cmd;
        input [3:0] result;
        begin
            cmd_done <= 1'b1; cmd_result <= result; cmd_done_index <= cmd_idx; cmd_pend <= 1'b0;
            if (result != CR_OK) event_set[E_CMD_REJ] <= 1'b1;
        end
    endtask

    // request_cancel(): returns through ms (M_IDLE unless it starts an op or M_NEXT)
    task request_cancel;
        begin
            if (st == S_WAIT_PATH || st == S_PRECHECK) begin
                cancelled;
            end else if (released || st == S_HALT || cancel_req || tray_running) begin
                event_set[E_CANCEL_IGN] <= 1'b1;
                ms <= M_IDLE;
            end else begin
                cancel_req <= 1'b1;
                if (st == S_WAIT_PALM) begin
                    ms <= M_NEXT;
                end else if (st == S_PAUSED) begin
                    if (!keep_out) st <= S_STOPPING;
                    ms <= M_IDLE;
                end else if (st == S_RUN && mv_active && !keep_out
                             && ((mv_flags & SF_STOP) != 8'd0 || (holding && cfg_hold_policy))) begin
                    st <= S_STOPPING;
                    start_op(OP_PAUSE, M_STOP_DONE);
                end else begin
                    ms <= M_IDLE;
                end
            end
        end
    endtask

    task begin_phase;
        input [2:0] p;
        begin
            ph <= p; st <= S_RUN; pos <= 6'd0; ph_count <= phase_count(p);
            if (p == PH_DELIVER) sp_deliver <= sp;
            ms <= M_NEXT;
        end
    endtask

    task begin_tray;                   // tray-exit patch
        begin
            cancel_req <= 1'b0; blind_req <= 1'b0; tray_active <= 1'b1; mv_active <= 1'b0;
            begin_phase(PH_TRAY);
        end
    endtask

    // ---------------------------------------------------------------- main
    integer k;
    always @(posedge clk) begin
        if (!rst_n) begin
            st <= S_OFF; ph <= PH_NONE; ms <= M_IDLE; ms_ret <= M_IDLE;
            armed <= 1'b0; holding <= 1'b0; released <= 1'b0; ready_latched <= 1'b0;release_wait<=1'b0;
            cancel_req <= 1'b0; blind_req <= 1'b0;
            fault_latched <= 1'b0; fault_code <= 8'd0; fault_detail <= 8'd0; refuse_code <= 8'd0; fault_pending <= 1'b0;
            owner_s4 <= 1'b0; object <= 2'd0; task_id <= 16'd0; last_task_id <= 16'd0; last_task_valid <= 1'b0;
            b_selection_seq<=16'd0;
            slot_available <= 3'd0;restocking<=0;sc_restock_releases<=0;
            mode_b_task <= 1'b0; cmd_pend <= 1'b0; cmd_idx <= 4'd0; tick_pend <= 1'b0; fist_evt <= 1'b0;
            fist_hold<=0;fist_sent<=0;scan_bank<=0;active_step<=32;active_bank<=(HAND_ALIGN!=0)?1:0;align_revision<=0;align_origin<=0;align_dirty<=0;align_accept<=0;align_move_timing<=0;align_retarget<=0;align_retargets<=0;align_delta<=0;align_time_stage<=0;align_diff_q<=0;align_abs_q<=0;
            palm_hold <= 16'd0; palm_wait <= 16'd0; path_wait <= 16'd0; hb_age <= 16'd0; fb_age <= 16'd0;
            mv_done_ticks <= 16'd0; fb_seen <= 16'd0; blind_cnt <= 16'd0; mv_periods <= 16'd0; moves_issued <= 8'd0;
            pos <= 6'd0; ph_count <= 6'd0; out_fifo_count <= 6'd0; rel_n_total <= 16'd0; deliver_count <= 6'd0;
            mv_active <= 1'b0; mv_stopped <= 1'b0; mv_push <= 1'b0; mv_kind <= K_FWD; mv_target <= 192'd0;
            mv_start <= 192'd0; mv_n <= 16'd0; mv_na <= 16'd0; mv_prof <= 1'b0; mv_flags <= 8'd0;
            sp <= 6'd0; sp_deliver <= 6'd0; home_pose <= 192'd0; pre_pose <= 192'd0;
            fstep <= 4'd0; f_fifo <= 1'b0; f_idx <= 6'd0; sg_kp <= 6'd0; sg_flags <= 8'd0; sg_prof <= 1'b0;
            sg_n <= 16'd0; sg_na <= 16'd0; sg_target <= 192'd0; f_scan <= 1'b0;
            sc_r <= 3'd0; sc_i <= 6'd0; sc_path_check <= 1'b0; sc_table_bad <= 1'b0; sc_range_bad <= 1'b0;
            sc_grasps <= 6'd0; sc_out_total <= 6'd0; sc_rel_n <= 16'd0; hstep <= 3'd0;
            sc_tray_bad <= 1'b0; tray_ok_task <= 1'b0; tray_active <= 1'b0;
            kp_raddr <= 9'd0; seg_raddr <= 7'd0; fifo_raddr <= 8'd0; fifo_clear <= 1'b0;
            op_valid <= 1'b0; op_code <= OP_POLL; op_target <= 192'd0; op_n <= 16'd0; op_na <= 16'd0;
            op_profile <= 1'b0; op_source <= 1'b0;
            cmd_done <= 1'b0; cmd_result <= 4'd0; cmd_done_index <= 4'd0;
            event_set <= 16'd0; cnt_inc <= 5'd0; poll_done_pulse <= 1'b0;
        end else begin
            cmd_done <= 1'b0;
            event_set <= 16'd0;
            cnt_inc <= 5'd0;
            fifo_clear <= 1'b0;
            poll_done_pulse <= 1'b0;
            if (op_valid && op_ready) op_valid <= 1'b0;
            align_accept<=0;
            if(st==S_OFF || st==S_IDLE)begin scan_bank<=0;active_step<=32;active_bank<=(HAND_ALIGN!=0)?1:0;align_revision<=0;align_dirty<=0;end
            // ---- event capture (any micro state)
            if (cmd_valid && !cmd_pend) begin cmd_pend <= 1'b1; cmd_idx <= cmd_index; end
            if (tick) tick_pend <= 1'b1;
            if(HANDOVER_V2!=0) begin
                if(!vis_valid || vis_class!=VC_FIST || st==S_OFF || st==S_IDLE || st==S_HALT) begin
                    fist_hold<=0;fist_sent<=0;
                end else if(tick && !fist_sent) begin
                    if(fist_hold!=16'hffff)fist_hold<=fist_hold+1'b1;
                    if(cfg_t_fist_hold==0 || fist_hold+16'd1>=cfg_t_fist_hold)begin fist_evt<=1;fist_sent<=1;end
                end
            end else if (vis_valid && vis_changed && vis_class == VC_FIST) fist_evt <= 1'b1;
            if (period_pulse) begin
                if (HANDOVER_V2==0 && ready_latched && (ph == PH_DELIVER || (PALM_ENABLED && ph==PH_RELEASE && !released)) && !blind_req) begin
                    if(PALM_ENABLED && palm_current) blind_cnt<=16'd0;
                    else if(blind_cnt!=16'hFFFF) blind_cnt<=blind_cnt+16'd1;
                end
                if (mv_active && (st == S_RUN || st == S_RETRACE || st == S_STOPPING) && mv_periods != 16'hFFFF)
                    mv_periods <= mv_periods + 16'd1;
            end
            // e-stop input: immediate fault during an active task
            if (!estop_ok && active && !fault_latched) raise_fault(F_ESTOP_INPUT, 8'd0);
            // rearm (level) in IDLE
            if (st == S_IDLE && vis_valid && cfg_rearm_mask[vis_class]) armed <= 1'b1;

            if (fault_pending && ms != M_OPWAIT && ms != M_FAULT && ms != M_FAULT_DONE) begin
                ms <= M_FAULT;
            end else begin
                case (ms)
                // ============================================================ dispatch
                M_IDLE: begin
                    if (cmd_pend) begin
                        case (cmd_idx)
                            C_ENABLE:
                                if (st != S_OFF) finish_cmd(CR_STATE);
                                else if (fault_latched) finish_cmd(CR_FAULT);
                                else if (!estop_ok) finish_cmd(CR_ESTOP);
                                else begin op_source <= 1'b1; start_op(OP_SOURCE, M_ENABLE_DONE); end
                            C_RELEASE:
                                if (st == S_IDLE || st == S_FAULT || st == S_HALT) begin
                                    op_source <= 1'b0; start_op(OP_SOURCE, M_RELEASE_DONE);
                                end else finish_cmd(CR_STATE);
                            C_START:
                                if (st != S_IDLE || req_object == 2'd0) finish_cmd(CR_STATE);
                                else if (AUTO_RESTOCK==0 && SLOT_INVENTORY != 0 && !cfg_mode_b && !slot_available[req_object - 1'b1]) begin
                                    finish_cmd(CR_STATE); refuse(R_EMPTY_SLOT);
                                end
                                else begin
                                    finish_cmd(CR_OK);
                                    if (req_task_id != 16'd0 && last_task_valid && req_task_id == last_task_id) begin
                                        refuse(R_DUPLICATE);
                                    end else begin
                                        object <= req_object; task_id <= req_task_id; mode_b_task <= cfg_mode_b;
                                        restocking<=(AUTO_RESTOCK!=0 && SLOT_INVENTORY!=0 && !cfg_mode_b && !slot_available[req_object-1'b1]);
                                        scan_bank<=(AUTO_RESTOCK!=0 && !cfg_mode_b && !slot_available[req_object-1'b1])?3:0;
                                        if (cfg_mode_b) begin
                                            st <= S_WAIT_PATH; path_wait <= 16'd0; hb_age <= 16'd0;
                                            event_set[E_SELECTED] <= 1'b1;
                                        end else begin
                                            st <= S_PRECHECK; sc_path_check <= 1'b0; hstep <= 3'd0; ms <= M_HOME;
                                        end
                                    end
                                end
                            C_CANCEL:
                                if (!(active || st == S_WAIT_PATH) || st == S_HALT) finish_cmd(CR_STATE);
                                else begin finish_cmd(CR_OK); request_cancel; end
                            C_PAUSE:
                                if (st == S_RUN && mv_active) start_op(OP_PAUSE, M_PAUSE_DONE);
                                else finish_cmd(CR_STATE);
                            C_RESUME:
                                if (st == S_PAUSED) start_op(OP_RESUME, M_RESUME_DONE);
                                else finish_cmd(CR_STATE);
                            C_ABORT:
                                if (!owner_s4 || st == S_FAULT) finish_cmd(CR_STATE);
                                else begin finish_cmd(CR_OK); raise_fault(F_ABORT, 8'd0); end
                            C_FCLEAR:
                                if (st != S_OFF || !fault_latched) finish_cmd(CR_STATE);
                                else if (!estop_ok) finish_cmd(CR_ESTOP);
                                else begin
                                    finish_cmd(CR_OK);
                                    fault_latched <= 1'b0; fault_code <= 8'd0; fault_detail <= 8'd0;
                                end
                            C_COMMIT:
                                if (st != S_WAIT_PATH || path_object != object || path_task_id != task_id)
                                    finish_cmd(CR_STATE);
                                else begin
                                    finish_cmd(CR_OK);
                                    out_fifo_count <= fifo_count;
                                    if(DYNAMIC_B!=0)restocking<=cfg_b_restock;
                                    sc_path_check <= 1'b1;
                                    ms <= M_HOME;              // read HOME/PRE poses, then scan
                                    hstep <= 3'd0;
                                end
                            C_PRESET:
                                if (st == S_OFF || st == S_IDLE || st == S_WAIT_PATH) begin
                                    finish_cmd(CR_OK); fifo_clear <= 1'b1;
                                end else finish_cmd(CR_STATE);
                            C_HEARTBEAT: begin finish_cmd(CR_OK); hb_age <= 16'd0; end
                            C_RESTOCK:
                                if (SLOT_INVENTORY == 0 || (cfg_mode_b && !(DYNAMIC_B!=0 && req_object==1)) || req_object == 0 ||
                                    !(st == S_OFF || st == S_IDLE) || holding || fault_latched)
                                    finish_cmd(CR_STATE);
                                else begin
                                    slot_available[req_object - 1'b1] <= 1'b1;
                                    finish_cmd(CR_OK);
                                end
                            C_SHARED_RED_EMPTY:
                                if(DYNAMIC_B==0 || SLOT_INVENTORY==0 || req_object!=1 ||
                                   !(st==S_OFF || st==S_IDLE) || holding || fault_latched)finish_cmd(CR_STATE);
                                else begin slot_available[0]<=0;finish_cmd(CR_OK);end
                            default: finish_cmd(CR_STATE);
                        endcase
                    end else if (st == S_IDLE && vis_valid && vis_changed && armed && cfg_select_mask[vis_class]) begin
                        armed <= 1'b0;
                        if (SLOT_INVENTORY != 0 && !cfg_mode_b &&
                            (vis_class < 1 || vis_class > 3 || (AUTO_RESTOCK==0 && !slot_available[vis_class - 1'b1]))) begin
                            refuse(R_EMPTY_SLOT);
                        end else begin
                        object <= vis_class[1:0]; task_id <= (DYNAMIC_B!=0 && cfg_mode_b)?b_selection_seq+16'd1:16'd0; mode_b_task <= cfg_mode_b;
                        if(DYNAMIC_B!=0 && cfg_mode_b)b_selection_seq<=b_selection_seq+16'd1;
                        restocking<=(AUTO_RESTOCK!=0 && SLOT_INVENTORY!=0 && !cfg_mode_b && !slot_available[vis_class-1'b1]);
                        scan_bank<=(AUTO_RESTOCK!=0 && !cfg_mode_b && !slot_available[vis_class-1'b1])?3:0;
                        if (cfg_mode_b) begin
                            st <= S_WAIT_PATH; path_wait <= 16'd0; hb_age <= 16'd0;
                            event_set[E_SELECTED] <= 1'b1;
                        end else begin
                            st <= S_PRECHECK; sc_path_check <= 1'b0; hstep <= 3'd0; ms <= M_HOME;
                        end
                        end
                    end else if (tick_pend && st == S_WAIT_PATH) begin
                        tick_pend <= 1'b0;
                        path_wait <= path_wait + 16'd1;
                        hb_age <= hb_age + 16'd1;
                        if (fist_evt) begin
                            fist_evt <= 1'b0;
                            cancelled;
                        end else if (path_wait + 16'd1 > cfg_t_path_wait) begin
                            event_set[E_PATH_TMO] <= 1'b1;
                            cancelled;
                        end else if (cfg_t_heartbeat != 16'd0 && hb_age + 16'd1 > cfg_t_heartbeat) begin
                            event_set[E_HB_TMO] <= 1'b1;
                            cancelled;
                        end
                    end else if (tick_pend && active) begin
                        tick_pend <= 1'b0;
                        start_op(OP_POLL, M_MON);
                    end else if (tick_pend) begin
                        tick_pend <= 1'b0;
                        fist_evt <= 1'b0;
                    end
                end
                // ============================================================ link op wait
                M_OPWAIT: begin
                    if (op_done) begin
                        if (op_code == OP_POLL) poll_done_pulse <= 1'b1;
                        ms <= fault_pending ? M_FAULT : ms_ret;
                    end
                end
                // ============================================================ fault
                M_FAULT: begin
                    fault_pending <= 1'b0;
                    mv_active <= 1'b0; cancel_req <= 1'b0; blind_req <= 1'b0;
                    if (fault_code != F_AXI) start_op(OP_ESTOP, M_FAULT_DONE);
                    else ms <= M_FAULT_DONE;
                end
                M_FAULT_DONE: begin
                    st <= S_FAULT; ph <= PH_NONE; ms <= M_IDLE;
                end
                // ============================================================ command completions
                M_ENABLE_DONE: begin
                    if (op_ok) begin
                        finish_cmd(CR_OK); owner_s4 <= 1'b1;
                        to_idle;
                    end else begin
                        finish_cmd(CR_SOURCE); ms <= M_IDLE;
                    end
                end
                M_RELEASE_DONE: begin
                    if (op_ok) begin
                        finish_cmd(CR_OK);
                        owner_s4 <= 1'b0; st <= S_OFF; ph <= PH_NONE; mv_active <= 1'b0;restocking<=0;
                        cancel_req <= 1'b0; blind_req <= 1'b0; ms <= M_IDLE;
                    end else begin finish_cmd(CR_SOURCE); ms <= M_IDLE; end
                end
                M_PAUSE_DONE: begin
                    if (op_ok) begin finish_cmd(CR_OK); st <= S_PAUSED; end
                    else finish_cmd(CR_STATE);
                    ms <= M_IDLE;
                end
                M_RESUME_DONE: begin
                    if (op_ok) begin finish_cmd(CR_OK); st <= S_RUN; end
                    else finish_cmd(CR_STATE);
                    ms <= M_IDLE;
                end
                M_STOP_DONE: ms <= M_IDLE;             // PAUSE of stop_now: result not needed
                M_CLEAR_DONE: begin
                    if(HAND_ALIGN_LOCATOR!=0 && align_retarget && !cancel_req)begin
                        align_retarget<=0;align_revision<=0;mv_active<=0;mv_stopped<=0;
                        st<=S_WAIT_PALM;ph<=PH_NONE;palm_wait<=0;palm_hold<=0;ms<=M_IDLE;
                    end else begin align_retarget<=0;
                    mv_stopped <= 1'b1;
                    ms <= M_NEXT;
                    end
                end
                // ============================================================ monitor (per tick, fresh poll)
                M_MON: begin
                    ms <= M_IDLE;
                    if (!op_ok) raise_fault(F_AXI, 8'd0);
                    else if (st_s1_status[4]) raise_fault(F_S1_FAULT, 8'd0);
                    else if (line_mode && !st_s1_status[2]) raise_fault(F_S1_PERMISSION, 8'd0);
                    else if (pl_state == PL_ERROR || pl_state == PL_ESTOP) raise_fault(F_PLANNER, st_pl_error[7:0]);
                    else if (line_mode && fb_seq == fb_seen && fb_age + 16'd1 > cfg_t_comm) raise_fault(F_COMM, 8'd0);
                    else begin
                        if (line_mode) begin
                            if (fb_seq != fb_seen) begin fb_seen <= fb_seq; fb_age <= 16'd0; end
                            else fb_age <= fb_age + 16'd1;
                        end
                        if (mode_b_task && cfg_t_heartbeat != 16'd0 && !released) hb_age <= hb_age + 16'd1;
                        if (mode_b_task && cfg_t_heartbeat != 16'd0 && !released && hb_age + 16'd1 > cfg_t_heartbeat
                            && !cancel_req && !tray_running) begin
                            event_set[E_HB_TMO] <= 1'b1;
                            fist_evt <= 1'b0;
                            request_cancel;
                        end else if (fist_evt && st != S_HALT) begin
                            fist_evt <= 1'b0;
                            request_cancel;
                        end else begin
                            fist_evt <= 1'b0;
                            if (st == S_HALT) begin
                                // hold: faults only
                            end else if (HANDOVER_V2==0 && ready_latched && (ph == PH_DELIVER || (PALM_ENABLED && ph==PH_RELEASE && !released)) && !blind_req && blind_cnt > cfg_blind_periods
                                         && !cancel_req) begin
                                event_set[E_BLIND] <= 1'b1; cnt_inc[4] <= 1'b1; blind_req <= 1'b1;
                                if(PALM_ENABLED) begin
                                    request_cancel;
                                end else if (st == S_RUN && mv_active) begin
                                    st <= S_STOPPING;
                                    start_op(OP_PAUSE, M_STOP_DONE);
                                end else if (st == S_PAUSED) begin
                                    st <= S_STOPPING;
                                end
                            end else if(HAND_ALIGN_LOCATOR!=0 && st==S_RUN && mv_active && mv_kind==K_ALIGN &&
                                        align_target_valid && position_changed && pl_state==PL_RUN)begin
                                align_retarget<=1;align_retargets<=align_retargets+1'b1;
                                st<=S_STOPPING;start_op(OP_PAUSE,M_STOP_DONE);
                            end else if (st == S_WAIT_PALM && HAND_ALIGN!=0 && align_delivery_ready) begin
                                ready_latched<=1;blind_cnt<=0;begin_phase(PH_DELIVER);
                            end else if (st == S_WAIT_PALM && HAND_ALIGN!=0 && align_target_valid && align_target_cell<HAND_ALIGN_REGIONS && !align_same) begin
                                align_accept<=1;align_revision<=align_target_revision;
                                align_move_timing<=(CONTINUOUS_HAND!=0)?32'd0:cfg_align_pairs[{active_bank,align_target_cell[1:0],5'b0}+:32];active_bank<=align_target_cell[1:0];active_step<=align_target_step;palm_hold<=0;palm_wait<=0;
                                if(position_changed || (HAND_ALIGN_LOCATOR!=0 && align_revision==0))begin align_dirty<=1;hstep<=0;st<=S_RUN;ph<=PH_NONE;ms<=M_ALIGN_FETCH;end
                            end else if (st == S_WAIT_PALM) begin
                                if (palm_wait != 16'hffff) palm_wait <= palm_wait + 16'd1;
                                if(pre_min_wait || (HAND_ALIGN!=0 && !align_same)) begin
                                    palm_hold<=0;
                                end else if (vis_valid && vis_class == VC_PALM && vis_window_ok) begin
                                    if(palm_hold!=16'hffff)palm_hold <= palm_hold + 16'd1;
                                    if (HAND_ALIGN==0 && palm_hold + 16'd1 >= cfg_t_palm_hold) begin
                                        ready_latched <= 1'b1; blind_cnt <= 16'd0;
                                        if(PALM_ENABLED && release_wait) begin
                                            release_wait<=1'b0;st<=S_RUN;ms<=M_PREMOVE;
                                        end else begin_phase(PH_DELIVER);
                                    end else if ((TIMED_WALKTHROUGH==0 || cfg_t_palm_wait!=0) && palm_wait + 16'd1 > cfg_t_palm_wait) begin
                                        event_set[E_PALM_TMO] <= 1'b1;
                                        request_cancel;
                                    end
                                end else begin
                                    palm_hold <= 16'd0;
                                    if ((TIMED_WALKTHROUGH==0 || cfg_t_palm_wait!=0) && palm_wait + 16'd1 > cfg_t_palm_wait) begin
                                        event_set[E_PALM_TMO] <= 1'b1;
                                        request_cancel;
                                    end
                                end
                            end else if (st == S_STOPPING && pl_state == PL_PAUSED && !pl_pending) begin
                                start_op(OP_CLEAR, M_CLEAR_DONE);
                            end else if ((st == S_STOPPING || st == S_RUN || st == S_RETRACE) && mv_active) begin
                                // ---- check_done
                                // DONE with the last sample still pending in the backend: not finished
                                // (LAST_DELIVERED is still the previous sample); the move timeout applies
                                if (pl_state == PL_RUN || pl_state == PL_VALIDATE || (pl_state == PL_DONE && pl_pending)) begin
                                    if (st != S_STOPPING && mv_periods > mv_n + cfg_move_margin)
                                        raise_fault(F_MOVE_TIMEOUT, 8'd0);
                                end else if (pl_state == PL_DONE) begin
                                    if (!(&last_target_equal_q)) begin
                                        raise_fault(F_MISMATCH, 8'd0);
                                    end else if (TIMED_WALKTHROUGH!=0 && (mv_kind==K_FWD || mv_kind==K_ALIGN) &&
                                                 !(FAST_B!=0&&mode_b_task&&mv_flags[7]&&!mv_prof) && mv_done_ticks < {6'd0,mv_flags[7:2],4'b0000}) begin
                                        // ABI3405 flags[7:2] encode fixed settling in 16ms units.
                                        // No feedback-position comparison controls progression.
                                        mv_done_ticks <= mv_done_ticks + 16'd1;
                                    end else if (TIMED_WALKTHROUGH==0 && line_mode && (arrival & cfg_arrival_mask) != cfg_arrival_mask) begin
                                        mv_done_ticks <= mv_done_ticks + 16'd1;
                                        if (mv_done_ticks + 16'd1 > cfg_t_arrival) raise_fault(F_ARRIVAL, 8'd0);
                                    end else begin
                                        // ---- move_complete
                                        if (mv_kind == K_FWD && mv_push) begin
                                            stack_mem[(DYNAMIC_B!=0?sp:{1'b0,sp[4:0]})] <= {mv_start, mv_n, mv_na, mv_prof, mv_flags};
                                            sp <= sp + 6'd1;
                                            if ((mv_flags & SF_GRASP) != 8'd0) holding <= 1'b1;
                                        end
                                        if (mv_kind == K_RETRACE && (mv_flags & SF_GRASP) != 8'd0) holding <= 1'b0;
                                        if(restock_task && mv_kind==K_FWD && sg_kp==rs_release_kp)holding<=0;
                                        mv_active <= 1'b0;
                                        if (st == S_STOPPING) st <= S_RETRACE;
                                        if(HAND_ALIGN!=0 && mv_kind==K_ALIGN && !cancel_req)begin
                                            st<=S_WAIT_PALM;ph<=PH_NONE;palm_wait<=0;palm_hold<=0;ms<=M_IDLE;
                                        end else ms <= M_NEXT;
                                    end
                                end
                            end
                        end
                    end
                end
                // ============================================================ precheck
                M_PRE: begin
                    st <= S_PRECHECK;
                    if (!estop_ok) refuse(R_ESTOP);
                    else start_op(OP_POLL, M_PRE_POLLED);
                end
                M_PRE_POLLED: begin
                    if (!op_ok) refuse(R_LINK);
                    else if(HAND_ALIGN!=0 && cfg_banks_ready!={HAND_ALIGN_REGIONS{1'b1}})refuse(R_TABLE);
                    else if (!st_s1_status[0] || st_s1_status[4]) refuse(R_S1_NOT_READY);
                    else if (!(s1_mode == 2'd1 || s1_mode == 2'd3) || (cfg_require_line && s1_mode != 2'd3)) refuse(R_S1_MODE);
                    else if (REAL_PALM_REQUIRED && s1_mode==2'd3 && cfg_vision_sim) refuse(R_S1_MODE);
                    else if (s1_mode == 2'd3 && !(st_s1_status[2] && st_s1_status[5])) refuse(R_S1_NOT_READY);
                    else if (!(pl_state == PL_IDLE || pl_state == PL_DONE) || (st_pl_error[5:0] != 6'd0) || pl_pending
                             || !st_pl_status[8]) refuse(R_PLANNER);
                    else if (!st_pl_status[7] || !(&last_home_equal_q)) refuse(R_NOT_HOME);
                    else if (mode_b_task) ms <= M_START_RUN;           // tables checked at PATH_COMMIT
                    else begin
                        sc_path_check <= 1'b0; sc_r <= 3'd0; sc_i <= 6'd0;
                        sc_table_bad <= 1'b0; sc_range_bad <= 1'b0; sc_grasps <= 6'd0; sc_out_total <= 6'd0;
                        sc_rel_n <= 16'd0;sc_restock_releases<=0;deliver_count<=0;if(A_TRAY_EXIT!=0) sc_tray_bad<=1'b0;
                        ms <= M_SCAN;
                    end
                end
                // read HOME and PRE_DELIVERY poses (mode A: before the precheck poll; mode B: at commit)
                // HOME pose: kp address issued at hstep 0..5, data captured at hstep 2..7
                M_HOME: begin
                    hstep <= hstep + 3'd1;
                    if (hstep <= 3'd5) kp_raddr <= {cfg_home_kp, hstep[2:0]};
                    if (hstep >= 2+KP_EXTRA && hstep<=7+KP_EXTRA) home_pose[(hstep-2-KP_EXTRA)*32+:32] <= kp_rdata;
                    if (hstep == 7+KP_EXTRA) begin
                        hstep <= 3'd0; fstep <= 4'd0;
                        if(DYNAMIC_B!=0 && restock_task && mode_b_task)begin
                            sc_r<=0;sc_i<=0;sc_table_bad<=0;sc_range_bad<=0;sc_grasps<=0;
                            sc_out_total<=0;sc_rel_n<=0;sc_restock_releases<=0;deliver_count<=0;ms<=M_SCAN;
                        end else ms <= restock_task?M_PRE:M_SCAN_SEG;                 // no PRE/PALM phase in restock
                    end
                end
                // PRE_DELIVERY pose (same schedule), then the path scan (mode B) or the precheck poll (mode A)
                M_SCAN_SEG: begin
                    fstep <= fstep + 4'd1;
                    if (fstep < 4'd6) kp_raddr <= {cfg_predelivery_kp, fstep[2:0]};
                    if (fstep>=2+KP_EXTRA && fstep<=7+KP_EXTRA) pre_pose[(fstep-2-KP_EXTRA)*32+:32] <= kp_rdata;
                    if (fstep == 7+KP_EXTRA) begin
                        if (sc_path_check) begin
                            sc_r <= 3'd0; sc_i <= 6'd0; sc_table_bad <= 1'b0; sc_range_bad <= 1'b0;
                            if (TRAY_EXIT != 0) sc_tray_bad <= 1'b0;
                            sc_grasps <= 6'd0; sc_out_total <= 6'd0; sc_rel_n <= 16'd0;
                            ms <= M_SCAN;
                        end else begin
                            ms <= M_PRE;
                        end
                    end
                end
                // ============================================================ table scan
                M_SCAN: begin
                    if (sc_r == ((DYNAMIC_B!=0 && restock_task && mode_b_task)?3'd1:restock_task?3'd2:(scan_tray ? 3'd7 : 3'd6))) begin
                        ms <= M_SCAN_END;
                    end else if (sc_i >= r_count) begin
                        // range finished: structural checks of this range
                        if(restock_task)begin
                            if(r_count==0 || ({1'b0,r_first}+{1'b0,r_count})>64)sc_table_bad<=1;
                        end else begin
                        if (sc_r == 3'd0 && !mode_b_task && r_count == 6'd0) sc_table_bad <= 1'b1;   // approach empty
                        if (sc_r == 3'd2 && !mode_b_task && r_count == 6'd0) sc_table_bad <= 1'b1;   // lift empty
                        if (sc_r >= 3'd3 && (TRAY_EXIT == 0 || sc_r <= 3'd5) && r_count == 6'd0)
                            sc_table_bad <= 1'b1;                                                    // deliver/release/retreat
                        if (TRAY_EXIT != 0 && sc_r == 3'd6 && r_count == 6'd0) sc_tray_bad <= 1'b1;  // tray (patch)
                        if (sc_r == 3'd3) deliver_count <= r_count;
                        end
                        sc_r <= sc_r + 3'd1; sc_i <= 6'd0;
                    end else begin
                        f_fifo <= r_fifo; f_idx <= r_first + sc_i; f_scan <= 1'b1; fstep <= 4'd0;
                        ms <= M_FETCH;
                    end
                end
                M_SCAN_CHECK: begin
                    if (!tgt_in_range && (TRAY_EXIT == 0 || sc_r != 3'd6)) sc_range_bad <= 1'b1;
                    if (TRAY_EXIT != 0 && !tgt_in_range && sc_r == 3'd6) sc_tray_bad <= 1'b1;   // tray: no validated exit
                    if(restock_task && mode_b_task && DYNAMIC_B!=0)begin
                        sc_out_total<=sc_out_total+1'b1;
                        if((sg_flags & SF_GRASP)!=0)begin sc_grasps<=sc_grasps+1'b1;if(sc_restock_releases!=0)sc_table_bad<=1;end
                        if(sc_i==cfg_b_release_index)begin
                            sc_restock_releases<=sc_restock_releases+1'b1;if(sc_grasps!=1)sc_table_bad<=1;
                        end
                        if(sc_i+1==r_count && sg_target!=home_pose)sc_table_bad<=1;
                    end else if(restock_task)begin
                        sc_out_total<=sc_out_total+1'b1;
                        if((sg_flags & SF_GRASP)!=0)begin sc_grasps<=sc_grasps+1'b1;if(sc_restock_releases!=0)sc_table_bad<=1;end
                        if(sg_kp==rs_release_kp)begin sc_restock_releases<=sc_restock_releases+1'b1;if(sc_r!=1 || sc_grasps!=1)sc_table_bad<=1;end
                        if(sc_r==1 && sc_i+1==r_count && sg_kp!=cfg_home_kp)sc_table_bad<=1;
                    end else if (sc_r <= 3'd2) begin
                        sc_out_total <= sc_out_total + 6'd1;
                        if ((sg_flags & SF_GRASP) != 8'd0) sc_grasps <= sc_grasps + 6'd1;
                        // last OUT segment must end at PRE_DELIVERY
                        if ((mode_b_task && sc_r == 3'd0 && sc_i + 6'd1 == r_count && sg_target != pre_pose) ||
                            (!mode_b_task && sc_r == 3'd2 && sc_i + 6'd1 == r_count && sg_kp != cfg_predelivery_kp))
                            sc_table_bad <= 1'b1;
                    end
                    if (!restock_task && sc_r == 3'd4) sc_rel_n <= sc_rel_n + sg_n;
                    if (!restock_task && sc_r == 3'd5 && sc_i + 6'd1 == r_count && sg_kp != cfg_home_kp) sc_table_bad <= 1'b1;
                    if (TRAY_EXIT != 0 && sc_r == 3'd6 && sc_i + 6'd1 == r_count && sg_kp != cfg_home_kp) sc_tray_bad <= 1'b1;
                    sc_i <= sc_i + 6'd1;
                    ms <= M_SCAN;
                end
                M_SCAN_END: begin
                    rel_n_total <= sc_rel_n;
                    if ((restock_task && sc_restock_releases!=1) || sc_grasps != 6'd1 || ({1'b0, sc_out_total} + {1'b0, deliver_count}) > (DYNAMIC_B!=0?7'd63:7'd32) ||
                        (mode_b_task && (out_fifo_count == 6'd0 || out_fifo_count > (DYNAMIC_B!=0?6'd63:6'd32))))
                        sc_table_bad <= 1'b1;
                    ms <= M_BEGIN;
                end
                M_BEGIN: begin
                    if (sc_path_check) begin
                        if (sc_table_bad || sc_range_bad) begin
                            event_set[E_PATH_BAD] <= 1'b1;
                            refuse(R_PATH);
                        end else begin
                            event_set[E_PATH_OK] <= 1'b1;
                            sc_path_check <= 1'b0;
                            tray_ok_task <= scan_tray && !sc_tray_bad;
                            ms <= M_PRE;
                        end
                    end else if (sc_table_bad) refuse(R_TABLE);
                    else if (sc_range_bad) refuse(R_RANGE);
                    else begin
                        if(A_TRAY_EXIT!=0 && !mode_b_task) tray_ok_task<=scan_tray && !sc_tray_bad;
                        if(HAND_ALIGN!=0 && !mode_b_task && !restock_task && scan_bank<((AUTO_RESTOCK!=0)?2:HAND_ALIGN_REGIONS-1))begin scan_bank<=scan_bank+1'b1;hstep<=0;ms<=M_HOME;end
                        else begin active_bank<=restock_task?3:((HAND_ALIGN!=0)?1:0);ms <= M_START_RUN;end
                    end
                end
                M_START_RUN: begin
                    if (SLOT_INVENTORY != 0 && !mode_b_task && object != 0)
                        slot_available[object - 1'b1] <= 1'b0;
                    last_task_id <= task_id; last_task_valid <= 1'b1;
                    fb_seen <= fb_seq; fb_age <= 16'd0; hb_age <= 16'd0;
                    sp <= 6'd0; holding <= 1'b0; released <= 1'b0; ready_latched <= 1'b0;release_wait<=1'b0;
                    cancel_req <= 1'b0; blind_req <= 1'b0; palm_wait <= 16'd0;
                    begin_phase(PH_OUT);
                end
                // ============================================================ next_action
                M_NEXT: begin
                    if ((cancel_req || blind_req) && !released && !(keep_out && cancel_req && !(mv_active && mv_stopped))) begin
                        if (cancel_req && tray_applies) begin
                            // tray exit: back to PRE_DELIVERY (DELIVER floor), then the tray path
                            st <= S_RETRACE;
                            if (mv_active && mv_stopped) begin
                                mv_target <= mv_start; mv_kind <= K_PARTIAL; mv_push <= 1'b0; mv_flags <= (FAST_B!=0&&mode_b_task&&!mv_prof)?(mv_flags&8'h80):8'd0;
                                ms <= M_PREMOVE;
                            end else if (sp > sp_deliver) begin
                                mv_target <= stack_top[232:41]; mv_n <= stack_top[40:25]; mv_na <= stack_top[24:9];
                                mv_prof <= stack_top[8]; mv_flags <= stack_top[7:0];
                                mv_kind <= K_RETRACE; mv_push <= 1'b0;
                                sp <= sp - 6'd1;
                                ms <= M_PREMOVE;
                            end else begin
                                begin_tray;
                            end
                        end else if (cancel_req && holding && (cfg_hold_policy || (A_TRAY_EXIT!=0 && !mode_b_task))) begin
                            st <= S_HALT; mv_active <= 1'b0; event_set[E_HALTED] <= 1'b1; ms <= M_IDLE;
                        end else begin
                            st <= S_RETRACE;
                            if (mv_active && mv_stopped) begin
                                // back to the start pose of the stopped move
                                mv_target <= mv_start; mv_kind <= K_PARTIAL; mv_push <= 1'b0; mv_flags <= (FAST_B!=0&&mode_b_task&&!mv_prof)?(mv_flags&8'h80):8'd0;
                                ms <= M_PREMOVE;
                            end else if(HAND_ALIGN!=0 && cancel_req && align_dirty && sp<=sp_deliver)begin
                                align_dirty<=0;mv_target<=align_origin;mv_n<=cfg_align_n;mv_na<=cfg_align_na;mv_prof<=1;mv_flags<=0;mv_kind<=K_ANCHOR;mv_push<=0;ms<=M_PREMOVE;
                            end else if (sp > (cancel_req ? 6'd0 : sp_deliver)) begin
                                mv_target <= stack_top[232:41]; mv_n <= stack_top[40:25]; mv_na <= stack_top[24:9];
                                mv_prof <= stack_top[8]; mv_flags <= stack_top[7:0];
                                mv_kind <= K_RETRACE; mv_push <= 1'b0;
                                sp <= sp - 6'd1;
                                ms <= M_PREMOVE;
                            end else begin
                                mv_active <= 1'b0;
                                if (cancel_req) begin
                                    cancelled;
                                end else begin
                                    blind_req <= 1'b0; ready_latched <= 1'b0;
                                    st <= S_WAIT_PALM; ph <= PH_NONE; palm_hold <= 16'd0; ms <= M_IDLE;
                                end
                            end
                        end
                    end else begin
                        st <= S_RUN;
                        if (pos < ph_count) begin
                            f_fifo <= x_fifo; f_idx <= x_idx; f_scan <= 1'b0; fstep <= 4'd0;
                            pos <= pos + 6'd1;
                            ms <= M_FETCH;
                        end else begin
                            mv_active <= 1'b0;
                            case (ph)
                                PH_OUT: begin
                                    if(restock_task)begin
                                        if(!mode_b_task)slot_available[object-1'b1]<=1;event_set[14]<=1;
                                        to_idle;
                                    end else begin
                                    if (HAND_ALIGN!=0)align_origin<=st_last;
                                    if (TRAY_EXIT != 0 || HAND_ALIGN!=0) sp_deliver <= sp;     // = the DELIVER floor
                                    if (cancel_req && tray_applies) begin
                                        begin_tray;
                                    end else begin
                                        st <= S_WAIT_PALM; ph <= PH_NONE; palm_hold <= 16'd0; palm_wait <= 16'd0;
                                        ms <= M_IDLE;
                                    end
                                end
                                    end
                                PH_DELIVER: begin
                                    if (HANDOVER_V2==0 && !PALM_ENABLED && blind_cnt + rel_n_total > cfg_blind_periods) begin
                                        event_set[E_BLIND] <= 1'b1; cnt_inc[4] <= 1'b1; blind_req <= 1'b1;
                                        ms <= M_NEXT;
                                    end else begin
                                        begin_phase(PH_RELEASE);
                                    end
                                end
                                PH_RELEASE: begin_phase(PH_RETREAT);
                                PH_TRAY: cancelled;                           // tray-exit patch
                                default: begin
                                    cnt_inc[0] <= 1'b1; event_set[E_DONE] <= 1'b1;
                                    to_idle;
                                end
                            endcase
                        end
                    end
                end
                // ============================================================ segment fetch
                M_FETCH: begin
                    fstep <= fstep + 4'd1;
                    case (fstep)
                        4'd0: begin seg_raddr <= {f_idx, 1'b0}; fifo_raddr <= (DYNAMIC_B!=0?{f_idx,3'd6}:{1'b0,f_idx[4:0],3'd6}); end
                        4'd1: begin seg_raddr <= {f_idx, 1'b1}; fifo_raddr <= (DYNAMIC_B!=0?{f_idx,3'd7}:{1'b0,f_idx[4:0],3'd7}); end
                        default: ;
                    endcase
                    if (fstep == 4'd2) begin
                        sg_kp <= f_fifo ? 6'd0 : seg_rdata[5:0];
                        sg_flags <= f_fifo ? fifo_rdata[31:24] : seg_rdata[31:24];
                        sg_prof <= f_fifo ? fifo_rdata[16] : seg_rdata[16];
                        kp_raddr <= {seg_rdata[5:0], 3'd0};
                        fifo_raddr <= (DYNAMIC_B!=0?{f_idx,3'd0}:{1'b0,f_idx[4:0],3'd0});
                    end
                    if (fstep == 4'd3) begin
                        sg_n <= f_fifo ? fifo_rdata[15:0] : seg_rdata[15:0];
                        sg_na <= f_fifo ? fifo_rdata[31:16] : seg_rdata[31:16];
                    end
                    if (fstep >= 4'd3 && fstep <= 4'd7) begin
                        kp_raddr <= {sg_kp, fstep[2:0] - 3'd2};
                        fifo_raddr <= (DYNAMIC_B!=0?{f_idx,fstep[2:0] - 3'd2}:{1'b0,f_idx[4:0],fstep[2:0] - 3'd2});
                    end
                    if (fstep>=4+(f_fifo?0:KP_EXTRA) && fstep<=9+(f_fifo?0:KP_EXTRA))
                        sg_target[(fstep-4-(f_fifo?0:KP_EXTRA))*32+:32] <= f_fifo ? fifo_rdata : kp_rdata;
                    if (fstep==9+(f_fifo?0:KP_EXTRA)) begin
                        if (f_scan) begin
                            ms <= M_SCAN_CHECK;
                        end else begin
                            ms <= M_PREMOVE;
                            mv_kind <= K_FWD;
                            mv_push <= ((ph == PH_OUT) || (ph == PH_DELIVER)) && !(restock_task &&
                                (released || (!mode_b_task && sg_kp==rs_release_kp) ||
                                 (DYNAMIC_B!=0 && mode_b_task && f_idx==cfg_b_release_index)));
                            // target/n/na/profile/flags are complete one cycle later (M_PREMOVE copies them)
                        end
                    end
                end
                // ============================================================ move issue (poll first)
                M_ALIGN_FETCH: begin
                    hstep<=hstep+1'b1;
                    if(hstep<=5)kp_raddr<={cfg_predelivery_kp,hstep[2:0]};
                    if(hstep>=2+KP_EXTRA && hstep<=7+KP_EXTRA)mv_target[(hstep-2-KP_EXTRA)*32+:32]<=kp_rdata;
                    if(hstep==7+KP_EXTRA)begin mv_n<=(HAND_ALIGN_REGIONS==4)?align_move_timing[15:0]:cfg_align_n;mv_na<=(HAND_ALIGN_REGIONS==4)?align_move_timing[31:16]:cfg_align_na;mv_prof<=1;mv_flags<=(HAND_ALIGN_REGIONS==4)?8'h2a:8'h5a;mv_kind<=K_ALIGN;mv_push<=0;
                        if(HAND_ALIGN_LOCATOR!=0)begin hstep<=0;align_delta<=0;align_time_stage<=0;ms<=M_ALIGN_TIME;mv_flags<=8'h0e;end
                        else ms<=M_PREMOVE;end
                end
                M_ALIGN_TIME:begin
                    if(hstep<6)begin
                        case(align_time_stage)
                        0:begin align_diff_q<=align_diff;align_time_stage<=1;end
                        1:begin align_abs_q<=align_diff_q[32]?-align_diff_q:align_diff_q;align_time_stage<=2;end
                        default:begin
                            if(align_abs_q>align_delta)align_delta<=align_abs_q;
                            hstep<=hstep+1'b1;align_time_stage<=0;
                        end
                        endcase
                    end else begin mv_n<=align_steps(align_delta);mv_na<=align_steps(align_delta)>>2;ms<=M_PREMOVE;end
                end
                M_PREMOVE: begin
                    if(PALM_ENABLED && ph==PH_RELEASE && !released && !palm_current) begin
                        release_wait<=1'b1;st<=S_WAIT_PALM;palm_wait<=16'd0;palm_hold<=16'd0;ms<=M_IDLE;
                    end else begin
                        if (mv_kind == K_FWD) begin
                            mv_target <= sg_target; mv_n <= sg_n; mv_na <= (FAST_B!=0&&mode_b_task&&sg_flags[7]&&!sg_prof)?{5'd0,active_step,sg_na[3:0]}:sg_na; mv_prof <= sg_prof; mv_flags <= sg_flags;
                            if((!PALM_ENABLED && ph==PH_RELEASE) ||
                               (restock_task && !mode_b_task && sg_kp==rs_release_kp) ||
                               (DYNAMIC_B!=0 && restock_task && mode_b_task && f_idx==cfg_b_release_index))released<=1'b1;
                            if(A_TRAY_EXIT!=0 && (sg_flags & SF_GRASP)!=0) holding<=1'b1;
                        end
                        start_op(OP_POLL, M_PREMOVE_DONE);
                    end
                end
                M_PREMOVE_DONE: begin
                    if (!op_ok) raise_fault(F_AXI, 8'd0);
                    else if (!(pl_state == PL_IDLE || pl_state == PL_DONE) || pl_pending) raise_fault(F_MISMATCH, 8'd0);
                    else if(PALM_ENABLED && ph==PH_RELEASE && !released && !palm_current) begin
                        release_wait<=1'b1;st<=S_WAIT_PALM;palm_wait<=16'd0;palm_hold<=16'd0;ms<=M_IDLE;
                    end else begin
                        mv_start <= st_last;
                        op_target <= mv_target; op_n <= mv_n; op_na <= mv_na; op_profile <= (FAST_B!=0&&mode_b_task&&mv_flags[7]&&!mv_prof)?(mv_kind==K_RETRACE||mv_kind==K_PARTIAL):mv_prof;
                        if(PALM_ENABLED && ph==PH_RELEASE) released<=1'b1;
                        start_op((FAST_B!=0&&mode_b_task&&mv_flags[7]&&!mv_prof)?3'd7:OP_MOVE, M_MOVE_DONE);
                    end
                end
                M_MOVE_DONE: begin
                    if (!op_ok) raise_fault(F_AXI, 8'd0);
                    else begin
                        mv_active <= 1'b1; mv_stopped <= 1'b0; mv_periods <= 16'd0; mv_done_ticks <= 16'd0;
                        moves_issued <= moves_issued + 8'd1;
                        ms <= M_IDLE;
                    end
                end
                default: ms <= M_IDLE;
                endcase
            end
        end
    end

    wire _unused = &{1'b0, op_timeout, st_fb_masks[31:14], st_fb_masks[7:0], f_scan};

endmodule
