// ============================================================================
// Block Name : arm_backend_core
// Description: Phase 3 S1 arm backend: consumes the six-channel Q16.16
//              trajectory sample stream and drives either the RoArm-M3 UART
//              (JSON line / binary bridge) or the SO-ARM101 half-duplex
//              servo bus.  Reference model: arm_backend.ArmBackendPlModel.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz, same as the trajectory scheduler and AXI).
//               Asynchronous inputs: arm_uart_rx, bus_rx, motion_enable_in
//               (two-flop synchronizers inside arm_uart_rx / permission gate).
//
// Per motion sample (s_valid held by the scheduler's ready/valid contract):
//   MAP  : arm_joint_unit_mapper (soft limits before direction, 217 cycles)
//   CHECK: arm_frame_formatter check pass (legality + BIN saturation), then
//          the last gate: motion_ok (request frames: !fault) is re-evaluated,
//          so a fault, a dropped ARM or lost permission that arrives during
//          MAP/CHECK cancels the frame before any byte is sent
//   s_ready pulse (sample consumed only now; a cancelled sample is not consumed)
//   TX   : emit CMD frame (half-duplex: lead/lag through the dir controller)
//   REQ  : optional feedback requests (SO-ARM101: reads_per_cycle READs of
//          the round-robin channels, each waiting for its status reply or the
//          response timeout; RoArm: one request line)
// PRIME / idle polling: in MONITOR and LINE, whenever no motion sample is
//   pending and prime_period_cycles have elapsed since the last cycle, a
//   request-only cycle refreshes feedback.  This primes LINE before the first
//   motion frame, keeps feedback fresh while the arm holds between segments
//   (no false feedback timeout) and lets arrival be confirmed after the last
//   sample.  Motion has priority and restarts the poll timer, so polls never
//   interleave with a segment whose sample period is shorter than the poll
//   period.
//
// Modes (latched only between frames): OFF, DRY_RUN (frames are serialized
// but the TX/DIR pins stay idle), MONITOR (requests only), LINE (motion when
// the permission gate allows it).  backend_sel is latched only while OFF.
// Fatal sticky errors (AXI top) raise `fault`; the core then starts no frame.
//
// Protection kept on purpose (no duplicated checks): soft limits, encode
// saturation, template legality, feedback timeout, e-stop/permission,
// protocol checksum.  No frame mirror, no redundant CRC, no voting.
//
// Resource plan: the mapped command values live in one 8 x 32 LUTRAM
// (written by the mapper, read by the formatter, the watchdog and the
// snapshot copy); feedback values are read channel by channel, so no 192-bit
// buses cross this module.  Timers are 20/24 bit (see register map).
//
// Truth boundary: source candidate.  Supplementary Icarus Verilog run only;
// XSim/synthesis/implementation/board not run.
// ============================================================================

