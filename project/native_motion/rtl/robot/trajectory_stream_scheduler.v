// ============================================================================
// Block Name : trajectory_stream_scheduler
// Description: Development wrapper around trajectory_smoothstep_q16_16.
//              It precomputes one 32-sample segment, buffers the samples, then
//              emits them at a programmable minimum interval through a
//              backpressure-safe ready/valid stream.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (planned 100 MHz system domain)
//
// Packed channel order matches phase3_trajectory_q16_16_v1:
//   [191:160] ch5 ... [63:32] ch1, [31:0] ch0.
//
// Truth boundary:
// - period_cycles is measured in clk cycles and is not the final servo period.
// - Output timing is a minimum interval. Backpressure extends the interval and
//   never drops or overwrites a sample.
// - This block is not an AXI slave, UART encoder, feedback controller or final
//   actuator safety layer.
// ============================================================================

`timescale 1ns / 1ps

module trajectory_stream_scheduler #(
    parameter [31:0] MIN_PERIOD_CYCLES = 32'd256
) (
    input  wire         clk,
    input  wire         rst_n,

    input  wire         cmd_valid,
    output wire         cmd_ready,
    input  wire [191:0] cmd_start_data,
    input  wire [191:0] cmd_target_data,
    input  wire [31:0]  cmd_period_cycles,

    output reg          busy,
    output reg          sample_valid,
    input  wire         sample_ready,
    output reg  [191:0] sample_data,
    output reg  [5:0]   sample_index,
    output reg          sample_last,
    output reg          segment_done,

    output reg          error_invalid_period,
    output reg          error_fill_protocol,
    output reg          error_deadline_miss,
    output wire         error_core
);

    localparam [1:0] ST_IDLE = 2'd0;
    localparam [1:0] ST_FILL = 2'd1;
    localparam [1:0] ST_WAIT = 2'd2;
    localparam [1:0] ST_HOLD = 2'd3;

    reg [1:0] state;
    reg core_start;

    reg [191:0] start_reg;
    reg [191:0] target_reg;
    reg [31:0] period_reg;
    reg [31:0] period_counter;
    reg [6:0] fill_expected;
    reg [4:0] playback_index;

    // One complete segment is intentionally buffered so trajectory arithmetic
    // is decoupled from slow or stalled actuator/host consumers.
    (* ram_style = "block" *) reg [191:0] sample_mem [0:31];

    wire core_busy;
    wire core_sample_valid;
    wire [5:0] core_sample_index;
    wire signed [31:0] core_joint_ch0;
    wire signed [31:0] core_joint_ch1;
    wire signed [31:0] core_joint_ch2;
    wire signed [31:0] core_joint_ch3;
    wire signed [31:0] core_joint_ch4;
    wire signed [31:0] core_joint_ch5;
    wire core_done;
    wire core_error_start_while_busy;
    wire core_error_arithmetic_overflow;

    wire [191:0] core_sample_data = {
        core_joint_ch5,
        core_joint_ch4,
        core_joint_ch3,
        core_joint_ch2,
        core_joint_ch1,
        core_joint_ch0
    };

    assign cmd_ready = (state == ST_IDLE) && !busy;
    assign error_core =
        core_error_start_while_busy || core_error_arithmetic_overflow;

    trajectory_smoothstep_q16_16 u_trajectory_core (
        .clk(clk),
        .rst_n(rst_n),
        .start(core_start),
        .start_ch0(start_reg[31:0]),
        .start_ch1(start_reg[63:32]),
        .start_ch2(start_reg[95:64]),
        .start_ch3(start_reg[127:96]),
        .start_ch4(start_reg[159:128]),
        .start_ch5(start_reg[191:160]),
        .target_ch0(target_reg[31:0]),
        .target_ch1(target_reg[63:32]),
        .target_ch2(target_reg[95:64]),
        .target_ch3(target_reg[127:96]),
        .target_ch4(target_reg[159:128]),
        .target_ch5(target_reg[191:160]),
        .busy(core_busy),
        .sample_valid(core_sample_valid),
        .sample_index(core_sample_index),
        .joint_ch0(core_joint_ch0),
        .joint_ch1(core_joint_ch1),
        .joint_ch2(core_joint_ch2),
        .joint_ch3(core_joint_ch3),
        .joint_ch4(core_joint_ch4),
        .joint_ch5(core_joint_ch5),
        .done(core_done),
        .error_start_while_busy(core_error_start_while_busy),
        .error_arithmetic_overflow(core_error_arithmetic_overflow)
    );

    // Keep the RAM write port in a reset-free synchronous process. Placing a
    // memory write in the asynchronously reset control process prevents Vivado
    // from inferring block RAM and expands the buffer into 6,144 flip-flops.
    always @(posedge clk) begin
        if ((state == ST_FILL) && core_sample_valid &&
            (core_sample_index >= 6'd1) && (core_sample_index <= 6'd32) &&
            (core_sample_index == fill_expected[5:0]))
            sample_mem[core_sample_index - 1'b1] <= core_sample_data;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state                  <= ST_IDLE;
            core_start             <= 1'b0;
            start_reg              <= 192'd0;
            target_reg             <= 192'd0;
            period_reg             <= 32'd0;
            period_counter         <= 32'd0;
            fill_expected          <= 7'd1;
            playback_index         <= 5'd0;
            busy                   <= 1'b0;
            sample_valid           <= 1'b0;
            sample_data            <= 192'd0;
            sample_index           <= 6'd0;
            sample_last            <= 1'b0;
            segment_done           <= 1'b0;
            error_invalid_period   <= 1'b0;
            error_fill_protocol    <= 1'b0;
            error_deadline_miss    <= 1'b0;
        end else begin
            core_start   <= 1'b0;
            segment_done <= 1'b0;

            case (state)
                ST_IDLE: begin
                    busy         <= 1'b0;
                    sample_valid <= 1'b0;
                    sample_last  <= 1'b0;

                    if (cmd_valid && cmd_ready) begin
                        if (cmd_period_cycles < MIN_PERIOD_CYCLES) begin
                            error_invalid_period <= 1'b1;
                        end else begin
                            start_reg       <= cmd_start_data;
                            target_reg      <= cmd_target_data;
                            period_reg      <= cmd_period_cycles;
                            period_counter  <= cmd_period_cycles - 1'b1;
                            fill_expected   <= 7'd1;
                            playback_index  <= 5'd0;
                            core_start      <= 1'b1;
                            busy            <= 1'b1;
                            state           <= ST_FILL;
                        end
                    end
                end

                ST_FILL: begin
                    if (period_counter != 32'd0)
                        period_counter <= period_counter - 1'b1;
                    else if (!core_done)
                        error_deadline_miss <= 1'b1;

                    if (core_sample_valid) begin
                        if ((core_sample_index < 6'd1) ||
                            (core_sample_index > 6'd32) ||
                            (core_sample_index != fill_expected[5:0])) begin
                            error_fill_protocol <= 1'b1;
                        end
                        fill_expected <= fill_expected + 1'b1;
                    end

                    if (core_done) begin
                        if (!core_sample_valid ||
                            (core_sample_index != 6'd32) ||
                            (fill_expected != 7'd32))
                            error_fill_protocol <= 1'b1;
                        state <= ST_WAIT;
                    end
                end

                ST_WAIT: begin
                    if (period_counter != 32'd0) begin
                        period_counter <= period_counter - 1'b1;
                    end else begin
                        sample_data  <= sample_mem[playback_index];
                        sample_index <= {1'b0, playback_index} + 1'b1;
                        sample_last  <= (playback_index == 5'd31);
                        sample_valid <= 1'b1;
                        state        <= ST_HOLD;
                    end
                end

                ST_HOLD: begin
                    // All payload fields remain unchanged until the consumer
                    // acknowledges the sample.
                    if (sample_valid && sample_ready) begin
                        sample_valid <= 1'b0;
                        if (sample_last) begin
                            busy         <= 1'b0;
                            segment_done <= 1'b1;
                            state        <= ST_IDLE;
                        end else begin
                            playback_index <= playback_index + 1'b1;
                            period_counter <= period_reg - 1'b1;
                            state          <= ST_WAIT;
                        end
                    end
                end

                default: begin
                    state               <= ST_IDLE;
                    busy                <= 1'b0;
                    sample_valid        <= 1'b0;
                    error_fill_protocol <= 1'b1;
                end
            endcase
        end
    end

endmodule
