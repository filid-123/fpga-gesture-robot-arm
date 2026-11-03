// ============================================================================
// Block Name : phase3_s4_task_top
// Description: Phase 3 S4 PL task controller around the UNCHANGED S2 v0.2.3
//              motion top (which contains the unchanged S1 v0.1.1 trajectory and
//              arm backend):
//
//   s_axi_traj (0x43C2_0000) -> s4_axil_window (PS only) ------------> S1 trajectory 0x3002
//   s_axi_arm  (0x43C3_0000) -> s4_axil_window (PS + S4 link) -------> S1 arm backend 0x3101
//   s_axi_plan (0x43C4_0000) -> s4_axil_window (PS + S4 link) -------> S2 planner    0x3201
//   s_axi_s4   (0x43C5_0000, proposed) -> s4_task_regs (ABI 0x0000_3401; 0x0000_3402 with TRAY_EXIT = 1)
//                                 s4_task_fsm <-> s4_motion_link <-> window internal ports
//   motion_enable_in (physical e-stop / motion permission chain)
//        --AND !fault_latched--> S1 motion_enable_in      (revoked in the fault cycle)
//
//   While S4 owns motion (ENABLE .. RELEASE) PS writes to the three motion
//   windows are dropped (OKAY + EVENT/counter); PS reads always pass.  With S4
//   released (reset state) the windows are transparent: S1/S2 PS drivers and
//   ABIs work unchanged.
//   Vision (S3 candidate interface): vis_valid, vis_stable_class[2:0],
//   vis_class_changed, vis_palm_window_ok.  VIS_ASYNC=1 (default): the levels
//   are 2-FF synchronized, a new class is accepted after 4 stable cycles and the
//   change event is derived from the accepted class (the pulse input is not
//   used: a one-cycle pulse is not CDC-safe).  VIS_ASYNC=0: same 100 MHz clock,
//   levels and pulse used directly.  MODE_CFG.vision_sim=1 selects the PS
//   register VISION_SIM instead (bench tests without S3).
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: s_axi_aclk (100 MHz) for everything; vision inputs async (VIS_ASYNC=1)
// Truth boundary: source candidate; supplementary Icarus run only; no BD/XSim/
// synthesis/implementation/board run.
// ============================================================================

