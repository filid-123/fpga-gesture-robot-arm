// ============================================================================
// Block Name : arm_feedback_watchdog
// Description: Per-channel feedback age, timeout and arrival detection for the
//              Phase 3 S1 arm backend.  Event-level equivalent of
//              arm_feedback.FeedbackWatchdogModel.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz)
//
// Events (single-cycle pulses; an event arriving while a scan runs is held
// pending and served afterwards, update before tick):
//   tick       : every age saturating-increments (16 bit)
//   fb_update  : channels in fb_mask take their new value, age=0, valid=1,
//                and their arrival counter advances if |fb - cmd| <= tol,
//                else resets; fb_seq increments.
//   cmd_update : a new motion command was sent; all arrival counters reset.
// Values are read channel by channel during the 6-cycle scan through
// scan_ch -> fb_value / cmd_value (the parsers and the command LUTRAM hold
// them for >= 160 cycles), so no 192-bit input buses are needed.
// enable=0 clears ages, validity and arrival (feedback values and fb_seq are
// kept); the age LUTRAM is cleared by a 6-cycle pass before events are
// accepted again.  timeout = enable && (some required age > timeout_ticks),
// registered at the end of every scan (ages only change in scans).
// hold=1 postpones new scans (pending events are kept) so a snapshot copy
// sees one consistent state.
//
// Resources: one 33-bit subtractor, one age incrementer and one comparator
// shared by six channels; ages and values in LUTRAM.
// Timing: every scan takes two cycles per channel.  Cycle 1 registers the
// new age (LUTRAM read + saturating increment or clear) and, in an update
// scan, |fb - cmd| (value read + subtract + absolute value); cycle 2 writes
// the age back and does the compares (tolerance, running max, timeout), so
// no path chains a LUTRAM read with an adder and a magnitude compare.
// A full scan is 12 cycles, far below the 1 ms tick.
//
// Truth boundary: source candidate.  Supplementary Icarus Verilog run only;
// XSim/synthesis/implementation not run.
// ============================================================================

