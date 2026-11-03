// ============================================================================
// Block Name : planner_p2p_core
// Description: Phase 3 S2 joint-space point-to-point planner (contract
//              planner_p2p_q16_16_v1).  Validates a move, then emits N
//              six-axis Q16.16 samples (linear or trapezoidal velocity) at a
//              fixed period on a ready/valid stream.  Bit-exact reference:
//              ps/robot/planner_p2p_reference.py.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz, same as the S1 trajectory and arm backend).
//
// Shared datapath (the same for RoArm-M3 and SO-ARM101; unit mapping and the
// protocol stay in the unchanged S1 arm backend):
// - ONE scalar path parameter per sample: S(k) advanced incrementally
//   (+2k+1 / +2Na / +2(N-k)-1, or +1 for LINEAR), s_frac = floor(S*2^32/D)
//   by one sequential divider (planner_seq_div).
// - ONE sequential multiplier (planner_seq_mult) time-multiplexed over the six
//   axes: p = start + sign(d) * round(|d| * s_frac / 2^32), and over the
//   START validation products (D, vmax*V*2^16, amax*A; one shared
//   comparator).  No DSP, no BRAM.
// - Per-channel parameters are read one at a time through cfg_ch/cfg_field
//   from the LUTRAM in planner_axi_top; the output sample register m_data is
//   written channel by channel only while no sample is pending.
//   Per sample: ~1 + 34 + 6 x 37 cycles (< MIN_PERIOD_CYCLES).
//
// Stream rules (S1 arm backend contract): once m_valid rises, m_valid and
// m_data stay unchanged until the m_valid && m_ready handshake; a sample is
// never withdrawn (not even by ESTOP, STALL or CLEAR).  The first sample is
// offered one period after RUN is entered, every next one one period after
// the previous offer; if the sink accepts late, the schedule slides (no
// catch-up burst) and late_pulse marks the delayed offer.
//
// Commands (single-cycle pulses; planner_axi_top decides legality and the
// SLVERR response, the core re-checks its own state so a command that races
// with an autonomous transition is ignored): START (IDLE/DONE), PAUSE (RUN:
// no new offers, the pending one may still be accepted), RESUME (PAUSED: next
// offer one period later), ESTOP (any state, fatal until CLEAR), CLEAR
// (PAUSED/DONE/ERROR/ESTOP/IDLE -> IDLE; a paused move is abandoned).
// A pending sample that is not accepted within cfg_stall_timeout cycles
// raises STALL_TIMEOUT (fatal).  Fatal errors stop all further offers.
//
// Truth boundary: source candidate.  Supplementary Icarus Verilog run only;
// XSim/synthesis/implementation/board not run.
// ============================================================================

