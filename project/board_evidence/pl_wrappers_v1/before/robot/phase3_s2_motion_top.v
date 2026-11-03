// ============================================================================
// Block Name : phase3_s2_motion_top
// Description: Vivado Block Design module reference for the isolated Phase 3
//              S2 motion overlay.  S1 modules are instantiated UNCHANGED
//              (byte-identical to S1 v0.1.1); S2 adds the planner and an
//              explicit compatibility mux in front of the arm backend:
//
//   s_axi_traj (0x43C2_0000) -> trajectory_axi_lite_top  ABI 0x0000_3002 --.
//                                                                          |-> motion_sample_mux
//   s_axi_plan (0x43C4_0000) -> planner_axi_top          ABI 0x0000_3201 --'        |
//                                (SOURCE_SELECT, reset = S1 trajectory)             v
//   s_axi_arm  (0x43C3_0000) -> arm_backend_axi_top      ABI 0x0000_3101 -> pins
//
//              With SOURCE_SELECT = 0 (reset) the overlay behaves like the S1
//              overlay: S1 software and ABIs work unmodified.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: s_axi_aclk (100 MHz FCLK0) for all three interfaces.
//
// AWPROT/ARPROT are accepted for complete AXI4-Lite interfaces and unused.
// Truth boundary: source candidate.  Supplementary Icarus Verilog run only;
// BD/XSim/synthesis/implementation/board not run.
// ============================================================================