`timescale 1ns / 1ps

module arm_backend_core #(
    parameter integer FAST_B = 0,
    parameter integer HAS_ROARM       = 1,
    parameter integer HAS_SO101       = 1,
    parameter integer DEBOUNCE_CYCLES = 1_000_000,
    parameter integer ROARM_FEEDBACK_EVERY = 1
) (
    input wire b_context,b_grip,
    input wire [15:0] b_speed,
    input wire [7:0] b_acc,
    input  wire         clk,
    input  wire         rst_n,

    input  wire [1:0]   mode_req,
    input  wire         backend_sel,
    input  wire         arm,
    input  wire         config_valid,
    input  wire         fault,
    input  wire         commit_start,
    output reg          commit_done,
    output reg          commit_ok,

    input  wire [15:0]  baud_div_roarm,
    input  wire [15:0]  baud_div_bus,
    input  wire [15:0]  hd_lead_cycles,
    input  wire [15:0]  hd_lag_cycles,
    input  wire [23:0]  resp_timeout_cycles,
    input  wire [19:0]  wd_prescale,
    input  wire [23:0]  prime_period_cycles,
    input  wire [15:0]  fb_timeout_ticks,
    input  wire [3:0]   arrival_count,
    input  wire [5:0]   required_mask,
    input  wire [7:0]   cmd_base,
    input  wire [7:0]   req_base,
    input  wire         req_enable,
    input  wire [2:0]   reads_per_cycle,
    input  wire [5:0]   dir_neg,
    input  wire [47:0]  device_ids,
    input  wire [95:0]  tol_dev,
    input  wire [2:0]   json_frac_digits,
    input  wire [7:0]   json_line_term,
    input  wire [15:0]  json_max_line_len,
    input  wire [27:0]  json_key_len,
    input  wire [31:0]  json_disc_value,
    input  wire [7:0]   sts_hdr0,
    input  wire [7:0]   sts_hdr1,
    input  wire [2:0]   sts_read_len,
    input  wire [1:0]   sts_encoding,
    input  wire         sts_big_endian,
    input  wire         sts_ck_invert,
    input  wire [7:0]   seq_byte,

    output wire [2:0]   map_cfg_ch,
    input  wire [31:0]  map_soft_min,
    input  wire [31:0]  map_soft_max,
    input  wire [31:0]  map_zero,
    input  wire [31:0]  map_scale,

    input  wire         tpl_we,
    input  wire [7:0]   tpl_waddr,
    input  wire [15:0]  tpl_wdata,
    input  wire         key_we,
    input  wire [6:0]   key_waddr,
    input  wire [7:0]   key_wdata,

    input  wire         s_valid,
    output reg          s_ready,
    input  wire [191:0] s_data,

    output reg          arm_uart_tx,
    input  wire         arm_uart_rx,
    output reg          bus_tx,
    input  wire         bus_rx,
    output reg          bus_dir,
    input  wire         motion_enable_in,

    output wire         engine_busy,
    output wire [3:0]   core_state,
    output wire [1:0]   active_mode,
    output wire         active_backend,
    output wire         permission,
    output wire         estop_ok,
    output wire         feedback_all_valid,

    output reg  [14:0]  err_pulse,
    output reg  [5:0]   limit_mask_evt,
    output reg          evt_frame_tx,
    output reg          evt_fb_ok,
    output reg          evt_fb_err,
    output reg          evt_resp_timeout,
    output reg          evt_line_ignored,
    output reg          evt_frame_done,
    output reg  [23:0]  frame_cycles,

    // Snapshot support: channel-addressed reads and a hold while copying.
    input  wire         snap_hold,
    input  wire [2:0]   snap_ch,
    output wire [31:0]  snap_fb_value,
    output wire [31:0]  snap_cmd_value,
    output wire         snap_quiet,
    output wire [5:0]   fb_valid,
    output wire [5:0]   fb_arrival,
    output reg  [5:0]   servo_fault_mask,
    output wire [15:0]  fb_age_max,
    output wire [15:0]  fb_seq,
    output reg  [7:0]   last_servo_err,
    output reg  [7:0]   last_servo_err_id
);

    localparam [1:0] MODE_OFF     = 2'd0;
    localparam [1:0] MODE_DRY_RUN = 2'd1;
    localparam [1:0] MODE_MONITOR = 2'd2;
    localparam [1:0] MODE_LINE    = 2'd3;

    // ERROR_STATUS bit numbers (arm_feedback.ArmError).
    localparam integer E_LIMIT        = 0;
    localparam integer E_SATURATION   = 1;
    localparam integer E_TEMPLATE     = 2;
    localparam integer E_UART_FRAMING = 6;
    localparam integer E_RX_OVERRUN   = 7;
    localparam integer E_RX_CHECKSUM  = 8;
    localparam integer E_RX_PROTOCOL  = 9;
    localparam integer E_RESP_TIMEOUT = 10;
    localparam integer E_FB_TIMEOUT   = 11;
    localparam integer E_ESTOP        = 12;
    localparam integer E_SERVO_FAULT  = 13;

    localparam [3:0] C_IDLE      = 4'd0;
    localparam [3:0] C_COMMIT    = 4'd1;
    localparam [3:0] C_MAP       = 4'd2;
    localparam [3:0] C_CHECK     = 4'd3;
    localparam [3:0] C_TX        = 4'd4;
    localparam [3:0] C_WAIT_RESP = 4'd5;
    localparam [3:0] C_FINISH    = 4'd6;

    reg [3:0]  state;
    reg [1:0]  active_mode_r;
    reg        backend_r;
    reg [1:0]  sub_phase;
    reg        frame_is_req;
    reg        motion_cycle;
    reg        fmt_started;
    reg [2:0]  rr_ch;
    // Motion queries are decimated; PRIME/idle queries and watchdogs remain.
    localparam integer ROARM_DIV_WIDTH = (ROARM_FEEDBACK_EVERY > 1) ? $clog2(ROARM_FEEDBACK_EVERY) : 1;
    reg [ROARM_DIV_WIDTH-1:0] roarm_query_phase;
    reg [2:0]  req_left;
    reg [23:0] cycle_count;
    reg [23:0] resp_counter;
    reg [23:0] pace_counter;
    reg [19:0] prescale_counter;
    reg        wd_tick;
    reg        mapper_start;
    reg        fmt_start;
    reg        fmt_check;
    reg        tx_req;
    reg        cmd_update;
    reg        sts_flush;

    wire use_bus      = (backend_r == 1'b1);
    wire pins_enabled = (active_mode_r == MODE_MONITOR) || (active_mode_r == MODE_LINE);
    wire line_mode    = (active_mode_r == MODE_LINE);
    wire req_active   = req_enable && (!use_bus || (required_mask != 6'd0));
    wire [2:0] req_count = (!use_bus || (reads_per_cycle == 3'd0)) ? 3'd1 : reads_per_cycle;

    assign core_state     = state;
    assign active_mode    = active_mode_r;
    assign active_backend = backend_r;

    // ------------------------------------------------------------ mapper
    wire         mapper_busy;
    wire         mapper_done;
    wire         mapper_we;
    wire [2:0]   mapper_wch;
    wire [31:0]  mapper_wdata;
    wire [5:0]   mapper_limit;
    wire [5:0]   mapper_sat;

    arm_joint_unit_mapper u_mapper (
        .clk(clk),
        .rst_n(rst_n),
        .start(mapper_start),
        .joints_q16(s_data),
        .cfg_ch(map_cfg_ch),
        .ch_soft_min_q16(map_soft_min),
        .ch_soft_max_q16(map_soft_max),
        .ch_zero_dev(map_zero),
        .ch_scale_uq16_16(map_scale),
        .dir_neg(dir_neg),
        .busy(mapper_busy),
        .done(mapper_done),
        .dev_we(mapper_we),
        .dev_ch(mapper_wch),
        .dev_data(mapper_wdata),
        .limit_mask(mapper_limit),
        .sat_mask(mapper_sat)
    );

    // Command LUTRAM: the mapped values are also the "last command" (arrival
    // reference and snapshot); the watchdog resets arrival on every
    // cmd_update.  Initial contents are the FPGA RAM init values.
    reg frame_b,frame_grip;
    reg [15:0] frame_speed;
    reg [7:0] frame_acc;
    (* ram_style = "distributed" *) reg [31:0] cmd_mem [0:7];
    integer init_i;
    initial begin
        for (init_i = 0; init_i < 8; init_i = init_i + 1)
            cmd_mem[init_i] = 32'd0;
    end
    always @(posedge clk) begin
        if (mapper_we)
            cmd_mem[mapper_wch] <= mapper_wdata;
        else if(FAST_B!=0&&state==C_MAP)begin
            cmd_mem[6]<={16'd0,frame_speed};cmd_mem[7]<={24'd0,frame_acc};
        end
    end

    wire [2:0] fmt_val_ch;
    wire [2:0] wd_scan_ch;
    assign snap_cmd_value = cmd_mem[snap_ch];

    // --------------------------------------------------------- formatter
    wire        fmt_busy;
    wire        fmt_done;
    wire        fmt_error;
    wire        fmt_saturated;
    wire [7:0]  fmt_byte;
    wire        fmt_valid;
    wire        fmt_ready;

    arm_frame_formatter #(.EXTRA_SCALARS(FAST_B)) u_formatter (
        .clk(clk),
        .rst_n(rst_n),
        .tpl_we(tpl_we),
        .tpl_waddr(tpl_waddr),
        .tpl_wdata(tpl_wdata),
        .start(fmt_start),
        .check_only(fmt_check),
        .base_addr(frame_is_req ? req_base : ((FAST_B!=0&&frame_b)?(frame_grip?8'd208:8'd112):cmd_base)),
        .val_ch(fmt_val_ch),
        .val_data(cmd_mem[fmt_val_ch]),
        .device_ids(device_ids),
        .rr_channel(rr_ch),
        .seq_byte(seq_byte),
        .busy(fmt_busy),
        .done(fmt_done),
        .error(fmt_error),
        .saturated(fmt_saturated),
        .out_byte(fmt_byte),
        .out_valid(fmt_valid),
        .out_ready(fmt_ready)
    );

    // ---------------------------------------------------- UART + direction
    wire [15:0] baud_div = use_bus ? baud_div_bus : baud_div_roarm;
    wire        tx_grant;
    wire        uart_ready;
    wire        uart_busy;
    wire        uart_line;
    wire        hd_dir;
    wire        hd_rx_enable;
    wire        hd_released;

    assign fmt_ready = uart_ready && tx_grant;

    arm_uart_tx u_uart_tx (
        .clk(clk),
        .rst_n(rst_n),
        .clks_per_bit(baud_div),
        .byte_valid(fmt_valid && tx_grant),
        .byte_ready(uart_ready),
        .byte_data(fmt_byte),
        .tx(uart_line),
        .busy(uart_busy)
    );

    arm_half_duplex_dir_ctrl u_dir (
        .clk(clk),
        .rst_n(rst_n),
        .half_duplex(use_bus),
        .lead_cycles(hd_lead_cycles),
        .lag_cycles(hd_lag_cycles),
        .tx_req(tx_req),
        .tx_line_idle(!uart_busy && !fmt_valid),
        .tx_grant(tx_grant),
        .dir_tx(hd_dir),
        .rx_enable(hd_rx_enable),
        .released(hd_released)
    );

    wire       rx_valid;
    wire [7:0] rx_byte;
    wire       rx_framing_error;

    // The select only changes while MODE_OFF, so this mux in front of the
    // receiver's synchronizer never switches during a frame.
    arm_uart_rx u_uart_rx (
        .clk(clk),
        .rst_n(rst_n),
        .clks_per_bit(baud_div),
        .enable(pins_enabled && hd_rx_enable),
        .rx_async(use_bus ? bus_rx : arm_uart_rx),
        .byte_valid(rx_valid),
        .byte_data(rx_byte),
        .framing_error(rx_framing_error)
    );

    // Registered pins: DRY_RUN and OFF keep TX idle-high and the driver off.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            arm_uart_tx <= 1'b1;
            bus_tx      <= 1'b1;
            bus_dir     <= 1'b0;
        end else begin
            arm_uart_tx <= (!use_bus && pins_enabled) ? uart_line : 1'b1;
            bus_tx      <= (use_bus && pins_enabled) ? uart_line : 1'b1;
            bus_dir     <= (use_bus && pins_enabled) ? hd_dir : 1'b0;
        end
    end

    // ------------------------------------------------------------ parsers
    wire         json_rec_valid;
    wire [31:0]  json_rd_value;
    wire [5:0]   json_rec_mask;
    wire         json_ignored;
    wire         json_err;
    wire         json_overrun;

    generate
        if (HAS_ROARM != 0) begin : g_roarm
            arm_json_feedback_parser u_json (
                .clk(clk),
                .rst_n(rst_n),
                .key_we(key_we),
                .key_waddr(key_waddr),
                .key_wdata(key_wdata),
                .key_len_cfg(json_key_len),
                .frac_digits(json_frac_digits),
                .line_term(json_line_term),
                .max_line_len(json_max_line_len),
                .disc_value(json_disc_value),
                .byte_valid(rx_valid && !use_bus),
                .byte_data(rx_byte),
                .rec_valid(json_rec_valid),
                .rec_mask(json_rec_mask),
                .rd_ch(wd_scan_ch),
                .rd_value(json_rd_value),
                .line_ignored(json_ignored),
                .err_parse(json_err),
                .err_overrun(json_overrun)
            );
        end else begin : g_no_roarm
            assign json_rec_valid = 1'b0;
            assign json_rd_value  = 32'd0;
            assign json_rec_mask  = 6'd0;
            assign json_ignored   = 1'b0;
            assign json_err       = 1'b0;
            assign json_overrun   = 1'b0;
        end
    endgenerate

    wire               sts_pkt_valid;
    wire [7:0]         sts_pkt_id;
    wire [7:0]         sts_pkt_err;
    wire signed [31:0] sts_pkt_value;
    wire               sts_err_checksum;
    wire               sts_err_protocol;

    generate
        if (HAS_SO101 != 0) begin : g_so101
            arm_so101_status_parser u_sts (
                .clk(clk),
                .rst_n(rst_n),
                .flush(sts_flush),
                .byte_valid(rx_valid && use_bus),
                .byte_data(rx_byte),
                .hdr0(sts_hdr0),
                .hdr1(sts_hdr1),
                .expected_id(device_ids[rr_ch * 8 +: 8]),
                .expected_nparams(sts_read_len),
                .pos_encoding(sts_encoding),
                .big_endian(sts_big_endian),
                .ck_invert(sts_ck_invert),
                .pkt_valid(sts_pkt_valid),
                .pkt_id(sts_pkt_id),
                .pkt_err(sts_pkt_err),
                .pkt_value(sts_pkt_value),
                .err_checksum(sts_err_checksum),
                .err_protocol(sts_err_protocol)
            );
        end else begin : g_no_so101
            assign sts_pkt_valid    = 1'b0;
            assign sts_pkt_id       = 8'd0;
            assign sts_pkt_err      = 8'd0;
            assign sts_pkt_value    = 32'sd0;
            assign sts_err_checksum = 1'b0;
            assign sts_err_protocol = 1'b0;
        end
    endgenerate

    wire sts_accept = (state == C_WAIT_RESP) && sts_pkt_valid;

    // ----------------------------------------------------------- watchdog
    wire        wd_enable = pins_enabled && config_valid;
    wire        wd_busy;
    wire        wd_scanning;
    wire        wd_timeout;
    wire        fb_update = use_bus ? sts_accept : json_rec_valid;
    wire [5:0]  fb_mask   = use_bus ? (6'd1 << rr_ch) : json_rec_mask;
    wire [31:0] fb_value  = use_bus ? sts_pkt_value : json_rd_value;

    // A snapshot copy may start only when neither the mapper nor a
    // watchdog scan is changing the values being copied.
    assign snap_quiet = !mapper_busy && !mapper_we && !wd_scanning;

    arm_feedback_watchdog u_watchdog (
        .clk(clk),
        .rst_n(rst_n),
        .enable(wd_enable),
        .hold(snap_hold),
        .tick(wd_tick),
        .timeout_ticks(fb_timeout_ticks),
        .arrival_count(arrival_count),
        .required_mask(required_mask),
        .tol_dev(tol_dev),
        .cmd_update(cmd_update),
        .fb_update(fb_update),
        .fb_mask(fb_mask),
        .scan_ch(wd_scan_ch),
        .fb_value(fb_value),
        .cmd_value(cmd_mem[wd_scan_ch]),
        .snap_ch(snap_ch),
        .snap_fb_value(snap_fb_value),
        .busy(wd_busy),
        .scanning(wd_scanning),
        .valid_mask(fb_valid),
        .arrival_mask(fb_arrival),
        .timeout(wd_timeout),
        .age_max(fb_age_max),
        .fb_seq(fb_seq)
    );

    wire primed = ((fb_valid & required_mask) == required_mask);
    assign feedback_all_valid = primed;

    // ------------------------------------------------------ permission gate
    wire estop_event;

    arm_motion_permission_gate #(
        .DEBOUNCE_CYCLES(DEBOUNCE_CYCLES)
    ) u_gate (
        .clk(clk),
        .rst_n(rst_n),
        .motion_enable_async(motion_enable_in),
        .line_mode(line_mode),
        .arm(arm),
        .config_valid(config_valid),
        .fault(fault),
        .estop_ok(estop_ok),
        .permission(permission),
        .estop_event(estop_event)
    );

    assign engine_busy = (state != C_IDLE) || uart_busy || !hd_released;

    // Round-robin over required channels (same rule as arm_backend.next_required):
    // the smallest required channel above rr_ch, else the smallest required one.
    reg [2:0] rr_first;
    reg [2:0] rr_up;
    reg       rr_up_found;
    integer   k;
    always @(*) begin
        rr_first    = 3'd0;
        rr_up       = 3'd0;
        rr_up_found = 1'b0;
        for (k = 5; k >= 0; k = k - 1) begin
            if (required_mask[k])
                rr_first = k[2:0];
            if (required_mask[k] && (k > rr_ch)) begin
                rr_up       = k[2:0];
                rr_up_found = 1'b1;
            end
        end
    end
    wire [2:0] rr_next = rr_up_found ? rr_up :
                         ((required_mask != 6'd0) ? rr_first : rr_ch);

    wire motion_ok = config_valid && !fault &&
                     ((active_mode_r == MODE_DRY_RUN) || (line_mode && permission && primed));
    wire req_only_ok = config_valid && !fault && req_active && (pace_counter == 24'd0) &&
                       pins_enabled;

    // End of one request transaction: advance the round robin, then either
    // issue the next request of this cycle or leave the cycle.  A fatal error
    // ends the cycle at once: no new frame of any kind after `fault`.
    task finish_request;
        begin
            rr_ch <= rr_next;
            if ((req_left > 3'd1) && !fault) begin
                req_left     <= req_left - 3'd1;
                frame_is_req <= 1'b1;
                fmt_check    <= 1'b1;
                fmt_start    <= 1'b1;
                state        <= C_CHECK;
            end else if (motion_cycle) begin
                state <= C_FINISH;
            end else begin
                pace_counter <= prime_period_cycles;
                state        <= C_IDLE;
            end
        end
    endtask

    // ---------------------------------------------------------- sequencer
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state             <= C_IDLE;
            active_mode_r     <= MODE_OFF;
            backend_r         <= 1'b0;
            sub_phase         <= 2'd0;
            frame_is_req      <= 1'b0;
            motion_cycle      <= 1'b0;
            fmt_started       <= 1'b0;
            rr_ch             <= 3'd0;
            roarm_query_phase <= 0;
            req_left          <= 3'd0;
            cycle_count       <= 24'd0;
            resp_counter      <= 24'd0;
            pace_counter      <= 24'd0;
            prescale_counter  <= 20'd0;
            wd_tick           <= 1'b0;
            frame_b<=0;frame_grip<=0;frame_speed<=0;frame_acc<=0;
            mapper_start      <= 1'b0;
            fmt_start         <= 1'b0;
            fmt_check         <= 1'b0;
            tx_req            <= 1'b0;
            cmd_update        <= 1'b0;
            sts_flush         <= 1'b0;
            s_ready           <= 1'b0;
            commit_done       <= 1'b0;
            commit_ok         <= 1'b0;
            err_pulse         <= 15'd0;
            limit_mask_evt    <= 6'd0;
            evt_frame_tx      <= 1'b0;
            evt_fb_ok         <= 1'b0;
            evt_fb_err        <= 1'b0;
            evt_resp_timeout  <= 1'b0;
            evt_line_ignored  <= 1'b0;
            evt_frame_done    <= 1'b0;
            frame_cycles      <= 24'd0;
            servo_fault_mask  <= 6'd0;
            last_servo_err    <= 8'd0;
            last_servo_err_id <= 8'd0;
        end else begin
            mapper_start     <= 1'b0;
            fmt_start        <= 1'b0;
            cmd_update       <= 1'b0;
            sts_flush        <= 1'b0;
            s_ready          <= 1'b0;
            commit_done      <= 1'b0;
            err_pulse        <= 15'd0;
            evt_frame_tx     <= 1'b0;
            evt_fb_ok        <= 1'b0;
            evt_fb_err       <= 1'b0;
            evt_resp_timeout <= 1'b0;
            evt_line_ignored <= 1'b0;
            evt_frame_done   <= 1'b0;
            wd_tick          <= 1'b0;

            // Watchdog time base (1 tick per wd_prescale cycles while enabled).
            if (!wd_enable) begin
                prescale_counter <= 20'd0;
            end else if (prescale_counter == 20'd0) begin
                prescale_counter <= (wd_prescale == 20'd0) ? 20'd0 : (wd_prescale - 20'd1);
                wd_tick          <= 1'b1;
            end else begin
                prescale_counter <= prescale_counter - 20'd1;
            end

            if (pace_counter != 24'd0)
                pace_counter <= pace_counter - 24'd1;
            if ((state != C_IDLE) && (cycle_count != 24'hff_ffff))
                cycle_count <= cycle_count + 24'd1;      // saturating

            // Always-on event capture from the receive side.
            if (rx_framing_error)            err_pulse[E_UART_FRAMING] <= 1'b1;
            if (json_err)                  begin err_pulse[E_RX_PROTOCOL] <= 1'b1; evt_fb_err <= 1'b1; end
            if (json_overrun)              begin err_pulse[E_RX_OVERRUN]  <= 1'b1; evt_fb_err <= 1'b1; end
            if (json_ignored)                evt_line_ignored <= 1'b1;
            if (json_rec_valid && !use_bus)  evt_fb_ok <= 1'b1;
            if (sts_err_checksum)          begin err_pulse[E_RX_CHECKSUM] <= 1'b1; evt_fb_err <= 1'b1; end
            if (sts_err_protocol)          begin err_pulse[E_RX_PROTOCOL] <= 1'b1; evt_fb_err <= 1'b1; end
            if (wd_timeout)                  err_pulse[E_FB_TIMEOUT] <= 1'b1;
            if (estop_event)                 err_pulse[E_ESTOP] <= 1'b1;
            if (!pins_enabled)               servo_fault_mask <= 6'd0;

            case (state)
                C_IDLE: begin
                    active_mode_r <= mode_req;
                    sub_phase     <= 2'd0;
                    fmt_started   <= 1'b0;
                    if (active_mode_r == MODE_OFF) begin
                        rr_ch        <= rr_first;
                        pace_counter <= 24'd0;
                        if (mode_req == MODE_OFF)
                            backend_r <= backend_sel;
                        if (commit_start) begin
                            frame_is_req <= 1'b0;
                            fmt_check    <= 1'b1;
                            fmt_start    <= 1'b1;
                            state        <= C_COMMIT;
                        end
                    end else if (motion_ok && s_valid && !snap_hold) begin
                        cycle_count  <= 24'd0;
                        frame_b<=FAST_B!=0&&b_context;frame_grip<=b_grip;frame_speed<=b_speed;frame_acc<=b_acc;
                        motion_cycle <= 1'b1;
                        frame_is_req <= 1'b0;
                        mapper_start <= 1'b1;
                        state        <= C_MAP;
                    end else if (req_only_ok) begin
                        cycle_count  <= 24'd0;
                        motion_cycle <= 1'b0;
                        req_left     <= req_count;
                        frame_is_req <= 1'b1;
                        fmt_check    <= 1'b1;
                        fmt_start    <= 1'b1;
                        state        <= C_CHECK;
                    end
                end

                C_COMMIT: begin
                    // sub_phase 0: command program, 1: request program.
                    if (fmt_done) begin
                        if (fmt_error) begin
                            commit_ok   <= 1'b0;
                            commit_done <= 1'b1;
                            state       <= C_IDLE;
                        end else if ((sub_phase == 2'd0) && req_enable) begin
                            sub_phase    <= 2'd1;
                            frame_is_req <= 1'b1;
                            fmt_check    <= 1'b1;
                            fmt_start    <= 1'b1;
                        end else begin
                            commit_ok    <= 1'b1;
                            commit_done  <= 1'b1;
                            frame_is_req <= 1'b0;
                            state        <= C_IDLE;
                        end
                    end
                end

                C_MAP: begin
                    if (mapper_done) begin
                        if (mapper_limit != 6'd0) begin
                            err_pulse[E_LIMIT] <= 1'b1;
                            limit_mask_evt     <= mapper_limit;
                            state              <= C_IDLE;
                        end else if (mapper_sat != 6'd0) begin
                            err_pulse[E_SATURATION] <= 1'b1;
                            state                   <= C_IDLE;
                        end else begin
                            fmt_check <= 1'b1;
                            fmt_start <= 1'b1;
                            state     <= C_CHECK;
                        end
                    end
                end

                C_CHECK: begin
                    if (fmt_done) begin
                        if (fmt_error) begin
                            err_pulse[E_TEMPLATE] <= 1'b1;
                            state                 <= C_IDLE;
                        end else if (fmt_saturated) begin
                            err_pulse[E_SATURATION] <= 1'b1;
                            state                   <= C_IDLE;
                        end else if (frame_is_req ? fault : !motion_ok) begin
                            // Last gate before any byte leaves: a fatal error,
                            // a dropped ARM or lost permission raised during
                            // MAP/CHECK cancels this frame (sample not consumed).
                            state <= C_IDLE;
                        end else begin
                            if (!frame_is_req)
                                s_ready <= 1'b1;       // consume the sample now
                            fmt_check <= 1'b0;
                            sub_phase <= 2'd0;
                            state     <= C_TX;
                        end
                    end
                end

                C_TX: begin
                    case (sub_phase)
                        2'd0: begin
                            tx_req <= 1'b1;
                            if (tx_grant && tx_req && !fmt_started) begin
                                fmt_start   <= 1'b1;
                                fmt_started <= 1'b1;
                                sub_phase   <= 2'd1;
                            end
                        end
                        2'd1: begin
                            if (fmt_done) begin
                                if (fmt_error)
                                    err_pulse[E_TEMPLATE] <= 1'b1;
                                sub_phase <= 2'd2;
                            end
                        end
                        2'd2: begin
                            if (!uart_busy && !fmt_valid) begin
                                tx_req    <= 1'b0;
                                sub_phase <= 2'd3;
                            end
                        end
                        default: begin
                            if (!tx_req && hd_released) begin
                                fmt_started <= 1'b0;
                                sub_phase   <= 2'd0;
                                if (!frame_is_req) begin
                                    evt_frame_tx <= 1'b1;
                                    cmd_update   <= 1'b1;
                                    if (!use_bus && ROARM_FEEDBACK_EVERY > 1) begin
                                        if (roarm_query_phase == ROARM_FEEDBACK_EVERY-1)
                                            roarm_query_phase <= 0;
                                        else roarm_query_phase <= roarm_query_phase + 1'b1;
                                    end
                                    if (req_active && !fault && (use_bus || ROARM_FEEDBACK_EVERY <= 1 || roarm_query_phase == 0)) begin
                                        req_left     <= req_count;
                                        frame_is_req <= 1'b1;
                                        fmt_check    <= 1'b1;
                                        fmt_start    <= 1'b1;
                                        state        <= C_CHECK;
                                    end else begin
                                        state <= C_FINISH;
                                    end
                                end else if (use_bus && pins_enabled) begin
                                    sts_flush    <= 1'b1;
                                    resp_counter <= resp_timeout_cycles;
                                    state        <= C_WAIT_RESP;
                                end else begin
                                    finish_request;
                                end
                            end
                        end
                    endcase
                end

                C_WAIT_RESP: begin
                    if (sts_accept) begin
                        evt_fb_ok <= 1'b1;
                        if (sts_pkt_err != 8'd0) begin
                            err_pulse[E_SERVO_FAULT] <= 1'b1;
                            servo_fault_mask[rr_ch]  <= 1'b1;
                            last_servo_err           <= sts_pkt_err;
                            last_servo_err_id        <= sts_pkt_id;
                        end else begin
                            servo_fault_mask[rr_ch]  <= 1'b0;
                        end
                    end else if (sts_err_checksum || sts_err_protocol) begin
                        // counted above; the transaction ends
                    end else if (resp_counter != 24'd0) begin
                        resp_counter <= resp_counter - 24'd1;
                    end else begin
                        err_pulse[E_RESP_TIMEOUT] <= 1'b1;
                        evt_resp_timeout          <= 1'b1;
                    end

                    if (sts_accept || sts_err_checksum || sts_err_protocol ||
                        (resp_counter == 24'd0))
                        finish_request;
                end

                C_FINISH: begin
                    frame_cycles   <= cycle_count;
                    evt_frame_done <= 1'b1;
                    pace_counter   <= prime_period_cycles;   // poll only when idle
                    state          <= C_IDLE;
                end

                default: state <= C_IDLE;
            endcase
        end
    end

endmodule
