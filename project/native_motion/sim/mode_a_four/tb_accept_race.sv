`timescale 1ns/1ps
module tb_accept_race;
reg clk=0;always #5 clk=~clk;reg rst=0,active=0,rv=0,valid=1,accept=0,settled=0,palm=0;reg[31:0]now=0,id=0,ts=0;reg[3:0]cell_in=0;wire tv,locked;wire[3:0]tc,lc;
hand_align_target_core #(.EXPLICIT_ACCEPT(1))dut(.clk(clk),.rst_n(rst),.task_active(active),.waiting_region(1'b1),.cancel(1'b0),.fault(1'b0),.now_ms(now),.max_age_ms(32'd250),.max_gap_ms(32'd250),.hold_ms(16'd120),.min_frames(8'd3),.response_valid(rv),.mapped_valid(valid),.mapped_cell(cell_in),.mapped_bundle(42'd0),.mapped_frame_id(id),.mapped_timestamp_ms(ts),.mapped_revision(32'd1),.mapped_class(3'd4),.accept_target(accept),.accepted_cell_in(4'd0),.accepted_revision_in(32'd1),.position_settled(settled),.palm_confirmed(palm),.target_valid(tv),.target_cell(tc),.locked(locked),.locked_cell(lc));
task frame(input[3:0]c,input[31:0]time_ms);begin @(negedge clk);cell_in=c;now=time_ms;ts=time_ms;id=id+1;rv=1;@(negedge clk);rv=0;end endtask
initial begin
 repeat(4)@(negedge clk);rst=1;active=1;
 frame(0,1000);frame(0,1060);frame(0,1120);if(!tv || tc!=0)$fatal(1,"Candidate not qualified");
 // S4 latched cell0, then a new frame overwrites the replaceable mailbox before its registered acknowledgement.
 frame(3,1180);accept=1;@(negedge clk);accept=0;
 if(!dut.accepted || dut.accepted_cell!=0 || locked)$fatal(1,"Explicit acceptance followed overwritten mailbox");
 frame(0,1240);frame(0,1300);frame(0,1360);settled=1;palm=1;repeat(3)@(negedge clk);
 if(!locked || lc!=0)$fatal(1,"Latched accepted cell could not lock");
 $display("PASS: registered acceptance preserves selected cell despite simultaneous mailbox replacement and later locks only its matching fresh PALM");$finish;
end
endmodule
