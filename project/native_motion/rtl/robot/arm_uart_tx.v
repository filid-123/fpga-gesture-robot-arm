// ============================================================================
// Block Name : arm_uart_tx
// Description: 8N1 UART transmitter with a runtime bit divisor, used by the
//              Phase 3 S1 arm backend for both the RoArm UART and the SO-ARM101
//              half-duplex bus (through arm_half_duplex_dir_ctrl).
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz system domain); tx is a registered output
//
// Interface:
// - byte_valid/byte_ready handshake; byte_ready is high only when idle, so a
//   producer holding byte_valid never loses or duplicates a byte.
// - clks_per_bit is sampled when a byte is accepted (>= 16 enforced by the
//   AXI commit check); changing it mid-byte has no effect.
// - LSB first, one start bit (0), eight data bits, one stop bit (1).
//
// Truth boundary: source candidate.  Supplementary Icarus Verilog run only;
// XSim/synthesis/implementation not run.
// ============================================================================

`timescale 1ns / 1ps

module arm_uart_tx (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [15:0] clks_per_bit,
    input  wire        byte_valid,
    output wire        byte_ready,
    input  wire [7:0]  byte_data,
    output reg         tx,
    output wire        busy
);

    reg        active;
    reg [9:0]  shift;
    reg [3:0]  bits_left;
    reg [15:0] bit_counter;
    reg [15:0] bit_period;

    assign busy       = active;
    assign byte_ready = !active;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active      <= 1'b0;
            shift       <= 10'h3ff;
            bits_left   <= 4'd0;
            bit_counter <= 16'd0;
            bit_period  <= 16'd0;
            tx          <= 1'b1;
        end else if (!active) begin
            tx <= 1'b1;
            if (byte_valid) begin
                // {stop, data[7:0], start}; bit 0 is transmitted first.
                shift       <= {1'b1, byte_data, 1'b0};
                bits_left   <= 4'd10;
                bit_period  <= clks_per_bit;
                bit_counter <= clks_per_bit - 16'd1;
                tx          <= 1'b0;
                active      <= 1'b1;
            end
        end else if (bit_counter != 16'd0) begin
            bit_counter <= bit_counter - 16'd1;
        end else begin
            bits_left <= bits_left - 4'd1;
            if (bits_left == 4'd1) begin
                // Stop bit has lasted a full bit period.
                active <= 1'b0;
                tx     <= 1'b1;
            end else begin
                shift       <= {1'b1, shift[9:1]};
                tx          <= shift[1];
                bit_counter <= bit_period - 16'd1;
            end
        end
    end

endmodule
