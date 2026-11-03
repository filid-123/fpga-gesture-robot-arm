`timescale 1ns / 1ps

module tb_video_timing_640x480;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    wire [9:0] x, y;
    wire active_video, hsync, vsync, frame_start;
    integer cycles;
    integer active_count;
    integer hsync_low_count;
    integer vsync_low_count;

    always #5 clk = ~clk;

    video_timing_640x480 dut (
        .pixel_clk(clk), .rst_n(rst_n), .x(x), .y(y),
        .active_video(active_video), .hsync(hsync), .vsync(vsync),
        .frame_start(frame_start)
    );

    initial begin
        repeat (4) @(posedge clk);
        rst_n = 1'b1;
        @(negedge clk);
        while (!frame_start)
            @(negedge clk);
        cycles = 0;
        active_count = 0;
        hsync_low_count = 0;
        vsync_low_count = 0;
        while (cycles < 420000) begin
            if (active_video) active_count = active_count + 1;
            if (!hsync) hsync_low_count = hsync_low_count + 1;
            if (!vsync) vsync_low_count = vsync_low_count + 1;
            cycles = cycles + 1;
            @(negedge clk);
        end
        if (!frame_start || (x != 0) || (y != 0))
            $fatal(1, "frame did not wrap at 800x525");
        if (active_count != 307200)
            $fatal(1, "active pixel count mismatch: %0d", active_count);
        if (hsync_low_count != (96 * 525))
            $fatal(1, "hsync width mismatch: %0d", hsync_low_count);
        if (vsync_low_count != (2 * 800))
            $fatal(1, "vsync width mismatch: %0d", vsync_low_count);
        $display("PASS: 640x480 timing is bit-exact for one 800x525 frame");
        $finish;
    end

    initial begin
        #10000000;
        $fatal(1, "video timing test timeout");
    end
endmodule
