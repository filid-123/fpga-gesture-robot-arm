// 640x480 progressive timing at a 25.2 MHz pixel clock.
// Totals are 800x525, giving exactly 60.0 Hz at 25.2 MHz.
`timescale 1ns / 1ps

module video_timing_640x480 (
    input  wire       pixel_clk,
    input  wire       rst_n,
    output reg  [9:0] x,
    output reg  [9:0] y,
    output wire       active_video,
    output wire       hsync,
    output wire       vsync,
    output wire       frame_start
);
    localparam integer H_ACTIVE = 640;
    localparam integer H_FRONT  = 16;
    localparam integer H_SYNC   = 96;
    localparam integer H_TOTAL  = 800;
    localparam integer V_ACTIVE = 480;
    localparam integer V_FRONT  = 10;
    localparam integer V_SYNC   = 2;
    localparam integer V_TOTAL  = 525;

    assign active_video = (x < H_ACTIVE) && (y < V_ACTIVE);
    assign hsync = ~((x >= (H_ACTIVE + H_FRONT)) &&
                     (x <  (H_ACTIVE + H_FRONT + H_SYNC)));
    assign vsync = ~((y >= (V_ACTIVE + V_FRONT)) &&
                     (y <  (V_ACTIVE + V_FRONT + V_SYNC)));
    assign frame_start = (x == 10'd0) && (y == 10'd0);

    always @(posedge pixel_clk) begin
        if (!rst_n) begin
            x <= 10'd0;
            y <= 10'd0;
        end else if (x == (H_TOTAL - 1)) begin
            x <= 10'd0;
            if (y == (V_TOTAL - 1))
                y <= 10'd0;
            else
                y <= y + 10'd1;
        end else begin
            x <= x + 10'd1;
        end
    end
endmodule
