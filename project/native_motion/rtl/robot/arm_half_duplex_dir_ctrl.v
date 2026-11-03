// ============================================================================
// Block Name : arm_half_duplex_dir_ctrl
// Description: Direction control for a single-wire servo bus behind an
//              external half-duplex transceiver (SO-ARM101 / STS3215 path).
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz)
//
// Timing (half-duplex mode, all counts in clk cycles, loaded at request):
//   tx_req rises -> dir_tx=1 -> lead_cycles later tx_grant=1 (first start bit
//   may begin) ... tx_req falls while tx_line_idle -> dir_tx held for
//   lag_cycles -> dir_tx=0, rx_enable=1, released=1.
// rx_enable is 0 whenever the driver is enabled, so the local echo of our own
// frame never reaches the status parser.
// Full-duplex mode (half_duplex=0): dir_tx=0, rx_enable=1, tx_grant=tx_req.
//
// The requester must keep tx_req high until its last byte has been accepted
// by the UART and tx_line_idle is high; the lag window always starts from
// the idle line, so the stop bit is never cut.
//
// Truth boundary: source candidate; transceiver lead/lag are TBD per board.
// Supplementary Icarus Verilog run only; XSim/synthesis/implementation not run.
// ============================================================================

`timescale 1ns / 1ps

module arm_half_duplex_dir_ctrl (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        half_duplex,
    input  wire [15:0] lead_cycles,
    input  wire [15:0] lag_cycles,
    input  wire        tx_req,
    input  wire        tx_line_idle,
    output wire        tx_grant,
    output reg         dir_tx,
    output wire        rx_enable,
    output wire        released
);

    localparam [1:0] ST_IDLE  = 2'd0;
    localparam [1:0] ST_LEAD  = 2'd1;
    localparam [1:0] ST_GRANT = 2'd2;
    localparam [1:0] ST_LAG   = 2'd3;

    reg [1:0]  state;
    reg [15:0] counter;

    assign tx_grant  = half_duplex ? (state == ST_GRANT) : tx_req;
    assign rx_enable = half_duplex ? !dir_tx : 1'b1;
    assign released  = half_duplex ? ((state == ST_IDLE) && !dir_tx) : 1'b1;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state   <= ST_IDLE;
            counter <= 16'd0;
            dir_tx  <= 1'b0;
        end else if (!half_duplex) begin
            state  <= ST_IDLE;
            dir_tx <= 1'b0;
        end else begin
            case (state)
                ST_IDLE: begin
                    dir_tx <= 1'b0;
                    if (tx_req) begin
                        dir_tx  <= 1'b1;
                        counter <= lead_cycles;
                        state   <= ST_LEAD;
                    end
                end

                ST_LEAD: begin
                    if (counter != 16'd0)
                        counter <= counter - 16'd1;
                    else
                        state <= ST_GRANT;
                end

                ST_GRANT: begin
                    if (!tx_req && tx_line_idle) begin
                        counter <= lag_cycles;
                        state   <= ST_LAG;
                    end
                end

                ST_LAG: begin
                    if (counter != 16'd0) begin
                        counter <= counter - 16'd1;
                    end else begin
                        dir_tx <= 1'b0;
                        state  <= ST_IDLE;
                    end
                end

                default: begin
                    state  <= ST_IDLE;
                    dir_tx <= 1'b0;
                end
            endcase
        end
    end

endmodule
