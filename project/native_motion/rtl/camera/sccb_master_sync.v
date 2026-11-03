// ============================================================================
// OV5640 SCCB single-register read/write master.
//
// Write: START + ID(W) + REG_H + REG_L + DATA + STOP
// Read : START + ID(W) + REG_H + REG_L + repeated START + ID(R)
//        + DATA + master NACK + STOP
//
// SIOC/SIOD are exposed as open-drain low-drive controls for IOBUFs. Clock
// stretching is intentionally not supported because OV5640 SCCB does not use
// it; the bus runs at the conservative default of 100 kHz.
// ============================================================================
`timescale 1ns / 1ps

module sccb_master_sync #(
    parameter integer CLK_FREQ_HZ  = 100000000,
    parameter integer SCCB_FREQ_HZ = 100000
)(
    input  wire        clk,
    input  wire        rst_n,

    input  wire        cmd_valid,
    output wire        cmd_ready,
    input  wire        cmd_read,
    input  wire [6:0]  device_addr,
    input  wire [15:0] register_addr,
    input  wire [7:0]  write_data,

    output reg  [7:0]  read_data,
    output reg         busy,
    output reg         done,
    output reg         ack_error,

    output reg         scl_drive_low,
    output reg         sda_drive_low,
    input  wire        sda_in
);

    localparam integer HALF_PERIOD = CLK_FREQ_HZ / (2 * SCCB_FREQ_HZ);
    localparam integer DIV_WIDTH = (HALF_PERIOD <= 1) ? 1 : $clog2(HALF_PERIOD);

    localparam [3:0] ST_IDLE             = 4'd0;
    localparam [3:0] ST_START            = 4'd1;
    localparam [3:0] ST_BIT_LOW          = 4'd2;
    localparam [3:0] ST_BIT_HIGH         = 4'd3;
    localparam [3:0] ST_ACK_LOW          = 4'd4;
    localparam [3:0] ST_ACK_HIGH         = 4'd5;
    localparam [3:0] ST_RESTART_LOW      = 4'd6;
    localparam [3:0] ST_RESTART_HIGH     = 4'd7;
    localparam [3:0] ST_RESTART_ASSERT   = 4'd8;
    localparam [3:0] ST_READ_BIT_LOW     = 4'd9;
    localparam [3:0] ST_READ_BIT_HIGH    = 4'd10;
    localparam [3:0] ST_READ_NACK_LOW    = 4'd11;
    localparam [3:0] ST_READ_NACK_HIGH   = 4'd12;
    localparam [3:0] ST_STOP_LOW         = 4'd13;
    localparam [3:0] ST_STOP_HIGH        = 4'd14;
    localparam [3:0] ST_STOP_RELEASE     = 4'd15;

    reg [3:0] state;
    reg [DIV_WIDTH-1:0] divider;
    reg [2:0] tx_stage;
    reg [2:0] bit_index;
    reg [7:0] shift_byte;
    reg       latched_cmd_read;
    reg [6:0] latched_device_addr;
    reg [15:0] latched_register_addr;
    reg [7:0] latched_write_data;

    wire half_tick = (divider == HALF_PERIOD - 1);
    assign cmd_ready = !busy;

    always @* begin
        scl_drive_low = 1'b0;
        sda_drive_low = 1'b0;
        case (state)
            ST_START,
            ST_RESTART_ASSERT: begin
                scl_drive_low = 1'b0;
                sda_drive_low = 1'b1;
            end
            ST_BIT_LOW: begin
                scl_drive_low = 1'b1;
                sda_drive_low = ~shift_byte[bit_index];
            end
            ST_BIT_HIGH: begin
                scl_drive_low = 1'b0;
                sda_drive_low = ~shift_byte[bit_index];
            end
            ST_ACK_LOW,
            ST_READ_BIT_LOW,
            ST_READ_NACK_LOW,
            ST_RESTART_LOW: begin
                scl_drive_low = 1'b1;
                sda_drive_low = 1'b0;
            end
            ST_ACK_HIGH,
            ST_READ_BIT_HIGH,
            ST_READ_NACK_HIGH,
            ST_RESTART_HIGH: begin
                scl_drive_low = 1'b0;
                sda_drive_low = 1'b0;
            end
            ST_STOP_LOW: begin
                scl_drive_low = 1'b1;
                sda_drive_low = 1'b1;
            end
            ST_STOP_HIGH: begin
                scl_drive_low = 1'b0;
                sda_drive_low = 1'b1;
            end
            default: begin
                scl_drive_low = 1'b0;
                sda_drive_low = 1'b0;
            end
        endcase
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            state                  <= ST_IDLE;
            divider                <= {DIV_WIDTH{1'b0}};
            tx_stage               <= 3'd0;
            bit_index              <= 3'd7;
            shift_byte             <= 8'd0;
            latched_cmd_read       <= 1'b0;
            latched_device_addr    <= 7'd0;
            latched_register_addr  <= 16'd0;
            latched_write_data     <= 8'd0;
            read_data              <= 8'd0;
            busy                   <= 1'b0;
            done                   <= 1'b0;
            ack_error              <= 1'b0;
        end else begin
            done <= 1'b0;
            if (!busy) begin
                divider <= {DIV_WIDTH{1'b0}};
                state   <= ST_IDLE;
                if (cmd_valid) begin
                    latched_cmd_read      <= cmd_read;
                    latched_device_addr   <= device_addr;
                    latched_register_addr <= register_addr;
                    latched_write_data    <= write_data;
                    shift_byte            <= {device_addr, 1'b0};
                    tx_stage              <= 3'd0;
                    bit_index             <= 3'd7;
                    read_data             <= 8'd0;
                    ack_error             <= 1'b0;
                    busy                  <= 1'b1;
                    state                 <= ST_START;
                end
            end else begin
                if (half_tick)
                    divider <= {DIV_WIDTH{1'b0}};
                else
                    divider <= divider + {{(DIV_WIDTH-1){1'b0}}, 1'b1};

                if (half_tick) begin
                    case (state)
                        ST_START: state <= ST_BIT_LOW;
                        ST_BIT_LOW: state <= ST_BIT_HIGH;

                        ST_BIT_HIGH: begin
                            if (bit_index == 0)
                                state <= ST_ACK_LOW;
                            else begin
                                bit_index <= bit_index - 3'd1;
                                state <= ST_BIT_LOW;
                            end
                        end

                        ST_ACK_LOW: state <= ST_ACK_HIGH;

                        ST_ACK_HIGH: begin
                            if (sda_in)
                                ack_error <= 1'b1;
                            bit_index <= 3'd7;
                            case (tx_stage)
                                3'd0: begin
                                    tx_stage <= 3'd1;
                                    shift_byte <= latched_register_addr[15:8];
                                    state <= ST_BIT_LOW;
                                end
                                3'd1: begin
                                    tx_stage <= 3'd2;
                                    shift_byte <= latched_register_addr[7:0];
                                    state <= ST_BIT_LOW;
                                end
                                3'd2: begin
                                    if (latched_cmd_read) begin
                                        state <= ST_RESTART_LOW;
                                    end else begin
                                        tx_stage <= 3'd3;
                                        shift_byte <= latched_write_data;
                                        state <= ST_BIT_LOW;
                                    end
                                end
                                default: begin
                                    if (latched_cmd_read)
                                        state <= ST_READ_BIT_LOW;
                                    else
                                        state <= ST_STOP_LOW;
                                end
                            endcase
                        end

                        ST_RESTART_LOW: state <= ST_RESTART_HIGH;
                        ST_RESTART_HIGH: state <= ST_RESTART_ASSERT;
                        ST_RESTART_ASSERT: begin
                            tx_stage <= 3'd3;
                            bit_index <= 3'd7;
                            shift_byte <= {latched_device_addr, 1'b1};
                            state <= ST_BIT_LOW;
                        end

                        ST_READ_BIT_LOW: state <= ST_READ_BIT_HIGH;
                        ST_READ_BIT_HIGH: begin
                            read_data[bit_index] <= sda_in;
                            if (bit_index == 0)
                                state <= ST_READ_NACK_LOW;
                            else begin
                                bit_index <= bit_index - 3'd1;
                                state <= ST_READ_BIT_LOW;
                            end
                        end
                        // Release SDA during the ninth clock to terminate a
                        // one-byte read, then generate a legal STOP.
                        ST_READ_NACK_LOW: state <= ST_READ_NACK_HIGH;
                        ST_READ_NACK_HIGH: state <= ST_STOP_LOW;

                        ST_STOP_LOW: state <= ST_STOP_HIGH;
                        ST_STOP_HIGH: state <= ST_STOP_RELEASE;
                        ST_STOP_RELEASE: begin
                            busy <= 1'b0;
                            done <= 1'b1;
                            state <= ST_IDLE;
                        end

                        default: begin
                            busy <= 1'b0;
                            ack_error <= 1'b1;
                            state <= ST_IDLE;
                        end
                    endcase
                end
            end
        end
    end

endmodule


