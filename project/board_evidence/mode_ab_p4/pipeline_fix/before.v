// B-only bounded native route sequencer. Immutable committed Q16 program;
// PL owns timing, bank interpolation, partial reverse and the sample handshake.
// Configuration is a retired S1 AXI aperture, independently locked by S4 and
// by this player's busy/paused state. It cannot stream host commands at runtime.
`timescale 1ns/1ps
module b_route_player # (parameter integer MIN_PERIOD=512)(
 input wire clk,rst_n,cfg_unlock,
 input wire [7:0] awaddr,input wire awvalid,output wire awready,
 input wire [31:0] wdata,input wire [3:0] wstrb,input wire wvalid,output wire wready,
 output reg [1:0] bresp,output reg bvalid,input wire bready,
 input wire [7:0] araddr,input wire arvalid,output wire arready,
 output reg [31:0] rdata,output reg [1:0] rresp,output reg rvalid,input wire rready,
 input wire cmd_valid,output wire cmd_ready,input wire [2:0] cmd_code,
 input wire [15:0] cmd_stage,input wire reverse,input wire [191:0] cmd_target,input wire [31:0] stall_timeout,
 output reg cmd_done,cmd_ok,
 output wire [2:0] state,output reg [31:0] error,output wire [15:0] sample_index,
 output reg sample_valid,input wire sample_ready,input wire delivered,pending,
 output reg [191:0] sample_data,input wire [191:0] last_data,
 output reg [15:0] speed,output reg [7:0] acceleration,output reg gripper_only,
 output wire committed_out
);
 localparam IDLE=0,FETCH=1,RUN=2,PAUSED=3,DONE=4;
 reg [2:0] st;
 assign state=st;
 assign cmd_ready=1'b1;
 reg committed,awp,wp,read_wait;
 reg [7:0] wa;
 reg [31:0] wd;
 reg [3:0] ws;
 assign awready=!awp&&!bvalid;
 assign wready=!wp&&!bvalid;
 assign arready=!rvalid&&!read_wait;
 wire busy=(st==FETCH || st==RUN || st==PAUSED);
 wire cfg_ok=cfg_unlock&&!busy&&!pending&&!sample_valid;
 reg [3:0] plane;
 reg [10:0] cursor;
 reg [5:0] base_mask;
 reg [4:0] stage_count;
 reg [31:0] bases[0:5];
 (* ram_style="distributed" *) reg [31:0] desc[0:191];
 reg [191:0] desc_mask;
 wire write_go=awp&&wp&&!bvalid;
 wire bulk_write=write_go&&cfg_ok&&!committed&&wa[7]&&ws==15&&wa[1:0]==0;
 wire [11:0] write_address={1'b0,cursor}+{7'd0,wa[6:2]};
 reg [3:0] read_plane;
 reg [10:0] read_address;
 wire [10:0] rd_left,rd_right;
 wire [107:0] left_word,right_word;
 wire [10:0] mem_a=busy?rd_left:read_address;
 wire [10:0] mem_b=busy?rd_right:write_address[10:0];
 genvar g;
 generate for(g=0;g<6;g=g+1)begin:channel_ram
  b_route_ram u_ram(.clk(clk),.a_addr(mem_a),.b_addr(mem_b),
   .we(bulk_write&&plane==g&&write_address<2048&&wd=={{14{wd[17]}},wd[17:0]}),
   .wdata(wd[17:0]),.a_data(left_word[g*18+:18]),.b_data(right_word[g*18+:18]));
 end endgenerate
 assign committed_out=committed;
 reg [3:0] stage_id,last_stage;
 reg [6:0] hand_step,last_step;
 reg backwards,partial_valid;
 reg [10:0] position,last_position,total,count_l,count_r,base_l,base_r;
 reg [10:0] idx_l,idx_r,acc_l,acc_r,last_idx_l,last_idx_r,last_acc_l,last_acc_r;
 reg [5:0] weight;
 reg [1:0] bank_l,bank_r;
 reg [31:0] period,countdown;
 reg [31:0] stall_age;
 reg [191:0] final_target;
 reg [2:0] fetch_step;
 reg drain,final_frame,finishing;
 reg [1:0] read_delay;
 reg [31:0] meta,reverse_meta;
 wire [7:0] dl={bank_l,stage_id,2'b00};
 wire [7:0] dr={bank_r,stage_id,2'b00};
 assign rd_left=base_l+idx_l;
 assign rd_right=base_r+idx_r;
 assign sample_index={5'd0,position};
 wire [191:0] blended;
 reg [191:0] restored_l,restored_r;
 reg signed [37:0] products[0:5];
 integer c,i;
 generate for(g=0;g<6;g=g+1)begin:blend_pipeline
  always @(posedge clk)begin
   restored_l[g*32+:32]<=$signed(bases[g])+$signed(left_word[g*18+:18]);
   restored_r[g*32+:32]<=$signed(bases[g])+$signed(right_word[g*18+:18]);
   products[g]<=$signed(restored_l[g*32+:32])*$signed({1'b0,7'd32-{1'b0,weight}})
     +$signed(restored_r[g*32+:32])*$signed({1'b0,weight})+38'sd16;
  end
  assign blended[g*32+:32]=products[g]>>>5;
 end endgenerate
 // No reset on RAM. A complete explicit host load and COMMIT is mandatory.
 always @(posedge clk)begin
  if(!rst_n)begin
   committed<=0;awp<=0;wp<=0;bresp<=0;bvalid<=0;rdata<=0;rresp<=0;rvalid<=0;
   read_wait<=0;read_delay<=0;read_plane<=0;read_address<=0;plane<=0;cursor<=0;
   base_mask<=0;desc_mask<=0;stage_count<=0;wa<=0;wd<=0;ws<=0;
   st<=IDLE;error<=0;cmd_done<=0;cmd_ok<=0;sample_valid<=0;sample_data<=0;
   stage_id<=0;last_stage<=0;hand_step<=0;last_step<=0;backwards<=0;partial_valid<=0;
   position<=0;last_position<=0;total<=0;count_l<=0;count_r<=0;base_l<=0;base_r<=0;
   idx_l<=0;idx_r<=0;acc_l<=0;acc_r<=0;last_idx_l<=0;last_idx_r<=0;last_acc_l<=0;last_acc_r<=0;weight<=0;bank_l<=0;bank_r<=0;
   period<=0;countdown<=0;stall_age<=0;final_target<=0;fetch_step<=0;drain<=0;final_frame<=0;finishing<=0;
   speed<=0;acceleration<=0;gripper_only<=0;meta<=0;reverse_meta<=0;
  end else begin
   cmd_done<=0;
   if(awvalid&&awready)begin awp<=1;wa<=awaddr;end
   if(wvalid&&wready)begin wp<=1;wd<=wdata;ws<=wstrb;end
   if(bvalid&&bready)bvalid<=0;
   if(rvalid&&rready)rvalid<=0;
   if(write_go)begin
    awp<=0;wp<=0;bvalid<=1;bresp<=0;
    if(!cfg_ok || ws!=15 || wa[1:0]!=0)begin bresp<=2;error[0]<=1;end
    else if(wa==0 && wd==1)begin committed<=0;base_mask<=0;desc_mask<=0;error<=0;end
    else if(wa==0 && wd==2)begin
     if(base_mask==63 && stage_count>0 && stage_count<=16 && &desc_mask)committed<=1;
     else begin bresp<=2;error[1]<=1;end
    end else if(wa==8'h10 && wd<8)plane<=wd[3:0];
    else if(wa==8'h14 && wd<2048)cursor<=wd[10:0];
    else if(wa==8'h1c && !committed && wd>0 && wd<=16)stage_count<=wd[4:0];
    else if(wa[7]&&!committed&&write_address<2048)begin
     if(plane<6)begin
      if(wd!={{14{wd[17]}},wd[17:0]})begin bresp<=2;error[2]<=1;end
     end else if(plane==6&&write_address<192)begin desc[write_address[7:0]]<=wd;desc_mask[write_address[7:0]]<=1;end
     else if(plane==7&&write_address<6)begin bases[write_address[2:0]]<=wd;base_mask[write_address[2:0]]<=1;end
     else bresp<=2;
    end else bresp<=2;
   end
   if(arvalid&&arready)begin
    rresp<=0;
    if(araddr[1:0]!=0)begin rdata<=0;rresp<=2;rvalid<=1;end
    else if(araddr[7])begin
     if(busy||{1'b0,cursor}+{7'd0,araddr[6:2]}>=2048)begin rdata<=0;rresp<=2;rvalid<=1;end
     else begin read_plane<=plane;read_address<=cursor+araddr[6:2];read_wait<=1;read_delay<=0;end
    end else begin
     rvalid<=1;
     case(araddr)
      0:rdata<=0;
      4:rdata<={29'd0,busy,cfg_ok,committed};
      8:rdata<=error;
      12:rdata<=32'h0000_b001;
      16:rdata<=plane;
      20:rdata<=cursor;
      28:rdata<=stage_count;
      default:begin rdata<=0;rresp<=2;end
     endcase
    end
   end
   if(read_wait)begin
    if(read_delay==2)begin
     read_wait<=0;rvalid<=1;
     if(read_plane<6)rdata<={{14{left_word[read_plane*18+17]}},left_word[read_plane*18+:18]};
     else if(read_plane==6&&read_address<192)rdata<=desc[read_address[7:0]];
     else if(read_plane==7&&read_address<6)rdata<=bases[read_address[2:0]];
     else begin rdata<=0;rresp<=2;end
    end else read_delay<=read_delay+1'b1;
   end
   if(countdown!=0&&st==RUN)countdown<=countdown-1'b1;
   if(sample_valid&&sample_ready)begin sample_valid<=0;drain<=1;end
   if(drain&&delivered)begin
    drain<=0;
    last_stage<=stage_id;last_step<=hand_step;last_position<=position;partial_valid<=1;
    last_idx_l<=idx_l;last_idx_r<=idx_r;last_acc_l<=acc_l;last_acc_r<=acc_r;
    if(final_frame)begin finishing<=1;end
    else if(!backwards)begin
     position<=position+1'b1;
     if({1'b0,acc_l}+count_l-1>=total-1)begin idx_l<=idx_l+1'b1;acc_l<=acc_l+count_l-total;end
     else acc_l<=acc_l+count_l-1'b1;
     if({1'b0,acc_r}+count_r-1>=total-1)begin idx_r<=idx_r+1'b1;acc_r<=acc_r+count_r-total;end
     else acc_r<=acc_r+count_r-1'b1;
     fetch_step<=4;
    end else if(position==0)begin final_frame<=1;fetch_step<=4;end
    else begin
     position<=position-1'b1;
     // Reversing the same integer DDA exactly: floor((p-1)*d/n).
     if(acc_l<count_l-1)begin idx_l<=idx_l-1'b1;acc_l<=acc_l+total-count_l;end
     else acc_l<=acc_l-count_l+1'b1;
     if(acc_r<count_r-1)begin idx_r<=idx_r-1'b1;acc_r<=acc_r+total-count_r;end
     else acc_r<=acc_r-count_r+1'b1;
     fetch_step<=4;
    end
   end
   if(st==FETCH)begin
    fetch_step<=fetch_step+1'b1;
    case(fetch_step)
     0:begin base_l<=desc[dl][10:0];count_l<=desc[dl][26:16];base_r<=desc[dr][10:0];count_r<=desc[dr][26:16];end
     1:begin period<=desc[dl+1];meta<=desc[dl+2];reverse_meta<=desc[dl+3];end
     2:begin
      if(count_l==0||count_r==0||{1'b0,base_l}+count_l>2048||{1'b0,base_r}+count_r>2048||period<MIN_PERIOD||meta!=desc[dr+2]||period!=desc[dr+1]||meta[31:25]!=0||reverse_meta[31:25]!=0||meta[15:0]==0||meta[15:0]>3960||meta[23:16]==0||meta[23:16]>254||reverse_meta[15:0]==0||reverse_meta[15:0]>3960||reverse_meta[23:16]==0||reverse_meta[23:16]>254)begin st<=IDLE;error[3]<=1;cmd_done<=1;cmd_ok<=0;end
      else begin
       total<=count_l>count_r?count_l:count_r;
       speed<=backwards?reverse_meta[15:0]:meta[15:0];
       acceleration<=backwards?reverse_meta[23:16]:meta[23:16];gripper_only<=meta[24];
       idx_l<=0;idx_r<=0;acc_l<=0;acc_r<=0;position<=0;final_frame<=0;finishing<=0;
      end
     end
     3:begin
      if(backwards)begin
       position<=partial_valid&&last_stage==stage_id&&last_step==hand_step?last_position:total-1'b1;
       // Reverse begins from the already delivered frame; replay it harmlessly.
       // Partial DDA state is retained from PAUSE/CLEAR; complete uses endpoints.
       if(partial_valid&&last_stage==stage_id&&last_step==hand_step)begin idx_l<=last_idx_l;idx_r<=last_idx_r;acc_l<=last_acc_l;acc_r<=last_acc_r;end
       else begin idx_l<=count_l-1'b1;idx_r<=count_r-1'b1;acc_l<=0;acc_r<=0;end
       if(meta[24])final_frame<=1;
      end
      st<=RUN;countdown<=0;cmd_done<=1;cmd_ok<=1;fetch_step<=4;
     end
    endcase
   end
   if(st==RUN&&finishing&&countdown==0&&!pending&&!drain)begin st<=DONE;partial_valid<=0;end
   if(st==RUN&&!sample_valid&&!drain&&!finishing)begin
    if(fetch_step!=7)fetch_step<=fetch_step+1'b1;
    else if(countdown==0)begin
     sample_data<=final_frame?final_target:blended;
     sample_valid<=1;countdown<=period-1'b1;
     if(!backwards&&position+1>=total)final_frame<=1;
    end
   end
   if(cmd_valid)begin
    cmd_done<=1;cmd_ok<=1;
    case(cmd_code)
     7:begin
      if(!committed||busy||pending||sample_valid||cmd_stage[15:11]!=0||cmd_stage[10:4]>64||cmd_stage[3:0]>=stage_count||error!=0)cmd_ok<=0;
      else begin
       stage_id<=cmd_stage[3:0];hand_step<=cmd_stage[10:4];backwards<=reverse;final_target<=cmd_target;
       if(cmd_stage[10:4]==64)begin bank_l<=2;bank_r<=2;weight<=0;end
       else if(cmd_stage[8:4]==0)begin bank_l<=cmd_stage[9]?1:0;bank_r<=cmd_stage[9]?1:0;weight<=0;end
       else begin bank_l<=cmd_stage[9]?1:0;bank_r<=cmd_stage[9]?2:1;weight<=cmd_stage[8:4];end
       st<=FETCH;fetch_step<=0;cmd_done<=0;drain<=0;sample_valid<=0;
      end
     end
     2:if(st==RUN)begin st<=PAUSED;sample_valid<=0;end else cmd_ok<=0;
     3:if(st==PAUSED)st<=RUN;else cmd_ok<=0;
     4:if((st==PAUSED||st==DONE||st==IDLE)&&!pending&&!drain)begin st<=IDLE;sample_valid<=0;end else cmd_ok<=0;
     5:begin st<=IDLE;sample_valid<=0;error[4]<=1;end
     6:if(busy||pending||sample_valid)cmd_ok<=0;
     default:cmd_ok<=0;
    endcase
   end
   // Retain the existing 500 ms downstream-stall contract, including a
   // pending frame while paused. Timing waits between samples are excluded.
   if((st==RUN||st==PAUSED)&&((sample_valid&&!sample_ready)||drain)&&!delivered)begin
    if(stall_timeout!=0&&stall_age>=stall_timeout-1'b1)begin
     error[5]<=1;st<=IDLE;sample_valid<=0;drain<=0;
    end else if(stall_age!=32'hffffffff)stall_age<=stall_age+1'b1;
   end else stall_age<=0;
  end
 end
endmodule
