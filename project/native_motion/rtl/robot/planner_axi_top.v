// ============================================================================
// Block Name : planner_axi_top
// Description: AXI4-Lite control/status of the Phase 3 S2 joint-space planner
//              (development ABI 0x0000_3201, proposed BD window 0x43C4_0000 /
//              4 KiB) plus the SOURCE_SELECT register of motion_sample_mux.
//              Register map: docs/PHASE3_S2_PLANNER_REGISTER_MAP_CN.md and
//              ps/robot/planner_axi_driver.py.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: S_AXI_ACLK only (100 MHz); no CDC.
//
// Configuration model (same as the S1 arm backend): move parameters are
// write-only and write-locked while the planner is busy (VALIDATE, RUN,
// PAUSED) -> SLVERR + CONFIG_LOCKED.  START validates and uses them in place;
// no shadow copy.  Per-channel START/TARGET/VMAX/AMAX live in one 32 x 32
// LUTRAM read by the core one word at a time.
//
// Command legality (one CONTROL bit per write, else SLVERR):
//   START  IDLE/DONE, no planner sample pending (else COMMAND_CONFLICT);
//          SOURCE_SELECT = planner and no S1 sample waiting behind the mux
//          (else SOURCE_CONFLICT)
//   PAUSE  RUN;  RESUME PAUSED;  CLEAR not in VALIDATE/RUN (clears the sticky
//   errors and DONE);  ESTOP always.
// SOURCE_SELECT (compatibility layer; the S1 trajectory has no continuity
// check of its own, so a switch must not make the commanded position jump).
// Writing the current value is a no-op.  Otherwise SLVERR + SOURCE_CONFLICT
// unless:
//   S1 -> planner: no committed or active S1 segment and no buffered sample;
//   planner -> S1: planner not busy, no buffered sample, and no S1
//                  sample waiting if the planner has moved since it was
//                  selected (that S1 segment was committed for an old
//                  position; it stays blocked until a PL reset, see
//                  KNOWN_ISSUES).
//
// Timing plan (100 MHz): writes take a decode cycle (address class,
// reserved bits, lock state registered) and an execute cycle; reads register
// the address decode and return data one cycle later.
//
// Truth boundary: source candidate.  Supplementary Icarus Verilog run only;
// Board not run; consult the exact S2 build report for PC verification.
// ============================================================================

