`timescale 1ns / 1ps

module cnn_core_fsm (
    input  wire        clk,
    input  wire        rst_n,

    // Top Control
    input  wire        start,
    output reg         busy,
    output reg         done,

    // Descriptor BRAM (Read-only, 32-bit)
    output reg         desc_bram_en,
    output reg  [7:0]  desc_bram_addr,
    input  wire [31:0] desc_bram_data,

    // Layer Parameters Broadcast to Engines
    output reg  [15:0] layer_Cin,
    output reg  [8:0]  layer_Cout,
    output reg  [5:0]  layer_InH,
    output reg  [5:0]  layer_InW,
    output reg  [31:0] layer_weight_offset,
    output reg  [31:0] layer_bias_offset,
    output reg  [31:0] layer_quant_M,
    output reg  [7:0]  layer_quant_shift,
    output reg  [1:0]  layer_act_src,
    output reg  [1:0]  layer_act_dst,
    output reg         layer_is_final,
    output reg  [1:0]  layer_type, // 0: Conv, 1: Pool, 2: Dense

    // Engine Start Triggers
    output reg         start_conv,
    output reg         start_pool,
    output reg         start_dense,

    // Engine Done Status
    input  wire        done_conv,
    input  wire        done_pool,
    input  wire        done_dense,

    // Active Engine Mux Control
    output reg  [1:0]  active_engine // 0: Conv, 1: Pool, 2: Dense, 3: None
);

    localparam S_IDLE        = 0;
    localparam S_LOAD_DESC_0 = 1;
    localparam S_LOAD_DESC_1 = 2;
    localparam S_LOAD_DESC_2 = 3;
    localparam S_LOAD_DESC_3 = 4;
    localparam S_LOAD_DESC_4 = 5;
    localparam S_LOAD_DESC_5 = 6;
    localparam S_START       = 7;
    localparam S_WAIT_DESC5  = 8;
    localparam S_WAIT        = 9;
    localparam S_NEXT_LAYER  = 10;
    localparam S_DONE        = 11;

    reg [3:0] state;
    reg [4:0] layer_idx;

    always @(posedge clk) begin
        if (!rst_n) begin
            state <= S_IDLE;
            busy <= 0;
            done <= 0;
            desc_bram_en <= 0;
            start_conv <= 0;
            start_pool <= 0;
            start_dense <= 0;
            active_engine <= 3;
        end else begin
            desc_bram_en <= 0;
            start_conv <= 0;
            start_pool <= 0;
            start_dense <= 0;

            case (state)
                S_IDLE: begin
                    done <= 0;
                    if (start) begin
                        busy <= 1;
                        layer_idx <= 0;
                        state <= S_LOAD_DESC_0;
                    end
                end

                S_LOAD_DESC_0: begin
                    desc_bram_en <= 1;
                    desc_bram_addr <= {layer_idx, 3'd0}; // Request Word 0
                    state <= S_LOAD_DESC_1;
                end

                S_LOAD_DESC_1: begin
                    desc_bram_en <= 1;
                    desc_bram_addr <= {layer_idx, 3'd1}; // Request Word 1
                    // Word 0 is being fetched during this cycle
                    state <= S_LOAD_DESC_2;
                end

                S_LOAD_DESC_2: begin
                    desc_bram_en <= 1;
                    desc_bram_addr <= {layer_idx, 3'd2}; // Request Word 2
                    
                    // Word 0 arrived: InH[31:24], Cout[23:16], Cin[15:2] (14-bit), Type[1:0]
                    layer_InH  <= desc_bram_data[31:24];
                    layer_Cout <= desc_bram_data[23:16];
                    layer_Cin  <= desc_bram_data[15:2];
                    layer_type <= desc_bram_data[1:0];

                    state <= S_LOAD_DESC_3;
                end

                S_LOAD_DESC_3: begin
                    desc_bram_en <= 1;
                    desc_bram_addr <= {layer_idx, 3'd3}; // Request Word 3

                    // Word 1 arrived: HasPool[31:24], Pad[23:16], Stride[15:8], InW[7:0]
                    layer_InW  <= desc_bram_data[7:0];

                    state <= S_LOAD_DESC_4;
                end

                S_LOAD_DESC_4: begin
                    desc_bram_en <= 1;
                    desc_bram_addr <= {layer_idx, 3'd4}; // Request Word 4

                    // Word 2 arrived: Weight Offset
                    layer_weight_offset <= desc_bram_data;

                    state <= S_LOAD_DESC_5;
                end

                S_LOAD_DESC_5: begin
                    desc_bram_en <= 1;
                    desc_bram_addr <= {layer_idx, 3'd5}; // Request Word 5

                    // Word 3 arrived: Bias Offset
                    layer_bias_offset <= desc_bram_data;

                    state <= S_START;
                end

                S_START: begin
                    desc_bram_en <= 0; // Stop reading

                    // Word 4 arrived: Quant M
                    layer_quant_M <= desc_bram_data;

                    state <= S_WAIT_DESC5;
                end


                S_WAIT_DESC5: begin
                    // Word 5 arrived: IsFinal[31], Reserved[30:24], ActDst[23:16], ActSrc[15:8], QuantShift[7:0]
                    layer_quant_shift <= desc_bram_data[7:0];
                    layer_act_src <= desc_bram_data[15:8];
                    layer_act_dst <= desc_bram_data[23:16];
                    layer_is_final <= desc_bram_data[31];

                    $display("[%0t] [CORE_FSM] S_WAIT_DESC5: layer_type=%d, layer_Cin=%d, layer_Cout=%d, InH=%d, InW=%d, Word5=%h", $time, layer_type, layer_Cin, layer_Cout, layer_InH, layer_InW, desc_bram_data);

                    active_engine <= layer_type;
                    if (layer_type == 0) begin
                        start_conv <= 1;
                        $display("[%0t] [CORE_FSM] Starting CONV Engine (layer_type=0)", $time);
                    end else if (layer_type == 1) begin
                        start_pool <= 1;
                        $display("[%0t] [CORE_FSM] Starting POOL Engine (layer_type=1)", $time);
                    end else if (layer_type == 2) begin
                        start_dense <= 1;
                        $display("[%0t] [CORE_FSM] Starting DENSE Engine (layer_type=2)", $time);
                    end

                    state <= S_WAIT;
                end

                S_WAIT: begin
                    start_conv <= 0;
                    start_pool <= 0;
                    start_dense <= 0;

                    if (done_conv || done_pool || done_dense) begin
                        $display("[%0t] [CORE_FSM] Received Engine DONE. Moving to next layer or finishing. (is_final=%d)", $time, layer_is_final);
                        if (layer_is_final) begin
                            state <= S_DONE;
                        end else begin
                            layer_idx <= layer_idx + 1;
                            state <= S_LOAD_DESC_0;
                        end
                    end
                end

                S_NEXT_LAYER: begin
                    active_engine <= 3;
                    if (layer_is_final) begin
                        state <= S_DONE;
                    end else begin
                        layer_idx <= layer_idx + 1;
                        state <= S_LOAD_DESC_0;
                    end
                end

                S_DONE: begin
                    busy <= 0;
                    done <= 1;
                    state <= S_IDLE; // Transition unconditionally to IDLE next cycle
                end
                
                default: state <= S_IDLE;
            endcase
        end
    end
endmodule
