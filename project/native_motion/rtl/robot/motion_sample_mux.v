// ============================================================================
// Block Name : motion_sample_mux
// Description: Phase 3 S2 compatibility layer between the two motion sources
//              and the unchanged S1 arm backend (ABI 0x0000_3101):
//                source 0: S1 trajectory_axi_lite_top (ABI 0x0000_3002)
//                source 1: S2 planner_axi_top          (ABI 0x0000_3201)
//              192-bit samples, ready/valid, channel 0 in the low word.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz)
//
// - sel comes from the planner's SOURCE_SELECT register.  planner_axi_top
//   changes it only when the switch cannot make the commanded position jump
//   (rules in planner_axi_top), and never while the selected source offers a
//   sample, so the backend never sees a sample change under it.  Reset
//   selects the S1 trajectory, i.e. the S2 overlay behaves exactly like S1
//   until the PS selects the planner.
// - The source that is not selected gets ready = 0 and simply waits; nothing
//   is dropped or withdrawn.
// - last_data/last_valid capture every sample the backend accepts (from either
//   source): the planner's START continuity reference and the PS readback of
//   the current commanded position.  A sample the backend refuses (limit,
//   fault, cancelled by its last gate) is not accepted and not captured.
// - traj_open: an S1 segment has delivered a sample but not its last one
//   (S1 ext_sample_last).  The S1 trajectory has no continuity check of its
//   own, so the planner may not take over while an S1 segment is queued or running.
// - The one-entry elastic register adds one cycle to the backend stream and
//   holds valid/data stable under backpressure. LAST_DELIVERED updates only
//   on the backend handshake.
//
// Truth boundary: source candidate.  Supplementary Icarus Verilog run only;
// XSim and Vivado OOC checked for the S2 repair; board not run.
// ============================================================================

`timescale 1ns / 1ps

module motion_sample_mux (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         sel,              // 0 S1 trajectory, 1 S2 planner

    input  wire         traj_valid,
    output wire         traj_ready,
    input  wire [191:0] traj_data,
    input  wire         traj_last,
    // AXI write tap: tracks an accepted S1 COMMIT before the first sample.
    input  wire [7:0]   traj_axi_awaddr,
    input  wire         traj_axi_awvalid,
    input  wire         traj_axi_awready,
    input  wire [31:0]  traj_axi_wdata,
    input  wire [3:0]   traj_axi_wstrb,
    input  wire         traj_axi_wvalid,
    input  wire         traj_axi_wready,
    input  wire [1:0]   traj_axi_bresp,
    input  wire         traj_axi_bvalid,
    input  wire         traj_axi_bready,

    input  wire         plan_valid,
    output wire         plan_ready,
    input  wire [191:0] plan_data,

    output wire         m_valid,
    input  wire         m_ready,
    output wire [191:0] m_data,

    output reg  [191:0] last_data,
    output reg          last_valid,
    output reg          traj_open,
    output wire         traj_segment_busy,
    output wire         downstream_pending,
    output wire         plan_delivered
);

    // One-entry elastic register cuts the S1 BRAM -> S1 mapper path.
    // It accepts a replacement on the same cycle the previous entry drains.
    reg         buf_valid;
    reg [191:0] buf_data;
    reg         buf_is_traj;
    wire        slot_ready = !buf_valid || m_ready;
    wire        src_valid  = sel ? plan_valid : traj_valid;
    wire [191:0] src_data  = sel ? plan_data : traj_data;
    assign m_valid = buf_valid;
    assign m_data = buf_data;
    assign traj_ready = !sel && slot_ready;
    assign plan_ready = sel && slot_ready;
    assign downstream_pending = buf_valid;
    assign plan_delivered = buf_valid && m_ready && !buf_is_traj;

    reg        aw_seen;
    reg        w_seen;
    reg [7:0]  awaddr_seen;
    reg [31:0] wdata_seen;
    reg [3:0]  wstrb_seen;
    reg        segment_active;

    // S1 sample_valid is low between COMMIT and the first sample. Block
    // switching throughout a write and from successful COMMIT to last beat.
    assign traj_segment_busy = segment_active || aw_seen || w_seen ||
                               traj_axi_awvalid || traj_axi_wvalid || traj_axi_bvalid;

    initial last_data = 192'd0;              // FPGA configuration value

    always @(posedge clk) begin
        if (slot_ready && src_valid)
            buf_data <= src_data;
        if (m_valid && m_ready)
            last_data <= m_data;             // only backend-accepted position
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            last_valid <= 1'b0;
            traj_open  <= 1'b0;
            aw_seen <= 1'b0;
            w_seen <= 1'b0;
            awaddr_seen <= 8'd0;
            wdata_seen <= 32'd0;
            wstrb_seen <= 4'd0;
            segment_active <= 1'b0;
            buf_valid <= 1'b0;
            buf_is_traj <= 1'b0;
        end else begin
            if (slot_ready) begin
                buf_valid <= src_valid;
                if (src_valid)
                    buf_is_traj <= !sel;
            end
            if (traj_axi_awvalid && traj_axi_awready) begin
                aw_seen <= 1'b1;
                awaddr_seen <= traj_axi_awaddr;
            end
            if (traj_axi_wvalid && traj_axi_wready) begin
                w_seen <= 1'b1;
                wdata_seen <= traj_axi_wdata;
                wstrb_seen <= traj_axi_wstrb;
            end
            if (traj_axi_bvalid) begin
                if ((traj_axi_bresp == 2'b00) && aw_seen && w_seen &&
                    (awaddr_seen == 8'h00) && (wdata_seen == 32'h0000_0001) &&
                    (wstrb_seen == 4'hf))
                    segment_active <= 1'b1;
                if (traj_axi_bready) begin
                    aw_seen <= 1'b0;
                    w_seen <= 1'b0;
                end
            end
            if (m_valid && m_ready)
                last_valid <= 1'b1;
            if (traj_valid && traj_ready) begin
                traj_open <= !traj_last;
                if (traj_last)
                    segment_active <= 1'b0;
            end
        end
    end

endmodule
