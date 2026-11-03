// ============================================================================
// Block Name : class_confirm_filter_7c
// Description: Consecutive-result confirmation of the Phase 3 S3 seven-class
//              pipeline.  Codes 0..6 are classes (0 BACKGROUND, 1..3 OBJECT_x,
//              4 PALM_READY, 5 FIST_CANCEL, 6 OTHER_INVALID); 7 is the
//              NO_DETECTION sentinel.  Same hysteresis as the four-class
//              class_confirm_filter.v, generalised:
//   * CONFIRM_COUNTS[4c+3:4c] = consecutive results needed to switch the
//     output to code c (1..15; 0 is treated as 1);
//   * optional margin gate: a candidate whose code is set in GATED_CODES and
//     whose top1-top2 logit margin is below MARGIN_MIN is replaced by
//     OTHER_INVALID before counting.  MARGIN_MIN = 0 disables the gate.  The
//     margin is an uncalibrated logit difference: its threshold has to be
//     chosen on real data (not a probability, no calibrated confidence);
//   * output_changed pulses for one cycle when output_class switches;
//   * leds = {1, output_class} for classes, 4'b0000 for NO_DETECTION
//     (4'b1111 is left to the top for fatal errors; code 7 is never shown
//     with bit3 set).
//              Task locking / one-shot command semantics belong to S4/S5.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz scheduler clock)
// Bit-exact reference: model/gesture7/confirm_model.py
// Truth boundary: source candidate; supplementary Icarus run only.
// ============================================================================
`timescale 1ns / 1ps

module class_confirm_filter_7c #(
    // {c7 NO_DETECTION, c6 OTHER_INVALID, c5 FIST_CANCEL, c4 PALM_READY,
    //  c3 OBJECT_3, c2 OBJECT_2, c1 OBJECT_1, c0 BACKGROUND}
    parameter [31:0] CONFIRM_COUNTS = {4'd3, 4'd2, 4'd2, 4'd2, 4'd2, 4'd2, 4'd2, 4'd3},
    parameter [7:0]  GATED_CODES    = 8'b0011_1110,      // OBJECT_1..3, PALM_READY, FIST_CANCEL
    parameter [15:0] MARGIN_MIN     = 16'd0
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        candidate_valid,
    input  wire [2:0]  candidate_class,
    input  wire [15:0] candidate_margin,
    output reg  [2:0]  output_class,
    output reg         output_changed,
    output wire [2:0]  gated_class,
    output wire [3:0]  leds
);

    localparam [2:0] NO_DETECTION  = 3'd7;
    localparam [2:0] OTHER_INVALID = 3'd6;

    reg        pending_valid;
    reg [2:0]  pending_class;
    reg [3:0]  pending_count;

    wire gate_hit = GATED_CODES[candidate_class] && (candidate_margin < MARGIN_MIN);
    assign gated_class = gate_hit ? OTHER_INVALID : candidate_class;

    wire [3:0] required_raw = CONFIRM_COUNTS[{gated_class, 2'b00} +: 4];
    wire [3:0] required     = (required_raw == 4'd0) ? 4'd1 : required_raw;
    wire [4:0] next_count   = {1'b0, pending_count} + 5'd1;

    assign leds = (output_class == NO_DETECTION) ? 4'b0000 : {1'b1, output_class};

    always @(posedge clk) begin
        if (!rst_n) begin
            output_class   <= NO_DETECTION;
            output_changed <= 1'b0;
            pending_valid  <= 1'b0;
            pending_class  <= NO_DETECTION;
            pending_count  <= 4'd0;
        end else begin
            output_changed <= 1'b0;
            if (candidate_valid) begin
                if (gated_class == output_class) begin
                    pending_valid <= 1'b0;
                    pending_count <= 4'd0;
                end else if (!pending_valid || (gated_class != pending_class)) begin
                    if (required == 4'd1) begin
                        output_class   <= gated_class;
                        output_changed <= 1'b1;
                        pending_valid  <= 1'b0;
                        pending_count  <= 4'd0;
                    end else begin
                        pending_valid <= 1'b1;
                        pending_class <= gated_class;
                        pending_count <= 4'd1;
                    end
                end else if (next_count >= {1'b0, required}) begin
                    output_class   <= gated_class;
                    output_changed <= 1'b1;
                    pending_valid  <= 1'b0;
                    pending_count  <= 4'd0;
                end else begin
                    pending_count <= next_count[3:0];
                end
            end
        end
    end

endmodule
