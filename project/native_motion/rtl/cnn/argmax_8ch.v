// ============================================================================
// Block Name : argmax_8ch.v
// Description: 8-Channel Dynamic Hardware Argmax Comparator.
//              Tracks 8 sequential output pixel scores and outputs the
//              Class Index (0~7) with the Highest Score!
// Target FPAG : Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk
// ============================================================================

`timescale 1ns / 1ps

module argmax_8ch (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,          // Clear max scores on inference start
    input  wire        valid_in,       // High when a class score arrives
    input  wire [7:0]  score_in,       // UINT8 Pixel score from Requant
    input  wire        core_done,      // Core computation complete signal
    output reg  [2:0]  class_id_out    // Final Predicted Class ID (0~7)
);

    reg [2:0] cnt;
    reg [7:0] max_score;
    reg [2:0] max_index;
    reg       first_score;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cnt          <= 3'd0;
            max_score    <= 8'd0;
            max_index    <= 3'd0;
            class_id_out <= 3'd0;
            first_score  <= 1'b1;
        end else if (start) begin
            cnt          <= 3'd0;
            max_score    <= 8'd0;
            max_index    <= 3'd0;
            first_score  <= 1'b1;
        end else if (valid_in) begin
            cnt <= cnt + 1'b1;
            if (first_score || (score_in > max_score)) begin
                max_score   <= score_in;
                max_index   <= cnt;
                first_score <= 1'b0;
            end
        end else if (core_done) begin
            class_id_out <= max_index; // Latch the index of the highest score!
        end
    end

endmodule
