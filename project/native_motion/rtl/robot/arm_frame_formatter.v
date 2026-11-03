// ============================================================================
// Block Name : arm_frame_formatter
// Description: Template engine for ISA arm_frame_template_isa_v1
//              (ps/robot/arm_frame_template.py).  One engine produces the
//              RoArm JSON line, the RoArm binary-bridge frame and the Feetech
//              sync-write / read-request packets; no protocol word is hard
//              coded in RTL.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz)
//
// Operation:
// - Template RAM: 256 x 16 distributed RAM, written only while the backend is
//   in MODE_OFF (reset-free write process so Vivado infers LUTRAM).  The read
//   is asynchronous and registered in ST_FETCH before decode.
// - start + check_only=1: walk the program without emitting; report illegal
//   words, a missing END, and BIN saturation for the current dev_values.
//   Used at CONFIG_COMMIT and before every real frame.
// - start + check_only=0: emit bytes on out_valid/out_ready.  out_byte is
//   stable while out_valid is high.  Checksums accumulate on the handshake.
// - DEC: 32-cycle double-dabble conversion (no divider, no DSP).
// - Channel values are read through val_ch/val_data from the command LUTRAM
//   in arm_backend_core, so the engine carries no 192-bit value bus.  DEC and
//   BIN register the value in ST_DECODE and use it one cycle later
//   (ST_VALUE), so the LUTRAM read is never chained with the 33-bit absolute
//   value, the saturation compare and the encoder.
// - done is a one-cycle pulse; error/saturated are valid from done until the
//   next start.
//
// Truth boundary: source candidate.  Supplementary Icarus Verilog run only;
// XSim/synthesis/implementation not run.
// ============================================================================

