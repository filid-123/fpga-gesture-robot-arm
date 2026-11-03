// ============================================================================
// Block Name : conv3x3_c1_engine.v
// Description: Single-Layer C1 Conv3x3 Engine (Bit-Exact Proof Point)
//              Cin=1, Cout=8, 32x32, Pad=1, Stride=1
//
//  Architecture:
//    - Processes 8 output channels sequentially
//    - For each channel: iterates all 32x32 output pixels
//    - Per pixel: 3x3 dot product with zero-padding + requant
//    - Row buffers hold 3 rows of input for sliding window
//    - 4-stage requant pipeline (bias add → multiply → shift → clamp)
//
// Target FPGA : Xilinx Zynq-7020 (PYNQ-Z2, XC7Z020-1CLG400C)
// Clock Domain: clk (100 MHz)
// ============================================================================

`timescale 1ns / 1ps

module conv3x3_c1_engine (
    input  wire        clk,
    input  wire        rst_n,

    // Control
    input  wire        start,
    output reg         done,
    output reg         busy,

    // Input Image BRAM Interface (1-cycle read latency)
    output reg         img_rd_en,
    output reg  [9:0]  img_rd_addr,
    input  wire [7:0]  img_rd_data,

    // Weight/Bias Register Load Interface
    input  wire        weight_wr_en,
    input  wire [6:0]  weight_wr_addr,
    input  wire [7:0]  weight_wr_data,
    input  wire        bias_wr_en,
    input  wire [2:0]  bias_wr_addr,
    input  wire [31:0] bias_wr_data,

    // Output Feature Map Write Interface
    output reg         out_wr_en,
    output reg  [12:0] out_wr_addr,
    output reg  [7:0]  out_wr_data
);

    // ======================================================================
    // Weight & Bias Register Files
    // ======================================================================
    reg signed [7:0]  weight_rf [0:71];
    reg signed [31:0] bias_rf   [0:7];

    always @(posedge clk) begin
        if (weight_wr_en) weight_rf[weight_wr_addr] <= $signed(weight_wr_data);
    end
    always @(posedge clk) begin
        if (bias_wr_en) bias_rf[bias_wr_addr] <= bias_wr_data;
    end

    // ======================================================================
    // Internal Requantization Pipeline (4-stage, matching requant_unit.v)
    // ======================================================================
    localparam signed [31:0] QUANT_M     = 32'sd107374182;
    localparam        [4:0]  QUANT_SHIFT = 5'd16;

    reg                rq_valid_s0;
    reg signed [31:0]  rq_acc_s0;
    reg signed [31:0]  rq_bias_s0;
    reg        [12:0]  rq_addr_s0;

    reg signed [31:0]  rq_s1_biased;
    reg                rq_s1_valid;
    reg        [12:0]  rq_s1_addr;

    reg signed [63:0]  rq_s2_mult;
    reg                rq_s2_valid;
    reg        [12:0]  rq_s2_addr;

    reg signed [63:0]  rq_s3_shifted;
    reg                rq_s3_valid;
    reg        [12:0]  rq_s3_addr;

    reg        [7:0]   rq_s4_pixel;
    reg                rq_s4_valid;
    reg        [12:0]  rq_s4_addr;

    wire signed [63:0] rq_round = (QUANT_SHIFT > 0) ? (64'sd1 <<< (QUANT_SHIFT - 1)) : 64'sd0;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rq_s1_biased <= 0; rq_s1_valid <= 0; rq_s1_addr <= 0;
            rq_s2_mult <= 0; rq_s2_valid <= 0; rq_s2_addr <= 0;
            rq_s3_shifted <= 0; rq_s3_valid <= 0; rq_s3_addr <= 0;
            rq_s4_pixel <= 0; rq_s4_valid <= 0; rq_s4_addr <= 0;
        end else begin
            rq_s1_biased <= rq_acc_s0 + rq_bias_s0;
            rq_s1_valid  <= rq_valid_s0;
            rq_s1_addr   <= rq_addr_s0;

            rq_s2_mult   <= rq_s1_biased * QUANT_M;
            rq_s2_valid  <= rq_s1_valid;
            rq_s2_addr   <= rq_s1_addr;

            rq_s3_shifted <= (rq_s2_mult + rq_round) >>> QUANT_SHIFT;
            rq_s3_valid   <= rq_s2_valid;
            rq_s3_addr    <= rq_s2_addr;

            rq_s4_valid   <= rq_s3_valid;
            rq_s4_addr    <= rq_s3_addr;
            if (rq_s3_shifted < 64'sd0)        rq_s4_pixel <= 8'd0;
            else if (rq_s3_shifted > 64'sd255) rq_s4_pixel <= 8'd255;
            else                               rq_s4_pixel <= rq_s3_shifted[7:0];
        end
    end

    // ======================================================================
    // FSM States
    // ======================================================================
    localparam S_IDLE         = 4'd0;
    localparam S_LOAD_ROW     = 4'd1;
    localparam S_LOAD_LATENCY = 4'd2;
    localparam S_LOAD_WAIT    = 4'd3;
    localparam S_COMPUTE      = 4'd4;
    localparam S_NEXT_CH      = 4'd5;
    localparam S_FLUSH        = 4'd6;  // Drain requant pipeline before done
    localparam S_DONE         = 4'd7;

    reg [3:0]  state;
    reg [2:0]  cur_ch;
    reg [5:0]  out_y, out_x;

    // Row buffer: 3 rows × 32 columns
    reg [7:0]  rbuf0 [0:31];
    reg [7:0]  rbuf1 [0:31];
    reg [7:0]  rbuf2 [0:31];

    // Row loading control
    reg [5:0]  load_col;
    reg [5:0]  load_target_row;   // Which image row we're loading
    reg [1:0]  load_dest;         // Which rbuf slot (0,1,2)

    // Which image rows are currently in rbuf0/1/2
    // For output row y, we need input rows y-1, y, y+1
    // rbuf0 = row y-1, rbuf1 = row y, rbuf2 = row y+1
    reg [5:0]  rows_ready;        // How many rows we've loaded for current channel

    // Watchdog
    reg [19:0] wd_cnt;
    reg [3:0]  flush_cnt;  // Pipeline flush counter

    // ======================================================================
    // Combinational: 3x3 dot product
    // ======================================================================
    // Read pixel from row buffers with zero-padding
    reg [7:0] px [0:8];
    integer ki;

    always @(*) begin
        for (ki = 0; ki < 9; ki = ki + 1) begin : build_window
            reg signed [6:0] iy_s;
            reg signed [6:0] ix_s;
            iy_s = $signed({1'b0, out_y}) + (ki / 3) - 1;
            ix_s = $signed({1'b0, out_x}) + (ki % 3) - 1;

            if (iy_s < 0 || iy_s >= 32 || ix_s < 0 || ix_s >= 32)
                px[ki] = 8'd0;
            else begin
                case (ki / 3)
                    0: px[ki] = rbuf0[ix_s[5:0]];
                    1: px[ki] = rbuf1[ix_s[5:0]];
                    2: px[ki] = rbuf2[ix_s[5:0]];
                    default: px[ki] = 8'd0;
                endcase
            end
        end
    end

    // Dot product
    wire signed [31:0] dot;
    wire signed [17:0] p0, p1, p2, p3, p4, p5, p6, p7, p8;

    assign p0 = weight_rf[cur_ch*9+0] * $signed({1'b0, px[0]});
    assign p1 = weight_rf[cur_ch*9+1] * $signed({1'b0, px[1]});
    assign p2 = weight_rf[cur_ch*9+2] * $signed({1'b0, px[2]});
    assign p3 = weight_rf[cur_ch*9+3] * $signed({1'b0, px[3]});
    assign p4 = weight_rf[cur_ch*9+4] * $signed({1'b0, px[4]});
    assign p5 = weight_rf[cur_ch*9+5] * $signed({1'b0, px[5]});
    assign p6 = weight_rf[cur_ch*9+6] * $signed({1'b0, px[6]});
    assign p7 = weight_rf[cur_ch*9+7] * $signed({1'b0, px[7]});
    assign p8 = weight_rf[cur_ch*9+8] * $signed({1'b0, px[8]});

    assign dot = p0 + p1 + p2 + p3 + p4 + p5 + p6 + p7 + p8;

    // ======================================================================
    // Main FSM
    // ======================================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state      <= S_IDLE;
            done       <= 0;
            busy       <= 0;
            img_rd_en  <= 0;
            img_rd_addr <= 0;
            out_wr_en  <= 0;
            out_wr_addr <= 0;
            out_wr_data <= 0;
            cur_ch     <= 0;
            out_y      <= 0;
            out_x      <= 0;
            load_col   <= 0;
            load_target_row <= 0;
            load_dest  <= 0;
            rows_ready <= 0;
            rq_valid_s0 <= 0;
            rq_acc_s0   <= 0;
            rq_bias_s0  <= 0;
            rq_addr_s0  <= 0;
            wd_cnt     <= 0;
        end else begin
            // Defaults
            img_rd_en   <= 0;
            out_wr_en   <= 0;
            rq_valid_s0 <= 0;

            // Requant pipeline output → write to output port
            if (rq_s4_valid) begin
                out_wr_en   <= 1;
                out_wr_addr <= rq_s4_addr;
                out_wr_data <= rq_s4_pixel;
            end

            // Watchdog
            if (busy) begin
                wd_cnt <= wd_cnt + 1;
                if (wd_cnt > 20'd500000) state <= S_DONE;
            end else begin
                wd_cnt <= 0;
            end

            case (state)
                // ----------------------------------------------------------
                S_IDLE: begin
                    done <= 0; busy <= 0;
                    if (start) begin
                        busy   <= 1;
                        cur_ch <= 0;
                        out_y  <= 0;
                        out_x  <= 0;
                        rows_ready <= 0;
                        load_target_row <= 0;
                        load_dest <= 2'd1;  // row0 → rbuf1, rbuf0 = padding zeros
                        load_col <= 0;
                        // Clear rbuf0 for top-row zero-padding
                        begin : init_rbuf0
                            integer ic;
                            for (ic = 0; ic < 32; ic = ic + 1)
                                rbuf0[ic] <= 8'd0;
                        end
                        state  <= S_LOAD_ROW;
                    end
                end

                // ----------------------------------------------------------
                // Load one row from BRAM into rbuf[load_dest]
                S_LOAD_ROW: begin
                    if (load_target_row >= 6'd32) begin
                        // No more rows to load, go compute
                        state <= S_COMPUTE;
                    end else begin
                        img_rd_en   <= 1;
                        img_rd_addr <= load_target_row * 32 + load_col;
                        state       <= S_LOAD_LATENCY;
                    end
                end

                // ----------------------------------------------------------
                S_LOAD_LATENCY: begin
                    img_rd_en   <= 1;
                    img_rd_addr <= load_target_row * 32 + load_col + 1;
                    state       <= S_LOAD_WAIT;
                end

                // ----------------------------------------------------------
                S_LOAD_WAIT: begin
                    // BRAM data is now valid on img_rd_data
                    case (load_dest)
                        2'd0: rbuf0[load_col] <= img_rd_data;
                        2'd1: rbuf1[load_col] <= img_rd_data;
                        2'd2: rbuf2[load_col] <= img_rd_data;
                        default: ;
                    endcase

                    if (load_col == 6'd31) begin
                        // Row fully loaded
                        load_col <= 0;
                        rows_ready <= rows_ready + 1;
                        load_target_row <= load_target_row + 1;
                        load_dest <= load_dest + 1;

                        // Do we have enough rows to start computing?
                        // For out_y=0 we need rbuf0=row(y-1)=PADDING, rbuf1=row0, rbuf2=row1
                        // We initially load row0 into rbuf1, row1 into rbuf2
                        // rbuf0 stays at zeros (padding for y-1=-1)
                        if (out_y == 6'd0 && rows_ready + 1 >= 6'd2) begin
                            // Loaded rows 0,1 → compute
                            state <= S_COMPUTE;
                        end else if (out_y > 6'd0) begin
                            // Single new row loaded for scroll
                            state <= S_COMPUTE;
                        end else begin
                            // Need more rows
                            state <= S_LOAD_ROW;
                        end
                    end else begin
                        load_col <= load_col + 1;
                        img_rd_en <= 1;
                        img_rd_addr <= load_target_row * 32 + load_col + 2;
                        state <= S_LOAD_WAIT;
                    end
                end

                // ----------------------------------------------------------
                S_COMPUTE: begin
                    // dot is computed combinationally above
                    rq_valid_s0 <= 1;
                    rq_acc_s0   <= dot;
                    rq_bias_s0  <= bias_rf[cur_ch];
                    rq_addr_s0  <= {cur_ch, out_y[4:0], out_x[4:0]};  // ch*1024 + y*32 + x

                    // Advance to next pixel
                    if (out_x == 6'd31) begin
                        out_x <= 0;
                        if (out_y == 6'd31) begin
                            // Channel done
                            state <= S_NEXT_CH;
                        end else begin
                            out_y <= out_y + 1;
                            // Scroll row buffers: rbuf0←rbuf1, rbuf1←rbuf2, load new row into rbuf2
                            // We do this by rotating which buffer slot holds which row
                            // Simpler: copy rbuf1→rbuf0, rbuf2→rbuf1, then load new row into rbuf2
                            begin : scroll_rows
                                integer sc;
                                for (sc = 0; sc < 32; sc = sc + 1) begin
                                    rbuf0[sc] <= rbuf1[sc];
                                    rbuf1[sc] <= rbuf2[sc];
                                end
                            end
                            // Load the new row (out_y+1+1 = next y's bottom row)
                            if (out_y + 2 < 6'd32) begin
                                load_target_row <= out_y + 2;
                                load_dest <= 2'd2;
                                load_col <= 0;
                                state <= S_LOAD_ROW;
                            end else begin
                                // No more rows; for the last row, rbuf2 will be padding (zeros)
                                begin : zero_rbuf2
                                    integer zc;
                                    for (zc = 0; zc < 32; zc = zc + 1)
                                        rbuf2[zc] <= 8'd0;
                                end
                                state <= S_COMPUTE;
                            end
                        end
                    end else begin
                        out_x <= out_x + 1;
                        // Stay in S_COMPUTE for next column
                    end
                end

                // ----------------------------------------------------------
                S_NEXT_CH: begin
                    if (cur_ch == 3'd7) begin
                        // All channels done, flush requant pipeline
                        flush_cnt <= 4'd0;
                        state <= S_FLUSH;
                    end else begin
                        cur_ch <= cur_ch + 1;
                        out_y  <= 0;
                        out_x  <= 0;
                        rows_ready <= 0;
                        load_target_row <= 0;
                        load_dest <= 2'd1;
                        load_col <= 0;
                        begin : clear_rbuf0
                            integer cc;
                            for (cc = 0; cc < 32; cc = cc + 1)
                                rbuf0[cc] <= 8'd0;
                        end
                        state <= S_LOAD_ROW;
                    end
                end

                // ----------------------------------------------------------
                // Drain the 4-stage requant pipeline (wait 8 cycles)
                S_FLUSH: begin
                    flush_cnt <= flush_cnt + 1;
                    if (flush_cnt >= 4'd8) begin
                        state <= S_DONE;
                    end
                end

                // ----------------------------------------------------------
                S_DONE: begin
                    busy <= 0;
                    done <= 1;
                    if (start) begin
                        state <= S_IDLE;
                        done <= 0;
                    end
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
