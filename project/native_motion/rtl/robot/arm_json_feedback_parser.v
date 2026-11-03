// ============================================================================
// Block Name : arm_json_feedback_parser
// Description: Streaming key/number parser for newline-terminated JSON
//              feedback lines (RoArm-M3 official path).  Byte-exact with
//              roarm_json_reference.JsonKeyLineParserModel.
//              Keys are configuration (7 slots x up to 15 bytes): slots 0..5
//              are position channels, slot 6 is an optional integer
//              discriminator.  Numbers are scaled to device units
//              value * 10^D with first-dropped-digit rounding (ties away).
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz)
//
// Resource plan:
// - Incremental key match: every key byte is compared with byte i of all
//   seven configured keys (7 cycles, key LUTRAM read by {slot, i}) and clears
//   the slot's bit in a 7-bit candidate mask.  The length compare and slot
//   priority are registered every cycle, so ':' uses a registered match.
//   No captured-key buffer and no per-key compare loop are needed.
// - Parsed values live in an 8 x 32 LUTRAM written at number finalization;
//   the watchdog reads a record channel by channel through rd_ch/rd_value.
//
// Timing contract:
// - Bytes pass a one-cycle input register (byte + character-class flags).
// - One byte per cycle except key bytes (7 cycles), number finalization
//   (<= 9 cycles) and end-of-line (1 cycle).  The backend enforces
//   clks_per_bit >= 16 (>= 160 cycles per byte).  A byte that still arrives
//   while busy is dropped, marks its line bad and pulses err_overrun.
// - rec_valid / line_ignored / err_parse / err_overrun are one-cycle pulses.
//   rd_value (masked by rec_mask) stays valid for >= 160 cycles after
//   rec_valid, i.e. until the next line writes a value.
//
// Supported subset (documented limitation): keyed decimal numbers anywhere
// in the line (nested objects are flattened), no arrays of positions, no
// exponent notation, keys without escapes, single-byte line terminator.
//
// Truth boundary: source candidate.  Supplementary Icarus Verilog run only;
// XSim/synthesis/implementation not run.
// ============================================================================

