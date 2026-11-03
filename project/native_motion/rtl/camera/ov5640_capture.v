// ============================================================================
// OV5640 DVP YUV422 luminance capture in the sensor PCLK domain.
// Y_BYTE_PHASE=0 selects bytes 0/2/... (YUYV), =1 selects 1/3/... (UYVY).
// Each emitted token carries its source coordinate and a start-of-frame bit;
// all of these signals are consumed only by the asynchronous FIFO.
// ============================================================================
`timescale 1ns / 1ps

module ov5640_capture #(
    parameter integer Y_BYTE_PHASE      = 0,
    parameter integer VSYNC_ACTIVE_HIGH = 1
)(
    input  wire       pclk,
    input  wire       rst_n,
    input  wire       enable,
    input  wire [7:0] dvp_data,
    input  wire       dvp_href,
    input  wire       dvp_vsync,

    output reg        pixel_valid,
    output reg  [7:0] pixel_y,
    output reg  [9:0] pixel_x,
    output reg  [9:0] pixel_y_coord,
    output reg        pixel_sof
);

    // Keep the first sampling stage in the input IOBs. This makes the DVP
    // pin-to-register path short and leaves only the external sensor timing
    // window to be refined after the first scope/ILA capture.
    (* IOB = "TRUE" *) reg [7:0] dvp_data_iob;
    (* IOB = "TRUE" *) reg       dvp_href_iob;
    (* IOB = "TRUE" *) reg       dvp_vsync_iob;

    wire vsync_active = VSYNC_ACTIVE_HIGH ? dvp_vsync_iob : ~dvp_vsync_iob;

    reg href_d;
    reg byte_phase;
    reg frame_pending;
    reg [9:0] x_count;
    reg [9:0] y_count;
    wire current_byte_phase = href_d ? byte_phase : 1'b0;

    always @(posedge pclk) begin
        if (!rst_n) begin
            dvp_data_iob  <= 8'd0;
            dvp_href_iob  <= 1'b0;
            dvp_vsync_iob <= 1'b0;
        end else begin
            dvp_data_iob  <= dvp_data;
            dvp_href_iob  <= dvp_href;
            dvp_vsync_iob <= dvp_vsync;
        end
    end

    always @(posedge pclk) begin
        if (!rst_n) begin
            href_d        <= 1'b0;
            byte_phase    <= 1'b0;
            frame_pending <= 1'b1;
            x_count       <= 10'd0;
            y_count       <= 10'd0;
            pixel_valid   <= 1'b0;
            pixel_y       <= 8'd0;
            pixel_x       <= 10'd0;
            pixel_y_coord <= 10'd0;
            pixel_sof     <= 1'b0;
        end else begin
            href_d      <= dvp_href_iob;
            pixel_valid <= 1'b0;
            pixel_sof   <= 1'b0;

            if (!enable) begin
                byte_phase    <= 1'b0;
                frame_pending <= 1'b1;
                x_count       <= 10'd0;
                y_count       <= 10'd0;
            end else if (vsync_active) begin
                byte_phase    <= 1'b0;
                frame_pending <= 1'b1;
                x_count       <= 10'd0;
                y_count       <= 10'd0;
            end else begin
                if (!dvp_href_iob) begin
                    byte_phase <= 1'b0;
                    x_count    <= 10'd0;
                    if (href_d)
                        y_count <= y_count + 10'd1;
                end else begin
                    if (!href_d) begin
                        x_count    <= 10'd0;
                    end
                    byte_phase <= ~current_byte_phase;

                    if (current_byte_phase == Y_BYTE_PHASE[0]) begin
                        pixel_valid   <= 1'b1;
                        pixel_y       <= dvp_data_iob;
                        pixel_x       <= x_count;
                        pixel_y_coord <= y_count;
                        pixel_sof     <= frame_pending;
                        frame_pending <= 1'b0;
                        x_count       <= x_count + 10'd1;
                    end
                end
            end
        end
    end

endmodule