`timescale 1ns / 1ps

module phase3_s4_task_top #(
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
    parameter integer DYNAMIC_B = 0,
    parameter integer SMOOTH_PROFILE = 0,
    parameter integer ROARM_FEEDBACK_EVERY = 1
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 s_axi_aclk CLK",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_aclk, ASSOCIATED_BUSIF s_axi_traj:s_axi_arm:s_axi_plan:s_axi_s4, ASSOCIATED_RESET s_axi_aresetn, FREQ_HZ 100000000" *)
    input  wire         s_axi_aclk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 s_axi_aresetn RST",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_aresetn, POLARITY ACTIVE_LOW" *)
    input  wire         s_axi_aresetn,
    // trajectory window (S1)
    input  wire [7:0]   s_axi_traj_awaddr,  input wire [2:0] s_axi_traj_awprot, input wire s_axi_traj_awvalid,
    output wire         s_axi_traj_awready,
    input  wire [31:0]  s_axi_traj_wdata,   input wire [3:0] s_axi_traj_wstrb,  input wire s_axi_traj_wvalid,
    output wire         s_axi_traj_wready,
    output wire [1:0]   s_axi_traj_bresp,   output wire s_axi_traj_bvalid, input wire s_axi_traj_bready,
    input  wire [7:0]   s_axi_traj_araddr,  input wire [2:0] s_axi_traj_arprot, input wire s_axi_traj_arvalid,
    output wire         s_axi_traj_arready,
    output wire [31:0]  s_axi_traj_rdata,   output wire [1:0] s_axi_traj_rresp, output wire s_axi_traj_rvalid,
    input  wire         s_axi_traj_rready,
    // arm backend window (S1)
    input  wire [11:0]  s_axi_arm_awaddr,   input wire [2:0] s_axi_arm_awprot,  input wire s_axi_arm_awvalid,
    output wire         s_axi_arm_awready,
    input  wire [31:0]  s_axi_arm_wdata,    input wire [3:0] s_axi_arm_wstrb,   input wire s_axi_arm_wvalid,
    output wire         s_axi_arm_wready,
    output wire [1:0]   s_axi_arm_bresp,    output wire s_axi_arm_bvalid,  input wire s_axi_arm_bready,
    input  wire [11:0]  s_axi_arm_araddr,   input wire [2:0] s_axi_arm_arprot,  input wire s_axi_arm_arvalid,
    output wire         s_axi_arm_arready,
    output wire [31:0]  s_axi_arm_rdata,    output wire [1:0] s_axi_arm_rresp,  output wire s_axi_arm_rvalid,
    input  wire         s_axi_arm_rready,
    // planner window (S2)
    input  wire [11:0]  s_axi_plan_awaddr,  input wire [2:0] s_axi_plan_awprot, input wire s_axi_plan_awvalid,
    output wire         s_axi_plan_awready,
    input  wire [31:0]  s_axi_plan_wdata,   input wire [3:0] s_axi_plan_wstrb,  input wire s_axi_plan_wvalid,
    output wire         s_axi_plan_wready,
    output wire [1:0]   s_axi_plan_bresp,   output wire s_axi_plan_bvalid, input wire s_axi_plan_bready,
    input  wire [11:0]  s_axi_plan_araddr,  input wire [2:0] s_axi_plan_arprot, input wire s_axi_plan_arvalid,
    output wire         s_axi_plan_arready,
    output wire [31:0]  s_axi_plan_rdata,   output wire [1:0] s_axi_plan_rresp, output wire s_axi_plan_rvalid,
    input  wire         s_axi_plan_rready,
    // S4 task window
    input  wire [11:0]  s_axi_s4_awaddr,    input wire [2:0] s_axi_s4_awprot,   input wire s_axi_s4_awvalid,
    output wire         s_axi_s4_awready,
    input  wire [31:0]  s_axi_s4_wdata,     input wire [3:0] s_axi_s4_wstrb,    input wire s_axi_s4_wvalid,
    output wire         s_axi_s4_wready,
    output wire [1:0]   s_axi_s4_bresp,     output wire s_axi_s4_bvalid,   input wire s_axi_s4_bready,
    input  wire [11:0]  s_axi_s4_araddr,    input wire [2:0] s_axi_s4_arprot,   input wire s_axi_s4_arvalid,
    output wire         s_axi_s4_arready,
    output wire [31:0]  s_axi_s4_rdata,     output wire [1:0] s_axi_s4_rresp,   output wire s_axi_s4_rvalid,
    input  wire         s_axi_s4_rready,
    output wire         irq_traj,
    output wire         irq_arm,
    output wire         irq_plan,
    output wire         irq_s4,
    // physical pins (identical to S1/S2)
    output wire         arm_uart_tx,
    input  wire         arm_uart_rx,
    output wire         bus_tx,
    input  wire         bus_rx,
    output wire         bus_dir,
    input  wire         motion_enable_in,
    // vision event interface (S3 candidate)
    input  wire         vis_valid,
    input  wire [2:0]   vis_stable_class,
    input  wire         vis_class_changed,
    input  wire         vis_palm_window_ok,
    input wire hand_frame_valid,
    input wire [8:0] hand_x,hand_y,
    input wire [2:0] hand_class,
    input wire [31:0] hand_frame_id,hand_timestamp_ms,hand_now_ms,
    // status (for S5 / LEDs; not required)
    output wire         s4_motion_enable,
    output wire         s4_fault,
    output wire [191:0] display_last_delivered,
    output wire [31:0] display_task_status, display_interaction, display_arm_status, display_arm_error, display_feedback_masks, display_feedback_age, display_motion_frames
);

    wire clk = s_axi_aclk;
    wire rst_n = s_axi_aresetn;

    // ---------------------------------------------------------------- e-stop input
    (* ASYNC_REG = "TRUE" *) reg estop_s1, estop_s2;
    always @(posedge clk) begin
        if (!rst_n) begin estop_s1 <= 1'b0; estop_s2 <= 1'b0; end
        else begin estop_s1 <= motion_enable_in; estop_s2 <= estop_s1; end
    end
    wire fault_latched;
    // raw input AND !fault: the revoke needs no synchronizer on the S4 side; S1 debounces its input
    assign s4_motion_enable = motion_enable_in & ~fault_latched;
    assign s4_fault = fault_latched;

    // ---------------------------------------------------------------- windows <-> S2 motion top
    wire [7:0]  t_awaddr, t_araddr;  wire t_awvalid, t_awready, t_wvalid, t_wready, t_bvalid, t_bready;
    wire [31:0] t_wdata, t_rdata;    wire [3:0] t_wstrb; wire [1:0] t_bresp, t_rresp;
    wire        t_arvalid, t_arready, t_rvalid, t_rready;
    wire [11:0] a_awaddr, a_araddr;  wire a_awvalid, a_awready, a_wvalid, a_wready, a_bvalid, a_bready;
    wire [31:0] a_wdata, a_rdata;    wire [3:0] a_wstrb; wire [1:0] a_bresp, a_rresp;
    wire        a_arvalid, a_arready, a_rvalid, a_rready;
    wire [11:0] p_awaddr, p_araddr;  wire p_awvalid, p_awready, p_wvalid, p_wready, p_bvalid, p_bready;
    wire [31:0] p_wdata, p_rdata;    wire [3:0] p_wstrb; wire [1:0] p_bresp, p_rresp;
    wire        p_arvalid, p_arready, p_rvalid, p_rready;

    wire        owner_s4;
    wire        drop_t, drop_a, drop_p, tmo_t, tmo_a, tmo_p, hung_t, hung_a, hung_p;
    wire [7:0]  dropped_t;
    wire [11:0] dropped_a, dropped_p;
    // S4 link <-> window internal ports
    wire        arm_req_valid, arm_req_ready, arm_req_write, arm_rsp_valid, arm_rsp_timeout;
    wire [11:0] arm_req_addr;  wire [31:0] arm_req_wdata, arm_rsp_rdata; wire [1:0] arm_rsp_resp;
    wire        plan_req_valid, plan_req_ready, plan_req_write, plan_rsp_valid, plan_rsp_timeout;
    wire [11:0] plan_req_addr; wire [31:0] plan_req_wdata, plan_rsp_rdata; wire [1:0] plan_rsp_resp;

    wire [31:0] cfg_tick_prescale, cfg_period, cfg_stall;
    wire [191:0] cfg_joint_min, cfg_joint_max, cfg_vmax, cfg_amax;
    wire        op_valid, op_ready, op_done, op_ok, op_timeout, op_profile, op_source;
    wire [2:0]  op_code;  wire [191:0] op_target; wire [15:0] op_n, op_na;
    s4_axil_window #(.ADDR_W(8), .TIMEOUT_CYCLES(AXI_TIMEOUT_CYCLES), .HAS_INTERNAL(0)) u_win_traj (
        .clk(clk), .rst_n(rst_n),
        .s_awaddr(s_axi_traj_awaddr), .s_awvalid(s_axi_traj_awvalid), .s_awready(s_axi_traj_awready),
        .s_wdata(s_axi_traj_wdata), .s_wstrb(s_axi_traj_wstrb), .s_wvalid(s_axi_traj_wvalid), .s_wready(s_axi_traj_wready),
        .s_bresp(s_axi_traj_bresp), .s_bvalid(s_axi_traj_bvalid), .s_bready(s_axi_traj_bready),
        .s_araddr(s_axi_traj_araddr), .s_arvalid(s_axi_traj_arvalid), .s_arready(s_axi_traj_arready),
        .s_rdata(s_axi_traj_rdata), .s_rresp(s_axi_traj_rresp), .s_rvalid(s_axi_traj_rvalid), .s_rready(s_axi_traj_rready),
        .i_req_valid(1'b0), .i_req_ready(), .i_req_write(1'b0), .i_req_addr(8'd0), .i_req_wdata(32'd0),
        .i_rsp_valid(), .i_rsp_rdata(), .i_rsp_resp(), .i_rsp_timeout(),
        .ps_write_block(owner_s4 || (op_valid && op_code==3'd6 && op_source)), .ps_write_dropped(drop_t), .dropped_addr(dropped_t), .axi_timeout(tmo_t), .hung(hung_t),
        .m_awaddr(t_awaddr), .m_awvalid(t_awvalid), .m_awready(t_awready), .m_wdata(t_wdata), .m_wstrb(t_wstrb),
        .m_wvalid(t_wvalid), .m_wready(t_wready), .m_bresp(t_bresp), .m_bvalid(t_bvalid), .m_bready(t_bready),
        .m_araddr(t_araddr), .m_arvalid(t_arvalid), .m_arready(t_arready), .m_rdata(t_rdata), .m_rresp(t_rresp),
        .m_rvalid(t_rvalid), .m_rready(t_rready));

    s4_axil_window #(.ADDR_W(12), .TIMEOUT_CYCLES(AXI_TIMEOUT_CYCLES), .HAS_INTERNAL(0)) u_win_arm (
        .clk(clk), .rst_n(rst_n),
        .s_awaddr(s_axi_arm_awaddr), .s_awvalid(s_axi_arm_awvalid), .s_awready(s_axi_arm_awready),
        .s_wdata(s_axi_arm_wdata), .s_wstrb(s_axi_arm_wstrb), .s_wvalid(s_axi_arm_wvalid), .s_wready(s_axi_arm_wready),
        .s_bresp(s_axi_arm_bresp), .s_bvalid(s_axi_arm_bvalid), .s_bready(s_axi_arm_bready),
        .s_araddr(s_axi_arm_araddr), .s_arvalid(s_axi_arm_arvalid), .s_arready(s_axi_arm_arready),
        .s_rdata(s_axi_arm_rdata), .s_rresp(s_axi_arm_rresp), .s_rvalid(s_axi_arm_rvalid), .s_rready(s_axi_arm_rready),
        .i_req_valid(1'b0), .i_req_ready(arm_req_ready), .i_req_write(arm_req_write),
        .i_req_addr(arm_req_addr), .i_req_wdata(arm_req_wdata), .i_rsp_valid(arm_rsp_valid),
        .i_rsp_rdata(arm_rsp_rdata), .i_rsp_resp(arm_rsp_resp), .i_rsp_timeout(arm_rsp_timeout),
        .ps_write_block(owner_s4 || (op_valid && op_code==3'd6 && op_source)), .ps_write_dropped(drop_a), .dropped_addr(dropped_a), .axi_timeout(tmo_a), .hung(hung_a),
        .m_awaddr(a_awaddr), .m_awvalid(a_awvalid), .m_awready(a_awready), .m_wdata(a_wdata), .m_wstrb(a_wstrb),
        .m_wvalid(a_wvalid), .m_wready(a_wready), .m_bresp(a_bresp), .m_bvalid(a_bvalid), .m_bready(a_bready),
        .m_araddr(a_araddr), .m_arvalid(a_arvalid), .m_arready(a_arready), .m_rdata(a_rdata), .m_rresp(a_rresp),
        .m_rvalid(a_rvalid), .m_rready(a_rready));

    s4_axil_window #(.ADDR_W(12), .TIMEOUT_CYCLES(AXI_TIMEOUT_CYCLES), .HAS_INTERNAL(0)) u_win_plan (
        .clk(clk), .rst_n(rst_n),
        .s_awaddr(s_axi_plan_awaddr), .s_awvalid(s_axi_plan_awvalid), .s_awready(s_axi_plan_awready),
        .s_wdata(s_axi_plan_wdata), .s_wstrb(s_axi_plan_wstrb), .s_wvalid(s_axi_plan_wvalid), .s_wready(s_axi_plan_wready),
        .s_bresp(s_axi_plan_bresp), .s_bvalid(s_axi_plan_bvalid), .s_bready(s_axi_plan_bready),
        .s_araddr(s_axi_plan_araddr), .s_arvalid(s_axi_plan_arvalid), .s_arready(s_axi_plan_arready),
        .s_rdata(s_axi_plan_rdata), .s_rresp(s_axi_plan_rresp), .s_rvalid(s_axi_plan_rvalid), .s_rready(s_axi_plan_rready),
        .i_req_valid(1'b0), .i_req_ready(plan_req_ready), .i_req_write(plan_req_write),
        .i_req_addr(plan_req_addr), .i_req_wdata(plan_req_wdata), .i_rsp_valid(plan_rsp_valid),
        .i_rsp_rdata(plan_rsp_rdata), .i_rsp_resp(plan_rsp_resp), .i_rsp_timeout(plan_rsp_timeout),
        .ps_write_block(owner_s4 || (op_valid && op_code==3'd6 && op_source)), .ps_write_dropped(drop_p), .dropped_addr(dropped_p), .axi_timeout(tmo_p), .hung(hung_p),
        .m_awaddr(p_awaddr), .m_awvalid(p_awvalid), .m_awready(p_awready), .m_wdata(p_wdata), .m_wstrb(p_wstrb),
        .m_wvalid(p_wvalid), .m_wready(p_wready), .m_bresp(p_bresp), .m_bvalid(p_bvalid), .m_bready(p_bready),
        .m_araddr(p_araddr), .m_arvalid(p_arvalid), .m_arready(p_arready), .m_rdata(p_rdata), .m_rresp(p_rresp),
        .m_rvalid(p_rvalid), .m_rready(p_rready));

    wire native_valid,native_ready,native_done,native_ok,native_snap,native_snap_ready,native_snap_done;
    wire [2:0] native_code;
    wire [31:0] native_pl_status,native_pl_error,native_pl_index;
    wire [31:0] native_arm_status,native_arm_error,native_masks,native_age,native_frames;
    wire [191:0] native_last;
    (* keep_hierarchy = "yes" *)
    phase3_s2_motion_top #(.SMOOTH_PROFILE(SMOOTH_PROFILE),
        .HAS_ROARM(HAS_ROARM), .HAS_SO101(HAS_SO101), .DEBOUNCE_CYCLES(DEBOUNCE_CYCLES),
        .MIN_PERIOD_CYCLES(MIN_PERIOD_CYCLES),.ROARM_FEEDBACK_EVERY(ROARM_FEEDBACK_EVERY)
    ) u_motion (
        .native_valid(native_valid), .native_ready(native_ready), .native_code(native_code),
        .native_target(op_target), .native_vmax(cfg_vmax), .native_amax(cfg_amax),
        .native_n(op_n), .native_na(op_na), .native_profile(op_profile),
        .native_period(cfg_period), .native_stall(cfg_stall), .native_done(native_done), .native_ok(native_ok),
        .native_status(native_pl_status), .native_error(native_pl_error), .native_index(native_pl_index),
        .native_snap(native_snap), .native_snap_ready(native_snap_ready), .native_snap_done(native_snap_done),
        .native_arm_status(native_arm_status), .native_arm_error(native_arm_error),
        .native_masks(native_masks), .native_age(native_age), .native_frames(native_frames), .native_last(native_last),
        .s_axi_aclk(clk), .s_axi_aresetn(rst_n),
        .s_axi_traj_awaddr(t_awaddr), .s_axi_traj_awprot(3'd0), .s_axi_traj_awvalid(t_awvalid),
        .s_axi_traj_awready(t_awready), .s_axi_traj_wdata(t_wdata), .s_axi_traj_wstrb(t_wstrb),
        .s_axi_traj_wvalid(t_wvalid), .s_axi_traj_wready(t_wready), .s_axi_traj_bresp(t_bresp),
        .s_axi_traj_bvalid(t_bvalid), .s_axi_traj_bready(t_bready), .s_axi_traj_araddr(t_araddr),
        .s_axi_traj_arprot(3'd0), .s_axi_traj_arvalid(t_arvalid), .s_axi_traj_arready(t_arready),
        .s_axi_traj_rdata(t_rdata), .s_axi_traj_rresp(t_rresp), .s_axi_traj_rvalid(t_rvalid),
        .s_axi_traj_rready(t_rready),
        .s_axi_arm_awaddr(a_awaddr), .s_axi_arm_awprot(3'd0), .s_axi_arm_awvalid(a_awvalid),
        .s_axi_arm_awready(a_awready), .s_axi_arm_wdata(a_wdata), .s_axi_arm_wstrb(a_wstrb),
        .s_axi_arm_wvalid(a_wvalid), .s_axi_arm_wready(a_wready), .s_axi_arm_bresp(a_bresp),
        .s_axi_arm_bvalid(a_bvalid), .s_axi_arm_bready(a_bready), .s_axi_arm_araddr(a_araddr),
        .s_axi_arm_arprot(3'd0), .s_axi_arm_arvalid(a_arvalid), .s_axi_arm_arready(a_arready),
        .s_axi_arm_rdata(a_rdata), .s_axi_arm_rresp(a_rresp), .s_axi_arm_rvalid(a_rvalid),
        .s_axi_arm_rready(a_rready),
        .s_axi_plan_awaddr(p_awaddr), .s_axi_plan_awprot(3'd0), .s_axi_plan_awvalid(p_awvalid),
        .s_axi_plan_awready(p_awready), .s_axi_plan_wdata(p_wdata), .s_axi_plan_wstrb(p_wstrb),
        .s_axi_plan_wvalid(p_wvalid), .s_axi_plan_wready(p_wready), .s_axi_plan_bresp(p_bresp),
        .s_axi_plan_bvalid(p_bvalid), .s_axi_plan_bready(p_bready), .s_axi_plan_araddr(p_araddr),
        .s_axi_plan_arprot(3'd0), .s_axi_plan_arvalid(p_arvalid), .s_axi_plan_arready(p_arready),
        .s_axi_plan_rdata(p_rdata), .s_axi_plan_rresp(p_rresp), .s_axi_plan_rvalid(p_rvalid),
        .s_axi_plan_rready(p_rready),
        .irq_traj(irq_traj), .irq_arm(irq_arm), .irq_plan(irq_plan),
        .arm_uart_tx(arm_uart_tx), .arm_uart_rx(arm_uart_rx), .bus_tx(bus_tx), .bus_rx(bus_rx), .bus_dir(bus_dir),
        .motion_enable_in(s4_motion_enable));

    // ---------------------------------------------------------------- S4 registers
    wire        cmd_valid, cmd_done;  wire [3:0] cmd_index, cmd_result, cmd_done_index;
    wire        cfg_unlock, fifo_unlock;
    wire        cfg_mode_b, cfg_require_line, cfg_hold_policy, cfg_vision_sim;
    wire [7:0]  cfg_rearm_mask, cfg_select_mask;
    wire [15:0] cfg_t_palm_hold, cfg_t_palm_wait, cfg_blind_periods, cfg_t_arrival, cfg_t_comm, cfg_t_path_wait,
                cfg_t_heartbeat, cfg_move_margin;
    wire [5:0]  cfg_arrival_mask, cfg_home_kp, cfg_predelivery_kp;
    wire [143:0] cfg_paths;
    wire        cfg_tray_exit;  wire [11:0] cfg_tray_path;              // tray-exit patch
    wire [1:0]  req_object, path_object;
    wire [15:0] req_task_id, path_task_id, last_task_id;
    wire [2:0]  sim_class;  wire sim_valid, sim_window_ok, sim_changed;
    wire [8:0]  kp_raddr;   wire [31:0] kp_rdata;
    wire [6:0]  seg_raddr;  wire [31:0] seg_rdata;
    wire [(DYNAMIC_B!=0?9:8)-1:0] fifo_raddr; wire [31:0] fifo_rdata; wire [5:0] fifo_count; wire fifo_clear;
    wire [31:0] status_fsm, fault_word, progress_word;
    wire restock_task;wire[47:0]cfg_restock_paths;wire[17:0]cfg_restock_release_kps;
    wire cfg_b_restock;wire[5:0]cfg_b_release_index;wire[15:0]selected_task_id;
    wire [31:0] interaction_status,interaction_timers;
    wire[511:0]cfg_align_pairs;wire[3:0]align_accepted_cell;wire[31:0]align_accepted_revision;wire [1:0] kp_bank;wire [15:0]cfg_align_n,cfg_align_na;wire [HAND_ALIGN_REGIONS-1:0]cfg_banks_ready;
    wire map_write,map_commit,map_ready,map_committed,map_error,map_locked;
    wire [3:0]map_cell,map_error_code,ha_cell,locked_cell;
    wire [1:0]map_word;wire [31:0]map_wdata,map_revision,map_active_revision,ha_revision,align_debug;
    wire [15:0]map_mask;wire align_accept,align_waiting,align_settled,align_palm_confirmed,ha_valid,ha_ready;
    wire [6:0] target_step,active_step;wire kp_mix_enable;
    hand_y_step_map u_step_map(.clk(clk),.rst_n(rst_n),.frame_valid(hand_frame_valid),.x(hand_x),.y(hand_y),.target_step(target_step));
    wire [31:0]align_cells={map_locked,ha_valid,10'd0,locked_cell,4'd0,ha_cell,8'd0};
    generate if(HAND_ALIGN!=0)begin:g_handalign
        wire rv,mv;wire [3:0]mapped_cell_wire;wire [41:0]bundle;wire [31:0]id,ts,revision;wire [2:0]cls;
        hand_align_region_lut #(.REGION_COUNT(HAND_ALIGN_REGIONS)) u_regions(.clk(clk),.rst_n(rst_n),.task_active(!cfg_unlock && !(DYNAMIC_B!=0 && cfg_mode_b && fifo_unlock)),
            .cfg_write(map_write),.cfg_commit(map_commit),.cfg_cell(map_cell),.cfg_word(map_word),.cfg_wdata(map_wdata),.cfg_revision(map_revision),.cfg_mask(map_mask),
            .cfg_ready(map_ready),.cfg_error(map_error),.committed(map_committed),.cfg_error_code(map_error_code),.active_revision(map_active_revision),
            .lookup_req(hand_frame_valid),.lookup_x(hand_x),.lookup_y(hand_y),.lookup_frame_id(hand_frame_id),.lookup_timestamp_ms(hand_timestamp_ms),.lookup_class(hand_class),
            .response_valid(rv),.mapped_valid(mv),.mapped_cell(mapped_cell_wire),.mapped_bundle(bundle),.mapped_frame_id(id),.mapped_timestamp_ms(ts),.mapped_revision(revision),.mapped_class(cls));
        hand_align_target_core #(.PIPELINED_FRESHNESS(CONTINUOUS_HAND),.POSITION_ONLY(HAND_ALIGN_LOCATOR),.EXPLICIT_ACCEPT((HAND_ALIGN_REGIONS==4)?1:0)) u_target(.clk(clk),.rst_n(rst_n),.task_active(!cfg_unlock),.waiting_region(align_waiting),
            .cancel(status_fsm[16]),.fault(fault_latched),.now_ms(hand_now_ms),.max_age_ms(32'd250),.max_gap_ms(32'd250),.hold_ms((HAND_ALIGN_LOCATOR!=0)?16'd80:(HAND_ALIGN_REGIONS==4)?16'd120:16'd200),.min_frames((HAND_ALIGN_LOCATOR!=0)?8'd2:8'd3),
            .response_valid(rv),.mapped_valid(mv),.mapped_cell(mapped_cell_wire),.mapped_bundle(bundle),.mapped_frame_id(id),.mapped_timestamp_ms(ts),.mapped_revision(revision),.mapped_class(cls),
            .accepted_cell_in(align_accepted_cell),.accepted_revision_in(align_accepted_revision),.accept_target(align_accept),.position_settled(align_settled),.palm_confirmed(align_palm_confirmed),.target_valid(ha_valid),.target_cell(ha_cell),.target_revision(ha_revision),
            .locked(map_locked),.delivery_ready(ha_ready),.locked_cell(locked_cell));
    end else begin:g_no_handalign
        assign map_ready=0;assign map_committed=0;assign map_error=0;assign map_error_code=0;assign map_active_revision=0;
        assign ha_valid=0;assign ha_cell=0;assign ha_revision=0;assign map_locked=0;assign ha_ready=0;assign locked_cell=0;
    end endgenerate
    wire [15:0] cfg_t_fist_hold,cfg_t_pre_wait;
    wire [15:0] event_fsm;  wire [4:0] cnt_fsm; wire poll_done;
    wire [31:0] st_s1_status, st_s1_error, st_fb_masks, st_fb_age, st_frames, st_pl_status, st_pl_error, st_pl_index;
    wire [191:0] st_last;
    wire        any_drop = drop_t | drop_a | drop_p;
    wire [13:0] dropped_info = drop_t ? {2'd0, 4'd0, dropped_t} : drop_a ? {2'd1, dropped_a} : {2'd2, dropped_p};
    wire        any_hung = hung_t | hung_a | hung_p;
    // Passive display taps; no path from HDMI to motion or ownership.
    assign display_interaction=interaction_status;
    assign display_arm_status=native_arm_status;
    assign display_arm_error=native_arm_error;
    assign display_feedback_masks=native_masks;
    assign display_feedback_age=native_age;
    assign display_motion_frames=native_frames;
    assign display_last_delivered=native_last;
    wire [31:0] status_word = status_fsm | {8'd0, any_hung, 23'd0};
    assign display_task_status=status_word;
    wire [15:0] event_set = event_fsm | {4'd0, any_drop, 11'd0};         // bit 11 PS_WRITE_BLOCKED

    s4_task_regs #(.TRAY_EXIT(TRAY_EXIT),.SLOT_INVENTORY(SLOT_INVENTORY),.TIMED_WALKTHROUGH(TIMED_WALKTHROUGH),.HANDOVER_V2(HANDOVER_V2),.HAND_ALIGN(HAND_ALIGN),.HAND_ALIGN_REGIONS(HAND_ALIGN_REGIONS),.HAND_ALIGN_LOCATOR(HAND_ALIGN_LOCATOR),.CONTINUOUS_HAND(CONTINUOUS_HAND),.AUTO_RESTOCK(AUTO_RESTOCK),.DYNAMIC_B(DYNAMIC_B)) u_regs (
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

    // ---------------------------------------------------------------- tick / sample period
    reg [31:0] tick_cnt, period_cnt;
    reg        tick, period_pulse;
    always @(posedge clk) begin
        if (!rst_n) begin
            tick_cnt <= 32'd0; period_cnt <= 32'd0; tick <= 1'b0; period_pulse <= 1'b0;
        end else begin
            tick <= 1'b0; period_pulse <= 1'b0;
            if (tick_cnt + 32'd1 >= cfg_tick_prescale) begin tick_cnt <= 32'd0; tick <= 1'b1; end
            else tick_cnt <= tick_cnt + 32'd1;
            if (period_cnt + 32'd1 >= cfg_period) begin period_cnt <= 32'd0; period_pulse <= 1'b1; end
            else period_cnt <= period_cnt + 32'd1;
        end
    end

    // ---------------------------------------------------------------- vision input
    (* ASYNC_REG = "TRUE" *) reg [4:0] vis_s1, vis_s2;              // {window_ok, valid, class[2:0]}
    reg  [4:0] vis_cand, vis_acc;
    reg  [1:0] vis_stable_cnt;
    reg        vis_acc_changed;
    always @(posedge clk) begin
        if (!rst_n) begin
            vis_s1 <= 5'b0_0111; vis_s2 <= 5'b0_0111; vis_cand <= 5'b0_0111; vis_acc <= 5'b0_0111;
            vis_stable_cnt <= 2'd0; vis_acc_changed <= 1'b0;
        end else begin
            vis_s1 <= {vis_palm_window_ok, vis_valid, vis_stable_class};
            vis_s2 <= vis_s1;
            vis_acc_changed <= 1'b0;
            if (vis_s2 != vis_cand) begin
                vis_cand <= vis_s2; vis_stable_cnt <= 2'd0;
            end else if (vis_stable_cnt != 2'd3) begin
                vis_stable_cnt <= vis_stable_cnt + 2'd1;
            end else if (vis_acc != vis_cand) begin
                vis_acc <= vis_cand;
                if (vis_acc[2:0] != vis_cand[2:0]) vis_acc_changed <= 1'b1;
            end
        end
    end
    wire [2:0] f_class   = cfg_vision_sim ? sim_class     : (VIS_ASYNC != 0) ? vis_acc[2:0] : vis_stable_class;
    wire       f_valid   = cfg_vision_sim ? sim_valid     : (VIS_ASYNC != 0) ? vis_acc[3]   : vis_valid;
    wire       f_window  = cfg_vision_sim ? sim_window_ok : (VIS_ASYNC != 0) ? vis_acc[4]   : vis_palm_window_ok;
    wire       f_changed = cfg_vision_sim ? sim_changed   : (VIS_ASYNC != 0) ? vis_acc_changed : vis_class_changed;

    // ---------------------------------------------------------------- FSM + link

    s4_task_fsm #(.TRAY_EXIT(TRAY_EXIT),.A_TRAY_EXIT(A_TRAY_EXIT),.PALM_CONTINUITY(PALM_CONTINUITY),.SLOT_INVENTORY(SLOT_INVENTORY),.TIMED_WALKTHROUGH(TIMED_WALKTHROUGH),.HANDOVER_V2(HANDOVER_V2),.HAND_ALIGN(HAND_ALIGN),.HAND_ALIGN_REGIONS(HAND_ALIGN_REGIONS),.HAND_ALIGN_LOCATOR(HAND_ALIGN_LOCATOR),.CONTINUOUS_HAND(CONTINUOUS_HAND),.AUTO_RESTOCK(AUTO_RESTOCK),.DYNAMIC_B(DYNAMIC_B)) u_fsm (
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

    wire _unused = &{1'b0, s_axi_traj_awprot, s_axi_traj_arprot, s_axi_arm_awprot, s_axi_arm_arprot,
                     s_axi_plan_awprot, s_axi_plan_arprot, s_axi_s4_awprot, s_axi_s4_arprot, tmo_t, tmo_a, tmo_p};

endmodule
