// EXPERIMENTAL: one front-end job plus one classifier, two ordered ROI slots.
// Camera ownership ends only after same-frame ROI extraction. A slot retains
// its frame metadata until the classifier result (or ordered miss) is emitted.
// All ports are in clk; camera CDC remains in the existing Phase2 front end.
`timescale 1ns/1ps
module autonomous_overlap_ctrl #(
 parameter integer NUM_CLASSES=6,TASK_CLASS_MAP=1
)(
 input wire clk,rst_n,camera_init_done,camera_init_error,fifo_overflow,pause_new_jobs,
 input wire[1:0]camera_buffer_valid,
 input wire camera_latest_buffer,
 input wire[31:0]camera_frame_id_0,camera_frame_id_1,camera_timestamp_0,camera_timestamp_1,
 output wire capture_enable,
 output reg[1:0]camera_buffer_release,
 input wire locator_busy,locator_done,
 output reg locator_start,locator_input_buffer,
 output reg[31:0]locator_frame_id,locator_timestamp_ms,
 input wire[31:0]top1_cell,
 input wire signed[31:0]top1_confidence,top1_dx,top1_dy,top1_width,top1_height,
 output reg bbox_start,
 input wire bbox_busy,bbox_done,bbox_detected,
 output reg[7:0]bbox_cell,
 output reg signed[31:0]bbox_confidence,bbox_dx,bbox_dy,bbox_width,bbox_height,
 input wire[9:0]bbox_roi_x0,bbox_roi_y0,bbox_roi_side,
 input wire[8:0]bbox_raw_x0,bbox_raw_y0,bbox_raw_x1,bbox_raw_y1,
 input wire[8:0]bbox_ema_x0,bbox_ema_y0,bbox_ema_x1,bbox_ema_y1,
 input wire roi_busy,roi_done,roi_error,
 output reg roi_start,roi_buffer_id,roi_write_bank,
 output reg[9:0]roi_x0,roi_y0,roi_side,
 output reg[31:0]roi_tag,
 input wire classifier_request_busy,classifier_result_pulse,
 output reg classifier_request,classifier_read_bank,
 input wire[8:0]classifier_result_class,
 input wire[15:0]classifier_result_margin,
 output reg class_candidate_valid,
 output reg[2:0]class_candidate,result_model_class,
 output reg[15:0]class_candidate_margin,
 output reg[31:0]result_frame_id,result_timestamp_ms,
 output reg result_detected,
 output reg[8:0]result_raw_x0,result_raw_y0,result_raw_x1,result_raw_y1,
 output reg[8:0]result_ema_x0,result_ema_y0,result_ema_x1,result_ema_y1,
 output reg[9:0]result_roi_x0,result_roi_y0,result_roi_side,
 output reg signed[31:0]result_confidence,
 output reg fatal_error,
 output wire pipeline_idle,
 output wire[3:0]state_debug
);
 localparam F_IDLE=0,F_LOC_START=1,F_LOC_WAIT=2,F_TOP1=3,
            F_BOX_START=4,F_BOX_WAIT=5,F_ROI_START=6,F_ROI_WAIT=7;
 localparam C_IDLE=0,C_START=1,C_WAIT=2;
 localparam FREE=0,BUILD=1,READY=2,RUNNING=3;
 reg[2:0]front_state;
 reg[1:0]class_state,job_count;
 reg head,tail,front_bank,held_camera_buffer;
 reg[1:0]slot_state[0:1];
 reg needs_classifier[0:1];
 // id/ts/detected/raw box/EMA box/ROI descriptor/confidence = 199 bits.
 reg[198:0]metadata[0:1];
 wire[1:0]available=camera_buffer_valid & ~camera_buffer_release;
 wire selected=available[camera_latest_buffer]?camera_latest_buffer:available[1];
 wire allocate=front_state==F_IDLE && job_count<2 && |available &&
               camera_init_done && !pause_new_jobs && !fatal_error &&
               !camera_init_error && !fifo_overflow;
 wire finish_miss=class_state==C_IDLE && job_count!=0 &&
                  slot_state[head]==READY && !needs_classifier[head];
 wire finish_class=class_state==C_WAIT && classifier_result_pulse;
 wire retire=finish_miss || finish_class;
 assign capture_enable=camera_init_done && !fatal_error;
 assign pipeline_idle=front_state==F_IDLE && job_count==0 && class_state==C_IDLE && !fatal_error;
 // Existing snapshot logic recognizes state 1 as entirely quiescent.
 assign state_debug=fatal_error?4'd15:(pipeline_idle?4'd1:4'd2);
 wire[3:0]state=state_debug;
 function[2:0]task_class;
 input[8:0]c;
 begin
  if(c>=NUM_CLASSES)task_class=7;
  else if(TASK_CLASS_MAP!=0 && c==4)task_class=5;
  else if(TASK_CLASS_MAP!=0 && c==5)task_class=4;
  else task_class=c[2:0];
 end endfunction
 integer i;
 always @(posedge clk) begin
  if(!rst_n)begin
   front_state<=F_IDLE;class_state<=C_IDLE;job_count<=0;head<=0;tail<=0;
   front_bank<=0;held_camera_buffer<=0;camera_buffer_release<=0;
   locator_start<=0;locator_input_buffer<=0;locator_frame_id<=0;locator_timestamp_ms<=0;
   bbox_start<=0;bbox_cell<=0;bbox_confidence<=0;bbox_dx<=0;bbox_dy<=0;bbox_width<=0;bbox_height<=0;
   roi_start<=0;roi_buffer_id<=0;roi_write_bank<=0;roi_x0<=0;roi_y0<=0;roi_side<=1;roi_tag<=0;
   classifier_request<=0;classifier_read_bank<=0;
   class_candidate_valid<=0;class_candidate<=7;result_model_class<=7;class_candidate_margin<=0;
   result_frame_id<=0;result_timestamp_ms<=0;result_detected<=0;
   result_raw_x0<=0;result_raw_y0<=0;result_raw_x1<=0;result_raw_y1<=0;
   result_ema_x0<=0;result_ema_y0<=0;result_ema_x1<=0;result_ema_y1<=0;
   result_roi_x0<=0;result_roi_y0<=0;result_roi_side<=1;result_confidence<=0;
   fatal_error<=0;
   for(i=0;i<2;i=i+1)begin slot_state[i]<=FREE;needs_classifier[i]<=0;metadata[i]<=0;end
  end else begin
   camera_buffer_release<=0;locator_start<=0;bbox_start<=0;roi_start<=0;
   classifier_request<=0;class_candidate_valid<=0;
   if(camera_init_error || fifo_overflow || fatal_error)begin
    fatal_error<=1;camera_buffer_release<=camera_buffer_valid;
   end else begin
    case({allocate,retire})
     2'b10:job_count<=job_count+1'b1;
     2'b01:job_count<=job_count-1'b1;
     default:begin end
    endcase
    if(allocate)begin
     front_bank<=tail;slot_state[tail]<=BUILD;needs_classifier[tail]<=0;tail<=~tail;
     held_camera_buffer<=selected;locator_input_buffer<=selected;
     locator_frame_id<=selected?camera_frame_id_1:camera_frame_id_0;
     locator_timestamp_ms<=selected?camera_timestamp_1:camera_timestamp_0;
     camera_buffer_release<=camera_buffer_valid & ~(selected?2'b10:2'b01);
     front_state<=F_LOC_START;
    end
    case(front_state)
     F_IDLE:begin end
     F_LOC_START:if(!locator_busy)begin locator_start<=1;front_state<=F_LOC_WAIT;end
     F_LOC_WAIT:if(locator_done)front_state<=F_TOP1;
     F_TOP1:begin
      bbox_cell<=top1_cell[7:0];bbox_confidence<=top1_confidence;
      bbox_dx<=top1_dx;bbox_dy<=top1_dy;bbox_width<=top1_width;bbox_height<=top1_height;
      front_state<=F_BOX_START;
     end
     F_BOX_START:if(!bbox_busy)begin bbox_start<=1;front_state<=F_BOX_WAIT;end
     F_BOX_WAIT:if(bbox_done)begin
      metadata[front_bank]<={locator_frame_id,locator_timestamp_ms,bbox_detected,
       bbox_raw_x0,bbox_raw_y0,bbox_raw_x1,bbox_raw_y1,
       bbox_ema_x0,bbox_ema_y0,bbox_ema_x1,bbox_ema_y1,
       bbox_roi_x0,bbox_roi_y0,bbox_roi_side,bbox_confidence};
      if(!bbox_detected)begin
       camera_buffer_release<=held_camera_buffer?2'b10:2'b01;
       slot_state[front_bank]<=READY;front_state<=F_IDLE;
      end else begin
       roi_buffer_id<=held_camera_buffer;roi_write_bank<=front_bank;
       roi_x0<=bbox_roi_x0;roi_y0<=bbox_roi_y0;roi_side<=bbox_roi_side;
       roi_tag<=locator_frame_id;front_state<=F_ROI_START;
      end
     end
     F_ROI_START:if(!roi_busy)begin roi_start<=1;front_state<=F_ROI_WAIT;end
     F_ROI_WAIT:if(roi_error || roi_done)begin
      camera_buffer_release<=held_camera_buffer?2'b10:2'b01;
      needs_classifier[front_bank]<=!roi_error;
      slot_state[front_bank]<=READY;front_state<=F_IDLE;
     end
     default:fatal_error<=1;
    endcase
    case(class_state)
     C_IDLE:if(job_count!=0 && slot_state[head]==READY && needs_classifier[head] && !classifier_request_busy)begin
      classifier_read_bank<=head;class_state<=C_START;
     end
     C_START:if(!classifier_request_busy)begin
      classifier_request<=1;slot_state[head]<=RUNNING;class_state<=C_WAIT;
     end
     C_WAIT:if(classifier_result_pulse)class_state<=C_IDLE;
     default:fatal_error<=1;
    endcase
    if(retire)begin
     {result_frame_id,result_timestamp_ms,result_detected,
      result_raw_x0,result_raw_y0,result_raw_x1,result_raw_y1,
      result_ema_x0,result_ema_y0,result_ema_x1,result_ema_y1,
      result_roi_x0,result_roi_y0,result_roi_side,result_confidence}<=metadata[head];
     class_candidate_valid<=1;
     class_candidate<=finish_class?task_class(classifier_result_class):3'd7;
     result_model_class<=finish_class && classifier_result_class<NUM_CLASSES?classifier_result_class[2:0]:3'd7;
     class_candidate_margin<=finish_class?classifier_result_margin:16'd0;
     slot_state[head]<=FREE;head<=~head;
    end
   end
  end
 end
endmodule
