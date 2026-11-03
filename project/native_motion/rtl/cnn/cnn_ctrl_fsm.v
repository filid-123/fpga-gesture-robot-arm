// ============================================================================
// Block Name : cnn_ctrl_fsm.v (Clean Full Case Edition)
// Description: CNN Layer Scheduler with:
//              1. Hardware Interrupt Output (irq_out)
//              2. Bubble-Free Descriptor Prefetching Pipeline
//              3. Reset Synchronizer Tree
// Target FPAG : Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk_100mhz
// ============================================================================

`timescale 1ns / 1ps

module cnn_ctrl_fsm (
    input  wire        clk,
    input  wire        rst_n,
    
    // Command & Status
    input  wire        start,           // Pulse to start CNN inference
    output reg         done,            // High when all layers complete
    output reg         busy,            // High during computation
    output wire        irq_out,         // Hardware Interrupt Output to PS GIC
    output reg         timeout_err,     // High if Watchdog limit exceeded
    output reg  [2:0]  current_layer,   // Layer ID (0 ~ 7)
    
    // Layer Descriptor Interface
    output reg  [5:0]  desc_addr,       // Descriptor BRAM address
    input  wire [31:0] desc_word_in,    // 32-bit word from descriptor BRAM
    
    // Accelerator Control Signals
    output reg         mac_clr,         // Clear MAC accumulators
    output reg         mac_en,          // Enable MAC calculation
    output reg         requant_valid    // Trigger requantization
);

    // Reset Synchronizer Tree
    reg rst_n_sync1, rst_n_local;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rst_n_sync1 <= 1'b0;
            rst_n_local <= 1'b0;
        end else begin
            rst_n_sync1 <= 1'b1;
            rst_n_local <= rst_n_sync1;
        end
    end

    // FSM States with Prefetch Pipeline
    localparam STATE_IDLE          = 4'd0;
    localparam STATE_FETCH_DESC    = 4'd1;
    localparam STATE_PARSE_DESC    = 4'd2;
    localparam STATE_COMPUTE       = 4'd3;
    localparam STATE_REQUANT       = 4'd4;
    localparam STATE_PREFETCH_DESC = 4'd5;
    localparam STATE_NEXT_LAYER    = 4'd6;
    localparam STATE_DONE          = 4'd7;

    reg [3:0] state, next_state;
    reg [19:0] watchdog_cnt;
    reg [2:0]  layer_cnt;
    reg [10:0] pixel_cnt;

    // Interrupt Output
    assign irq_out = done;

    // State Register
    always @(posedge clk or negedge rst_n_local) begin
        if (!rst_n_local) begin
            state <= STATE_IDLE;
        end else begin
            state <= next_state;
        end
    end

    // Next State Logic (Full Case Coverage)
    always @(*) begin
        next_state = state;
        case (state)
            STATE_IDLE: begin
                if (start) next_state = STATE_FETCH_DESC;
            end
            STATE_FETCH_DESC: begin
                next_state = STATE_PARSE_DESC;
            end
            STATE_PARSE_DESC: begin
                next_state = STATE_COMPUTE;
            end
            STATE_COMPUTE: begin
                if (pixel_cnt == 11'd1031)
                    next_state = STATE_PREFETCH_DESC;
                else
                    next_state = STATE_COMPUTE;
            end
            STATE_PREFETCH_DESC: begin
                next_state = STATE_REQUANT;
            end
            STATE_REQUANT: begin
                next_state = STATE_NEXT_LAYER;
            end
            STATE_NEXT_LAYER: begin
                if (layer_cnt == 3'd7)
                    next_state = STATE_DONE;
                else
                    next_state = STATE_PARSE_DESC;
            end
            STATE_DONE: begin
                if (start)
                    next_state = STATE_FETCH_DESC;
                else
                    next_state = STATE_DONE;
            end
            default: next_state = STATE_IDLE;
        endcase
    end

    // Output Registers (Full Case Coverage)
    always @(posedge clk or negedge rst_n_local) begin
        if (!rst_n_local) begin
            busy          <= 1'b0;
            done          <= 1'b0;
            timeout_err   <= 1'b0;
            current_layer <= 3'd0;
            layer_cnt     <= 3'd0;
            pixel_cnt     <= 11'd0;
            watchdog_cnt  <= 20'd0;
            mac_clr       <= 1'b0;
            mac_en        <= 1'b0;
            requant_valid <= 1'b0;
            desc_addr     <= 6'd0;
        end else begin
            case (state)
                STATE_IDLE: begin
                    busy        <= 1'b0;
                    done        <= 1'b0;
                    timeout_err <= 1'b0;
                    layer_cnt   <= 3'd0;
                    pixel_cnt   <= 11'd0;
                    if (start) busy <= 1'b1;
                end
                STATE_FETCH_DESC: begin
                    desc_addr     <= layer_cnt * 8;
                    current_layer <= layer_cnt;
                    mac_clr       <= 1'b1;
                    pixel_cnt     <= 11'd0;
                end
                STATE_PARSE_DESC: begin
                    mac_clr <= 1'b0;
                    mac_en  <= 1'b1;
                    pixel_cnt <= 11'd0;
                end
                STATE_COMPUTE: begin
                    if (pixel_cnt < 11'd1023) begin
                        mac_en <= 1'b1;
                    end else begin
                        mac_en <= 1'b0; // Stop reading BRAM after 1024 pixels
                    end

                    if (pixel_cnt < 11'd1031) begin
                        pixel_cnt <= pixel_cnt + 1'b1;
                        requant_valid <= 1'b0;
                    end else begin
                        requant_valid <= 1'b1; // Trigger requant after adder tree pipeline flush
                    end
                end
                STATE_PREFETCH_DESC: begin
                    mac_en        <= 1'b0;
                    requant_valid <= 1'b0;
                    if (layer_cnt < 3'd7) begin
                        desc_addr <= (layer_cnt + 3'd1) * 8;
                    end
                end
                STATE_REQUANT: begin
                    mac_en        <= 1'b0;
                    requant_valid <= 1'b0;
                end
                STATE_NEXT_LAYER: begin
                    layer_cnt <= layer_cnt + 1;
                    if (layer_cnt < 3'd7) begin
                        current_layer <= layer_cnt + 1;
                        mac_clr       <= 1'b1;
                    end
                end
                STATE_DONE: begin
                    busy <= 1'b0;
                    done <= 1'b1;
                end
                default: begin
                    busy          <= 1'b0;
                    done          <= 1'b0;
                    mac_clr       <= 1'b0;
                    mac_en        <= 1'b0;
                    requant_valid <= 1'b0;
                end
            endcase

            // Watchdog Timeout (Max 500,000 cycles)
            if (busy) begin
                watchdog_cnt <= watchdog_cnt + 1;
                if (watchdog_cnt > 20'd500000) begin
                    timeout_err <= 1'b1;
                end
            end else begin
                watchdog_cnt <= 20'd0;
            end
        end
    end

endmodule
