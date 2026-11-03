`timescale 1ns/1ps
module tb_handalign_regs;
reg clk=0;always #5 clk=~clk;reg rst=0,unlock=1;
reg[11:0]aw=0,ar=0;reg av=0,wv=0,rv=0;reg[31:0]wd=0;wire ayr,wyr,bv,ary,rr;wire[1:0]br,rresp;wire[31:0]rd;
wire mw,commit,mready,committed,me;wire[3:0]cellid,code;wire[1:0]wordid;wire[31:0]data,revision,active;wire[15:0]mask;wire[2:0]banks;reg[1:0]bank=0;reg[8:0]ka=0;wire[31:0]kd;
s4_task_regs #(.HAND_ALIGN(1),.HANDOVER_V2(1),.SLOT_INVENTORY(1))regs(.clk(clk),.rst_n(rst),.s_awaddr(aw),.s_awvalid(av),.s_awready(ayr),.s_wdata(wd),.s_wstrb(4'hf),.s_wvalid(wv),.s_wready(wyr),.s_bresp(br),.s_bvalid(bv),.s_bready(1'b1),.s_araddr(ar),.s_arvalid(rv),.s_arready(ary),.s_rdata(rd),.s_rresp(rresp),.s_rvalid(rr),.s_rready(1'b1),.cfg_unlock(unlock),.fifo_unlock(unlock),.kp_bank(bank),.kp_raddr(ka),.kp_rdata(kd),.cfg_banks_ready(banks),.map_write(mw),.map_commit(commit),.map_cell(cellid),.map_word(wordid),.map_wdata(data),.map_revision(revision),.map_mask(mask),.map_ready(mready),.map_committed(committed),.map_error(me),.map_locked(1'b0),.map_error_code(code),.map_active_revision(active),.cmd_done(1'b0),.cnt_inc(6'd0),.event_set(16'd0),.fifo_clear(1'b0),.poll_done(1'b0));
hand_align_region_lut #(.REGION_COUNT(3))lut(.clk(clk),.rst_n(rst),.task_active(!unlock),.cfg_write(mw),.cfg_commit(commit),.cfg_cell(cellid),.cfg_word(wordid),.cfg_wdata(data),.cfg_revision(revision),.cfg_mask(mask),.cfg_ready(mready),.cfg_error(me),.committed(committed),.cfg_error_code(code),.active_revision(active),.lookup_req(1'b0));
task wr(input[11:0]a,input[31:0]v,input[1:0]expected);begin
 @(negedge clk);aw=a;wd=v;av=1;wv=1;wait(ayr&&wyr);@(negedge clk);av=0;wv=0;wait(bv);if(br!=expected)$fatal(1,"AXI write response %h %h",a,br);@(negedge clk);end endtask
task readcheck(input[11:0]a,input[31:0]value,input[31:0]maskv);begin
 @(negedge clk);ar=a;rv=1;wait(ary);@(negedge clk);rv=0;wait(rr);if(rresp!=0 || (rd&maskv)!=(value&maskv))$fatal(1,"AXI read %h got %h expected %h",a,rd,value);@(negedge clk);end endtask
integer b,i,c,w;
initial begin
 repeat(5)@(negedge clk);rst=1;
 readcheck(12'h010,32'h3407,32'hffffffff);
 wr(12'h12c,3,2);
 for(b=0;b<3;b=b+1)begin
  wr(12'h12c,b,0);wr(12'h110,0,0);
  for(i=0;i<511;i=i+1)wr(12'h114,(b<<16)|i,0);
  if(banks[b])$fatal(1,"Incomplete bank marked ready");
  wr(12'h114,(b<<16)|511,0);if(!banks[b])$fatal(1,"Complete bank missing");
  bank=b;ka=511;repeat(3)@(negedge clk);if(kd!==((b<<16)|511))$fatal(1,"Bank read last");
  ka=7;repeat(3)@(negedge clk);if(kd!==((b<<16)|7))$fatal(1,"Padding/address skipped");
 end
 readcheck(12'h12c,32'h1e,32'h1f);
 wr(12'h308,7,0);wr(12'h30c,1234,0);wr(12'h310,1,0);wait(mready);repeat(3)@(negedge clk);if(committed || !regs.map_error_sticky)$fatal(1,"Incomplete map accepted");
 for(c=0;c<3;c=c+1)begin
  wr(12'h300,c*4,0);
  for(w=0;w<4;w=w+1)begin
   case(w)0:wd=c*40|((c*40+39)<<9);1:wd=16|(111<<9);2:wd=15|(97<<6)|(557<<18);3:wd=353;endcase
   wr(12'h304,wd,0);
  end
 end
 wr(12'h310,1,0);wait(committed);if(active!=1234 || regs.map_error_sticky)$fatal(1,"Commit revision/error");
 for(c=0;c<3;c=c+1)if(lut.rows[c][8:0]!=c*40 || lut.written[c]!=15)$fatal(1,"Map write index race");
 unlock=0;wr(12'h12c,0,0);wr(12'h300,0,0);wr(12'h304,999,0);repeat(3)@(negedge clk);
 if(lut.rows[0][8:0]!=0 || regs.cfg_bank!=2 || !regs.event_sticky[14])$fatal(1,"Locked writes changed map/bank");
 $display("PASS: AXI ABI3407, 3x512 padded bank memory, incomplete-bank readiness, invalid bank rejection, map complete/revision/index, active-task config lock");$finish;
end
initial begin #2000000;$fatal(1,"AXI timeout");end
endmodule
