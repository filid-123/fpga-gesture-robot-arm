// ============================================================================
// Streaming Conv5 Top-1 reducer.
//
// Observes the existing CHW output write stream and keeps one raw five-channel
// summary per output buffer.  The full 5x16x16 map remains available for
// diagnostics; the normal PS loop can read 24 bytes instead of 5 KiB.
// ============================================================================
`timescale 1ns / 1ps

module locator_top1_reducer (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    input  wire        output_buffer_id,
    input  wire        done,
    input  wire        output_we,
    input  wire [11:0] output_addr,
    input  wire [31:0] output_data,

    output reg  [31:0] top1_cell_0,
    output reg  [31:0] top1_conf_0,
    output reg  [31:0] top1_dx_0,
    output reg  [31:0] top1_dy_0,
    output reg  [31:0] top1_width_0,
    output reg  [31:0] top1_height_0,
    output reg  [31:0] top1_cell_1,
    output reg  [31:0] top1_conf_1,
    output reg  [31:0] top1_dx_1,
    output reg  [31:0] top1_dy_1,
    output reg  [31:0] top1_width_1,
    output reg  [31:0] top1_height_1
);

    reg        active_buffer;
    reg [7:0]  best_index;
    reg signed [31:0] best_confidence;
    reg [31:0] best_dx;
    reg [31:0] best_dy;
    reg [31:0] best_width;
    reg [31:0] best_height;

    wire [2:0] output_channel = output_addr[10:8];
    wire [7:0] output_cell = output_addr[7:0];

    always @(posedge clk) begin
        if (!rst_n) begin
            active_buffer   <= 1'b0;
            best_index      <= 8'd0;
            best_confidence <= -32'sh8000_0000;
            best_dx         <= 32'd0;
            best_dy         <= 32'd0;
            best_width      <= 32'd0;
            best_height     <= 32'd0;
            top1_cell_0     <= 32'd0;
            top1_conf_0     <= 32'd0;
            top1_dx_0       <= 32'd0;
            top1_dy_0       <= 32'd0;
            top1_width_0    <= 32'd0;
            top1_height_0   <= 32'd0;
            top1_cell_1     <= 32'd0;
            top1_conf_1     <= 32'd0;
            top1_dx_1       <= 32'd0;
            top1_dy_1       <= 32'd0;
            top1_width_1    <= 32'd0;
            top1_height_1   <= 32'd0;
        end else begin
            if (start) begin
                active_buffer   <= output_buffer_id;
                best_index      <= 8'd0;
                best_confidence <= -32'sh8000_0000;
                best_dx         <= 32'd0;
                best_dy         <= 32'd0;
                best_width      <= 32'd0;
                best_height     <= 32'd0;
            end

            if (output_we && output_channel == 3'd0 &&
                $signed(output_data) > best_confidence) begin
                best_index      <= output_cell;
                best_confidence <= $signed(output_data);
            end
            if (output_we && output_cell == best_index) begin
                case (output_channel)
                    3'd1: best_dx     <= output_data;
                    3'd2: best_dy     <= output_data;
                    3'd3: best_width  <= output_data;
                    3'd4: best_height <= output_data;
                    default: begin end
                endcase
            end

            if (done) begin
                if (!active_buffer) begin
                    top1_cell_0   <= {24'd0, best_index};
                    top1_conf_0   <= best_confidence;
                    top1_dx_0     <= best_dx;
                    top1_dy_0     <= best_dy;
                    top1_width_0  <= best_width;
                    top1_height_0 <= best_height;
                end else begin
                    top1_cell_1   <= {24'd0, best_index};
                    top1_conf_1   <= best_confidence;
                    top1_dx_1     <= best_dx;
                    top1_dy_1     <= best_dy;
                    top1_width_1  <= best_width;
                    top1_height_1 <= best_height;
                end
            end
        end
    end

endmodule