`timescale 1ns / 1ps

module planner_axi_top #(
    parameter integer SMOOTH_PROFILE=0,
    parameter integer C_S_AXI_DATA_WIDTH = 32,
    parameter integer C_S_AXI_ADDR_WIDTH = 12,
    parameter integer MIN_PERIOD_CYCLES  = 512,
    parameter [31:0]  ABI_VERSION        = 32'h0000_3201
) (
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


    input wire native_valid,
    output wire native_ready,
    input wire [2:0] native_code,
    input wire [191:0] native_target, native_vmax, native_amax,
    input wire [15:0] native_n, native_na,
    input wire native_profile,
    input wire [31:0] native_period, native_stall,
    output reg native_done, native_ok,
    output wire [31:0] native_status, native_error, native_index,
    output wire                          irq,

    // Planner sample stream (to motion_sample_mux).
    output wire                          m_sample_valid,
    input  wire                          m_sample_ready,
    output wire [191:0]                  m_sample_data,

    // Mux control and observation.
    output reg                           source_sel,          // 1 = planner
    input  wire                          traj_sample_valid,
    input  wire                          traj_segment_open,
    input  wire                          traj_segment_busy,
    input  wire                          downstream_pending,
    input  wire                          plan_delivered,
    input  wire [191:0]                  last_delivered,
    input  wire                          last_valid
);

    localparam [1:0] AXI_RESP_OKAY   = 2'b00;
    localparam [1:0] AXI_RESP_SLVERR = 2'b10;

    localparam [11:0] REG_CONTROL       = 12'h000;
    localparam [11:0] REG_STATUS        = 12'h004;
    localparam [11:0] REG_ERROR_STATUS  = 12'h008;
    localparam [11:0] REG_ABI_VERSION   = 12'h00c;
    localparam [11:0] REG_CAPABILITIES  = 12'h010;
    localparam [11:0] REG_IRQ_ENABLE    = 12'h014;
    localparam [11:0] REG_SOURCE_SELECT = 12'h018;
    localparam [11:0] REG_SAMPLE_INDEX  = 12'h01c;
    localparam [11:0] REG_LATE_COUNT    = 12'h020;
    localparam [11:0] REG_N_SAMPLES     = 12'h040;
    localparam [11:0] REG_ACCEL_SAMPLES = 12'h044;
    localparam [11:0] REG_PROFILE       = 12'h048;
    localparam [11:0] REG_PERIOD        = 12'h04c;
    localparam [11:0] REG_STALL_TIMEOUT = 12'h050;

    // ERROR_STATUS bit numbers (planner_p2p_reference.PlannerError).
    localparam integer E_CONFIG_LOCKED = 6;
    localparam integer E_COMMAND       = 7;
    localparam integer E_SOURCE        = 8;
    localparam integer E_AXI_ACCESS    = 9;
    localparam [9:0]   FATAL_MASK      = 10'b00_0011_1111;

    localparam [2:0] S_IDLE     = 3'd0;
    localparam [2:0] S_VALIDATE = 3'd1;
    localparam [2:0] S_RUN      = 3'd2;
    localparam [2:0] S_PAUSED   = 3'd3;
    localparam [2:0] S_DONE     = 3'd4;

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
    reg                          wdec_valid;
    reg                          rd_pending;
    reg [11:0]                   araddr_r;
    reg                          rd_ok;
    reg [3:0]                    rd_sel;

    wire aw_accept    = S_AXI_AWVALID && S_AXI_AWREADY;
    wire w_accept     = S_AXI_WVALID && S_AXI_WREADY;
    wire ar_accept    = S_AXI_ARVALID && S_AXI_ARREADY;
    wire write_decode = aw_pending && w_pending && !axi_bvalid && !wdec_valid;
    wire write_commit = wdec_valid;

    assign S_AXI_AWREADY = !aw_pending && !axi_bvalid;
    assign S_AXI_WREADY  = !w_pending && !axi_bvalid;
    assign S_AXI_BRESP   = axi_bresp;
    assign S_AXI_BVALID  = axi_bvalid;
    assign S_AXI_ARREADY = !axi_rvalid && !rd_pending;
    assign S_AXI_RDATA   = axi_rdata;
    assign S_AXI_RRESP   = axi_rresp;
    assign S_AXI_RVALID  = axi_rvalid;

    // ------------------------------------------------------ registers
    reg  [15:0] n_samples;
    reg  [15:0] accel_samples;
    reg         profile;
    reg  [31:0] period_cycles;
    reg  [31:0] stall_timeout;
    reg  [1:0]  irq_enable;
    reg  [9:0]  error_status;
    reg  [2:0]  error_channel;
    reg         done_sticky;
    reg  [15:0] late_count;
    reg         plan_moved;       // planner sample accepted since SOURCE = planner

    reg         cmd_start, cmd_pause, cmd_resume, cmd_estop, cmd_clear;
    reg native_loading;
    reg [4:0] native_word;
    reg [191:0] native_target_r, native_vmax_r, native_amax_r, native_start_r;
    wire native_accept = native_valid && native_ready;
    assign native_ready = !native_loading && !aw_pending && !w_pending && !wdec_valid && !axi_bvalid && !S_AXI_AWVALID && !S_AXI_WVALID;


    (* ram_style = "distributed" *) reg [31:0] param_mem [0:31];   // {field, ch}

    wire [2:0]  core_state;
    wire        core_computing;
    wire [15:0] core_sample_index;
    wire        core_err_pulse;
    wire [2:0]  core_err_code;
    wire [2:0]  core_err_channel;
    wire        core_done_pulse;
    wire        core_late_pulse;
    wire [2:0]  core_cfg_ch;
    wire [1:0]  core_cfg_field;
    wire        core_valid;

    wire core_busy = (core_state == S_VALIDATE) || (core_state == S_RUN) || (core_state == S_PAUSED);
    wire fatal     = |(error_status & FATAL_MASK);
    assign irq     = (irq_enable[0] && done_sticky) || (irq_enable[1] && fatal);

    integer init_i;
    initial begin
        for (init_i = 0; init_i < 32; init_i = init_i + 1)
            param_mem[init_i] = 32'd0;
    end

    // ------------------------------------------------------ write decode
    wire [11:0] waddr = awaddr_hold[11:0];
    wire [2:0]  wch   = waddr[7:5];
    wire [1:0]  wfld  = waddr[3:2];
    wire        wfull_d    = (awaddr_hold[1:0] == 2'b00) &&
                             (wstrb_hold == {(C_S_AXI_DATA_WIDTH/8){1'b1}});
    wire        w_is_chan_d   = (waddr[11:8] == 4'h1) && (wch < 3'd6) && (waddr[4] == 1'b0);
    wire        w_is_scalar_d = (waddr >= REG_N_SAMPLES) && (waddr <= REG_STALL_TIMEOUT);

    function automatic multiple_bits;
        input [4:0] bits;
        begin
            multiple_bits = (bits[0] + bits[1] + bits[2] + bits[3] + bits[4]) > 3'd1;
        end
    endfunction

    reg wfull, w_is_chan, w_is_scalar, unlocked;
    reg ctrl_rsvd, one_bit_rsvd, two_bit_rsvd, half_rsvd;

    wire param_we = write_commit && wfull && w_is_chan && unlocked && !native_loading;

    always @(posedge S_AXI_ACLK) begin
        if (native_loading && native_word <= 5'd29) begin
            case (native_word[4:3])
                2'd0: param_mem[{2'd0,native_word[2:0]}] <= native_start_r[native_word[2:0]*32 +: 32];
                2'd1: param_mem[{2'd1,native_word[2:0]}] <= native_target_r[native_word[2:0]*32 +: 32];
                2'd2: param_mem[{2'd2,native_word[2:0]}] <= native_vmax_r[native_word[2:0]*32 +: 32];
                default: param_mem[{2'd3,native_word[2:0]}] <= native_amax_r[native_word[2:0]*32 +: 32];
            endcase
        end else if (param_we)
            param_mem[{wfld, wch}] <= wdata_hold;
    end

    // ------------------------------------------------------ core
    wire [191:0] core_data;

    planner_p2p_core #(.SMOOTH_PROFILE(SMOOTH_PROFILE),
        .MIN_PERIOD_CYCLES(MIN_PERIOD_CYCLES)
    ) u_core (
        .clk(S_AXI_ACLK),
        .rst_n(S_AXI_ARESETN),
        .cmd_start(cmd_start),
        .cmd_pause(cmd_pause),
        .cmd_resume(cmd_resume),
        .cmd_estop(cmd_estop),
        .cmd_clear(cmd_clear),
        .cfg_n_samples(n_samples),
        .cfg_accel_samples(accel_samples),
        .cfg_profile(profile),
        .cfg_period_cycles(period_cycles),
        .cfg_stall_timeout(stall_timeout),
        .cfg_ch(core_cfg_ch),
        .cfg_field(core_cfg_field),
        .cfg_data(param_mem[{core_cfg_field, core_cfg_ch}]),
        .last_delivered(last_delivered),
        .last_valid(last_valid),
        .m_valid(core_valid),
        .m_ready(m_sample_ready),
        .m_data(core_data),
        .state(core_state),
        .computing(core_computing),
        .sample_index(core_sample_index),
        .err_pulse(core_err_pulse),
        .err_code(core_err_code),
        .err_channel(core_err_channel),
        .done_pulse(core_done_pulse),
        .late_pulse(core_late_pulse)
    );

    assign m_sample_valid = core_valid;
    assign m_sample_data  = core_data;

    // ------------------------------------------------------ write/commands
    always @(posedge S_AXI_ACLK) begin
        if (!S_AXI_ARESETN) begin
            awaddr_hold   <= {C_S_AXI_ADDR_WIDTH{1'b0}};
            aw_pending    <= 1'b0;
            wdata_hold    <= {C_S_AXI_DATA_WIDTH{1'b0}};
            wstrb_hold    <= {(C_S_AXI_DATA_WIDTH/8){1'b0}};
            w_pending     <= 1'b0;
            wdec_valid    <= 1'b0;
            wfull         <= 1'b0;
            w_is_chan     <= 1'b0;
            w_is_scalar   <= 1'b0;
            unlocked      <= 1'b0;
            ctrl_rsvd     <= 1'b0;
            one_bit_rsvd  <= 1'b0;
            two_bit_rsvd  <= 1'b0;
            half_rsvd     <= 1'b0;
            axi_bresp     <= AXI_RESP_OKAY;
            axi_bvalid    <= 1'b0;
            n_samples     <= 16'd0;
            accel_samples <= 16'd0;
            profile       <= 1'b0;
            period_cycles <= 32'd0;
            stall_timeout <= 32'd0;
            irq_enable    <= 2'd0;
            source_sel    <= 1'b1;                 // S1 trajectory: S1 behaviour
            error_status  <= 10'd0;
            error_channel <= 3'd0;
            done_sticky   <= 1'b0;
            late_count    <= 16'd0;
            plan_moved    <= 1'b0;
            cmd_start     <= 1'b0;
            cmd_pause     <= 1'b0;
            cmd_resume    <= 1'b0;
            cmd_estop     <= 1'b0;
            cmd_clear     <= 1'b0;
            native_loading<=0; native_word<=0; native_done<=0; native_ok<=0;
        end else begin
            cmd_start  <= 1'b0;
            cmd_pause  <= 1'b0;
            cmd_resume <= 1'b0;
            cmd_estop  <= 1'b0;
            cmd_clear  <= 1'b0;
            native_done <= 1'b0;
            if (native_loading) begin
                if (native_word == 5'd29) begin
                    native_loading <= 1'b0;
                    cmd_start <= 1'b1;
                    done_sticky <= 1'b0;
                    late_count <= 16'd0;
                    native_done <= 1'b1; native_ok <= 1'b1;
                end else if (native_word[2:0] == 3'd5) native_word <= native_word + 5'd3;
                else native_word <= native_word + 5'd1;
            end else if (native_accept) begin
                native_done <= 1'b1; native_ok <= 1'b1;
                case (native_code)
                    3'd1: begin
                        if (((core_state != S_IDLE) && (core_state != S_DONE)) || core_valid || downstream_pending || fatal) begin
                            native_ok<=0; error_status[E_COMMAND]<=1;
                        end else begin
                            native_done<=0; native_loading<=1; native_word<=0;
                            native_start_r<=last_delivered; native_target_r<=native_target;
                            native_vmax_r<=native_vmax; native_amax_r<=native_amax;
                            n_samples<=native_n; accel_samples<=native_na; profile<=native_profile;
                            period_cycles<=native_period; stall_timeout<=native_stall;
                        end
                    end
                    3'd2: if (core_state == S_RUN) cmd_pause<=1; else begin native_ok<=0; error_status[E_COMMAND]<=1; end
                    3'd3: if (core_state == S_PAUSED && !fatal) cmd_resume<=1; else begin native_ok<=0; error_status[E_COMMAND]<=1; end
                    3'd4: if (core_state != S_RUN && core_state != S_VALIDATE && !downstream_pending && !core_valid) begin
                        cmd_clear<=1; error_status<=core_err_pulse ? (10'd1 << core_err_code) : 10'd0; error_channel<=0; done_sticky<=0;
                    end else begin native_ok<=0; error_status[E_COMMAND]<=1; end
                    3'd5: cmd_estop<=1;
                    3'd6: if (core_busy || core_valid || downstream_pending) native_ok<=0; // ownership fence; no source switch
                    default: native_ok<=0;
                endcase
            end

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
                wdec_valid   <= 1'b1;
                wfull        <= wfull_d;
                w_is_chan    <= w_is_chan_d;
                w_is_scalar  <= w_is_scalar_d;
                unlocked     <= !core_busy && !native_loading;        // only an AXI START can lock it
                ctrl_rsvd    <= (wdata_hold[31:5] != 27'd0) || multiple_bits(wdata_hold[4:0]);
                one_bit_rsvd <= (wdata_hold[31:1] != 31'd0);
                two_bit_rsvd <= (wdata_hold[31:2] != 30'd0);
                half_rsvd    <= (wdata_hold[31:16] != 16'd0);
            end

            // -------------------------------------------- core events
            if (core_err_pulse) begin
                error_status[core_err_code] <= 1'b1;
                error_channel               <= core_err_channel;
            end
            if (core_done_pulse)
                done_sticky <= 1'b1;
            if (core_late_pulse && (late_count != 16'hffff))
                late_count <= late_count + 16'd1;
            if (rd_pending && !rd_ok)
                error_status[E_AXI_ACCESS] <= 1'b1;
            if (plan_delivered)
                plan_moved <= 1'b1;

            // -------------------------------------------- AXI writes
            if (write_commit) begin
                wdec_valid <= 1'b0;
                aw_pending <= 1'b0;
                w_pending  <= 1'b0;
                axi_bvalid <= 1'b1;
                axi_bresp  <= AXI_RESP_OKAY;

                if (!wfull) begin
                    axi_bresp                  <= AXI_RESP_SLVERR;
                    error_status[E_AXI_ACCESS] <= 1'b1;
                end else if (w_is_chan || w_is_scalar) begin
                    if (!unlocked) begin
                        axi_bresp                     <= AXI_RESP_SLVERR;
                        error_status[E_CONFIG_LOCKED] <= 1'b1;
                    end else if (w_is_scalar) begin
                        case (waddr)
                            REG_N_SAMPLES: begin
                                if (half_rsvd) begin
                                    axi_bresp                  <= AXI_RESP_SLVERR;
                                    error_status[E_AXI_ACCESS] <= 1'b1;
                                end else begin
                                    n_samples <= wdata_hold[15:0];
                                end
                            end
                            REG_ACCEL_SAMPLES: begin
                                if (half_rsvd) begin
                                    axi_bresp                  <= AXI_RESP_SLVERR;
                                    error_status[E_AXI_ACCESS] <= 1'b1;
                                end else begin
                                    accel_samples <= wdata_hold[15:0];
                                end
                            end
                            REG_PROFILE: begin
                                if (one_bit_rsvd) begin
                                    axi_bresp                  <= AXI_RESP_SLVERR;
                                    error_status[E_AXI_ACCESS] <= 1'b1;
                                end else begin
                                    profile <= wdata_hold[0];
                                end
                            end
                            REG_PERIOD:        period_cycles <= wdata_hold;
                            REG_STALL_TIMEOUT: stall_timeout <= wdata_hold;
                            default: begin
                                axi_bresp                  <= AXI_RESP_SLVERR;
                                error_status[E_AXI_ACCESS] <= 1'b1;
                            end
                        endcase
                    end
                end else begin
                    case (waddr)
                        REG_CONTROL: begin
                            if (ctrl_rsvd || (wdata_hold[4:0] == 5'd0)) begin
                                axi_bresp               <= AXI_RESP_SLVERR;
                                error_status[E_COMMAND] <= 1'b1;
                            end else if (wdata_hold[3]) begin
                                cmd_estop <= 1'b1;                        // always legal
                            end else if (wdata_hold[0]) begin
                                if (!source_sel || traj_sample_valid || traj_segment_busy || downstream_pending) begin
                                    axi_bresp              <= AXI_RESP_SLVERR;
                                    error_status[E_SOURCE] <= 1'b1;
                                end else if (((core_state != S_IDLE) && (core_state != S_DONE)) ||
                                             core_valid || downstream_pending) begin
                                    axi_bresp               <= AXI_RESP_SLVERR;
                                    error_status[E_COMMAND] <= 1'b1;
                                end else begin
                                    cmd_start   <= 1'b1;
                                    done_sticky <= 1'b0;
                                    late_count  <= 16'd0;
                                end
                            end else if (wdata_hold[1]) begin
                                if (core_state != S_RUN) begin
                                    axi_bresp               <= AXI_RESP_SLVERR;
                                    error_status[E_COMMAND] <= 1'b1;
                                end else begin
                                    cmd_pause <= 1'b1;
                                end
                            end else if (wdata_hold[2]) begin
                                if (core_state != S_PAUSED) begin
                                    axi_bresp               <= AXI_RESP_SLVERR;
                                    error_status[E_COMMAND] <= 1'b1;
                                end else begin
                                    cmd_resume <= 1'b1;
                                end
                            end else begin                                // CLEAR
                                if ((core_state == S_VALIDATE) || (core_state == S_RUN)) begin
                                    axi_bresp               <= AXI_RESP_SLVERR;
                                    error_status[E_COMMAND] <= 1'b1;
                                end else begin
                                    cmd_clear     <= 1'b1;
                                    error_status  <= core_err_pulse ? (10'd1 << core_err_code) : 10'd0;
                                    error_channel <= 3'd0;
                                    done_sticky   <= 1'b0;
                                end
                            end
                        end

                        REG_SOURCE_SELECT: begin
                            if (one_bit_rsvd) begin
                                axi_bresp                  <= AXI_RESP_SLVERR;
                                error_status[E_AXI_ACCESS] <= 1'b1;
                            end else if (wdata_hold[0] == source_sel) begin
                                // no change
                            end else if (wdata_hold[0] ? (traj_sample_valid || traj_segment_open || traj_segment_busy || downstream_pending)
                                                       : (core_busy || core_valid || downstream_pending ||
                                                          (traj_segment_busy && plan_moved))) begin
                                axi_bresp              <= AXI_RESP_SLVERR;
                                error_status[E_SOURCE] <= 1'b1;
                            end else begin
                                source_sel <= 1'b1;
                                plan_moved <= 1'b0;
                            end
                        end

                        REG_IRQ_ENABLE: begin
                            if (two_bit_rsvd) begin
                                axi_bresp                  <= AXI_RESP_SLVERR;
                                error_status[E_AXI_ACCESS] <= 1'b1;
                            end else begin
                                irq_enable <= wdata_hold[1:0];
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

    // ------------------------------------------------------ reads
    localparam [3:0] RD_ZERO = 4'd0, RD_STATUS = 4'd1, RD_ERROR = 4'd2, RD_ABI = 4'd3,
                     RD_CAPS = 4'd4, RD_IRQ = 4'd5, RD_SOURCE = 4'd6, RD_INDEX = 4'd7,
                     RD_LATE = 4'd8, RD_LAST = 4'd9;

    function automatic read_address_valid;
        input [11:0] addr;
        begin
            if (addr[1:0] != 2'b00)
                read_address_valid = 1'b0;
            else if (addr <= REG_LATE_COUNT)
                read_address_valid = 1'b1;
            else if ((addr >= REG_N_SAMPLES) && (addr <= REG_STALL_TIMEOUT))
                read_address_valid = 1'b1;
            else if ((addr[11:8] == 4'h1) && (addr[7:5] < 3'd6) && (addr[4] == 1'b0))
                read_address_valid = 1'b1;
            else if ((addr >= 12'h200) && (addr <= 12'h214))
                read_address_valid = 1'b1;
            else
                read_address_valid = 1'b0;
        end
    endfunction

    function automatic [3:0] read_select;
        input [11:0] addr;
        begin
            if ((addr >= 12'h200) && (addr <= 12'h214))
                read_select = RD_LAST;
            else begin
                case (addr)
                    REG_STATUS:        read_select = RD_STATUS;
                    REG_ERROR_STATUS:  read_select = RD_ERROR;
                    REG_ABI_VERSION:   read_select = RD_ABI;
                    REG_CAPABILITIES:  read_select = RD_CAPS;
                    REG_IRQ_ENABLE:    read_select = RD_IRQ;
                    REG_SOURCE_SELECT: read_select = RD_SOURCE;
                    REG_SAMPLE_INDEX:  read_select = RD_INDEX;
                    REG_LATE_COUNT:    read_select = RD_LATE;
                    default:           read_select = RD_ZERO;   // CONTROL, write-only config
                endcase
            end
        end
    endfunction

    wire [31:0] status_word = {13'd0, error_channel, 3'd0, plan_moved, traj_segment_open, irq, done_sticky,
                               source_sel, last_valid,
                               (traj_sample_valid || (downstream_pending && !source_sel)),
                               (core_valid || (downstream_pending && source_sel)), core_computing,
                               (core_busy || native_loading), core_state};
    assign native_status=status_word;
    assign native_error={22'd0,error_status};
    assign native_index={16'd0,core_sample_index};
    localparam [15:0] MIN_PERIOD_16 = MIN_PERIOD_CYCLES;
    // [3:0] channels, [5:4] profiles (LINEAR, TRAPEZOID), [15:8] N bits, [31:16] MIN_PERIOD_CYCLES
    wire [31:0] capabilities_word = {MIN_PERIOD_16, 8'd16, 2'b00, 2'b11, 4'd6};
    wire [2:0]  last_ch = (araddr_r[4:2] < 3'd6) ? araddr_r[4:2] : 3'd0;

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
            axi_rresp  <= rd_ok ? AXI_RESP_OKAY : AXI_RESP_SLVERR;
            case (rd_sel)
                RD_STATUS: axi_rdata <= status_word;
                RD_ERROR:  axi_rdata <= {22'd0, error_status};
                RD_ABI:    axi_rdata <= ABI_VERSION;
                RD_CAPS:   axi_rdata <= capabilities_word;
                RD_IRQ:    axi_rdata <= {30'd0, irq_enable};
                RD_SOURCE: axi_rdata <= {31'd0, source_sel};
                RD_INDEX:  axi_rdata <= {16'd0, core_sample_index};
                RD_LATE:   axi_rdata <= {16'd0, late_count};
                RD_LAST:   axi_rdata <= last_delivered[last_ch * 32 +: 32];
                default:   axi_rdata <= 32'd0;
            endcase
        end else if (ar_accept) begin
            rd_pending <= 1'b1;
            araddr_r   <= S_AXI_ARADDR[11:0];
            rd_ok      <= read_address_valid(S_AXI_ARADDR[11:0]);
            rd_sel     <= read_select(S_AXI_ARADDR[11:0]);
        end else if (axi_rvalid && S_AXI_RREADY) begin
            axi_rvalid <= 1'b0;
        end
    end

endmodule
