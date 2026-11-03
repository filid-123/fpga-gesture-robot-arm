// Acquisition-time confirmation, unique frames, freshness and logit-margin gate.
// Tasks still require their FSM state, spatial PALM window and neutral rearm.
// No softmax; margin is raw/un-calibrated and defaults to an inactive gate.
`timescale 1ns/1ps
module gesture_time_filter #(
    parameter integer OBJECT_HOLD_MS=100,PALM_HOLD_MS=200,FIST_HOLD_MS=80,
    parameter integer NEUTRAL_HOLD_MS=250,MIN_FRAMES=2,
    parameter integer OBJECT_MIN_FRAMES=MIN_FRAMES,PALM_MIN_FRAMES=MIN_FRAMES,
    parameter integer FIST_MIN_FRAMES=MIN_FRAMES,
    parameter integer MAX_GAP_MS=250,MAX_FRAME_AGE_MS=250,
    parameter [15:0] MARGIN_MIN=16'd0
)(
    input wire clk,input wire rst_n,
    input wire [31:0] now_ms,frame_timestamp_ms,frame_id,
    input wire candidate_valid,input wire [2:0] candidate_class,
    input wire [15:0] candidate_margin,
    output reg [2:0] output_class,output reg output_changed,
    output wire output_valid,output wire [2:0] gated_class,output wire [3:0] leds
);
    reg seen,qualified;
    reg [31:0] last_id,last_ts,first_ts;
    reg [2:0] pending_class;
    reg [7:0] count;
    reg [31:0] required_ms;
    integer required_frames;
    wire gated=(candidate_class>=1 && candidate_class<=5 && candidate_margin<MARGIN_MIN);
    assign gated_class=gated?3'd6:candidate_class;
    wire unique_frame=!seen || frame_id!=last_id;
    wire [31:0] frame_age=now_ms-frame_timestamp_ms;
    wire [31:0] gap=frame_timestamp_ms-last_ts;
    wire [31:0] elapsed=frame_timestamp_ms-first_ts;
    assign output_valid=qualified && seen && (now_ms-last_ts<=MAX_FRAME_AGE_MS);
    assign leds=output_valid?((output_class==7)?4'b0000:{1'b1,output_class}):4'b0000;
    always @(*) begin
        required_frames=MIN_FRAMES;
        case(gated_class)
            1,2,3:begin required_ms=OBJECT_HOLD_MS;required_frames=OBJECT_MIN_FRAMES;end
            4:begin required_ms=PALM_HOLD_MS;required_frames=PALM_MIN_FRAMES;end
            5:begin required_ms=FIST_HOLD_MS;required_frames=FIST_MIN_FRAMES;end
            default:required_ms=NEUTRAL_HOLD_MS;
        endcase
    end
    always @(posedge clk) begin
        if(!rst_n) begin
            output_class<=7;output_changed<=0;seen<=0;qualified<=0;
            last_id<=0;last_ts<=0;first_ts<=0;pending_class<=7;count<=0;
        end else begin
            output_changed<=0;
            if(candidate_valid && unique_frame) begin
                seen<=1;last_id<=frame_id;last_ts<=frame_timestamp_ms;
                if(frame_age>MAX_FRAME_AGE_MS) begin
                    qualified<=0;count<=0;pending_class<=7;first_ts<=frame_timestamp_ms;
                end else if(!seen || gap==0 || gap>MAX_GAP_MS || gated_class!=pending_class || count==0) begin
                    qualified<=0;pending_class<=gated_class;first_ts<=frame_timestamp_ms;count<=1;
                end else begin
                    if(count!=255) count<=count+1;
                    if(elapsed>=required_ms && {1'b0,count}+9'd1>=required_frames) begin
                        qualified<=1;output_class<=gated_class;
                        output_changed<=(output_class!=gated_class);
                    end
                end
            end
        end
    end
endmodule
