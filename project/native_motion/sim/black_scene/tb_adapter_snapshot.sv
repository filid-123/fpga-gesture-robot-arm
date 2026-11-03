`timescale 1ns/1ps
module tb_adapter_snapshot;
reg clk=0;always #5 clk=~clk;reg rst=0,qv=0,fv=0;reg[2:0]cls=4;reg[31:0]fid=1;
reg[11:0]wa=0,ra=0;reg[31:0]wd=0;reg wv=0,rv=0,rr=0;wire se,re;wire[16:0]addr;reg[31:0]ram=0;
wire vr;wire[31:0]rd;wire[1:0]resp;
s5_vision_event_adapter #(.USE_QUALIFIED_INPUT(1),.CAMERA_DIAGNOSTICS(1)) dut(.clk(clk),
.rst_n(rst),
.frame_valid(fv),
.frame_class(cls),
.frame_detected(1'b1),
.frame_id(fid),
.raw_x0('0),
.raw_y0('0),
.raw_x1('0),
.raw_y1('0),
.ema_x0('0),
.ema_y0('0),
.ema_x1('0),
.ema_y1('0),
.stable_class(cls),
.leds(4'hc),
.qualified_valid(qv),
.acquisition_ms(32'd10),
.now_ms(32'd40),
.result_margin(16'd33),
.model_class(3'd5),
.confidence_raw(-32'sd2500),
.camera_status(32'h0005212b),.frame_drop_count(32'd17),.format_error_count(32'd3),
.snapshot_ready(se),
.snapshot_frame_id(32'd77),
.snapshot_timestamp_ms(32'd99),
.snapshot_data(ram),
.s_awaddr(wa),
.s_awvalid(wv),
.s_wdata(wd),
.s_wstrb(4'hf),
.s_wvalid(wv),
.s_bready(1'b1),
.s_araddr(ra),
.s_arvalid(rv),
.s_rready(rr),
.snapshot_enable(se),.snapshot_rd_en(re),.snapshot_word_addr(addr),.s_rvalid(vr),.s_rdata(rd),.s_rresp(resp));
reg re_q=0;reg[31:0]ram_stage=0;
always @(posedge clk)begin
 re_q<=re;if(re)ram_stage<=32'hABCD0000+addr;
 if(re_q)ram<=ram_stage;
end
task wr(input[11:0]a,input[31:0]v);begin wa=a;wd=v;wv=1;@(negedge clk);wv=0;wait(dut.s_bvalid);repeat(2)@(negedge clk);end endtask
task read_word(input[11:0]a,input[31:0]v);reg[31:0]saved;begin ra=a;rv=1;rr=0;@(negedge clk);rv=0;wait(vr);@(negedge clk);if(resp!=0||rd!==v)$fatal(1,"FAIL: AXI addr=%h got=%h expected=%h",a,rd,v);saved=rd;repeat(4)begin @(negedge clk);if(!vr||rd!==saved)$fatal(1,"FAIL: AXI read backpressure");end rr=1;@(negedge clk);rr=0;@(negedge clk);end endtask
initial begin
repeat(3)@(negedge clk);rst=1;repeat(3)@(negedge clk);
read_word(12'h008,32'h3503);
read_word(12'h074,32'h43414d31);read_word(12'h078,32'h0005212b);
read_word(12'h07c,17);read_word(12'h080,3);read_word(12'h084,40);
wr(12'h040,1);wr(12'h04c,5);
read_word(12'h050,32'hABCD0005);read_word(12'h050,32'hABCD0006);read_word(12'h048,77);
wr(12'h040,0);fv=1;@(negedge clk);fv=0;repeat(5)@(negedge clk);
if(dut.vis_valid)$fatal(1,"FAIL: unqualified result escaped");qv=1;repeat(3)@(negedge clk);
if(!dut.vis_valid || dut.vis_stable_class!=4)$fatal(1,"FAIL: qualified live result");qv=0;@(negedge clk);@(negedge clk);
if(dut.vis_valid)$fatal(1,"FAIL: lost qualification did not invalidate");
read_word(12'h05c,10);read_word(12'h064,30);read_word(12'h06c,32'hfffff63c);
$display("PASS: ADAPTER snapshot RAM latency/autoincrement/AXI backpressure/qualified validity/telemetry");$finish;
end endmodule
