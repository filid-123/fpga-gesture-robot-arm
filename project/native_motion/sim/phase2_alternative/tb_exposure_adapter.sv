`timescale 1ns/1ps
module tb_exposure_adapter;
reg clk=0;always #5 clk=~clk;reg rst=0;
reg[11:0]aw=0,ar=0;reg[31:0]wd=0;reg[3:0]strb=15;
reg av=0,wv=0,bready=0,arv=0,rr=0;
wire awr,wr,bv,rv;wire[1:0]br,rresp;wire[31:0]rd;
reg ready=0,busy=0,done=0,err=0;reg[7:0]data=0;
wire start,readcmd;wire[15:0]addr;wire[7:0]outdata;
integer starts=0;
s5_vision_event_adapter #(.PHASE2_FRONTEND(1),.CAMERA_CONTROL(1)) dut(
.clk(clk),.rst_n(rst),.frame_valid(1'b0),.frame_class(3'd7),.frame_detected(1'b0),.frame_id(32'd0),
.stable_class(3'd7),.leds(4'd0),.qualified_valid(1'b0),.now_ms(32'd0),
.camera_cmd_start(start),.camera_cmd_read(readcmd),.camera_cmd_addr(addr),.camera_cmd_data(outdata),
.camera_cmd_ready(ready),.camera_cmd_busy(busy),.camera_cmd_done(done),.camera_cmd_error(err),.sensor_read_data(data),
.s_awaddr(aw),.s_awvalid(av),.s_awready(awr),.s_wdata(wd),.s_wstrb(strb),.s_wvalid(wv),.s_wready(wr),
.s_bvalid(bv),.s_bresp(br),.s_bready(bready),.s_araddr(ar),.s_arvalid(arv),.s_arready(),
.s_rdata(rd),.s_rresp(rresp),.s_rvalid(rv),.s_rready(rr));
always @(posedge clk) if(start) starts=starts+1;
task write_word(input[11:0]a,input[31:0]v,input[1:0]expect_resp);
begin
 @(negedge clk);aw=a;wd=v;av=1;
 @(negedge clk);av=0;repeat(2)@(negedge clk);wv=1;
 @(negedge clk);wv=0;wait(bv);@(negedge clk);
 if(br!==expect_resp)$fatal(1,"FAIL: write response %h %h",a,br);
 repeat(3)begin @(negedge clk);if(!bv || br!==expect_resp)$fatal(1,"FAIL: B backpressure");end
 bready=1;@(negedge clk);bready=0;@(negedge clk);
end endtask
task read_word(input[11:0]a,input[31:0]v);
begin
 ar=a;arv=1;@(negedge clk);arv=0;wait(rv);@(negedge clk);
 if(rresp!==0||rd!==v)$fatal(1,"FAIL: read %h got%h expected%h",a,rd,v);
 repeat(3)begin @(negedge clk);if(!rv||rd!==v)$fatal(1,"FAIL: R backpressure");end
 rr=1;@(negedge clk);rr=0;@(negedge clk);
end endtask
task finish_cmd(input[7:0]v,input e);
begin busy=0;ready=1;data=v;err=e;done=1;@(negedge clk);done=0;@(negedge clk);end endtask
initial begin
 repeat(3)@(negedge clk);rst=1;repeat(3)@(negedge clk);
 read_word('h008,'h3505);read_word('h094,'h45585031);
 write_word('h088,'h00350303,2); // no runtime ownership during init
 ready=1;
 write_word('h088,'h00380001,2); // cannot change geometry
 write_word('h088,'h01350303,2); // reserved bits
 write_word('h088,'h80350301,2); // read payload
 strb=1;write_word('h088,'h00350303,2);strb=15;
 write_word('h089,'h00350303,2);
 if(starts!=0)$fatal(1,"FAIL: rejected command leaked");
 write_word('h088,'h00350303,0);
 if(!dut.camera_pending||addr!=='h3503||outdata!==3||readcmd)$fatal(1,"FAIL: atomic command");
 busy=1;ready=0;write_word('h088,'h80350000,2);
 if(starts!=1)$fatal(1,"FAIL: reissue or busy accepted");
 finish_cmd(0,0);read_word('h08c,'h0001000a);
 write_word('h088,'h80350100,0);read_word('h088,'h80350100);
 if(!readcmd||addr!=='h3501)$fatal(1,"FAIL: read command");
 finish_cmd('h5a,0);read_word('h090,'h5a);read_word('h08c,'h0002000a);
 write_word('h088,'h00350b10,0);finish_cmd(0,1);read_word('h08c,'h0003000e);
 if(starts!=3)$fatal(1,"FAIL: incorrect accepted command count");
 rst=0;repeat(3)@(negedge clk);rst=1;repeat(2)@(negedge clk);read_word('h08c,8);
 $display("PASS: EXPOSURE_AXI atomic/skewedAW-W/backpressure/whitelist/initbusy/NACK/sequence/reset");$finish;
end
initial begin #1000000;$fatal(1,"FAIL: exposure AXI watchdog");end
endmodule
