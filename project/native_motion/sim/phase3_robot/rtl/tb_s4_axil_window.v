// ============================================================================
// Testbench: tb_s4_axil_window
// Purpose  : Unit test of s4_axil_window (ADDR_W 12, TIMEOUT_CYCLES 64,
//            HAS_INTERNAL 1) against a behavioural AXI4-Lite slave with
//            register file, response latency and fault switches:
//   1 PS write/read pass-through (data, OKAY), internal write/read pass-through
//   2 slave SLVERR is passed to the PS and to the internal requester
//   3 ps_write_block: PS write answered OKAY, not forwarded, ps_write_dropped +
//     dropped_addr; PS reads and internal writes still forwarded
//   4 arbitration: internal requester saturating the window, PS write/read
//     latency stays bounded (no starvation), every transaction completes
//   5 dead slave (no B response): SLVERR after TIMEOUT_CYCLES, axi_timeout,
//     hung; requests while hung answered SLVERR without being forwarded; late
//     response drained, window usable again
//   6 slave never accepts AW (internal write): i_rsp_timeout + SLVERR, hung
//     until the slave accepts and answers, then normal operation
// Prints "PASS: tb_s4_axil_window ..." or stops with "FAIL:".
// Truth boundary: supplementary Icarus run only (XSim NOT_RUN_ENV_UNAVAILABLE).
// ============================================================================

