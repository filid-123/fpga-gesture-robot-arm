// EXPERIMENTAL HandAlign protocol core. A candidate is a replaceable mailbox,
// not a ready/valid motion sample. S4 must explicitly accept it and report
// that accepted cell settled before PALM may lock its whole path bundle.
// S4 accepts a bank then reports settled; the mailbox issues no motion command.
`timescale 1ns/1ps
module hand_align_target_core #(parameter integer PIPELINED_FRESHNESS=0,parameter integer EXPLICIT_ACCEPT=0, parameter integer POSITION_ONLY=0)(
 input wire clk,rst_n,task_active,waiting_region,cancel,fault,
 input wire[31:0]now_ms,max_age_ms,max_gap_ms,
 input wire[15:0]hold_ms,
 input wire[7:0]min_frames,
 input wire response_valid,mapped_valid,
 input wire[3:0]mapped_cell,
 input wire[41:0]mapped_bundle,
 input wire[31:0]mapped_frame_id,mapped_timestamp_ms,mapped_revision,
 input wire[2:0]mapped_class,
 input wire accept_target,position_settled,palm_confirmed,
 input wire[3:0]accepted_cell_in,
 input wire[31:0]accepted_revision_in,
 output wire target_valid,
 output reg[3:0]target_cell,
 output reg[41:0]target_bundle,
 output reg[31:0]target_frame_id,target_timestamp_ms,target_revision,
 output reg locked,
 output wire delivery_ready,
 output reg[3:0]locked_cell,
 output reg[41:0]locked_bundle,
 output reg[31:0]locked_frame_id,locked_timestamp_ms,locked_revision
);
 reg seen,pending,inhibited,accepted;
 reg[31:0]last_id,last_ts,first_ts,accepted_revision;
 reg[3:0]accepted_cell;
 reg[7:0]count;
 reg[2:0]target_class;
 wire[31:0]age=now_ms-mapped_timestamp_ms;
 wire[31:0]gap=mapped_timestamp_ms-last_ts;
 wire[31:0]elapsed=mapped_timestamp_ms-first_ts;
 wire reliable=mapped_valid && (POSITION_ONLY!=0 || (mapped_class>=1 && mapped_class<=4)) && mapped_revision!=0 && age<=max_age_ms;
 reg target_age_ok;
 always @(posedge clk)begin
  if(!rst_n || !task_active)target_age_ok<=0;
  else target_age_ok<=now_ms-target_timestamp_ms<=max_age_ms;
 end
 assign target_valid=pending && task_active && waiting_region && !locked && !inhibited &&
                     ((PIPELINED_FRESHNESS!=0)?target_age_ok:(now_ms-target_timestamp_ms<=max_age_ms));
 assign delivery_ready=locked && task_active && !inhibited;
 always @(posedge clk)begin
  if(!rst_n || !task_active)begin
   seen<=0;pending<=0;inhibited<=0;accepted<=0;locked<=0;count<=0;
   last_id<=0;last_ts<=0;first_ts<=0;accepted_cell<=0;accepted_revision<=0;
   target_cell<=0;target_bundle<=0;target_frame_id<=0;target_timestamp_ms<=0;target_revision<=0;target_class<=7;
   locked_cell<=0;locked_bundle<=0;locked_frame_id<=0;locked_timestamp_ms<=0;locked_revision<=0;
  end else if(cancel || fault)begin
   inhibited<=1;pending<=0;
   // Keep locked route data available for the task's existing exit handling.
  end else if(!locked && !inhibited)begin
   // Registered S4 acceptance arrives one cycle after waiting_region falls.
   if(accept_target)begin
    if(EXPLICIT_ACCEPT!=0)begin accepted<=1;accepted_cell<=accepted_cell_in;accepted_revision<=accepted_revision_in;end
    else if(pending && now_ms-target_timestamp_ms<=max_age_ms)begin accepted<=1;accepted_cell<=target_cell;accepted_revision<=target_revision;end
   end
   if(response_valid && (!seen || mapped_frame_id!=last_id))begin
    seen<=1;last_id<=mapped_frame_id;last_ts<=mapped_timestamp_ms;
    target_class<=mapped_class;
    if(!waiting_region || !reliable)begin pending<=0;count<=0;end
    else begin
     target_cell<=mapped_cell;target_bundle<=mapped_bundle;target_frame_id<=mapped_frame_id;
     target_timestamp_ms<=mapped_timestamp_ms;target_revision<=mapped_revision;
     if(!seen || count==0 || gap==0 || gap>max_gap_ms || mapped_cell!=target_cell || mapped_revision!=target_revision)begin
      first_ts<=mapped_timestamp_ms;count<=1;pending<=min_frames<=1 && hold_ms==0;
     end else begin
      if(count!=255)count<=count+1'b1;
      pending<=elapsed>=hold_ms && {1'b0,count}+9'd1>=min_frames;
     end
    end
   end
   // Wait a cycle after a response so a newly invalid/non-PALM observation
   // cannot race a PALM assertion referring to the previous observation.
   if(!response_valid && target_valid && target_class==4 && accepted &&
      accepted_cell==target_cell && accepted_revision==target_revision && position_settled && palm_confirmed)begin
    locked<=1;pending<=0;locked_cell<=target_cell;locked_bundle<=target_bundle;
    locked_frame_id<=target_frame_id;locked_timestamp_ms<=target_timestamp_ms;locked_revision<=target_revision;
   end
  end
 end
endmodule
