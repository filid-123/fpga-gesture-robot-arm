// ============================================================================
// Frozen black-scene v0.4: Conv1/2/3 -> G1(d2) -> G2(d5) -> Conv4/5 fusion.
//
// The eight lanes share one activation read and advance over the same input
// channel / 3x3 tap.  Model read bandwidth comes from four true-dual-read
// copies of the frozen 4096-word ROM. Requantization shares one multiplier,
// but issues successive lanes every cycle with their tags through its stages.
// Final output/residual writes retain their original ordering and arithmetic.
//
// Activation channels are banked by channel[2:0].  The logical CHW layout and
// the external Locator ABI are unchanged.
// ============================================================================
`timescale 1ns / 1ps

module locator_cnn_engine_context_8lane #(
    parameter integer PIPELINED_REQUANT = 1
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         start,
    input  wire         input_buffer_id,
    input  wire         output_buffer_id,
    input  wire [31:0]  frame_id,

    output reg          input_bram_en,
    output reg  [12:0]  input_bram_addr,
    input  wire [31:0]  input_bram_data,

    output reg          output_bram_we,
    output reg  [11:0]  output_bram_addr,
    output reg  [31:0]  output_bram_data,

    output reg  [7:0]   model_lane_rd_en,
    output reg  [95:0]  model_lane_rd_addr,
    input  wire [255:0] model_lane_rd_data,

    output reg          busy,
    output reg          done,
    output reg          input_release,
    output reg          stall,

    output reg          debug_acc_valid,
    output reg  [2:0]   debug_layer,
    output reg  [17:0]  debug_acc_index,
    output reg  [31:0]  debug_acc_data,
    output reg          debug_act_valid,
    output reg  [14:0]  debug_act_index,
    output reg  [7:0]   debug_act_data
);

    localparam S_IDLE         = 5'd0;
    localparam S_BIAS_REQ     = 5'd1;
    localparam S_BIAS_WAIT    = 5'd2;
    localparam S_PIXEL_START  = 5'd3;
    localparam S_MAC          = 5'd4;
    localparam S_REQUANT_MUL  = 5'd5;
    localparam S_REQUANT_OUT  = 5'd6;
    localparam S_STORE_RAW    = 5'd7;
    localparam S_FLUSH        = 5'd8;
    localparam S_MAC_PRIME    = 5'd9;

    localparam S_RES_REQ_LO   = 5'd10;
    localparam S_RES_WAIT_LO  = 5'd11;
    localparam S_RES_REQ_HI   = 5'd12;
    localparam S_RES_WAIT_HI  = 5'd13;
    localparam S_FUSE_MUL     = 5'd14;
    localparam S_FUSE_ADD     = 5'd15;
    localparam S_RES_STORE_HI = 5'd16;
    localparam S_OUTPUT       = 5'd17;
    localparam S_REQUANT_ROUND=5'd18, S_REQUANT_CLAMP=5'd19, S_RES_ROUND=5'd20;
    reg signed [63:0] requant_shifted,residual_aligned_reg;
    reg [7:0] requant_value;
    localparam S_REQUANT_PREP=5'd21,S_FUSE_PREP=5'd22;
    localparam S_REQUANT_STREAM=5'd23;
    reg [3:0] rq_valid;
    reg [3:0] rq_issued;
    reg [2:0] rq_lane0,rq_lane1,rq_lane2,rq_lane3;
    reg signed [31:0] mul_l,mul_r;
    reg [4:0] state;
    reg [15:0] residual_low;
    reg signed [31:0] residual_raw;
    reg signed [31:0] fused_value;
    reg [2:0] layer;
    reg [5:0] out_channel_base;
    reg [7:0] out_y;
    reg [7:0] out_x;
    reg [1:0] pool_sub;
    reg [2:0] lane_cursor;

    reg [4:0] mac_ic;
    reg [1:0] mac_ky;
    reg [1:0] mac_kx;
    reg [8:0] issue_count;
    reg [8:0] consume_count;
    reg       mac_valid_d;
    reg       mac_operand_valid;
    reg       mac_product_valid;
    reg [7:0] mac_pixel_operand;
    reg [1:0] weight_lane_d [0:7];
    reg signed [7:0]  mac_weight_operand [0:7];
    reg signed [16:0] mac_product_d [0:7];
    reg       pixel_zero_d;
    reg       source_external_d;
    reg       source_bank_d;
    reg [2:0] pixel_bank_d;
    reg [1:0] pixel_lane_d;
    reg       request_padding;
    reg [14:0] request_pixel_linear;
    reg [11:0] request_pixel_bank_addr;
    reg [2:0] request_pixel_bank;

    reg signed [31:0] bias_cache [0:7];
    reg signed [31:0] accumulator [0:7];
    reg signed [31:0] post_acc32 [0:7];
    reg signed [63:0] requant_product;
    reg [7:0] pool_max [0:7];
    wire [2:0] residual_read_bank0 = (lane_cursor - 3'd1) << 1;
    wire [2:0] residual_read_bank1 = residual_read_bank0 + 3'd1;
    wire [2:0] residual_write_bank0 = lane_cursor << 1;
    wire [2:0] residual_write_bank1 = residual_write_bank0 + 3'd1;
    wire [11:0] residual_cell_addr = {4'd0, out_y[3:0], out_x[3:0]};
    reg signed [31:0] residual_multiplier;
    wire signed [63:0] residual_aligned =
        ($signed(requant_product) + 64'sd1073741824) >>> 31;
    wire signed [63:0] fused_sum =
        $signed({{32{post_acc32[lane_cursor][31]}}, post_acc32[lane_cursor]}) + residual_aligned_reg;


    reg [13:0] channel_weight_base [0:7];

    reg input_buffer_latched;
    reg output_buffer_latched;

    reg [7:0]  act0_we;
    reg [95:0] act0_waddr;
    reg [63:0] act0_wdata;
    reg [7:0]  act1_we;
    reg [95:0] act1_waddr;
    reg [63:0] act1_wdata;
    reg [7:0]  act0_rd_en;
    reg [95:0] act0_rd_addr;
    reg [7:0]  act1_rd_en;
    reg [95:0] act1_rd_addr;
    wire [63:0] act0_rdata;
    wire [63:0] act1_rdata;

    reg [7:0]  cfg_input_size;
    reg [7:0]  cfg_output_size;
    reg [5:0]  cfg_cin;
    reg [5:0]  cfg_cout;
    reg [8:0]  cfg_mac_count;
    reg        cfg_pool;
    reg        cfg_source_external;
    reg        cfg_source_bank;
    reg        cfg_dest_bank;
    reg [13:0] cfg_weight_base;
    reg [13:0] cfg_bias_base;
    reg signed [31:0] cfg_multiplier;
    reg [3:0] active_lane_count;

    reg signed [8:0] issue_y,issue_x;
    reg [7:0] issue_base_y,issue_base_x;
    reg issue_padding;
    reg [14:0] issue_pixel_linear;
    reg [11:0] issue_pixel_bank_addr;
    reg [13:0] issue_weight_byte_addr [0:7];
    reg issue_fire;
    integer lane_i;

    wire [7:0] conv_y = cfg_pool ? ((out_y << 1) + pool_sub[1]) : out_y;
    wire [7:0] conv_x = cfg_pool ? ((out_x << 1) + pool_sub[0]) : out_x;
    wire [2:0] result_lane = (state==S_REQUANT_STREAM) ? rq_lane3 : lane_cursor;
    wire [5:0] current_lane_channel = out_channel_base + {3'd0, result_lane};
    wire current_lane_last = ({1'b0, result_lane} + 4'd1) == active_lane_count;

    function [7:0] select_u8;
        input [31:0] word;
        input [1:0] lane;
        begin
            case (lane)
                2'd0: select_u8 = word[7:0];
                2'd1: select_u8 = word[15:8];
                2'd2: select_u8 = word[23:16];
                default: select_u8 = word[31:24];
            endcase
        end
    endfunction

    function signed [7:0] select_s8;
        input [31:0] word;
        input [1:0] lane;
        begin
            case (lane)
                2'd0: select_s8 = word[7:0];
                2'd1: select_s8 = word[15:8];
                2'd2: select_s8 = word[23:16];
                default: select_s8 = word[31:24];
            endcase
        end
    endfunction

    function [7:0] requant_clamp_u8;
        input signed [63:0] product;
        reg signed [63:0] rounded;
        reg signed [63:0] shifted;
        begin
            rounded = product + 64'sd1073741824;
            shifted = rounded >>> 31;
            if (shifted < 0)
                requant_clamp_u8 = 8'd0;
            else if (shifted > 255)
                requant_clamp_u8 = 8'd255;
            else
                requant_clamp_u8 = shifted[7:0];
        end
    endfunction

    function [17:0] accumulator_index;
        input [2:0] layer_id;
        input [5:0] channel;
        input [7:0] y;
        input [7:0] x;
        begin
            case (layer_id)
                3'd0: accumulator_index = ({12'd0, channel} * 18'd16384) +
                                              ({10'd0, y} * 18'd128) + x;
                3'd1: accumulator_index = ({12'd0, channel} * 18'd4096) +
                                              ({10'd0, y} * 18'd64) + x;
                3'd2: accumulator_index = ({12'd0, channel} * 18'd1024) +
                                              ({10'd0, y} * 18'd32) + x;
                default: accumulator_index = ({12'd0, channel} * 18'd256) +
                                                 ({10'd0, y} * 18'd16) + x;
            endcase
        end
    endfunction

    function [14:0] activation_index;
        input [2:0] layer_id;
        input [5:0] channel;
        input [7:0] y;
        input [7:0] x;
        begin
            case (layer_id)
                3'd0: activation_index = ({9'd0, channel} * 15'd4096) +
                                            ({7'd0, y} * 15'd64) + x;
                3'd1: activation_index = ({9'd0, channel} * 15'd1024) +
                                            ({7'd0, y} * 15'd32) + x;
                default: activation_index = ({9'd0, channel} * 15'd256) +
                                               ({7'd0, y} * 15'd16) + x;
            endcase
        end
    endfunction

    function [11:0] activation_write_bank_addr;
        input [2:0] layer_id;
        input [5:0] channel;
        input [7:0] y;
        input [7:0] x;
        begin
            case (layer_id)
                3'd0: activation_write_bank_addr =
                    ({9'd0, channel[5:3]} << 12) + ({4'd0, y} << 6) + x;
                3'd1: activation_write_bank_addr =
                    ({9'd0, channel[5:3]} << 10) + ({4'd0, y} << 5) + x;
                default: activation_write_bank_addr =
                    ({9'd0, channel[5:3]} << 8) + ({4'd0, y} << 4) + x;
            endcase
        end
    endfunction

    genvar bank_g;
    generate
        for (bank_g = 0; bank_g < 8; bank_g = bank_g + 1) begin : g_act_banks
            locator_act_bank_4k u_act0 (
                .clk(clk),
                .wr_en(act0_we[bank_g]),
                .wr_addr(act0_waddr[(bank_g*12) +: 12]),
                .wr_data(act0_wdata[(bank_g*8) +: 8]),
                .rd_en(act0_rd_en[bank_g]),
                .rd_addr(act0_rd_addr[(bank_g*12) +: 12]),
                .rd_data(act0_rdata[(bank_g*8) +: 8])
            );
            locator_act_bank_4k #(.ADDR_BITS(11)) u_act1 (
                .clk(clk),
                .wr_en(act1_we[bank_g]),
                .wr_addr(act1_waddr[(bank_g*12) +: 12]),
                .wr_data(act1_wdata[(bank_g*8) +: 8]),
                .rd_en(act1_rd_en[bank_g]),
                .rd_addr(act1_rd_addr[(bank_g*12) +: 12]),
                .rd_data(act1_rdata[(bank_g*8) +: 8])
            );
        end
    endgenerate

    always @(*) begin
        cfg_input_size      = 8'd128;
        cfg_output_size     = 8'd64;
        cfg_cin             = 6'd1;
        cfg_cout            = 6'd8;
        cfg_mac_count       = 9'd9;
        cfg_pool            = 1'b1;
        cfg_source_external = 1'b1;
        cfg_source_bank     = 1'b0;
        cfg_dest_bank       = 1'b0;
        cfg_weight_base     = 14'd0;
        cfg_bias_base       = 14'd72;
        cfg_multiplier      = 32'sd12390431;
        case (layer)
            3'd1: begin
                cfg_input_size      = 8'd64;
                cfg_output_size     = 8'd32;
                cfg_cin             = 6'd8;
                cfg_cout            = 6'd12;
                cfg_mac_count       = 9'd72;
                cfg_pool            = 1'b1;
                cfg_source_external = 1'b0;
                cfg_source_bank     = 1'b0;
                cfg_dest_bank       = 1'b1;
                cfg_weight_base     = 14'd128;
                cfg_bias_base       = 14'd992;
                cfg_multiplier      = 32'sd11062679;
            end
            3'd2: begin
                cfg_input_size      = 8'd32;
                cfg_output_size     = 8'd16;
                cfg_cin             = 6'd12;
                cfg_cout            = 6'd16;
                cfg_mac_count       = 9'd108;
                cfg_pool            = 1'b1;
                cfg_source_external = 1'b0;
                cfg_source_bank     = 1'b1;
                cfg_dest_bank       = 1'b0;
                cfg_weight_base     = 14'd1088;
                cfg_bias_base       = 14'd2816;
                cfg_multiplier      = 32'sd18665451;
            end
            3'd3: begin
                cfg_input_size      = 8'd16;
                cfg_output_size     = 8'd16;
                cfg_cin             = 6'd16;
                cfg_cout            = 6'd24;
                cfg_mac_count       = 9'd144;
                cfg_pool            = 1'b0;
                cfg_source_external = 1'b0;
                cfg_source_bank     = 1'b0;
                cfg_dest_bank       = 1'b1;
                cfg_weight_base     = 14'd2880;
                cfg_bias_base       = 14'd6336;
                cfg_multiplier      = 32'sd12154226;
            end
            3'd4: begin
                cfg_input_size      = 8'd16;
                cfg_output_size     = 8'd16;
                cfg_cin             = 6'd24;
                cfg_cout            = 6'd5;
                cfg_mac_count       = 9'd216;
                cfg_pool            = 1'b0;
                cfg_source_external = 1'b0;
                cfg_source_bank     = 1'b1;
                cfg_dest_bank       = 1'b0;
                cfg_weight_base     = 14'd6464;
                cfg_bias_base       = 14'd7544;
                cfg_multiplier      = 32'sd0;
            end
            3'd5: begin // G1: F3 -> act1, dilation=2
                cfg_input_size = 8'd16; cfg_output_size = 8'd16;
                cfg_cin = 6'd16; cfg_cout = 6'd8; cfg_mac_count = 9'd144;
                cfg_pool = 1'b0; cfg_source_external = 1'b0;
                cfg_source_bank = 1'b0; cfg_dest_bank = 1'b1;
                cfg_weight_base = 14'd7616; cfg_bias_base = 14'd8768;
                cfg_multiplier = 32'sd2919188;
            end
            3'd6: begin // G2: act1 -> four signed residual channels in act0 scratch
                cfg_input_size = 8'd16; cfg_output_size = 8'd16;
                cfg_cin = 6'd8; cfg_cout = 6'd4; cfg_mac_count = 9'd72;
                cfg_pool = 1'b0; cfg_source_external = 1'b0;
                cfg_source_bank = 1'b1; cfg_dest_bank = 1'b0;
                cfg_weight_base = 14'd8800; cfg_bias_base = 14'd9088;
                cfg_multiplier = 32'sd0;
            end
            default: begin end
        endcase
    end
    always @(*) begin
        case (lane_cursor)
            3'd1: residual_multiplier = 32'sd126680881;
            3'd2: residual_multiplier = 32'sd193904139;
            3'd3: residual_multiplier = 32'sd233575886;
            default: residual_multiplier = 32'sd383048081;
        endcase
    end

    always @(*) begin
        if ((cfg_cout - out_channel_base) >= 6'd8)
            active_lane_count = 5'd8;
        else
            active_lane_count = cfg_cout - out_channel_base;
    end

    always @(*) begin
        case (layer)
            3'd5: begin
                issue_y = $signed({1'b0,issue_base_y}) + (mac_ky * 2) - 2;
                issue_x = $signed({1'b0,issue_base_x}) + (mac_kx * 2) - 2;
            end
            3'd6: begin
                issue_y = $signed({1'b0,issue_base_y}) + ((mac_ky==0)?-9'sd5:(mac_ky==1)?9'sd0:9'sd5);
                issue_x = $signed({1'b0,issue_base_x}) + ((mac_kx==0)?-9'sd5:(mac_kx==1)?9'sd0:9'sd5);
            end
            default: begin
                issue_y = $signed({1'b0,issue_base_y}) + mac_ky - 1;
                issue_x = $signed({1'b0,issue_base_x}) + mac_kx - 1;
            end
        endcase
        issue_padding = (issue_y < 0) || (issue_x < 0) ||
                        (issue_y >= cfg_input_size) || (issue_x >= cfg_input_size);
        issue_pixel_linear = 15'd0;
        issue_pixel_bank_addr = 12'd0;
        if (!issue_padding) begin
            case (layer)
                3'd0: issue_pixel_linear = (issue_y << 7) + issue_x;
                3'd1: begin
                    issue_pixel_linear = (mac_ic * 15'd4096) + (issue_y << 6) + issue_x;
                    issue_pixel_bank_addr = (issue_y << 6) + issue_x;
                end
                3'd2: begin
                    issue_pixel_linear = (mac_ic * 15'd1024) + (issue_y << 5) + issue_x;
                    issue_pixel_bank_addr = ((mac_ic >> 3) << 10) + (issue_y << 5) + issue_x;
                end
                default: begin
                    issue_pixel_linear = (mac_ic * 15'd256) + (issue_y << 4) + issue_x;
                    issue_pixel_bank_addr = ((mac_ic >> 3) << 8) + (issue_y << 4) + issue_x;
                end
            endcase
        end
        for (lane_i = 0; lane_i < 8; lane_i = lane_i + 1)
            issue_weight_byte_addr[lane_i] = channel_weight_base[lane_i] + issue_count;
        issue_fire = (state == S_MAC) && (issue_count < cfg_mac_count);
    end


    always @(*) begin
        input_bram_en    = 1'b0;
        input_bram_addr  = {input_buffer_latched, request_pixel_linear[13:2]};
        model_lane_rd_en = 8'd0;
        model_lane_rd_addr = 96'd0;
        act0_rd_en       = 8'd0;
        act0_rd_addr     = 96'd0;
        act1_rd_en       = 8'd0;
        act1_rd_addr     = 96'd0;

        if (state == S_BIAS_REQ) begin
            for (lane_i = 0; lane_i < 8; lane_i = lane_i + 1) begin
                if (lane_i < active_lane_count) begin
                    model_lane_rd_en[lane_i] = 1'b1;
                    model_lane_rd_addr[(lane_i*12) +: 12] =
                        (cfg_bias_base + ((out_channel_base + lane_i) * 14'd4)) >> 2;
                end
            end
        end else if ((state == S_RES_REQ_LO) || (state == S_RES_REQ_HI)) begin
            act0_rd_en[residual_read_bank0] = 1'b1;
            act0_rd_en[residual_read_bank1] = 1'b1;
            act0_rd_addr[(residual_read_bank0*12) +: 12] =
                residual_cell_addr + ((state == S_RES_REQ_LO) ? 12'h200 : 12'h300);
            act0_rd_addr[(residual_read_bank1*12) +: 12] =
                residual_cell_addr + ((state == S_RES_REQ_LO) ? 12'h200 : 12'h300);
        end else if (issue_fire) begin
            for (lane_i = 0; lane_i < 8; lane_i = lane_i + 1) begin
                if (lane_i < active_lane_count) begin
                    model_lane_rd_en[lane_i] = 1'b1;
                    model_lane_rd_addr[(lane_i*12) +: 12] =
                        issue_weight_byte_addr[lane_i][13:2];
                end
            end
            if (layer == 3'd0) begin
                if (!request_padding)
                    input_bram_en = 1'b1;
            end else if (!request_padding) begin
                if (cfg_source_bank) begin
                    act1_rd_en[request_pixel_bank] = 1'b1;
                    act1_rd_addr[(request_pixel_bank*12) +: 12] = request_pixel_bank_addr;
                end else begin
                    act0_rd_en[request_pixel_bank] = 1'b1;
                    act0_rd_addr[(request_pixel_bank*12) +: 12] = request_pixel_bank_addr;
                end
            end
        end
    end

    wire [7:0] selected_pixel = pixel_zero_d ? 8'd0 :
        (source_external_d ? select_u8(input_bram_data, pixel_lane_d) :
         (source_bank_d ? act1_rdata[(pixel_bank_d*8) +: 8] :
                          act0_rdata[(pixel_bank_d*8) +: 8]));

    wire [7:0] pooled_value =
        (requant_value > pool_max[result_lane]) ? requant_value : pool_max[result_lane];
    wire [17:0] current_accumulator_index =
        accumulator_index(layer, current_lane_channel, out_y, out_x);
    wire [14:0] current_activation_index =
        activation_index(layer, current_lane_channel, out_y, out_x);
    wire [11:0] current_activation_bank_addr =
        activation_write_bank_addr(layer, current_lane_channel, out_y, out_x);

    integer seq_i;
    always @(posedge clk) begin
        if (!rst_n) begin
            state                 <= S_IDLE;
            residual_low <= 16'd0; residual_raw <= 32'sd0; fused_value <= 32'sd0;
            layer                 <= 3'd0;
            out_channel_base      <= 6'd0;
            out_y                 <= 8'd0;
            out_x                 <= 8'd0;
            pool_sub              <= 2'd0;
            lane_cursor           <= 3'd0;
            rq_valid<=0;rq_issued<=0;
            rq_lane0<=0;rq_lane1<=0;rq_lane2<=0;rq_lane3<=0;
            mul_l<=0;mul_r<=0;requant_shifted<=0;requant_value<=0;
            mac_ic                <= 5'd0;
            mac_ky                <= 2'd0;
            mac_kx                <= 2'd0;
            issue_count           <= 9'd0;
            consume_count         <= 9'd0;
            mac_valid_d           <= 1'b0;
            mac_operand_valid     <= 1'b0;
            mac_product_valid     <= 1'b0;
            mac_pixel_operand     <= 8'd0;
            pixel_zero_d          <= 1'b0;
            source_external_d     <= 1'b0;
            source_bank_d         <= 1'b0;
            pixel_bank_d          <= 3'd0;
            pixel_lane_d          <= 2'd0;
            request_padding        <= 1'b0;
            request_pixel_linear   <= 15'd0;
            request_pixel_bank_addr <= 12'd0;
            request_pixel_bank     <= 3'd0;
            requant_product       <= 64'sd0;
            input_buffer_latched  <= 1'b0;
            output_buffer_latched <= 1'b0;
            act0_we               <= 8'd0;
            act0_waddr            <= 96'd0;
            act0_wdata            <= 64'd0;
            act1_we               <= 8'd0;
            act1_waddr            <= 96'd0;
            act1_wdata            <= 64'd0;
            output_bram_we        <= 1'b0;
            output_bram_addr      <= 12'd0;
            output_bram_data      <= 32'd0;
            busy                  <= 1'b0;
            done                  <= 1'b0;
            input_release         <= 1'b0;
            stall                 <= 1'b0;
            debug_acc_valid       <= 1'b0;
            debug_layer           <= 3'd0;
            debug_acc_index       <= 18'd0;
            debug_acc_data        <= 32'd0;
            debug_act_valid       <= 1'b0;
            debug_act_index       <= 15'd0;
            debug_act_data        <= 8'd0;
            for (seq_i = 0; seq_i < 8; seq_i = seq_i + 1) begin
                weight_lane_d[seq_i]       <= 2'd0;
                mac_weight_operand[seq_i]  <= 8'sd0;
                mac_product_d[seq_i]       <= 17'sd0;
                bias_cache[seq_i]          <= 32'sd0;
                accumulator[seq_i]         <= 32'sd0;
                post_acc32[seq_i]          <= 32'sd0;
                pool_max[seq_i]            <= 8'd0;
                channel_weight_base[seq_i] <= 14'd0;
            end
        end else begin
            done            <= 1'b0;
            input_release   <= 1'b0;
            stall           <= 1'b0;
            act0_we         <= 8'd0;
            act1_we         <= 8'd0;
            output_bram_we  <= 1'b0;
            debug_acc_valid <= 1'b0;
            debug_act_valid <= 1'b0;

            // The shared arithmetic registers are free during the lane drain.
            // A lane tag travels with each product; pool/writeback uses that
            // tag rather than the next lane being issued. No extra multiplier.
            if (PIPELINED_REQUANT!=0 && state==S_REQUANT_STREAM) begin
                rq_valid <= {rq_valid[2:0],rq_issued<active_lane_count};
                if(rq_issued<active_lane_count) begin
                    mul_l<=post_acc32[rq_issued[2:0]];mul_r<=cfg_multiplier;
                    rq_lane0<=rq_issued[2:0];rq_issued<=rq_issued+1'b1;
                end
                rq_lane1<=rq_lane0;rq_lane2<=rq_lane1;rq_lane3<=rq_lane2;
                if(rq_valid[0]) requant_product<=$signed(mul_l)*$signed(mul_r);
                if(rq_valid[1]) requant_shifted<=($signed(requant_product)+64'sd1073741824)>>>31;
                if(rq_valid[2]) begin
                    if(requant_shifted<0)requant_value<=0;
                    else if(requant_shifted>255)requant_value<=255;
                    else requant_value<=requant_shifted[7:0];
                end
            end else rq_valid<=0;

            if (state != S_MAC) begin
                mac_valid_d       <= 1'b0;
                mac_operand_valid <= 1'b0;
                mac_product_valid <= 1'b0;
            end

            case (state)
                S_IDLE: begin
                    busy <= 1'b0;
                    if (start) begin
                        busy                  <= 1'b1;
                        layer                 <= 3'd0;
                        out_channel_base      <= 6'd0;
                        out_y                 <= 8'd0;
                        out_x                 <= 8'd0;
                        pool_sub              <= 2'd0;
                        lane_cursor           <= 3'd0;
                        input_buffer_latched  <= input_buffer_id;
                        output_buffer_latched <= output_buffer_id;
                        state                 <= S_BIAS_REQ;
                    end
                end

                S_BIAS_REQ: begin
                    for (seq_i = 0; seq_i < 8; seq_i = seq_i + 1)
                        channel_weight_base[seq_i] <= cfg_weight_base +
                            ((out_channel_base + seq_i) * cfg_cin * 14'd9);
                    state <= S_BIAS_WAIT;
                end

                S_BIAS_WAIT: begin
                    for (seq_i = 0; seq_i < 8; seq_i = seq_i + 1) begin
                        if (seq_i < active_lane_count)
                            bias_cache[seq_i] <=
                                $signed(model_lane_rd_data[(seq_i*32) +: 32]);
                        else
                            bias_cache[seq_i] <= 32'sd0;
                    end
                    state <= S_PIXEL_START;
                end

                S_PIXEL_START: begin
                    issue_base_y<=conv_y;issue_base_x<=conv_x;
                    for (seq_i = 0; seq_i < 8; seq_i = seq_i + 1)
                        accumulator[seq_i] <= bias_cache[seq_i];
                    issue_count       <= 9'd0;
                    consume_count     <= 9'd0;
                    mac_ic            <= 5'd0;
                    mac_ky            <= 2'd0;
                    mac_kx            <= 2'd0;
                    mac_valid_d       <= 1'b0;
                    mac_operand_valid <= 1'b0;
                    mac_product_valid <= 1'b0;
                    lane_cursor       <= 3'd0;
                    state             <= S_MAC_PRIME;
                end


                S_MAC_PRIME: begin
                    request_padding        <= issue_padding;
                    request_pixel_linear   <= issue_pixel_linear;
                    request_pixel_bank_addr <= issue_pixel_bank_addr;
                    request_pixel_bank     <= mac_ic[2:0];
                    if (mac_kx == 2) begin
                        mac_kx <= 2'd0;
                        if (mac_ky == 2) begin
                            mac_ky <= 2'd0;
                            mac_ic <= mac_ic + 5'd1;
                        end else begin
                            mac_ky <= mac_ky + 2'd1;
                        end
                    end else begin
                        mac_kx <= mac_kx + 2'd1;
                    end
                    state <= S_MAC;
                end
                S_MAC: begin
                    mac_valid_d       <= issue_fire;
                    mac_operand_valid <= mac_valid_d;
                    mac_product_valid <= mac_operand_valid;
                    if (mac_valid_d) begin
                        mac_pixel_operand <= selected_pixel;
                        for (seq_i = 0; seq_i < 8; seq_i = seq_i + 1) begin
                            if (seq_i < active_lane_count)
                                mac_weight_operand[seq_i] <= select_s8(
                                    model_lane_rd_data[(seq_i*32) +: 32],
                                    weight_lane_d[seq_i]
                                );
                        end
                    end
                    if (mac_operand_valid) begin
                        for (seq_i = 0; seq_i < 8; seq_i = seq_i + 1) begin
                            if (seq_i < active_lane_count)
                                mac_product_d[seq_i] <=
                                    $signed({1'b0, mac_pixel_operand}) *
                                    $signed(mac_weight_operand[seq_i]);
                        end
                    end
                    if (issue_fire) begin
                        for (seq_i = 0; seq_i < 8; seq_i = seq_i + 1)
                            weight_lane_d[seq_i] <= issue_weight_byte_addr[seq_i][1:0];
                        pixel_zero_d      <= request_padding;
                        source_external_d <= cfg_source_external;
                        source_bank_d     <= cfg_source_bank;
                        pixel_bank_d      <= request_pixel_bank;
                        pixel_lane_d      <= request_pixel_linear[1:0];
                        issue_count       <= issue_count + 9'd1;
                        if ((issue_count + 9'd1) < cfg_mac_count) begin
                            request_padding        <= issue_padding;
                            request_pixel_linear   <= issue_pixel_linear;
                            request_pixel_bank_addr <= issue_pixel_bank_addr;
                            request_pixel_bank     <= mac_ic[2:0];
                        if (mac_kx == 2) begin
                            mac_kx <= 2'd0;
                            if (mac_ky == 2) begin
                                mac_ky <= 2'd0;
                                mac_ic <= mac_ic + 5'd1;
                            end else begin
                                mac_ky <= mac_ky + 2'd1;
                            end
                        end else begin
                            mac_kx <= mac_kx + 2'd1;
                        end
                        end
                    end

                    if (mac_product_valid) begin
                        for (seq_i = 0; seq_i < 8; seq_i = seq_i + 1) begin
                            if (seq_i < active_lane_count)
                                accumulator[seq_i] <= accumulator[seq_i] +
                                    {{15{mac_product_d[seq_i][16]}}, mac_product_d[seq_i]};
                        end
                        consume_count <= consume_count + 9'd1;
                        if ((consume_count + 9'd1) == cfg_mac_count) begin
                            for (seq_i = 0; seq_i < 8; seq_i = seq_i + 1) begin
                                if (seq_i < active_lane_count)
                                    post_acc32[seq_i] <= accumulator[seq_i] +
                                        {{15{mac_product_d[seq_i][16]}}, mac_product_d[seq_i]};
                            end
                            mac_valid_d       <= 1'b0;
                            mac_operand_valid <= 1'b0;
                            mac_product_valid <= 1'b0;
                            lane_cursor       <= 3'd0;
                            if (layer == 3'd6)
                                state <= S_STORE_RAW;
                            else if (layer == 3'd4)
                                state <= S_FUSE_ADD; // confidence lane bypass
                            else
                                state <= S_REQUANT_PREP;
                        end
                    end
                end

                S_REQUANT_PREP:begin
                    if(PIPELINED_REQUANT!=0) begin
                        // post_acc32 is already registered: issue lane zero
                        // in PREP rather than spending an empty stream cycle.
                        mul_l<=post_acc32[0];mul_r<=cfg_multiplier;rq_lane0<=0;
                        rq_valid<=4'b0001;rq_issued<=1;state<=S_REQUANT_STREAM;
                    end else begin
                        mul_l<=post_acc32[lane_cursor];mul_r<=cfg_multiplier;
                        state<=S_REQUANT_MUL;
                    end
                end
                S_REQUANT_MUL: begin
                    requant_product <= $signed(mul_l)*$signed(mul_r);
                    state <= S_REQUANT_ROUND;
                end

                S_REQUANT_ROUND: begin
                    requant_shifted<=($signed(requant_product)+64'sd1073741824)>>>31;
                    state<=S_REQUANT_CLAMP;
                end
                S_REQUANT_CLAMP: begin
                    if(requant_shifted<0)requant_value<=0;
                    else if(requant_shifted>255)requant_value<=255;
                    else requant_value<=requant_shifted[7:0];
                    state<=S_REQUANT_OUT;
                end
                S_REQUANT_OUT,S_REQUANT_STREAM: if(state==S_REQUANT_OUT || rq_valid[3]) begin
                    debug_acc_valid <= 1'b1;
                    debug_layer     <= layer;
                    debug_acc_index <= accumulator_index(
                        layer, current_lane_channel, conv_y, conv_x
                    );
                    debug_acc_data  <= post_acc32[result_lane];

                    if (cfg_pool && (pool_sub != 2'd3)) begin
                        if ((pool_sub == 2'd0) ||
                            (requant_value > pool_max[result_lane]))
                            pool_max[result_lane] <= requant_value;
                        if (current_lane_last) begin
                            lane_cursor <= 3'd0;
                            pool_sub    <= pool_sub + 2'd1;
                            state       <= S_PIXEL_START;
                        end else if(state==S_REQUANT_OUT) begin
                            lane_cursor <= lane_cursor + 3'd1;
                            state <= S_REQUANT_PREP;
                        end
                    end else begin
                        debug_act_valid <= 1'b1;
                        debug_act_index <= current_activation_index;
                        debug_act_data  <= cfg_pool ? pooled_value : requant_value;
                        if (!cfg_dest_bank) begin
                            act0_we[current_lane_channel[2:0]] <= 1'b1;
                            act0_waddr[(current_lane_channel[2:0]*12) +: 12] <=
                                current_activation_bank_addr;
                            act0_wdata[(current_lane_channel[2:0]*8) +: 8] <=
                                cfg_pool ? pooled_value : requant_value;
                        end else begin
                            act1_we[current_lane_channel[2:0]] <= 1'b1;
                            act1_waddr[(current_lane_channel[2:0]*12) +: 12] <=
                                current_activation_bank_addr;
                            act1_wdata[(current_lane_channel[2:0]*8) +: 8] <=
                                cfg_pool ? pooled_value : requant_value;
                        end

                        if (!current_lane_last) begin
                            if(state==S_REQUANT_OUT) begin
                                lane_cursor <= lane_cursor + 3'd1;
                                state <= S_REQUANT_PREP;
                            end
                        end else begin
                            lane_cursor <= 3'd0;
                            pool_sub    <= 2'd0;
                            if ((out_x + 8'd1) < cfg_output_size) begin
                                out_x <= out_x + 8'd1;
                                state <= S_PIXEL_START;
                            end else if ((out_y + 8'd1) < cfg_output_size) begin
                                out_x <= 8'd0;
                                out_y <= out_y + 8'd1;
                                state <= S_PIXEL_START;
                            end else if ((out_channel_base + active_lane_count) < cfg_cout) begin
                                out_x            <= 8'd0;
                                out_y            <= 8'd0;
                                out_channel_base <= out_channel_base + active_lane_count;
                                state            <= S_BIAS_REQ;
                            end else begin
                                if (layer == 3'd0)
                                    input_release <= 1'b1;
                                case (layer)
                                    3'd2: layer <= 3'd5;
                                    3'd5: layer <= 3'd6;
                                    default: layer <= layer + 3'd1;
                                endcase
                                out_channel_base <= 6'd0;
                                out_y            <= 8'd0;
                                out_x            <= 8'd0;
                                state            <= S_BIAS_REQ;
                            end
                        end
                    end
                end

                S_STORE_RAW: begin // G2: low two bytes, two banks per cycle
                    debug_acc_valid <= 1'b1; debug_layer <= layer;
                    debug_acc_index <= current_accumulator_index;
                    debug_acc_data <= post_acc32[lane_cursor];
                    act0_we[residual_write_bank0] <= 1'b1;
                    act0_we[residual_write_bank1] <= 1'b1;
                    act0_waddr[(residual_write_bank0*12) +: 12] <= 12'h200 + residual_cell_addr;
                    act0_waddr[(residual_write_bank1*12) +: 12] <= 12'h200 + residual_cell_addr;
                    act0_wdata[(residual_write_bank0*8) +: 8] <= post_acc32[lane_cursor][7:0];
                    act0_wdata[(residual_write_bank1*8) +: 8] <= post_acc32[lane_cursor][15:8];
                    state <= S_RES_STORE_HI;
                end
                S_RES_STORE_HI: begin
                    act0_we[residual_write_bank0] <= 1'b1;
                    act0_we[residual_write_bank1] <= 1'b1;
                    act0_waddr[(residual_write_bank0*12) +: 12] <= 12'h300 + residual_cell_addr;
                    act0_waddr[(residual_write_bank1*12) +: 12] <= 12'h300 + residual_cell_addr;
                    act0_wdata[(residual_write_bank0*8) +: 8] <= post_acc32[lane_cursor][23:16];
                    act0_wdata[(residual_write_bank1*8) +: 8] <= post_acc32[lane_cursor][31:24];
                    if (!current_lane_last) begin
                        lane_cursor <= lane_cursor + 3'd1; state <= S_STORE_RAW;
                    end else begin
                        lane_cursor <= 3'd0;
                        if (out_x != 8'd15) begin out_x <= out_x + 8'd1; state <= S_PIXEL_START; end
                        else if (out_y != 8'd15) begin out_x <= 8'd0; out_y <= out_y + 8'd1; state <= S_PIXEL_START; end
                        else begin
                            layer <= 3'd3; out_x <= 8'd0; out_y <= 8'd0;
                            out_channel_base <= 6'd0; state <= S_BIAS_REQ;
                        end
                    end
                end
                S_RES_REQ_LO: state <= S_RES_WAIT_LO;
                S_RES_WAIT_LO: begin
                    residual_low <= {act0_rdata[(residual_read_bank1*8) +: 8],
                                     act0_rdata[(residual_read_bank0*8) +: 8]};
                    state <= S_RES_REQ_HI;
                end
                S_RES_REQ_HI: state <= S_RES_WAIT_HI;
                S_RES_WAIT_HI: begin
                    residual_raw <= {act0_rdata[(residual_read_bank1*8) +: 8],
                                     act0_rdata[(residual_read_bank0*8) +: 8], residual_low};
                    state <= S_FUSE_PREP;
                end
                S_FUSE_PREP:begin
                    mul_l<=residual_raw;mul_r<=residual_multiplier;state<=S_FUSE_MUL;
                end
                S_FUSE_MUL: begin
                    requant_product <= $signed(mul_l)*$signed(mul_r);
                    state <= S_RES_ROUND;
                end
                S_RES_ROUND: begin
                    residual_aligned_reg<=residual_aligned;
                    state<=S_FUSE_ADD;
                end
                S_FUSE_ADD: begin
                    fused_value <= (lane_cursor == 3'd0) ? post_acc32[0] : fused_sum[31:0];
                    state <= S_OUTPUT;
                end
                S_OUTPUT: begin
                    debug_acc_valid <= 1'b1; debug_layer <= layer;
                    debug_acc_index <= current_accumulator_index;
                    debug_acc_data <= post_acc32[lane_cursor];
                    output_bram_we <= 1'b1;
                    output_bram_addr <= {output_buffer_latched, current_accumulator_index[10:0]};
                    output_bram_data <= fused_value;
                    if (!current_lane_last) begin
                        lane_cursor <= lane_cursor + 3'd1; state <= S_RES_REQ_LO;
                    end else begin
                        lane_cursor <= 3'd0;
                        if (out_x != 8'd15) begin out_x <= out_x + 8'd1; state <= S_PIXEL_START; end
                        else if (out_y != 8'd15) begin out_x <= 8'd0; out_y <= out_y + 8'd1; state <= S_PIXEL_START; end
                        else state <= S_FLUSH;
                    end
                end

                S_FLUSH: begin
                    busy  <= 1'b0;
                    done  <= 1'b1;
                    state <= S_IDLE;
                end

                default: begin
                    busy  <= 1'b0;
                    state <= S_IDLE;
                end
            endcase
        end
    end

    wire [31:0] _unused_frame_id = frame_id;

endmodule