`timescale 1ns / 1ps

module tb_s4_axil_window;
    localparam integer TMO = 64;
    localparam integer LAT = 3;
    localparam [1:0] OKAY = 2'b00, SLVERR = 2'b10;

    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    integer cycle = 0;
    always @(posedge clk) cycle <= cycle + 1;

    // PS side
    reg  [11:0] s_awaddr = 0, s_araddr = 0;
    reg         s_awvalid = 0, s_wvalid = 0, s_bready = 0, s_arvalid = 0, s_rready = 0;
    reg  [31:0] s_wdata = 0;
    wire        s_awready, s_wready, s_bvalid, s_arready, s_rvalid;
    wire [1:0]  s_bresp, s_rresp;
    wire [31:0] s_rdata;
    // internal side
    reg         i_req_valid = 0, i_req_write = 0;
    reg  [11:0] i_req_addr = 0;
    reg  [31:0] i_req_wdata = 0;
    wire        i_req_ready, i_rsp_valid, i_rsp_timeout;
    wire [31:0] i_rsp_rdata;
    wire [1:0]  i_rsp_resp;
    reg         ps_write_block = 0;
    wire        ps_write_dropped, axi_timeout, hung;
    wire [11:0] dropped_addr;
    // downstream
    wire [11:0] m_awaddr, m_araddr;
    wire        m_awvalid, m_wvalid, m_bready, m_arvalid, m_rready;
    wire [31:0] m_wdata;
    wire [3:0]  m_wstrb;
    reg         m_awready = 0, m_wready = 0, m_bvalid = 0, m_arready = 0, m_rvalid = 0;
    reg  [1:0]  m_bresp = 0, m_rresp = 0;
    reg  [31:0] m_rdata = 0;

    s4_axil_window #(.ADDR_W(12), .TIMEOUT_CYCLES(TMO), .HAS_INTERNAL(1)) dut (
        .clk(clk), .rst_n(rst_n),
        .s_awaddr(s_awaddr), .s_awvalid(s_awvalid), .s_awready(s_awready), .s_wdata(s_wdata), .s_wstrb(4'hF),
        .s_wvalid(s_wvalid), .s_wready(s_wready), .s_bresp(s_bresp), .s_bvalid(s_bvalid), .s_bready(s_bready),
        .s_araddr(s_araddr), .s_arvalid(s_arvalid), .s_arready(s_arready), .s_rdata(s_rdata), .s_rresp(s_rresp),
        .s_rvalid(s_rvalid), .s_rready(s_rready),
        .i_req_valid(i_req_valid), .i_req_ready(i_req_ready), .i_req_write(i_req_write), .i_req_addr(i_req_addr),
        .i_req_wdata(i_req_wdata), .i_rsp_valid(i_rsp_valid), .i_rsp_rdata(i_rsp_rdata), .i_rsp_resp(i_rsp_resp),
        .i_rsp_timeout(i_rsp_timeout),
        .ps_write_block(ps_write_block), .ps_write_dropped(ps_write_dropped), .dropped_addr(dropped_addr),
        .axi_timeout(axi_timeout), .hung(hung),
        .m_awaddr(m_awaddr), .m_awvalid(m_awvalid), .m_awready(m_awready), .m_wdata(m_wdata), .m_wstrb(m_wstrb),
        .m_wvalid(m_wvalid), .m_wready(m_wready), .m_bresp(m_bresp), .m_bvalid(m_bvalid), .m_bready(m_bready),
        .m_araddr(m_araddr), .m_arvalid(m_arvalid), .m_arready(m_arready), .m_rdata(m_rdata), .m_rresp(m_rresp),
        .m_rvalid(m_rvalid), .m_rready(m_rready));

    // ---------------------------------------------------------------- behavioural slave
    reg  [31:0] mem [0:1023];
    reg         hold_resp = 0;          // 1: never answer (dead slave) until released
    reg         block_aw = 0;           // 1: never accept AW
    integer     aw_count = 0, ar_count = 0, ev_timeout = 0, ev_drop = 0;
    reg         aw_got = 0, w_got = 0, r_busy = 0;
    reg  [11:0] w_addr = 0, r_addr = 0;
    reg  [31:0] w_data = 0;
    integer     b_timer = 0, r_timer = 0;
    integer     k;
    initial for (k = 0; k < 1024; k = k + 1) mem[k] = 32'hA000_0000 + k;

    always @(posedge clk) begin
        if (ps_write_dropped) ev_drop <= ev_drop + 1;
        if (axi_timeout) ev_timeout <= ev_timeout + 1;
        m_awready <= !aw_got && !block_aw;
        m_wready  <= !w_got;
        m_arready <= !r_busy;
        if (m_awvalid && m_awready) begin aw_got <= 1'b1; w_addr <= m_awaddr; aw_count <= aw_count + 1; m_awready <= 1'b0; end
        if (m_wvalid && m_wready)   begin w_got <= 1'b1; w_data <= m_wdata; m_wready <= 1'b0; end
        if (aw_got && w_got && !m_bvalid) begin
            b_timer <= b_timer + 1;
            if (b_timer >= LAT && !hold_resp) begin
                m_bvalid <= 1'b1;
                m_bresp <= (w_addr == 12'hFFC) ? SLVERR : OKAY;
                if (w_addr != 12'hFFC) mem[w_addr[11:2]] <= w_data;
            end
        end
        if (m_bvalid && m_bready) begin m_bvalid <= 1'b0; aw_got <= 1'b0; w_got <= 1'b0; b_timer <= 0; end
        if (m_arvalid && m_arready) begin r_busy <= 1'b1; r_addr <= m_araddr; ar_count <= ar_count + 1; m_arready <= 1'b0; end
        if (r_busy && !m_rvalid) begin
            r_timer <= r_timer + 1;
            if (r_timer >= LAT && !hold_resp) begin
                m_rvalid <= 1'b1;
                m_rresp <= (r_addr == 12'hFFC) ? SLVERR : OKAY;
                m_rdata <= mem[r_addr[11:2]];
            end
        end
        if (m_rvalid && m_rready) begin m_rvalid <= 1'b0; r_busy <= 1'b0; r_timer <= 0; end
        if (cycle > 200000) $fatal(1, "FAIL: watchdog");
    end

    // ---------------------------------------------------------------- requester tasks
    // handshakes are sampled right after the clock edge (pre-edge values), as in tb_s4_axi_tasks.vh
    integer ps_lat;
    task ps_write;
        input [11:0] addr;
        input [31:0] data;
        input [1:0]  expect_resp;
        integer t0, guard;
        reg aw_ok, w_ok, b_ok;
        reg [1:0] resp;
        begin
            @(negedge clk);
            s_awaddr = addr; s_wdata = data; s_awvalid = 1'b1; s_wvalid = 1'b1; s_bready = 1'b1;
            t0 = cycle; guard = 0; aw_ok = 1'b0; w_ok = 1'b0; b_ok = 1'b0;
            while (!b_ok) begin
                @(posedge clk);
                if (s_awready) aw_ok = 1'b1;
                if (s_wready) w_ok = 1'b1;
                if (s_bvalid) begin b_ok = 1'b1; resp = s_bresp; end
                #1;
                if (aw_ok) s_awvalid = 1'b0;
                if (w_ok) s_wvalid = 1'b0;
                guard = guard + 1;
                if (guard > 10 * TMO) $fatal(1, "FAIL: PS write 0x%03h no response", addr);
            end
            @(negedge clk); s_bready = 1'b0;
            if (resp !== expect_resp) $fatal(1, "FAIL: PS write 0x%03h resp %0d expected %0d", addr, resp, expect_resp);
            ps_lat = cycle - t0;
        end
    endtask

    task ps_read;
        input  [11:0] addr;
        input  [1:0]  expect_resp;
        output [31:0] data;
        integer t0, guard;
        reg ar_ok, r_ok;
        reg [1:0] resp;
        begin
            @(negedge clk);
            s_araddr = addr; s_arvalid = 1'b1; s_rready = 1'b1;
            t0 = cycle; guard = 0; ar_ok = 1'b0; r_ok = 1'b0;
            while (!r_ok) begin
                @(posedge clk);
                if (s_arready) ar_ok = 1'b1;
                if (s_rvalid) begin r_ok = 1'b1; data = s_rdata; resp = s_rresp; end
                #1;
                if (ar_ok) s_arvalid = 1'b0;
                guard = guard + 1;
                if (guard > 10 * TMO) $fatal(1, "FAIL: PS read 0x%03h no response", addr);
            end
            @(negedge clk); s_rready = 1'b0;
            if (resp !== expect_resp) $fatal(1, "FAIL: PS read 0x%03h resp %0d expected %0d", addr, resp, expect_resp);
            ps_lat = cycle - t0;
        end
    endtask

    task int_req;                        // i_rsp_* is a one-cycle pulse
        input         wr;
        input  [11:0] addr;
        input  [31:0] data;
        input  [1:0]  expect_resp;
        input         expect_tmo;
        output [31:0] rdata;
        integer guard;
        reg ok;
        begin
            @(negedge clk);
            i_req_valid = 1'b1; i_req_write = wr; i_req_addr = addr; i_req_wdata = data;
            ok = 1'b0;
            while (!ok) begin
                @(posedge clk);
                if (i_req_ready) ok = 1'b1;
                #1;
            end
            i_req_valid = 1'b0;
            guard = 0;
            while (!i_rsp_valid) begin
                @(posedge clk); #1;
                guard = guard + 1;
                if (guard > 10 * TMO) $fatal(1, "FAIL: internal request 0x%03h no response", addr);
            end
            rdata = i_rsp_rdata;
            if (i_rsp_resp !== expect_resp || i_rsp_timeout !== expect_tmo)
                $fatal(1, "FAIL: internal 0x%03h resp %0d tmo %0d expected %0d/%0d", addr, i_rsp_resp, i_rsp_timeout,
                       expect_resp, expect_tmo);
        end
    endtask

    // ---------------------------------------------------------------- test
    reg [31:0] v;
    integer    n, aw0, ar0, max_ps_lat, int_done;

    initial begin
        repeat (5) @(posedge clk);
        rst_n = 1'b1;
        repeat (5) @(posedge clk);
        // 1 pass-through
        ps_write(12'h010, 32'h1234_5678, OKAY);
        ps_read(12'h010, OKAY, v);
        if (v !== 32'h1234_5678) $fatal(1, "FAIL: PS read back 0x%08h", v);
        int_req(1'b1, 12'h020, 32'hCAFE_0001, OKAY, 1'b0, v);
        int_req(1'b0, 12'h020, 32'd0, OKAY, 1'b0, v);
        if (v !== 32'hCAFE_0001) $fatal(1, "FAIL: internal read back 0x%08h", v);
        ps_read(12'h020, OKAY, v);
        if (v !== 32'hCAFE_0001) $fatal(1, "FAIL: PS read of the internal write 0x%08h", v);
        // 2 slave error passed through
        ps_write(12'hFFC, 32'h1, SLVERR);
        ps_read(12'hFFC, SLVERR, v);
        int_req(1'b0, 12'hFFC, 32'd0, SLVERR, 1'b0, v);
        // 3 write block
        ps_write_block = 1'b1;
        aw0 = aw_count;
        ps_write(12'h030, 32'hDEAD_BEEF, OKAY);
        @(posedge clk);
        if (aw_count != aw0) $fatal(1, "FAIL: blocked PS write was forwarded");
        if (ev_drop != 1 || dropped_addr !== 12'h030) $fatal(1, "FAIL: drop not reported (%0d, 0x%03h)", ev_drop, dropped_addr);
        if (mem[12'h030 >> 2] !== 32'hA000_000C) $fatal(1, "FAIL: slave register changed by a blocked write");
        ps_read(12'h010, OKAY, v);
        if (v !== 32'h1234_5678) $fatal(1, "FAIL: PS read while blocked 0x%08h", v);
        int_req(1'b1, 12'h030, 32'h0000_0030, OKAY, 1'b0, v);
        if (mem[12'h030 >> 2] !== 32'h0000_0030) $fatal(1, "FAIL: internal write while PS writes are blocked");
        ps_write_block = 1'b0;
        // 4 arbitration: internal saturates, PS latency bounded
        max_ps_lat = 0; int_done = 0;
        fork
            begin : internal_flood
                for (n = 0; n < 40; n = n + 1) begin
                    int_req(1'b1, 12'h300 + 4 * (n % 16), n, OKAY, 1'b0, v);
                    int_done = int_done + 1;
                end
            end
            begin : ps_traffic
                repeat (4) @(posedge clk);
                for (k = 0; k < 6; k = k + 1) begin
                    ps_write(12'h100 + 4 * k, 32'h5000_0000 + k, OKAY);
                    if (ps_lat > max_ps_lat) max_ps_lat = ps_lat;
                    ps_read(12'h100 + 4 * k, OKAY, v);
                    if (ps_lat > max_ps_lat) max_ps_lat = ps_lat;
                    if (v !== 32'h5000_0000 + k) $fatal(1, "FAIL: PS read under load 0x%08h", v);
                end
                if (int_done >= 40) $fatal(1, "FAIL: PS traffic finished only after the internal flood (starved)");
            end
        join
        if (max_ps_lat > 3 * (LAT + 8)) $fatal(1, "FAIL: PS latency %0d cycles under internal load", max_ps_lat);
        // 5 dead slave: no B response
        hold_resp = 1'b1;
        ps_write(12'h040, 32'h4040_4040, SLVERR);
        @(posedge clk);
        if (!hung || ev_timeout != 1) $fatal(1, "FAIL: timeout not reported (hung %0d, events %0d)", hung, ev_timeout);
        ar0 = ar_count; aw0 = aw_count;
        ps_read(12'h010, SLVERR, v);
        int_req(1'b0, 12'h010, 32'd0, SLVERR, 1'b1, v);
        ps_write(12'h044, 32'h1, SLVERR);
        if (ar_count != ar0 || aw_count != aw0) $fatal(1, "FAIL: a request was forwarded while hung");
        hold_resp = 1'b0;                                   // late response: drained, not delivered
        repeat (LAT + 6) @(posedge clk);
        if (hung) $fatal(1, "FAIL: window still hung after the late response");
        ps_read(12'h010, OKAY, v);
        if (v !== 32'h1234_5678) $fatal(1, "FAIL: read after drain 0x%08h", v);
        // 6 slave never accepts AW (internal write)
        block_aw = 1'b1;
        int_req(1'b1, 12'h050, 32'h5050_5050, SLVERR, 1'b1, v);
        @(posedge clk); #1;
        if (!hung || ev_timeout != 2) $fatal(1, "FAIL: AW timeout not reported");
        repeat (20) @(posedge clk);
        if (!hung || m_awvalid !== 1'b1) $fatal(1, "FAIL: AWVALID dropped before the handshake (AXI rule)");
        block_aw = 1'b0;
        repeat (LAT + 10) @(posedge clk);
        if (hung) $fatal(1, "FAIL: window still hung after the late AW handshake");
        int_req(1'b0, 12'h020, 32'd0, OKAY, 1'b0, v);
        if (v !== 32'hCAFE_0001) $fatal(1, "FAIL: internal read after drain 0x%08h", v);
        $display("PASS: tb_s4_axil_window pass-through, SLVERR, write block, arbitration (max PS latency %0d cycles), timeout/hung/drain",
                 max_ps_lat);
        $finish;
    end
endmodule
