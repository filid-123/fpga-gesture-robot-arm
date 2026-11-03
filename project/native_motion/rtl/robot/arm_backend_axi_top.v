// ============================================================================
// Block Name : arm_backend_axi_top
// Description: AXI4-Lite control/status for the Phase 3 S1 arm backend
//              (development ABI 0x0000_3101, proposed BD window
//              0x43C3_0000 / 4 KiB).  Register map: docs/register_map.md and
//              ps/robot/arm_backend_axi_driver.py.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: S_AXI_ACLK only (100 MHz); no CDC inside this block.
//
// Configuration model (write-lock + COMMIT):
// - Configuration registers accept writes only while MODE=OFF and the core is
//   idle (otherwise SLVERR + CONFIG_WRITE_LOCKED).  Any accepted
//   configuration write, and any backend change, clears config_valid.
// - CONFIG_COMMIT runs the hardware template check of both programs plus the
//   scalar checks below and then sets config_valid (or CONFIG_INVALID_COMMIT).
//   Because the active path never reads configuration while OFF, this gives
//   shadow/COMMIT atomicity without a second copy of ~1,000 flip-flops.
// - Per-channel mapping parameters live in LUTRAM read by the sequential
//   mapper; configuration registers are write-only and read as zero.
//
// Hardware scalar checks at COMMIT (they prevent hangs or instant faults, not
// profile semantics, which stay in ps/robot/arm_profile.py):
//   selected baud divisor >= 16, WD_PRESCALE != 0, and when feedback is
//   required: timeout != 0 and arrival_count != 0; SO-ARM101: read_len == 2.
//
// Timing plan (100 MHz): writes take a decode cycle and an execute cycle,
// reads a registered address and a registered data cycle, and `fault` is
// registered; see the comments at write_decode and at `fault`.
//
// Status outputs that span several words (feedback, last command) are copied
// on CONTROL.FB_SNAPSHOT into two 8 x 32 snapshot LUTRAMs and held until the
// next snapshot.  The copy waits until the mapper and the watchdog are quiet,
// holds both for 6 cycles (one channel per cycle) and stalls AXI reads until
// it is complete, so every snapshot is one consistent instant.
//
// Field widths: RESP_TIMEOUT and PRIME_PERIOD 24 bit (167 ms), WD_PRESCALE
// 20 bit (10.5 ms per tick), FRAME_CYCLES_LAST/MAX 24 bit saturating,
// CNT_FB_ERR / CNT_RESP_TIMEOUT / CNT_LINES_IGNORED 16 bit wrapping.
//
// Truth boundary: source candidate.  Supplementary Icarus Verilog run only;
// XSim/synthesis/implementation/board not run.
// ============================================================================

