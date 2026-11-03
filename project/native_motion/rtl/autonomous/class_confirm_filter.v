// Consecutive-result hysteresis used by the autonomous production pipeline.
// Candidate 0 (background) requires 3 results, gestures 1..3 require 2, and
// candidate 4 (no detection) requires 3.  LEDs are one-hot for classes 0..3.
`timescale 1ns / 1ps

module class_confirm_filter (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       candidate_valid,
    input  wire [2:0] candidate_class,
    output reg  [2:0] output_class,
    output wire [3:0] leds
);

    localparam [2:0] CLASS_NONE = 3'd4;

    reg [2:0] pending_class;
    reg [1:0] pending_count;
    reg [1:0] required_count;

    assign leds =
        (output_class == 3'd0) ? 4'b0001 :
        (output_class == 3'd1) ? 4'b0010 :
        (output_class == 3'd2) ? 4'b0100 :
        (output_class == 3'd3) ? 4'b1000 : 4'b0000;

    always @(*) begin
        if ((candidate_class == 3'd0) || (candidate_class == CLASS_NONE))
            required_count = 2'd3;
        else
            required_count = 2'd2;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            output_class  <= CLASS_NONE;
            pending_class <= CLASS_NONE;
            pending_count <= 2'd0;
        end else if (candidate_valid) begin
            if (candidate_class == output_class) begin
                pending_class <= CLASS_NONE;
                pending_count <= 2'd0;
            end else if (candidate_class != pending_class) begin
                if (required_count == 2'd1) begin
                    output_class  <= candidate_class;
                    pending_class <= CLASS_NONE;
                    pending_count <= 2'd0;
                end else begin
                    pending_class <= candidate_class;
                    pending_count <= 2'd1;
                end
            end else if ((pending_count + 2'd1) >= required_count) begin
                output_class  <= candidate_class;
                pending_class <= CLASS_NONE;
                pending_count <= 2'd0;
            end else begin
                pending_count <= pending_count + 2'd1;
            end
        end
    end

endmodule
