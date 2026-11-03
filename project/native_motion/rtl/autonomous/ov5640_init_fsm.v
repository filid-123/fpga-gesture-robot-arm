// ============================================================================
// Autonomous OV5640 power-up and VGA/YUYV register programming.
//
// The command ROM is the already board-validated 2026-09-04 sequence.  ACK
// failure restarts the complete power/configuration sequence, at most three
// attempts.  No chip-ID readback, checksum, or software handshake is used.
// ============================================================================
`timescale 1ns / 1ps

module ov5640_init_fsm #(
    parameter INIT_FILE             = "ov5640_vga_yuyv.mem",
    parameter integer COMMAND_COUNT = 159,
    parameter integer POWER_DOWN_CYCLES = 500000,
    parameter integer PWDN_LOW_CYCLES   = 100000,
    parameter integer RESET_WAIT_CYCLES = 2000000,
    parameter integer SOFT_RESET_CYCLES = 500000,
    parameter integer STREAM_WAIT_CYCLES= 30000000,
    parameter integer RETRY_WAIT_CYCLES = 100000000
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        xclk_locked,

    output reg         camera_reset_n,
    output reg         camera_pwdn,
    output reg         cmd_valid,
    input  wire        cmd_ready,
    output wire        cmd_read,
    output wire [6:0]  device_addr,
    output reg  [15:0] register_addr,
    output reg  [7:0]  write_data,
    input  wire        cmd_done,
    input  wire        cmd_ack_error,

    output reg         init_done,
    output reg         init_error
);

    localparam [3:0] ST_WAIT_LOCK   = 4'd0;
    localparam [3:0] ST_POWER_DOWN  = 4'd1;
    localparam [3:0] ST_PWDN_LOW    = 4'd2;
    localparam [3:0] ST_RESET_WAIT  = 4'd3;
    localparam [3:0] ST_ISSUE       = 4'd4;
    localparam [3:0] ST_WAIT_CMD    = 4'd5;
    localparam [3:0] ST_POST_DELAY  = 4'd6;
    localparam [3:0] ST_RETRY_WAIT  = 4'd7;
    localparam [3:0] ST_DONE        = 4'd8;
    localparam [3:0] ST_ERROR       = 4'd9;

    reg [3:0] state;
    reg [31:0] delay_count;
    reg [7:0] command_index;
    reg [1:0] attempt_index;
    reg [23:0] command_rom [0:COMMAND_COUNT-1];

    assign cmd_read = 1'b0;
    assign device_addr = 7'h3c;

    initial begin
        $readmemh(INIT_FILE, command_rom);
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            state           <= ST_WAIT_LOCK;
            delay_count     <= 32'd0;
            command_index   <= 8'd0;
            attempt_index   <= 2'd0;
            camera_reset_n  <= 1'b0;
            camera_pwdn     <= 1'b1;
            cmd_valid       <= 1'b0;
            register_addr   <= 16'd0;
            write_data      <= 8'd0;
            init_done       <= 1'b0;
            init_error      <= 1'b0;
        end else begin
            cmd_valid <= 1'b0;

            case (state)
                ST_WAIT_LOCK: begin
                    camera_reset_n <= 1'b0;
                    camera_pwdn    <= 1'b1;
                    if (xclk_locked) begin
                        delay_count <= POWER_DOWN_CYCLES - 1;
                        state <= ST_POWER_DOWN;
                    end
                end

                ST_POWER_DOWN: begin
                    camera_reset_n <= 1'b0;
                    camera_pwdn    <= 1'b1;
                    if (delay_count == 0) begin
                        camera_pwdn <= 1'b0;
                        delay_count <= PWDN_LOW_CYCLES - 1;
                        state <= ST_PWDN_LOW;
                    end else begin
                        delay_count <= delay_count - 32'd1;
                    end
                end

                ST_PWDN_LOW: begin
                    if (delay_count == 0) begin
                        camera_reset_n <= 1'b1;
                        delay_count <= RESET_WAIT_CYCLES - 1;
                        state <= ST_RESET_WAIT;
                    end else begin
                        delay_count <= delay_count - 32'd1;
                    end
                end

                ST_RESET_WAIT: begin
                    if (delay_count == 0) begin
                        command_index <= 8'd0;
                        state <= ST_ISSUE;
                    end else begin
                        delay_count <= delay_count - 32'd1;
                    end
                end

                ST_ISSUE: begin
                    if (cmd_ready) begin
                        register_addr <= command_rom[command_index][23:8];
                        write_data    <= command_rom[command_index][7:0];
                        cmd_valid     <= 1'b1;
                        state         <= ST_WAIT_CMD;
                    end
                end

                ST_WAIT_CMD: begin
                    if (cmd_done) begin
                        if (cmd_ack_error) begin
                            camera_reset_n <= 1'b0;
                            camera_pwdn    <= 1'b1;
                            if (attempt_index == 2'd2) begin
                                init_error <= 1'b1;
                                state <= ST_ERROR;
                            end else begin
                                attempt_index <= attempt_index + 2'd1;
                                delay_count <= RETRY_WAIT_CYCLES - 1;
                                state <= ST_RETRY_WAIT;
                            end
                        end else if (command_index == 0) begin
                            delay_count <= SOFT_RESET_CYCLES - 1;
                            state <= ST_POST_DELAY;
                        end else if (command_index == COMMAND_COUNT - 1) begin
                            delay_count <= STREAM_WAIT_CYCLES - 1;
                            state <= ST_POST_DELAY;
                        end else begin
                            command_index <= command_index + 8'd1;
                            state <= ST_ISSUE;
                        end
                    end
                end

                ST_POST_DELAY: begin
                    if (delay_count == 0) begin
                        if (command_index == COMMAND_COUNT - 1) begin
                            init_done <= 1'b1;
                            state <= ST_DONE;
                        end else begin
                            command_index <= command_index + 8'd1;
                            state <= ST_ISSUE;
                        end
                    end else begin
                        delay_count <= delay_count - 32'd1;
                    end
                end

                ST_RETRY_WAIT: begin
                    camera_reset_n <= 1'b0;
                    camera_pwdn    <= 1'b1;
                    if (delay_count == 0) begin
                        delay_count <= POWER_DOWN_CYCLES - 1;
                        state <= ST_POWER_DOWN;
                    end else begin
                        delay_count <= delay_count - 32'd1;
                    end
                end

                ST_DONE: begin
                    init_done <= 1'b1;
                    if (!xclk_locked) begin
                        init_done      <= 1'b0;
                        init_error     <= 1'b1;
                        camera_reset_n <= 1'b0;
                        camera_pwdn    <= 1'b1;
                        state          <= ST_ERROR;
                    end
                end

                ST_ERROR: begin
                    camera_reset_n <= 1'b0;
                    camera_pwdn    <= 1'b1;
                end

                default: state <= ST_ERROR;
            endcase
        end
    end

endmodule
