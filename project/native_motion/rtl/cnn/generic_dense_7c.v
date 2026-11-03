// ============================================================================
// Block Name : generic_dense_7c
// Description: Dense engine of the Phase 3 S3 classifier core (cnn_core_7c).
//              Datapath, BRAM timing and requant are identical to
//              generic_dense.v (unchanged, used by the four-class build); the
//              final layer additionally keeps the runner-up logit:
//                final_class_id = argmax over Cout int32 logits, strict '>'
//                                 from index 0 up (ties -> lowest index);
//                final_margin   = top1 - top2 saturated to 0..65535
//                                 (0 on a tie; with Cout == 1 the runner-up
//                                 stays INT32_MIN).
//              Output count comes from the descriptor (Cout), e.g. 7 for the
//              seven-class model; no class-count constant in this module.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (classifier clock, 50 MHz in the autonomous top)
// Bit-exact reference: model/gesture7/int_reference.py (dense, top1_margin).
// Truth boundary: source candidate; supplementary Icarus run only.
// ============================================================================
`timescale 1ns / 1ps

module generic_dense_7c #(parameter integer PIPELINED_REQUANT=0)(
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

    output reg  [8:0]  final_class_id,
    output reg  [15:0] final_margin,
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
    localparam S_WAIT_REQUANT   = 10;
    localparam S_MAC_PRODUCT    = 11;
    localparam S_MAC_ACCUMULATE = 12;

    reg [3:0] state;
    reg [8:0] cur_co;
    reg [15:0] cur_ci;
    reg [3:0] byte_cnt;

    reg signed [31:0] cur_bias;
    reg signed [31:0] acc;
    reg signed [7:0] mac_weight;
    reg [7:0] mac_pixel;
    reg signed [17:0] mac_product;

    // Top-1 / top-2 tracking over the final-layer logits.
    reg signed [31:0] max_logit;
    reg signed [31:0] second_logit;
    reg [8:0]         max_id;

    wire signed [63:0] rq_round = (quant_shift > 0) ? (64'sd1 << (quant_shift - 1)) : 64'sd0;
    wire signed [63:0] rq_mult_comb = $signed(acc) * $signed(quant_M);
    wire signed [63:0] rq_shifted_comb = (rq_mult_comb + rq_round) >>> quant_shift;
    wire [7:0] rq_clamped_comb =
        (rq_shifted_comb < 64'sd0)   ? 8'd0 :
        (rq_shifted_comb > 64'sd255) ? 8'd255 : rq_shifted_comb[7:0];
    wire rq_valid_out;
    wire [7:0] rq_pixel;
    generate if(PIPELINED_REQUANT!=0)begin:g_rq
        requant_fixed31_pipeline u_requant(.clk(clk),.rst_n(rst_n),
            .valid_in(state==S_REQUANT && !is_final_layer),.quant_M(quant_M),
            .acc_in(acc),.valid_out(rq_valid_out),.pixel_out(rq_pixel));
    end else begin:g_no_rq
        assign rq_valid_out=1'b0;assign rq_pixel=8'd0;
    end endgenerate

    // max_logit >= second_logit always, so the 33-bit difference is >= 0.
    wire signed [32:0] margin_wide = {max_logit[31], max_logit} - {second_logit[31], second_logit};
    wire [15:0] margin_sat = (margin_wide > 33'sd65535) ? 16'hFFFF : margin_wide[15:0];

    always @(posedge clk) begin
        if (!rst_n) begin
            state <= S_IDLE;
            busy <= 0;
            done <= 0;
            w_bram_en <= 0;
            src_bram_en <= 0;
            dst_bram_en <= 0;
            logits_valid <= 0;
            final_class_id <= 9'd0;
            final_margin <= 16'd0;
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
                        max_logit <= 32'h80000000;
                        second_logit <= 32'h80000000;
                        max_id <= 0;
                        state <= S_LOAD_BIAS;
                    end
                end

                S_LOAD_BIAS: begin
                    if (byte_cnt == 4) begin
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
                    if(PIPELINED_REQUANT!=0)begin
                        mac_weight<=w_bram_data;mac_pixel<=src_bram_data;
                        state<=S_MAC_PRODUCT;
                    end else begin
                        acc <= acc + $signed(w_bram_data) * $signed({1'b0, src_bram_data});
                        cur_ci <= cur_ci + 1;
                        state <= S_COMPUTE;
                    end
                end
                S_MAC_PRODUCT: begin
                    mac_product<=mac_weight*$signed({1'b0,mac_pixel});
                    state<=S_MAC_ACCUMULATE;
                end
                S_MAC_ACCUMULATE: begin
                    acc<=acc+$signed({{14{mac_product[17]}},mac_product});
                    cur_ci <= cur_ci + 1;
                    state <= S_COMPUTE;
                end

                S_REQUANT: begin
                    if (is_final_layer) begin
                        if ($signed(acc) > $signed(max_logit)) begin
                            second_logit <= max_logit;
                            max_logit <= acc;
                            max_id <= cur_co;
                        end else if ($signed(acc) > $signed(second_logit)) begin
                            second_logit <= acc;
                        end
                    end else if(PIPELINED_REQUANT==0)begin
                        dst_bram_en <= 1;
                        dst_bram_addr <= cur_co;
                        dst_bram_data <= rq_clamped_comb;
                    end
                    state <= (!is_final_layer && PIPELINED_REQUANT!=0)?S_WAIT_REQUANT:S_NEXT_CO;
                end
                S_WAIT_REQUANT:if(rq_valid_out)begin
                    dst_bram_en<=1;dst_bram_addr<=cur_co;dst_bram_data<=rq_pixel;state<=S_NEXT_CO;
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
                        final_margin <= margin_sat;
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
