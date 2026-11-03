`timescale 1ns/1ps
module tb_gesture_time_filter;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,valid=0;reg [31:0] now=0,ts=0,id=0;
    reg [2:0] candidate=7;reg [15:0] margin=1000;
    wire [2:0] stable,gated;wire changed,qualified;wire [3:0] leds;
    gesture_time_filter #(.MARGIN_MIN(100)) dut(.clk(clk),.rst_n(rst_n),.now_ms(now),
        .frame_timestamp_ms(ts),.frame_id(id),.candidate_valid(valid),.candidate_class(candidate),
        .candidate_margin(margin),.output_class(stable),.output_changed(changed),
        .output_valid(qualified),.gated_class(gated),.leds(leds));
    task frame(input [31:0] t,input [2:0] c,input [15:0] m);
        begin @(negedge clk);now=t+100;ts=t;id=id+1;candidate=c;margin=m;valid=1;
            @(negedge clk);valid=0;#1;end
    endtask
    initial begin
        repeat(3) @(negedge clk);rst_n=1;
        // A single strong glitch and alternating classes never select an object.
        frame(0,1,1000);frame(50,2,1000);frame(100,1,1000);
        if(qualified) $fatal(1,"FAIL: alternating glitch accepted");
        frame(150,1,1000);if(qualified)$fatal(1,"FAIL: early frame-count confirmation");
        frame(200,1,1000);if(!qualified||stable!=1)$fatal(1,"FAIL: object dwell not accepted");
        // Duplicate frame/timestamp does not count as another observation.
        @(negedge clk);candidate=5;valid=1;@(negedge clk);valid=0;#1;
        if(stable!=1)$fatal(1,"FAIL: duplicate frame changed class");
        frame(250,4,1000);frame(350,4,1000);if(qualified)$fatal(1,"FAIL: PALM early");
        frame(450,4,1000);if(!qualified||stable!=4)$fatal(1,"FAIL: PALM dwell");
        frame(500,5,1000);frame(580,5,1000);if(!qualified||stable!=5)$fatal(1,"FAIL: FIST dwell");
        // Gap reset, raw-margin gate, stale acquisition and neutral rearm dwell.
        frame(1000,2,1000);if(qualified)$fatal(1,"FAIL: long gap retained qualification");
        frame(1050,2,1);if(qualified||gated!=6)$fatal(1,"FAIL: margin gate");
        frame(1100,0,1000);frame(1250,0,1000);if(qualified)$fatal(1,"FAIL: neutral early");
        frame(1350,0,1000);if(!qualified||stable!=0)$fatal(1,"FAIL: neutral dwell");
        now=ts+251;#1;if(qualified)$fatal(1,"FAIL: stale class remained valid");
        @(negedge clk);now=2000;ts=1500;id=id+1;candidate=1;valid=1;
        @(negedge clk);valid=0;#1;if(qualified)$fatal(1,"FAIL: old acquisition accepted");
        $display("PASS: TIME_FILTER glitch/dwell/duplicate/PALM/FIST/gap/margin/stale/rearm");$finish;
    end
endmodule
