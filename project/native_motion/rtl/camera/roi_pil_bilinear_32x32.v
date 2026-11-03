// Same owned VGA frame, square crop -> PIL-compatible separable BILINEAR.
// Triangle support expands on downsample; coefficients use PIL's Q22 rounding.
// One shared 8x23 multiply, one iterative coefficient divider, 15 KiB scratch.
// Owned VGA source uses two-clock reads; internal RAM reads use one clock.
`timescale 1ns/1ps
module roi_pil_bilinear_32x32 (
    input wire clk,input wire rst_n,input wire start,
    input wire [9:0] desc_x0,desc_y0,desc_side,input wire [31:0] desc_tag,
    input wire frame_valid,input wire [31:0] frame_id,
    output wire busy,output reg done_pulse,error_pulse,
    output reg [31:0] completed_tag,completed_source_frame_id,
    output wire source_rd_en,output wire [16:0] source_word_addr,input wire [31:0] source_data,
    output reg roi_word_we,output reg [7:0] roi_word_addr,output reg [31:0] roi_word_data
);
    localparam IDLE=0,SCAN=1,DIV_LOAD=2,DIV_STEP=3,CO_STORE=4,H_INIT=5,
        H_REQ=6,H_WAIT=7,H_MUL=8,H_ACC=9,V_INIT=10,V_REQ=11,V_WAIT=12,V_MUL=13,V_ACC=14,FLUSH=15,H_CAPTURE=16,H_ADDR=17;
    reg [4:0] state;
    reg [9:0] x0,y0,side;
    reg [31:0] tag;
    reg [4:0] co_dst,dst_x,dst_y;
    reg [8:0] scan_j,src_row,first_src;
    reg [5:0] tap,count_taps,co_count;
    reg [15:0] center,support;
    reg [31:0] weight_total,co_total;
    reg [8:0] co_first;
    (* ram_style="distributed" *) reg [8:0] first [0:31];
    (* ram_style="distributed" *) reg [5:0] lengths [0:31];
    (* ram_style="block" *) reg [22:0] coeff_mem [0:1023];
    reg coeff_we,coeff_rd_en;
    reg [9:0] coeff_waddr,coeff_raddr;
    reg [22:0] coeff_wdata,coeff_rdata;
    (* ram_style="block" *) reg [7:0] horizontal_mem [0:15359];
    reg temp_we,temp_rd_en;
    reg [13:0] temp_waddr,temp_raddr;
    reg [7:0] temp_wdata,temp_rdata;
    reg [31:0] div_num,div_den,div_q;
    reg [32:0] div_rem;
    reg [4:0] div_bit;
    reg [7:0] pixel_reg;
    reg [22:0] coeff_reg;
    reg [31:0] product,sum;
    reg [31:0] pack;
    reg [16:0] source_addr_q;
    reg [1:0] byte_lane_q;
    wire [15:0] scan_center={1'b0,scan_j,6'd0}+16'd32;
    wire [15:0] scan_distance=(scan_center>=center)?scan_center-center:center-scan_center;
    wire [15:0] scan_weight=(scan_distance<support)?support-scan_distance:16'd0;
    wire [9:0] co_src={1'b0,co_first}+tap;
    wire [15:0] co_pixel_center={co_src,6'd0}+16'd32;
    wire [15:0] co_distance=(co_pixel_center>=center)?co_pixel_center-center:center-co_pixel_center;
    wire [15:0] co_weight=support-co_distance;
    wire [32:0] div_trial={div_rem[31:0],div_num[div_bit]};
    wire [31:0] accumulated=sum+product;
    wire [9:0] clipped_sum=accumulated[31:22];
    wire [7:0] value=(clipped_sum>255)?8'd255:clipped_sum[7:0];
    wire [9:0] read_x=x0+{1'b0,first[dst_x]}+tap;
    wire [9:0] read_y=y0+{1'b0,src_row};
    wire [16:0] read_row_base=({7'd0,read_y}<<7)+({7'd0,read_y}<<5);
    assign source_rd_en=(state==H_REQ);
    assign source_word_addr=source_addr_q;
    assign busy=state!=IDLE;
    always @(posedge clk) begin
        if(coeff_we) coeff_mem[coeff_waddr]<=coeff_wdata;
        if(coeff_rd_en) coeff_rdata<=coeff_mem[coeff_raddr];
        if(temp_we) horizontal_mem[temp_waddr]<=temp_wdata;
        if(temp_rd_en) temp_rdata<=horizontal_mem[temp_raddr];
    end
    always @(*) begin
        coeff_rd_en=1'b0;coeff_raddr=10'd0;
        temp_rd_en=1'b0;temp_raddr=14'd0;
        if(state==H_REQ) begin coeff_rd_en=1'b1;coeff_raddr={dst_x,5'd0}+tap;end
        if(state==V_REQ) begin
            coeff_rd_en=1'b1;coeff_raddr={dst_y,5'd0}+tap;
            temp_rd_en=1'b1;temp_raddr=({5'd0,first[dst_y]}+tap)*14'd32+dst_x;
        end
    end
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=IDLE;x0<=0;y0<=0;side<=1;tag<=0;co_dst<=0;dst_x<=0;dst_y<=0;
            scan_j<=0;src_row<=0;first_src<=0;tap<=0;count_taps<=0;co_count<=0;
            center<=0;support<=64;weight_total<=0;co_total<=0;co_first<=0;
            coeff_we<=0;coeff_waddr<=0;coeff_wdata<=0;
            temp_we<=0;temp_waddr<=0;temp_wdata<=0;
            div_num<=0;div_den<=1;div_q<=0;div_rem<=0;div_bit<=31;
            pixel_reg<=0;coeff_reg<=0;product<=0;sum<=0;pack<=0;
            done_pulse<=0;error_pulse<=0;completed_tag<=0;completed_source_frame_id<=0;
            roi_word_we<=0;roi_word_addr<=0;roi_word_data<=0;
        end else begin
            coeff_we<=0;temp_we<=0;roi_word_we<=0;done_pulse<=0;error_pulse<=0;
            if(state==H_MUL || state==V_MUL) product<=pixel_reg*coeff_reg;
            case(state)
                IDLE: if(start) begin
                    if(!frame_valid || desc_tag!=frame_id || desc_side<1 || desc_side>480 ||
                       ({1'b0,desc_x0}+{1'b0,desc_side}>640) ||
                       ({1'b0,desc_y0}+{1'b0,desc_side}>480)) error_pulse<=1;
                    else begin
                        x0<=desc_x0;y0<=desc_y0;side<=desc_side;tag<=desc_tag;
                        co_dst<=0;scan_j<=0;count_taps<=0;first_src<=0;weight_total<=0;
                        center<={6'd0,desc_side};support<=(desc_side>32)?{5'd0,desc_side,1'b0}:16'd64;
                        state<=SCAN;
                    end
                end
                SCAN: begin
                    if(scan_weight!=0) begin
                        if(count_taps==0) first_src<=scan_j;
                        count_taps<=count_taps+1;weight_total<=weight_total+scan_weight;
                    end
                    if({1'b0,scan_j}+10'd1==side) begin
                        first[co_dst]<=(count_taps==0)?scan_j:first_src;
                        lengths[co_dst]<=count_taps+((scan_weight!=0)?6'd1:6'd0);
                        co_first<=(count_taps==0)?scan_j:first_src;
                        co_count<=count_taps+((scan_weight!=0)?6'd1:6'd0);
                        co_total<=weight_total+scan_weight;tap<=0;state<=DIV_LOAD;
                    end else scan_j<=scan_j+1;
                end
                DIV_LOAD: begin
                    div_num<=({16'd0,co_weight}<<22)+(co_total>>1);
                    div_den<=co_total;div_q<=0;div_rem<=0;div_bit<=31;state<=DIV_STEP;
                end
                DIV_STEP: begin
                    if(div_trial>={1'b0,div_den}) begin div_rem<=div_trial-div_den;div_q[div_bit]<=1'b1;end
                    else div_rem<=div_trial;
                    if(div_bit==0) state<=CO_STORE;
                    else div_bit<=div_bit-1;
                end
                CO_STORE: begin
                    coeff_we<=1;coeff_waddr<={co_dst,5'd0}+tap;coeff_wdata<=div_q[22:0];
                    if(tap+1<co_count) begin tap<=tap+1;state<=DIV_LOAD;end
                    else if(co_dst!=31) begin
                        co_dst<=co_dst+1;center<=center+{5'd0,side,1'b0};scan_j<=0;
                        first_src<=0;count_taps<=0;weight_total<=0;state<=SCAN;
                    end else state<=H_INIT;
                end
                H_INIT:begin src_row<=0;dst_x<=0;tap<=0;sum<=32'd2097152;state<=H_ADDR;end
                H_ADDR:begin source_addr_q<=read_row_base+read_x[9:2];byte_lane_q<=read_x[1:0];state<=H_REQ;end
                H_REQ:state<=H_WAIT;
                H_WAIT:state<=H_CAPTURE;
                H_CAPTURE:begin pixel_reg<=source_data>>(8*byte_lane_q);coeff_reg<=coeff_rdata;state<=H_MUL;end
                H_MUL:state<=H_ACC;
                H_ACC:begin
                    if(tap+1<lengths[dst_x]) begin sum<=accumulated;tap<=tap+1;state<=H_ADDR;end
                    else begin
                        temp_we<=1;temp_waddr<={src_row,dst_x};temp_wdata<=value;
                        sum<=32'd2097152;tap<=0;
                        if(dst_x!=31) begin dst_x<=dst_x+1;state<=H_ADDR;end
                        else if({1'b0,src_row}+10'd1<side) begin src_row<=src_row+1;dst_x<=0;state<=H_ADDR;end
                        else state<=V_INIT;
                    end
                end
                V_INIT:begin dst_x<=0;dst_y<=0;tap<=0;sum<=32'd2097152;pack<=0;state<=V_REQ;end
                V_REQ:state<=V_WAIT;
                V_WAIT:begin pixel_reg<=temp_rdata;coeff_reg<=coeff_rdata;state<=V_MUL;end
                V_MUL:state<=V_ACC;
                V_ACC:begin
                    if(tap+1<lengths[dst_y]) begin sum<=accumulated;tap<=tap+1;state<=V_REQ;end
                    else begin
                        case(dst_x[1:0])
                            0:pack[7:0]<=value;1:pack[15:8]<=value;2:pack[23:16]<=value;
                            3:begin roi_word_we<=1;roi_word_addr<={dst_y,dst_x[4:2]};roi_word_data<={value,pack[23:0]};end
                        endcase
                        sum<=32'd2097152;tap<=0;
                        if(dst_x!=31) begin dst_x<=dst_x+1;state<=V_REQ;end
                        else if(dst_y!=31) begin dst_y<=dst_y+1;dst_x<=0;state<=V_REQ;end
                        else state<=FLUSH;
                    end
                end
                FLUSH:begin completed_tag<=tag;completed_source_frame_id<=tag;done_pulse<=1;state<=IDLE;end
                default:begin error_pulse<=1;state<=IDLE;end
            endcase
        end
    end
endmodule
