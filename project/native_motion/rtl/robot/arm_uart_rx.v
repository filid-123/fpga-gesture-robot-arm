// ============================================================================
// Block Name : arm_uart_rx
// Description: 8N1 UART receiver with a runtime bit divisor and an enable used
//              for half-duplex echo blanking.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz).  rx_async is an asynchronous pin and passes a
//               two-flop ASYNC_REG synchronizer before any logic (XDC: false
//               path into the first flop only; see phase3_s1_armpath_timing.xdc).
//
// Behaviour:
// - Falling edge starts a frame; the start bit is re-checked at mid-bit, so a
//   glitch shorter than half a bit is rejected.
// - Data bits are sampled at the middle of each bit (LSB first).
// - A low stop bit reports framing_error (no byte) and waits for the line to
//   return high before re-arming, so a held-low line reports once.
// - enable=0 holds the receiver idle and drops any frame in progress.
// - byte_valid and framing_error are single-cycle pulses.
//
// Truth boundary: source candidate.  Supplementary Icarus Verilog run only;
// XSim/synthesis/implementation not run.
// ============================================================================

`timescale 1ns / 1ps

module arm_uart_rx (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [15:0] clks_per_bit,
    input  wire        enable,
    input  wire        rx_async,
    output reg         byte_valid,
    output reg  [7:0]  byte_data,
    output reg         framing_error
);

    localparam [2:0] ST_IDLE  = 3'd0;
    localparam [2:0] ST_START = 3'd1;
    localparam [2:0] ST_DATA  = 3'd2;
    localparam [2:0] ST_STOP  = 3'd3;
    localparam [2:0] ST_BREAK = 3'd4;

    (* ASYNC_REG = "TRUE" *) reg rx_meta;
    (* ASYNC_REG = "TRUE" *) reg rx_sync;

    reg [2:0]  state;
    reg [15:0] counter;
    reg [2:0]  bit_index;
    reg [7:0]  shift;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rx_meta <= 1'b1;
            rx_sync <= 1'b1;
        end else begin
            rx_meta <= rx_async;
            rx_sync <= rx_meta;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state         <= ST_IDLE;
            counter       <= 16'd0;
            bit_index     <= 3'd0;
            shift         <= 8'd0;
            byte_valid    <= 1'b0;
            byte_data     <= 8'd0;
            framing_error <= 1'b0;
        end else begin
            byte_valid    <= 1'b0;
            framing_error <= 1'b0;

            if (!enable) begin
                state <= ST_IDLE;
            end else begin
                case (state)
                    ST_IDLE: begin
                        if (!rx_sync) begin
                            // Half a bit to the middle of the start bit.
                            counter <= {1'b0, clks_per_bit[15:1]} - 16'd1;
                            state   <= ST_START;
                        end
                    end

                    ST_START: begin
                        if (counter != 16'd0) begin
                            counter <= counter - 16'd1;
                        end else if (rx_sync) begin
                            state <= ST_IDLE;             // glitch rejected
                        end else begin
                            counter   <= clks_per_bit - 16'd1;
                            bit_index <= 3'd0;
                            state     <= ST_DATA;
                        end
                    end

                    ST_DATA: begin
                        if (counter != 16'd0) begin
                            counter <= counter - 16'd1;
                        end else begin
                            shift   <= {rx_sync, shift[7:1]};
                            counter <= clks_per_bit - 16'd1;
                            if (bit_index == 3'd7)
                                state <= ST_STOP;
                            bit_index <= bit_index + 3'd1;
                        end
                    end

                    ST_STOP: begin
                        if (counter != 16'd0) begin
                            counter <= counter - 16'd1;
                        end else if (rx_sync) begin
                            byte_valid <= 1'b1;
                            byte_data  <= shift;
                            state      <= ST_IDLE;
                        end else begin
                            framing_error <= 1'b1;
                            state         <= ST_BREAK;
                        end
                    end

                    ST_BREAK: begin
                        if (rx_sync)
                            state <= ST_IDLE;
                    end

                    default: state <= ST_IDLE;
                endcase
            end
        end
    end

endmodule
