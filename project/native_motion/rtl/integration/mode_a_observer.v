// Passive 100 MHz stage timer and overwrite ring. Never stalls vision or motion.
`timescale 1ns/1ps
module mode_a_observer(
 input wire clk,rst_n,capture,loc_start,loc_done,cls_start,cls_done,result_valid,
 input wire [31:0] capture_id,job_id,result_id,task_status,motion_frames,
 input wire [191:0] last_delivered,
 input wire freeze_trace,
 input wire [7:0] read_index,
 output reg [255:0] read_record,
 output reg [31:0] loc_cycles,cls_cycles,trace_total,trace_collisions,
 output wire [31:0] cycle_now,
 output wire [7:0] write_index);
 reg [31:0] cycles,loc_begin,cls_begin,last_task,last_frames;
 reg [7:0] wr;
 (* ram_style="block" *) reg [255:0] trace[0:255];
 assign cycle_now=cycles;assign write_index=wr;
 wire task_event=task_status!=last_task,tx_event=motion_frames!=last_frames;
 wire [3:0] event_count={3'd0,capture}+{3'd0,loc_start}+{3'd0,loc_done}+{3'd0,cls_start}+{3'd0,cls_done}+{3'd0,result_valid}+{3'd0,task_event}+{3'd0,tx_event};
 reg [3:0] event_code;reg [27:0] event_tag;
 always @*begin
  event_code=0;event_tag=job_id[27:0];
  if(capture)begin event_code=1;event_tag=capture_id[27:0];end
  else if(loc_start)event_code=2;
  else if(loc_done)event_code=3;
  else if(cls_start)event_code=4;
  else if(cls_done)event_code=5;
  else if(result_valid)begin event_code=6;event_tag=result_id[27:0];end
  else if(task_event)begin event_code=7;event_tag=task_status[27:0];end
  else if(tx_event)begin event_code=8;event_tag=motion_frames[27:0];end
 end
 always @(posedge clk)begin
  read_record<=trace[read_index];
  if(!rst_n)begin cycles<=0;loc_begin<=0;cls_begin<=0;loc_cycles<=0;cls_cycles<=0;trace_total<=0;trace_collisions<=0;wr<=0;last_task<=0;last_frames<=0;end
  else begin
   cycles<=cycles+1'b1;last_task<=task_status;last_frames<=motion_frames;
   if(loc_start)loc_begin<=cycles;
   if(loc_done)loc_cycles<=cycles-loc_begin;
   if(cls_start)cls_begin<=cycles;
   if(cls_done)cls_cycles<=cycles-cls_begin;
   if(event_code!=0 && !freeze_trace)begin trace[wr]<={last_delivered,event_code,event_tag,cycles};wr<=wr+1'b1;trace_total<=trace_total+1'b1;end
   if(event_count>1 && !freeze_trace)trace_collisions<=trace_collisions+event_count-1'b1;
  end
 end
endmodule