`timescale 1ns / 1ps

module arm_feedback_watchdog (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         enable,
    input  wire         hold,
    input  wire         tick,
    input  wire [15:0]  timeout_ticks,
    input  wire [3:0]   arrival_count,
    input  wire [5:0]   required_mask,
    input  wire [95:0]  tol_dev,
    input  wire         cmd_update,
    input  wire         fb_update,
    input  wire [5:0]   fb_mask,

    output wire [2:0]   scan_ch,
    input  wire [31:0]  fb_value,
    input  wire [31:0]  cmd_value,

    input  wire [2:0]   snap_ch,
    output wire [31:0]  snap_fb_value,

    output wire         busy,
    output wire         scanning,
    output reg  [5:0]   valid_mask,
    output reg  [5:0]   arrival_mask,
    output wire         timeout,
    output reg  [15:0]  age_max,
    output reg  [15:0]  fb_seq
);

    localparam [1:0] ST_IDLE   = 2'd0;
    localparam [1:0] ST_UPDATE = 2'd1;
    localparam [1:0] ST_TICK   = 2'd2;

    (* ram_style = "distributed" *) reg [15:0] age_mem [0:7];
    (* ram_style = "distributed" *) reg [31:0] fb_mem  [0:7];

    reg [1:0]  state;
    reg [2:0]  channel;
    reg [5:0]  upd_mask;
    reg        upd_pending;
    reg        tick_pending;
    reg        cmd_pending;
    reg [5:0]  pending_mask;
    reg [15:0] running_max;
    reg        running_over;
    reg        timeout_r;
    reg [23:0] arr_counts;       // 6 x 4-bit
    reg [2:0]  clear_ch;
    reg        clear_done;
    reg        enable_q;
    reg        diff_phase;       // 0 = register age (and |fb - cmd|), 1 = apply
    reg [32:0] abs_diff_r;
    reg [15:0] age_written_r;

    wire active = enable && clear_done;

    assign scan_ch       = channel;
    assign scanning      = (state != ST_IDLE);
    assign busy          = scanning || upd_pending || tick_pending || cmd_pending || !clear_done;
    assign timeout       = enable && timeout_r;
    assign snap_fb_value = fb_mem[snap_ch];

    // Shared per-channel datapath for the channel under scan.
    wire signed [31:0] sel_fb   = fb_value;
    wire signed [31:0] sel_cmd  = cmd_value;
    wire signed [32:0] diff     = {sel_fb[31], sel_fb} - {sel_cmd[31], sel_cmd};
    wire [32:0]        abs_diff = diff[32] ? (33'd0 - diff) : diff;
    wire               in_tolerance = (abs_diff_r <= {17'd0, tol_dev[channel * 16 +: 16]});
    wire [3:0]         cnt_cur  = arr_counts[channel * 4 +: 4];
    wire [3:0]         cnt_next = in_tolerance ? ((cnt_cur == 4'd15) ? 4'd15 : cnt_cur + 4'd1) : 4'd0;
    wire [15:0]        age_cur  = age_mem[channel];
    wire [15:0]        age_inc  = (age_cur == 16'hffff) ? age_cur : age_cur + 16'd1;
    wire [15:0]        age_written = (state == ST_TICK) ? age_inc :
                                     (upd_mask[channel] ? 16'd0 : age_cur);
    wire               req_ch   = required_mask[channel];
    wire [15:0] max_next  = (req_ch && (age_written_r > running_max)) ? age_written_r : running_max;
    wire        over_next = running_over || (req_ch && (age_written_r > timeout_ticks));
    // A channel step commits in the second (apply) cycle of either scan.
    wire        step_commit = (state != ST_IDLE) && diff_phase;

    // Configuration-time contents (FPGA RAM init; a PL reset does not clear
    // them, so feedback values are meaningful only where valid_mask is set).
    integer init_i;
    initial begin
        for (init_i = 0; init_i < 8; init_i = init_i + 1) begin
            age_mem[init_i] = 16'd0;
            fb_mem[init_i]  = 32'd0;
        end
    end

    // LUTRAM write ports (reset-free).
    always @(posedge clk) begin
        if (!clear_done)
            age_mem[clear_ch] <= 16'd0;
        else if (step_commit)
            age_mem[channel] <= age_written_r;
        if ((state == ST_UPDATE) && !diff_phase && upd_mask[channel])
            fb_mem[channel] <= fb_value;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state        <= ST_IDLE;
            channel      <= 3'd0;
            upd_mask     <= 6'd0;
            upd_pending  <= 1'b0;
            tick_pending <= 1'b0;
            cmd_pending  <= 1'b0;
            pending_mask <= 6'd0;
            running_max  <= 16'd0;
            running_over <= 1'b0;
            timeout_r    <= 1'b0;
            arr_counts   <= 24'd0;
            valid_mask   <= 6'd0;
            arrival_mask <= 6'd0;
            age_max      <= 16'd0;
            fb_seq       <= 16'd0;
            clear_ch     <= 3'd0;
            clear_done   <= 1'b0;
            enable_q     <= 1'b0;
            diff_phase   <= 1'b0;
            abs_diff_r   <= 33'd0;
            age_written_r <= 16'd0;
        end else if (!active) begin
            // Disabled (or still clearing): drop events, clear the age table.
            state        <= ST_IDLE;
            upd_pending  <= 1'b0;
            tick_pending <= 1'b0;
            cmd_pending  <= 1'b0;
            arr_counts   <= 24'd0;
            valid_mask   <= 6'd0;
            arrival_mask <= 6'd0;
            age_max      <= 16'd0;
            timeout_r    <= 1'b0;
            enable_q     <= enable;
            if (enable_q && !enable) begin
                clear_done <= 1'b0;             // start one clear pass
                clear_ch   <= 3'd0;
            end else if (!clear_done) begin
                if (clear_ch == 3'd5) begin
                    clear_ch   <= 3'd0;
                    clear_done <= 1'b1;
                end else begin
                    clear_ch <= clear_ch + 3'd1;
                end
            end
        end else begin
            enable_q <= enable;
            if (fb_update) begin
                upd_pending  <= 1'b1;
                pending_mask <= fb_mask;
            end
            if (tick)
                tick_pending <= 1'b1;
            if (cmd_update)
                cmd_pending <= 1'b1;

            case (state)
                ST_IDLE: begin
                    if (hold) begin
                        // snapshot copy in progress: start nothing
                    end else if (cmd_pending) begin
                        arr_counts   <= 24'd0;
                        arrival_mask <= 6'd0;
                        cmd_pending  <= cmd_update;
                    end else if (upd_pending) begin
                        upd_mask     <= pending_mask;
                        upd_pending  <= fb_update;
                        diff_phase   <= 1'b0;
                        channel      <= 3'd0;
                        running_max  <= 16'd0;
                        running_over <= 1'b0;
                        state        <= ST_UPDATE;
                    end else if (tick_pending) begin
                        tick_pending <= tick;
                        upd_mask     <= 6'd0;
                        diff_phase   <= 1'b0;
                        channel      <= 3'd0;
                        running_max  <= 16'd0;
                        running_over <= 1'b0;
                        state        <= ST_TICK;
                    end
                end

                ST_UPDATE: begin
                    if (!diff_phase) begin
                        abs_diff_r    <= abs_diff;
                        age_written_r <= age_written;
                        diff_phase    <= 1'b1;
                    end else begin
                        diff_phase <= 1'b0;
                        if (upd_mask[channel]) begin
                            valid_mask[channel]          <= 1'b1;
                            arr_counts[channel * 4 +: 4] <= cnt_next;
                            arrival_mask[channel]        <= (cnt_next >= arrival_count);
                        end
                        running_max  <= max_next;
                        running_over <= over_next;
                        if (channel == 3'd5) begin
                            age_max   <= max_next;
                            timeout_r <= over_next;
                            fb_seq    <= fb_seq + 16'd1;
                            state     <= ST_IDLE;
                        end else begin
                            channel <= channel + 3'd1;
                        end
                    end
                end

                ST_TICK: begin
                    if (!diff_phase) begin
                        age_written_r <= age_written;
                        diff_phase    <= 1'b1;
                    end else begin
                        diff_phase   <= 1'b0;
                        running_max  <= max_next;
                        running_over <= over_next;
                        if (channel == 3'd5) begin
                            age_max   <= max_next;
                            timeout_r <= over_next;
                            state     <= ST_IDLE;
                        end else begin
                            channel <= channel + 3'd1;
                        end
                    end
                end

                default: state <= ST_IDLE;
            endcase
        end
    end

endmodule
