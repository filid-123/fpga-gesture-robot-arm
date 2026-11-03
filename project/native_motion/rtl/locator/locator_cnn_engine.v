// ============================================================================
// Frozen v12 Phase 2-L1 Locator CNN, L1-A scalar-MAC implementation.
//
// Conv1..Conv3 are fused with 2x2 max-pool, so their full pre-pool maps are
// never stored.  Two 32 KiB byte-wide activation memories alternate between
// layers.  Conv5 writes raw signed int32 CHW values to the selected output
// bank without ReLU or requantization.
// ============================================================================
`timescale 1ns / 1ps

module locator_cnn_engine (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    input  wire        input_buffer_id,
    input  wire        output_buffer_id,
    input  wire [31:0] frame_id,

    output reg         input_bram_en,
    output reg  [12:0] input_bram_addr,
    input  wire [31:0] input_bram_data,

    output reg         output_bram_we,
    output reg  [11:0] output_bram_addr,
    output reg  [31:0] output_bram_data,

    output reg         model_rd_en,
    output reg  [10:0] model_rd_addr,
    input  wire [31:0] model_rd_data,

    output reg         busy,
    output reg         done,
    output reg         input_release,
    output reg         stall,

    // Simulation/bring-up observability.  These signals do not require an AXI
    // window and may be left unconnected in the integrated top level.
    output reg         debug_acc_valid,
    output reg  [2:0]  debug_layer,
    output reg  [17:0] debug_acc_index,
    output reg  [31:0] debug_acc_data,
    output reg         debug_act_valid,
    output reg  [14:0] debug_act_index,
    output reg  [7:0]  debug_act_data
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

    reg [3:0] state;
    reg [2:0] layer;
    reg [5:0] out_channel;
    reg [7:0] out_y;
    reg [7:0] out_x;
    reg [1:0] pool_sub;

    reg [4:0] mac_ic;
    reg [1:0] mac_ky;
    reg [1:0] mac_kx;
    reg [8:0] issue_count;
    reg [8:0] consume_count;
    reg       mac_valid_d;
    reg       mac_operand_valid;
    reg       mac_product_valid;
    reg [7:0] mac_pixel_operand;
    reg signed [7:0] mac_weight_operand;
    reg signed [16:0] mac_product_d;
    reg [1:0] weight_lane_d;
    reg [1:0] pixel_lane_d;
    reg       pixel_zero_d;
    reg       source_external_d;
    reg       source_bank_d;

    reg signed [31:0] bias_cache;
    reg signed [31:0] accumulator;
    reg signed [31:0] post_acc32;
    reg signed [63:0] requant_product;
    reg [7:0] pool_max;

    reg input_buffer_latched;
    reg output_buffer_latched;

    reg        act0_we;
    reg [14:0] act0_waddr;
    reg [7:0]  act0_wdata;
    reg        act1_we;
    reg [14:0] act1_waddr;
    reg [7:0]  act1_wdata;
    reg        act_read_en;
    reg [14:0] act_read_addr;
    wire [7:0] act0_rdata;
    wire [7:0] act1_rdata;

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
    reg [13:0] channel_weight_base;

    integer issue_y;
    integer issue_x;
    integer external_issue_y;
    integer external_issue_x;
    reg external_issue_valid;
    reg issue_padding;
    reg [14:0] issue_pixel_linear;
    reg [13:0] external_pixel_linear;
    reg [13:0] issue_weight_byte_addr;
    reg [13:0] issue_bias_byte_addr;
    reg issue_fire;

    wire [7:0] conv_y = cfg_pool ? ((out_y << 1) + pool_sub[1]) : out_y;
    wire [7:0] conv_x = cfg_pool ? ((out_x << 1) + pool_sub[0]) : out_x;

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
            rounded = product + 64'sd1073741824; // 1 << (31 - 1)
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

    wire [17:0] current_accumulator_index =
        accumulator_index(layer, out_channel, out_y, out_x);

    locator_act_bram u_act0 (
        .clk(clk),
        .wr_en(act0_we),
        .wr_addr(act0_waddr),
        .wr_data(act0_wdata),
        .rd_en(act_read_en && !cfg_source_external && !cfg_source_bank),
        .rd_addr(act_read_addr),
        .rd_data(act0_rdata)
    );

    locator_act_bram u_act1 (
        .clk(clk),
        .wr_en(act1_we),
        .wr_addr(act1_waddr),
        .wr_data(act1_wdata),
        .rd_en(act_read_en && !cfg_source_external && cfg_source_bank),
        .rd_addr(act_read_addr),
        .rd_data(act1_rdata)
    );

    // Fixed v16 layer contract.  Offsets are byte offsets in the 7,616-byte
    // little-endian parameter blob.
    always @(*) begin
        cfg_input_size     = 8'd128;
        cfg_output_size    = 8'd64;
        cfg_cin            = 6'd1;
        cfg_cout           = 6'd8;
        cfg_mac_count      = 9'd9;
        cfg_pool           = 1'b1;
        cfg_source_external= 1'b1;
        cfg_source_bank    = 1'b0;
        cfg_dest_bank      = 1'b0;
        cfg_weight_base    = 13'd0;
        cfg_bias_base      = 13'd72;
        cfg_multiplier     = 32'sd8802987;
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

    // Current MAC issue address.  All spatial dimensions are powers of two,
    // so activation addressing synthesizes as shifts/adds.
    always @(*) begin
        issue_y = conv_y + mac_ky - 1;
        issue_x = conv_x + mac_kx - 1;
        issue_padding = (issue_y < 0) || (issue_x < 0) ||
                        (issue_y >= cfg_input_size) || (issue_x >= cfg_input_size);
        issue_pixel_linear = 15'd0;
        if (!issue_padding) begin
            case (layer)
                3'd0: issue_pixel_linear = (issue_y << 7) + issue_x;
                3'd1: issue_pixel_linear = (mac_ic * 15'd4096) + (issue_y << 6) + issue_x;
                3'd2: issue_pixel_linear = (mac_ic * 15'd1024) + (issue_y << 5) + issue_x;
                default: issue_pixel_linear = (mac_ic * 15'd256) + (issue_y << 4) + issue_x;
            endcase
        end
        // OIHW weights for one output channel are contiguous.  Register the
        // channel base outside S_MAC so the BRAM address path contains only
        // this short sequential tap offset.
        issue_weight_byte_addr = channel_weight_base + issue_count;
        issue_bias_byte_addr = cfg_bias_base + (out_channel * 14'd4);
        issue_fire = (state == S_MAC) && (issue_count < cfg_mac_count);
    end

    // The external input port is used only by Conv1.  Keep its BRAM address
    // independent of the layer/configuration mux so the registered layer ID
    // is not on a long carry-chain path to the external RAM address pins.
    // The value is don't-care whenever input_bram_en is low.
    always @(*) begin
        external_issue_y = ((out_y << 1) + pool_sub[1]) + mac_ky - 1;
        external_issue_x = ((out_x << 1) + pool_sub[0]) + mac_kx - 1;
        external_pixel_linear = 14'd0;
        external_issue_valid = (external_issue_y >= 0) && (external_issue_y < 128) &&
                               (external_issue_x >= 0) && (external_issue_x < 128);
        if (external_issue_valid)
            external_pixel_linear = (external_issue_y << 7) + external_issue_x;
    end

    // Combinational read requests give the synchronous memories a one-cycle
    // request-to-data pipeline while allowing one scalar MAC to retire per clk.
    always @(*) begin
        input_bram_en   = 1'b0;
        input_bram_addr = {input_buffer_latched, external_pixel_linear[13:2]};
        act_read_en     = 1'b0;
        act_read_addr   = issue_pixel_linear;
        model_rd_en     = 1'b0;
        model_rd_addr   = 11'd0;

        if (state == S_BIAS_REQ) begin
            model_rd_en   = 1'b1;
            model_rd_addr = issue_bias_byte_addr[12:2];
        end else if (issue_fire) begin
            model_rd_en   = 1'b1;
            model_rd_addr = issue_weight_byte_addr[12:2];
            // Conv1 is the only external-source layer.  Use its independent
            // fixed 128x128 boundary result on the BRAM enable path instead
            // of the generic layer/configuration mux.  This is logically
            // equivalent but removes a long layer-to-BRAM-EN carry chain.
            if (layer == 3'd0) begin
                if (external_issue_valid)
                    input_bram_en   = 1'b1;
            end else if (!issue_padding) begin
                    act_read_en   = 1'b1;
                    act_read_addr = issue_pixel_linear;
            end
        end
    end

    wire [7:0] selected_pixel = pixel_zero_d ? 8'd0 :
                                (source_external_d ? select_u8(input_bram_data, pixel_lane_d) :
                                 (source_bank_d ? act1_rdata : act0_rdata));
    wire signed [7:0] selected_weight = select_s8(model_rd_data, weight_lane_d);
    // Register both operands before multiplication.  This cuts the synchronous
    // BRAM/LUTRAM read and byte-select muxes out of the multiplier input path,
    // while preserving a one-MAC-per-cycle steady-state pipeline.
    wire signed [16:0] mac_product_comb =
        $signed({1'b0, mac_pixel_operand}) * $signed(mac_weight_operand);
    wire signed [31:0] mac_product_ext =
        {{15{mac_product_d[16]}}, mac_product_d};
    wire [7:0] requant_value = requant_clamp_u8(requant_product);
    wire [7:0] pooled_value = (requant_value > pool_max) ? requant_value : pool_max;

    always @(posedge clk) begin
        if (!rst_n) begin
            state                 <= S_IDLE;
            layer                 <= 3'd0;
            out_channel           <= 6'd0;
            out_y                 <= 8'd0;
            out_x                 <= 8'd0;
            pool_sub              <= 2'd0;
            mac_ic                <= 5'd0;
            mac_ky                <= 2'd0;
            mac_kx                <= 2'd0;
            issue_count           <= 9'd0;
            consume_count         <= 9'd0;
            mac_valid_d           <= 1'b0;
            mac_operand_valid     <= 1'b0;
            mac_product_valid     <= 1'b0;
            mac_pixel_operand     <= 8'd0;
            mac_weight_operand    <= 8'sd0;
            mac_product_d         <= 17'sd0;
            weight_lane_d         <= 2'd0;
            pixel_lane_d          <= 2'd0;
            pixel_zero_d          <= 1'b0;
            source_external_d     <= 1'b0;
            source_bank_d         <= 1'b0;
            bias_cache            <= 32'sd0;
            accumulator           <= 32'sd0;
            post_acc32            <= 32'sd0;
            requant_product       <= 64'sd0;
            pool_max              <= 8'd0;
            channel_weight_base   <= 14'd0;
            input_buffer_latched  <= 1'b0;
            output_buffer_latched <= 1'b0;
            act0_we               <= 1'b0;
            act0_waddr            <= 15'd0;
            act0_wdata            <= 8'd0;
            act1_we               <= 1'b0;
            act1_waddr            <= 15'd0;
            act1_wdata            <= 8'd0;
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
        end else begin
            done            <= 1'b0;
            input_release   <= 1'b0;
            stall           <= 1'b0;
            act0_we         <= 1'b0;
            act1_we         <= 1'b0;
            output_bram_we  <= 1'b0;
            debug_acc_valid <= 1'b0;
            debug_act_valid <= 1'b0;

            if (state != S_MAC) begin
                mac_valid_d <= 1'b0;
                mac_operand_valid <= 1'b0;
                mac_product_valid <= 1'b0;
            end

            case (state)
                S_IDLE: begin
                    busy <= 1'b0;
                    if (start) begin
                        busy                  <= 1'b1;
                        layer                 <= 3'd0;
                        out_channel           <= 6'd0;
                        out_y                 <= 8'd0;
                        out_x                 <= 8'd0;
                        pool_sub              <= 2'd0;
                        input_buffer_latched  <= input_buffer_id;
                        output_buffer_latched <= output_buffer_id;
                        state                 <= S_BIAS_REQ;
                    end
                end

                S_BIAS_REQ: begin
                    channel_weight_base <= cfg_weight_base +
                                           (out_channel * cfg_cin * 14'd9);
                    state <= S_BIAS_WAIT;
                end

                S_BIAS_WAIT: begin
                    bias_cache <= $signed(model_rd_data);
                    state      <= S_PIXEL_START;
                end

                S_PIXEL_START: begin
                    accumulator   <= bias_cache;
                    issue_count   <= 9'd0;
                    consume_count <= 9'd0;
                    mac_ic        <= 5'd0;
                    mac_ky        <= 2'd0;
                    mac_kx        <= 2'd0;
                    mac_valid_d   <= 1'b0;
                    mac_operand_valid <= 1'b0;
                    mac_product_valid <= 1'b0;
                    state         <= S_MAC;
                end

                S_MAC: begin
                    mac_valid_d       <= issue_fire;
                    mac_operand_valid <= mac_valid_d;
                    mac_product_valid <= mac_operand_valid;
                    if (mac_valid_d) begin
                        mac_pixel_operand  <= selected_pixel;
                        mac_weight_operand <= selected_weight;
                    end
                    if (mac_operand_valid)
                        mac_product_d <= mac_product_comb;
                    if (issue_fire) begin
                        weight_lane_d     <= issue_weight_byte_addr[1:0];
                        pixel_lane_d      <= issue_pixel_linear[1:0];
                        pixel_zero_d      <= issue_padding;
                        source_external_d <= cfg_source_external;
                        source_bank_d     <= cfg_source_bank;
                        issue_count       <= issue_count + 9'd1;
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

                    if (mac_product_valid) begin
                        accumulator   <= accumulator + mac_product_ext;
                        consume_count <= consume_count + 9'd1;
                        if ((consume_count + 9'd1) == cfg_mac_count) begin
                            post_acc32      <= accumulator + mac_product_ext;
                            debug_acc_valid <= 1'b1;
                            debug_layer     <= layer;
                            debug_acc_index <= accumulator_index(layer, out_channel, conv_y, conv_x);
                            debug_acc_data  <= accumulator + mac_product_ext;
                            mac_valid_d       <= 1'b0;
                            mac_operand_valid <= 1'b0;
                            mac_product_valid <= 1'b0;
                            if (layer == 3'd4)
                                state <= S_STORE_RAW;
                            else
                                state <= S_REQUANT_MUL;
                        end
                    end
                end

                S_REQUANT_MUL: begin
                    requant_product <= $signed(post_acc32) * $signed(cfg_multiplier);
                    state           <= S_REQUANT_OUT;
                end

                S_REQUANT_OUT: begin
                    if (cfg_pool && (pool_sub != 2'd3)) begin
                        if ((pool_sub == 2'd0) || (requant_value > pool_max))
                            pool_max <= requant_value;
                        pool_sub <= pool_sub + 2'd1;
                        state    <= S_PIXEL_START;
                    end else begin
                        debug_act_valid <= 1'b1;
                        debug_act_index <= activation_index(layer, out_channel, out_y, out_x);
                        debug_act_data  <= cfg_pool ? pooled_value : requant_value;
                        if (!cfg_dest_bank) begin
                            act0_we    <= 1'b1;
                            act0_waddr <= activation_index(layer, out_channel, out_y, out_x);
                            act0_wdata <= cfg_pool ? pooled_value : requant_value;
                        end else begin
                            act1_we    <= 1'b1;
                            act1_waddr <= activation_index(layer, out_channel, out_y, out_x);
                            act1_wdata <= cfg_pool ? pooled_value : requant_value;
                        end
                        pool_sub <= 2'd0;

                        if ((out_x + 8'd1) < cfg_output_size) begin
                            out_x <= out_x + 8'd1;
                            state <= S_PIXEL_START;
                        end else if ((out_y + 8'd1) < cfg_output_size) begin
                            out_x <= 8'd0;
                            out_y <= out_y + 8'd1;
                            state <= S_PIXEL_START;
                        end else if ((out_channel + 6'd1) < cfg_cout) begin
                            out_x       <= 8'd0;
                            out_y       <= 8'd0;
                            out_channel <= out_channel + 6'd1;
                            state       <= S_BIAS_REQ;
                        end else begin
                            if (layer == 3'd0)
                                input_release <= 1'b1;
                            layer       <= layer + 3'd1;
                            out_channel <= 6'd0;
                            out_y       <= 8'd0;
                            out_x       <= 8'd0;
                            state       <= S_BIAS_REQ;
                        end
                    end
                end

                S_STORE_RAW: begin
                    output_bram_we   <= 1'b1;
                    output_bram_addr <= {output_buffer_latched,
                                         current_accumulator_index[10:0]};
                    output_bram_data <= post_acc32;
                    if ((out_x + 8'd1) < cfg_output_size) begin
                        out_x <= out_x + 8'd1;
                        state <= S_PIXEL_START;
                    end else if ((out_y + 8'd1) < cfg_output_size) begin
                        out_x <= 8'd0;
                        out_y <= out_y + 8'd1;
                        state <= S_PIXEL_START;
                    end else if ((out_channel + 6'd1) < cfg_cout) begin
                        out_x       <= 8'd0;
                        out_y       <= 8'd0;
                        out_channel <= out_channel + 6'd1;
                        state       <= S_BIAS_REQ;
                    end else begin
                        state <= S_FLUSH;
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
