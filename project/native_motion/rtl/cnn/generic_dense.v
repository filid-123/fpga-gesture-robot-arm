`timescale 1ns / 1ps

module generic_dense (
    input  wire        clk,
    input  wire        rst_n,

    input  wire        start,
    output reg         busy,
    output reg         done,

    input  wire [15:0] Cin,
    input  wire [8:0]  Cout,
    input  wire [31:0] weight_offset,
    input  wire [31:0] bias_offset,
    input  wire [31:0] quant_M,
    input  wire [7:0]  quant_shift,
    input  wire        is_final_layer,

    output reg         w_bram_en,
    output reg  [15:0] w_bram_addr,
    input  wire [7:0]  w_bram_data,

    output reg         src_bram_en,
    output reg  [13:0] src_bram_addr,
    input  wire [7:0]  src_bram_data,

    output reg         dst_bram_en,
    output reg  [13:0] dst_bram_addr,
    output reg  [7:0]  dst_bram_data,
    
    // For final layer logits
    output reg  [8:0]  final_class_id,
    output reg         logits_valid
);

    localparam S_IDLE           = 0;
    localparam S_LOAD_BIAS      = 1;
    localparam S_LOAD_BIAS_LAT  = 2;
    localparam S_LOAD_BIAS_WAIT = 3;
    localparam S_COMPUTE        = 4;
    localparam S_COMPUTE_LAT    = 5;
    localparam S_COMPUTE_ACC    = 6;
    localparam S_REQUANT        = 7;
    localparam S_NEXT_CO        = 8;
    localparam S_DONE           = 9;

    reg [3:0] state;
    reg [8:0] cur_co;
    reg [15:0] cur_ci;
    reg [3:0] byte_cnt;

    reg signed [31:0] cur_bias;
    reg signed [31:0] acc;

    // Argmax tracking
    reg signed [31:0] max_logit;
    reg [8:0]         max_id;

    wire signed [63:0] rq_round = (quant_shift > 0) ? (64'sd1 << (quant_shift - 1)) : 64'sd0;
    wire signed [63:0] rq_mult_comb = $signed(acc) * $signed(quant_M);
    wire signed [63:0] rq_shifted_comb = (rq_mult_comb + rq_round) >>> quant_shift;
    wire [7:0] rq_clamped_comb =
        (rq_shifted_comb < 64'sd0)   ? 8'd0 :
        (rq_shifted_comb > 64'sd255) ? 8'd255 : rq_shifted_comb[7:0];

    always @(posedge clk) begin
        if (!rst_n) begin
            state <= S_IDLE;
            busy <= 0;
            done <= 0;
            w_bram_en <= 0;
            src_bram_en <= 0;
            dst_bram_en <= 0;
            logits_valid <= 0;
        end else begin
            w_bram_en <= 0;
            src_bram_en <= 0;
            dst_bram_en <= 0;
            logits_valid <= 0;

            case (state)
                S_IDLE: begin
                    done <= 0;
                    logits_valid <= 0;
                    if (start) begin
                        busy <= 1;
                        cur_co <= 0;
                        cur_ci <= 0;
                        byte_cnt <= 0;
                        max_logit <= 32'h80000000; // Minimum signed 32-bit integer (-2147483648)
                        max_id <= 0;
                        state <= S_LOAD_BIAS;
                    end
                end

                S_LOAD_BIAS: begin
                    if (byte_cnt == 4) begin
                        $display("[%0t] [DENSE] Loading Bias for cur_co: %d. cur_bias = %h", $time, cur_co, cur_bias);
                        acc <= cur_bias;
                        state <= S_COMPUTE;
                    end else begin
                        w_bram_en <= 1;
                        w_bram_addr <= bias_offset + cur_co * 4 + byte_cnt;
                        state <= S_LOAD_BIAS_LAT;
                    end
                end

                S_LOAD_BIAS_LAT: begin
                    state <= S_LOAD_BIAS_WAIT;
                end

                S_LOAD_BIAS_WAIT: begin
                    case (byte_cnt)
                        0: cur_bias[7:0]   <= w_bram_data;
                        1: cur_bias[15:8]  <= w_bram_data;
                        2: cur_bias[23:16] <= w_bram_data;
                        3: cur_bias[31:24] <= w_bram_data;
                        default: ;
                    endcase
                    byte_cnt <= byte_cnt + 1;
                    state <= S_LOAD_BIAS;
                end

                S_COMPUTE: begin
                    if (cur_ci == Cin) begin
                        state <= S_REQUANT;
                    end else begin
                        w_bram_en <= 1;
                        w_bram_addr <= weight_offset + cur_co * Cin + cur_ci;
                        src_bram_en <= 1;
                        src_bram_addr <= cur_ci;
                        state <= S_COMPUTE_LAT;
                    end
                end

                S_COMPUTE_LAT: begin
                    state <= S_COMPUTE_ACC;
                end

                S_COMPUTE_ACC: begin
                    if (^w_bram_data === 1'bx || ^src_bram_data === 1'bx) begin
                        $display("[%0t] [DENSE] X DETECTED! w_data=%h, src_data=%h, cur_ci=%d, w_addr=%d, src_addr=%d", $time, w_bram_data, src_bram_data, cur_ci, w_bram_addr, src_bram_addr);
                    end
                    acc <= acc + $signed(w_bram_data) * $signed({1'b0, src_bram_data});
                    cur_ci <= cur_ci + 1;
                    state <= S_COMPUTE;
                end

                S_REQUANT: begin
                    if (is_final_layer) begin
                        $display("[%0t] [DENSE FINAL] cur_co: %d, acc: %d, max_logit before: %d", $time, cur_co, acc, max_logit);
                        // Compute Argmax on-the-fly!
                        if ($signed(acc) > $signed(max_logit)) begin
                            $display("[%0t] [DENSE FINAL] -> New Max Logit! max_id updating to %d", $time, cur_co);
                            max_logit <= acc;
                            max_id <= cur_co;
                        end
                    end else begin
                        dst_bram_en <= 1;
                        dst_bram_addr <= cur_co;
                        dst_bram_data <= rq_clamped_comb;
                    end
                    state <= S_NEXT_CO;
                end

                S_NEXT_CO: begin
                    if (cur_co == Cout - 1) begin
                        state <= S_DONE;
                    end else begin
                        cur_co <= cur_co + 1;
                        cur_ci <= 0;
                        byte_cnt <= 0;
                        state <= S_LOAD_BIAS;
                    end
                end

                S_DONE: begin
                    busy <= 0;
                    done <= 1;
                    if (is_final_layer) begin
                        final_class_id <= max_id;
                        logits_valid <= 1;
                    end
                    state <= S_IDLE;
                end
                default: begin
                    state <= S_IDLE;
                    busy <= 1'b0;
                    done <= 1'b0;
                end
            endcase
        end
    end

endmodule