`timescale 1ns / 1ps

module arm_frame_formatter #(parameter integer EXTRA_SCALARS=0) (
    input  wire         clk,
    input  wire         rst_n,

    input  wire         tpl_we,
    input  wire [7:0]   tpl_waddr,
    input  wire [15:0]  tpl_wdata,

    input  wire         start,
    input  wire         check_only,
    input  wire [7:0]   base_addr,
    output wire [2:0]   val_ch,
    input  wire [31:0]  val_data,
    input  wire [47:0]  device_ids,
    input  wire [2:0]   rr_channel,
    input  wire [7:0]   seq_byte,

    output wire         busy,
    output reg          done,
    output reg          error,
    output reg          saturated,

    output reg  [7:0]   out_byte,
    output reg          out_valid,
    input  wire         out_ready
);

    localparam [3:0] OP_END = 4'h0;
    localparam [3:0] OP_LIT = 4'h1;
    localparam [3:0] OP_DEC = 4'h2;
    localparam [3:0] OP_BIN = 4'h3;
    localparam [3:0] OP_CKB = 4'h4;
    localparam [3:0] OP_CKE = 4'h5;
    localparam [3:0] OP_IDB = 4'h6;
    localparam [3:0] OP_SEQ = 4'h7;

    localparam [3:0] ST_IDLE     = 4'd0;
    localparam [3:0] ST_FETCH    = 4'd1;
    localparam [3:0] ST_DECODE   = 4'd2;
    localparam [3:0] ST_NEXT     = 4'd3;
    localparam [3:0] ST_WAIT     = 4'd4;
    localparam [3:0] ST_DEC_CONV = 4'd5;
    localparam [3:0] ST_DEC_SCAN = 4'd6;
    localparam [3:0] ST_DEC_SIGN = 4'd7;
    localparam [3:0] ST_DEC_DIG  = 4'd8;
    localparam [3:0] ST_DEC_DOT  = 4'd9;
    localparam [3:0] ST_BIN_OUT  = 4'd10;
    localparam [3:0] ST_VALUE    = 4'd11;

    (* ram_style = "distributed" *) reg [15:0] tpl_mem [0:255];

    reg [3:0]  state;
    reg [3:0]  ret_state;
    reg [7:0]  pc;
    reg [15:0] word;
    reg        check_mode;

    reg        ck_active;
    reg        ck_xor;
    reg        ck_count;       // 1 when the byte in flight is accumulated
    reg [7:0]  ck_acc;

    reg [39:0] bcd;
    reg [31:0] bin_shift;
    reg [5:0]  conv_count;
    reg [2:0]  dec_digits;
    reg        dec_negative;
    reg [3:0]  dig_k;
    reg        dig_frac;

    reg [31:0] value_r;
    reg [31:0] bin_word;
    reg [1:0]  bin_index;
    reg [1:0]  bin_last;
    reg        bin_big_endian;

    assign busy = (state != ST_IDLE);

    // Reset-free write port so the template infers distributed RAM.
    always @(posedge clk) begin
        if (tpl_we)
            tpl_mem[tpl_waddr] <= tpl_wdata;
    end

    wire [3:0]  opcode  = word[15:12];
    wire [11:0] operand = word[11:0];
    wire [2:0]  op_ch   = operand[2:0];

    // Operand legality: identical to arm_frame_template.word_is_legal().
    reg word_legal;
    always @(*) begin
        case (opcode)
            OP_END, OP_SEQ: word_legal = (operand == 12'd0);
            OP_LIT:         word_legal = (operand[11:8] == 4'd0);
            OP_DEC:         word_legal = (operand[11:7] == 5'd0) && (operand[3] == 1'b0) &&
                                         ((op_ch < 3'd6) || (EXTRA_SCALARS!=0 && operand[6:4]==0)) && (operand[6:4] <= 3'd6);
            OP_BIN:         word_legal = (operand[11:8] == 4'd0) && (op_ch < 3'd6) &&
                                         ((operand[4:3] == 2'd1) || (operand[4:3] == 2'd2)) &&
                                         (operand[7:6] != 2'd3);
            OP_CKB, OP_CKE: word_legal = (operand[11:1] == 11'd0);
            OP_IDB:         word_legal = operand[3] ? (operand == 12'h008) :
                                         ((operand[11:3] == 9'd0) && (op_ch < 3'd6));
            default:        word_legal = 1'b0;
        endcase
    end

    // Channel value for DEC/BIN (explicitly signed), read by operand channel
    // in ST_DECODE and registered for ST_VALUE.
    assign val_ch = op_ch;
    wire signed [31:0] op_value = value_r;
    wire               value_negative = op_value[31];
    wire signed [32:0] value_ext = {op_value[31], op_value};
    wire [32:0]        value_abs = value_negative ? (33'd0 - value_ext) : value_ext;

    // BIN encoding with explicit saturation (arm_frame_template.encode_binary_field).
    wire       bin_w32 = (operand[4:3] == 2'd2);
    wire [1:0] bin_enc = operand[7:6];
    reg [31:0] bin_encoded;
    reg        bin_saturates;
    always @(*) begin
        bin_encoded   = op_value;
        bin_saturates = 1'b0;
        case (bin_enc)
            2'd0: begin   // two's complement
                if (!bin_w32) begin
                    if (op_value > 32'sd32767) begin
                        bin_encoded = 32'h0000_7fff; bin_saturates = 1'b1;
                    end else if (op_value < -32'sd32768) begin
                        bin_encoded = 32'h0000_8000; bin_saturates = 1'b1;
                    end else begin
                        bin_encoded = {16'd0, op_value[15:0]};
                    end
                end
            end
            2'd1: begin   // unsigned
                if (value_negative) begin
                    bin_encoded = 32'd0; bin_saturates = 1'b1;
                end else if (!bin_w32 && (op_value > 32'sd65535)) begin
                    bin_encoded = 32'h0000_ffff; bin_saturates = 1'b1;
                end
            end
            default: begin   // sign-magnitude, sign in the field MSB
                if (!bin_w32) begin
                    if (value_abs > 33'd32767) begin
                        bin_encoded = {16'd0, value_negative, 15'h7fff}; bin_saturates = 1'b1;
                    end else begin
                        bin_encoded = {16'd0, value_negative, value_abs[14:0]};
                    end
                end else begin
                    if (value_abs > 33'h0_7fff_ffff) begin
                        bin_encoded = {value_negative, 31'h7fff_ffff}; bin_saturates = 1'b1;
                    end else begin
                        bin_encoded = {value_negative, value_abs[30:0]};
                    end
                end
            end
        endcase
    end

    // Double-dabble step: add 3 to every BCD digit >= 5, then shift left.
    reg [39:0] bcd_adjusted;
    integer d;
    always @(*) begin
        for (d = 0; d < 10; d = d + 1)
            bcd_adjusted[d * 4 +: 4] = (bcd[d * 4 +: 4] >= 4'd5) ?
                                       (bcd[d * 4 +: 4] + 4'd3) : bcd[d * 4 +: 4];
    end

    wire [3:0] digit_at_k = bcd[dig_k * 4 +: 4];

    task emit;
        input [7:0] value;
        input       count_in_checksum;
        input [3:0] return_to;
        begin
            out_byte  <= value;
            out_valid <= 1'b1;
            ck_count  <= count_in_checksum;
            ret_state <= return_to;
            state     <= ST_WAIT;
        end
    endtask

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state          <= ST_IDLE;
            ret_state      <= ST_IDLE;
            pc             <= 8'd0;
            word           <= 16'd0;
            check_mode     <= 1'b0;
            ck_active      <= 1'b0;
            ck_xor         <= 1'b0;
            ck_count       <= 1'b0;
            ck_acc         <= 8'd0;
            bcd            <= 40'd0;
            bin_shift      <= 32'd0;
            conv_count     <= 6'd0;
            dec_digits     <= 3'd0;
            dec_negative   <= 1'b0;
            dig_k          <= 4'd0;
            dig_frac       <= 1'b0;
            value_r        <= 32'd0;
            bin_word       <= 32'd0;
            bin_index      <= 2'd0;
            bin_last       <= 2'd0;
            bin_big_endian <= 1'b0;
            done           <= 1'b0;
            error          <= 1'b0;
            saturated      <= 1'b0;
            out_byte       <= 8'd0;
            out_valid      <= 1'b0;
        end else begin
            done <= 1'b0;
            case (state)
                ST_IDLE: begin
                    if (start) begin
                        pc         <= base_addr;
                        check_mode <= check_only;
                        ck_active  <= 1'b0;
                        ck_acc     <= 8'd0;
                        error      <= 1'b0;
                        saturated  <= 1'b0;
                        state      <= ST_FETCH;
                    end
                end

                ST_FETCH: begin
                    word  <= tpl_mem[pc];
                    state <= ST_DECODE;
                end

                ST_DECODE: begin
                    if (!word_legal) begin
                        error <= 1'b1;
                        done  <= 1'b1;
                        state <= ST_IDLE;
                    end else begin
                        case (opcode)
                            OP_END: begin
                                done  <= 1'b1;
                                state <= ST_IDLE;
                            end
                            OP_LIT: begin
                                if (check_mode) state <= ST_NEXT;
                                else emit(operand[7:0], ck_active, ST_NEXT);
                            end
                            OP_DEC: begin
                                if (check_mode) begin
                                    state <= ST_NEXT;
                                end else begin
                                    value_r <= val_data;
                                    state   <= ST_VALUE;
                                end
                            end
                            OP_BIN: begin
                                value_r <= val_data;
                                state   <= ST_VALUE;
                            end
                            OP_CKB: begin
                                ck_active <= 1'b1;
                                ck_xor    <= operand[0];
                                ck_acc    <= 8'd0;
                                state     <= ST_NEXT;
                            end
                            OP_CKE: begin
                                ck_active <= 1'b0;
                                if (check_mode) state <= ST_NEXT;
                                else emit(operand[0] ? ~ck_acc : ck_acc, 1'b0, ST_NEXT);
                            end
                            OP_IDB: begin
                                if (check_mode)
                                    state <= ST_NEXT;
                                else if (operand[3])
                                    emit(device_ids[rr_channel * 8 +: 8], ck_active, ST_NEXT);
                                else
                                    emit(device_ids[op_ch * 8 +: 8], ck_active, ST_NEXT);
                            end
                            default: begin   // OP_SEQ (legality already checked)
                                if (check_mode) state <= ST_NEXT;
                                else emit(seq_byte, ck_active, ST_NEXT);
                            end
                        endcase
                    end
                end

                ST_VALUE: begin
                    // word/operand still describe the DEC or BIN instruction.
                    if (opcode == OP_DEC) begin
                        bcd          <= 40'd0;
                        bin_shift    <= value_abs[31:0];
                        conv_count   <= 6'd0;
                        dec_digits   <= operand[6:4];
                        dec_negative <= value_negative;
                        state        <= ST_DEC_CONV;
                    end else begin
                        if (bin_saturates)
                            saturated <= 1'b1;
                        if (check_mode) begin
                            state <= ST_NEXT;
                        end else begin
                            bin_word       <= bin_encoded;
                            bin_last       <= bin_w32 ? 2'd3 : 2'd1;
                            bin_big_endian <= operand[5];
                            bin_index      <= operand[5] ? (bin_w32 ? 2'd3 : 2'd1) : 2'd0;
                            state          <= ST_BIN_OUT;
                        end
                    end
                end

                ST_NEXT: begin
                    if (pc == 8'd255) begin
                        error <= 1'b1;         // ran past the RAM without END
                        done  <= 1'b1;
                        state <= ST_IDLE;
                    end else begin
                        pc    <= pc + 8'd1;
                        state <= ST_FETCH;
                    end
                end

                ST_WAIT: begin
                    if (out_valid && out_ready) begin
                        out_valid <= 1'b0;
                        if (ck_count)
                            ck_acc <= ck_xor ? (ck_acc ^ out_byte) : (ck_acc + out_byte);
                        state <= ret_state;
                    end
                end

                ST_DEC_CONV: begin
                    bcd        <= {bcd_adjusted[38:0], bin_shift[31]};
                    bin_shift  <= {bin_shift[30:0], 1'b0};
                    conv_count <= conv_count + 6'd1;
                    if (conv_count == 6'd31) begin
                        dig_k <= 4'd9;
                        state <= ST_DEC_SCAN;
                    end
                end

                ST_DEC_SCAN: begin
                    // Highest non-zero integer digit, or the units digit.
                    if ((digit_at_k != 4'd0) || (dig_k == {1'b0, dec_digits}))
                        state <= ST_DEC_SIGN;
                    else
                        dig_k <= dig_k - 4'd1;
                end

                ST_DEC_SIGN: begin
                    dig_frac <= 1'b0;
                    if (dec_negative) emit(8'h2d, ck_active, ST_DEC_DIG);
                    else state <= ST_DEC_DIG;
                end

                ST_DEC_DIG: begin
                    if (!dig_frac && (dig_k == {1'b0, dec_digits})) begin
                        // Last integer digit; a '.' follows when D > 0.
                        if (dec_digits == 3'd0) begin
                            emit({4'h3, digit_at_k}, ck_active, ST_NEXT);
                        end else begin
                            emit({4'h3, digit_at_k}, ck_active, ST_DEC_DOT);
                        end
                    end else if (dig_frac && (dig_k == 4'd0)) begin
                        emit({4'h3, digit_at_k}, ck_active, ST_NEXT);
                    end else begin
                        emit({4'h3, digit_at_k}, ck_active, ST_DEC_DIG);
                        dig_k <= dig_k - 4'd1;
                    end
                end

                ST_DEC_DOT: begin
                    dig_frac <= 1'b1;
                    dig_k    <= {1'b0, dec_digits} - 4'd1;
                    emit(8'h2e, ck_active, ST_DEC_DIG);
                end

                ST_BIN_OUT: begin
                    if (bin_big_endian) begin
                        emit(bin_word[bin_index * 8 +: 8], ck_active,
                             (bin_index == 2'd0) ? ST_NEXT : ST_BIN_OUT);
                        bin_index <= bin_index - 2'd1;
                    end else begin
                        emit(bin_word[bin_index * 8 +: 8], ck_active,
                             (bin_index == bin_last) ? ST_NEXT : ST_BIN_OUT);
                        bin_index <= bin_index + 2'd1;
                    end
                end

                default: begin
                    state     <= ST_IDLE;
                    out_valid <= 1'b0;
                    error     <= 1'b1;
                end
            endcase
        end
    end

endmodule
