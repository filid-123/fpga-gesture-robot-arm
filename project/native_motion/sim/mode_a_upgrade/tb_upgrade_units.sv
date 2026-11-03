`timescale 1ns/1ps
module tb_upgrade_units;
 reg clk=0,rst=0;always #5 clk=~clk;
 reg[8:0]addr=0;reg[1:0]bank=0;reg mix=0;reg[6:0]step=32;wire[31:0]q;
 reg[31:0]memory[0:2047];integer s,a,lb,w;reg signed[63:0]l,h,expected;
 s4_task_regs #(.HAND_ALIGN(1),.HAND_ALIGN_REGIONS(4),.HAND_ALIGN_LOCATOR(1),.CONTINUOUS_HAND(1)) regs(
  .clk(clk),.rst_n(rst),.s_awvalid(1'b0),.s_wvalid(1'b0),.s_arvalid(1'b0),.s_bready(1'b1),.s_rready(1'b1),
  .kp_raddr(addr),.kp_bank(bank),.kp_mix_enable(mix),.active_step(step),.target_step(step),.kp_rdata(q));
 reg capture=0,ls=0,ld=0,cs=0,cd=0,rv=0,freeze=0;reg[31:0]id=0,taskword=0,frames=0;reg[191:0]last=0;
 reg[7:0]ri=0;wire[255:0]record;wire[31:0]lc,cc,total,coll,now;wire[7:0]wi;
 mode_a_observer obs(.clk(clk),.rst_n(rst),.capture(capture),.loc_start(ls),.loc_done(ld),.cls_start(cs),.cls_done(cd),.result_valid(rv),
  .capture_id(id),.job_id(id),.result_id(id),.task_status(taskword),.motion_frames(frames),.last_delivered(last),.freeze_trace(freeze),
  .read_index(ri),.read_record(record),.loc_cycles(lc),.cls_cycles(cc),.trace_total(total),.trace_collisions(coll),.cycle_now(now),.write_index(wi));
 integer i,begin_time,baseline,loc_begin;reg[255:0]saved;
 reg map_valid=0;reg[8:0]map_x=60,map_y=64;wire[6:0]map_step;
 hand_y_step_map step_map(clk,rst,map_valid,map_x,map_y,map_step);
 reg[31:0]cycle_input=0;wire[7:0]converted_ms;
 cycles_to_ms8 converter(clk,rst,cycle_input,converted_ms);
 initial begin
  $readmemh("keypoints.mem",memory);for(i=0;i<2048;i=i+1)regs.kp_mem[i]=memory[i];
  repeat(8)@(negedge clk);rst=1;repeat(3)@(negedge clk);
  if(regs.ABI!=32'h340a)$fatal(1,"Continuous ABI");
  for(i=16;i<=111;i=i+1)begin
   map_y=i;map_valid=1;@(negedge clk);map_valid=0;repeat(2)@(negedge clk);
   baseline=(i<=44)?64:((i>=84)?0:((84-i)*8+2)/5);
   if(map_step!=baseline)$fatal(1,"Image coordinate map mismatch Y=%0d",i);
  end
  map_x=511;map_y=44;map_valid=1;repeat(3)@(negedge clk);map_valid=0;
  if(map_step!=0)$fatal(1,"Invalid center changed target");
  $display("PASS: production pipelined imageY map all96 valid rows, exact bounds and invalid center rejection");
  for(i=0;i<=255;i=i+1)begin
   cycle_input=i*100000+99999;repeat(10)@(negedge clk);
   if(converted_ms!=i)$fatal(1,"Pipelined millisecond conversion %0d got %0d",i,converted_ms);
  end
  cycle_input=32'hffffffff;repeat(10)@(negedge clk);if(converted_ms!=255)$fatal(1,"MS saturation");
  $display("PASS: pipelined cycle/ms conversion all256 bins, boundaries and full32-bit saturation");
  // Precheck must see every original bank without interpolation.
  for(i=0;i<4;i=i+1)for(a=0;a<512;a=a+1)begin
   bank=i;addr=a;repeat(5)@(negedge clk);if(q!==memory[i*512+a])$fatal(1,"Raw precheck bank mismatch");
  end
  mix=1;
  for(s=0;s<=64;s=s+1)begin
   step=s;lb=(s<32)?0:1;w=s-lb*32;
   for(a=0;a<376;a=a+1)begin
    addr=a;l=$signed(memory[lb*512+a]);h=$signed(memory[(lb+1)*512+a]);expected=l+(((h-l)*w+16)>>>5);
    repeat(5)@(negedge clk);if(q!==expected[31:0])$fatal(1,"Blend mismatch step=%0d address=%0d",s,a);
   end
  end
  $display("PASS: production two-port keypoint RAM all65 continuous positions and47 keypoints, raw precheck banks unchanged");
  ls=1;loc_begin=now;@(negedge clk);ls=0;repeat(19)@(negedge clk);ld=1;@(negedge clk);ld=0;
  if(lc!=20)$fatal(1,"Locator timer %d",lc);
  cs=1;@(negedge clk);cs=0;repeat(9)@(negedge clk);cd=1;@(negedge clk);cd=0;
  if(cc!=10)$fatal(1,"Classifier timer %d",cc);
  baseline=coll;capture=1;rv=1;id=321;@(negedge clk);capture=0;rv=0;if(coll!=baseline+1)$fatal(1,"Collision accounting");
  for(i=0;i<300;i=i+1)begin frames=frames+1;last={6{32'h12340000+i}};@(negedge clk);end
  freeze=1;baseline=total;ri=wi-1;repeat(3)@(negedge clk);saved=record;
  if(record[63:60]!=8 || record[59:32]!=300 || record[255:64]!==last)$fatal(1,"Trace command/angles mismatch");
  repeat(20)begin frames=frames+1;@(negedge clk);end
  if(total!=baseline || record!==saved)$fatal(1,"Frozen trace changed");
  freeze=0;frames=frames+1;@(negedge clk);if(total!=baseline+1)$fatal(1,"Unfreeze failed");
  $display("PASS: stage cycle timers, trace collision accounting, overwrite wrap, six-axis LAST_DELIVERED and coherent freeze/read/unfreeze");
  $finish;
 end
endmodule
