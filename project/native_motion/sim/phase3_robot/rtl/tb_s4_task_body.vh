// ============================================================================
// Include : tb_s4_task_body.vh
// Purpose : Body of the S4 integration testbenches.  Each wrapper tb_s4_<name>.v
//           sets SCEN (scenario index in golden/s4/s4_scenarios.mem) and VISA
//           (phase3_s4_task_top VIS_ASYNC) and includes this file - no run-time
//           arguments are needed.
//   DUT: phase3_s4_task_top = S4 windows/regs/FSM/link around the UNCHANGED S2
//   v0.2.3 motion top (unchanged S1 v0.1.1 trajectory + arm backend inside).
//   The testbench acts as PS and as the vision source:
//     S1 bench configuration (RoArm JSON, baud divider 16) -> COMMIT -> DRY_RUN or
//     LINE+ARM with the bench feedback stand-in on arm_uart_rx (below); PS planner move to the
//     start pose; S4 configuration + tables; ENABLE; BACKGROUND then OBJECT_k;
//     scenario triggers (FIST, e-stop, RX break, PS writes, ABORT, mode-B path,
//     PALM at WAIT_PALM, RELEASE at HALT, recovery) keyed to S4 state and to the
//     number of S4 MOVEs, as in s4_scenarios.run_scenario.
//   Checks:
//     * action trace: the S4 link's planner writes (MOVE target/N/Na/profile,
//       PAUSE/RESUME/CLEAR/ESTOP, SOURCE) == reference model trace; each action's
//       code is checked as it happens (a divergence stops the run at once), the
//       targets and samples at the end;
//     * every planner sample accepted by the backend during S4 ownership, per
//       move: bit-exact vs the S2 reference samples (exact), a bit-exact prefix
//       for stopped moves, count N and final pose for moves from an
//       intermediate pose;
//     * final STATUS state, FAULT/refuse code, required EVENT bits, counters;
//     * invariants: after a fault the S4 motion enable is low in the same cycle
//       and at most one pending sample is still accepted; DRY_RUN pins idle;
//       watchdog.
// Prints "PASS:" or stops with "FAIL:".
// ============================================================================

    localparam integer MAX_CYCLES = 6_000_000;       // longest scenario ~1.7M cycles
    localparam [11:0] A_CONTROL = 12'h000, A_MODE = 12'h004, A_STATUS = 12'h008;
    localparam [11:0] P_CONTROL = 12'h000, P_STATUS = 12'h004, P_SOURCE = 12'h018, P_LAST = 12'h200;
    localparam [11:0] R_CONTROL = 12'h000, R_STATUS = 12'h004, R_FAULT = 12'h008, R_EVENT = 12'h00C,
                      R_ABI = 12'h010, R_CMD = 12'h01C, R_PATH_INFO = 12'h05C, R_VISION = 12'h060,
                      R_FIFO = 12'h068, R_CNT = 12'h240;
    localparam [2:0] V_BACKGROUND = 3'd0, V_PALM = 3'd4, V_FIST = 3'd5, V_OTHER = 3'd6;

    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    integer cycle = 0;
    always @(posedge clk) cycle <= cycle + 1;

    reg  [7:0]  traj_awaddr = 0, traj_araddr = 0;
    reg         traj_awvalid = 0, traj_wvalid = 0, traj_bready = 0, traj_arvalid = 0, traj_rready = 0;
    reg  [31:0] traj_wdata = 0;  reg [3:0] traj_wstrb = 0;
    wire        traj_awready, traj_wready, traj_bvalid, traj_arready, traj_rvalid;
    wire [1:0]  traj_bresp, traj_rresp; wire [31:0] traj_rdata;
    reg  [11:0] arm_awaddr = 0, arm_araddr = 0;
    reg         arm_awvalid = 0, arm_wvalid = 0, arm_bready = 0, arm_arvalid = 0, arm_rready = 0;
    reg  [31:0] arm_wdata = 0;   reg [3:0] arm_wstrb = 0;
    wire        arm_awready, arm_wready, arm_bvalid, arm_arready, arm_rvalid;
    wire [1:0]  arm_bresp, arm_rresp; wire [31:0] arm_rdata;
    reg  [11:0] plan_awaddr = 0, plan_araddr = 0;
    reg         plan_awvalid = 0, plan_wvalid = 0, plan_bready = 0, plan_arvalid = 0, plan_rready = 0;
    reg  [31:0] plan_wdata = 0;  reg [3:0] plan_wstrb = 0;
    wire        plan_awready, plan_wready, plan_bvalid, plan_arready, plan_rvalid;
    wire [1:0]  plan_bresp, plan_rresp; wire [31:0] plan_rdata;
    reg  [11:0] s4_awaddr = 0, s4_araddr = 0;
    reg         s4_awvalid = 0, s4_wvalid = 0, s4_bready = 0, s4_arvalid = 0, s4_rready = 0;
    reg  [31:0] s4_wdata = 0;    reg [3:0] s4_wstrb = 0;
    wire        s4_awready, s4_wready, s4_bvalid, s4_arready, s4_rvalid;
    wire [1:0]  s4_bresp, s4_rresp; wire [31:0] s4_rdata;
    wire        irq_traj, irq_arm, irq_plan, irq_s4;
    wire        arm_uart_tx, bus_tx, bus_dir, s4_motion_enable, s4_fault;
    reg         loop_en = 1'b0;
    reg         motion_enable_in = 1'b0;
    reg         fb_rx = 1'b1;
    wire        arm_uart_rx = loop_en ? fb_rx : 1'b1;
    reg         vis_valid = 1'b0, vis_changed = 1'b0, vis_window = 1'b0;
    reg  [2:0]  vis_class = 3'd7;

    phase3_s4_task_top #(.DEBOUNCE_CYCLES(8), .MIN_PERIOD_CYCLES(512), .AXI_TIMEOUT_CYCLES(4096),
                         .VIS_ASYNC(VISA)) dut (
        .s_axi_aclk(clk), .s_axi_aresetn(rst_n),
        .s_axi_traj_awaddr(traj_awaddr), .s_axi_traj_awprot(3'd0), .s_axi_traj_awvalid(traj_awvalid),
        .s_axi_traj_awready(traj_awready), .s_axi_traj_wdata(traj_wdata), .s_axi_traj_wstrb(traj_wstrb),
        .s_axi_traj_wvalid(traj_wvalid), .s_axi_traj_wready(traj_wready), .s_axi_traj_bresp(traj_bresp),
        .s_axi_traj_bvalid(traj_bvalid), .s_axi_traj_bready(traj_bready), .s_axi_traj_araddr(traj_araddr),
        .s_axi_traj_arprot(3'd0), .s_axi_traj_arvalid(traj_arvalid), .s_axi_traj_arready(traj_arready),
        .s_axi_traj_rdata(traj_rdata), .s_axi_traj_rresp(traj_rresp), .s_axi_traj_rvalid(traj_rvalid),
        .s_axi_traj_rready(traj_rready),
        .s_axi_arm_awaddr(arm_awaddr), .s_axi_arm_awprot(3'd0), .s_axi_arm_awvalid(arm_awvalid),
        .s_axi_arm_awready(arm_awready), .s_axi_arm_wdata(arm_wdata), .s_axi_arm_wstrb(arm_wstrb),
        .s_axi_arm_wvalid(arm_wvalid), .s_axi_arm_wready(arm_wready), .s_axi_arm_bresp(arm_bresp),
        .s_axi_arm_bvalid(arm_bvalid), .s_axi_arm_bready(arm_bready), .s_axi_arm_araddr(arm_araddr),
        .s_axi_arm_arprot(3'd0), .s_axi_arm_arvalid(arm_arvalid), .s_axi_arm_arready(arm_arready),
        .s_axi_arm_rdata(arm_rdata), .s_axi_arm_rresp(arm_rresp), .s_axi_arm_rvalid(arm_rvalid),
        .s_axi_arm_rready(arm_rready),
        .s_axi_plan_awaddr(plan_awaddr), .s_axi_plan_awprot(3'd0), .s_axi_plan_awvalid(plan_awvalid),
        .s_axi_plan_awready(plan_awready), .s_axi_plan_wdata(plan_wdata), .s_axi_plan_wstrb(plan_wstrb),
        .s_axi_plan_wvalid(plan_wvalid), .s_axi_plan_wready(plan_wready), .s_axi_plan_bresp(plan_bresp),
        .s_axi_plan_bvalid(plan_bvalid), .s_axi_plan_bready(plan_bready), .s_axi_plan_araddr(plan_araddr),
        .s_axi_plan_arprot(3'd0), .s_axi_plan_arvalid(plan_arvalid), .s_axi_plan_arready(plan_arready),
        .s_axi_plan_rdata(plan_rdata), .s_axi_plan_rresp(plan_rresp), .s_axi_plan_rvalid(plan_rvalid),
        .s_axi_plan_rready(plan_rready),
        .s_axi_s4_awaddr(s4_awaddr), .s_axi_s4_awprot(3'd0), .s_axi_s4_awvalid(s4_awvalid),
        .s_axi_s4_awready(s4_awready), .s_axi_s4_wdata(s4_wdata), .s_axi_s4_wstrb(s4_wstrb),
        .s_axi_s4_wvalid(s4_wvalid), .s_axi_s4_wready(s4_wready), .s_axi_s4_bresp(s4_bresp),
        .s_axi_s4_bvalid(s4_bvalid), .s_axi_s4_bready(s4_bready), .s_axi_s4_araddr(s4_araddr),
        .s_axi_s4_arprot(3'd0), .s_axi_s4_arvalid(s4_arvalid), .s_axi_s4_arready(s4_arready),
        .s_axi_s4_rdata(s4_rdata), .s_axi_s4_rresp(s4_rresp), .s_axi_s4_rvalid(s4_rvalid),
        .s_axi_s4_rready(s4_rready),
        .irq_traj(irq_traj), .irq_arm(irq_arm), .irq_plan(irq_plan), .irq_s4(irq_s4),
        .arm_uart_tx(arm_uart_tx), .arm_uart_rx(arm_uart_rx), .bus_tx(bus_tx), .bus_rx(1'b1), .bus_dir(bus_dir),
        .motion_enable_in(motion_enable_in),
        .vis_valid(vis_valid), .vis_stable_class(vis_class), .vis_class_changed(vis_changed),
        .vis_palm_window_ok(vis_window),
        .s4_motion_enable(s4_motion_enable), .s4_fault(s4_fault));

    `include "tb_s4_axi_tasks.vh"

    // ---------------------------------------------------------------- LINE bench feedback stand-in
    // The S1 bench profile (RoArm JSON, FIXTURE_NOT_OFFICIAL) has no request line, so S1 sends a frame only
    // per motion sample.  A plain TX->RX wire would give feedback only while samples flow and never confirm
    // arrival after the last sample.  Stand-in for an arm that holds its pose and keeps reporting it: every
    // byte S1 transmits is decoded (8N1, 16 clocks/bit) and re-sent on RX (feedback = command, as in the S1
    // bench), and while TX is idle the last complete frame is re-sent every FB_REPLAY_CYCLES.  Bytes are
    // queued, so a replay never collides with a new echo.  loop_en=0 (RX break) stops both and idles RX.
    // No real arm and no protocol knowledge: frames are copied byte for byte.
    localparam integer FB_BAUD = 16, FB_GAP = 40 * FB_BAUD, FB_REPLAY_CYCLES = 30000;
    reg  [7:0] fbq [0:8191];
    reg  [7:0] fb_last [0:1023];
    reg  [7:0] fb_cur  [0:1023];
    integer    fbq_wr = 0, fbq_rd = 0, fb_last_len = 0, fb_cur_len = 0, fb_tx_idle = 0, fb_replay_t = 0;
    integer    dec_cnt = 0, dec_bit = 0, enc_cnt = 0, enc_bit = 0, fbi;
    reg        dec_busy = 1'b0, enc_busy = 1'b0;
    reg  [7:0] dec_sh = 8'd0;
    reg  [9:0] enc_sh = 10'h3FF;
    always @(posedge clk) begin
        // TX decoder
        if (!dec_busy) begin
            if (arm_uart_tx === 1'b0) begin dec_busy = 1'b1; dec_cnt = FB_BAUD + FB_BAUD / 2; dec_bit = 0; end
        end else begin
            dec_cnt = dec_cnt - 1;
            if (dec_cnt == 0) begin
                if (dec_bit < 8) begin
                    dec_sh = {arm_uart_tx, dec_sh[7:1]}; dec_bit = dec_bit + 1; dec_cnt = FB_BAUD;
                end else begin
                    dec_busy = 1'b0;
                    if (arm_uart_tx !== 1'b1) $fatal(1, "FAIL: S1 TX framing error");
                    if (fb_cur_len < 1024) begin fb_cur[fb_cur_len] = dec_sh; fb_cur_len = fb_cur_len + 1; end
                    if (loop_en) begin fbq[fbq_wr % 8192] = dec_sh; fbq_wr = fbq_wr + 1; end
                end
            end
        end
        // frame boundary: TX idle for FB_GAP clocks
        if (dec_busy || arm_uart_tx !== 1'b1) fb_tx_idle = 0;
        else if (fb_tx_idle < FB_GAP) fb_tx_idle = fb_tx_idle + 1;
        if (fb_tx_idle == FB_GAP && fb_cur_len != 0) begin
            for (fbi = 0; fbi < fb_cur_len; fbi = fbi + 1) fb_last[fbi] = fb_cur[fbi];
            fb_last_len = fb_cur_len; fb_cur_len = 0;
        end
        // replay while TX is idle and nothing is queued
        if (fb_tx_idle == FB_GAP && fbq_rd == fbq_wr && !enc_busy && loop_en && fb_last_len != 0) begin
            fb_replay_t = fb_replay_t + 1;
            if (fb_replay_t >= FB_REPLAY_CYCLES) begin
                fb_replay_t = 0;
                for (fbi = 0; fbi < fb_last_len; fbi = fbi + 1) begin fbq[fbq_wr % 8192] = fb_last[fbi]; fbq_wr = fbq_wr + 1; end
            end
        end else if (fb_tx_idle != FB_GAP) begin
            fb_replay_t = 0;
        end
        if (fbq_wr - fbq_rd > 8192) $fatal(1, "FAIL: feedback queue overflow");
        // RX encoder
        if (!loop_en) begin
            fbq_rd = fbq_wr; enc_busy = 1'b0; fb_rx <= 1'b1;
        end else if (!enc_busy) begin
            if (fbq_rd != fbq_wr) begin
                enc_sh = {1'b1, fbq[fbq_rd % 8192], 1'b0}; fbq_rd = fbq_rd + 1;
                enc_busy = 1'b1; enc_bit = 0; enc_cnt = FB_BAUD; fb_rx <= 1'b0;
            end
        end else begin
            enc_cnt = enc_cnt - 1;
            if (enc_cnt == 0) begin
                enc_bit = enc_bit + 1;
                if (enc_bit == 10) begin enc_busy = 1'b0; fb_rx <= 1'b1; end
                else begin fb_rx <= enc_sh[enc_bit]; enc_cnt = FB_BAUD; end
            end
        end
    end

    // ---------------------------------------------------------------- golden
    reg [31:0] g [0:65535];
    integer so, sp_s4, sp_fifo, sp_act, sp_exp, n_act_exp, p_walk;
    integer s1_mode, flags, obj, fist_at, estop_at, rx_at, psw_at, abort_at;
    wire    is_line = flags[0];

    // ---------------------------------------------------------------- action snoop (S4 link -> planner)
    integer     act_n = 0;
    reg [7:0]   act_code [0:127];
    reg [31:0]  act_arg  [0:127];
    reg [191:0] act_tgt  [0:127];
    reg [15:0]  act_nn   [0:127];
    reg [15:0]  act_na   [0:127];
    reg         act_pf   [0:127];
    reg [191:0] cur_tgt;
    reg [15:0]  cur_n, cur_na;
    reg         cur_pf;
    integer     moves_seen = 0;
    wire link_wr=dut.native_valid && dut.native_ready;
    wire [11:0] link_a=(dut.native_code==6)?12'h018:12'h000;
    wire [31:0] link_d=(dut.native_code==6)?{31'd0,dut.op_source}:32'd0;
    always @(posedge clk) begin
        if(link_wr) begin
            if(act_n>=128) $fatal(1,"FAIL: more than 128 S4 actions");
            act_tgt[act_n]<=dut.op_target;act_nn[act_n]<=dut.op_n;
            act_na[act_n]<=dut.op_na;act_pf[act_n]<=dut.op_profile;
            act_arg[act_n]<=link_d;act_code[act_n]<={5'd0,dut.native_code};
            if(dut.native_code==1) moves_seen<=moves_seen+1;
            act_n<=act_n+1;
        end
    end

    // ---------------------------------------------------------------- sample monitor (backend-accepted)
    integer     smp_n = 0;
    reg [191:0] smp     [0:8191];
    integer     smp_mv  [0:8191];
    integer     per_move [0:127];
    integer     k0;
    initial for (k0 = 0; k0 < 128; k0 = k0 + 1) per_move[k0] = 0;
    always @(posedge clk) begin
        if (dut.u_fsm.owner_s4 && dut.u_motion.plan_delivered) begin
            if (smp_n >= 8192) $fatal(1, "FAIL: sample buffer full");
            smp[smp_n] <= dut.u_motion.u_mux.m_data;
            smp_mv[smp_n] <= moves_seen;
            per_move[moves_seen] = per_move[moves_seen] + 1;
            smp_n <= smp_n + 1;
        end
    end

`ifdef TB_S4_TRACE
    // optional debug trace (define TB_S4_TRACE): S4 state changes, actions, heartbeat
    reg [3:0] tr_st = 4'd0;
    integer   tr_act = 0, tr_msn = 0;
    reg [5:0] tr_ms = 6'd0;
    reg       tr_fault = 1'b0;
    integer   tr_polls = 0;
    always @(posedge clk) begin
        if (dut.u_fsm.st != tr_st) begin
            $display("[%0d] S4 state %0d -> %0d (phase %0d, pos %0d, refuse %0d)", cycle, tr_st, dut.u_fsm.st,
                     dut.u_fsm.ph, dut.u_fsm.pos, dut.u_fsm.refuse_code);
            tr_st <= dut.u_fsm.st;
`ifdef TB_S4_TRACE_MS
            $display("    cfg_paths %h", dut.u_regs.cfg_paths);
`endif
        end
        if (dut.u_fsm.fault_latched && !tr_fault)
            $display("[%0d] fault code %0d detail 0x%02h: S1 STATUS 0x%08h ERROR 0x%08h, planner STATUS 0x%08h ERROR 0x%08h",
                     cycle, dut.u_fsm.fault_code, dut.u_fsm.fault_detail, dut.u_link.st_s1_status,
                     dut.u_link.st_s1_error, dut.u_link.st_pl_status, dut.u_link.st_pl_error);
        tr_fault <= dut.u_fsm.fault_latched;
        if (act_n != tr_act) begin
            $display("[%0d] action %0d code %0d arg 0x%0h", cycle, act_n - 1, act_code[act_n - 1], act_arg[act_n - 1]);
            tr_act <= act_n;
        end
`ifdef TB_S4_TRACE_MS
        if (dut.u_fsm.ms != tr_ms && tr_msn < 400) begin
            $display("[%0d] ms %0d -> %0d sc_r %0d sc_i %0d r_count %0d fstep %0d", cycle, tr_ms, dut.u_fsm.ms,
                     dut.u_fsm.sc_r, dut.u_fsm.sc_i, dut.u_fsm.r_count, dut.u_fsm.fstep);
            tr_ms <= dut.u_fsm.ms; tr_msn <= tr_msn + 1;
        end
`endif
`ifdef TB_S4_TRACE_FB
        if (dut.u_fsm.poll_done_pulse && tr_polls < 400) begin
            $display("[%0d] poll: core fb_seq %0d, snap FB_AGE 0x%08h MASKS 0x%08h FRAMES %0d, S1 STATUS 0x%08h, planner 0x%08h/0x%08h",
                     cycle, dut.u_motion.u_arm_backend.core_fb_seq, dut.u_link.st_fb_age, dut.u_link.st_fb_masks,
                     dut.u_link.st_frames, dut.u_link.st_s1_status, dut.u_link.st_pl_status, dut.u_link.st_pl_error);
            tr_polls <= tr_polls + 1;
        end
`endif
        if (cycle % 100000 == 0) $display("[%0d] heartbeat: ms %0d samples %0d", cycle, dut.u_fsm.ms, smp_n);
        $fflush;
    end
`endif

    // ---------------------------------------------------------------- incremental action check
    integer chk_n = 0, chk_p = -1;                 // chk_p: golden record of action chk_n (set after load)
    always @(posedge clk) begin
        if (chk_p >= 0 && act_n > chk_n) begin
            if (chk_n >= n_act_exp)
                $fatal(1, "FAIL: action %0d (code %0d) beyond the %0d actions of the reference model", chk_n,
                       act_code[chk_n], n_act_exp);
            if (act_code[chk_n] != g[chk_p][7:0])
                $fatal(1, "FAIL: action %0d code %0d, reference model %0d", chk_n, act_code[chk_n], g[chk_p]);
            if (act_code[chk_n] == 8'd6 && act_arg[chk_n] != g[chk_p + 1])
                $fatal(1, "FAIL: action %0d SOURCE %0d, reference model %0d", chk_n, act_arg[chk_n], g[chk_p + 1]);
            chk_p = chk_p + 13 + 6 * g[chk_p + 12];
            chk_n = chk_n + 1;
        end
    end

    // ---------------------------------------------------------------- invariants
    integer fault_cycle = -1, samples_at_fault = 0;
    always @(posedge clk) begin
        if (cycle > MAX_CYCLES) $fatal(1, "FAIL: watchdog (scenario %0d)", SCEN);
        if (rst_n && dut.u_fsm.fault_latched && s4_motion_enable)
            $fatal(1, "FAIL: S4 motion enable high while the S4 fault is latched");
        if (rst_n && dut.u_fsm.fault_latched && fault_cycle < 0) begin
            fault_cycle = cycle; samples_at_fault = smp_n;
        end
        if (fault_cycle >= 0 && dut.u_fsm.fault_latched && smp_n > samples_at_fault + 1)
            $fatal(1, "FAIL: %0d samples accepted after the fault (at most the pending one)", smp_n - samples_at_fault);
        if (!dut.u_fsm.fault_latched) fault_cycle = -1;
        if (rst_n && !is_line && s1_mode == 1 && ((arm_uart_tx !== 1'b1) || (bus_tx !== 1'b1) || (bus_dir !== 1'b0)))
            $fatal(1, "FAIL: a physical pin toggled in DRY_RUN");
    end

    // ---------------------------------------------------------------- helpers
    reg [31:0] v;
    integer    i, j, k, n;

    task s4_cmd;                         // one CONTROL bit, expect the given result code
        input integer bitn;
        input integer expect_code;
        reg [31:0] prev, now;
        integer guard;
        begin
            axi_read(3, R_CMD, prev);
            axi_write(3, R_CONTROL, 32'h1 << bitn, RESP_OKAY);
            guard = 0;
            axi_read(3, R_CMD, now);
            while (now[31:16] == prev[31:16] || now[3:0] != bitn[3:0]) begin
                guard = guard + 1;
                if (guard > 2000) $fatal(1, "FAIL: S4 command %0d has no result", bitn);
                repeat (10) @(posedge clk);
                axi_read(3, R_CMD, now);
            end
            if (now[11:8] != expect_code[3:0])
                $fatal(1, "FAIL: S4 command %0d result %0d expected %0d", bitn, now[11:8], expect_code);
        end
    endtask

    task set_vision;
        input [2:0] cls;
        input       window;
        begin
            if (flags[1]) begin
                axi_write(3, R_VISION, {23'd0, 1'b1, 3'd0, window, 1'b1, cls}, RESP_OKAY);
            end else begin
                @(negedge clk);
                vis_valid = 1'b1; vis_class = cls; vis_window = window; vis_changed = 1'b1;
                @(negedge clk);
                vis_changed = 1'b0;
            end
            repeat (40) @(posedge clk);
        end
    endtask

    task planner_move_home;             // PS move of the planner to the scenario start pose
        reg [31:0] last [0:5];
        begin
            axi_read(2, P_STATUS, v);
            for (k = 0; k < 6; k = k + 1) begin
                if (v[7]) axi_read(2, P_LAST + 4 * k, last[k]); else last[k] = 32'd0;
            end
            axi_write(2, 12'h040, g[so + 17], RESP_OKAY);
            axi_write(2, 12'h044, g[so + 18], RESP_OKAY);
            axi_write(2, 12'h048, g[so + 19], RESP_OKAY);
            axi_write(2, 12'h04C, g[so + 15], RESP_OKAY);
            axi_write(2, 12'h050, g[so + 16], RESP_OKAY);
            for (k = 0; k < 6; k = k + 1) begin
                axi_write(2, 12'h100 + 32 * k, last[k], RESP_OKAY);
                axi_write(2, 12'h104 + 32 * k, g[so + 9 + k], RESP_OKAY);
                axi_write(2, 12'h108 + 32 * k, 32'hFFFF_FFFF, RESP_OKAY);
                axi_write(2, 12'h10C + 32 * k, 32'hFFFF_FFFF, RESP_OKAY);
            end
            axi_write(2, P_CONTROL, 32'h1, RESP_OKAY);
            axi_wait(2, P_STATUS, 32'h27, 32'h4, 4_000_000);                 // DONE and no sample pending
        end
    endtask

    task enable_and_select;
        begin
            s4_cmd(0, 0);                                                  // ENABLE
            axi_wait(3, R_STATUS, 32'h8F, 32'h81, 10000);                  // owner, IDLE
            set_vision(V_BACKGROUND, 1'b0);
            set_vision(obj[2:0], 1'b0);
        end
    endtask

    // ---------------------------------------------------------------- scenario
    reg fist_done, estop_done, rx_done, psw_done, abort_done, path_done, palm_done, other_done, released_done,
        recovered, blind_seen;
    integer exp_state, exp_fault, exp_refuse, exp_events, exp_done, exp_cancel, exp_faults, exp_blind, exp_psb;

    initial begin
        $readmemh("sim/phase3_robot/golden/s4/s4_scenarios.mem", g);
        if (g[0] !== 32'h5334_4756) $fatal(1, "FAIL: golden file magic");
        so = g[2 + SCEN];
        if (g[so] !== SCEN) $fatal(1, "FAIL: scenario index %0d at offset %0d", g[so], so);
        s1_mode = g[so + 1]; flags = g[so + 2]; obj = g[so + 3];
        fist_at = g[so + 4]; estop_at = g[so + 5]; rx_at = g[so + 6]; psw_at = g[so + 7]; abort_at = g[so + 8];
        sp_s4 = so + 20;
        sp_fifo = sp_s4 + 1 + 2 * g[sp_s4];
        sp_act = sp_fifo + 1 + g[sp_fifo];
        n_act_exp = g[sp_act];
        p_walk = sp_act + 1;
        for (i = 0; i < n_act_exp; i = i + 1) p_walk = p_walk + 13 + 6 * g[p_walk + 12];
        sp_exp = p_walk;
        chk_p = sp_act + 1;
        exp_state = g[sp_exp]; exp_fault = g[sp_exp + 1]; exp_refuse = g[sp_exp + 2]; exp_events = g[sp_exp + 3];
        exp_done = g[sp_exp + 4]; exp_cancel = g[sp_exp + 5]; exp_faults = g[sp_exp + 6]; exp_blind = g[sp_exp + 7];
        exp_psb = g[sp_exp + 8];
        fist_done = 0; estop_done = 0; rx_done = 0; psw_done = 0; abort_done = 0; path_done = 0; palm_done = 0;
        other_done = 0; released_done = 0; recovered = 0; blind_seen = 0;

        repeat (10) @(posedge clk);
        rst_n = 1'b1;
        repeat (10) @(posedge clk);
        axi_read(3, R_ABI, v);
        if (v !== 32'h0000_3403) $fatal(1, "FAIL: S4 ABI 0x%08h", v);
        axi_read(2, 12'h00C, v);
        if (v !== 32'h0000_3202) $fatal(1, "FAIL: planner ABI 0x%08h through the window", v);
        axi_read(1, 12'h010, v);
        if (v !== 32'h0000_3101) $fatal(1, "FAIL: arm backend ABI 0x%08h through the window", v);
        // ---- S1 backend: bench configuration, COMMIT, mode
        n = g[2 + g[1]];
        for (i = 0; i < n; i = i + 1) axi_write(1, g[3 + g[1] + 2 * i][11:0], g[4 + g[1] + 2 * i], RESP_OKAY);
        axi_write(1, A_CONTROL, 32'h1, RESP_OKAY);
        axi_wait(1, A_STATUS, 32'h3, 32'h1, 100000);                       // config_valid, not busy
        motion_enable_in = 1'b1;
        repeat (100) @(posedge clk);
        if (is_line) begin
            loop_en = 1'b1;
            axi_write(1, A_MODE, 32'h103, RESP_OKAY);                      // LINE + ARM, RoArm
            axi_wait(1, A_STATUS, 32'h24, 32'h24, 200000);                 // permission + feedback_valid
        end else begin
            axi_write(1, A_MODE, 32'h1, RESP_OKAY);                        // DRY_RUN
        end
        // ---- PS: planner to the start pose
        axi_write(2, P_SOURCE, 32'h1, RESP_OKAY);
        planner_move_home;
        // ---- S4 configuration and tables
        n = g[sp_s4];
        for (i = 0; i < n; i = i + 1) axi_write(3, g[sp_s4 + 1 + 2 * i][11:0], g[sp_s4 + 2 + 2 * i], RESP_OKAY);
        axi_read(3, R_EVENT, v);
        if (v[14]) $fatal(1, "FAIL: a configuration write was locked");
        enable_and_select;

        // ---- scenario loop
        while (!(dut.u_fsm.st == exp_state[3:0] && act_n == n_act_exp && dut.u_fsm.ms == 6'd0 && !dut.u_link.op_valid
                 && dut.u_link.state == 3'd0 && (dut.u_regs.event_sticky & exp_events[15:0]) == exp_events[15:0])) begin
            @(posedge clk);
            if (fist_at != 0 && !fist_done && moves_seen == fist_at && per_move[fist_at] >= 1) begin
                fist_done = 1; set_vision(V_FIST, 1'b0);
            end
            if (estop_at != 0 && !estop_done && moves_seen == estop_at && per_move[estop_at] >= 1) begin
                estop_done = 1; motion_enable_in = 1'b0;
            end
            if (rx_at != 0 && !rx_done && moves_seen == rx_at) begin
                rx_done = 1; loop_en = 1'b0;
            end
            if (psw_at != 0 && !psw_done && moves_seen == psw_at && per_move[psw_at] >= 1) begin
                psw_done = 1;
                axi_write(2, P_CONTROL, 32'h8, RESP_OKAY);                 // planner ESTOP: must be dropped
                axi_write(1, A_MODE, 32'h0, RESP_OKAY);                    // S1 MODE=OFF: must be dropped
            end
            if (abort_at != 0 && !abort_done && moves_seen == abort_at && per_move[abort_at] >= 1) begin
                abort_done = 1; s4_cmd(6, 0);                              // ABORT
            end
            if (flags[2] && !path_done && dut.u_fsm.st == 4'd2) begin     // WAIT_PATH: PS commits the path
                path_done = 1;
                for (i = 0; i < g[sp_fifo]; i = i + 1) axi_write(3, R_FIFO, g[sp_fifo + 1 + i], RESP_OKAY);
                axi_write(3, R_PATH_INFO, {16'd0, 14'd0, obj[1:0]}, RESP_OKAY);
                s4_cmd(8, 0);                                              // PATH_COMMIT
            end
            if (dut.u_regs.event_sticky[8]) blind_seen = 1;
            if (dut.u_fsm.st == 4'd5) begin                                // WAIT_PALM
                if (blind_seen && flags[7] && !other_done) begin
                    other_done = 1; set_vision(V_OTHER, 1'b0);
                end else if (flags[3] && !palm_done && !blind_seen) begin
                    palm_done = 1; set_vision(V_PALM, 1'b1);
                end
            end
            if (flags[5] && !released_done && dut.u_fsm.st == 4'd9) begin // HALT: PS takes over
                released_done = 1; s4_cmd(1, 0);                           // RELEASE
            end
            if (flags[4] && !recovered && dut.u_fsm.st == 4'd10 && dut.u_fsm.ms == 6'd0) begin
                recovered = 1;
                s4_cmd(1, 0);                                              // RELEASE
                axi_write(2, P_CONTROL, 32'h10, RESP_OKAY);                // planner CLEAR (ESTOP state)
                axi_write(2, P_SOURCE, 32'h1, RESP_OKAY);
                planner_move_home;
                s4_cmd(7, 0);                                              // FAULT_CLEAR
                palm_done = 0;
                enable_and_select;
            end
        end
        repeat (2000) @(posedge clk);

        // ---- action trace
        if (act_n != n_act_exp) $fatal(1, "FAIL: %0d S4 actions, expected %0d", act_n, n_act_exp);
        p_walk = sp_act + 1;
        j = 0;
        for (i = 0; i < n_act_exp; i = i + 1) begin
            if (act_code[i] != g[p_walk][7:0])
                $fatal(1, "FAIL: action %0d code %0d expected %0d", i, act_code[i], g[p_walk]);
            if (act_code[i] == 8'd6 && act_arg[i] != g[p_walk + 1])
                $fatal(1, "FAIL: action %0d SOURCE %0d expected %0d", i, act_arg[i], g[p_walk + 1]);
            if (act_code[i] == 8'd1) begin
                j = j + 1;
                for (k = 0; k < 6; k = k + 1)
                    if (act_tgt[i][k * 32 +: 32] !== g[p_walk + 3 + k])
                        $fatal(1, "FAIL: move %0d target ch%0d 0x%08h expected 0x%08h", j, k, act_tgt[i][k * 32 +: 32],
                               g[p_walk + 3 + k]);
                if (act_nn[i] != g[p_walk + 9][15:0] || act_na[i] != g[p_walk + 10][15:0] || act_pf[i] != g[p_walk + 11][0])
                    $fatal(1, "FAIL: move %0d N/Na/profile %0d/%0d/%0d", j, act_nn[i], act_na[i], act_pf[i]);
                check_samples(j, p_walk);
            end
            p_walk = p_walk + 13 + 6 * g[p_walk + 12];
        end
        // ---- final registers
        axi_read(3, R_STATUS, v);
        if (v[3:0] != exp_state[3:0]) $fatal(1, "FAIL: final state %0d expected %0d", v[3:0], exp_state);
        axi_read(3, R_FAULT, v);
        if (v[7:0] != exp_fault[7:0] || v[23:16] != exp_refuse[7:0])
            $fatal(1, "FAIL: fault %0d refuse %0d, expected %0d / %0d", v[7:0], v[23:16], exp_fault, exp_refuse);
        axi_read(3, R_EVENT, v);
        if ((v & exp_events) != exp_events) $fatal(1, "FAIL: events 0x%04h lack 0x%04h", v, exp_events);
        axi_read(3, R_CNT + 12'h000, v); if (v != exp_done)   $fatal(1, "FAIL: tasks done %0d expected %0d", v, exp_done);
        axi_read(3, R_CNT + 12'h004, v); if (v != exp_cancel) $fatal(1, "FAIL: cancels %0d expected %0d", v, exp_cancel);
        axi_read(3, R_CNT + 12'h008, v); if (v != exp_faults) $fatal(1, "FAIL: faults %0d expected %0d", v, exp_faults);
        axi_read(3, R_CNT + 12'h010, v); if (v != exp_blind)  $fatal(1, "FAIL: blind timeouts %0d expected %0d", v, exp_blind);
        axi_read(3, R_CNT + 12'h014, v); if (v != exp_psb)    $fatal(1, "FAIL: PS writes blocked %0d expected %0d", v, exp_psb);
        if (exp_fault != 0 && s4_motion_enable) $fatal(1, "FAIL: motion enable after the fault");
        if (exp_fault == 7 || exp_fault == 6) begin                         // LINE faults: S1 saw the revoke
            axi_read(1, A_STATUS, v);
            if (!v[4]) $fatal(1, "FAIL: S1 not faulted after the S4 permission revoke (STATUS 0x%08h)", v);
        end
        $display("PASS: tb_s4 scenario %0d (%0s): %0d actions and %0d backend samples as the reference model, state %0d fault %0d refuse %0d",
                 SCEN, is_line ? "LINE loopback" : "DRY_RUN", act_n, smp_n, exp_state, exp_fault, exp_refuse);
        $finish;
    end

    task check_samples;
        input integer mv;                // 1-based move number
        input integer pa;                // action record
        integer s, c, first, mode, ns;
        begin
            mode = g[pa + 2]; ns = g[pa + 12];
            // samples of move mv
            c = 0; first = -1;
            for (s = 0; s < smp_n; s = s + 1)
                if (smp_mv[s] == mv) begin if (first < 0) first = s; c = c + 1; end
            if (mode == 0 && c != ns) $fatal(1, "FAIL: move %0d: %0d samples, expected %0d", mv, c, ns);
            if (mode == 1 && c > ns) $fatal(1, "FAIL: move %0d (stopped): %0d samples > %0d", mv, c, ns);
            if (mode == 2 && c != g[pa + 9]) $fatal(1, "FAIL: move %0d (from a stop pose): %0d samples, expected N=%0d",
                                                   mv, c, g[pa + 9]);
            for (s = 0; s < c; s = s + 1) begin
                if (mode != 2) begin
                    for (k = 0; k < 6; k = k + 1)
                        if (smp[first + s][k * 32 +: 32] !== g[pa + 13 + 6 * s + k])
                            $fatal(1, "FAIL: move %0d sample %0d ch%0d 0x%08h expected 0x%08h", mv, s, k,
                                   smp[first + s][k * 32 +: 32], g[pa + 13 + 6 * s + k]);
                end else if (s == c - 1) begin
                    for (k = 0; k < 6; k = k + 1)
                        if (smp[first + s][k * 32 +: 32] !== g[pa + 3 + k])
                            $fatal(1, "FAIL: move %0d last sample ch%0d is not the target", mv, k);
                end
            end
        end
    endtask
