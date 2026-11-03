// ============================================================================
// CRC-32/ISO-HDLC byte-stream engine.
// Bytes inside data_word are consumed little-endian: [7:0] first.
// poly(reflected)=0xEDB88320, init=0xFFFFFFFF, xorout=0xFFFFFFFF.
// ============================================================================
`timescale 1ns / 1ps

module locator_crc32 (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        init,
    input  wire        data_valid,
    input  wire [31:0] data_word,
    input  wire [2:0]  byte_count,
    input  wire        finish,
    output reg  [31:0] crc_out,
    output reg         crc_valid
);

    reg [31:0] crc_state;

    function [31:0] crc32_byte;
        input [31:0] crc_in;
        input [7:0]  data_in;
        reg   [31:0] c;
        integer i;
        begin
            c = crc_in ^ {24'd0, data_in};
            for (i = 0; i < 8; i = i + 1) begin
                if (c[0])
                    c = (c >> 1) ^ 32'hEDB8_8320;
                else
                    c = c >> 1;
            end
            crc32_byte = c;
        end
    endfunction

    function [31:0] crc32_word_n;
        input [31:0] crc_in;
        input [31:0] data_in;
        input [2:0]  count_in;
        reg   [31:0] c;
        begin
            c = crc_in;
            if (count_in >= 1) c = crc32_byte(c, data_in[7:0]);
            if (count_in >= 2) c = crc32_byte(c, data_in[15:8]);
            if (count_in >= 3) c = crc32_byte(c, data_in[23:16]);
            if (count_in >= 4) c = crc32_byte(c, data_in[31:24]);
            crc32_word_n = c;
        end
    endfunction

    always @(posedge clk) begin
        if (!rst_n) begin
            crc_state <= 32'hFFFF_FFFF;
            crc_out   <= 32'd0;
            crc_valid <= 1'b0;
        end else begin
            crc_valid <= 1'b0;
            if (init) begin
                crc_state <= 32'hFFFF_FFFF;
            end else if (data_valid) begin
                crc_state <= crc32_word_n(crc_state, data_word, byte_count);
            end else if (finish) begin
                crc_out   <= crc_state ^ 32'hFFFF_FFFF;
                crc_valid <= 1'b1;
            end
        end
    end

endmodule
