`timescale 1ns/1ps
module tb_locator_position;
reg clk=0;always #5 clk=~clk;
reg rst=0,active=0,rv=0,valid=1,accept=0,settled=0,palm=0;
reg[31:0]now=0,id=0,ts=0;reg[3:0]cell_in=1,accepted_cell=1;reg[2:0]cls=7;
wire tv,locked;wire[3:0]tc,lc;
hand_align_target_core #(.POSITION_ONLY(1),.EXPLICIT_ACCEPT(1))dut(
 .clk(clk),.rst_n(rst),.task_active(active),.waiting_region(1'b1),.cancel(1'b0),.fault(1'b0),
 .now_ms(now),.max_age_ms(32'd250),.max_gap_ms(32'd250),.hold_ms(16'd80),.min_frames(8'd2),
 .response_valid(rv),.mapped_valid(valid),.mapped_cell(cell_in),.mapped_bundle(42'd0),.mapped_frame_id(id),.mapped_timestamp_ms(ts),.mapped_revision(32'd2),.mapped_class(cls),
 .accept_target(accept),.accepted_cell_in(accepted_cell),.accepted_revision_in(32'd2),.position_settled(settled),.palm_confirmed(palm),.target_valid(tv),.target_cell(tc),.locked(locked),.locked_cell(lc));
task frame(input[3:0]c,input[2:0]g,input[31:0]time_ms);begin @(negedge clk);cell_in=c;cls=g;now=time_ms;ts=time_ms;id=id+1;rv=1;@(negedge clk);rv=0;end endtask
initial begin
 repeat(4)@(negedge clk);rst=1;active=1;
 frame(1,7,1000);if(tv)$fatal(1,"One frame qualified position");
 frame(1,6,1085);if(!tv || tc!=1)$fatal(1,"Unqualified class suppressed valid Locator");
 accept=1;settled=1;palm=1;repeat(3)@(negedge clk);accept=0;
 if(locked)$fatal(1,"Non PALM Locator locked delivery");
 now=1400;repeat(2)@(negedge clk);if(tv)$fatal(1,"Stale Locator remained valid");
 frame(2,7,1500);valid=0;frame(2,7,1585);if(tv)$fatal(1,"Invalid detection qualified");
 valid=1;frame(2,7,1670);if(tv)$fatal(1,"Invalid frame did not reset dwell");
 frame(2,7,1755);if(!tv || tc!=2)$fatal(1,"Position did not recover");
 accepted_cell=2;accept=1;@(negedge clk);accept=0;
 frame(2,4,1840);repeat(3)@(negedge clk);if(!locked || lc!=2)$fatal(1,"Confirmed matching PALM did not lock");
 $display("PASS: fresh valid Locator ignores class qualification, invalid/stale resets, no false PALM, matching qualified PALM locks");$finish;
end
endmodule
