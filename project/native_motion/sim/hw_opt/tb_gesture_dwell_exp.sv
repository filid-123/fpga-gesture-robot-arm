`timescale 1ns/1ps
module tb_gesture_dwell_exp;
 reg clk=0;always #5 clk=~clk;
 reg rst=0,valid=0;reg[31:0]now_ms=0,ts=0,id=0;
 reg[2:0]candidate=7;reg[15:0]margin=1000;
 wire[2:0]stable,gated;wire qualified,changed;wire[3:0]leds;
 gesture_time_filter #(.OBJECT_HOLD_MS(200),.PALM_HOLD_MS(300),
 .FIST_HOLD_MS(80),.OBJECT_MIN_FRAMES(3),.PALM_MIN_FRAMES(3),
 .FIST_MIN_FRAMES(2),.MARGIN_MIN(100)) dut(
 .clk(clk),.rst_n(rst),.now_ms(now_ms),.frame_timestamp_ms(ts),.frame_id(id),
 .candidate_valid(valid),.candidate_class(candidate),.candidate_margin(margin),
 .output_class(stable),.output_changed(changed),.output_valid(qualified),
 .gated_class(gated),.leds(leds));
 task frame(input[31:0]t,input[2:0]c);
 begin @(negedge clk);now_ms=t+40;ts=t;id=id+1;candidate=c;valid=1;
 @(negedge clk);valid=0;#1;end endtask
 task expect_valid(input bit yes,input[2:0]c);
 begin if(qualified!==yes || (yes && stable!==c))
 $fatal(1,"FAIL: dwell ts=%0d candidate=%0d expected=%0d/%0d got=%0d/%0d",ts,candidate,yes,c,qualified,stable);end endtask
 task reset_filter;
 begin @(negedge clk);rst=0;valid=0;repeat(3)@(negedge clk);rst=1;end endtask
 initial begin
 reset_filter;
 frame(0,1);frame(50,2);frame(100,1);expect_valid(0,0);
 frame(200,1);expect_valid(0,0);frame(299,1);expect_valid(0,0);
 frame(300,1);expect_valid(1,1);
 frame(350,4);frame(450,4);frame(649,4);expect_valid(0,0);
 frame(650,4);expect_valid(1,4);
 // Cancellation still qualifies from two independent frames spanning 80ms.
 frame(700,5);expect_valid(0,0);frame(780,5);expect_valid(1,5);
 frame(1100,2);expect_valid(0,0);
 margin=1;frame(1150,2);expect_valid(0,0);if(gated!=6)$fatal(1,"FAIL: weak margin");margin=1000;
 frame(1200,0);frame(1450,0);expect_valid(1,0);
 now_ms=ts+251;#1;expect_valid(0,0);
 // Processing delay cannot turn an old frame into a current command.
 @(negedge clk);now_ms=2200;ts=1500;id=id+1;candidate=1;valid=1;
 @(negedge clk);valid=0;#1;expect_valid(0,0);
 reset_filter;
 frame(0,1);frame(200,1);expect_valid(0,0); // two frames are not three
 @(negedge clk);valid=1;candidate=4;@(negedge clk);valid=0;#1;
 expect_valid(0,0); // duplicate id must not count or replace the candidate
 frame(400,1);expect_valid(1,1);
 frame(401,2);expect_valid(0,0); // no held old command through a class change
 reset_filter;
 frame(32'hffffffa0,3);frame(32'hfffffff0,3);frame(32'h00000068,3);
 expect_valid(1,3); // acquisition-time differences remain correct across wrap
 $display("PASS: EXP_DWELL object200ms/3frames PALM300ms/3frames FIST80ms/2frames; jitter/transition/gap/stale/duplicate/margin/neutral/wrap");
 $finish;
 end
endmodule
