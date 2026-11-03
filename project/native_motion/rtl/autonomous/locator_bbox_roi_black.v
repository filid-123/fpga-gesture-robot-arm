// Frozen v0.4 source geometry + timestamp-based fixed-point PC stabilizer.
// Coordinates are Q16.16 source pixels; dt is acquisition time, not frame count.
// exp(-dt/tau) is a 1 ms / Q16 table. One shared signed 32x32 multiplier.
`timescale 1ns/1ps
module locator_bbox_roi_black #(
    parameter integer USE_EMA=1,
    parameter ALPHA_FILE="geometry_alpha_q16.mem"
)(
    input wire clk,input wire rst_n,input wire start,
    input wire [31:0] timestamp_ms,input wire [7:0] cell_index,
    input wire signed [31:0] confidence_i32,dx_i32,dy_i32,width_i32,height_i32,
    output wire busy,output reg done,detected,
    output reg [9:0] roi_x0,roi_y0,roi_side,
    output reg [8:0] raw_box_x0,raw_box_y0,raw_box_x1,raw_box_y1,
    output reg [8:0] ema_box_x0,ema_box_y0,ema_box_x1,ema_box_y1
);
    `include "black_geometry_constants.vh"
    localparam IDLE=0,RAW_MUL=1,RAW_CAPTURE=2,FORM=3,CLAMP=4,SOURCE=5,GEOM=6,
        FILTER=7,DIFF=8,SQ_W=9,SQ_H=10,SQ_CHANGE=11,SQ_PENDING=12,DECIDE=13,
        ALPHA_REQ=14,EMA_MUL=15,EMA_ADD=16,EFFECT=17,INTBOX=18,SIDE_LOAD=19,
        SIDE_DIV=20,SIDE_CLAMP=21,ORIGIN=22,OUTPUT=23,SCALE_PARTS=24,SCALE_SUM=25,COMPARE=26,MUL_WAIT=27,
        DIFF_ABS=28,DIFF_COMPARE=29;
    reg [4:0] state;
    reg [4:0] mul_return;
    reg [1:0] index;
    reg [7:0] peak_cell;
    reg signed [31:0] conf,raw[0:3];
    reg signed [63:0] decoded[0:3];
    reg signed [63:0] cx,cy,hw,hh;
    reg [31:0] loc[0:3],src[0:3],effective[0:3];
    reg signed [31:0] observation[0:3],ema[0:3],pending[0:3];
    reg ema_valid,time_valid,pending_valid,since_valid,use_fast;
    reg [31:0] ts,dt,last_time,last_accepted,pending_time,pending_since;
    reg [31:0] max_delta,max_pending_delta;
    reg signed [31:0] delta_q,pending_delta_q;
    reg [31:0] abs_delta_q,abs_pending_q;
    reg [63:0] diag_sq,change_sq;
    reg [63:0] pending_part,pending_tail,change_part,pending_scaled,change_scaled;
    reg jump_large,pending_agrees,pending_fresh,pending_wait_expired;
    reg signed [31:0] mul_a,mul_b;
    reg mul_en;
    reg mul_en_q;
    reg signed [31:0] mul_a_q,mul_b_q;
    reg signed [63:0] mul_result;
    (* rom_style="block" *) reg [31:0] alpha_mem [0:255];
    reg [31:0] alpha_data;
    wire [7:0] alpha_addr=(dt>255)?8'd255:dt[7:0];
    wire [15:0] alpha=use_fast?alpha_data[31:16]:alpha_data[15:0];
    reg [9:0] ix0,iy0,ix1,iy1;
    reg [15:0] side_num,side_q;
    reg [5:0] side_rem;
    reg [3:0] side_bit;
    wire [6:0] side_trial={side_rem,side_num[side_bit]};
    wire signed [31:0] obs_delta=observation[index]-ema[index];
    wire signed [31:0] pending_delta=observation[index]-pending[index];
    wire [63:0] normalized_diag=(diag_sq<64'd4398046511104)?64'd4398046511104:diag_sq;
    wire [63:0] change25=(change_sq<<4)+(change_sq<<3)+change_sq;
    wire [63:0] pending100=($unsigned(mul_result)<<6)+($unsigned(mul_result)<<5)+($unsigned(mul_result)<<2);
    wire [31:0] dt_live=timestamp_ms-last_time;
    wire [31:0] age_pending=ts-pending_time;
    wire [31:0] age_since=since_valid?(ts-pending_since):32'd0;
    wire [10:0] box_w={1'b0,ix1}-{1'b0,ix0};
    wire [10:0] box_h={1'b0,iy1}-{1'b0,iy0};
    wire [10:0] max_side=(box_w>box_h)?box_w:box_h;
    wire signed [11:0] origin_x=$signed({2'd0,ix0})+$signed({2'd0,ix1})-$signed({2'd0,roi_side});
    wire signed [11:0] origin_y=$signed({2'd0,iy0})+$signed({2'd0,iy1})-$signed({2'd0,roi_side});
    initial $readmemh(ALPHA_FILE,alpha_mem);
    always @(posedge clk) begin
        mul_en_q<=rst_n && mul_en;
        if(mul_en)begin mul_a_q<=mul_a;mul_b_q<=mul_b;end
        if(mul_en_q)mul_result<=$signed(mul_a_q)*$signed(mul_b_q);
        if(state==ALPHA_REQ) alpha_data<=alpha_mem[alpha_addr];
    end
    assign busy=state!=IDLE;
    function [31:0] clipq;
        input signed [63:0] x;input [31:0] maximum;
        begin if(x<0) clipq=0;else if(x>$signed({32'd0,maximum})) clipq=maximum;else clipq=x[31:0];end
    endfunction
    function [9:0] roundq;
        input [31:0] x;reg [15:0] whole;reg increment;
        begin whole=x[31:16];increment=(x[15:0]>32768)||((x[15:0]==32768)&&whole[0]);roundq=whole+increment;end
    endfunction
    function [8:0] div5;
        input [10:0] x;reg [21:0] scaled;
        // Exact for the entire unsigned 11-bit input domain (0..2047).
        // Reciprocal error <0.15, below the 0.2 gap to the next integer.
        begin scaled=x*11'd1639;div5=scaled[21:13];end
    endfunction
    function [9:0] round_half_clamp;
        input signed [11:0] numerator;input [9:0] maximum;reg [11:0] q;
        begin
            if(numerator<0) round_half_clamp=0;
            else begin q=(numerator>>1)+(numerator[0]&&numerator[1]);
                round_half_clamp=(q>maximum)?maximum:q[9:0];end
        end
    endfunction
    wire [9:0] rounded_left=(roundq(effective[0])>639)?10'd639:roundq(effective[0]);
    wire [9:0] rounded_top=(roundq(effective[1])>479)?10'd479:roundq(effective[1]);
    wire [9:0] rounded_right=(roundq(effective[2])<rounded_left+1)?rounded_left+1:roundq(effective[2]);
    wire [9:0] rounded_bottom=(roundq(effective[3])<rounded_top+1)?rounded_top+1:roundq(effective[3]);
    always @(*) begin
        mul_en=1'b0;mul_a=0;mul_b=0;
        case(state)
            RAW_MUL:begin mul_en=1'b1;mul_a=raw[index];case(index)
                0:mul_b=DX_Q30;1:mul_b=DY_Q30;2:mul_b=HALF_WIDTH_Q30;3:mul_b=HALF_HEIGHT_Q30;endcase end
            SQ_W:begin mul_en=1'b1;mul_a=ema[2];mul_b=ema[2];end
            SQ_H:begin mul_en=1'b1;mul_a=ema[3];mul_b=ema[3];end
            SQ_CHANGE:begin mul_en=1'b1;mul_a=max_delta;mul_b=max_delta;end
            SQ_PENDING:begin mul_en=1'b1;mul_a=max_pending_delta;mul_b=max_pending_delta;end
            EMA_MUL:begin mul_en=1'b1;mul_a=obs_delta;mul_b={16'd0,alpha};end
            default:begin end
        endcase
    end
    integer k;
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=IDLE;index<=0;peak_cell<=0;conf<=0;cx<=0;cy<=0;hw<=0;hh<=0;
            ema_valid<=0;time_valid<=0;pending_valid<=0;since_valid<=0;use_fast<=0;
            ts<=0;dt<=0;last_time<=0;last_accepted<=0;pending_time<=0;pending_since<=0;
            max_delta<=0;max_pending_delta<=0;diag_sq<=0;change_sq<=0;
            ix0<=0;iy0<=0;ix1<=1;iy1<=1;side_num<=0;side_q<=0;side_rem<=0;side_bit<=15;
            done<=0;detected<=0;roi_x0<=0;roi_y0<=0;roi_side<=1;
            raw_box_x0<=0;raw_box_y0<=0;raw_box_x1<=0;raw_box_y1<=0;
            ema_box_x0<=0;ema_box_y0<=0;ema_box_x1<=0;ema_box_y1<=0;
            for(k=0;k<4;k=k+1) begin raw[k]<=0;decoded[k]<=0;loc[k]<=0;src[k]<=0;effective[k]<=0;end
        end else begin
            done<=0;
            case(state)
                IDLE:if(start) begin
                    raw[0]<=dx_i32;raw[1]<=dy_i32;raw[2]<=width_i32;raw[3]<=height_i32;
                    peak_cell<=cell_index;conf<=confidence_i32;ts<=timestamp_ms;
                    dt<=time_valid?dt_live:32'd0;index<=0;detected<=0;state<=RAW_MUL;
                end
                RAW_MUL:begin mul_return<=RAW_CAPTURE;state<=MUL_WAIT;end
                MUL_WAIT:state<=mul_return;
                RAW_CAPTURE:begin decoded[index]<=mul_result;
                    if(index==3) state<=FORM;else begin index<=index+1;state<=RAW_MUL;end end
                FORM:begin
                    cx<=$signed({36'd0,peak_cell[3:0],19'd0})+64'sd262144+($signed(decoded[0])>>>14);
                    cy<=$signed({36'd0,peak_cell[7:4],19'd0})+64'sd262144+($signed(decoded[1])>>>14);
                    hw<=$signed({32'd0,clipq($signed(decoded[2])>>>14,32'd4194304)});
                    hh<=$signed({32'd0,clipq($signed(decoded[3])>>>14,32'd4194304)});
                    state<=CLAMP;
                end
                CLAMP:begin
                    loc[0]<=clipq(cx-hw,32'd8388608);loc[1]<=clipq(cy-hh,32'd8388608);
                    loc[2]<=clipq(cx+hw,32'd8388608);loc[3]<=clipq(cy+hh,32'd8388608);state<=SOURCE;
                end
                SOURCE:begin
                    src[0]<=loc[0]*32'd5;src[2]<=loc[2]*32'd5;
                    src[1]<=clipq(($signed({32'd0,loc[1]})-64'sd1048576)*64'sd5,32'd31457280);
                    src[3]<=clipq(($signed({32'd0,loc[3]})-64'sd1048576)*64'sd5,32'd31457280);
                    raw_box_x0<=roundq(loc[0]);raw_box_y0<=roundq(loc[1]);
                    raw_box_x1<=roundq(loc[2]);raw_box_y1<=roundq(loc[3]);state<=GEOM;
                end
                GEOM:begin
                    last_time<=ts;time_valid<=1;
                    if(conf < -32'sd11748 || src[2]<=src[0] || src[3]<=src[1]) begin
                        detected<=0;roi_x0<=0;roi_y0<=0;roi_side<=1;pending_valid<=0;since_valid<=0;
                        if(src[2]<=src[0] || src[3]<=src[1] || dt>250 || ts-last_accepted>200) ema_valid<=0;
                        state<=OUTPUT;
                    end else begin
                        detected<=1;
                        observation[0]<=(src[0]+src[2])>>1;observation[1]<=(src[1]+src[3])>>1;
                        observation[2]<=src[2]-src[0];observation[3]<=src[3]-src[1];
                        if(USE_EMA==0) begin for(k=0;k<4;k=k+1) effective[k]<=src[k];state<=INTBOX;end
                        else state<=FILTER;
                    end
                end
                FILTER:begin
                    if(!ema_valid || dt>250) begin
                        for(k=0;k<4;k=k+1) ema[k]<=observation[k];
                        ema_valid<=1;pending_valid<=0;since_valid<=0;last_accepted<=ts;state<=EFFECT;
                    end else begin index<=0;max_delta<=0;max_pending_delta<=0;state<=DIFF;end
                end
                DIFF:begin
                    // Separate subtraction, absolute value and max comparison.
                    // The previous combined path ended at a 32-bit register CE
                    // and left only 43 ps of full-design setup margin.
                    delta_q<=obs_delta;pending_delta_q<=pending_delta;state<=DIFF_ABS;
                end
                DIFF_ABS:begin
                    abs_delta_q<=delta_q[31]?-delta_q:delta_q;
                    abs_pending_q<=pending_delta_q[31]?-pending_delta_q:pending_delta_q;
                    state<=DIFF_COMPARE;
                end
                DIFF_COMPARE:begin
                    if(abs_delta_q>max_delta) max_delta<=abs_delta_q;
                    if(abs_pending_q>max_pending_delta) max_pending_delta<=abs_pending_q;
                    if(index==3) state<=SQ_W;else begin index<=index+1;state<=DIFF;end
                end
                SQ_W:begin mul_return<=SQ_H;state<=MUL_WAIT;end
                SQ_H:begin diag_sq<=mul_result;mul_return<=SQ_CHANGE;state<=MUL_WAIT;end
                SQ_CHANGE:begin diag_sq<=diag_sq+$unsigned(mul_result);mul_return<=SQ_PENDING;state<=MUL_WAIT;end
                SQ_PENDING:begin change_sq<=mul_result;mul_return<=SCALE_PARTS;state<=MUL_WAIT;end
                SCALE_PARTS:begin
                    pending_part<=($unsigned(mul_result)<<6)+($unsigned(mul_result)<<5);
                    pending_tail<=($unsigned(mul_result)<<2);
                    change_part<=(change_sq<<4)+(change_sq<<3);
                    state<=SCALE_SUM;
                end
                SCALE_SUM:begin
                    pending_scaled<=pending_part+pending_tail;
                    change_scaled<=change_part+change_sq;
                    state<=COMPARE;
                end
                COMPARE:begin
                    jump_large<=change_scaled>normalized_diag;
                    pending_agrees<=pending_scaled<=normalized_diag;
                    pending_fresh<=age_pending<=200;
                    pending_wait_expired<=age_since+dt>=200;
                    state<=DECIDE;
                end
                DECIDE:begin
                    if(jump_large &&
                       !(pending_valid && pending_fresh && pending_agrees) && !pending_wait_expired) begin
                        for(k=0;k<4;k=k+1) pending[k]<=observation[k];
                        pending_valid<=1;pending_time<=ts;
                        if(!since_valid) begin pending_since<=ts;since_valid<=1;end
                        last_accepted<=ts;state<=EFFECT;
                    end else begin
                        use_fast<=jump_large;pending_valid<=0;since_valid<=0;index<=0;state<=ALPHA_REQ;
                    end
                end
                ALPHA_REQ:state<=EMA_MUL;
                EMA_MUL:begin mul_return<=EMA_ADD;state<=MUL_WAIT;end
                EMA_ADD:begin
                    ema[index]<=ema[index]+(($signed(mul_result)+64'sd32768)>>>16);
                    if(index==3) begin last_accepted<=ts;state<=EFFECT;end
                    else begin index<=index+1;state<=EMA_MUL;end
                end
                EFFECT:begin
                    effective[0]<=clipq($signed(ema[0])-($signed(ema[2])>>>1),32'd41943040);
                    effective[1]<=clipq($signed(ema[1])-($signed(ema[3])>>>1),32'd31457280);
                    effective[2]<=clipq($signed(ema[0])+($signed(ema[2])>>>1),32'd41943040);
                    effective[3]<=clipq($signed(ema[1])+($signed(ema[3])>>>1),32'd31457280);state<=INTBOX;
                end
                INTBOX:begin ix0<=rounded_left;iy0<=rounded_top;ix1<=rounded_right;iy1<=rounded_bottom;state<=SIDE_LOAD;end
                SIDE_LOAD:begin
                    side_num<=max_side*16'd34+16'd12;side_q<=0;side_rem<=0;side_bit<=15;state<=SIDE_DIV;
                end
                SIDE_DIV:begin
                    if(side_trial>=25) begin side_rem<=side_trial-25;side_q[side_bit]<=1'b1;end
                    else side_rem<=side_trial;
                    if(side_bit==0) state<=SIDE_CLAMP;else side_bit<=side_bit-1;
                end
                SIDE_CLAMP:begin roi_side<=(side_q>480)?10'd480:((side_q==0)?10'd1:side_q[9:0]);state<=ORIGIN;end
                ORIGIN:begin
                    roi_x0<=round_half_clamp(origin_x,10'd640-roi_side);
                    roi_y0<=round_half_clamp(origin_y,10'd480-roi_side);
                    ema_box_x0<=div5({1'b0,ix0}+11'd2);ema_box_x1<=div5({1'b0,ix1}+11'd2);
                    ema_box_y0<=div5({1'b0,iy0}+11'd82);ema_box_y1<=div5({1'b0,iy1}+11'd82);state<=OUTPUT;
                end
                OUTPUT:begin done<=1;state<=IDLE;end
                default:begin detected<=0;state<=IDLE;end
            endcase
        end
    end
endmodule
