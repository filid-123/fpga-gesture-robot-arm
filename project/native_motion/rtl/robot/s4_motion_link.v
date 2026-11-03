// Native S4 adapter. Same operation FSM; no internal AXI register scheduling.
// Commands hold until accepted, with one completion per operation. Poll reuses
// the backend snapshot; no shadow watchdog or trajectory arithmetic is added.
`timescale 1ns/1ps
module s4_motion_link # (parameter integer TIMEOUT_CYCLES=4096) (
 input wire clk,rst_n,
 input wire op_valid, output wire op_ready, input wire [2:0] op_code,
 input wire [191:0] op_target, input wire [15:0] op_n,op_na,
 input wire op_profile,op_source,inhibit,
 output reg op_done,op_ok,op_timeout,
 input wire [31:0] cfg_period,cfg_stall,
 input wire [191:0] cfg_vmax,cfg_amax,
 output reg [31:0] st_s1_status,st_s1_error,st_fb_masks,st_fb_age,st_frames,
 output reg [31:0] st_pl_status,st_pl_error,st_pl_index,
 output reg [191:0] st_last,
 output wire native_valid, input wire native_ready, output wire [2:0] native_code,
 input wire native_done,native_ok,
 output wire native_snap, input wire native_snap_ready,native_snap_done,
 input wire [31:0] arm_status,arm_error,fb_masks,fb_age,frames,
 input wire [31:0] pl_status,pl_error,pl_index, input wire [191:0] last_data
);
 localparam IDLE=0,CMD_REQ=1,CMD_WAIT=2,SNAP_REQ=3,SNAP_WAIT=4;
 reg [2:0] state,code;
 reg [31:0] age;
 assign op_ready=(state==IDLE);
 assign native_valid=(state==CMD_REQ);
 assign native_code=code;
 assign native_snap=(state==SNAP_REQ);
 always @(posedge clk) begin
  if(!rst_n) begin
   state<=IDLE;code<=0;age<=0;op_done<=0;op_ok<=0;op_timeout<=0;
   st_s1_status<=0;st_s1_error<=0;st_fb_masks<=0;st_fb_age<=0;st_frames<=0;
   st_pl_status<=0;st_pl_error<=0;st_pl_index<=0;st_last<=0;
  end else begin
   op_done<=0;op_timeout<=0;
   if(state==IDLE) begin
    age<=0;
    if(op_valid) begin
     code<=op_code;
     if(inhibit && (op_code==1 || op_code==3 || op_code==7)) begin op_done<=1;op_ok<=0;end
     else state<=(op_code==0)?SNAP_REQ:CMD_REQ;
    end
   end else if(age+1>=TIMEOUT_CYCLES) begin
    state<=IDLE;op_done<=1;op_ok<=0;op_timeout<=1;
   end else begin
    age<=age+1;
    case(state)
     CMD_REQ: if(native_ready) state<=CMD_WAIT;
     CMD_WAIT: if(native_done) begin state<=IDLE;op_done<=1;op_ok<=native_ok;end
     SNAP_REQ: if(native_snap_ready) state<=SNAP_WAIT;
     SNAP_WAIT: if(native_snap_done) begin
      st_s1_status<=arm_status;st_s1_error<=arm_error;st_fb_masks<=fb_masks;
      st_fb_age<=fb_age;st_frames<=frames;st_pl_status<=pl_status;
      st_pl_error<=pl_error;st_pl_index<=pl_index;st_last<=last_data;
      state<=IDLE;op_done<=1;op_ok<=1;
     end
    endcase
   end
  end
 end
endmodule
