`timescale 1ns / 1ps

module generic_conv3x3 #(
    parameter integer COUT_START=0, COUT_STEP=1,
    parameter integer PIPELINED_DOT=0,
    parameter integer SYNC_ACC_BRAM=PIPELINED_DOT
) (
    input  wire        clk,
    input  wire        rst_n,

    // Control
    input  wire        start,
    output reg         busy,
    output reg         done,

    // Layer Parameters (Static during execution)
    input  wire [15:0] Cin,
    input  wire [8:0]  Cout,
    input  wire [5:0]  InH,
    input  wire [5:0]  InW,
    input  wire [31:0] weight_offset,
    input  wire [31:0] bias_offset,
    input  wire [31:0] quant_M,
    input  wire [7:0]  quant_shift,

    // Weight BRAM Interface (Read-only, 8-bit)
    output reg         w_bram_en,
    output reg  [15:0] w_bram_addr,
    input  wire [7:0]  w_bram_data,

    // Activation Source BRAM (Read-only, 8-bit)
    output reg         src_bram_en,
    output reg  [13:0] src_bram_addr,
    input  wire [7:0]  src_bram_data,

    // Activation Dest BRAM (Write-only, 8-bit)
    output reg         dst_bram_en,
    output reg  [13:0] dst_bram_addr,
    output reg  [7:0]  dst_bram_data
);

    // ======================================================================
    // FSM States
    // ======================================================================
    localparam S_IDLE              = 0;
    localparam S_LOAD_BIAS         = 1;
    localparam S_LOAD_BIAS_LAT     = 2;
    localparam S_LOAD_BIAS_WAIT    = 3;
    localparam S_LOAD_WEIGHT       = 4;
    localparam S_LOAD_WEIGHT_LAT   = 5;
    localparam S_LOAD_WEIGHT_WAIT  = 6;
    localparam S_LOAD_ROW          = 7;
    localparam S_LOAD_ROW_LAT      = 8;
    localparam S_LOAD_ROW_WAIT     = 9;
    localparam S_COMPUTE           = 10;
    localparam S_COMPUTE_WR        = 16;
    localparam S_NEXT_CI           = 11;
    localparam S_REQUANT           = 12;
    localparam S_REQUANT_FLUSH     = 13;
    localparam S_NEXT_CO           = 14;
    localparam S_DONE              = 15;
    localparam S_DOT_MULT          = 17;
    localparam S_DOT_PAIR          = 18;
    localparam S_DOT_HALF          = 19;
    localparam S_DOT_SUM           = 20;
    localparam S_ACC_WAIT          = 21;

    reg [4:0] state;

    // Iteration Counters
    reg [15:0] cur_co, cur_ci;
    reg [5:0] out_y, out_x;
    reg [3:0] byte_cnt;

    // Row loading state
    reg [5:0] load_target_row;
    reg [5:0] load_col;
    reg [1:0] load_dest;
    reg [5:0] rows_ready;

    // Requantization state
    reg [10:0] req_pixel_idx;
    reg [3:0]  flush_cnt;

    // Registers for weights and bias
    reg [31:0] cur_bias;
    reg signed [31:0] dot_reg;
    reg [7:0]  weight_rf [0:8];

    // Row Buffers (Max 32 pixels per row)
    reg [7:0] rbuf0 [0:31];
    reg [7:0] rbuf1 [0:31];
    reg [7:0] rbuf2 [0:31];

    // Accumulator BRAM (Max 32x32 = 1024 pixels, 32-bit each)
    reg        acc_rd_en;
    reg [9:0]  acc_rd_addr;
    reg [31:0] acc_rd_data;

    reg        acc_wr_en;
    reg [9:0]  acc_wr_addr;
    reg [31:0] acc_wr_data;

    // Production's registered dot pipeline already covers the synchronous
    // read latency. One shared read port serves accumulation and requant,
    // instead of inferring asynchronous distributed RAM plus a second read.
    reg [31:0] acc_bram [0:1023];
    // Frozen square 32/16/8 maps: shifts replace serial descriptor multiplies.
    wire [11:0] plane_pixels=(PIPELINED_DOT!=0)?((InW==32)?12'd1024:(InW==16)?12'd256:12'd64):(InH*InW);
    function [13:0] map_address;
        input [15:0] channel;input [5:0] row,col;
        begin if(PIPELINED_DOT!=0)begin
            case(InW)
                32:map_address=(channel<<10)+(row<<5)+col;
                16:map_address=(channel<<8)+(row<<4)+col;
                8:map_address=(channel<<6)+(row<<3)+col;
                default:map_address=0;
            endcase
        end else map_address=channel*(InH*InW)+row*InW+col;end
    endfunction
    function [15:0] weight_address;
        input [15:0] channel,input_channel;reg [15:0] element;
        begin if(PIPELINED_DOT!=0)begin
            case(Cin)
                1:element=channel+input_channel;
                8:element=(channel<<3)+input_channel;
                16:element=(channel<<4)+input_channel;
                default:element=0;
            endcase
            weight_address=weight_offset+(element<<3)+element+byte_cnt;
        end else weight_address=weight_offset+channel*Cin*9+input_channel*9+byte_cnt;end
    endfunction

    always @(posedge clk) begin
        if (acc_wr_en) acc_bram[acc_wr_addr] <= acc_wr_data;
    end
    generate if (SYNC_ACC_BRAM != 0) begin: g_sync_acc
        always @(posedge clk)
            if (acc_rd_en) acc_rd_data <= acc_bram[acc_rd_addr];
    end else begin: g_async_acc
        always @(*) acc_rd_data = acc_bram[acc_rd_addr];
    end endgenerate

    // ======================================================================
    // Dot Product Combinational Logic
    // ======================================================================
    wire signed [17:0] p [0:8];
    wire [7:0] px [0:8];

    // Zero-padding bounds check
    wire [6:0] ix_s = {1'b0, out_x} - 7'd1;

    // Retrieve pixels for current window
    assign px[0] = (out_y == 0 || ix_s[6]) ? 8'd0 : rbuf0[ix_s[5:0]];
    assign px[1] = (out_y == 0)            ? 8'd0 : rbuf0[out_x];
    assign px[2] = (out_y == 0 || out_x == InW - 1) ? 8'd0 : rbuf0[out_x + 1];

    assign px[3] = (ix_s[6]) ? 8'd0 : rbuf1[ix_s[5:0]];
    assign px[4] =                    rbuf1[out_x];
    assign px[5] = (out_x == InW - 1) ? 8'd0 : rbuf1[out_x + 1];

    assign px[6] = (out_y == InH - 1 || ix_s[6]) ? 8'd0 : rbuf2[ix_s[5:0]];
    assign px[7] = (out_y == InH - 1)            ? 8'd0 : rbuf2[out_x];
    assign px[8] = (out_y == InH - 1 || out_x == InW - 1) ? 8'd0 : rbuf2[out_x + 1];

    assign p[0] = $signed(weight_rf[0]) * $signed({1'b0, px[0]});
    assign p[1] = $signed(weight_rf[1]) * $signed({1'b0, px[1]});
    assign p[2] = $signed(weight_rf[2]) * $signed({1'b0, px[2]});
    assign p[3] = $signed(weight_rf[3]) * $signed({1'b0, px[3]});
    assign p[4] = $signed(weight_rf[4]) * $signed({1'b0, px[4]});
    assign p[5] = $signed(weight_rf[5]) * $signed({1'b0, px[5]});
    assign p[6] = $signed(weight_rf[6]) * $signed({1'b0, px[6]});
    assign p[7] = $signed(weight_rf[7]) * $signed({1'b0, px[7]});
    assign p[8] = $signed(weight_rf[8]) * $signed({1'b0, px[8]});

    wire signed [31:0] dot = p[0] + p[1] + p[2] + p[3] + p[4] + p[5] + p[6] + p[7] + p[8];
    // Frozen model build: isolate the row mux, nine signed products, and
    // balanced addition levels. Legacy builds retain their original schedule.
    reg [7:0] dot_px [0:8];
    reg signed [17:0] dot_p [0:8];
    reg signed [18:0] dot_pair [0:3];
    reg signed [19:0] dot_half [0:1];
    reg signed [17:0] dot_tail1,dot_tail2;

    // ======================================================================
    // Requantization Pipeline
    // ======================================================================
    reg        acc_rd_en_d1;
    reg [9:0]  acc_rd_addr_d1;

    always @(posedge clk) begin
        acc_rd_en_d1 <= acc_rd_en;
        acc_rd_addr_d1 <= acc_rd_addr;
    end

    // Stage 0: Data Arrival
    reg        rq_valid_s0;
    reg [31:0] rq_acc_s0;
    reg [9:0]  rq_addr_s0;

    // Stage 1: Add Bias
    reg        rq_s1_valid;
    reg [31:0] rq_s1_biased;
    reg [9:0]  rq_s1_addr;

    // Stage 2: Multiply
    reg        rq_s2_valid;
    reg signed [63:0] rq_s2_mult;
    reg [9:0]  rq_s2_addr;

    // Stage 3: Shift & Round
    reg        rq_s3_valid;
    reg signed [63:0] rq_s3_shifted;
    reg [9:0]  rq_s3_addr;

    // Stage 4: Clamp
    reg        rq_s4_valid;
    reg [7:0]  rq_s4_pixel;
    reg [9:0]  rq_s4_addr;

    wire signed [63:0] rq_round = (quant_shift > 0) ? (64'sd1 << (quant_shift - 1)) : 64'sd0;

    always @(posedge clk) begin
        if (!rst_n) begin
            rq_valid_s0 <= 0;
            rq_s1_valid <= 0;
            rq_s2_valid <= 0;
            rq_s3_valid <= 0;
            rq_s4_valid <= 0;
        end else begin
            // Stage 0
            if ((state == S_REQUANT || state == S_REQUANT_FLUSH) && acc_rd_en_d1) begin
                rq_valid_s0 <= 1;
                rq_acc_s0   <= (SYNC_ACC_BRAM != 0) ? acc_rd_data : acc_bram[acc_rd_addr_d1];
                rq_addr_s0  <= acc_rd_addr_d1;
            end else begin
                rq_valid_s0 <= 0;
            end

            // Stage 1
            rq_s1_valid  <= rq_valid_s0;
            rq_s1_biased <= $signed(rq_acc_s0) + $signed(cur_bias);
            rq_s1_addr   <= rq_addr_s0;

            // Stage 2
            rq_s2_valid <= rq_s1_valid;
            rq_s2_mult  <= $signed(rq_s1_biased) * $signed(quant_M);
            rq_s2_addr  <= rq_s1_addr;

            // Stage 3
            rq_s3_valid   <= rq_s2_valid;
            rq_s3_shifted <= (rq_s2_mult + rq_round) >>> quant_shift;
            rq_s3_addr    <= rq_s2_addr;

            // Stage 4
            rq_s4_valid <= rq_s3_valid;
            rq_s4_addr  <= rq_s3_addr;
            if (rq_s3_shifted < 64'sd0)        rq_s4_pixel <= 8'd0;
            else if (rq_s3_shifted > 64'sd255) rq_s4_pixel <= 8'd255;
            else                               rq_s4_pixel <= rq_s3_shifted[7:0];
        end
    end

    // ======================================================================
    // FSM Control
    // ======================================================================
    always @(posedge clk) begin
        if (!rst_n) begin
            state <= S_IDLE;
            busy <= 0;
            done <= 0;
            w_bram_en <= 0;
            src_bram_en <= 0;
            dst_bram_en <= 0;
            acc_rd_en <= 0;
            acc_wr_en <= 0;
        end else begin
            // Default inactive
            w_bram_en <= 0;
            src_bram_en <= 0;
            dst_bram_en <= 0;
            acc_rd_en <= 0;
            acc_wr_en <= 0;

            // Output Pipeline Write
            if (rq_s4_valid) begin
                dst_bram_en <= 1;
                // dst_bram_addr = cur_co * (InH * InW) + rq_s4_addr
                dst_bram_addr <= map_address(cur_co,0,0) + rq_s4_addr;
                dst_bram_data <= rq_s4_pixel;
            end

            case (state)
                S_IDLE: begin
                    done <= 0;
                    if (start) begin
                        $display("[%0t] [CONV] Layer Started! Cin=%d Cout=%d InW=%d InH=%d", $time, Cin, Cout, InW, InH);
                        busy <= 1;
                        cur_co <= COUT_START;
                        cur_ci <= 0;
                        out_y <= 0;
                        out_x <= 0;
                        rows_ready <= 0;
                        load_target_row <= 0;
                        load_dest <= 1;
                        load_col <= 0;
                        byte_cnt <= 0;
                        begin : clear_rbuf0
                            integer i;
                            for(i=0; i<32; i=i+1) rbuf0[i] <= 0;
                        end
                        state <= S_LOAD_BIAS;
                    end
                end

                S_LOAD_BIAS: begin
                    if (byte_cnt == 4) begin
                        state <= S_LOAD_WEIGHT;
                        byte_cnt <= 0;
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

                S_LOAD_WEIGHT: begin
                    if (byte_cnt == 9) begin
                        state <= S_LOAD_ROW;
                        byte_cnt <= 0;
                    end else begin
                        w_bram_en <= 1;
                        w_bram_addr <= weight_address(cur_co,cur_ci);
                        state <= S_LOAD_WEIGHT_LAT;
                    end
                end

                S_LOAD_WEIGHT_LAT: begin
                    state <= S_LOAD_WEIGHT_WAIT;
                end

                S_LOAD_WEIGHT_WAIT: begin
                    weight_rf[byte_cnt] <= w_bram_data;
                    byte_cnt <= byte_cnt + 1;
                    state <= S_LOAD_WEIGHT;
                end

                S_LOAD_ROW: begin
                    if (load_target_row >= InH) begin
                        state <= S_COMPUTE;
                        // PREFETCH acc_bram for first pixel
                        acc_rd_en <= 1;
                        acc_rd_addr <= out_y * InW + out_x;
                    end else begin
                        src_bram_en <= 1;
                        src_bram_addr <= map_address(cur_ci,load_target_row,load_col);
                        state <= S_LOAD_ROW_LAT;
                    end
                end

                S_LOAD_ROW_LAT: begin
                    src_bram_en <= 1;
                    src_bram_addr <= map_address(cur_ci,load_target_row,load_col) + 1;
                    state <= S_LOAD_ROW_WAIT;
                end

                S_LOAD_ROW_WAIT: begin
                    case (load_dest)
                        2'd0: rbuf0[load_col] <= src_bram_data;
                        2'd1: rbuf1[load_col] <= src_bram_data;
                        2'd2: rbuf2[load_col] <= src_bram_data;
                        default: ;
                    endcase

                    if (load_col == InW - 1) begin
                        load_col <= 0;
                        rows_ready <= rows_ready + 1;
                        load_target_row <= load_target_row + 1;

                        if (load_dest == 2) load_dest <= 0;
                        else load_dest <= load_dest + 1;

                        if (out_y == 0 && rows_ready + 1 >= 2) begin
                            state <= S_COMPUTE;
                        end else if (out_y > 0) begin
                            state <= S_COMPUTE;
                        end else begin
                            state <= S_LOAD_ROW;
                        end
                    end else begin
                        load_col <= load_col + 1;
                        src_bram_en <= 1;
                        src_bram_addr <= map_address(cur_ci,load_target_row,load_col) + 2;
                        state <= S_LOAD_ROW_WAIT;
                    end
                end

                // Pipeline Stage 1: Register dot product, set up BRAM read address
                S_COMPUTE: begin
                    acc_rd_en <= 1;
                    acc_rd_addr <= out_y * InW + out_x;
                    if(PIPELINED_DOT!=0)begin: capture_window
                        integer k;
                        for(k=0;k<9;k=k+1)dot_px[k]<=px[k];
                        state<=S_DOT_MULT;
                    end else begin
                        dot_reg<=dot;
                        state<=(SYNC_ACC_BRAM!=0)?S_ACC_WAIT:S_COMPUTE_WR;
                    end
                end

                S_ACC_WAIT: state <= S_COMPUTE_WR;

                S_DOT_MULT: begin: multiply_window
                    integer k;
                    for(k=0;k<9;k=k+1)dot_p[k]<=$signed(weight_rf[k])*$signed({1'b0,dot_px[k]});
                    state<=S_DOT_PAIR;
                end
                S_DOT_PAIR: begin: pair_products
                    integer k;
                    for(k=0;k<4;k=k+1)
                        dot_pair[k]<=$signed({dot_p[2*k][17],dot_p[2*k]})+$signed({dot_p[2*k+1][17],dot_p[2*k+1]});
                    dot_tail1<=dot_p[8];state<=S_DOT_HALF;
                end
                S_DOT_HALF: begin
                    dot_half[0]<=$signed({dot_pair[0][18],dot_pair[0]})+$signed({dot_pair[1][18],dot_pair[1]});
                    dot_half[1]<=$signed({dot_pair[2][18],dot_pair[2]})+$signed({dot_pair[3][18],dot_pair[3]});
                    dot_tail2<=dot_tail1;state<=S_DOT_SUM;
                end
                S_DOT_SUM: begin
                    dot_reg<=$signed({{12{dot_half[0][19]}},dot_half[0]})+
                             $signed({{12{dot_half[1][19]}},dot_half[1]})+
                             $signed({{14{dot_tail2[17]}},dot_tail2});
                    state<=S_COMPUTE_WR;
                end

                // Pipeline Stage 2: BRAM data ready (combinational), write accumulator
                S_COMPUTE_WR: begin
                    acc_wr_en <= 1;
                    acc_wr_addr <= out_y * InW + out_x;
                    if (cur_ci == 0) begin
                        acc_wr_data <= dot_reg;
                    end else begin
                        acc_wr_data <= acc_rd_data + dot_reg;
                    end

                    if (out_x == InW - 1) begin
                        out_x <= 0;
                        if (out_y == InH - 1) begin
                            state <= S_NEXT_CI;
                        end else begin
                            out_y <= out_y + 1;
                            begin : scroll_rows
                                integer i;
                                for (i=0; i<32; i=i+1) begin
                                    rbuf0[i] <= rbuf1[i];
                                    rbuf1[i] <= rbuf2[i];
                                end
                            end
                            if (out_y + 2 < InH) begin
                                load_target_row <= out_y + 2;
                                load_dest <= 2;
                                state <= S_LOAD_ROW;
                            end else begin
                                begin : clr_rbuf2
                                    integer i;
                                    for (i=0; i<32; i=i+1) rbuf2[i] <= 0;
                                end
                                state <= S_COMPUTE;
                            end
                        end
                    end else begin
                        out_x <= out_x + 1;
                        state <= S_COMPUTE;
                    end
                end

                S_NEXT_CI: begin
                    if (cur_ci == Cin - 1) begin
                        state <= S_REQUANT;
                        req_pixel_idx <= 0;
                    end else begin
                        cur_ci <= cur_ci + 1;
                        out_y <= 0;
                        out_x <= 0;
                        rows_ready <= 0;
                        load_target_row <= 0;
                        load_dest <= 1;
                        load_col <= 0;
                        begin : clr_rbuf0_next
                            integer i;
                            for(i=0; i<32; i=i+1) rbuf0[i] <= 0;
                        end
                        state <= S_LOAD_WEIGHT;
                        byte_cnt <= 0;
                    end
                end

                S_REQUANT: begin
                    if (req_pixel_idx == plane_pixels) begin
                        flush_cnt <= 0;
                        state <= S_REQUANT_FLUSH;
                    end else begin
                        acc_rd_en <= 1;
                        acc_rd_addr <= req_pixel_idx;
                        req_pixel_idx <= req_pixel_idx + 1;
                    end
                end

                S_REQUANT_FLUSH: begin
                    flush_cnt <= flush_cnt + 1;
                    if (flush_cnt >= 8) begin
                        state <= S_NEXT_CO;
                    end
                end

                S_NEXT_CO: begin
                    if (cur_co + COUT_STEP >= Cout) begin
                        $display("[%0t] [CONV] ALL CHANNELS DONE. FINISHING.", $time);
                        state <= S_DONE;
                    end else begin
                        if (cur_co % 4 == 0) $display("[%0t] [CONV] Finished Output Channel %d", $time, cur_co);
                        cur_co <= cur_co + COUT_STEP;
                        cur_ci <= 0;
                        out_y <= 0;
                        out_x <= 0;
                        rows_ready <= 0;
                        load_target_row <= 0;
                        load_dest <= 1;
                        load_col <= 0;
                        begin : clr_rbuf0_nxtco
                            integer i;
                            for(i=0; i<32; i=i+1) rbuf0[i] <= 0;
                        end
                        state <= S_LOAD_BIAS;
                        byte_cnt <= 0;
                    end
                end

                S_DONE: begin
                    busy <= 0;
                    done <= 1;
                    state <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
