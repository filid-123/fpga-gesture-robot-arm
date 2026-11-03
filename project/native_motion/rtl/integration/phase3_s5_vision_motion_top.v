// ============================================================================
// Block Name : phase3_s5_vision_motion_top
// Description: Phase 3 S5 single design for the pure-FPGA mode: the UNCHANGED
//              S3 v0.1.1 seven-class vision top (gesture_autonomous_top_v5_7c)
//              and the UNCHANGED S4 v0.1.1 task controller (phase3_s4_task_top,
//              which contains the unchanged S2 v0.2.3 motion top with S1 v0.1.1)
//              joined by the new s5_vision_event_adapter.
//
//   OV5640 DVP -> u_vision (S3) --top-level ports--> u_adapter --vis_*--> u_task (S4)
//   PS GP0 -> s_axi_traj 0x43C2 / s_axi_arm 0x43C3 / s_axi_plan 0x43C4 (S1/S2, unchanged)
//             s_axi_s4 0x43C5 (S4, proposed)  s_axi_vis 0x43C6 (S5 adapter, proposed)
//   IRQ bits as S4: irq_traj/arm/plan/s4 -> IRQ_F2P[3:0]; the adapter has no IRQ.
//
//   Clocking: ONE input clk_100mhz feeds the S3 system domain (clk_100mhz) AND
//   the S4 s_axi_aclk, so the adapter, S3 outputs and S4 inputs are one clock
//   net by construction; S4 is therefore built with VIS_ASYNC = 0 (levels and
//   the adapter's change pulse used directly).  The S3 classifier keeps its own
//   clk_50mhz and the camera its pclk; their crossings stay inside S3
//   (classifier_cdc_bridge_7c, camera async FIFO), unchanged.
//   Reset: rst_100mhz_n resets S3's system domain, the adapter and S4 together.
//   The S4 VISION_SIM register path (MODE_CFG[3]) is kept for bench tests.
//   LEDs: the S3 class/fatal LEDs, unchanged.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Truth boundary: source candidate; supplementary Icarus/pyslang only; no BD,
//   XSim, synthesis, implementation or board run.
// ============================================================================