`timescale 1ns / 1ps

module phase3_s2_motion_top #(
    parameter integer SMOOTH_PROFILE=0,
    parameter integer HAS_ROARM         = 1,
    parameter integer HAS_SO101         = 1,
    parameter integer DEBOUNCE_CYCLES   = 1_000_000,
    parameter integer MIN_PERIOD_CYCLES = 512,
    parameter integer ROARM_FEEDBACK_EVERY = 1
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 s_axi_aclk CLK",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_aclk, ASSOCIATED_BUSIF s_axi_traj:s_axi_arm:s_axi_plan, ASSOCIATED_RESET s_axi_aresetn, FREQ_HZ 100000000" *)
    input  wire         s_axi_aclk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 s_axi_aresetn RST",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_aresetn, POLARITY ACTIVE_LOW" *)
    input  wire         s_axi_aresetn,

    // ------------------------------------------------ trajectory window (S1, unchanged)
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj AWADDR",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_traj, PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 8, FREQ_HZ 100000000" *)
    input  wire [7:0]    s_axi_traj_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj AWPROT" *)
    input  wire [2:0]    s_axi_traj_awprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj AWVALID" *)
    input  wire          s_axi_traj_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj AWREADY" *)
    output wire          s_axi_traj_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj WDATA" *)
    input  wire [31:0]   s_axi_traj_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj WSTRB" *)
    input  wire [3:0]    s_axi_traj_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj WVALID" *)
    input  wire          s_axi_traj_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj WREADY" *)
    output wire          s_axi_traj_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj BRESP" *)
    output wire [1:0]    s_axi_traj_bresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj BVALID" *)
    output wire          s_axi_traj_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj BREADY" *)
    input  wire          s_axi_traj_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj ARADDR" *)
    input  wire [7:0]    s_axi_traj_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj ARPROT" *)
    input  wire [2:0]    s_axi_traj_arprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj ARVALID" *)
    input  wire          s_axi_traj_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj ARREADY" *)
    output wire          s_axi_traj_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj RDATA" *)
    output wire [31:0]   s_axi_traj_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj RRESP" *)
    output wire [1:0]    s_axi_traj_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj RVALID" *)
    output wire          s_axi_traj_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj RREADY" *)
    input  wire          s_axi_traj_rready,
    // ------------------------------------------------ arm backend window (S1, unchanged)
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm AWADDR",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_arm, PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 12, FREQ_HZ 100000000" *)
    input  wire [11:0]   s_axi_arm_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm AWPROT" *)
    input  wire [2:0]    s_axi_arm_awprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm AWVALID" *)
    input  wire          s_axi_arm_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm AWREADY" *)
    output wire          s_axi_arm_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm WDATA" *)
    input  wire [31:0]   s_axi_arm_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm WSTRB" *)
    input  wire [3:0]    s_axi_arm_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm WVALID" *)
    input  wire          s_axi_arm_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm WREADY" *)
    output wire          s_axi_arm_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm BRESP" *)
    output wire [1:0]    s_axi_arm_bresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm BVALID" *)
    output wire          s_axi_arm_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm BREADY" *)
    input  wire          s_axi_arm_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm ARADDR" *)
    input  wire [11:0]   s_axi_arm_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm ARPROT" *)
    input  wire [2:0]    s_axi_arm_arprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm ARVALID" *)
    input  wire          s_axi_arm_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm ARREADY" *)
    output wire          s_axi_arm_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm RDATA" *)
    output wire [31:0]   s_axi_arm_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm RRESP" *)
    output wire [1:0]    s_axi_arm_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm RVALID" *)
    output wire          s_axi_arm_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm RREADY" *)
    input  wire          s_axi_arm_rready,
    // ------------------------------------------------ planner window (S2)
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan AWADDR",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_plan, PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 12, FREQ_HZ 100000000" *)
    input  wire [11:0]   s_axi_plan_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan AWPROT" *)
    input  wire [2:0]    s_axi_plan_awprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan AWVALID" *)
    input  wire          s_axi_plan_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan AWREADY" *)
    output wire          s_axi_plan_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan WDATA" *)
    input  wire [31:0]   s_axi_plan_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan WSTRB" *)
    input  wire [3:0]    s_axi_plan_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan WVALID" *)
    input  wire          s_axi_plan_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan WREADY" *)
    output wire          s_axi_plan_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan BRESP" *)
    output wire [1:0]    s_axi_plan_bresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan BVALID" *)
    output wire          s_axi_plan_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan BREADY" *)
    input  wire          s_axi_plan_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan ARADDR" *)
    input  wire [11:0]   s_axi_plan_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan ARPROT" *)
    input  wire [2:0]    s_axi_plan_arprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan ARVALID" *)
    input  wire          s_axi_plan_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan ARREADY" *)
    output wire          s_axi_plan_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan RDATA" *)
    output wire [31:0]   s_axi_plan_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan RRESP" *)
    output wire [1:0]    s_axi_plan_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan RVALID" *)
    output wire          s_axi_plan_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_plan RREADY" *)
    input  wire          s_axi_plan_rready,

    (* X_INTERFACE_INFO = "xilinx.com:signal:interrupt:1.0 irq_traj INTERRUPT",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME irq_traj, SENSITIVITY LEVEL_HIGH" *)

    input wire native_valid,
    output wire native_ready,
    input wire [2:0] native_code,
    input wire [191:0] native_target, native_vmax, native_amax,
    input wire [15:0] native_n, native_na,
    input wire native_profile,
    input wire [31:0] native_period, native_stall,
    output wire native_done, native_ok,
    output wire [31:0] native_status, native_error, native_index,
    input wire native_snap,
    output wire native_snap_ready, native_snap_done,
    output wire [31:0] native_arm_status, native_arm_error, native_masks, native_age, native_frames,
    output wire [191:0] native_last,
    output wire         irq_traj,
    (* X_INTERFACE_INFO = "xilinx.com:signal:interrupt:1.0 irq_arm INTERRUPT",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME irq_arm, SENSITIVITY LEVEL_HIGH" *)
    output wire         irq_arm,
    (* X_INTERFACE_INFO = "xilinx.com:signal:interrupt:1.0 irq_plan INTERRUPT",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME irq_plan, SENSITIVITY LEVEL_HIGH" *)
    output wire         irq_plan,

    // Physical pins: identical to S1 (constraints/phase3_s1_armpath_*.xdc).
    output wire         arm_uart_tx,
    input  wire         arm_uart_rx,
    output wire         bus_tx,
    input  wire         bus_rx,
    output wire         bus_dir,
    input  wire         motion_enable_in
);

    wire         traj_valid;
    wire         traj_ready;
    wire [191:0] traj_data;
    wire         traj_last;
    wire         traj_open;
    wire         traj_segment_busy;
    wire         downstream_pending;
    wire         plan_delivered;
    wire         plan_valid;
    wire         plan_ready;
    wire [191:0] plan_data;
    wire         arm_valid;
    wire         arm_ready;
    wire [191:0] arm_data;
    wire         source_sel;
    wire [191:0] last_delivered;
    wire         last_valid;

    // Retired S1 address: reads return zero, writes drain without motion.
    reg old_aw, old_w, old_b, old_r;
    assign s_axi_traj_awready = !old_aw && !old_b;
    assign s_axi_traj_wready = !old_w && !old_b;
    assign s_axi_traj_bvalid = old_b;
    assign s_axi_traj_bresp = 2'b00;
    assign s_axi_traj_arready = !old_r;
    assign s_axi_traj_rvalid = old_r;
    assign s_axi_traj_rdata = 32'd0;
    assign s_axi_traj_rresp = 2'b00;
    assign irq_traj = 1'b0;
    assign traj_valid=1'b0;
    assign traj_data=192'd0;
    assign traj_last=1'b0;
    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin old_aw<=0; old_w<=0; old_b<=0; old_r<=0; end
        else begin
            if (s_axi_traj_awvalid && s_axi_traj_awready) old_aw<=1;
            if (s_axi_traj_wvalid && s_axi_traj_wready) old_w<=1;
            if (old_aw && old_w && !old_b) begin old_aw<=0; old_w<=0; old_b<=1; end
            else if (old_b && s_axi_traj_bready) old_b<=0;
            if (s_axi_traj_arvalid && s_axi_traj_arready) old_r<=1;
            else if (old_r && s_axi_traj_rready) old_r<=0;
        end
    end

    // keep_hierarchy: the S2 increment (u_planner + u_mux) stays a separate
    // cell so report_utilization -cells can measure it against its budget.
    (* keep_hierarchy = "yes" *)
    planner_axi_top #(.SMOOTH_PROFILE(SMOOTH_PROFILE),
        .C_S_AXI_DATA_WIDTH(32),
        .C_S_AXI_ADDR_WIDTH(12),
        .MIN_PERIOD_CYCLES(MIN_PERIOD_CYCLES),
        .ABI_VERSION(SMOOTH_PROFILE!=0?32'h0000_3203:32'h0000_3202)
    ) u_planner (
        .native_valid(native_valid), .native_ready(native_ready), .native_code(native_code),
        .native_target(native_target), .native_vmax(native_vmax), .native_amax(native_amax),
        .native_n(native_n), .native_na(native_na), .native_profile(native_profile),
        .native_period(native_period), .native_stall(native_stall),
        .native_done(native_done), .native_ok(native_ok), .native_status(native_status),
        .native_error(native_error), .native_index(native_index),

        .S_AXI_ACLK(s_axi_aclk),
        .S_AXI_ARESETN(s_axi_aresetn),
        .S_AXI_AWADDR(s_axi_plan_awaddr),
        .S_AXI_AWVALID(s_axi_plan_awvalid),
        .S_AXI_AWREADY(s_axi_plan_awready),
        .S_AXI_WDATA(s_axi_plan_wdata),
        .S_AXI_WSTRB(s_axi_plan_wstrb),
        .S_AXI_WVALID(s_axi_plan_wvalid),
        .S_AXI_WREADY(s_axi_plan_wready),
        .S_AXI_BRESP(s_axi_plan_bresp),
        .S_AXI_BVALID(s_axi_plan_bvalid),
        .S_AXI_BREADY(s_axi_plan_bready),
        .S_AXI_ARADDR(s_axi_plan_araddr),
        .S_AXI_ARVALID(s_axi_plan_arvalid),
        .S_AXI_ARREADY(s_axi_plan_arready),
        .S_AXI_RDATA(s_axi_plan_rdata),
        .S_AXI_RRESP(s_axi_plan_rresp),
        .S_AXI_RVALID(s_axi_plan_rvalid),
        .S_AXI_RREADY(s_axi_plan_rready),
        .irq(irq_plan),
        .m_sample_valid(plan_valid),
        .m_sample_ready(plan_ready),
        .m_sample_data(plan_data),
        .source_sel(source_sel),
        .traj_sample_valid(traj_valid),
        .traj_segment_open(traj_open),
        .traj_segment_busy(traj_segment_busy),
        .downstream_pending(downstream_pending),
        .plan_delivered(plan_delivered),
        .last_delivered(last_delivered),
        .last_valid(last_valid)
    );

    (* keep_hierarchy = "yes" *)
    motion_sample_mux u_mux (
        .clk(s_axi_aclk),
        .rst_n(s_axi_aresetn),
        .sel(source_sel),
        .traj_valid(traj_valid),
        .traj_ready(traj_ready),
        .traj_data(traj_data),
        .traj_last(traj_last),
        .traj_axi_awaddr(8'd0),
        .traj_axi_awvalid(1'b0),
        .traj_axi_awready(1'b0),
        .traj_axi_wdata(32'd0),
        .traj_axi_wstrb(4'd0),
        .traj_axi_wvalid(1'b0),
        .traj_axi_wready(1'b0),
        .traj_axi_bresp(2'd0),
        .traj_axi_bvalid(1'b0),
        .traj_axi_bready(1'b0),
        .plan_valid(plan_valid),
        .plan_ready(plan_ready),
        .plan_data(plan_data),
        .m_valid(arm_valid),
        .m_ready(arm_ready),
        .m_data(arm_data),
        .last_data(last_delivered),
        .last_valid(last_valid),
        .traj_open(traj_open),
        .traj_segment_busy(traj_segment_busy),
        .downstream_pending(downstream_pending),
        .plan_delivered(plan_delivered)
    );

    arm_backend_axi_top #(
        .C_S_AXI_DATA_WIDTH(32),
        .C_S_AXI_ADDR_WIDTH(12),
        .HAS_ROARM(HAS_ROARM),
        .HAS_SO101(HAS_SO101),
        .DEBOUNCE_CYCLES(DEBOUNCE_CYCLES),.ROARM_FEEDBACK_EVERY(ROARM_FEEDBACK_EVERY)
    ) u_arm_backend (
        .native_snap(native_snap), .native_snap_ready(native_snap_ready), .native_snap_done(native_snap_done),
        .native_status(native_arm_status), .native_error(native_arm_error), .native_masks(native_masks),
        .native_age(native_age), .native_frames(native_frames),
        .S_AXI_ACLK(s_axi_aclk),
        .S_AXI_ARESETN(s_axi_aresetn),
        .S_AXI_AWADDR(s_axi_arm_awaddr),
        .S_AXI_AWVALID(s_axi_arm_awvalid),
        .S_AXI_AWREADY(s_axi_arm_awready),
        .S_AXI_WDATA(s_axi_arm_wdata),
        .S_AXI_WSTRB(s_axi_arm_wstrb),
        .S_AXI_WVALID(s_axi_arm_wvalid),
        .S_AXI_WREADY(s_axi_arm_wready),
        .S_AXI_BRESP(s_axi_arm_bresp),
        .S_AXI_BVALID(s_axi_arm_bvalid),
        .S_AXI_BREADY(s_axi_arm_bready),
        .S_AXI_ARADDR(s_axi_arm_araddr),
        .S_AXI_ARVALID(s_axi_arm_arvalid),
        .S_AXI_ARREADY(s_axi_arm_arready),
        .S_AXI_RDATA(s_axi_arm_rdata),
        .S_AXI_RRESP(s_axi_arm_rresp),
        .S_AXI_RVALID(s_axi_arm_rvalid),
        .S_AXI_RREADY(s_axi_arm_rready),
        .irq(irq_arm),
        .s_sample_valid(arm_valid),
        .s_sample_ready(arm_ready),
        .s_sample_data(arm_data),
        .arm_uart_tx(arm_uart_tx),
        .arm_uart_rx(arm_uart_rx),
        .bus_tx(bus_tx),
        .bus_rx(bus_rx),
        .bus_dir(bus_dir),
        .motion_enable_in(motion_enable_in)
    );

    assign native_last=last_delivered;
    wire _unused_ok = &{1'b0, s_axi_traj_awprot, s_axi_traj_arprot, s_axi_arm_awprot,
                        s_axi_arm_arprot, s_axi_plan_awprot, s_axi_plan_arprot};

endmodule
