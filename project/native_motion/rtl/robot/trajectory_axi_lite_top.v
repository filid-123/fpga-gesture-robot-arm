// ============================================================================
// Block Name : trajectory_axi_lite_top
// Description: AXI4-Lite development control/status wrapper around the
//              verified Phase 3 trajectory_stream_scheduler.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: S_AXI_ACLK only
//
// Control model:
// - PS writes start/target/period shadow registers.
// - CONTROL.COMMIT atomically submits the complete shadow command.
// - The scheduler exposes one stable six-axis sample until CONTROL.SAMPLE_POP.
// - Shadow registers remain writable while a segment is active; active data is
//   protected because the scheduler latches the full command on COMMIT.
//
// Truth boundary:
// - This module has no assigned SoC base address and is not yet in the Vivado BD.
// - The register ABI is a development contract, not the final UART/servo ABI.
// - All AXI and trajectory logic use one clock; no CDC is implemented here.
//
// S1 extension (EXTERNAL_SAMPLE_SINK, default 0 = unchanged ABI 0x0000_3001):
// - EXTERNAL_SAMPLE_SINK=1 hands the scheduler's sample stream to a PL
//   consumer (arm_backend_core) through ext_sample_*.  The instantiating top
//   must then pass ABI_VERSION 0x0000_3002.  The SAMPLE window stays readable
//   as a monitor; CONTROL.SAMPLE_POP returns SLVERR and sets the
//   control-conflict sticky bit, so the PS can never steal a sample.
// - With the default 0 the ext_sample_* outputs are tied low/zero and the
//   scheduler is driven exactly as before.
// ============================================================================

