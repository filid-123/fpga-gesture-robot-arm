// ============================================================================
// Block Name : phase3_s1_armpath_top
// Description: Vivado Block Design module reference for the isolated Phase 3
//              S1 arm data path:
//                s_axi_traj (0x43C2_0000) -> trajectory_axi_lite_top
//                               (EXTERNAL_SAMPLE_SINK=1, ABI 0x0000_3002)
//                                 |  192-bit sample ready/valid, PL only
//                                 v
//                s_axi_arm  (0x43C3_0000) -> arm_backend_axi_top (ABI 0x0000_3101)
//                                 -> arm_uart_tx/rx | bus_tx/rx/dir
//              The PS commits keyframe segments and reads status; it never
//              touches individual trajectory samples.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: s_axi_aclk (100 MHz FCLK0) for both interfaces.
//
// AWPROT/ARPROT are accepted for complete AXI4-Lite interfaces and unused.
// Truth boundary: source candidate.  Supplementary Icarus Verilog run only;
// BD/XSim/synthesis/implementation not run.
// ============================================================================

`timescale 1ns / 1ps

module phase3_s1_armpath_top #(
    parameter integer HAS_ROARM       = 1,
    parameter integer HAS_SO101       = 1,
    parameter integer DEBOUNCE_CYCLES = 1_000_000
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 s_axi_aclk CLK",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_aclk, ASSOCIATED_BUSIF s_axi_traj:s_axi_arm, ASSOCIATED_RESET s_axi_aresetn, FREQ_HZ 100000000" *)
    input  wire         s_axi_aclk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 s_axi_aresetn RST",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_aresetn, POLARITY ACTIVE_LOW" *)
    input  wire         s_axi_aresetn,

    // ------------------------------------------------ trajectory window
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj AWADDR",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_traj, PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 8, FREQ_HZ 100000000" *)
    input  wire [7:0]   s_axi_traj_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj AWPROT" *)
    input  wire [2:0]   s_axi_traj_awprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj AWVALID" *)
    input  wire         s_axi_traj_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj AWREADY" *)
    output wire         s_axi_traj_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj WDATA" *)
    input  wire [31:0]  s_axi_traj_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj WSTRB" *)
    input  wire [3:0]   s_axi_traj_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj WVALID" *)
    input  wire         s_axi_traj_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj WREADY" *)
    output wire         s_axi_traj_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj BRESP" *)
    output wire [1:0]   s_axi_traj_bresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj BVALID" *)
    output wire         s_axi_traj_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj BREADY" *)
    input  wire         s_axi_traj_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj ARADDR" *)
    input  wire [7:0]   s_axi_traj_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj ARPROT" *)
    input  wire [2:0]   s_axi_traj_arprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj ARVALID" *)
    input  wire         s_axi_traj_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj ARREADY" *)
    output wire         s_axi_traj_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj RDATA" *)
    output wire [31:0]  s_axi_traj_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj RRESP" *)
    output wire [1:0]   s_axi_traj_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj RVALID" *)
    output wire         s_axi_traj_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_traj RREADY" *)
    input  wire         s_axi_traj_rready,

    // ------------------------------------------------- arm backend window
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm AWADDR",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_arm, PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 12, FREQ_HZ 100000000" *)
    input  wire [11:0]  s_axi_arm_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm AWPROT" *)
    input  wire [2:0]   s_axi_arm_awprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm AWVALID" *)
    input  wire         s_axi_arm_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm AWREADY" *)
    output wire         s_axi_arm_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm WDATA" *)
    input  wire [31:0]  s_axi_arm_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm WSTRB" *)
    input  wire [3:0]   s_axi_arm_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm WVALID" *)
    input  wire         s_axi_arm_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm WREADY" *)
    output wire         s_axi_arm_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm BRESP" *)
    output wire [1:0]   s_axi_arm_bresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm BVALID" *)
    output wire         s_axi_arm_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm BREADY" *)
    input  wire         s_axi_arm_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm ARADDR" *)
    input  wire [11:0]  s_axi_arm_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm ARPROT" *)
    input  wire [2:0]   s_axi_arm_arprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm ARVALID" *)
    input  wire         s_axi_arm_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm ARREADY" *)
    output wire         s_axi_arm_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm RDATA" *)
    output wire [31:0]  s_axi_arm_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm RRESP" *)
    output wire [1:0]   s_axi_arm_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm RVALID" *)
    output wire         s_axi_arm_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_arm RREADY" *)
    input  wire         s_axi_arm_rready,

    (* X_INTERFACE_INFO = "xilinx.com:signal:interrupt:1.0 irq_traj INTERRUPT",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME irq_traj, SENSITIVITY LEVEL_HIGH" *)
    output wire         irq_traj,
    (* X_INTERFACE_INFO = "xilinx.com:signal:interrupt:1.0 irq_arm INTERRUPT",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME irq_arm, SENSITIVITY LEVEL_HIGH" *)
    output wire         irq_arm,

    // Physical pins (package pins are TBD in constraints; see XDC template).
    output wire         arm_uart_tx,
    input  wire         arm_uart_rx,
    output wire         bus_tx,
    input  wire         bus_rx,
    output wire         bus_dir,
    input  wire         motion_enable_in
);

    wire         sample_valid;
    wire         sample_ready;
    wire [191:0] sample_data;

    trajectory_axi_lite_top #(
        .C_S_AXI_DATA_WIDTH(32),
        .C_S_AXI_ADDR_WIDTH(8),
        .ABI_VERSION(32'h0000_3002),
        .EXTERNAL_SAMPLE_SINK(1)
    ) u_trajectory (
        .S_AXI_ACLK(s_axi_aclk),
        .S_AXI_ARESETN(s_axi_aresetn),
        .S_AXI_AWADDR(s_axi_traj_awaddr),
        .S_AXI_AWVALID(s_axi_traj_awvalid),
        .S_AXI_AWREADY(s_axi_traj_awready),
        .S_AXI_WDATA(s_axi_traj_wdata),
        .S_AXI_WSTRB(s_axi_traj_wstrb),
        .S_AXI_WVALID(s_axi_traj_wvalid),
        .S_AXI_WREADY(s_axi_traj_wready),
        .S_AXI_BRESP(s_axi_traj_bresp),
        .S_AXI_BVALID(s_axi_traj_bvalid),
        .S_AXI_BREADY(s_axi_traj_bready),
        .S_AXI_ARADDR(s_axi_traj_araddr),
        .S_AXI_ARVALID(s_axi_traj_arvalid),
        .S_AXI_ARREADY(s_axi_traj_arready),
        .S_AXI_RDATA(s_axi_traj_rdata),
        .S_AXI_RRESP(s_axi_traj_rresp),
        .S_AXI_RVALID(s_axi_traj_rvalid),
        .S_AXI_RREADY(s_axi_traj_rready),
        .irq(irq_traj),
        .ext_sample_valid(sample_valid),
        .ext_sample_ready(sample_ready),
        .ext_sample_data(sample_data),
        .ext_sample_index(),
        .ext_sample_last()
    );

    arm_backend_axi_top #(
        .C_S_AXI_DATA_WIDTH(32),
        .C_S_AXI_ADDR_WIDTH(12),
        .HAS_ROARM(HAS_ROARM),
        .HAS_SO101(HAS_SO101),
        .DEBOUNCE_CYCLES(DEBOUNCE_CYCLES)
    ) u_arm_backend (
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
        .s_sample_valid(sample_valid),
        .s_sample_ready(sample_ready),
        .s_sample_data(sample_data),
        .arm_uart_tx(arm_uart_tx),
        .arm_uart_rx(arm_uart_rx),
        .bus_tx(bus_tx),
        .bus_rx(bus_rx),
        .bus_dir(bus_dir),
        .motion_enable_in(motion_enable_in)
    );

    wire _unused_ok = &{1'b0, s_axi_traj_awprot, s_axi_traj_arprot,
                        s_axi_arm_awprot, s_axi_arm_arprot};

endmodule