`timescale 1ns / 1ps

module phase3_s5_vision_motion_top #(
    parameter LOCATOR_MODEL_FILE     = "locator_model_blob.mem",
    parameter CLASSIFIER_WEIGHT_FILE = "weights_all.mem",
    parameter CLASSIFIER_DESC_FILE   = "layer_descriptors.mem",
    parameter OV5640_INIT_FILE       = "ov5640_vga_yuyv.mem",
    parameter [31:0] CONFIRM_COUNTS  = {4'd3, 4'd2, 4'd2, 4'd2, 4'd2, 4'd2, 4'd2, 4'd3},
    parameter [7:0]  GATED_CODES     = 8'b0011_1110,
    parameter [15:0] MARGIN_MIN      = 16'd0,
    parameter integer HAS_ROARM          = 1,
    parameter integer HAS_SO101          = 0,
    parameter integer DEBOUNCE_CYCLES    = 1_000_000,
    parameter integer MIN_PERIOD_CYCLES  = 512,
    parameter integer AXI_TIMEOUT_CYCLES = 4096
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk_100mhz CLK",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME clk_100mhz, ASSOCIATED_BUSIF s_axi_traj:s_axi_arm:s_axi_plan:s_axi_s4:s_axi_vis, ASSOCIATED_RESET rst_100mhz_n, FREQ_HZ 100000000" *)
    input  wire         clk_100mhz,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 rst_100mhz_n RST",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME rst_100mhz_n, POLARITY ACTIVE_LOW" *)
    input  wire         rst_100mhz_n,
    input  wire         clk_50mhz,
    input  wire         rst_50mhz_n,
    input  wire         pclk,
    input  wire         pclk_rst_n,
    // OV5640 (as S3)
    input  wire [7:0]   dvp_data,
    input  wire         dvp_href,
    input  wire         dvp_vsync,
    input  wire         xclk_locked,
    output wire         camera_reset_n,
    output wire         camera_pwdn,
    output wire         sccb_scl_drive_low,
    output wire         sccb_sda_drive_low,
    input  wire         sccb_sda_in,
    output wire [3:0]   leds,
    // traj window
    input  wire [7:0]  s_axi_traj_awaddr,
    input  wire [2:0]   s_axi_traj_awprot,
    input  wire         s_axi_traj_awvalid,
    output wire         s_axi_traj_awready,
    input  wire [31:0]  s_axi_traj_wdata,
    input  wire [3:0]   s_axi_traj_wstrb,
    input  wire         s_axi_traj_wvalid,
    output wire         s_axi_traj_wready,
    output wire [1:0]   s_axi_traj_bresp,
    output wire         s_axi_traj_bvalid,
    input  wire         s_axi_traj_bready,
    input  wire [7:0]  s_axi_traj_araddr,
    input  wire [2:0]   s_axi_traj_arprot,
    input  wire         s_axi_traj_arvalid,
    output wire         s_axi_traj_arready,
    output wire [31:0]  s_axi_traj_rdata,
    output wire [1:0]   s_axi_traj_rresp,
    output wire         s_axi_traj_rvalid,
    input  wire         s_axi_traj_rready,
    // arm window
    input  wire [11:0]  s_axi_arm_awaddr,
    input  wire [2:0]   s_axi_arm_awprot,
    input  wire         s_axi_arm_awvalid,
    output wire         s_axi_arm_awready,
    input  wire [31:0]  s_axi_arm_wdata,
    input  wire [3:0]   s_axi_arm_wstrb,
    input  wire         s_axi_arm_wvalid,
    output wire         s_axi_arm_wready,
    output wire [1:0]   s_axi_arm_bresp,
    output wire         s_axi_arm_bvalid,
    input  wire         s_axi_arm_bready,
    input  wire [11:0]  s_axi_arm_araddr,
    input  wire [2:0]   s_axi_arm_arprot,
    input  wire         s_axi_arm_arvalid,
    output wire         s_axi_arm_arready,
    output wire [31:0]  s_axi_arm_rdata,
    output wire [1:0]   s_axi_arm_rresp,
    output wire         s_axi_arm_rvalid,
    input  wire         s_axi_arm_rready,
    // plan window
    input  wire [11:0]  s_axi_plan_awaddr,
    input  wire [2:0]   s_axi_plan_awprot,
    input  wire         s_axi_plan_awvalid,
    output wire         s_axi_plan_awready,
    input  wire [31:0]  s_axi_plan_wdata,
    input  wire [3:0]   s_axi_plan_wstrb,
    input  wire         s_axi_plan_wvalid,
    output wire         s_axi_plan_wready,
    output wire [1:0]   s_axi_plan_bresp,
    output wire         s_axi_plan_bvalid,
    input  wire         s_axi_plan_bready,
    input  wire [11:0]  s_axi_plan_araddr,
    input  wire [2:0]   s_axi_plan_arprot,
    input  wire         s_axi_plan_arvalid,
    output wire         s_axi_plan_arready,
    output wire [31:0]  s_axi_plan_rdata,
    output wire [1:0]   s_axi_plan_rresp,
    output wire         s_axi_plan_rvalid,
    input  wire         s_axi_plan_rready,
    // s4 window
    input  wire [11:0]  s_axi_s4_awaddr,
    input  wire [2:0]   s_axi_s4_awprot,
    input  wire         s_axi_s4_awvalid,
    output wire         s_axi_s4_awready,
    input  wire [31:0]  s_axi_s4_wdata,
    input  wire [3:0]   s_axi_s4_wstrb,
    input  wire         s_axi_s4_wvalid,
    output wire         s_axi_s4_wready,
    output wire [1:0]   s_axi_s4_bresp,
    output wire         s_axi_s4_bvalid,
    input  wire         s_axi_s4_bready,
    input  wire [11:0]  s_axi_s4_araddr,
    input  wire [2:0]   s_axi_s4_arprot,
    input  wire         s_axi_s4_arvalid,
    output wire         s_axi_s4_arready,
    output wire [31:0]  s_axi_s4_rdata,
    output wire [1:0]   s_axi_s4_rresp,
    output wire         s_axi_s4_rvalid,
    input  wire         s_axi_s4_rready,
    // vis window
    input  wire [11:0]  s_axi_vis_awaddr,
    input  wire [2:0]   s_axi_vis_awprot,
    input  wire         s_axi_vis_awvalid,
    output wire         s_axi_vis_awready,
    input  wire [31:0]  s_axi_vis_wdata,
    input  wire [3:0]   s_axi_vis_wstrb,
    input  wire         s_axi_vis_wvalid,
    output wire         s_axi_vis_wready,
    output wire [1:0]   s_axi_vis_bresp,
    output wire         s_axi_vis_bvalid,
    input  wire         s_axi_vis_bready,
    input  wire [11:0]  s_axi_vis_araddr,
    input  wire [2:0]   s_axi_vis_arprot,
    input  wire         s_axi_vis_arvalid,
    output wire         s_axi_vis_arready,
    output wire [31:0]  s_axi_vis_rdata,
    output wire [1:0]   s_axi_vis_rresp,
    output wire         s_axi_vis_rvalid,
    input  wire         s_axi_vis_rready,
    output wire         irq_traj,
    output wire         irq_arm,
    output wire         irq_plan,
    output wire         irq_s4,
    // arm pins (as S1/S2/S4)
    output wire         arm_uart_tx,
    input  wire         arm_uart_rx,
    output wire         bus_tx,
    input  wire         bus_rx,
    output wire         bus_dir,
    input  wire         motion_enable_in
);

    // ---------------------------------------------------------------- S3 vision (unchanged)
    wire        v_frame_valid, v_detected;
    wire [31:0] v_frame_id;
    wire [2:0]  v_candidate, v_stable;
    wire [8:0]  v_raw_x0, v_raw_y0, v_raw_x1, v_raw_y1, v_ema_x0, v_ema_y0, v_ema_x1, v_ema_y1;
    wire [3:0]  v_leds;
    assign leds = v_leds;

    (* keep_hierarchy = "yes" *)
    gesture_autonomous_top_v5_7c #(
        .LOCATOR_MODEL_FILE(LOCATOR_MODEL_FILE), .CLASSIFIER_WEIGHT_FILE(CLASSIFIER_WEIGHT_FILE),
        .CLASSIFIER_DESC_FILE(CLASSIFIER_DESC_FILE), .OV5640_INIT_FILE(OV5640_INIT_FILE),
        .CONFIRM_COUNTS(CONFIRM_COUNTS), .GATED_CODES(GATED_CODES), .MARGIN_MIN(MARGIN_MIN)
    ) u_vision (
        .clk_100mhz(clk_100mhz), .rst_100mhz_n(rst_100mhz_n), .clk_50mhz(clk_50mhz), .rst_50mhz_n(rst_50mhz_n),
        .pclk(pclk), .pclk_rst_n(pclk_rst_n), .dvp_data(dvp_data), .dvp_href(dvp_href), .dvp_vsync(dvp_vsync),
        .xclk_locked(xclk_locked), .camera_reset_n(camera_reset_n), .camera_pwdn(camera_pwdn),
        .sccb_scl_drive_low(sccb_scl_drive_low), .sccb_sda_drive_low(sccb_sda_drive_low), .sccb_sda_in(sccb_sda_in),
        .leds(v_leds),
        .debug_camera_we(), .debug_camera_word_addr(), .debug_camera_wdata(), .debug_camera_frame_published(),
        .debug_camera_latest_frame_id(),
        .debug_result_valid(v_frame_valid), .debug_result_frame_id(v_frame_id), .debug_result_detected(v_detected),
        .debug_raw_x0(v_raw_x0), .debug_raw_y0(v_raw_y0), .debug_raw_x1(v_raw_x1), .debug_raw_y1(v_raw_y1),
        .debug_ema_x0(v_ema_x0), .debug_ema_y0(v_ema_y0), .debug_ema_x1(v_ema_x1), .debug_ema_y1(v_ema_y1),
        .debug_roi_x0(), .debug_roi_y0(), .debug_roi_side(),
        .debug_candidate_class(v_candidate), .debug_stable_class(v_stable));

    // ---------------------------------------------------------------- S3 -> S4 event adapter (new)
    wire        e_valid, e_changed, e_window_ok;
    wire [2:0]  e_class;

    s5_vision_event_adapter u_adapter (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n),
        .frame_valid(v_frame_valid), .frame_class(v_candidate), .frame_detected(v_detected), .frame_id(v_frame_id),
        .raw_x0(v_raw_x0), .raw_y0(v_raw_y0), .raw_x1(v_raw_x1), .raw_y1(v_raw_y1),
        .ema_x0(v_ema_x0), .ema_y0(v_ema_y0), .ema_x1(v_ema_x1), .ema_y1(v_ema_y1),
        .stable_class(v_stable), .leds(v_leds),
        .vis_valid(e_valid), .vis_stable_class(e_class), .vis_class_changed(e_changed), .vis_palm_window_ok(e_window_ok),
        .s_awaddr(s_axi_vis_awaddr), .s_awvalid(s_axi_vis_awvalid), .s_awready(s_axi_vis_awready),
        .s_wdata(s_axi_vis_wdata), .s_wstrb(s_axi_vis_wstrb), .s_wvalid(s_axi_vis_wvalid), .s_wready(s_axi_vis_wready),
        .s_bresp(s_axi_vis_bresp), .s_bvalid(s_axi_vis_bvalid), .s_bready(s_axi_vis_bready),
        .s_araddr(s_axi_vis_araddr), .s_arvalid(s_axi_vis_arvalid), .s_arready(s_axi_vis_arready),
        .s_rdata(s_axi_vis_rdata), .s_rresp(s_axi_vis_rresp), .s_rvalid(s_axi_vis_rvalid), .s_rready(s_axi_vis_rready));
    wire _unused_vis_prot = &{1'b0, s_axi_vis_awprot, s_axi_vis_arprot};

    // ---------------------------------------------------------------- S4 task controller (unchanged)
    (* keep_hierarchy = "yes" *)
    phase3_s4_task_top #(
        .HAS_ROARM(HAS_ROARM), .HAS_SO101(HAS_SO101), .DEBOUNCE_CYCLES(DEBOUNCE_CYCLES),
        .MIN_PERIOD_CYCLES(MIN_PERIOD_CYCLES), .AXI_TIMEOUT_CYCLES(AXI_TIMEOUT_CYCLES), .VIS_ASYNC(0),
        .TRAY_EXIT(1)
    ) u_task (
        .s_axi_aclk(clk_100mhz), .s_axi_aresetn(rst_100mhz_n),
        .s_axi_traj_awaddr(s_axi_traj_awaddr), .s_axi_traj_awprot(s_axi_traj_awprot), .s_axi_traj_awvalid(s_axi_traj_awvalid), .s_axi_traj_awready(s_axi_traj_awready),
        .s_axi_traj_wdata(s_axi_traj_wdata), .s_axi_traj_wstrb(s_axi_traj_wstrb), .s_axi_traj_wvalid(s_axi_traj_wvalid), .s_axi_traj_wready(s_axi_traj_wready),
        .s_axi_traj_bresp(s_axi_traj_bresp), .s_axi_traj_bvalid(s_axi_traj_bvalid), .s_axi_traj_bready(s_axi_traj_bready), .s_axi_traj_araddr(s_axi_traj_araddr),
        .s_axi_traj_arprot(s_axi_traj_arprot), .s_axi_traj_arvalid(s_axi_traj_arvalid), .s_axi_traj_arready(s_axi_traj_arready), .s_axi_traj_rdata(s_axi_traj_rdata),
        .s_axi_traj_rresp(s_axi_traj_rresp), .s_axi_traj_rvalid(s_axi_traj_rvalid), .s_axi_traj_rready(s_axi_traj_rready),
        .s_axi_arm_awaddr(s_axi_arm_awaddr), .s_axi_arm_awprot(s_axi_arm_awprot), .s_axi_arm_awvalid(s_axi_arm_awvalid), .s_axi_arm_awready(s_axi_arm_awready),
        .s_axi_arm_wdata(s_axi_arm_wdata), .s_axi_arm_wstrb(s_axi_arm_wstrb), .s_axi_arm_wvalid(s_axi_arm_wvalid), .s_axi_arm_wready(s_axi_arm_wready),
        .s_axi_arm_bresp(s_axi_arm_bresp), .s_axi_arm_bvalid(s_axi_arm_bvalid), .s_axi_arm_bready(s_axi_arm_bready), .s_axi_arm_araddr(s_axi_arm_araddr),
        .s_axi_arm_arprot(s_axi_arm_arprot), .s_axi_arm_arvalid(s_axi_arm_arvalid), .s_axi_arm_arready(s_axi_arm_arready), .s_axi_arm_rdata(s_axi_arm_rdata),
        .s_axi_arm_rresp(s_axi_arm_rresp), .s_axi_arm_rvalid(s_axi_arm_rvalid), .s_axi_arm_rready(s_axi_arm_rready),
        .s_axi_plan_awaddr(s_axi_plan_awaddr), .s_axi_plan_awprot(s_axi_plan_awprot), .s_axi_plan_awvalid(s_axi_plan_awvalid), .s_axi_plan_awready(s_axi_plan_awready),
        .s_axi_plan_wdata(s_axi_plan_wdata), .s_axi_plan_wstrb(s_axi_plan_wstrb), .s_axi_plan_wvalid(s_axi_plan_wvalid), .s_axi_plan_wready(s_axi_plan_wready),
        .s_axi_plan_bresp(s_axi_plan_bresp), .s_axi_plan_bvalid(s_axi_plan_bvalid), .s_axi_plan_bready(s_axi_plan_bready), .s_axi_plan_araddr(s_axi_plan_araddr),
        .s_axi_plan_arprot(s_axi_plan_arprot), .s_axi_plan_arvalid(s_axi_plan_arvalid), .s_axi_plan_arready(s_axi_plan_arready), .s_axi_plan_rdata(s_axi_plan_rdata),
        .s_axi_plan_rresp(s_axi_plan_rresp), .s_axi_plan_rvalid(s_axi_plan_rvalid), .s_axi_plan_rready(s_axi_plan_rready),
        .s_axi_s4_awaddr(s_axi_s4_awaddr), .s_axi_s4_awprot(s_axi_s4_awprot), .s_axi_s4_awvalid(s_axi_s4_awvalid), .s_axi_s4_awready(s_axi_s4_awready),
        .s_axi_s4_wdata(s_axi_s4_wdata), .s_axi_s4_wstrb(s_axi_s4_wstrb), .s_axi_s4_wvalid(s_axi_s4_wvalid), .s_axi_s4_wready(s_axi_s4_wready),
        .s_axi_s4_bresp(s_axi_s4_bresp), .s_axi_s4_bvalid(s_axi_s4_bvalid), .s_axi_s4_bready(s_axi_s4_bready), .s_axi_s4_araddr(s_axi_s4_araddr),
        .s_axi_s4_arprot(s_axi_s4_arprot), .s_axi_s4_arvalid(s_axi_s4_arvalid), .s_axi_s4_arready(s_axi_s4_arready), .s_axi_s4_rdata(s_axi_s4_rdata),
        .s_axi_s4_rresp(s_axi_s4_rresp), .s_axi_s4_rvalid(s_axi_s4_rvalid), .s_axi_s4_rready(s_axi_s4_rready),
        .irq_traj(irq_traj), .irq_arm(irq_arm), .irq_plan(irq_plan), .irq_s4(irq_s4),
        .arm_uart_tx(arm_uart_tx), .arm_uart_rx(arm_uart_rx), .bus_tx(bus_tx), .bus_rx(bus_rx), .bus_dir(bus_dir),
        .motion_enable_in(motion_enable_in),
        .vis_valid(e_valid), .vis_stable_class(e_class), .vis_class_changed(e_changed),
        .vis_palm_window_ok(e_window_ok),
        .s4_motion_enable(), .s4_fault());

endmodule