`timescale 1ns / 1ps

module trajectory_axi_lite_top #(
    parameter integer C_S_AXI_DATA_WIDTH = 32,
    parameter integer C_S_AXI_ADDR_WIDTH = 8,
    parameter [31:0]  MIN_PERIOD_CYCLES  = 32'd256,
    parameter [31:0]  ABI_VERSION        = 32'h0000_3001,
    parameter integer EXTERNAL_SAMPLE_SINK = 0
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

    output wire                          irq,

    // PL sample sink (used only when EXTERNAL_SAMPLE_SINK=1).
    output wire                          ext_sample_valid,
    input  wire                          ext_sample_ready,
    output wire [191:0]                  ext_sample_data,
    output wire [5:0]                    ext_sample_index,
    output wire                          ext_sample_last
);

    localparam [1:0] AXI_RESP_OKAY   = 2'b00;
    localparam [1:0] AXI_RESP_SLVERR = 2'b10;

    localparam [7:0] REG_CONTROL       = 8'h00;
    localparam [7:0] REG_STATUS        = 8'h04;
    localparam [7:0] REG_ERROR_STATUS  = 8'h08;
    localparam [7:0] REG_ABI_VERSION   = 8'h0c;
    localparam [7:0] REG_IRQ_ENABLE    = 8'h10;
    localparam [7:0] REG_PERIOD        = 8'h14;
    localparam [7:0] REG_MIN_PERIOD    = 8'h18;

    localparam [7:0] REG_START_CH0     = 8'h20;
    localparam [7:0] REG_START_CH1     = 8'h24;
    localparam [7:0] REG_START_CH2     = 8'h28;
    localparam [7:0] REG_START_CH3     = 8'h2c;
    localparam [7:0] REG_START_CH4     = 8'h30;
    localparam [7:0] REG_START_CH5     = 8'h34;

    localparam [7:0] REG_TARGET_CH0    = 8'h40;
    localparam [7:0] REG_TARGET_CH1    = 8'h44;
    localparam [7:0] REG_TARGET_CH2    = 8'h48;
    localparam [7:0] REG_TARGET_CH3    = 8'h4c;
    localparam [7:0] REG_TARGET_CH4    = 8'h50;
    localparam [7:0] REG_TARGET_CH5    = 8'h54;

    localparam [7:0] REG_SAMPLE_CH0    = 8'h60;
    localparam [7:0] REG_SAMPLE_CH1    = 8'h64;
    localparam [7:0] REG_SAMPLE_CH2    = 8'h68;
    localparam [7:0] REG_SAMPLE_CH3    = 8'h6c;
    localparam [7:0] REG_SAMPLE_CH4    = 8'h70;
    localparam [7:0] REG_SAMPLE_CH5    = 8'h74;
    localparam [7:0] REG_SAMPLE_META   = 8'h78;

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

    reg [31:0] start_shadow_ch0;
    reg [31:0] start_shadow_ch1;
    reg [31:0] start_shadow_ch2;
    reg [31:0] start_shadow_ch3;
    reg [31:0] start_shadow_ch4;
    reg [31:0] start_shadow_ch5;
    reg [31:0] target_shadow_ch0;
    reg [31:0] target_shadow_ch1;
    reg [31:0] target_shadow_ch2;
    reg [31:0] target_shadow_ch3;
    reg [31:0] target_shadow_ch4;
    reg [31:0] target_shadow_ch5;
    reg [31:0] period_shadow;
    reg [1:0]  irq_enable;

    reg done_sticky;
    reg error_commit_busy;
    reg error_pop_empty;
    reg error_access;
    reg error_command_conflict;
    reg error_commit_invalid_period;

    reg scheduler_cmd_valid;
    reg scheduler_sample_ready;

    wire scheduler_cmd_ready;
    wire scheduler_busy;
    wire scheduler_sample_valid;
    wire [191:0] scheduler_sample_data;
    wire [5:0] scheduler_sample_index;
    wire scheduler_sample_last;
    wire scheduler_segment_done;
    wire error_invalid_period;
    wire error_fill_protocol;
    wire error_deadline_miss;
    wire error_core;

    wire ext_sink = (EXTERNAL_SAMPLE_SINK != 0);
    wire scheduler_ready_mux = ext_sink ? ext_sample_ready : scheduler_sample_ready;

    assign ext_sample_valid = ext_sink ? scheduler_sample_valid : 1'b0;
    assign ext_sample_data  = ext_sink ? scheduler_sample_data  : 192'd0;
    assign ext_sample_index = ext_sink ? scheduler_sample_index : 6'd0;
    assign ext_sample_last  = ext_sink ? scheduler_sample_last  : 1'b0;

    wire [191:0] command_start_data = {
        start_shadow_ch5, start_shadow_ch4, start_shadow_ch3,
        start_shadow_ch2, start_shadow_ch1, start_shadow_ch0
    };
    wire [191:0] command_target_data = {
        target_shadow_ch5, target_shadow_ch4, target_shadow_ch3,
        target_shadow_ch2, target_shadow_ch1, target_shadow_ch0
    };

    wire error_any =
        error_invalid_period || error_fill_protocol || error_deadline_miss ||
        error_core || error_commit_busy || error_pop_empty || error_access ||
        error_command_conflict || error_commit_invalid_period;

    wire aw_accept = S_AXI_AWVALID && S_AXI_AWREADY;
    wire w_accept  = S_AXI_WVALID  && S_AXI_WREADY;
    wire ar_accept = S_AXI_ARVALID && S_AXI_ARREADY;
    wire write_commit = aw_pending && w_pending && !axi_bvalid;

    assign S_AXI_AWREADY = !aw_pending && !axi_bvalid;
    assign S_AXI_WREADY  = !w_pending  && !axi_bvalid;
    assign S_AXI_BRESP   = axi_bresp;
    assign S_AXI_BVALID  = axi_bvalid;
    assign S_AXI_ARREADY = !axi_rvalid;
    assign S_AXI_RDATA   = axi_rdata;
    assign S_AXI_RRESP   = axi_rresp;
    assign S_AXI_RVALID  = axi_rvalid;

    assign irq = (irq_enable[0] && done_sticky) ||
                 (irq_enable[1] && error_any);

    function automatic is_read_address;
        input [C_S_AXI_ADDR_WIDTH-1:0] addr;
        begin
            case (addr[7:0])
                REG_CONTROL,
                REG_STATUS,
                REG_ERROR_STATUS,
                REG_ABI_VERSION,
                REG_IRQ_ENABLE,
                REG_PERIOD,
                REG_MIN_PERIOD,
                REG_START_CH0,
                REG_START_CH1,
                REG_START_CH2,
                REG_START_CH3,
                REG_START_CH4,
                REG_START_CH5,
                REG_TARGET_CH0,
                REG_TARGET_CH1,
                REG_TARGET_CH2,
                REG_TARGET_CH3,
                REG_TARGET_CH4,
                REG_TARGET_CH5,
                REG_SAMPLE_CH0,
                REG_SAMPLE_CH1,
                REG_SAMPLE_CH2,
                REG_SAMPLE_CH3,
                REG_SAMPLE_CH4,
                REG_SAMPLE_CH5,
                REG_SAMPLE_META: is_read_address = 1'b1;
                default:         is_read_address = 1'b0;
            endcase
        end
    endfunction

    function automatic multiple_control_commands;
        input [2:0] command_bits;
        begin
            multiple_control_commands =
                (command_bits[0] && command_bits[1]) ||
                (command_bits[0] && command_bits[2]) ||
                (command_bits[1] && command_bits[2]);
        end
    endfunction

    trajectory_stream_scheduler #(
        .MIN_PERIOD_CYCLES(MIN_PERIOD_CYCLES)
    ) u_scheduler (
        .clk(S_AXI_ACLK),
        .rst_n(S_AXI_ARESETN),
        .cmd_valid(scheduler_cmd_valid),
        .cmd_ready(scheduler_cmd_ready),
        .cmd_start_data(command_start_data),
        .cmd_target_data(command_target_data),
        .cmd_period_cycles(period_shadow),
        .busy(scheduler_busy),
        .sample_valid(scheduler_sample_valid),
        .sample_ready(scheduler_ready_mux),
        .sample_data(scheduler_sample_data),
        .sample_index(scheduler_sample_index),
        .sample_last(scheduler_sample_last),
        .segment_done(scheduler_segment_done),
        .error_invalid_period(error_invalid_period),
        .error_fill_protocol(error_fill_protocol),
        .error_deadline_miss(error_deadline_miss),
        .error_core(error_core)
    );

    // AXI write-channel skid registers and register write side effects.
    // AW and W may arrive independently and are paired exactly once.
    always @(posedge S_AXI_ACLK) begin
        if (!S_AXI_ARESETN) begin
            awaddr_hold                <= {C_S_AXI_ADDR_WIDTH{1'b0}};
            aw_pending                 <= 1'b0;
            wdata_hold                 <= {C_S_AXI_DATA_WIDTH{1'b0}};
            wstrb_hold                 <= {(C_S_AXI_DATA_WIDTH/8){1'b0}};
            w_pending                  <= 1'b0;
            axi_bresp                  <= AXI_RESP_OKAY;
            axi_bvalid                 <= 1'b0;
            start_shadow_ch0           <= 32'd0;
            start_shadow_ch1           <= 32'd0;
            start_shadow_ch2           <= 32'd0;
            start_shadow_ch3           <= 32'd0;
            start_shadow_ch4           <= 32'd0;
            start_shadow_ch5           <= 32'd0;
            target_shadow_ch0          <= 32'd0;
            target_shadow_ch1          <= 32'd0;
            target_shadow_ch2          <= 32'd0;
            target_shadow_ch3          <= 32'd0;
            target_shadow_ch4          <= 32'd0;
            target_shadow_ch5          <= 32'd0;
            period_shadow              <= MIN_PERIOD_CYCLES;
            irq_enable                 <= 2'b00;
            done_sticky                <= 1'b0;
            error_commit_busy          <= 1'b0;
            error_pop_empty            <= 1'b0;
            error_access               <= 1'b0;
            error_command_conflict     <= 1'b0;
            error_commit_invalid_period <= 1'b0;
            scheduler_cmd_valid        <= 1'b0;
            scheduler_sample_ready     <= 1'b0;
        end else begin
            scheduler_cmd_valid    <= 1'b0;
            scheduler_sample_ready <= 1'b0;

            if (aw_accept) begin
                awaddr_hold <= S_AXI_AWADDR;
                aw_pending  <= 1'b1;
            end

            if (w_accept) begin
                wdata_hold <= S_AXI_WDATA;
                wstrb_hold <= S_AXI_WSTRB;
                w_pending  <= 1'b1;
            end

            // Invalid read addresses also leave a persistent diagnostic bit.
            if (ar_accept && ((S_AXI_ARADDR[1:0] != 2'b00) ||
                              !is_read_address(S_AXI_ARADDR)))
                error_access <= 1'b1;

            if (write_commit) begin
                aw_pending <= 1'b0;
                w_pending  <= 1'b0;
                axi_bvalid <= 1'b1;
                axi_bresp  <= AXI_RESP_OKAY;

                if ((awaddr_hold[1:0] != 2'b00) ||
                    (wstrb_hold != {(C_S_AXI_DATA_WIDTH/8){1'b1}})) begin
                    axi_bresp    <= AXI_RESP_SLVERR;
                    error_access <= 1'b1;
                end else begin
                    case (awaddr_hold[7:0])
                        REG_CONTROL: begin
                            if ((wdata_hold[31:3] != 29'd0) ||
                                multiple_control_commands(wdata_hold[2:0])) begin
                                axi_bresp              <= AXI_RESP_SLVERR;
                                error_command_conflict <= 1'b1;
                            end else begin
                                case (wdata_hold[2:0])
                                    3'b000: begin
                                        // Explicit no-op write.
                                    end
                                    3'b001: begin
                                        if (period_shadow < MIN_PERIOD_CYCLES) begin
                                            axi_bresp <= AXI_RESP_SLVERR;
                                            error_commit_invalid_period <= 1'b1;
                                        end else if (!scheduler_cmd_ready) begin
                                            axi_bresp         <= AXI_RESP_SLVERR;
                                            error_commit_busy <= 1'b1;
                                        end else begin
                                            scheduler_cmd_valid <= 1'b1;
                                        end
                                    end
                                    3'b010: begin
                                        if (ext_sink) begin
                                            // The PL arm backend owns the stream.
                                            axi_bresp              <= AXI_RESP_SLVERR;
                                            error_command_conflict <= 1'b1;
                                        end else if (!scheduler_sample_valid) begin
                                            axi_bresp       <= AXI_RESP_SLVERR;
                                            error_pop_empty <= 1'b1;
                                        end else begin
                                            scheduler_sample_ready <= 1'b1;
                                        end
                                    end
                                    3'b100: begin
                                        done_sticky <= 1'b0;
                                    end
                                    default: begin
                                        axi_bresp              <= AXI_RESP_SLVERR;
                                        error_command_conflict <= 1'b1;
                                    end
                                endcase
                            end
                        end

                        REG_IRQ_ENABLE: begin
                            if (wdata_hold[31:2] != 30'd0) begin
                                axi_bresp    <= AXI_RESP_SLVERR;
                                error_access <= 1'b1;
                            end else begin
                                irq_enable <= wdata_hold[1:0];
                            end
                        end

                        REG_PERIOD:     period_shadow     <= wdata_hold;
                        REG_START_CH0:  start_shadow_ch0  <= wdata_hold;
                        REG_START_CH1:  start_shadow_ch1  <= wdata_hold;
                        REG_START_CH2:  start_shadow_ch2  <= wdata_hold;
                        REG_START_CH3:  start_shadow_ch3  <= wdata_hold;
                        REG_START_CH4:  start_shadow_ch4  <= wdata_hold;
                        REG_START_CH5:  start_shadow_ch5  <= wdata_hold;
                        REG_TARGET_CH0: target_shadow_ch0 <= wdata_hold;
                        REG_TARGET_CH1: target_shadow_ch1 <= wdata_hold;
                        REG_TARGET_CH2: target_shadow_ch2 <= wdata_hold;
                        REG_TARGET_CH3: target_shadow_ch3 <= wdata_hold;
                        REG_TARGET_CH4: target_shadow_ch4 <= wdata_hold;
                        REG_TARGET_CH5: target_shadow_ch5 <= wdata_hold;

                        default: begin
                            axi_bresp    <= AXI_RESP_SLVERR;
                            error_access <= 1'b1;
                        end
                    endcase
                end
            end else if (axi_bvalid && S_AXI_BREADY) begin
                axi_bvalid <= 1'b0;
            end

            // Hardware completion has priority over a simultaneous software
            // clear, preventing the final completion event from being lost.
            if (scheduler_segment_done)
                done_sticky <= 1'b1;
        end
    end

    // One outstanding read transaction. RDATA/RRESP remain stable until the
    // master accepts the response.
    always @(posedge S_AXI_ACLK) begin
        if (!S_AXI_ARESETN) begin
            axi_rdata  <= {C_S_AXI_DATA_WIDTH{1'b0}};
            axi_rresp  <= AXI_RESP_OKAY;
            axi_rvalid <= 1'b0;
        end else begin
            if (ar_accept) begin
                axi_rvalid <= 1'b1;
                axi_rresp  <= AXI_RESP_OKAY;
                axi_rdata  <= {C_S_AXI_DATA_WIDTH{1'b0}};

                if ((S_AXI_ARADDR[1:0] != 2'b00) ||
                    !is_read_address(S_AXI_ARADDR)) begin
                    axi_rresp <= AXI_RESP_SLVERR;
                end else begin
                    case (S_AXI_ARADDR[7:0])
                        REG_CONTROL:      axi_rdata <= 32'd0;
                        REG_STATUS:       axi_rdata <= {
                            18'd0,
                            scheduler_sample_index,
                            1'b0,
                            error_any,
                            irq,
                            done_sticky,
                            scheduler_sample_last,
                            scheduler_sample_valid,
                            scheduler_cmd_ready,
                            scheduler_busy
                        };
                        REG_ERROR_STATUS: axi_rdata <= {
                            23'd0,
                            error_commit_invalid_period,
                            error_command_conflict,
                            error_access,
                            error_pop_empty,
                            error_commit_busy,
                            error_core,
                            error_deadline_miss,
                            error_fill_protocol,
                            error_invalid_period
                        };
                        REG_ABI_VERSION:  axi_rdata <= ABI_VERSION;
                        REG_IRQ_ENABLE:   axi_rdata <= {30'd0, irq_enable};
                        REG_PERIOD:       axi_rdata <= period_shadow;
                        REG_MIN_PERIOD:   axi_rdata <= MIN_PERIOD_CYCLES;
                        REG_START_CH0:    axi_rdata <= start_shadow_ch0;
                        REG_START_CH1:    axi_rdata <= start_shadow_ch1;
                        REG_START_CH2:    axi_rdata <= start_shadow_ch2;
                        REG_START_CH3:    axi_rdata <= start_shadow_ch3;
                        REG_START_CH4:    axi_rdata <= start_shadow_ch4;
                        REG_START_CH5:    axi_rdata <= start_shadow_ch5;
                        REG_TARGET_CH0:   axi_rdata <= target_shadow_ch0;
                        REG_TARGET_CH1:   axi_rdata <= target_shadow_ch1;
                        REG_TARGET_CH2:   axi_rdata <= target_shadow_ch2;
                        REG_TARGET_CH3:   axi_rdata <= target_shadow_ch3;
                        REG_TARGET_CH4:   axi_rdata <= target_shadow_ch4;
                        REG_TARGET_CH5:   axi_rdata <= target_shadow_ch5;
                        REG_SAMPLE_CH0:   axi_rdata <= scheduler_sample_data[31:0];
                        REG_SAMPLE_CH1:   axi_rdata <= scheduler_sample_data[63:32];
                        REG_SAMPLE_CH2:   axi_rdata <= scheduler_sample_data[95:64];
                        REG_SAMPLE_CH3:   axi_rdata <= scheduler_sample_data[127:96];
                        REG_SAMPLE_CH4:   axi_rdata <= scheduler_sample_data[159:128];
                        REG_SAMPLE_CH5:   axi_rdata <= scheduler_sample_data[191:160];
                        REG_SAMPLE_META:  axi_rdata <= {
                            21'd0,
                            scheduler_busy,
                            scheduler_sample_valid,
                            scheduler_sample_last,
                            2'd0,
                            scheduler_sample_index
                        };
                        default: begin
                            axi_rdata <= 32'd0;
                            axi_rresp <= AXI_RESP_SLVERR;
                        end
                    endcase
                end
            end else if (axi_rvalid && S_AXI_RREADY) begin
                axi_rvalid <= 1'b0;
            end
        end
    end

endmodule

