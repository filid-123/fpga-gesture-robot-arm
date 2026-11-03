// ============================================================================
// Block Name : arm_so101_status_parser
// Description: Streaming parser for Feetech-style status packets, byte-exact
//              with so101_feetech_reference.StatusStreamParserModel:
//                HDR0 HDR1 ID LEN ERR PARAM[LEN-2] CK
//                CK = ck_invert ? ~sum8(ID..PARAM) : sum8(ID..PARAM)
//              Header bytes, parameter count, position encoding and endian
//              come from configuration (protocol file); the structure itself
//              is a documented assumption pending official confirmation.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz)
//
// Outputs are single-cycle pulses:
//   pkt_valid      : checksum OK, ID == expected_id, param count == expected
//   err_checksum   : checksum mismatch
//   err_protocol   : LEN outside 2..(2+MAX_PARAMS), wrong ID or param count
// flush resynchronizes to HUNT0 (the backend flushes before each request).
// One state step per received byte; no multi-cycle processing, so no overrun.
//
// Truth boundary: source candidate.  Supplementary Icarus Verilog run only;
// XSim/synthesis/implementation not run.
// ============================================================================

`timescale 1ns / 1ps

module arm_so101_status_parser (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        flush,
    input  wire        byte_valid,
    input  wire [7:0]  byte_data,

    input  wire [7:0]  hdr0,
    input  wire [7:0]  hdr1,
    input  wire [7:0]  expected_id,
    input  wire [2:0]  expected_nparams,
    input  wire [1:0]  pos_encoding,
    input  wire        big_endian,
    input  wire        ck_invert,

    output reg         pkt_valid,
    output reg  [7:0]  pkt_id,
    output reg  [7:0]  pkt_err,
    output reg  signed [31:0] pkt_value,
    output reg         err_checksum,
    output reg         err_protocol
);

    localparam integer MAX_PARAMS = 4;

    localparam [2:0] ST_HUNT0 = 3'd0;
    localparam [2:0] ST_HUNT1 = 3'd1;
    localparam [2:0] ST_ID    = 3'd2;
    localparam [2:0] ST_LEN   = 3'd3;
    localparam [2:0] ST_ERR   = 3'd4;
    localparam [2:0] ST_PARAM = 3'd5;
    localparam [2:0] ST_CK    = 3'd6;

    reg [2:0]  state;
    reg [7:0]  id_reg;
    reg [7:0]  len_reg;
    reg [7:0]  err_reg;
    reg [7:0]  sum;
    reg [2:0]  nparams;
    reg [7:0]  param0;
    reg [7:0]  param1;

    wire [7:0] expected_ck = ck_invert ? ~sum : sum;

    // 16-bit position decode of the first two parameters.
    wire [15:0] raw16 = big_endian ? {param0, param1} : {param1, param0};
    reg signed [31:0] decoded;
    always @(*) begin
        case (pos_encoding)
            2'd0:    decoded = {{16{raw16[15]}}, raw16};                       // two's complement
            2'd1:    decoded = {16'd0, raw16};                                 // unsigned
            default: decoded = raw16[15] ? -$signed({17'd0, raw16[14:0]})     // sign-magnitude
                                         :  $signed({17'd0, raw16[14:0]});
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state        <= ST_HUNT0;
            id_reg       <= 8'd0;
            len_reg      <= 8'd0;
            err_reg      <= 8'd0;
            sum          <= 8'd0;
            nparams      <= 3'd0;
            param0       <= 8'd0;
            param1       <= 8'd0;
            pkt_valid    <= 1'b0;
            pkt_id       <= 8'd0;
            pkt_err      <= 8'd0;
            pkt_value    <= 32'sd0;
            err_checksum <= 1'b0;
            err_protocol <= 1'b0;
        end else begin
            pkt_valid    <= 1'b0;
            err_checksum <= 1'b0;
            err_protocol <= 1'b0;

            if (flush) begin
                state <= ST_HUNT0;
            end else if (byte_valid) begin
                case (state)
                    ST_HUNT0: begin
                        if (byte_data == hdr0)
                            state <= ST_HUNT1;
                    end

                    ST_HUNT1: begin
                        if (byte_data == hdr1)
                            state <= ST_ID;
                        else if (byte_data != hdr0)
                            state <= ST_HUNT0;
                    end

                    ST_ID: begin
                        // Repeated identical header bytes are skipped.
                        if (!((byte_data == hdr1) && (hdr0 == hdr1))) begin
                            id_reg <= byte_data;
                            sum    <= byte_data;
                            state  <= ST_LEN;
                        end
                    end

                    ST_LEN: begin
                        if ((byte_data < 8'd2) || (byte_data > (8'd2 + MAX_PARAMS))) begin
                            err_protocol <= 1'b1;
                            pkt_id       <= id_reg;
                            state        <= ST_HUNT0;
                        end else begin
                            len_reg <= byte_data;
                            sum     <= sum + byte_data;
                            state   <= ST_ERR;
                        end
                    end

                    ST_ERR: begin
                        err_reg <= byte_data;
                        sum     <= sum + byte_data;
                        nparams <= 3'd0;
                        state   <= (len_reg > 8'd2) ? ST_PARAM : ST_CK;
                    end

                    ST_PARAM: begin
                        if (nparams == 3'd0) param0 <= byte_data;
                        if (nparams == 3'd1) param1 <= byte_data;
                        sum     <= sum + byte_data;
                        nparams <= nparams + 3'd1;
                        if ({5'd0, nparams + 3'd1} == (len_reg - 8'd2))
                            state <= ST_CK;
                    end

                    ST_CK: begin
                        pkt_id <= id_reg;
                        if (byte_data != expected_ck) begin
                            err_checksum <= 1'b1;
                        end else if ((id_reg != expected_id) || (nparams != expected_nparams)) begin
                            err_protocol <= 1'b1;
                        end else begin
                            pkt_valid <= 1'b1;
                            pkt_err   <= err_reg;
                            pkt_value <= (expected_nparams == 3'd2) ? decoded : 32'sd0;
                        end
                        state <= ST_HUNT0;
                    end

                    default: state <= ST_HUNT0;
                endcase
            end
        end
    end

endmodule
