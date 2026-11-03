// Single owned VGA Gray8 frame + exact nearest 128x96 letterbox feed.
// Incoming frames are drained while owned; they never overwrite the ROI source.
// No RAM clearing on reset. Valid is published only after all writes commit.
`timescale 1ns/1ps
module retained_gray_frame #(
    parameter integer CYCLES_PER_MS=100000
)(
    input wire clk,input wire rst_n,
    input wire pixel_valid,output wire pixel_ready,
    input wire [7:0] pixel_data,input wire [9:0] pixel_x,pixel_y,
    input wire pixel_sof,input wire release_frame,
    output reg frame_valid,output reg [31:0] frame_id,output reg published,
    output reg [31:0] frame_timestamp_ms,output reg [31:0] now_ms,
    output reg loc_we,output reg [12:0] loc_word_addr,output reg [31:0] loc_data,
    input wire source_rd_en,input wire [16:0] source_word_addr,output reg [31:0] source_data,
    output reg [31:0] frame_drop_count,format_error_count,
    output wire [2:0] debug_capture_state
);
    localparam WAIT_SOF=0,TOP_PAD=1,ACTIVE=2,BOTTOM_PAD=3,PUBLISH=4,HELD=5;
    reg [2:0] state;
    assign debug_capture_state=state;
    reg [8:0] pad_word;
    reg [9:0] next_x,next_y,sample_x,sample_y;
    reg [6:0] loc_x,loc_y;
    reg [31:0] full_pack,loc_pack,frame_counter;
    reg [31:0] captured_ms;
    reg [$clog2(CYCLES_PER_MS)-1:0] ms_div;
    reg full_we;
    reg [16:0] full_addr;
    reg [31:0] full_data;
    // Explicit 1024x32 banks avoid Vivado padding a 76800-word RAM to 96 RAMB36.
    // 75 banks use exactly 75 RAMB36. Two-clock reads register the 8-bank
    // group selection before a short 10-group mux; no 75-way path to ROI DSP.
    wire [31:0] bank_data[0:74];
    reg [6:0] bank_q;
    reg read_en_q;
    reg [3:0] group_q;
    wire [31:0] group_data[0:9];
    genvar bank;
    generate for(bank=0;bank<75;bank=bank+1)begin:g_source
        (* ram_style="block" *) reg [31:0] mem[0:1023];
        reg [31:0] dout;
        always @(posedge clk)begin
            if(full_we && full_addr[16:10]==bank)mem[full_addr[9:0]]<=full_data;
            if(source_rd_en && source_word_addr[16:10]==bank)dout<=mem[source_word_addr[9:0]];
        end
        assign bank_data[bank]=dout;
    end endgenerate
    genvar group_index,tap_index;
    generate for(group_index=0;group_index<10;group_index=group_index+1)begin:g_read_group
        wire [31:0] inputs[0:7];
        reg [31:0] selected;
        for(tap_index=0;tap_index<8;tap_index=tap_index+1)begin:g_tap
            if(group_index*8+tap_index<75)
                assign inputs[tap_index]=bank_data[group_index*8+tap_index];
            else assign inputs[tap_index]=32'd0;
        end
        always @(posedge clk)if(read_en_q)selected<=inputs[bank_q[2:0]];
        assign group_data[group_index]=selected;
    end endgenerate
    always @(posedge clk)begin
        if(!rst_n)read_en_q<=1'b0;
        else read_en_q<=source_rd_en;
        if(source_rd_en)bank_q<=source_word_addr[16:10];
        if(read_en_q)group_q<=bank_q[6:3];
    end
    always @(*)source_data=(group_q<10)?group_data[group_q]:32'd0;
    assign pixel_ready=(state==ACTIVE || state==HELD ||
        (state==WAIT_SOF && !(pixel_valid && pixel_sof && pixel_x==0 && pixel_y==0)));
    wire fire=pixel_valid && pixel_ready;
    wire coords_ok=(pixel_x==next_x && pixel_y==next_y);
    wire [31:0] packed_full={pixel_data,full_pack[23:0]};
    wire [31:0] packed_loc={pixel_data,loc_pack[23:0]};
    wire [16:0] row_word_base=({7'd0,pixel_y}<<7)+({7'd0,pixel_y}<<5);
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=WAIT_SOF;frame_valid<=0;frame_id<=0;published<=0;
            loc_we<=0;loc_word_addr<=0;loc_data<=0;full_we<=0;full_addr<=0;full_data<=0;
            next_x<=0;next_y<=0;sample_x<=0;sample_y<=0;loc_x<=0;loc_y<=16;
            full_pack<=0;loc_pack<=0;frame_counter<=0;pad_word<=0;
            now_ms<=0;ms_div<=0;captured_ms<=0;frame_timestamp_ms<=0;
            frame_drop_count<=0;format_error_count<=0;
        end else begin
            loc_we<=0;full_we<=0;published<=0;
            if(ms_div==CYCLES_PER_MS-1) begin ms_div<=0;now_ms<=now_ms+1;end
            else ms_div<=ms_div+1;
            case(state)
                WAIT_SOF: if(pixel_valid && pixel_sof && pixel_x==0 && pixel_y==0) begin
                    // Keep the first token until the top padding completes.
                    // pixel_ready is suppressed combinationally for this token below.
                    state<=TOP_PAD;pad_word<=0;next_x<=0;next_y<=0;
                    sample_x<=0;sample_y<=0;loc_x<=0;loc_y<=16;
                    frame_counter<=frame_counter+1;captured_ms<=now_ms;
                end
                TOP_PAD: begin
                    loc_we<=1;loc_word_addr<={4'd0,pad_word};loc_data<=0;
                    if(pad_word==511) begin state<=ACTIVE;pad_word<=0;end
                    else pad_word<=pad_word+1;
                end
                ACTIVE: if(fire) begin
                    if(!coords_ok) begin
                        format_error_count<=format_error_count+1;state<=WAIT_SOF;
                    end else begin
                        case(pixel_x[1:0])
                            0:full_pack[7:0]<=pixel_data;
                            1:full_pack[15:8]<=pixel_data;
                            2:full_pack[23:16]<=pixel_data;
                            3:begin full_we<=1;full_addr<=row_word_base+pixel_x[9:2];full_data<=packed_full;end
                        endcase
                        if(pixel_y==sample_y && pixel_x==sample_x) begin
                            case(loc_x[1:0])
                                0:loc_pack[7:0]<=pixel_data;
                                1:loc_pack[15:8]<=pixel_data;
                                2:loc_pack[23:16]<=pixel_data;
                                3:begin loc_we<=1;loc_word_addr<={1'b0,loc_y,loc_x[6:2]};loc_data<=packed_loc;end
                            endcase
                            sample_x<=sample_x+5;loc_x<=loc_x+1;
                        end
                        if(pixel_x==639) begin
                            next_x<=0;next_y<=next_y+1;
                            if(pixel_y==sample_y) begin sample_y<=sample_y+5;loc_y<=loc_y+1;end
                            sample_x<=0;loc_x<=0;
                            if(pixel_y==479) begin state<=BOTTOM_PAD;pad_word<=0;end
                        end else next_x<=next_x+1;
                    end
                end
                BOTTOM_PAD: begin
                    loc_we<=1;loc_word_addr<=13'd3584+pad_word;loc_data<=0;
                    if(pad_word==511) state<=PUBLISH;
                    else pad_word<=pad_word+1;
                end
                PUBLISH: begin frame_valid<=1;frame_id<=frame_counter;published<=1;frame_timestamp_ms<=captured_ms;state<=HELD;end
                HELD: begin
                    if(fire && pixel_sof) frame_drop_count<=frame_drop_count+1;
                    if(release_frame) begin frame_valid<=0;state<=WAIT_SOF;end
                end
                default:begin frame_valid<=0;state<=WAIT_SOF;end
            endcase
        end
    end
endmodule
