
`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;reg rst=0;
reg[1:0]mode=0;reg b_ctx=0,grip=0;reg[15:0]speed=0;reg[7:0]acc=0;
reg twe=0;reg[7:0]ta=0;reg[15:0]td=0;reg valid=0;wire ready,busy,done;
reg[191:0]q;wire[3:0]state;wire[14:0]err;
reg[15:0]programs[0:255];reg[31:0]gold[0:1023];integer at=0,length=0,got=0,caseid=0;
arm_backend_core #(.FAST_B(1),.HAS_SO101(0),.DEBOUNCE_CYCLES(4))dut(
.clk(clk),.rst_n(rst),.mode_req(mode),.backend_sel(1'b0),.arm(1'b1),.config_valid(1'b1),.fault(1'b0),.commit_start(1'b0),
.b_context(b_ctx),.b_grip(grip),.b_speed(speed),.b_acc(acc),
.baud_div_roarm(16'd4),.baud_div_bus(16'd4),.hd_lead_cycles(16'd0),.hd_lag_cycles(16'd0),.resp_timeout_cycles(24'd0),
.wd_prescale(20'd1000),.prime_period_cycles(24'd1000),.fb_timeout_ticks(16'd500),.arrival_count(4'd3),.required_mask(6'd0),
.cmd_base(8'd0),.req_base(8'd91),.req_enable(1'b0),.reads_per_cycle(3'd0),.dir_neg(6'd0),.device_ids(48'd0),.tol_dev(96'd0),
.json_frac_digits(3'd4),.json_line_term(8'd10),.json_max_line_len(16'd512),.json_key_len(28'd0),.json_disc_value(32'd1051),
.sts_hdr0(8'd0),.sts_hdr1(8'd0),.sts_read_len(3'd0),.sts_encoding(2'd0),.sts_big_endian(1'b0),.sts_ck_invert(1'b0),.seq_byte(8'd0),
.map_soft_min(-32'sd262144),.map_soft_max(32'sd262144),.map_zero(32'd0),.map_scale(32'd655360000),
.tpl_we(twe),.tpl_waddr(ta),.tpl_wdata(td),.key_we(1'b0),.key_waddr(7'd0),.key_wdata(8'd0),
.s_valid(valid),.s_ready(ready),.s_data(q),.arm_uart_rx(1'b1),.bus_rx(1'b1),.motion_enable_in(1'b1),
.engine_busy(busy),.core_state(state),.evt_frame_done(done),.err_pulse(err),.snap_hold(1'b0),.snap_ch(3'd0));
always @(posedge clk)begin
 if(rst&&|err)$fatal(1,"Backend error %h",err);
 if(dut.fmt_valid&&dut.fmt_ready)begin
  if(got>=length||dut.fmt_byte!==gold[at+got][7:0])$fatal(1,"case=%d byte=%d actual=%h expected=%h",caseid,got,dut.fmt_byte,gold[at+got]);
  got=got+1;
 end
end
task frame(input bit b,input bit g,input[15:0]s,input[7:0]a,input bit mutate);
begin
 @(negedge clk);b_ctx=b;grip=g;speed=s;acc=a;length=gold[at];at=at+1;got=0;caseid=caseid+1;valid=1;
 wait(state==2);if(mutate)begin @(negedge clk);b_ctx=0;grip=!g;speed=17;acc=1;end
 wait(ready);@(negedge clk);valid=0;
 wait(done);@(negedge clk);if(got!=length)$fatal(1,"Short frame case=%d got=%d expected=%d",caseid,got,length);at=at+length;
 wait(!busy);repeat(4)@(negedge clk);
end endtask
initial begin
 $readmemh("program.mem",programs);$readmemh("gold.mem",gold);
 q=192'h00019604ffff4000000020000002000000004000ffff8000;
 repeat(4)@(negedge clk);rst=1;
 for(integer i=0;i<256;i=i+1)begin @(negedge clk);ta=i;td=programs[i];twe=1;end
 @(negedge clk);twe=0;mode=1;repeat(6)@(negedge clk);
 frame(0,0,0,0,0);frame(1,0,2640,254,1);frame(1,0,3960,254,0);frame(1,1,60,5,1);frame(0,0,0,0,0);
 $display("PASS: byte-exact A1320/66 -> B2640/254 -> B3960/254 -> T10660/5 -> unchanged A1320/66");
 $display("PASS: speed/type b_ctx latched before MAP and stable through frame transmission despite upstream change");
 $finish;
end
initial begin #20000000;$fatal(1,"Backend simulation timeout");end
endmodule
