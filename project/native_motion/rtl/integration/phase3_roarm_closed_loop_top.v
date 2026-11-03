// RoARM-M3-S physical closed loop: Rain six-class vision, qualified S4 A/B, one S2, native UART.
// Four AXI windows; retired cubic and SO101 external ports removed.
`timescale 1ns / 1ps

module phase3_roarm_closed_loop_top #(
    parameter LOCATOR_MODEL_FILE     = "model_rom_16k.mem",
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
    parameter integer AXI_TIMEOUT_CYCLES = 4096,
    parameter integer TIMED_WALKTHROUGH = 0,
    parameter integer HANDOVER_V2 = 0,
    parameter integer HAND_ALIGN_REGIONS = 3,
    parameter integer HAND_ALIGN_LOCATOR = 0,
    parameter integer ENABLE_HDMI = 0,
    parameter integer UPGRADE = 0,
    parameter integer AUTO_RESTOCK = 0,
    parameter integer FAST_B = 0,
    parameter integer DYNAMIC_B = 0,
    parameter HDMI_FONT_FILE = "mode_a_font.mem",
    parameter integer HAND_ALIGN = 0
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk_100mhz CLK",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME clk_100mhz, ASSOCIATED_BUSIF s_axi_route:s_axi_arm:s_axi_plan:s_axi_s4:s_axi_vis, ASSOCIATED_RESET rst_100mhz_n, FREQ_HZ 100000000" *)
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
    // B program configuration, 0x43C20000; locked while running.
    input  wire [7:0]  s_axi_route_awaddr,
    input  wire [2:0]   s_axi_route_awprot,
    input  wire         s_axi_route_awvalid,
    output wire         s_axi_route_awready,
    input  wire [31:0]  s_axi_route_wdata,
    input  wire [3:0]   s_axi_route_wstrb,
    input  wire         s_axi_route_wvalid,
    output wire         s_axi_route_wready,
    output wire [1:0]   s_axi_route_bresp,
    output wire         s_axi_route_bvalid,
    input  wire         s_axi_route_bready,
    input  wire [7:0]  s_axi_route_araddr,
    input  wire [2:0]   s_axi_route_arprot,
    input  wire         s_axi_route_arvalid,
    output wire         s_axi_route_arready,
    output wire [31:0]  s_axi_route_rdata,
    output wire [1:0]   s_axi_route_rresp,
    output wire         s_axi_route_rvalid,
    input  wire         s_axi_route_rready,

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
    output wire         irq_arm,
    output wire         irq_plan,
    output wire         irq_s4,
    // arm pins (as S1/S2/S4)
    output wire         arm_uart_tx,
    input  wire         arm_uart_rx,
    input  wire         motion_enable_in,
    input wire hdmi_pixel_clk, hdmi_pixel_clk_5x, hdmi_pixel_rst_n,
    output wire hdmi_clk_p, hdmi_clk_n,
    output wire [2:0] hdmi_data_p, hdmi_data_n
);

    // ---------------------------------------------------------------- S3 vision (unchanged)
    wire        v_frame_valid, v_detected;
    wire preview_we,preview_pub;wire[13:0]preview_addr;wire[31:0]preview_data,preview_id;
    wire loc_start,loc_done,cls_start,cls_done;wire[31:0]job_id;
    wire[31:0] measure_loc,measure_cls,measure_total,measure_collisions,measure_cycle;
    wire measure_freeze;wire[7:0]measure_write_index,measure_read_index;wire[255:0]measure_record;wire[191:0]ui_last;
    generate if(UPGRADE!=0)begin:g_observe
      mode_a_observer observer(.clk(clk_100mhz),.rst_n(rst_100mhz_n),.capture(preview_pub),.capture_id(preview_id),.job_id(job_id),
       .loc_start(loc_start),.loc_done(loc_done),.cls_start(cls_start),.cls_done(cls_done),.result_valid(v_frame_valid),.result_id(v_frame_id),
       .freeze_trace(measure_freeze),.last_delivered(ui_last),.task_status(ui_task),.motion_frames(ui_frames),.read_index(measure_read_index),.read_record(measure_record),
       .loc_cycles(measure_loc),.cls_cycles(measure_cls),.trace_total(measure_total),.trace_collisions(measure_collisions),.cycle_now(measure_cycle),.write_index(measure_write_index));
    end else begin:g_no_observe
      assign measure_record=0;assign measure_loc=0;assign measure_cls=0;assign measure_total=0;assign measure_collisions=0;assign measure_cycle=0;assign measure_write_index=0;
    end endgenerate
    wire cam_we,cam_publish; wire [12:0] cam_addr;wire [31:0] cam_data,cam_id;
    wire [31:0] ui_task,ui_interaction,ui_arm,ui_error,ui_masks,ui_age,ui_frames;

    wire [31:0] v_frame_id;
    wire [2:0]  v_candidate, v_stable;
    wire [8:0]  v_raw_x0, v_raw_y0, v_raw_x1, v_raw_y1, v_ema_x0, v_ema_y0, v_ema_x1, v_ema_y1;
    wire [3:0]  v_leds;
    wire v_qualified,snap_enable,snap_rd_en,snap_ready;
    wire [16:0] snap_addr;
    wire [31:0] snap_data,snap_id,snap_ts,v_acq_ms,v_now_ms,v_conf;
    wire [31:0] v_camera_status,v_frame_drop_count,v_format_error_count;
    wire [15:0] v_margin;
    wire [2:0] v_model_class;
    wire camera_cmd_start,camera_cmd_read,camera_cmd_ready,camera_cmd_busy,camera_cmd_done,camera_cmd_error;
    wire [15:0] camera_cmd_addr;
    wire [7:0] camera_cmd_data,sensor_read_data;
    assign leds = v_leds;

    (* keep_hierarchy = "yes" *)
    gesture_autonomous_top_black #(
        .CLASSIFIER_LANES(UPGRADE!=0?2:1),.HD_PREVIEW(UPGRADE),.CAMERA_CONTROL(1),
        .LOCATOR_MODEL_FILE(LOCATOR_MODEL_FILE), .CLASSIFIER_WEIGHT_FILE(CLASSIFIER_WEIGHT_FILE),
        .CLASSIFIER_DESC_FILE(CLASSIFIER_DESC_FILE), .OV5640_INIT_FILE(OV5640_INIT_FILE),
        .CONFIRM_COUNTS(CONFIRM_COUNTS), .GATED_CODES(GATED_CODES), .MARGIN_MIN(MARGIN_MIN)
    ) u_vision (
        .clk_100mhz(clk_100mhz), .rst_100mhz_n(rst_100mhz_n), .clk_50mhz(clk_50mhz), .rst_50mhz_n(rst_50mhz_n),
        .pclk(pclk), .pclk_rst_n(pclk_rst_n), .dvp_data(dvp_data), .dvp_href(dvp_href), .dvp_vsync(dvp_vsync),
        .xclk_locked(xclk_locked), .camera_reset_n(camera_reset_n), .camera_pwdn(camera_pwdn),
        .sccb_scl_drive_low(sccb_scl_drive_low), .sccb_sda_drive_low(sccb_sda_drive_low), .sccb_sda_in(sccb_sda_in),
        .leds(v_leds),
        .camera_cmd_start(camera_cmd_start),.camera_cmd_read(camera_cmd_read),
        .camera_cmd_addr(camera_cmd_addr),.camera_cmd_data(camera_cmd_data),
        .camera_cmd_ready(camera_cmd_ready),.camera_cmd_busy(camera_cmd_busy),
        .camera_cmd_done(camera_cmd_done),.camera_cmd_error(camera_cmd_error),.sensor_read_data(sensor_read_data),
        .debug_loc_start(loc_start),.debug_loc_done(loc_done),.debug_cls_start(cls_start),.debug_cls_done(cls_done),.debug_job_id(job_id),
        .debug_preview_we(preview_we),.debug_preview_addr(preview_addr),.debug_preview_data(preview_data),.debug_preview_published(preview_pub),.debug_preview_id(preview_id),
        .debug_camera_we(cam_we), .debug_camera_word_addr(cam_addr), .debug_camera_wdata(cam_data), .debug_camera_frame_published(cam_publish),
        .debug_camera_latest_frame_id(cam_id),
        .debug_result_valid(v_frame_valid), .debug_result_frame_id(v_frame_id), .debug_result_detected(v_detected),
        .debug_raw_x0(v_raw_x0), .debug_raw_y0(v_raw_y0), .debug_raw_x1(v_raw_x1), .debug_raw_y1(v_raw_y1),
        .debug_ema_x0(v_ema_x0), .debug_ema_y0(v_ema_y0), .debug_ema_x1(v_ema_x1), .debug_ema_y1(v_ema_y1),
        .debug_roi_x0(), .debug_roi_y0(), .debug_roi_side(),
        .debug_candidate_class(v_candidate), .debug_stable_class(v_stable),
        .debug_filter_valid(v_qualified),.snapshot_enable(snap_enable),.snapshot_rd_en(snap_rd_en),
        .snapshot_word_addr(snap_addr),.snapshot_data(snap_data),.snapshot_ready(snap_ready),
        .snapshot_frame_id(snap_id),.snapshot_timestamp_ms(snap_ts),
        .debug_frame_timestamp_ms(v_acq_ms),.debug_now_ms(v_now_ms),.debug_margin(v_margin),
        .debug_model_class(v_model_class),.debug_confidence_i32(v_conf),
        .debug_camera_status(v_camera_status),.debug_frame_drop_count(v_frame_drop_count),
        .debug_format_error_count(v_format_error_count));

    // ---------------------------------------------------------------- S3 -> S4 event adapter (new)
    wire        e_valid, e_changed, e_window_ok;
    wire [2:0]  e_class;

    s5_vision_event_adapter #(.USE_QUALIFIED_INPUT(1),.CAMERA_DIAGNOSTICS(1),.PHASE2_FRONTEND(1),.CAMERA_CONTROL(1),.MEASURE(UPGRADE)) u_adapter (
        .measure_freeze(measure_freeze),.measure_loc(measure_loc),.measure_cls(measure_cls),.measure_total(measure_total),.measure_collisions(measure_collisions),.measure_cycle(measure_cycle),.measure_write_index(measure_write_index),.measure_record(measure_record),.measure_read_index(measure_read_index),
        .clk(clk_100mhz), .rst_n(rst_100mhz_n),
        .frame_valid(v_frame_valid), .frame_class(v_candidate), .frame_detected(v_detected), .frame_id(v_frame_id),
        .raw_x0(v_raw_x0), .raw_y0(v_raw_y0), .raw_x1(v_raw_x1), .raw_y1(v_raw_y1),
        .ema_x0(v_ema_x0), .ema_y0(v_ema_y0), .ema_x1(v_ema_x1), .ema_y1(v_ema_y1),
        .stable_class(v_stable), .leds(v_leds),
        .qualified_valid(v_qualified),.acquisition_ms(v_acq_ms),.now_ms(v_now_ms),
        .result_margin(v_margin),.model_class(v_model_class),.confidence_raw(v_conf),
        .camera_status(v_camera_status),.frame_drop_count(v_frame_drop_count),.format_error_count(v_format_error_count),
        .snapshot_enable(snap_enable),.snapshot_rd_en(snap_rd_en),.snapshot_word_addr(snap_addr),
        .snapshot_ready(snap_ready),.snapshot_frame_id(snap_id),.snapshot_timestamp_ms(snap_ts),.snapshot_data(snap_data),
        .camera_cmd_start(camera_cmd_start),.camera_cmd_read(camera_cmd_read),
        .camera_cmd_addr(camera_cmd_addr),.camera_cmd_data(camera_cmd_data),
        .camera_cmd_ready(camera_cmd_ready),.camera_cmd_busy(camera_cmd_busy),
        .camera_cmd_done(camera_cmd_done),.camera_cmd_error(camera_cmd_error),.sensor_read_data(sensor_read_data),
        .vis_valid(e_valid), .vis_stable_class(e_class), .vis_class_changed(e_changed), .vis_palm_window_ok(e_window_ok),
        .s_awaddr(s_axi_vis_awaddr), .s_awvalid(s_axi_vis_awvalid), .s_awready(s_axi_vis_awready),
        .s_wdata(s_axi_vis_wdata), .s_wstrb(s_axi_vis_wstrb), .s_wvalid(s_axi_vis_wvalid), .s_wready(s_axi_vis_wready),
        .s_bresp(s_axi_vis_bresp), .s_bvalid(s_axi_vis_bvalid), .s_bready(s_axi_vis_bready),
        .s_araddr(s_axi_vis_araddr), .s_arvalid(s_axi_vis_arvalid), .s_arready(s_axi_vis_arready),
        .s_rdata(s_axi_vis_rdata), .s_rresp(s_axi_vis_rresp), .s_rvalid(s_axi_vis_rvalid), .s_rready(s_axi_vis_rready));
    wire _unused_vis_prot = &{1'b0, s_axi_vis_awprot, s_axi_vis_arprot};

    wire [9:0] hand_sum_x=(HAND_ALIGN_LOCATOR!=0)?({1'b0,v_raw_x0}+{1'b0,v_raw_x1}):({1'b0,v_ema_x0}+{1'b0,v_ema_x1});
    wire [9:0] hand_sum_y=(HAND_ALIGN_LOCATOR!=0)?({1'b0,v_raw_y0}+{1'b0,v_raw_y1}):({1'b0,v_ema_y0}+{1'b0,v_ema_y1});
    // ---------------------------------------------------------------- S4 task controller
    (* keep_hierarchy = "yes" *)
    phase3_s4_task_top #(
        .HAS_ROARM(HAS_ROARM), .HAS_SO101(HAS_SO101), .DEBOUNCE_CYCLES(DEBOUNCE_CYCLES),
        .MIN_PERIOD_CYCLES(MIN_PERIOD_CYCLES), .AXI_TIMEOUT_CYCLES(AXI_TIMEOUT_CYCLES), .VIS_ASYNC(0),
        .TRAY_EXIT(1),.A_TRAY_EXIT(0),.PALM_CONTINUITY(1),.SLOT_INVENTORY(1),.ROARM_FEEDBACK_EVERY(3),.TIMED_WALKTHROUGH(TIMED_WALKTHROUGH),.HANDOVER_V2(HANDOVER_V2),.HAND_ALIGN(HAND_ALIGN),.HAND_ALIGN_REGIONS(HAND_ALIGN_REGIONS),.HAND_ALIGN_LOCATOR(HAND_ALIGN_LOCATOR),.CONTINUOUS_HAND(UPGRADE),.SMOOTH_PROFILE(UPGRADE),.AUTO_RESTOCK(AUTO_RESTOCK),.DYNAMIC_B(DYNAMIC_B),.FAST_B(FAST_B)
    ) u_task (
        .display_last_delivered(ui_last),.display_task_status(ui_task),.display_interaction(ui_interaction),.display_arm_status(ui_arm),.display_arm_error(ui_error),.display_feedback_masks(ui_masks),.display_feedback_age(ui_age),.display_motion_frames(ui_frames),
        .hand_frame_valid(v_frame_valid),.hand_x((HAND_ALIGN_LOCATOR!=0 && !v_detected)?9'h1ff:hand_sum_x[9:1]),.hand_y((HAND_ALIGN_LOCATOR!=0 && !v_detected)?9'h1ff:hand_sum_y[9:1]),
        .hand_class((v_qualified && v_candidate==v_stable)?v_candidate:3'd7),
        .hand_frame_id(v_frame_id),.hand_timestamp_ms(v_acq_ms),.hand_now_ms(v_now_ms),
        .s_axi_aclk(clk_100mhz), .s_axi_aresetn(rst_100mhz_n),
        .s_axi_traj_awaddr(s_axi_route_awaddr), .s_axi_traj_awprot(s_axi_route_awprot), .s_axi_traj_awvalid(s_axi_route_awvalid), .s_axi_traj_awready(s_axi_route_awready),
        .s_axi_traj_wdata(s_axi_route_wdata), .s_axi_traj_wstrb(s_axi_route_wstrb), .s_axi_traj_wvalid(s_axi_route_wvalid), .s_axi_traj_wready(s_axi_route_wready),
        .s_axi_traj_bresp(s_axi_route_bresp), .s_axi_traj_bvalid(s_axi_route_bvalid), .s_axi_traj_bready(s_axi_route_bready), .s_axi_traj_araddr(s_axi_route_araddr),
        .s_axi_traj_arprot(s_axi_route_arprot), .s_axi_traj_arvalid(s_axi_route_arvalid), .s_axi_traj_arready(s_axi_route_arready), .s_axi_traj_rdata(s_axi_route_rdata),
        .s_axi_traj_rresp(s_axi_route_rresp), .s_axi_traj_rvalid(s_axi_route_rvalid), .s_axi_traj_rready(s_axi_route_rready),
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
        .irq_traj(), .irq_arm(irq_arm), .irq_plan(irq_plan), .irq_s4(irq_s4),
        .arm_uart_tx(arm_uart_tx), .arm_uart_rx(arm_uart_rx), .bus_tx(), .bus_rx(1'b1), .bus_dir(),
        .motion_enable_in(motion_enable_in),
        .vis_valid(e_valid), .vis_stable_class(e_class), .vis_class_changed(e_changed),
        .vis_palm_window_ok(e_window_ok),
        .s4_motion_enable(), .s4_fault());

    generate if(ENABLE_HDMI!=0)begin:g_hdmi
        mode_a_hdmi_output #(.HD_PREVIEW(UPGRADE),.FONT_FILE(HDMI_FONT_FILE)) u_display(
            .sys_clk(clk_100mhz),.sys_rst_n(rst_100mhz_n),
            .pixel_clk(hdmi_pixel_clk),.pixel_clk_5x(hdmi_pixel_clk_5x),.pixel_rst_n(hdmi_pixel_rst_n),
            .camera_we(UPGRADE!=0?preview_we:cam_we),.camera_word_addr(UPGRADE!=0?preview_addr:{1'b0,cam_addr}),.camera_wdata(UPGRADE!=0?preview_data:cam_data),.camera_frame_published(UPGRADE!=0?preview_pub:cam_publish),.camera_latest_frame_id(UPGRADE!=0?preview_id:cam_id),
            .result_valid(v_frame_valid),.result_frame_id(v_frame_id),.result_detected(v_detected),
            .box_x0(v_raw_x0),.box_y0(v_raw_y0),.box_x1(v_raw_x1),.box_y1(v_raw_y1),
            .locator_fresh(v_detected && (v_now_ms-v_acq_ms)<=250),.gesture_valid(e_valid),.gesture_class(e_class),.task_status(ui_task),.interaction(ui_interaction),
            .stage_loc_cycles(measure_loc),.stage_cls_cycles(measure_cls),.vision_age(v_now_ms-v_acq_ms),
            .arm_status(ui_arm),.arm_error(ui_error),.feedback_masks(ui_masks),.feedback_age(ui_age),.motion_frames(ui_frames),
            .tmds_clk_p(hdmi_clk_p),.tmds_clk_n(hdmi_clk_n),.tmds_data_p(hdmi_data_p),.tmds_data_n(hdmi_data_n));
    end else begin:g_no_hdmi
        assign hdmi_clk_p=1'b0;assign hdmi_clk_n=1'b1;assign hdmi_data_p=3'b0;assign hdmi_data_n=3'b111;
    end endgenerate
endmodule
