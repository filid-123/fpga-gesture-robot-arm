// ============================================================================
// Block Name : s4_axil_window
// Description: AXI4-Lite window gate of the Phase 3 S4 task controller, placed
//              in front of one unchanged S1/S2 AXI4-Lite slave.  Two requesters
//              share the downstream slave, one transaction at a time:
//                * the PS (AXI4-Lite slave port s_*), and
//                * the S4 motion link (internal request port i_*, HAS_INTERNAL=1).
//              Pending requests are served alternately (PS write, PS read and
//              internal requests; no starvation).
//   ps_write_block=1 (S4 owns motion): a PS write is NOT forwarded; it is
//     answered OKAY and reported by ps_write_dropped / dropped_addr.  OKAY and
//     not SLVERR, because a bus error on PYNQ MMIO kills the PS process; the S4
//     EVENT register records the drop.  PS reads are always forwarded.
//   Downstream response timeout (TIMEOUT_CYCLES without handshake/response):
//     the requester gets SLVERR (internal: i_rsp_timeout=1), axi_timeout pulses,
//     and the window stays "hung" (valid/ready kept as AXI requires) until the
//     late response is drained; requests arriving while hung are answered
//     SLVERR without being forwarded.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz s_axi_aclk)
// Truth boundary: source candidate; supplementary Icarus run only.
// ============================================================================