`timescale 1ns / 1ps

module arm_backend_axi_top #(
    parameter integer C_S_AXI_DATA_WIDTH = 32,
    parameter integer C_S_AXI_ADDR_WIDTH = 12,
    parameter integer FAST_B = 0,
    parameter integer HAS_ROARM          = 1,
    parameter integer HAS_SO101          = 1,
    parameter integer DEBOUNCE_CYCLES    = 1_000_000,
    parameter integer ROARM_FEEDBACK_EVERY = 1,
    parameter [31:0]  ABI_VERSION        = 32'h0000_3101
) (
    input wire b_context,b_grip,
    input wire [15:0] b_speed,
    input wire [7:0] b_acc,
    input  wire                          S_AXI_ACLK,
    input  wire                          S_AXI_ARESETN,

    input  wire [C_S_AXI_ADDR_WIDTH-1:0] S_AXI_AWADDR,
    input  wire                          S_AXI_AWVALID,
    output wire                          S_AXI_AWREADY,
    input  wire [C_S_AXI_DATA_WIDTH-1:0] S_AXI_WDATA,
    input  wire [(C_S_AXI_DATA_WIDTH/8)-1:0] S_AXI_WSTRB,
    input  wire                          S_AXI_WVALID,
    output wire                          S_AXI_WREADY,
    output wire [1:0]                    S_AXI_BRESP,
    output wire                          S_AXI_BVALID,
    input  wire                          S_AXI_BREADY,
    input  wire [C_S_AXI_ADDR_WIDTH-1:0] S_AXI_ARADDR,
    input  wire                          S_AXI_ARVALID,
    output wire                          S_AXI_ARREADY,
    output wire [C_S_AXI_DATA_WIDTH-1:0] S_AXI_RDATA,
    output wire [1:0]                    S_AXI_RRESP,
    output wire                          S_AXI_RVALID,
    input  wire                          S_AXI_RREADY,

    input wire native_snap,
    output wire native_snap_ready,
    output reg native_snap_done,
    output wire [31:0] native_status, native_error, native_masks, native_age, native_frames,
    output wire                          irq,

    input  wire                          s_sample_valid,
    output wire                          s_sample_ready,
    input  wire [191:0]                  s_sample_data,

    output wire                          arm_uart_tx,
    input  wire                          arm_uart_rx,
    output wire                          bus_tx,
    input  wire                          bus_rx,
    output wire                          bus_dir,
    input  wire                          motion_enable_in
);

    localparam [1:0] AXI_RESP_OKAY   = 2'b00;
    localparam [1:0] AXI_RESP_SLVERR = 2'b10;

    localparam [11:0] REG_CONTROL       = 12'h000;
    localparam [11:0] REG_MODE          = 12'h004;
    localparam [11:0] REG_STATUS        = 12'h008;
    localparam [11:0] REG_ERROR_STATUS  = 12'h00c;
    localparam [11:0] REG_ABI_VERSION   = 12'h010;
    localparam [11:0] REG_CAPABILITIES  = 12'h014;
    localparam [11:0] REG_LIMIT_MASK    = 12'h018;
    localparam [11:0] REG_IRQ_ENABLE    = 12'h01c;
    localparam [11:0] REG_BAUD_ROARM    = 12'h020;
    localparam [11:0] REG_BAUD_BUS      = 12'h024;
    localparam [11:0] REG_HD_GUARD      = 12'h028;
    localparam [11:0] REG_RESP_TIMEOUT  = 12'h02c;
    localparam [11:0] REG_WD_PRESCALE   = 12'h030;
    localparam [11:0] REG_FEEDBACK_CFG  = 12'h034;
    localparam [11:0] REG_PROGRAM_CFG   = 12'h038;
    localparam [11:0] REG_PRIME_PERIOD  = 12'h03c;
    localparam [11:0] REG_TEMPLATE_ADDR = 12'h040;
    localparam [11:0] REG_TEMPLATE_DATA = 12'h044;
    localparam [11:0] REG_KEY_ADDR      = 12'h048;
    localparam [11:0] REG_KEY_DATA      = 12'h04c;
    localparam [11:0] REG_JSON_CFG      = 12'h050;
    localparam [11:0] REG_JSON_KEY_LEN  = 12'h054;
    localparam [11:0] REG_JSON_DISC     = 12'h058;
    localparam [11:0] REG_STS_CFG       = 12'h05c;
    localparam [11:0] REG_SNAP_FB_MASKS = 12'h218;
    localparam [11:0] REG_SNAP_FB_AGE   = 12'h21c;
    localparam [11:0] REG_SNAP_FB_ERR   = 12'h238;
    localparam [11:0] REG_CNT_FRAMES    = 12'h300;
    localparam [11:0] REG_CNT_FB_OK     = 12'h304;
    localparam [11:0] REG_CNT_FB_ERR    = 12'h308;
    localparam [11:0] REG_CNT_RESP_TO   = 12'h30c;
    localparam [11:0] REG_CYCLES_LAST   = 12'h310;
    localparam [11:0] REG_CYCLES_MAX    = 12'h314;
    localparam [11:0] REG_CNT_IGNORED   = 12'h318;

    localparam [1:0] MODE_OFF = 2'd0;

    // ERROR_STATUS bits owned by this block.
    localparam integer E_CONFIG_INVALID = 3;
    localparam integer E_CONFIG_LOCKED  = 4;
    localparam integer E_AXI_ACCESS     = 5;
    localparam integer E_CONTROL        = 14;
    // Fatal set (arm_feedback.PL_FATAL_ERRORS): limit, saturation, template,
    // feedback timeout, e-stop, servo fault.
    localparam [14:0] FATAL_MASK = 15'b011_1000_0000_0111;

    // ------------------------------------------------------ AXI handshake
    reg [C_S_AXI_ADDR_WIDTH-1:0] awaddr_hold;
    reg                          aw_pending;
    reg [C_S_AXI_DATA_WIDTH-1:0] wdata_hold;
    reg [(C_S_AXI_DATA_WIDTH/8)-1:0] wstrb_hold;
    reg                          w_pending;
    reg [1:0]                    axi_bresp;
    reg                          axi_bvalid;
    reg [C_S_AXI_DATA_WIDTH-1:0] axi_rdata;
    reg [1:0]                    axi_rresp;
    reg                          axi_rvalid;

    // Timing plan: a write is decoded in one cycle (write_decode registers
    // the address class and the reserved-bit checks) and executed in the next
    // (write_commit); a read registers its address and returns data one cycle
    // later.  No path chains the AXI address decode with the core state.
    reg                          wdec_valid;
    reg                          rd_pending;
    reg [11:0]                   araddr_r;
    reg                          rd_ok;          // registered read_address_valid
    reg [4:0]                    rd_sel;         // registered read_select
    wire aw_accept    = S_AXI_AWVALID && S_AXI_AWREADY;
    wire w_accept     = S_AXI_WVALID && S_AXI_WREADY;
    wire ar_accept    = S_AXI_ARVALID && S_AXI_ARREADY;
    wire write_decode = aw_pending && w_pending && !axi_bvalid && !wdec_valid;
    wire write_commit = wdec_valid;

    assign S_AXI_AWREADY = !aw_pending && !axi_bvalid;
    assign S_AXI_WREADY  = !w_pending && !axi_bvalid;
    assign S_AXI_BRESP   = axi_bresp;
    assign S_AXI_BVALID  = axi_bvalid;
    assign S_AXI_RDATA   = axi_rdata;
    assign S_AXI_RRESP   = axi_rresp;
    assign S_AXI_RVALID  = axi_rvalid;

    // ------------------------------------------------------ control state
    reg [1:0]  mode_reg;
    reg        backend_reg;
    reg        arm_reg;
    reg        config_valid;
    reg        commit_busy;
    reg        commit_scalars_ok;
    reg        commit_start;
    reg        snapshot_valid;
    reg        irq_enable;
    reg [14:0] error_status;
    reg [5:0]  limit_sticky;

    // ------------------------------------------------ configuration storage
    reg [15:0] baud_div_roarm;
    reg [15:0] baud_div_bus;
    reg [15:0] hd_lead;
    reg [15:0] hd_lag;
    reg [23:0] resp_timeout;
    reg [19:0] wd_prescale;
    reg [15:0] fb_timeout_ticks;
    reg [3:0]  arrival_count;
    reg [5:0]  required_mask;
    reg [7:0]  cmd_base;
    reg [7:0]  req_base;
    reg        req_enable;
    reg [2:0]  reads_per_cycle;
    reg [23:0] prime_period;
    reg [7:0]  template_addr;
    reg [6:0]  key_addr;
    reg [2:0]  json_frac;
    reg [7:0]  json_term;
    reg [15:0] json_max_len;
    reg [27:0] json_key_len;
    reg [31:0] json_disc;
    reg [7:0]  sts_hdr0;
    reg [7:0]  sts_hdr1;
    reg [2:0]  sts_read_len;
    reg [1:0]  sts_encoding;
    reg        sts_big_endian;
    reg        sts_ck_invert;
    reg [5:0]  dir_neg;
    reg [47:0] device_ids;
    reg [95:0] tol_dev;

    (* ram_style = "distributed" *) reg [31:0] ch_min_mem   [0:7];
    (* ram_style = "distributed" *) reg [31:0] ch_max_mem   [0:7];
    (* ram_style = "distributed" *) reg [31:0] ch_zero_mem  [0:7];
    (* ram_style = "distributed" *) reg [31:0] ch_scale_mem [0:7];

    // --------------------------------------------------------- snapshot
    (* ram_style = "distributed" *) reg [31:0] snap_fb_mem  [0:7];
    (* ram_style = "distributed" *) reg [31:0] snap_cmd_mem [0:7];
    reg         snap_req;
    reg         snap_busy;
    reg [2:0]   snap_copy_ch;
    reg [5:0]   snap_valid_mask;
    reg [5:0]   snap_arrival_mask;
    reg [5:0]   snap_servo_mask;
    reg [15:0]  snap_age_max;
    reg [15:0]  snap_fb_seq;
    reg [7:0]   snap_servo_err;
    reg [7:0]   snap_servo_err_id;

    // --------------------------------------------------------- counters
    reg [31:0] cnt_frames;
    reg [31:0] cnt_fb_ok;
    reg [15:0] cnt_fb_err;
    reg [15:0] cnt_resp_timeout;
    reg [15:0] cnt_ignored;
    reg [23:0] cycles_last;
    reg [23:0] cycles_max;

    // ------------------------------------------------------------- core
    wire         core_commit_done;
    wire         core_commit_ok;
    wire         core_busy;
    wire [3:0]   core_state;
    wire [1:0]   core_active_mode;
    wire         core_active_backend;
    wire         core_permission;
    wire         core_estop_ok;
    wire         core_feedback_valid;
    wire [14:0]  core_err_pulse;
    wire [5:0]   core_limit_evt;
    wire         core_evt_frame_tx;
    wire         core_evt_fb_ok;
    wire         core_evt_fb_err;
    wire         core_evt_resp_timeout;
    wire         core_evt_ignored;
    wire         core_evt_frame_done;
    wire [23:0]  core_frame_cycles;
    wire [31:0]  core_snap_fb;
    wire [31:0]  core_snap_cmd;
    wire         core_snap_quiet;
    wire [5:0]   core_fb_valid;
    wire [5:0]   core_fb_arrival;
    wire [5:0]   core_servo_mask;
    wire [15:0]  core_age_max;
    wire [15:0]  core_fb_seq;
    wire [7:0]   core_servo_err;
    wire [7:0]   core_servo_err_id;
    wire [2:0]   map_cfg_ch;

    // fault is registered (one cycle after the sticky bit); the core re-checks
    // it at its last gate before transmitting, so the extra cycle never lets a
    // frame out.
    reg  fault;
    wire snap_hold = snap_req || snap_busy;
    assign native_snap_ready = !snap_hold && !aw_pending && !w_pending && !wdec_valid && !axi_bvalid && !S_AXI_AWVALID && !S_AXI_WVALID;

    assign S_AXI_ARREADY = !axi_rvalid && !rd_pending && !snap_hold;   // reads wait for a running copy

    always @(posedge S_AXI_ACLK) begin
        if (!S_AXI_ARESETN)
            fault <= 1'b0;
        else
            fault <= |(error_status & FATAL_MASK);
    end

    integer init_i;
    initial begin
        for (init_i = 0; init_i < 8; init_i = init_i + 1) begin
            snap_fb_mem[init_i]  = 32'd0;
            snap_cmd_mem[init_i] = 32'd0;
        end
    end

    // Snapshot copy: one channel per cycle from the core's LUTRAM read ports.
    always @(posedge S_AXI_ACLK) begin
        if (snap_busy) begin
            snap_fb_mem[snap_copy_ch]  <= core_snap_fb;
            snap_cmd_mem[snap_copy_ch] <= core_snap_cmd;
        end
    end
    assign irq = irq_enable && fault;

    // Lock state, registered at write_decode and used at write_commit.  It can
    // turn from unlocked to locked only through an AXI write (MODE or COMMIT),
    // and writes are serialized (a decode starts only after the previous B
    // handshake), so the registered value is exact for the executing write;
    // the opposite transition (core finishing) at worst returns one SLVERR.
    wire core_idle_off_d = (mode_reg == MODE_OFF) && (core_active_mode == MODE_OFF) && !core_busy;
    wire cfg_unlocked_d  = core_idle_off_d && !commit_busy;
    reg  core_idle_off;
    reg  cfg_unlocked;

    // --------------------------------------------------- write decoding
    wire [11:0] waddr = awaddr_hold[11:0];
    wire [2:0]  wch       = waddr[7:5];
    wire [2:0]  wfield    = waddr[4:2];
    // Decode stage (registered at write_decode, used at write_commit).
    wire        wfull_d   = (awaddr_hold[1:0] == 2'b00) &&
                            (wstrb_hold == {(C_S_AXI_DATA_WIDTH/8){1'b1}});
    wire        w_is_chan_d = (waddr[11:8] == 4'h1) && (wch < 3'd6) && (wfield <= 3'd5);
    wire        w_is_scalar_cfg_d = (waddr >= REG_BAUD_ROARM) && (waddr <= REG_STS_CFG);
    reg         wfull;
    reg         w_is_chan;
    reg         w_is_scalar_cfg;
    reg         ctrl_rsvd;           // CONTROL: reserved bits or more than one command bit
    reg         mode_rsvd;           // MODE: reserved bits set
    reg         irq_rsvd;            // IRQ_ENABLE: reserved bits set
    wire        w_is_cfg  = w_is_chan || w_is_scalar_cfg;
    wire        cfg_write_ok = write_commit && wfull && w_is_cfg && cfg_unlocked;

    wire ch_mem_we = cfg_write_ok && w_is_chan;

    // Reset-free LUTRAM write ports.
    always @(posedge S_AXI_ACLK) begin
        if (ch_mem_we) begin
            case (wfield)
                3'd0: ch_min_mem[wch]   <= wdata_hold;
                3'd1: ch_max_mem[wch]   <= wdata_hold;
                3'd2: ch_zero_mem[wch]  <= wdata_hold;
                3'd3: ch_scale_mem[wch] <= wdata_hold;
                default: ;
            endcase
        end
    end

    wire        tpl_we  = cfg_write_ok && (waddr == REG_TEMPLATE_DATA);
    wire        key_we  = cfg_write_ok && (waddr == REG_KEY_DATA);

    // Scalar COMMIT checks (see header).
    wire [15:0] sel_baud = backend_reg ? baud_div_bus : baud_div_roarm;
    wire scalars_ok = (sel_baud >= 16'd16) && (wd_prescale != 20'd0) &&
                      ((required_mask == 6'd0) ||
                       ((fb_timeout_ticks != 16'd0) && (arrival_count != 4'd0))) &&
                      (reads_per_cycle <= 3'd6) &&
                      (!backend_reg || (sts_read_len == 3'd2));

    function automatic multiple_bits;
        input [3:0] bits;
        begin
            multiple_bits = (bits[0] + bits[1] + bits[2] + bits[3]) > 3'd1;
        end
    endfunction

    wire backend_present_0 = (HAS_ROARM != 0);
    wire backend_present_1 = (HAS_SO101 != 0);

    always @(posedge S_AXI_ACLK) begin
        if (!S_AXI_ARESETN) begin
            awaddr_hold       <= {C_S_AXI_ADDR_WIDTH{1'b0}};
            aw_pending        <= 1'b0;
            wdec_valid        <= 1'b0;
            core_idle_off     <= 1'b0;
            cfg_unlocked      <= 1'b0;
            wfull             <= 1'b0;
            w_is_chan         <= 1'b0;
            w_is_scalar_cfg   <= 1'b0;
            ctrl_rsvd         <= 1'b0;
            mode_rsvd         <= 1'b0;
            irq_rsvd          <= 1'b0;
            wdata_hold        <= {C_S_AXI_DATA_WIDTH{1'b0}};
            wstrb_hold        <= {(C_S_AXI_DATA_WIDTH/8){1'b0}};
            w_pending         <= 1'b0;
            axi_bresp         <= AXI_RESP_OKAY;
            axi_bvalid        <= 1'b0;
            mode_reg          <= MODE_OFF;
            backend_reg       <= (HAS_ROARM != 0) ? 1'b0 : 1'b1;
            arm_reg           <= 1'b0;
            config_valid      <= 1'b0;
            commit_busy       <= 1'b0;
            commit_scalars_ok <= 1'b0;
            commit_start      <= 1'b0;
            snapshot_valid    <= 1'b0; native_snap_done<=0;
            irq_enable        <= 1'b0;
            error_status      <= 15'd0;
            limit_sticky      <= 6'd0;
            baud_div_roarm    <= 16'd868;
            baud_div_bus      <= 16'd100;
            hd_lead           <= 16'd0;
            hd_lag            <= 16'd0;
            resp_timeout      <= 24'd0;
            wd_prescale       <= 20'd100000;
            fb_timeout_ticks  <= 16'd0;
            arrival_count     <= 4'd0;
            required_mask     <= 6'd0;
            cmd_base          <= 8'd0;
            req_base          <= 8'd0;
            req_enable        <= 1'b0;
            reads_per_cycle   <= 3'd1;
            prime_period      <= 24'd0;
            template_addr     <= 8'd0;
            key_addr          <= 7'd0;
            json_frac         <= 3'd0;
            json_term         <= 8'h0a;
            json_max_len      <= 16'd512;
            json_key_len      <= 28'd0;
            json_disc         <= 32'd0;
            sts_hdr0          <= 8'd0;
            sts_hdr1          <= 8'd0;
            sts_read_len      <= 3'd2;
            sts_encoding      <= 2'd0;
            sts_big_endian    <= 1'b0;
            sts_ck_invert     <= 1'b1;
            dir_neg           <= 6'd0;
            device_ids        <= 48'd0;
            tol_dev           <= 96'd0;
            snap_req          <= 1'b0;
            snap_busy         <= 1'b0;
            snap_copy_ch      <= 3'd0;
            snap_valid_mask   <= 6'd0;
            snap_arrival_mask <= 6'd0;
            snap_servo_mask   <= 6'd0;
            snap_age_max      <= 16'd0;
            snap_fb_seq       <= 16'd0;
            snap_servo_err    <= 8'd0;
            snap_servo_err_id <= 8'd0;
            cnt_frames        <= 32'd0;
            cnt_fb_ok         <= 32'd0;
            cnt_fb_err        <= 16'd0;
            cnt_resp_timeout  <= 16'd0;
            cnt_ignored       <= 16'd0;
            cycles_last       <= 24'd0;
            cycles_max        <= 24'd0;
        end else begin
            commit_start <= 1'b0;

            if (aw_accept) begin
                awaddr_hold <= S_AXI_AWADDR;
                aw_pending  <= 1'b1;
            end
            if (w_accept) begin
                wdata_hold <= S_AXI_WDATA;
                wstrb_hold <= S_AXI_WSTRB;
                w_pending  <= 1'b1;
            end
            if (write_decode) begin
                wdec_valid      <= 1'b1;
                core_idle_off   <= core_idle_off_d;
                cfg_unlocked    <= cfg_unlocked_d;
                wfull           <= wfull_d;
                w_is_chan       <= w_is_chan_d;
                w_is_scalar_cfg <= w_is_scalar_cfg_d;
                ctrl_rsvd       <= (wdata_hold[31:4] != 28'd0) || multiple_bits(wdata_hold[3:0]);
                mode_rsvd       <= (wdata_hold[31:9] != 23'd0) || (wdata_hold[7:5] != 3'd0) ||
                                   (wdata_hold[3:2] != 2'd0);
                irq_rsvd        <= (wdata_hold[31:1] != 31'd0);
            end

            // --------------------------------------------- core events
            native_snap_done<=0;
            if (native_snap && native_snap_ready) snap_req<=1;
            error_status <= error_status | core_err_pulse;
            if (core_err_pulse[0])
                limit_sticky <= limit_sticky | core_limit_evt;
            if (core_evt_frame_tx)     cnt_frames       <= cnt_frames + 32'd1;
            if (core_evt_fb_ok)        cnt_fb_ok        <= cnt_fb_ok + 32'd1;
            if (core_evt_fb_err)       cnt_fb_err       <= cnt_fb_err + 16'd1;
            if (core_evt_resp_timeout) cnt_resp_timeout <= cnt_resp_timeout + 16'd1;
            if (core_evt_ignored)      cnt_ignored      <= cnt_ignored + 16'd1;
            if (core_evt_frame_done) begin
                cycles_last <= core_frame_cycles;
                if (core_frame_cycles > cycles_max)
                    cycles_max <= core_frame_cycles;
            end
            // Snapshot copy sequencing.
            if (snap_req && !snap_busy && core_snap_quiet) begin
                snap_req          <= 1'b0;
                snap_busy         <= 1'b1;
                snap_copy_ch      <= 3'd0;
                snap_valid_mask   <= core_fb_valid;
                snap_arrival_mask <= core_fb_arrival;
                snap_servo_mask   <= core_servo_mask;
                snap_age_max      <= core_age_max;
                snap_fb_seq       <= core_fb_seq;
                snap_servo_err    <= core_servo_err;
                snap_servo_err_id <= core_servo_err_id;
            end else if (snap_busy) begin
                if (snap_copy_ch == 3'd5) begin
                    snap_busy      <= 1'b0;
                    snapshot_valid <= 1'b1; native_snap_done<=1;
                end else begin
                    snap_copy_ch <= snap_copy_ch + 3'd1;
                end
            end

            if (core_commit_done) begin
                commit_busy  <= 1'b0;
                config_valid <= core_commit_ok && commit_scalars_ok;
                if (!(core_commit_ok && commit_scalars_ok))
                    error_status[E_CONFIG_INVALID] <= 1'b1;
            end

            // Invalid read addresses leave a sticky diagnostic.
            if (rd_pending && !rd_ok)
                error_status[E_AXI_ACCESS] <= 1'b1;

            // --------------------------------------------- AXI writes
            if (write_commit) begin
                wdec_valid <= 1'b0;
                aw_pending <= 1'b0;
                w_pending  <= 1'b0;
                axi_bvalid <= 1'b1;
                axi_bresp  <= AXI_RESP_OKAY;

                if (!wfull) begin
                    axi_bresp                  <= AXI_RESP_SLVERR;
                    error_status[E_AXI_ACCESS] <= 1'b1;
                end else if (w_is_cfg) begin
                    if (!cfg_unlocked) begin
                        axi_bresp                     <= AXI_RESP_SLVERR;
                        error_status[E_CONFIG_LOCKED] <= 1'b1;
                    end else begin
                        config_valid <= 1'b0;
                        if (w_is_chan) begin
                            if (wfield == 3'd4) begin
                                dir_neg[wch]            <= wdata_hold[0];
                                device_ids[wch * 8 +: 8] <= wdata_hold[15:8];
                            end else if (wfield == 3'd5) begin
                                tol_dev[wch * 16 +: 16] <= wdata_hold[15:0];
                            end
                        end else begin
                            case (waddr)
                                REG_BAUD_ROARM:   baud_div_roarm <= wdata_hold[15:0];
                                REG_BAUD_BUS:     baud_div_bus   <= wdata_hold[15:0];
                                REG_HD_GUARD: begin
                                    hd_lead <= wdata_hold[15:0];
                                    hd_lag  <= wdata_hold[31:16];
                                end
                                REG_RESP_TIMEOUT: resp_timeout <= wdata_hold[23:0];
                                REG_WD_PRESCALE:  wd_prescale  <= wdata_hold[19:0];
                                REG_FEEDBACK_CFG: begin
                                    fb_timeout_ticks <= wdata_hold[15:0];
                                    arrival_count    <= wdata_hold[19:16];
                                    required_mask    <= wdata_hold[29:24];
                                end
                                REG_PROGRAM_CFG: begin
                                    cmd_base        <= wdata_hold[7:0];
                                    req_base        <= wdata_hold[15:8];
                                    req_enable      <= wdata_hold[16];
                                    reads_per_cycle <= wdata_hold[19:17];
                                end
                                REG_PRIME_PERIOD:  prime_period  <= wdata_hold[23:0];
                                REG_TEMPLATE_ADDR: template_addr <= wdata_hold[7:0];
                                REG_TEMPLATE_DATA: template_addr <= template_addr + 8'd1;
                                REG_KEY_ADDR:      key_addr      <= wdata_hold[6:0];
                                REG_KEY_DATA:      key_addr      <= key_addr + 7'd1;
                                REG_JSON_CFG: begin
                                    json_frac    <= wdata_hold[2:0];
                                    json_term    <= wdata_hold[15:8];
                                    json_max_len <= wdata_hold[31:16];
                                end
                                REG_JSON_KEY_LEN: json_key_len <= wdata_hold[27:0];
                                REG_JSON_DISC:    json_disc    <= wdata_hold;
                                REG_STS_CFG: begin
                                    sts_hdr0       <= wdata_hold[7:0];
                                    sts_hdr1       <= wdata_hold[15:8];
                                    sts_read_len   <= wdata_hold[18:16];
                                    sts_encoding   <= wdata_hold[21:20];
                                    sts_big_endian <= wdata_hold[22];
                                    sts_ck_invert  <= wdata_hold[23];
                                end
                                default: begin
                                    // 0x020..0x05c is fully decoded above.
                                    axi_bresp                  <= AXI_RESP_SLVERR;
                                    error_status[E_AXI_ACCESS] <= 1'b1;
                                end
                            endcase
                        end
                    end
                end else begin
                    case (waddr)
                        REG_CONTROL: begin
                            if (ctrl_rsvd) begin
                                axi_bresp                <= AXI_RESP_SLVERR;
                                error_status[E_CONTROL]  <= 1'b1;
                            end else if (wdata_hold[0]) begin
                                if (!cfg_unlocked) begin
                                    axi_bresp               <= AXI_RESP_SLVERR;
                                    error_status[E_CONTROL] <= 1'b1;
                                end else begin
                                    commit_busy       <= 1'b1;
                                    commit_start      <= 1'b1;
                                    commit_scalars_ok <= scalars_ok;
                                    config_valid      <= 1'b0;
                                end
                            end else if (wdata_hold[1] || wdata_hold[3]) begin
                                if (!core_idle_off) begin
                                    axi_bresp               <= AXI_RESP_SLVERR;
                                    error_status[E_CONTROL] <= 1'b1;
                                end else if (wdata_hold[1]) begin
                                    error_status <= core_err_pulse;     // new events win
                                    limit_sticky <= 6'd0;
                                end else begin
                                    cnt_frames       <= 32'd0;
                                    cnt_fb_ok        <= 32'd0;
                                    cnt_fb_err       <= 16'd0;
                                    cnt_resp_timeout <= 16'd0;
                                    cnt_ignored      <= 16'd0;
                                    cycles_last      <= 24'd0;
                                    cycles_max       <= 24'd0;
                                end
                            end else if (wdata_hold[2]) begin
                                snap_req <= 1'b1;               // copied when quiet
                            end
                        end

                        REG_MODE: begin
                            if (mode_rsvd) begin
                                axi_bresp               <= AXI_RESP_SLVERR;
                                error_status[E_CONTROL] <= 1'b1;
                            end else if (wdata_hold[4] != backend_reg) begin
                                // Backend switch: OFF only, target must exist.
                                if ((wdata_hold[1:0] != MODE_OFF) || !cfg_unlocked ||
                                    (wdata_hold[4] ? !backend_present_1 : !backend_present_0)) begin
                                    axi_bresp               <= AXI_RESP_SLVERR;
                                    error_status[E_CONTROL] <= 1'b1;
                                end else begin
                                    backend_reg  <= wdata_hold[4];
                                    arm_reg      <= wdata_hold[8];
                                    config_valid <= 1'b0;
                                end
                            end else if ((wdata_hold[1:0] != MODE_OFF) &&
                                         (((mode_reg != MODE_OFF) && (wdata_hold[1:0] != mode_reg)) ||
                                          !config_valid || fault)) begin
                                axi_bresp               <= AXI_RESP_SLVERR;
                                error_status[E_CONTROL] <= 1'b1;
                            end else begin
                                mode_reg <= wdata_hold[1:0];
                                arm_reg  <= wdata_hold[8];
                            end
                        end

                        REG_IRQ_ENABLE: begin
                            if (irq_rsvd) begin
                                axi_bresp                  <= AXI_RESP_SLVERR;
                                error_status[E_AXI_ACCESS] <= 1'b1;
                            end else begin
                                irq_enable <= wdata_hold[0];
                            end
                        end

                        default: begin
                            axi_bresp                  <= AXI_RESP_SLVERR;
                            error_status[E_AXI_ACCESS] <= 1'b1;
                        end
                    endcase
                end
            end else if (axi_bvalid && S_AXI_BREADY) begin
                axi_bvalid <= 1'b0;
            end
        end
    end

    // ---------------------------------------------------------- reads
    function automatic read_address_valid;
        input [11:0] addr;
        begin
            if (addr[1:0] != 2'b00)
                read_address_valid = 1'b0;
            else if (addr <= REG_STS_CFG)
                read_address_valid = 1'b1;
            else if ((addr[11:8] == 4'h1) && (addr[7:5] < 3'd6) && (addr[4:2] <= 3'd5))
                read_address_valid = 1'b1;
            else if ((addr >= 12'h200) && (addr <= REG_SNAP_FB_ERR))
                read_address_valid = 1'b1;
            else if ((addr >= REG_CNT_FRAMES) && (addr <= REG_CNT_IGNORED))
                read_address_valid = 1'b1;
            else
                read_address_valid = 1'b0;
        end
    endfunction

    // Read-data source, decoded when AR is accepted and registered, so the
    // data cycle is a single 5-bit-select multiplexer.
    localparam [4:0] RD_ZERO = 5'd0,  RD_SNAP_FB = 5'd1, RD_SNAP_CMD = 5'd2, RD_MODE = 5'd3,
                     RD_STATUS = 5'd4, RD_ERROR = 5'd5, RD_ABI = 5'd6, RD_CAPS = 5'd7,
                     RD_LIMIT = 5'd8, RD_IRQ_EN = 5'd9, RD_TEMPLATE_ADDR = 5'd10,
                     RD_KEY_ADDR = 5'd11, RD_SNAP_MASKS = 5'd12, RD_SNAP_AGE = 5'd13,
                     RD_SNAP_ERR = 5'd14, RD_CNT_FRAMES = 5'd15, RD_CNT_FB_OK = 5'd16,
                     RD_CNT_FB_ERR = 5'd17, RD_CNT_RESP_TO = 5'd18, RD_CYCLES_LAST = 5'd19,
                     RD_CYCLES_MAX = 5'd20, RD_CNT_IGNORED = 5'd21;

    function automatic [4:0] read_select;
        input [11:0] addr;
        begin
            if ((addr >= 12'h200) && (addr <= 12'h214))
                read_select = RD_SNAP_FB;
            else if ((addr >= 12'h220) && (addr <= 12'h234))
                read_select = RD_SNAP_CMD;
            else begin
                case (addr)
                    REG_MODE:          read_select = RD_MODE;
                    REG_STATUS:        read_select = RD_STATUS;
                    REG_ERROR_STATUS:  read_select = RD_ERROR;
                    REG_ABI_VERSION:   read_select = RD_ABI;
                    REG_CAPABILITIES:  read_select = RD_CAPS;
                    REG_LIMIT_MASK:    read_select = RD_LIMIT;
                    REG_IRQ_ENABLE:    read_select = RD_IRQ_EN;
                    REG_TEMPLATE_ADDR: read_select = RD_TEMPLATE_ADDR;
                    REG_KEY_ADDR:      read_select = RD_KEY_ADDR;
                    REG_SNAP_FB_MASKS: read_select = RD_SNAP_MASKS;
                    REG_SNAP_FB_AGE:   read_select = RD_SNAP_AGE;
                    REG_SNAP_FB_ERR:   read_select = RD_SNAP_ERR;
                    REG_CNT_FRAMES:    read_select = RD_CNT_FRAMES;
                    REG_CNT_FB_OK:     read_select = RD_CNT_FB_OK;
                    REG_CNT_FB_ERR:    read_select = RD_CNT_FB_ERR;
                    REG_CNT_RESP_TO:   read_select = RD_CNT_RESP_TO;
                    REG_CYCLES_LAST:   read_select = RD_CYCLES_LAST;
                    REG_CYCLES_MAX:    read_select = RD_CYCLES_MAX;
                    REG_CNT_IGNORED:   read_select = RD_CNT_IGNORED;
                    default:           read_select = RD_ZERO;
                endcase
            end
        end
    endfunction

    wire [31:0] status_word = {
        17'd0,
        core_active_backend,
        core_active_mode,
        core_state,
        irq,
        snapshot_valid,
        core_feedback_valid,
        fault,
        core_estop_ok,
        core_permission,
        core_busy || commit_busy,
        config_valid
    };

    assign native_status=status_word;
    assign native_error={17'd0,error_status};
    assign native_masks={10'd0,snap_servo_mask,2'd0,snap_arrival_mask,2'd0,snap_valid_mask};
    assign native_age={snap_fb_seq,snap_age_max};
    assign native_frames=cnt_frames;
    wire [31:0] capabilities_word = {
        4'd0,
        8'd16,                        // [27:20] minimum baud divisor
        4'd4,                         // [19:16] max status params
        4'd7,                         // [15:12] JSON key slots
        4'd8,                         // [11:8]  log2(template depth)
        6'd0,
        backend_present_1,
        backend_present_0
    };

    always @(posedge S_AXI_ACLK) begin
        if (!S_AXI_ARESETN) begin
            axi_rdata  <= {C_S_AXI_DATA_WIDTH{1'b0}};
            axi_rresp  <= AXI_RESP_OKAY;
            axi_rvalid <= 1'b0;
            rd_pending <= 1'b0;
            araddr_r   <= 12'd0;
            rd_ok      <= 1'b0;
            rd_sel     <= RD_ZERO;
        end else if (rd_pending) begin
            rd_pending <= 1'b0;
            axi_rvalid <= 1'b1;
            axi_rresp  <= AXI_RESP_OKAY;
            axi_rdata  <= 32'd0;              // configuration registers read as zero
            if (!rd_ok) begin
                axi_rresp <= AXI_RESP_SLVERR;
            end else begin
                case (rd_sel)
                    RD_SNAP_FB:        axi_rdata <= snap_fb_mem[araddr_r[4:2]];
                    RD_SNAP_CMD:       axi_rdata <= snap_cmd_mem[araddr_r[4:2]];
                    RD_MODE:           axi_rdata <= {23'd0, arm_reg, 3'd0, backend_reg, 2'd0, mode_reg};
                    RD_STATUS:         axi_rdata <= status_word;
                    RD_ERROR:          axi_rdata <= {17'd0, error_status};
                    RD_ABI:            axi_rdata <= ABI_VERSION;
                    RD_CAPS:           axi_rdata <= capabilities_word;
                    RD_LIMIT:          axi_rdata <= {26'd0, limit_sticky};
                    RD_IRQ_EN:         axi_rdata <= {31'd0, irq_enable};
                    RD_TEMPLATE_ADDR:  axi_rdata <= {24'd0, template_addr};
                    RD_KEY_ADDR:       axi_rdata <= {25'd0, key_addr};
                    RD_SNAP_MASKS:     axi_rdata <= {10'd0, snap_servo_mask, 2'd0, snap_arrival_mask,
                                                     2'd0, snap_valid_mask};
                    RD_SNAP_AGE:       axi_rdata <= {snap_fb_seq, snap_age_max};
                    RD_SNAP_ERR:       axi_rdata <= {16'd0, snap_servo_err_id, snap_servo_err};
                    RD_CNT_FRAMES:     axi_rdata <= cnt_frames;
                    RD_CNT_FB_OK:      axi_rdata <= cnt_fb_ok;
                    RD_CNT_FB_ERR:     axi_rdata <= {16'd0, cnt_fb_err};
                    RD_CNT_RESP_TO:    axi_rdata <= {16'd0, cnt_resp_timeout};
                    RD_CYCLES_LAST:    axi_rdata <= {8'd0, cycles_last};
                    RD_CYCLES_MAX:     axi_rdata <= {8'd0, cycles_max};
                    RD_CNT_IGNORED:    axi_rdata <= {16'd0, cnt_ignored};
                    default:           axi_rdata <= 32'd0;       // write-only configuration
                endcase
            end
        end else if (ar_accept) begin
            rd_pending <= 1'b1;
            araddr_r   <= S_AXI_ARADDR[11:0];
            rd_ok      <= read_address_valid(S_AXI_ARADDR[11:0]);
            rd_sel     <= read_select(S_AXI_ARADDR[11:0]);
        end else if (axi_rvalid && S_AXI_RREADY) begin
            axi_rvalid <= 1'b0;
        end
    end

    // ------------------------------------------------------------- core
    arm_backend_core #(
        .FAST_B(FAST_B),
        .HAS_ROARM(HAS_ROARM),
        .HAS_SO101(HAS_SO101),
        .DEBOUNCE_CYCLES(DEBOUNCE_CYCLES),.ROARM_FEEDBACK_EVERY(ROARM_FEEDBACK_EVERY)
    ) u_core (
        .clk(S_AXI_ACLK),
        .rst_n(S_AXI_ARESETN),
        .mode_req(mode_reg),
        .backend_sel(backend_reg),
        .arm(arm_reg),
        .config_valid(config_valid),
        .fault(fault),
        .commit_start(commit_start),
        .commit_done(core_commit_done),
        .commit_ok(core_commit_ok),
        .baud_div_roarm(baud_div_roarm),
        .baud_div_bus(baud_div_bus),
        .hd_lead_cycles(hd_lead),
        .hd_lag_cycles(hd_lag),
        .resp_timeout_cycles(resp_timeout),
        .wd_prescale(wd_prescale),
        .prime_period_cycles(prime_period),
        .fb_timeout_ticks(fb_timeout_ticks),
        .arrival_count(arrival_count),
        .required_mask(required_mask),
        .b_context(b_context),.b_speed(b_speed),.b_acc(b_acc),.b_grip(b_grip),
        .cmd_base(cmd_base),
        .req_base(req_base),
        .req_enable(req_enable),
        .reads_per_cycle(reads_per_cycle),
        .dir_neg(dir_neg),
        .device_ids(device_ids),
        .tol_dev(tol_dev),
        .json_frac_digits(json_frac),
        .json_line_term(json_term),
        .json_max_line_len(json_max_len),
        .json_key_len(json_key_len),
        .json_disc_value(json_disc),
        .sts_hdr0(sts_hdr0),
        .sts_hdr1(sts_hdr1),
        .sts_read_len(sts_read_len),
        .sts_encoding(sts_encoding),
        .sts_big_endian(sts_big_endian),
        .sts_ck_invert(sts_ck_invert),
        .seq_byte(cnt_frames[7:0]),
        .map_cfg_ch(map_cfg_ch),
        .map_soft_min(ch_min_mem[map_cfg_ch]),
        .map_soft_max(ch_max_mem[map_cfg_ch]),
        .map_zero(ch_zero_mem[map_cfg_ch]),
        .map_scale(ch_scale_mem[map_cfg_ch]),
        .tpl_we(tpl_we),
        .tpl_waddr(template_addr),
        .tpl_wdata(wdata_hold[15:0]),
        .key_we(key_we),
        .key_waddr(key_addr),
        .key_wdata(wdata_hold[7:0]),
        .s_valid(s_sample_valid),
        .s_ready(s_sample_ready),
        .s_data(s_sample_data),
        .arm_uart_tx(arm_uart_tx),
        .arm_uart_rx(arm_uart_rx),
        .bus_tx(bus_tx),
        .bus_rx(bus_rx),
        .bus_dir(bus_dir),
        .motion_enable_in(motion_enable_in),
        .engine_busy(core_busy),
        .core_state(core_state),
        .active_mode(core_active_mode),
        .active_backend(core_active_backend),
        .permission(core_permission),
        .estop_ok(core_estop_ok),
        .feedback_all_valid(core_feedback_valid),
        .err_pulse(core_err_pulse),
        .limit_mask_evt(core_limit_evt),
        .evt_frame_tx(core_evt_frame_tx),
        .evt_fb_ok(core_evt_fb_ok),
        .evt_fb_err(core_evt_fb_err),
        .evt_resp_timeout(core_evt_resp_timeout),
        .evt_line_ignored(core_evt_ignored),
        .evt_frame_done(core_evt_frame_done),
        .frame_cycles(core_frame_cycles),
        .snap_hold(snap_hold),
        .snap_ch(snap_copy_ch),
        .snap_fb_value(core_snap_fb),
        .snap_cmd_value(core_snap_cmd),
        .snap_quiet(core_snap_quiet),
        .fb_valid(core_fb_valid),
        .fb_arrival(core_fb_arrival),
        .servo_fault_mask(core_servo_mask),
        .fb_age_max(core_age_max),
        .fb_seq(core_fb_seq),
        .last_servo_err(core_servo_err),
        .last_servo_err_id(core_servo_err_id)
    );

endmodule
