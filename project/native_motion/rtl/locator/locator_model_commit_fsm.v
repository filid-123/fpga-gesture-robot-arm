// ============================================================================
// Validates model/descriptor length, non-zero versions and CRC-32.
// Memory read ports are synchronous with one registered data output.
// ============================================================================
`timescale 1ns / 1ps

module locator_model_commit_fsm #(
    parameter [31:0] MODEL_WORDS_REQUIRED = 32'd1904,
    parameter [31:0] DESC_WORDS_MAX       = 32'd1024,
    parameter [7:0]  ERR_LENGTH           = 8'h0A,
    parameter [7:0]  ERR_VERSION          = 8'h0B,
    parameter [7:0]  ERR_CRC              = 8'h0C
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    input  wire        abort,
    input  wire [31:0] model_word_count,
    input  wire [31:0] desc_word_count,
    input  wire [31:0] expected_model_crc,
    input  wire [31:0] expected_desc_crc,
    input  wire [31:0] model_version,
    input  wire [31:0] desc_version,

    output reg         model_rd_en,
    output reg  [10:0] model_rd_addr,
    input  wire [31:0] model_rd_data,
    output reg         desc_rd_en,
    output reg  [9:0]  desc_rd_addr,
    input  wire [31:0] desc_rd_data,

    output reg         busy,
    output reg         done,
    output reg         success,
    output reg  [7:0]  error_code,
    output reg  [31:0] computed_model_crc,
    output reg  [31:0] computed_desc_crc
);

    localparam S_IDLE         = 4'd0;
    localparam S_MODEL_INIT   = 4'd1;
    localparam S_MODEL_SCAN   = 4'd2;
    localparam S_MODEL_FINISH = 4'd3;
    localparam S_MODEL_WAIT   = 4'd4;
    localparam S_DESC_INIT    = 4'd5;
    localparam S_DESC_SCAN    = 4'd6;
    localparam S_DESC_FINISH  = 4'd7;
    localparam S_DESC_WAIT    = 4'd8;

    reg [3:0]  state;
    reg [10:0] issue_count;
    reg [10:0] feed_count;
    reg        rd_valid_d;

    reg        crc_init;
    reg        crc_data_valid;
    reg [31:0] crc_data_word;
    reg        crc_finish;
    wire [31:0] crc_result;
    wire        crc_result_valid;

    locator_crc32 u_crc32 (
        .clk(clk),
        .rst_n(rst_n),
        .init(crc_init),
        .data_valid(crc_data_valid),
        .data_word(crc_data_word),
        .byte_count(3'd4),
        .finish(crc_finish),
        .crc_out(crc_result),
        .crc_valid(crc_result_valid)
    );

    always @(posedge clk) begin
        if (!rst_n) begin
            state               <= S_IDLE;
            issue_count         <= 11'd0;
            feed_count          <= 11'd0;
            rd_valid_d          <= 1'b0;
            model_rd_en         <= 1'b0;
            model_rd_addr       <= 11'd0;
            desc_rd_en          <= 1'b0;
            desc_rd_addr        <= 10'd0;
            crc_init            <= 1'b0;
            crc_data_valid      <= 1'b0;
            crc_data_word       <= 32'd0;
            crc_finish          <= 1'b0;
            busy                <= 1'b0;
            done                <= 1'b0;
            success             <= 1'b0;
            error_code          <= 8'd0;
            computed_model_crc  <= 32'd0;
            computed_desc_crc   <= 32'd0;
        end else if (abort) begin
            state          <= S_IDLE;
            issue_count    <= 11'd0;
            feed_count     <= 11'd0;
            rd_valid_d     <= 1'b0;
            model_rd_en    <= 1'b0;
            desc_rd_en     <= 1'b0;
            crc_init       <= 1'b0;
            crc_data_valid <= 1'b0;
            crc_finish     <= 1'b0;
            busy           <= 1'b0;
            done           <= 1'b0;
            success        <= 1'b0;
        end else begin
            done           <= 1'b0;
            model_rd_en    <= 1'b0;
            desc_rd_en     <= 1'b0;
            crc_init       <= 1'b0;
            crc_data_valid <= 1'b0;
            crc_finish     <= 1'b0;

            case (state)
                S_IDLE: begin
                    busy       <= 1'b0;
                    rd_valid_d <= 1'b0;
                    if (start) begin
                        success    <= 1'b0;
                        error_code <= 8'd0;
                        if ((model_word_count != MODEL_WORDS_REQUIRED) ||
                            (desc_word_count == 0) ||
                            (desc_word_count > DESC_WORDS_MAX)) begin
                            done       <= 1'b1;
                            error_code <= ERR_LENGTH;
                        end else if ((model_version == 0) || (desc_version == 0)) begin
                            done       <= 1'b1;
                            error_code <= ERR_VERSION;
                        end else begin
                            busy  <= 1'b1;
                            state <= S_MODEL_INIT;
                        end
                    end
                end

                S_MODEL_INIT: begin
                    crc_init    <= 1'b1;
                    issue_count <= 11'd0;
                    feed_count  <= 11'd0;
                    rd_valid_d  <= 1'b0;
                    state       <= S_MODEL_SCAN;
                end

                S_MODEL_SCAN: begin
                    rd_valid_d <= model_rd_en;
                    if (issue_count < model_word_count[10:0]) begin
                        model_rd_en   <= 1'b1;
                        model_rd_addr <= issue_count;
                        issue_count   <= issue_count + 11'd1;
                    end
                    if (rd_valid_d) begin
                        crc_data_valid <= 1'b1;
                        crc_data_word  <= model_rd_data;
                        feed_count     <= feed_count + 11'd1;
                        if ((feed_count + 11'd1) == model_word_count[10:0])
                            state <= S_MODEL_FINISH;
                    end
                end

                S_MODEL_FINISH: begin
                    crc_finish <= 1'b1;
                    state      <= S_MODEL_WAIT;
                end

                S_MODEL_WAIT: begin
                    if (crc_result_valid) begin
                        computed_model_crc <= crc_result;
                        state              <= S_DESC_INIT;
                    end
                end

                S_DESC_INIT: begin
                    crc_init    <= 1'b1;
                    issue_count <= 11'd0;
                    feed_count  <= 11'd0;
                    rd_valid_d  <= 1'b0;
                    state       <= S_DESC_SCAN;
                end

                S_DESC_SCAN: begin
                    rd_valid_d <= desc_rd_en;
                    if (issue_count < desc_word_count[10:0]) begin
                        desc_rd_en   <= 1'b1;
                        desc_rd_addr <= issue_count[9:0];
                        issue_count  <= issue_count + 11'd1;
                    end
                    if (rd_valid_d) begin
                        crc_data_valid <= 1'b1;
                        crc_data_word  <= desc_rd_data;
                        feed_count     <= feed_count + 11'd1;
                        if ((feed_count + 11'd1) == desc_word_count[10:0])
                            state <= S_DESC_FINISH;
                    end
                end

                S_DESC_FINISH: begin
                    crc_finish <= 1'b1;
                    state      <= S_DESC_WAIT;
                end

                S_DESC_WAIT: begin
                    if (crc_result_valid) begin
                        computed_desc_crc <= crc_result;
                        busy              <= 1'b0;
                        done              <= 1'b1;
                        state             <= S_IDLE;
                        if ((computed_model_crc == expected_model_crc) &&
                            (crc_result == expected_desc_crc)) begin
                            success    <= 1'b1;
                            error_code <= 8'd0;
                        end else begin
                            success    <= 1'b0;
                            error_code <= ERR_CRC;
                        end
                    end
                end

                default: begin
                    state <= S_IDLE;
                    busy  <= 1'b0;
                end
            endcase
        end
    end

endmodule