`timescale 1ns / 1ps

module s4_axil_window #(
    parameter integer ADDR_W         = 12,
    parameter integer TIMEOUT_CYCLES = 4096,
    parameter integer HAS_INTERNAL   = 1
) (
    input  wire              clk,
    input  wire              rst_n,
    // PS-facing AXI4-Lite slave
    input  wire [ADDR_W-1:0] s_awaddr,
    input  wire              s_awvalid,
    output wire              s_awready,
    input  wire [31:0]       s_wdata,
    input  wire [3:0]        s_wstrb,
    input  wire              s_wvalid,
    output wire              s_wready,
    output reg  [1:0]        s_bresp,
    output reg               s_bvalid,
    input  wire              s_bready,
    input  wire [ADDR_W-1:0] s_araddr,
    input  wire              s_arvalid,
    output wire              s_arready,
    output reg  [31:0]       s_rdata,
    output reg  [1:0]        s_rresp,
    output reg               s_rvalid,
    input  wire              s_rready,
    // internal requester (S4 motion link)
    input  wire              i_req_valid,
    output wire              i_req_ready,
    input  wire              i_req_write,
    input  wire [ADDR_W-1:0] i_req_addr,
    input  wire [31:0]       i_req_wdata,
    output reg               i_rsp_valid,
    output reg  [31:0]       i_rsp_rdata,
    output reg  [1:0]        i_rsp_resp,
    output reg               i_rsp_timeout,
    // policy / status
    input  wire              ps_write_block,
    output reg               ps_write_dropped,
    output reg  [ADDR_W-1:0] dropped_addr,
    output reg               axi_timeout,
    output wire              hung,
    // downstream AXI4-Lite master
    output reg  [ADDR_W-1:0] m_awaddr,
    output reg               m_awvalid,
    input  wire              m_awready,
    output reg  [31:0]       m_wdata,
    output reg  [3:0]        m_wstrb,
    output reg               m_wvalid,
    input  wire              m_wready,
    input  wire [1:0]        m_bresp,
    input  wire              m_bvalid,
    output reg               m_bready,
    output reg  [ADDR_W-1:0] m_araddr,
    output reg               m_arvalid,
    input  wire              m_arready,
    input  wire [31:0]       m_rdata,
    input  wire [1:0]        m_rresp,
    input  wire              m_rvalid,
    output reg               m_rready
);

    localparam [1:0] RESP_OKAY = 2'b00, RESP_SLVERR = 2'b10;
    localparam [1:0] SRC_PSW = 2'd0, SRC_PSR = 2'd1, SRC_INT = 2'd2;
    localparam [1:0] W_IDLE = 2'd0, W_BUSY = 2'd1, W_DRAIN = 2'd2;

    // ---------------------------------------------------------------- PS capture
    reg              aw_full, w_full, ar_full;
    reg [ADDR_W-1:0] aw_addr, ar_addr;
    reg [31:0]       w_data;
    reg [3:0]        w_strb;
    assign s_awready = !aw_full;
    assign s_wready  = !w_full;
    assign s_arready = !ar_full;

    // ---------------------------------------------------------------- internal capture
    reg              i_full, i_write;
    reg [ADDR_W-1:0] i_addr;
    reg [31:0]       i_wdata;
    assign i_req_ready = (HAS_INTERNAL != 0) && !i_full;

    reg [1:0]  st;
    reg [1:0]  src;
    reg [1:0]  rr;                      // next source to prefer
    reg [31:0] timer;
    assign hung = (st == W_DRAIN);

    wire ps_w_pending = aw_full && w_full && !s_bvalid;
    wire ps_r_pending = ar_full && !s_rvalid;
    wire int_pending  = i_full;

    // choose a pending source, starting at rr
    reg        pick_valid;
    reg [1:0]  pick;
    always @(*) begin
        pick_valid = 1'b0;
        pick = SRC_PSW;
        case (rr)
            SRC_PSW: begin
                if (ps_w_pending)      begin pick_valid = 1'b1; pick = SRC_PSW; end
                else if (ps_r_pending) begin pick_valid = 1'b1; pick = SRC_PSR; end
                else if (int_pending)  begin pick_valid = 1'b1; pick = SRC_INT; end
            end
            SRC_PSR: begin
                if (ps_r_pending)      begin pick_valid = 1'b1; pick = SRC_PSR; end
                else if (int_pending)  begin pick_valid = 1'b1; pick = SRC_INT; end
                else if (ps_w_pending) begin pick_valid = 1'b1; pick = SRC_PSW; end
            end
            default: begin
                if (int_pending)       begin pick_valid = 1'b1; pick = SRC_INT; end
                else if (ps_w_pending) begin pick_valid = 1'b1; pick = SRC_PSW; end
                else if (ps_r_pending) begin pick_valid = 1'b1; pick = SRC_PSR; end
            end
        endcase
    end

    task respond;                       // deliver a response to the current source
        input [1:0]  rsrc;
        input [1:0]  resp;
        input [31:0] rdata;
        input        tmo;
        begin
            case (rsrc)
                SRC_PSW: begin s_bvalid <= 1'b1; s_bresp <= resp; end
                SRC_PSR: begin s_rvalid <= 1'b1; s_rresp <= resp; s_rdata <= rdata; end
                default: begin
                    i_rsp_valid <= 1'b1; i_rsp_resp <= resp; i_rsp_rdata <= rdata; i_rsp_timeout <= tmo;
                end
            endcase
        end
    endtask

    always @(posedge clk) begin
        if (!rst_n) begin
            aw_full <= 1'b0; w_full <= 1'b0; ar_full <= 1'b0; i_full <= 1'b0;
            aw_addr <= {ADDR_W{1'b0}}; ar_addr <= {ADDR_W{1'b0}}; w_data <= 32'd0; w_strb <= 4'd0;
            i_write <= 1'b0; i_addr <= {ADDR_W{1'b0}}; i_wdata <= 32'd0;
            s_bvalid <= 1'b0; s_bresp <= RESP_OKAY; s_rvalid <= 1'b0; s_rresp <= RESP_OKAY; s_rdata <= 32'd0;
            i_rsp_valid <= 1'b0; i_rsp_rdata <= 32'd0; i_rsp_resp <= RESP_OKAY; i_rsp_timeout <= 1'b0;
            ps_write_dropped <= 1'b0; dropped_addr <= {ADDR_W{1'b0}}; axi_timeout <= 1'b0;
            m_awaddr <= {ADDR_W{1'b0}}; m_awvalid <= 1'b0; m_wdata <= 32'd0; m_wstrb <= 4'd0; m_wvalid <= 1'b0;
            m_bready <= 1'b0; m_araddr <= {ADDR_W{1'b0}}; m_arvalid <= 1'b0; m_rready <= 1'b0;
            st <= W_IDLE; src <= SRC_PSW; rr <= SRC_PSW; timer <= 32'd0;
        end else begin
            i_rsp_valid <= 1'b0;
            i_rsp_timeout <= 1'b0;
            ps_write_dropped <= 1'b0;
            axi_timeout <= 1'b0;
            // ---- request capture
            if (s_awvalid && !aw_full) begin aw_full <= 1'b1; aw_addr <= s_awaddr; end
            if (s_wvalid && !w_full)   begin w_full <= 1'b1; w_data <= s_wdata; w_strb <= s_wstrb; end
            if (s_arvalid && !ar_full) begin ar_full <= 1'b1; ar_addr <= s_araddr; end
            if (i_req_valid && i_req_ready) begin
                i_full <= 1'b1; i_write <= i_req_write; i_addr <= i_req_addr; i_wdata <= i_req_wdata;
            end
            // ---- PS response handshakes (free the captured request afterwards)
            if (s_bvalid && s_bready) begin s_bvalid <= 1'b0; aw_full <= 1'b0; w_full <= 1'b0; end
            if (s_rvalid && s_rready) begin s_rvalid <= 1'b0; ar_full <= 1'b0; end

            case (st)
                W_IDLE: begin
                    if (pick_valid) begin
                        src <= pick;
                        rr <= (pick == SRC_INT) ? SRC_PSW : pick + 2'd1;
                        if (pick == SRC_PSW && ps_write_block) begin
                            // dropped PS write: answered here, never forwarded
                            s_bvalid <= 1'b1; s_bresp <= RESP_OKAY;
                            ps_write_dropped <= 1'b1; dropped_addr <= aw_addr;
                        end else begin
                            timer <= 32'd0;
                            if (pick == SRC_PSW) begin
                                m_awaddr <= aw_addr; m_awvalid <= 1'b1;
                                m_wdata <= w_data; m_wstrb <= w_strb; m_wvalid <= 1'b1; m_bready <= 1'b1;
                            end else if (pick == SRC_PSR) begin
                                m_araddr <= ar_addr; m_arvalid <= 1'b1; m_rready <= 1'b1;
                            end else if (i_write) begin
                                m_awaddr <= i_addr; m_awvalid <= 1'b1;
                                m_wdata <= i_wdata; m_wstrb <= 4'hF; m_wvalid <= 1'b1; m_bready <= 1'b1;
                            end else begin
                                m_araddr <= i_addr; m_arvalid <= 1'b1; m_rready <= 1'b1;
                            end
                            st <= W_BUSY;
                        end
                    end
                end
                W_BUSY, W_DRAIN: begin
                    timer <= timer + 32'd1;
                    if (m_awvalid && m_awready) m_awvalid <= 1'b0;
                    if (m_wvalid && m_wready)   m_wvalid <= 1'b0;
                    if (m_arvalid && m_arready) m_arvalid <= 1'b0;
                    if (m_bready && m_bvalid) begin
                        m_bready <= 1'b0;
                        if (st == W_BUSY) begin
                            respond(src, m_bresp, 32'd0, 1'b0);
                            if (src == SRC_INT) i_full <= 1'b0;
                        end
                        st <= W_IDLE;
                    end else if (m_rready && m_rvalid) begin
                        m_rready <= 1'b0;
                        if (st == W_BUSY) begin
                            respond(src, m_rresp, m_rdata, 1'b0);
                            if (src == SRC_INT) i_full <= 1'b0;
                        end
                        st <= W_IDLE;
                    end else if (st == W_BUSY && timer >= TIMEOUT_CYCLES) begin
                        respond(src, RESP_SLVERR, 32'd0, 1'b1);
                        if (src == SRC_INT) i_full <= 1'b0;
                        axi_timeout <= 1'b1;
                        st <= W_DRAIN;
                    end
                    // while hung: every new request is answered SLVERR, not forwarded
                    if (st == W_DRAIN && !(m_bready && m_bvalid) && !(m_rready && m_rvalid)) begin
                        if (ps_w_pending && !s_bvalid) begin s_bvalid <= 1'b1; s_bresp <= RESP_SLVERR; end
                        else if (ps_r_pending && !s_rvalid) begin
                            s_rvalid <= 1'b1; s_rresp <= RESP_SLVERR; s_rdata <= 32'd0;
                        end else if (int_pending && !i_rsp_valid) begin
                            i_rsp_valid <= 1'b1; i_rsp_resp <= RESP_SLVERR; i_rsp_rdata <= 32'd0;
                            i_rsp_timeout <= 1'b1; i_full <= 1'b0;
                        end
                    end
                end
                default: st <= W_IDLE;
            endcase
        end
    end

endmodule
