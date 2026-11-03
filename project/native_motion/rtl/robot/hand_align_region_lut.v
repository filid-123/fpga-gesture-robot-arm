// Discrete HandAlign map for S4 bank selection. Pixel cells bind complete paths;
// no conversion from geometric desk coordinates to executable joint targets.
// Four words/cell: X bounds, Y bounds, deliver/release/PRE, retreat.
`timescale 1ns/1ps
module hand_align_region_lut #(parameter integer REGION_COUNT=16)(
 input wire clk,rst_n,task_active,
 input wire cfg_write,cfg_commit,
 input wire[3:0]cfg_cell,
 input wire[1:0]cfg_word,
 input wire[31:0]cfg_wdata,cfg_revision,
 input wire[15:0]cfg_mask,
 output wire cfg_ready,
 output reg cfg_error,committed,
 output reg[3:0]cfg_error_code,
 output reg[31:0]active_revision,
 input wire lookup_req,
 input wire[8:0]lookup_x,lookup_y,
 input wire[31:0]lookup_frame_id,lookup_timestamp_ms,
 input wire[2:0]lookup_class,
 output reg response_valid,mapped_valid,
 output reg[3:0]mapped_cell,
 output reg[41:0]mapped_bundle,
 output reg[31:0]mapped_frame_id,mapped_timestamp_ms,mapped_revision,
 output reg[2:0]mapped_class
);
 reg[127:0]rows[0:REGION_COUNT-1];
 reg[3:0]written[0:REGION_COUNT-1];
 reg[15:0]active_mask,scan_mask;
 reg[31:0]scan_revision;
 reg[1:0]state;
 reg[4:0]ci,cj;
 localparam IDLE=0,CHECK_ROW=1,CHECK_PAIR=2,FINISH=3;
 wire[127:0]row_i=rows[ci[3:0]],row_j=rows[cj[3:0]];
 wire[8:0]ix0=row_i[8:0],ix1=row_i[17:9],iy0=row_i[40:32],iy1=row_i[49:41];
 wire[8:0]jx0=row_j[8:0],jx1=row_j[17:9],jy0=row_j[40:32],jy1=row_j[49:41];
 wire overlaps=ix0<=jx1 && jx0<=ix1 && iy0<=jy1 && jy0<=iy1;
 assign cfg_ready=state==IDLE && !task_active;
 function good_path(input[11:0]d);
 begin good_path=d[11:6]!=0 && ({1'b0,d[11:6]}+{1'b0,d[5:0]}<=7'd64);end endfunction
 task reject(input[3:0]reason);
 begin cfg_error<=1;cfg_error_code<=reason;committed<=0;state<=IDLE;end endtask
 integer i,k;
 reg found;
 reg[3:0]selected;
 always @(*)begin
  found=0;selected=0;
  for(k=0;k<REGION_COUNT;k=k+1)begin
   if(!found && active_mask[k] && lookup_x>=rows[k][8:0] && lookup_x<=rows[k][17:9] &&
      lookup_y>=rows[k][40:32] && lookup_y<=rows[k][49:41])begin found=1;selected=k;end
  end
 end
 always @(posedge clk)begin
  if(!rst_n)begin
   state<=IDLE;ci<=0;cj<=0;scan_mask<=0;scan_revision<=0;active_mask<=0;active_revision<=0;
   cfg_error<=0;cfg_error_code<=0;committed<=0;response_valid<=0;mapped_valid<=0;
   mapped_cell<=0;mapped_bundle<=0;mapped_frame_id<=0;mapped_timestamp_ms<=0;mapped_revision<=0;mapped_class<=7;
   for(i=0;i<REGION_COUNT;i=i+1)written[i]<=0;
  end else begin
   cfg_error<=0;response_valid<=lookup_req;
   if(lookup_req)begin
    mapped_valid<=committed && found && state==IDLE;
    mapped_cell<=selected;
    mapped_bundle<={rows[selected][107:96],rows[selected][93:82],rows[selected][81:70],rows[selected][69:64]};
    mapped_frame_id<=lookup_frame_id;mapped_timestamp_ms<=lookup_timestamp_ms;
    mapped_revision<=active_revision;mapped_class<=lookup_class;
   end
   if((cfg_write || cfg_commit) && !cfg_ready)begin cfg_error<=1;cfg_error_code<=1;end
   if(cfg_write && cfg_ready && cfg_cell<REGION_COUNT)begin
    rows[cfg_cell][cfg_word*32+:32]<=cfg_wdata;
    written[cfg_cell][cfg_word]<=1;committed<=0;
   end
   if(cfg_write && cfg_ready && cfg_cell>=REGION_COUNT)begin cfg_error<=1;cfg_error_code<=8;end
   if(cfg_commit && cfg_ready)begin
    if(cfg_write || cfg_mask==0 || cfg_revision==0 || (cfg_mask & (16'hffff<<REGION_COUNT))!=0)reject(2);
    else begin
     committed<=0;scan_mask<=cfg_mask;scan_revision<=cfg_revision;ci<=0;cj<=0;state<=CHECK_ROW;
    end
   end
   case(state)
    IDLE:begin end
    CHECK_ROW:begin
     if(ci==REGION_COUNT)state<=FINISH;
     else if(!scan_mask[ci[3:0]])ci<=ci+1'b1;
     else if(written[ci[3:0]]!=4'hf)reject(3);
     else if(ix0>ix1 || ix1>127 || iy0>iy1 || iy0<16 || iy1>111)reject(4);
     else if(!good_path(row_i[93:82]) || !good_path(row_i[81:70]) || !good_path(row_i[107:96]))reject(5);
     else if(row_i[31:18]!=0 || row_i[63:50]!=0 || row_i[95:94]!=0 || row_i[127:108]!=0)reject(7);
     else begin cj<=0;state<=CHECK_PAIR;end
    end
    CHECK_PAIR:begin
     if(cj==ci)begin ci<=ci+1'b1;state<=CHECK_ROW;end
     else if(scan_mask[cj[3:0]] && overlaps)reject(6);
     else cj<=cj+1'b1;
    end
    FINISH:begin active_mask<=scan_mask;active_revision<=scan_revision;committed<=1;state<=IDLE;end
   endcase
  end
 end
endmodule