`timescale 1ns / 1ps

module arm_json_feedback_parser (
    input  wire         clk,
    input  wire         rst_n,

    input  wire         key_we,
    input  wire [6:0]   key_waddr,
    input  wire [7:0]   key_wdata,

    input  wire [27:0]  key_len_cfg,        // 7 x 4-bit key lengths, 0 = slot off
    input  wire [2:0]   frac_digits,        // D for slots 0..5 (0..6)
    input  wire [7:0]   line_term,
    input  wire [15:0]  max_line_len,
    input  wire [31:0]  disc_value,

    input  wire         byte_valid,
    input  wire [7:0]   byte_data,

    output reg          rec_valid,
    output wire [5:0]   rec_mask,
    input  wire [2:0]   rd_ch,
    output wire [31:0]  rd_value,
    output reg          line_ignored,
    output reg          err_parse,
    output reg          err_overrun
);

    localparam [3:0] ST_SCAN      = 4'd0;
    localparam [3:0] ST_KEY       = 4'd1;
    localparam [3:0] ST_KEY_ESC   = 4'd2;
    localparam [3:0] ST_AFTER_KEY = 4'd3;
    localparam [3:0] ST_VALUE_WS  = 4'd4;
    localparam [3:0] ST_VALUE_INT = 4'd5;
    localparam [3:0] ST_VALUE_FRC = 4'd6;
    localparam [3:0] ST_SKIP      = 4'd7;
    localparam [3:0] ST_KEY_CMP   = 4'd8;
    localparam [3:0] ST_FIN_SCALE = 4'd9;
    localparam [3:0] ST_FIN_ROUND = 4'd10;
    localparam [3:0] ST_FIN_STORE = 4'd11;
    localparam [3:0] ST_EOL       = 4'd12;

    localparam [35:0] LIMIT_2P32 = 36'h1_0000_0000;

    (* ram_style = "distributed" *) reg [7:0]  key_ram [0:127];
    (* ram_style = "distributed" *) reg [31:0] val_mem [0:7];

    reg [3:0]   state;
    reg [16:0]  line_len;
    reg         line_bad;
    reg [6:0]   seen;

    reg [6:0]   key_mask;            // slots still matching the captured prefix
    reg [7:0]   key_byte;
    reg [3:0]   cap_len;
    reg         key_bad;
    reg [2:0]   cmp_slot;

    reg [2:0]   slot;
    reg         neg;
    reg [35:0]  acc;
    reg [3:0]   int_digits;
    reg [2:0]   frac_count;          // 0..7 (7 = one dropped digit seen)
    reg [3:0]   round_digit;
    reg         got_digit;
    reg         value_overflow;
    reg         pending_eol;

    // The value is written in the ST_FIN_STORE cycle itself, so ST_EOL (the
    // next state) already reads it, e.g. a discriminator right before the
    // line terminator.
    wire        val_store_ok = !(value_overflow ||
                                 (neg  && (acc > 36'h0_8000_0000)) ||
                                 (!neg && (acc > 36'h0_7fff_ffff)));
    wire        val_we    = (state == ST_FIN_STORE) && val_store_ok;
    wire [2:0]  val_waddr = slot;
    wire [31:0] val_wdata = neg ? (32'd0 - acc[31:0]) : acc[31:0];

    // Configuration-time contents of the value table (FPGA RAM init).
    integer init_i;
    initial begin
        for (init_i = 0; init_i < 8; init_i = init_i + 1)
            val_mem[init_i] = 32'd0;
    end

    // Reset-free write ports so both tables infer distributed RAM.
    always @(posedge clk) begin
        if (key_we)
            key_ram[key_waddr] <= key_wdata;
        if (val_we)
            val_mem[val_waddr] <= val_wdata;
    end

    wire busy_state = (state == ST_KEY_CMP) || (state == ST_FIN_SCALE) ||
                      (state == ST_FIN_ROUND) || (state == ST_FIN_STORE) ||
                      (state == ST_EOL);

    // Input stage: the received byte and its character classes are
    // registered, so the FSM decides on one-bit flags instead of decoding raw
    // port bits in the same cycle (one cycle of latency, still one byte per
    // cycle of throughput).
    reg        in_valid;
    reg  [7:0] in_byte;
    reg        is_digit, is_ws, is_stop, is_quote, is_bslash, is_colon, is_minus, is_dot, is_term;
    wire [3:0] digit   = in_byte[3:0];
    wire       port_ws = (byte_data == 8'h20) || (byte_data == 8'h09) || (byte_data == 8'h0d);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            in_valid  <= 1'b0;
            in_byte   <= 8'd0;
            is_digit  <= 1'b0;
            is_ws     <= 1'b0;
            is_stop   <= 1'b0;
            is_quote  <= 1'b0;
            is_bslash <= 1'b0;
            is_colon  <= 1'b0;
            is_minus  <= 1'b0;
            is_dot    <= 1'b0;
            is_term   <= 1'b0;
        end else begin
            in_valid  <= byte_valid;
            in_byte   <= byte_data;
            is_digit  <= (byte_data >= 8'h30) && (byte_data <= 8'h39);
            is_ws     <= port_ws;
            is_stop   <= port_ws || (byte_data == 8'h2c) || (byte_data == 8'h7d) || (byte_data == 8'h5d);
            is_quote  <= (byte_data == 8'h22);
            is_bslash <= (byte_data == 8'h5c);
            is_colon  <= (byte_data == 8'h3a);
            is_minus  <= (byte_data == 8'h2d);
            is_dot    <= (byte_data == 8'h2e);
            is_term   <= (byte_data == line_term);
        end
    end

    wire [2:0] slot_digits = (slot == 3'd6) ? 3'd0 : frac_digits;

    // acc * 10 + digit with explicit widths.
    wire [35:0] acc_times10 = {acc[32:0], 3'b000} + {acc[34:0], 1'b0};
    wire [35:0] acc_digit   = acc_times10 + {32'd0, digit};

    wire [16:0] line_len_next = (line_len == 17'h1ffff) ? line_len : (line_len + 17'd1);

    // Incremental compare of the captured byte against byte cap_len of a slot.
    wire [3:0] cmp_len  = key_len_cfg[cmp_slot * 4 +: 4];
    wire [7:0] cmp_byte = key_ram[{cmp_slot, cap_len}];
    wire       cmp_keep = (cap_len < cmp_len) && (cmp_byte == key_byte);

    // Match resolution.  match_slot/match_found are registered every cycle
    // from key_mask and cap_len: both are final when the closing quote is
    // accepted, at least one cycle before ':' is processed in ST_AFTER_KEY,
    // so the length compare and the priority select never share a path
    // with the byte decode.
    reg [6:0] len_equal;
    reg [2:0] match_slot_d;
    reg       match_found_d;
    reg [2:0] match_slot;
    reg       match_found;
    integer   s;
    always @(*) begin
        for (s = 0; s < 7; s = s + 1)
            len_equal[s] = (key_len_cfg[s * 4 +: 4] == cap_len) && (key_len_cfg[s * 4 +: 4] != 4'd0);
        match_slot_d  = 3'd0;
        match_found_d = 1'b0;
        for (s = 6; s >= 0; s = s - 1)
            if (key_mask[s] && len_equal[s]) begin
                match_slot_d  = s[2:0];
                match_found_d = 1'b1;
            end
    end

    // End-of-line classification (same decision table as the Python model).
    // Slot enables are registered (configuration is static while the backend
    // runs); the discriminator compare is registered when slot 6 is stored.
    wire [5:0] pos_enabled_d;
    genvar g;
    generate
        for (g = 0; g < 6; g = g + 1) begin : g_pos_enabled
            assign pos_enabled_d[g] = (key_len_cfg[g * 4 +: 4] != 4'd0);
        end
    endgenerate
    reg  [5:0] pos_enabled;
    reg        disc_enabled;
    reg        disc_match;
    wire [5:0] seen_pos     = seen[5:0] & pos_enabled;
    wire       disc_ok      = seen[6] && disc_match;

    assign rec_mask = pos_enabled;
    assign rd_value = pos_enabled[rd_ch] ? val_mem[rd_ch] : 32'd0;

    reg eol_record, eol_ignore;
    always @(*) begin
        eol_record = 1'b0;
        eol_ignore = 1'b0;
        if (disc_enabled) begin
            if (!disc_ok)
                eol_ignore = 1'b1;
            else if (!line_bad && (seen_pos == pos_enabled))
                eol_record = 1'b1;
        end else begin
            if (!line_bad && (seen_pos == 6'd0))
                eol_ignore = 1'b1;
            else if (!line_bad && (seen_pos == pos_enabled))
                eol_record = 1'b1;
        end
    end

    task reset_value;
        begin
            neg            <= 1'b0;
            acc            <= 36'd0;
            int_digits     <= 4'd0;
            frac_count     <= 3'd0;
            round_digit    <= 4'd0;
            got_digit      <= 1'b0;
            value_overflow <= 1'b0;
        end
    endtask

    task start_key;
        begin
            cap_len  <= 4'd0;
            key_bad  <= 1'b0;
            key_mask <= 7'h7f;
            state    <= ST_KEY;
        end
    endtask

    task integer_digit;
        begin
            got_digit <= 1'b1;
            if (int_digits >= 4'd10) begin
                value_overflow <= 1'b1;
            end else begin
                int_digits <= int_digits + 4'd1;
                if (!value_overflow) begin
                    acc <= acc_digit;
                    if (acc_digit >= LIMIT_2P32)
                        value_overflow <= 1'b1;
                end
            end
        end
    endtask

    task fraction_digit;
        begin
            got_digit <= 1'b1;
            if (frac_count < slot_digits) begin
                frac_count <= frac_count + 3'd1;
                if (!value_overflow) begin
                    acc <= acc_digit;
                    if (acc_digit >= LIMIT_2P32)
                        value_overflow <= 1'b1;
                end
            end else if (frac_count == slot_digits) begin
                round_digit <= digit;
                frac_count  <= frac_count + 3'd1;
            end
        end
    endtask

    // Close a number: no digit -> bad line; otherwise start finalization.
    task close_number;
        input eol_after;
        begin
            pending_eol <= eol_after;
            if (!got_digit) begin
                line_bad <= 1'b1;
                reset_value;
                state    <= eol_after ? ST_EOL : ST_SCAN;
            end else begin
                if (frac_count > slot_digits)
                    frac_count <= slot_digits;
                state <= ST_FIN_SCALE;
            end
        end
    endtask

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state        <= ST_SCAN;
            line_len     <= 17'd0;
            line_bad     <= 1'b0;
            seen         <= 7'd0;
            key_mask     <= 7'd0;
            key_byte     <= 8'd0;
            cap_len      <= 4'd0;
            key_bad      <= 1'b0;
            cmp_slot     <= 3'd0;
            slot         <= 3'd0;
            pending_eol  <= 1'b0;
            rec_valid    <= 1'b0;
            line_ignored <= 1'b0;
            err_parse    <= 1'b0;
            err_overrun  <= 1'b0;
            match_slot   <= 3'd0;
            match_found  <= 1'b0;
            pos_enabled  <= 6'd0;
            disc_enabled <= 1'b0;
            disc_match   <= 1'b0;
            reset_value;
        end else begin
            rec_valid    <= 1'b0;
            line_ignored <= 1'b0;
            err_parse    <= 1'b0;
            err_overrun  <= 1'b0;
            match_slot   <= match_slot_d;
            match_found  <= match_found_d;
            pos_enabled  <= pos_enabled_d;
            disc_enabled <= (key_len_cfg[27:24] != 4'd0);

            if (busy_state) begin
                case (state)
                    ST_KEY_CMP: begin
                        if (!cmp_keep)
                            key_mask[cmp_slot] <= 1'b0;
                        if (cmp_slot == 3'd6) begin
                            cap_len <= cap_len + 4'd1;
                            state   <= ST_KEY;
                        end else begin
                            cmp_slot <= cmp_slot + 3'd1;
                        end
                    end

                    ST_FIN_SCALE: begin
                        if (!value_overflow && (frac_count < slot_digits)) begin
                            acc        <= acc_times10;
                            frac_count <= frac_count + 3'd1;
                            if (acc_times10 >= LIMIT_2P32)
                                value_overflow <= 1'b1;
                        end else begin
                            state <= ST_FIN_ROUND;
                        end
                    end

                    ST_FIN_ROUND: begin
                        if (!value_overflow && (round_digit >= 4'd5))
                            acc <= acc + 36'd1;
                        state <= ST_FIN_STORE;
                    end

                    ST_FIN_STORE: begin
                        if (!val_store_ok)
                            line_bad <= 1'b1;
                        else
                            seen[slot] <= 1'b1;
                        if (val_store_ok && (slot == 3'd6))
                            disc_match <= (val_wdata == disc_value);
                        reset_value;
                        state <= pending_eol ? ST_EOL : ST_SCAN;
                    end

                    default: begin   // ST_EOL
                        if (eol_record)
                            rec_valid <= 1'b1;
                        else if (eol_ignore)
                            line_ignored <= 1'b1;
                        else
                            err_parse <= 1'b1;
                        line_len    <= 17'd0;
                        line_bad    <= 1'b0;
                        seen        <= 7'd0;
                        disc_match  <= 1'b0;
                        pending_eol <= 1'b0;
                        key_bad     <= 1'b0;
                        cap_len     <= 4'd0;
                        reset_value;
                        state       <= ST_SCAN;
                    end
                endcase
                // Placed after the case so an overrun during ST_EOL marks the
                // next line bad instead of being cleared by the line reset.
                if (in_valid) begin
                    line_bad    <= 1'b1;
                    err_overrun <= 1'b1;
                end
            end else if (in_valid) begin
                line_len <= line_len_next;
                if (is_term) begin
                    if ((state == ST_VALUE_INT) || (state == ST_VALUE_FRC)) begin
                        close_number(1'b1);
                    end else begin
                        if (state == ST_VALUE_WS)
                            line_bad <= 1'b1;
                        state <= ST_EOL;
                    end
                end else if (line_len_next > {1'b0, max_line_len}) begin
                    line_bad <= 1'b1;
                    state    <= ST_SKIP;
                end else begin
                    case (state)
                        ST_SCAN: begin
                            if (is_quote)
                                start_key;
                        end

                        ST_KEY: begin
                            if (is_bslash) begin
                                key_bad <= 1'b1;
                                state   <= ST_KEY_ESC;
                            end else if (is_quote) begin
                                state <= ST_AFTER_KEY;
                            end else if (cap_len < 4'd15) begin
                                key_byte <= in_byte;
                                cmp_slot <= 3'd0;
                                state    <= ST_KEY_CMP;
                            end else begin
                                key_bad <= 1'b1;
                            end
                        end

                        ST_KEY_ESC: begin
                            state <= ST_KEY;
                        end

                        ST_AFTER_KEY: begin
                            if (is_ws) begin
                                state <= ST_AFTER_KEY;
                            end else if (is_colon) begin
                                if (key_bad || !match_found) begin
                                    state <= ST_SCAN;
                                end else if (seen[match_slot]) begin
                                    line_bad <= 1'b1;                  // duplicate key
                                    state    <= ST_SCAN;
                                end else begin
                                    slot  <= match_slot;
                                    reset_value;
                                    state <= ST_VALUE_WS;
                                end
                            end else if (is_quote) begin
                                start_key;
                            end else begin
                                state <= ST_SCAN;
                            end
                        end

                        ST_VALUE_WS: begin
                            if (is_ws) begin
                                state <= ST_VALUE_WS;
                            end else if (is_minus) begin
                                neg   <= 1'b1;
                                state <= ST_VALUE_INT;
                            end else if (is_digit) begin
                                integer_digit;
                                state <= ST_VALUE_INT;
                            end else begin
                                line_bad <= 1'b1;
                                state    <= ST_SCAN;
                            end
                        end

                        ST_VALUE_INT: begin
                            if (is_digit) begin
                                integer_digit;
                            end else if (is_dot) begin
                                if (!got_digit) begin
                                    line_bad <= 1'b1;
                                    state    <= ST_SCAN;
                                end else begin
                                    got_digit <= 1'b0;
                                    state     <= ST_VALUE_FRC;
                                end
                            end else if (is_stop) begin
                                close_number(1'b0);
                            end else begin
                                line_bad <= 1'b1;
                                state    <= ST_SCAN;
                            end
                        end

                        ST_VALUE_FRC: begin
                            if (is_digit) begin
                                fraction_digit;
                            end else if (is_stop) begin
                                close_number(1'b0);
                            end else begin
                                line_bad <= 1'b1;
                                state    <= ST_SCAN;
                            end
                        end

                        default: begin   // ST_SKIP
                            state <= ST_SKIP;
                        end
                    endcase
                end
            end
        end
    end

endmodule