`timescale 1ns / 1ps

module planner_p2p_core #(
    parameter integer SMOOTH_PROFILE=0,
    parameter integer MIN_PERIOD_CYCLES = 512
) (
    input  wire         clk,
    input  wire         rst_n,

    input  wire         cmd_start,
    input  wire         cmd_pause,
    input  wire         cmd_resume,
    input  wire         cmd_estop,
    input  wire         cmd_clear,

    // Scalar configuration (write-locked by planner_axi_top while busy).
    input  wire [15:0]  cfg_n_samples,
    input  wire [15:0]  cfg_accel_samples,
    input  wire         cfg_profile,          // 0 LINEAR, 1 TRAPEZOID
    input  wire [31:0]  cfg_period_cycles,
    input  wire [31:0]  cfg_stall_timeout,

    // Channel configuration read port (asynchronous LUTRAM in the AXI top).
    output reg  [2:0]   cfg_ch,
    output reg  [1:0]   cfg_field,            // 0 START 1 TARGET 2 VMAX 3 AMAX
    input  wire [31:0]  cfg_data,

    // Continuity reference: last sample accepted by the arm backend (mux).
    input  wire [191:0] last_delivered,
    input  wire         last_valid,

    output reg          m_valid,
    input  wire         m_ready,
    output reg  [191:0] m_data,

    output reg  [2:0]   state,
    output wire         computing,
    output reg  [15:0]  sample_index,         // index of the last offered sample
    output reg          err_pulse,
    output reg  [2:0]   err_code,             // PlannerError 0..5
    output reg  [2:0]   err_channel,
    output reg          done_pulse,
    output reg          late_pulse
);

    localparam [2:0] S_IDLE     = 3'd0;
    localparam [2:0] S_VALIDATE = 3'd1;
    localparam [2:0] S_RUN      = 3'd2;
    localparam [2:0] S_PAUSED   = 3'd3;
    localparam [2:0] S_DONE     = 3'd4;
    localparam [2:0] S_ERROR    = 3'd5;
    localparam [2:0] S_ESTOP    = 3'd6;

    localparam [2:0] E_PARAM    = 3'd0;
    localparam [2:0] E_VELOCITY = 3'd1;
    localparam [2:0] E_ACCEL    = 3'd2;
    localparam [2:0] E_START    = 3'd3;
    localparam [2:0] E_STALL    = 3'd4;
    localparam [2:0] E_ESTOP    = 3'd5;

    localparam [1:0] F_START  = 2'd0;
    localparam [1:0] F_TARGET = 2'd1;
    localparam [1:0] F_VMAX   = 2'd2;
    localparam [1:0] F_AMAX   = 2'd3;

    // Sub-phases (validation and per-sample computation share one register).
    localparam [3:0] P_IDLE     = 4'd0;
    localparam [3:0] V_SCALAR   = 4'd1;
    localparam [3:0] V_DWAIT    = 4'd2;
    localparam [3:0] V_START    = 4'd3;
    localparam [3:0] V_TARGET   = 4'd4;
    localparam [3:0] V_VWAIT    = 4'd5;
    localparam [3:0] V_LIMIT    = 4'd6;     // load VMAX, then AMAX, operand
    localparam [3:0] V_AWAIT    = 4'd7;
    localparam [3:0] C_STEP     = 4'd8;
    localparam [3:0] C_DIV      = 4'd9;
    localparam [3:0] C_START    = 4'd10;
    localparam [3:0] C_TARGET   = 4'd11;
    localparam [3:0] C_MUL      = 4'd12;
    localparam [3:0] C_FINAL    = 4'd13;

    localparam [3:0] C_SMOOTH=4'd14,V_CONST_DIV=4'd15;
    reg[31:0]a_dividend;reg[30:0]a_quotient;reg[2:0]a_remainder;reg[5:0]a_count;
    wire[3:0]a_shift={a_remainder,a_dividend[31]};
    wire a_fits=(a_shift>=4'd6);
    reg[31:0]smooth_u;reg[1:0]smooth_stage;reg signed[36:0]smooth_acc;
    reg  [3:0]   phase;
    reg  [15:0]  k;                  // index of the sample being computed
    reg  [30:0]  s_acc;              // S(k)
    reg  [30:0]  d_const;            // D
    reg  [30:0]  a_const;            // A
    reg  [15:0]  v_const;            // V
    reg  [31:0]  start_r;
    reg  [32:0]  mag_r;              // |target - start|
    reg          neg_r;
    reg          computed;
    reg  [31:0]  timer;
    reg          due_passed;
    reg  [31:0]  stall_cnt;

    reg          mult_start;
    reg  [32:0]  mult_a;
    reg  [31:0]  mult_b;
    wire         mult_busy;
    wire         mult_done;
    wire [64:0]  mult_p;
    wire[36:0]smooth_word={5'd0,mult_p[63:32]};
    wire signed[37:0]smooth_result=$signed(smooth_acc)+$signed({4'd0,mult_p[63:32],2'd0})+$signed({5'd0,mult_p[63:32],1'd0});

    reg          div_start;
    wire         div_busy;
    wire         div_done;
    wire [31:0]  div_q;

    planner_seq_mult u_mult (
        .clk(clk), .rst_n(rst_n), .start(mult_start), .a(mult_a), .b(mult_b),
        .busy(mult_busy), .done(mult_done), .product(mult_p)
    );

    planner_seq_div u_div (
        .clk(clk), .rst_n(rst_n), .start(div_start), .num(s_acc), .den(d_const),
        .busy(div_busy), .done(div_done), .quotient(div_q)
    );

    reg [31:0] s_frac;

    assign computing = (phase >= C_STEP && phase != V_CONST_DIV);

    // ------------------------------------------------------------ helpers
    wire        linear   = (cfg_profile == 1'b0);
    wire [15:0] n_minus_na = cfg_n_samples - cfg_accel_samples;
    wire [16:0] two_na     = {cfg_accel_samples, 1'b0};
    wire        scalars_ok = (cfg_n_samples != 16'd0) &&
                             (cfg_period_cycles >= MIN_PERIOD_CYCLES) &&
                             (cfg_stall_timeout != 32'd0) &&
                             (linear ? (cfg_accel_samples == 16'd0)
                                     : ((cfg_accel_samples != 16'd0) &&
                                        (two_na <= {1'b0, cfg_n_samples})));

    wire [31:0] last_ch = last_delivered[cfg_ch * 32 +: 32];
    wire signed [32:0] delta = $signed({cfg_data[31], cfg_data}) - $signed({start_r[31], start_r});
    wire [32:0] delta_mag = delta[32] ? (33'd0 - delta) : delta;

    // S increment for k -> k+1 (k = index of the last computed sample).
    wire [16:0] k_plus_1 = {1'b0, k} + 17'd1;
    wire [15:0] n_minus_k = cfg_n_samples - k;
    wire [30:0] s_inc = (linear || SMOOTH_PROFILE!=0) ? 31'd1 :
                        (k_plus_1 <= {1'b0, cfg_accel_samples}) ? {14'd0, k, 1'b1} :
                        (k_plus_1 <= {1'b0, n_minus_na})         ? {14'd0, two_na} :
                        {14'd0, {n_minus_k, 1'b0} - 17'd1};

    // p = start + sign(d) * (m + r), m = floor(|d| * s_frac / 2^32), r = rounding
    // bit (round half up on the magnitude).  One adder with carry-in:
    //   start - (m + r) == start + ~m + !r   (mod 2^33, only [31:0] is used).
    wire [32:0] prod_hi   = mult_p[64:32];
    wire        round_bit = mult_p[31];
    wire [32:0] start_ext = {start_r[31], start_r};
    wire [32:0] position  = start_ext + (neg_r ? ~prod_hi : prod_hi) + {32'd0, neg_r ^ round_bit};

    // One comparator for both START limits: the velocity product is formed as
    // vmax * (V * 2^16), so both checks compare |d| * 2^16 with the product.
    wire        over_limit = {16'd0, mag_r, 16'd0} > mult_p;

    // Output word of the sample register (one write port, channel cfg_ch).
    wire [31:0] out_word = (phase == C_FINAL) ? cfg_data : position[31:0];
    wire        out_we   = ((phase == C_MUL) && mult_done) || (phase == C_FINAL);

    task fail;
        input [2:0] code;
        input [2:0] channel;
        begin
            err_pulse   <= 1'b1;
            err_code    <= code;
            err_channel <= channel;
            state       <= S_ERROR;
            phase       <= P_IDLE;
            computed    <= 1'b0;
        end
    endtask

    task begin_compute;
        begin
            phase <= C_STEP;
        end
    endtask

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            a_dividend<=0;a_quotient<=0;a_remainder<=0;a_count<=0;
            smooth_u<=0;smooth_stage<=0;smooth_acc<=0;
            state        <= S_IDLE;
            phase        <= P_IDLE;
            cfg_ch       <= 3'd0;
            cfg_field    <= F_START;
            m_valid      <= 1'b0;
            m_data       <= 192'd0;
            sample_index <= 16'd0;
            err_pulse    <= 1'b0;
            err_code     <= 3'd0;
            err_channel  <= 3'd0;
            done_pulse   <= 1'b0;
            late_pulse   <= 1'b0;
            k            <= 16'd0;
            s_acc        <= 31'd0;
            d_const      <= 31'd1;
            a_const      <= 31'd0;
            v_const      <= 16'd0;
            start_r      <= 32'd0;
            mag_r        <= 33'd0;
            neg_r        <= 1'b0;
            s_frac       <= 32'd0;
            computed     <= 1'b0;
            timer        <= 32'd0;
            due_passed   <= 1'b0;
            stall_cnt    <= 32'd0;
            mult_start   <= 1'b0;
            mult_a       <= 33'd0;
            mult_b       <= 32'd0;
            div_start    <= 1'b0;
        end else begin
            err_pulse  <= 1'b0;
            done_pulse <= 1'b0;
            late_pulse <= 1'b0;
            mult_start <= 1'b0;
            div_start  <= 1'b0;

            // ---------------------------------------------- handshake
            if (m_valid && m_ready) begin
                m_valid   <= 1'b0;
                stall_cnt <= 32'd0;
            end else if (m_valid) begin
                stall_cnt <= stall_cnt + 32'd1;   // judged in RUN/PAUSED below
            end

            if (cmd_estop) begin
                // Highest priority; a pending sample stays offered (never withdrawn).
                state      <= S_ESTOP;
                phase      <= P_IDLE;
                computed   <= 1'b0;
                err_pulse  <= 1'b1;
                err_code   <= E_ESTOP;
                err_channel <= 3'd0;
            end else if (cmd_clear && (state != S_VALIDATE) && (state != S_RUN)) begin
                state    <= S_IDLE;
                phase    <= P_IDLE;
                computed <= 1'b0;
            end else begin
                case (state)
                    S_IDLE, S_DONE: begin
                        if (cmd_start && !m_valid) begin
                            state <= S_VALIDATE;
                            phase <= V_SCALAR;
                        end
                    end

                    S_VALIDATE: begin
                        case (phase)
                            V_SCALAR: begin
                                // Wait until an operation aborted by ESTOP/CLEAR has
                                // drained, so no stale done pulse is taken.
                                if (mult_busy || div_busy) begin
                                    phase <= V_SCALAR;
                                end else if (!scalars_ok) begin
                                    fail(E_PARAM, 3'd0);
                                end else if (linear) begin
                                    d_const   <= {15'd0, cfg_n_samples};
                                    a_const   <= {15'd0, cfg_n_samples};
                                    v_const   <= cfg_n_samples;
                                    cfg_ch    <= 3'd0;
                                    cfg_field <= F_START;
                                    phase     <= V_START;
                                end else if(SMOOTH_PROFILE!=0)begin
                                    // Conservative quintic bounds: peak s'<=2/N,
                                    // peak |s''|<=6/N^2. Na remains a valid ABI field.
                                    v_const<=cfg_n_samples>>1;
                                    mult_a<={17'd0,cfg_n_samples};mult_b<={16'd0,cfg_n_samples};mult_start<=1;phase<=V_DWAIT;
                                end else begin
                                    v_const    <= n_minus_na;
                                    mult_a     <= {17'd0, cfg_accel_samples};
                                    mult_b     <= {16'd0, n_minus_na};
                                    mult_start <= 1'b1;
                                    phase      <= V_DWAIT;
                                end
                            end
                            V_DWAIT: begin
                                if (mult_done) begin
                                    if(SMOOTH_PROFILE!=0)begin
                                        d_const<={15'd0,cfg_n_samples};a_dividend<=mult_p[31:0];
                                        a_quotient<=0;a_remainder<=0;a_count<=32;phase<=V_CONST_DIV;
                                    end else begin
                                        a_const<=mult_p[30:0];d_const<={mult_p[29:0],1'b0};
                                        cfg_ch<=0;cfg_field<=F_START;phase<=V_START;
                                    end
                                end
                            end
                            V_CONST_DIV:begin
                                // Exact N^2/6,32 cycles of four-bit compare/subtract.
                                a_dividend<={a_dividend[30:0],1'b0};
                                a_quotient<={a_quotient[29:0],a_fits};
                                a_remainder<=a_fits?(a_shift-4'd6):a_shift[2:0];
                                a_count<=a_count-1'b1;
                                if(a_count==1)begin
                                    a_const<={a_quotient[29:0],a_fits};cfg_ch<=0;cfg_field<=F_START;phase<=V_START;
                                end
                            end
                            V_START: begin
                                start_r <= cfg_data;
                                if (last_valid && (cfg_data != last_ch)) begin
                                    fail(E_START, cfg_ch);
                                end else begin
                                    cfg_field <= F_TARGET;
                                    phase     <= V_TARGET;
                                end
                            end
                            V_TARGET: begin
                                mag_r     <= delta_mag;
                                cfg_field <= F_VMAX;
                                phase     <= V_LIMIT;      // next cycle: VMAX data valid
                            end
                            V_LIMIT: begin
                                // cfg_data = VMAX on the first visit, AMAX on the second.
                                if (cfg_field == F_VMAX) begin
                                    mult_a     <= {1'b0, cfg_data};
                                    mult_b     <= {v_const, 16'd0};
                                    mult_start <= 1'b1;
                                    phase      <= V_VWAIT;
                                end else begin
                                    mult_a     <= {1'b0, cfg_data};
                                    mult_b     <= {1'b0, a_const};
                                    mult_start <= 1'b1;
                                    phase      <= V_AWAIT;
                                end
                            end
                            V_VWAIT: begin
                                if (mult_done) begin
                                    if (over_limit) begin
                                        fail(E_VELOCITY, cfg_ch);
                                    end else begin
                                        cfg_field <= F_AMAX;
                                        phase     <= V_LIMIT;
                                    end
                                end
                            end
                            V_AWAIT: begin
                                if (mult_done) begin
                                    if (over_limit) begin
                                        fail(E_ACCEL, cfg_ch);
                                    end else if (cfg_ch == 3'd5) begin
                                        // Validated: enter RUN, first offer one period later.
                                        state      <= S_RUN;
                                        k          <= 16'd0;
                                        s_acc      <= 31'd0;
                                        computed   <= 1'b0;
                                        timer      <= cfg_period_cycles - 32'd1;
                                        due_passed <= 1'b0;
                                        stall_cnt  <= 32'd0;
                                        begin_compute;
                                    end else begin
                                        cfg_ch    <= cfg_ch + 3'd1;
                                        cfg_field <= F_START;
                                        phase     <= V_START;
                                    end
                                end
                            end
                            default: phase <= V_SCALAR;
                        endcase
                    end

                    S_RUN, S_PAUSED: begin
                        if (cmd_pause && (state == S_RUN))
                            state <= S_PAUSED;
                        if (cmd_resume && (state == S_PAUSED)) begin
                            state      <= S_RUN;
                            timer      <= cfg_period_cycles - 32'd1;
                            due_passed <= 1'b0;
                        end

                        // ---- offer timing (RUN only; frozen while PAUSED)
                        if ((state == S_RUN) && !cmd_pause) begin
                            if (timer != 32'd0) begin
                                timer <= timer - 32'd1;
                            end else if (computed && !m_valid) begin
                                m_valid      <= 1'b1;
                                sample_index <= k;
                                computed     <= 1'b0;
                                timer        <= cfg_period_cycles - 32'd1;
                                late_pulse   <= due_passed;
                                due_passed   <= 1'b0;
                            end else begin
                                due_passed <= 1'b1;
                            end
                        end

                        // ---- completion / next computation after the handshake
                        if (m_valid && m_ready) begin
                            if (sample_index == cfg_n_samples) begin
                                state      <= S_DONE;
                                phase      <= P_IDLE;
                                done_pulse <= 1'b1;
                            end else if (!computed && (phase == P_IDLE)) begin
                                begin_compute;
                            end
                        end

                        // ---- per-sample computation (writes m_data only while !m_valid)
                        case (phase)
                            C_STEP: begin
                                s_acc <= s_acc + s_inc;
                                k     <= k + 16'd1;
                                if (k_plus_1 == {1'b0, cfg_n_samples}) begin
                                    cfg_ch    <= 3'd0;
                                    cfg_field <= F_TARGET;
                                    phase     <= C_FINAL;
                                end else begin
                                    phase <= C_DIV;
                                end
                            end
                            C_DIV: begin
                                if (!div_busy && !div_done && !div_start)
                                    div_start <= 1'b1;
                                if (div_done) begin
                                    s_frac    <= div_q;
                                    cfg_ch    <= 3'd0;
                                    cfg_field <= F_START;
                                    if(SMOOTH_PROFILE!=0 && !linear)begin
                                        smooth_u<=div_q;smooth_stage<=0;smooth_acc<=0;
                                        mult_a<={1'b0,div_q};mult_b<=div_q;mult_start<=1;phase<=C_SMOOTH;
                                    end else phase<=C_START;
                                end
                            end
                            C_SMOOTH:begin
                                if(mult_done)begin
                                    if(smooth_stage==1)smooth_acc<=$signed((smooth_word<<3)+(smooth_word<<1));
                                    if(smooth_stage==2)smooth_acc<=smooth_acc-$signed((smooth_word<<4)-smooth_word);
                                    if(smooth_stage==3)begin
                                        s_frac<=smooth_result<0 ? 32'd0 : (smooth_result>38'sd4294967295 ? 32'hffffffff : smooth_result[31:0]);
                                        cfg_ch<=0;cfg_field<=F_START;phase<=C_START;
                                    end else begin
                                        mult_a<={1'b0,mult_p[63:32]};mult_b<=smooth_u;mult_start<=1;smooth_stage<=smooth_stage+1'b1;
                                    end
                                end
                            end
                            C_START: begin
                                start_r   <= cfg_data;
                                cfg_field <= F_TARGET;
                                phase     <= C_TARGET;
                            end
                            C_TARGET: begin
                                neg_r      <= delta[32];
                                mult_a     <= delta_mag;
                                mult_b     <= s_frac;
                                mult_start <= 1'b1;
                                phase      <= C_MUL;
                            end
                            C_MUL: begin
                                if (mult_done) begin
                                    if (cfg_ch == 3'd5) begin
                                        computed <= 1'b1;
                                        phase    <= P_IDLE;
                                    end else begin
                                        cfg_ch    <= cfg_ch + 3'd1;
                                        cfg_field <= F_START;
                                        phase     <= C_START;
                                    end
                                end
                            end
                            C_FINAL: begin                            // exact target (out_word)
                                if (cfg_ch == 3'd5) begin
                                    computed <= 1'b1;
                                    phase    <= P_IDLE;
                                end else begin
                                    cfg_ch <= cfg_ch + 3'd1;
                                end
                            end
                            default: ;
                        endcase
                        // sample register: channel cfg_ch <- position (C_MUL) or target (C_FINAL);
                        // one 32-bit write port with a clock enable per channel
                        if (out_we) begin
                            case (cfg_ch)
                                3'd0: m_data[31:0]    <= out_word;
                                3'd1: m_data[63:32]   <= out_word;
                                3'd2: m_data[95:64]   <= out_word;
                                3'd3: m_data[127:96]  <= out_word;
                                3'd4: m_data[159:128] <= out_word;
                                3'd5: m_data[191:160] <= out_word;
                                default: ;
                            endcase
                        end

                        // ---- stall: last so that it wins over PAUSE/RESUME/offer
                        if (m_valid && !m_ready && (stall_cnt + 32'd1 >= cfg_stall_timeout))
                            fail(E_STALL, 3'd0);
                    end

                    default: ;   // S_ERROR, S_ESTOP: only ESTOP/CLEAR (above) leave
                endcase
            end
        end
    end

endmodule
