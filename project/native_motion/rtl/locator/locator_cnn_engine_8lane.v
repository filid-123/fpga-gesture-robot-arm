// ============================================================================
// Phase 2 Locator v16 CNN with eight output-channel MAC lanes.
//
// The eight lanes share one activation read and advance over the same input
// channel / 3x3 tap.  Model read bandwidth comes from eight write-through
// replicas of the frozen parameter memory.  Requantization and final output
// writes remain serialized by lane: this keeps the 32x32 multiplier and the
// single-port output BRAM shared while removing the dominant serial output-
// channel loop from Conv1..Conv5.
//
// Activation channels are banked by channel[2:0].  The logical CHW layout and
// the external Locator ABI are unchanged.
// ============================================================================
`timescale 1ns / 1ps

module locator_cnn_engine_8lane (
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
    output reg  [87:0]  model_lane_rd_addr,
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

    localparam S_IDLE         = 4'd0;
    localparam S_BIAS_REQ     = 4'd1;
    localparam S_BIAS_WAIT    = 4'd2;
    localparam S_PIXEL_START  = 4'd3;
    localparam S_MAC          = 4'd4;
    localparam S_REQUANT_MUL  = 4'd5;
    localparam S_REQUANT_OUT  = 4'd6;
    localparam S_STORE_RAW    = 4'd7;
    localparam S_FLUSH        = 4'd8;
    localparam S_MAC_PRIME    = 4'd9;

    reg [3:0] state;
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
    reg [12:0] cfg_weight_base;
    reg [12:0] cfg_bias_base;
    reg signed [31:0] cfg_multiplier;
    reg [3:0] active_lane_count;

    integer issue_y;
    integer issue_x;
    reg issue_padding;
    reg [14:0] issue_pixel_linear;
    reg [11:0] issue_pixel_bank_addr;
    reg [13:0] issue_weight_byte_addr [0:7];
    reg issue_fire;
    integer lane_i;

    wire [7:0] conv_y = cfg_pool ? ((out_y << 1) + pool_sub[1]) : out_y;
    wire [7:0] conv_x = cfg_pool ? ((out_x << 1) + pool_sub[0]) : out_x;
    wire [5:0] current_lane_channel = out_channel_base + {3'd0, lane_cursor};
    wire current_lane_last = ({1'b0, lane_cursor} + 4'd1) == active_lane_count;

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
            locator_act_bank_4k u_act1 (
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
        cfg_weight_base     = 13'd0;
        cfg_bias_base       = 13'd72;
        cfg_multiplier      = 32'sd8802987;
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
                cfg_weight_base     = 13'd128;
                cfg_bias_base       = 13'd992;
                cfg_multiplier      = 32'sd9344399;
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
                cfg_weight_base     = 13'd1088;
                cfg_bias_base       = 13'd2816;
                cfg_multiplier      = 32'sd13437907;
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
                cfg_weight_base     = 13'd2880;
                cfg_bias_base       = 13'd6336;
                cfg_multiplier      = 32'sd13500053;
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
                cfg_weight_base     = 13'd6464;
                cfg_bias_base       = 13'd7544;
                cfg_multiplier      = 32'sd0;
            end
            default: begin end
        endcase
    end

    always @(*) begin
        if ((cfg_cout - out_channel_base) >= 6'd8)
            active_lane_count = 4'd8;
        else
            active_lane_count = cfg_cout - out_channel_base;
    end

    always @(*) begin
        issue_y = conv_y + mac_ky - 1;
        issue_x = conv_x + mac_kx - 1;
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
        model_lane_rd_addr = 88'd0;
        act0_rd_en       = 8'd0;
        act0_rd_addr     = 96'd0;
        act1_rd_en       = 8'd0;
        act1_rd_addr     = 96'd0;

        if (state == S_BIAS_REQ) begin
            for (lane_i = 0; lane_i < 8; lane_i = lane_i + 1) begin
                if (lane_i < active_lane_count) begin
                    model_lane_rd_en[lane_i] = 1'b1;
                    model_lane_rd_addr[(lane_i*11) +: 11] =
                        (cfg_bias_base + ((out_channel_base + lane_i) * 14'd4)) >> 2;
                end
            end
        end else if (issue_fire) begin
            for (lane_i = 0; lane_i < 8; lane_i = lane_i + 1) begin
                if (lane_i < active_lane_count) begin
                    model_lane_rd_en[lane_i] = 1'b1;
                    model_lane_rd_addr[(lane_i*11) +: 11] =
                        issue_weight_byte_addr[lane_i][12:2];
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
    wire [7:0] requant_value = requant_clamp_u8(requant_product);
    wire [7:0] pooled_value =
        (requant_value > pool_max[lane_cursor]) ? requant_value : pool_max[lane_cursor];
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
            layer                 <= 3'd0;
            out_channel_base      <= 6'd0;
            out_y                 <= 8'd0;
            out_x                 <= 8'd0;
            pool_sub              <= 2'd0;
            lane_cursor           <= 3'd0;
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
                            if (layer == 3'd4)
                                state <= S_STORE_RAW;
                            else
                                state <= S_REQUANT_MUL;
                        end
                    end
                end

                S_REQUANT_MUL: begin
                    requant_product <= $signed(post_acc32[lane_cursor]) *
                                       $signed(cfg_multiplier);
                    state <= S_REQUANT_OUT;
                end

                S_REQUANT_OUT: begin
                    debug_acc_valid <= 1'b1;
                    debug_layer     <= layer;
                    debug_acc_index <= accumulator_index(
                        layer, current_lane_channel, conv_y, conv_x
                    );
                    debug_acc_data  <= post_acc32[lane_cursor];

                    if (cfg_pool && (pool_sub != 2'd3)) begin
                        if ((pool_sub == 2'd0) ||
                            (requant_value > pool_max[lane_cursor]))
                            pool_max[lane_cursor] <= requant_value;
                        if (current_lane_last) begin
                            lane_cursor <= 3'd0;
                            pool_sub    <= pool_sub + 2'd1;
                            state       <= S_PIXEL_START;
                        end else begin
                            lane_cursor <= lane_cursor + 3'd1;
                            state       <= S_REQUANT_MUL;
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
                            lane_cursor <= lane_cursor + 3'd1;
                            state       <= S_REQUANT_MUL;
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
                                layer            <= layer + 3'd1;
                                out_channel_base <= 6'd0;
                                out_y            <= 8'd0;
                                out_x            <= 8'd0;
                                state            <= S_BIAS_REQ;
                            end
                        end
                    end
                end

                S_STORE_RAW: begin
                    debug_acc_valid  <= 1'b1;
                    debug_layer      <= layer;
                    debug_acc_index  <= current_accumulator_index;
                    debug_acc_data   <= post_acc32[lane_cursor];
                    output_bram_we   <= 1'b1;
                    output_bram_addr <= {output_buffer_latched,
                                         current_accumulator_index[10:0]};
                    output_bram_data <= post_acc32[lane_cursor];
                    if (!current_lane_last) begin
                        lane_cursor <= lane_cursor + 3'd1;
                    end else begin
                        lane_cursor <= 3'd0;
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
                            state <= S_FLUSH;
                        end
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
