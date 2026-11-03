// ============================================================================
// Block Name : s5_vision_event_adapter
// Description: Phase 3 S5 adapter from the UNCHANGED S3 seven-class vision top
//              (gesture_autonomous_top_v5_7c, top-level ports only - no
//              hierarchical reference) to the S4 vision event inputs
//              (vis_valid, vis_stable_class, vis_class_changed,
//              vis_palm_window_ok), plus a small AXI4-Lite window
//              (ABI 0x0000_3501, proposed 0x43C6_0000) for the delivery-window
//              configuration and vision telemetry.
//
//   Inputs used (all registered in the S3 clk_100mhz domain):
//     frame_valid     = debug_result_valid     one pulse per processed frame
//     frame_class     = debug_candidate_class  class of that frame (7 = none)
//     frame_detected  = debug_result_detected  Locator box of that frame valid
//     box_raw/box_ema = debug_raw_* / debug_ema_* (128x128 Locator letterbox)
//     frame_id        = debug_result_frame_id
//     stable_class    = debug_stable_class     S3 confirm-filter output
//     leds            = 4'b1111 <=> S3 fatal (camera init error / FIFO
//                       overflow; no class maps to 1111)
//   The S3 scheduler registers the box of frame k at bbox done and emits the
//   class of frame k with frame_valid before the next Locator run starts, so
//   at every frame_valid pulse the box ports belong to that frame (when
//   frame_detected = 1).
//
//   vis_valid  = the last frame is younger than STALE_CYCLES AND NOT fatal
//                AND "agree": since reset at least one frame's own class was
//                equal to the stable class.  The S3 filter starts at
//                NO_DETECTION as a reset VALUE, not an observation; without
//                "agree" a gesture already held at start-up would see a
//                valid NO_DETECTION, re-arm S4 and select at once.
//                BACKGROUND and NO_DETECTION that were actually observed are
//                valid (they re-arm the S4 selection); reset, fatal and
//                missing frames are not.
//   vis_class_changed = one pulse when the stable class differs from the last
//                class reported while valid (so a change that happened while
//                invalid is reported once when valid returns; no pulse is
//                ever produced while invalid).
//   vis_palm_window_ok = window enabled AND vis_valid AND the last
//                STABLE_FRAMES consecutive frames were each: detected,
//                classified PALM_READY, box fully inside the configured
//                window, and every box corner moved <= MAX_MOVE from the
//                previous in-window frame.  Reset / default: disabled, so
//                PALM_READY delivery is refused until the PS writes a
//                calibrated window.  Any configuration write, stale data or
//                fatal clears the frame count.
//   Box edge rule: the PS configuration tool keeps the window away from the
//   letterbox content border, so "box inside window" also means "box not
//   touching the image edge" - no second edge comparator in hardware.
// Latency: stage 0 registers the S3 ports, stage 1 computes the frame
//   predicates, stage 2 updates state and the registered outputs.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk = S3 clk_100mhz = S4 s_axi_aclk (the same net by
//   construction in phase3_s5_vision_motion_top; no CDC here)
// Truth boundary: source candidate; supplementary Icarus run only.
// ============================================================================

`timescale 1ns / 1ps

module s5_vision_event_adapter #(
    parameter integer USE_QUALIFIED_INPUT=0,
    parameter integer CAMERA_DIAGNOSTICS=0,
    parameter integer PHASE2_FRONTEND=0,
    parameter integer MEASURE=0,
    parameter integer CAMERA_CONTROL=0
)(
    input wire [31:0] measure_loc,measure_cls,measure_total,measure_collisions,measure_cycle,
    input wire [7:0] measure_write_index,
    input wire [255:0] measure_record,
    output reg [7:0] measure_read_index,
    output reg measure_freeze,
    input  wire         clk,
    input  wire         rst_n,
    // S3 top-level outputs
    input  wire         frame_valid,
    input  wire [2:0]   frame_class,
    input  wire         frame_detected,
    input  wire [31:0]  frame_id,
    input  wire [8:0]   raw_x0, raw_y0, raw_x1, raw_y1,
    input  wire [8:0]   ema_x0, ema_y0, ema_x1, ema_y1,
    input  wire [2:0]   stable_class,
    input  wire [3:0]   leds,
    input wire qualified_valid,
    input wire [31:0] acquisition_ms,now_ms,
    input wire [15:0] result_margin,
    input wire [2:0] model_class,
    input wire signed [31:0] confidence_raw,
    input wire [31:0] camera_status,frame_drop_count,format_error_count,
    output reg snapshot_enable,
    output reg snapshot_rd_en,
    output reg [16:0] snapshot_word_addr,
    input wire snapshot_ready,
    input wire [31:0] snapshot_frame_id,snapshot_timestamp_ms,snapshot_data,
    // Optional calibration port: one existing SCCB master, same clock domain.
    output reg camera_cmd_start,
    output wire camera_cmd_read,
    output wire [15:0] camera_cmd_addr,
    output wire [7:0] camera_cmd_data,
    input wire camera_cmd_ready,camera_cmd_busy,camera_cmd_done,camera_cmd_error,
    input wire [7:0] sensor_read_data,
    // S4 vision event inputs
    output reg          vis_valid,
    output reg  [2:0]   vis_stable_class,
    output reg          vis_class_changed,
    output reg          vis_palm_window_ok,
    // AXI4-Lite slave
    input  wire [11:0]  s_awaddr,
    input  wire         s_awvalid,
    output reg          s_awready,
    input  wire [31:0]  s_wdata,
    input  wire [3:0]   s_wstrb,
    input  wire         s_wvalid,
    output reg          s_wready,
    output reg  [1:0]   s_bresp,
    output reg          s_bvalid,
    input  wire         s_bready,
    input  wire [11:0]  s_araddr,
    input  wire         s_arvalid,
    output reg          s_arready,
    output reg  [31:0]  s_rdata,
    output reg  [1:0]   s_rresp,
    output reg          s_rvalid,
    input  wire         s_rready
);

    localparam [31:0] ABI = (MEASURE!=0)?32'h0000_3506:(CAMERA_CONTROL!=0)?32'h0000_3505:((PHASE2_FRONTEND!=0)?32'h0000_3504:((CAMERA_DIAGNOSTICS!=0)?32'h0000_3503:
        ((USE_QUALIFIED_INPUT!=0)?32'h0000_3502:32'h0000_3501)));
    localparam integer SNAPSHOT_WORDS=(PHASE2_FRONTEND!=0)?4096:76800;
    localparam [2:0]  PALM_READY = 3'd4, NO_DETECTION = 3'd7;
    localparam [1:0]  OKAY = 2'b00, SLVERR = 2'b10;

    // ---------------------------------------------------------------- configuration
    reg         cfg_enable, cfg_ema;
    reg  [3:0]  cfg_frames;
    reg  [8:0]  cfg_x0, cfg_x1, cfg_y0, cfg_y1, cfg_move;
    reg  [31:0] cfg_stale;
    reg         cfg_touch;                         // pulse: a window register was written
    reg         cnt_clear;                         // pulse: CONTROL.CLEAR_COUNTERS

    // ---------------------------------------------------------------- stage 0: S3 ports
    reg         s0_pulse, s0_det, s0_fatal;
    reg  [2:0]  s0_class, s0_stable;
    reg  [8:0]  s0_x0, s0_y0, s0_x1, s0_y1;
    reg  [31:0] s0_id;
    reg [31:0] s0_acq_ms,s0_result_ms,s0_conf;
    reg [15:0] s0_margin;
    reg [2:0] s0_model;
    reg [31:0] last_acq_ms,last_result_ms,last_conf;
    reg [15:0] last_margin;
    reg [2:0] last_model;
    reg [1:0] snapshot_wait;
    always @(posedge clk) begin
        if (!rst_n) begin
            s0_pulse <= 1'b0; s0_det <= 1'b0; s0_fatal <= 1'b0;
            s0_class <= NO_DETECTION; s0_stable <= NO_DETECTION;
            s0_x0 <= 9'd0; s0_y0 <= 9'd0; s0_x1 <= 9'd0; s0_y1 <= 9'd0; s0_id <= 32'd0;
        end else begin
            s0_pulse <= frame_valid;
            s0_det <= frame_detected;
            s0_fatal <= (leds == 4'b1111);
            s0_class <= frame_class;
            s0_stable <= stable_class;
            s0_x0 <= cfg_ema ? ema_x0 : raw_x0;
            s0_y0 <= cfg_ema ? ema_y0 : raw_y0;
            s0_x1 <= cfg_ema ? ema_x1 : raw_x1;
            s0_y1 <= cfg_ema ? ema_y1 : raw_y1;
            s0_id <= frame_id;
            s0_acq_ms<=acquisition_ms;s0_result_ms<=now_ms;s0_conf<=confidence_raw;
            s0_margin<=result_margin;s0_model<=model_class;
        end
    end

    // ---------------------------------------------------------------- stage 1: frame predicates
    reg  [8:0]  prev_x0, prev_y0, prev_x1, prev_y1;   // box of the previous in-window frame
    reg         prev_in;                             // previous frame was in the window
    function [8:0] absdiff;
        input [8:0] a, b;
        begin
            absdiff = (a >= b) ? (a - b) : (b - a);
        end
    endfunction
    wire in_win = s0_det && (s0_class == PALM_READY) &&
                  (s0_x0 >= cfg_x0) && (s0_x1 <= cfg_x1) && (s0_y0 >= cfg_y0) && (s0_y1 <= cfg_y1);
    wire still  = prev_in && (absdiff(s0_x0, prev_x0) <= cfg_move) && (absdiff(s0_y0, prev_y0) <= cfg_move) &&
                  (absdiff(s0_x1, prev_x1) <= cfg_move) && (absdiff(s0_y1, prev_y1) <= cfg_move);
    reg         s1_pulse, s1_in, s1_still;
    always @(posedge clk) begin
        if (!rst_n) begin
            s1_pulse <= 1'b0; s1_in <= 1'b0; s1_still <= 1'b0;
            prev_in <= 1'b0; prev_x0 <= 9'd0; prev_y0 <= 9'd0; prev_x1 <= 9'd0; prev_y1 <= 9'd0;
        end else begin
            s1_pulse <= s0_pulse;
            s1_in <= in_win;
            s1_still <= still;
            if (s0_pulse) begin
                prev_in <= in_win;
                prev_x0 <= s0_x0; prev_y0 <= s0_y0; prev_x1 <= s0_x1; prev_y1 <= s0_y1;
            end
        end
    end

    // ---------------------------------------------------------------- stage 2: state and outputs
    reg         seen, agree, stale_q;
    reg  [31:0] age;                                 // cycles since the last frame (saturating)
    reg  [2:0]  last_class;                          // last class reported while valid
    reg  [3:0]  win_cnt;
    reg  [2:0]  last_cand;
    reg         last_det;
    reg  [8:0]  last_x0, last_y0, last_x1, last_y1;
    reg  [31:0] last_id, frame_count, change_count, stale_count;
    wire        fresh   = seen && (age < cfg_stale);
    wire        valid_c = fresh && !s0_fatal &&
        ((USE_QUALIFIED_INPUT!=0)?qualified_valid:agree);
    always @(posedge clk) begin
        if (!rst_n) begin
            seen <= 1'b0; agree <= 1'b0; stale_q <= 1'b0; age <= 32'd0; last_class <= NO_DETECTION; win_cnt <= 4'd0;
            vis_valid <= 1'b0; vis_stable_class <= NO_DETECTION; vis_class_changed <= 1'b0; vis_palm_window_ok <= 1'b0;
            last_cand <= NO_DETECTION; last_det <= 1'b0; last_id <= 32'd0;
            last_x0 <= 9'd0; last_y0 <= 9'd0; last_x1 <= 9'd0; last_y1 <= 9'd0;
            frame_count <= 32'd0; change_count <= 32'd0; stale_count <= 32'd0;
            last_acq_ms<=0;last_result_ms<=0;last_conf<=0;last_margin<=0;last_model<=7;
        end else begin
            // freshness (stage-0 pulse, so age restarts in the cycle the frame is seen)
            if (s0_pulse) begin
                seen <= 1'b1; age <= 32'd0;
                agree <= (s0_class == s0_stable);
                last_cand <= s0_class; last_det <= s0_det; last_id <= s0_id;
                last_acq_ms<=s0_acq_ms;last_result_ms<=s0_result_ms;last_conf<=s0_conf;
                last_margin<=s0_margin;last_model<=s0_model;
                last_x0 <= s0_x0; last_y0 <= s0_y0; last_x1 <= s0_x1; last_y1 <= s0_y1;
            end else if (age != 32'hFFFF_FFFF) begin
                age <= age + 32'd1;
            end
            stale_q <= seen && !fresh;
            // class events
            vis_valid <= valid_c;
            vis_stable_class <= (USE_QUALIFIED_INPUT!=0)?stable_class:s0_stable;
            vis_class_changed <= valid_c && (((USE_QUALIFIED_INPUT!=0)?stable_class:s0_stable) != last_class);
            if (valid_c) last_class <= (USE_QUALIFIED_INPUT!=0)?stable_class:s0_stable;
            // delivery window: consecutive qualifying frames
            if (!((USE_QUALIFIED_INPUT!=0)?(fresh&&!s0_fatal):valid_c) || !cfg_enable || cfg_touch) begin
                win_cnt <= 4'd0;
            end else if (s1_pulse) begin
                if (!s1_in)                         win_cnt <= 4'd0;
                else if (win_cnt == 4'd0 || !s1_still) win_cnt <= 4'd1;
                else if (win_cnt != 4'd15)          win_cnt <= win_cnt + 4'd1;
            end
            vis_palm_window_ok <= valid_c && cfg_enable && !cfg_touch && (cfg_frames != 4'd0) && (win_cnt >= cfg_frames);
            // counters (telemetry for S8)
            if (cnt_clear) begin
                frame_count <= 32'd0; change_count <= 32'd0; stale_count <= 32'd0;
            end else begin
                if (s0_pulse) frame_count <= frame_count + 32'd1;
                if (valid_c && (((USE_QUALIFIED_INPUT!=0)?stable_class:s0_stable) != last_class)) change_count <= change_count + 32'd1;
                if (seen && !fresh && !stale_q) stale_count <= stale_count + 32'd1;
            end
        end
    end

    // ---------------------------------------------------------------- AXI4-Lite
    reg         aw_full, w_full;
    reg  [11:0] aw_addr;
    reg  [31:0] w_data;
    reg  [3:0]  w_strb;
    reg [31:0] camera_command;
    reg camera_pending,camera_done_sticky,camera_error_sticky;
    reg [7:0] camera_result;
    reg [15:0] camera_sequence;
    assign camera_cmd_read=camera_command[31];
    assign camera_cmd_addr=camera_command[23:8];
    assign camera_cmd_data=camera_command[7:0];
    wire exposure_write_allowed=(w_data[23:8]==16'h3500 || w_data[23:8]==16'h3501 ||
        w_data[23:8]==16'h3502 || w_data[23:8]==16'h3503 ||
        w_data[23:8]==16'h350a || w_data[23:8]==16'h350b);
    always @(posedge clk) begin
        if (!rst_n) begin
            s_awready <= 1'b1; s_wready <= 1'b1; s_bvalid <= 1'b0; s_bresp <= OKAY;
            aw_full <= 1'b0; w_full <= 1'b0; aw_addr <= 12'd0; w_data <= 32'd0; w_strb <= 4'd0;
            cfg_enable <= 1'b0; cfg_ema <= 1'b0; cfg_frames <= 4'd3;
            cfg_x0 <= 9'd0; cfg_x1 <= 9'd0; cfg_y0 <= 9'd0; cfg_y1 <= 9'd0; cfg_move <= 9'd0;
            cfg_stale <= 32'd30_000_000;
            cfg_touch <= 1'b0; cnt_clear <= 1'b0;
            snapshot_enable<=1'b0;snapshot_word_addr<=0;
            measure_freeze<=0;measure_read_index<=0;camera_command<=0;camera_cmd_start<=0;camera_pending<=0;
            camera_done_sticky<=0;camera_error_sticky<=0;camera_result<=0;camera_sequence<=0;
        end else begin
            cfg_touch <= 1'b0; cnt_clear <= 1'b0;
            camera_cmd_start<=0;
            if(CAMERA_CONTROL!=0 && camera_pending && camera_cmd_done) begin
                camera_pending<=0;camera_done_sticky<=1;
                camera_error_sticky<=camera_cmd_error;camera_result<=sensor_read_data;
                camera_sequence<=camera_sequence+16'd1;
            end
            if(snapshot_wait==1) snapshot_word_addr<=snapshot_word_addr+1;
            if (s_awvalid && s_awready) begin aw_full <= 1'b1; aw_addr <= s_awaddr; s_awready <= 1'b0; end
            if (s_wvalid && s_wready)   begin w_full <= 1'b1; w_data <= s_wdata; w_strb <= s_wstrb; s_wready <= 1'b0; end
            if (s_bvalid && s_bready)   begin s_bvalid <= 1'b0; s_awready <= 1'b1; s_wready <= 1'b1; end
            if (aw_full && w_full && !s_bvalid) begin
                aw_full <= 1'b0; w_full <= 1'b0; s_bvalid <= 1'b1; s_bresp <= OKAY;
                if (aw_addr[1:0] != 2'b00 || w_strb != 4'hF) begin
                    s_bresp <= SLVERR;
                end else begin
                    case (aw_addr)
                        12'h23c: if(MEASURE!=0)measure_freeze<=w_data[0];else s_bresp<=SLVERR;
                        12'h240: if(MEASURE!=0)measure_read_index<=w_data[7:0];else s_bresp<=SLVERR;
                        12'h000: cnt_clear <= w_data[0];
                        12'h00C: begin
                            cfg_enable <= w_data[0]; cfg_ema <= w_data[1]; cfg_frames <= w_data[11:8]; cfg_touch <= 1'b1;
                        end
                        12'h010: begin cfg_x0 <= w_data[8:0]; cfg_x1 <= w_data[24:16]; cfg_touch <= 1'b1; end
                        12'h014: begin cfg_y0 <= w_data[8:0]; cfg_y1 <= w_data[24:16]; cfg_touch <= 1'b1; end
                        12'h018: begin cfg_move <= w_data[8:0]; cfg_touch <= 1'b1; end
                        12'h01C: cfg_stale <= (w_data == 32'd0) ? 32'd1 : w_data;
                        12'h040:begin snapshot_enable<=w_data[0];cfg_touch<=1'b1;end
                        12'h04C:begin
                            if(w_data<SNAPSHOT_WORDS) snapshot_word_addr<=w_data[16:0];
                            else s_bresp<=SLVERR;
                        end
                        12'h088:begin
                            // Atomic command. Read any sensor register; writes restricted to exposure/gain.
                            // Reserved bits and read payload must be zero. Never queued during init/busy.
                            if(CAMERA_CONTROL==0 || !camera_cmd_ready || camera_cmd_busy || camera_pending ||
                               w_data[30:24]!=0 || (w_data[31] && w_data[7:0]!=0) ||
                               (!w_data[31] && !exposure_write_allowed)) s_bresp<=SLVERR;
                            else begin
                                camera_command<=w_data;camera_cmd_start<=1;camera_pending<=1;
                                camera_done_sticky<=0;camera_error_sticky<=0;
                            end
                        end
                        default: s_bresp <= SLVERR;
                    endcase
                end
            end
        end
    end

    reg [31:0] rd;
    reg        rd_ok;
    always @(*) begin
        rd_ok = (s_araddr[1:0] == 2'b00);
        case (s_araddr)
            12'h200: begin rd=measure_loc;rd_ok=MEASURE!=0;end
            12'h204: begin rd=measure_cls;rd_ok=MEASURE!=0;end
            12'h208: begin rd=measure_total;rd_ok=MEASURE!=0;end
            12'h20c: begin rd=measure_collisions;rd_ok=MEASURE!=0;end
            12'h210: begin rd=measure_cycle;rd_ok=MEASURE!=0;end
            12'h214: begin rd={24'd0,measure_write_index};rd_ok=MEASURE!=0;end
            12'h23c: begin rd={31'd0,measure_freeze};rd_ok=MEASURE!=0;end
            12'h240: begin rd={24'd0,measure_read_index};rd_ok=MEASURE!=0;end
            12'h244: begin rd=measure_record[31:0];rd_ok=MEASURE!=0;end
            12'h248: begin rd=measure_record[63:32];rd_ok=MEASURE!=0;end
            12'h24c: begin rd=measure_record[95:64];rd_ok=MEASURE!=0;end
            12'h250: begin rd=measure_record[127:96];rd_ok=MEASURE!=0;end
            12'h254: begin rd=measure_record[159:128];rd_ok=MEASURE!=0;end
            12'h258: begin rd=measure_record[191:160];rd_ok=MEASURE!=0;end
            12'h25c: begin rd=measure_record[223:192];rd_ok=MEASURE!=0;end
            12'h260: begin rd=measure_record[255:224];rd_ok=MEASURE!=0;end
            12'h000: rd = 32'd0;
            12'h004: rd = {12'd0, win_cnt, 2'd0, agree, seen, last_det, last_cand, vis_stable_class, vis_palm_window_ok,
                           cfg_enable, s0_fatal, fresh, vis_valid};
            12'h008: rd = ABI;
            12'h00C: rd = {20'd0, cfg_frames, 6'd0, cfg_ema, cfg_enable};
            12'h010: rd = {7'd0, cfg_x1, 7'd0, cfg_x0};
            12'h014: rd = {7'd0, cfg_y1, 7'd0, cfg_y0};
            12'h018: rd = {23'd0, cfg_move};
            12'h01C: rd = cfg_stale;
            12'h020: rd = {7'd0, last_y0, 7'd0, last_x0};
            12'h024: rd = {7'd0, last_y1, 7'd0, last_x1};
            12'h028: rd = last_id;
            12'h02C: rd = frame_count;
            12'h030: rd = change_count;
            12'h034: rd = stale_count;
            12'h038: rd = {31'd0,qualified_valid};
            12'h040: rd = {31'd0,snapshot_enable};
            12'h044: rd = {30'd0,snapshot_enable,snapshot_ready};
            12'h048: rd = snapshot_frame_id;
            12'h04C: rd = {15'd0,snapshot_word_addr};
            12'h050:begin rd=snapshot_data;rd_ok=rd_ok && snapshot_ready && snapshot_word_addr<SNAPSHOT_WORDS;end
            12'h054: rd = (PHASE2_FRONTEND!=0)?{16'd128,16'd128}:{16'd480,16'd640};
            12'h058: rd = snapshot_timestamp_ms;
            12'h05C: rd = last_acq_ms;
            12'h060: rd = last_result_ms;
            12'h064: rd = last_result_ms-last_acq_ms;
            12'h068: rd = {13'd0,last_model,last_margin};
            12'h06C: rd = last_conf;
            12'h070: rd = 32'h022267A9; // v2 frozen Rain source identity; also bind full SHA in manifest
            12'h074: rd = (CAMERA_DIAGNOSTICS!=0)?32'h43414D31:32'd0; // CAM1
            12'h078: rd = (CAMERA_DIAGNOSTICS!=0)?camera_status:32'd0;
            12'h07C: rd = (CAMERA_DIAGNOSTICS!=0)?frame_drop_count:32'd0;
            12'h080: rd = (CAMERA_DIAGNOSTICS!=0)?format_error_count:32'd0;
            12'h084: rd = (CAMERA_DIAGNOSTICS!=0)?now_ms:32'd0;
            12'h088:begin rd=camera_command;rd_ok=rd_ok && CAMERA_CONTROL!=0;end
            12'h08C:begin
                rd={camera_sequence,12'd0,camera_cmd_ready,camera_error_sticky,camera_done_sticky,camera_pending};
                rd_ok=rd_ok && CAMERA_CONTROL!=0;
            end
            12'h090:begin rd={24'd0,camera_result};rd_ok=rd_ok && CAMERA_CONTROL!=0;end
            12'h094:begin rd=32'h45585031;rd_ok=rd_ok && CAMERA_CONTROL!=0;end // EXP1
            default: begin rd = 32'd0; rd_ok = 1'b0; end
        endcase
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            s_arready <= 1'b1; s_rvalid <= 1'b0; s_rdata <= 32'd0; s_rresp <= OKAY;
            snapshot_wait<=0;snapshot_rd_en<=0;
        end else begin
            snapshot_rd_en<=0;
            if(snapshot_wait!=0) begin
                snapshot_wait<=snapshot_wait-1;
                if(snapshot_wait==1)begin s_rvalid<=1;s_rdata<=snapshot_data;s_rresp<=OKAY;end
            end
            if (s_arvalid && s_arready) begin
                s_arready <= 1'b0;
                if(s_araddr==12'h050 && rd_ok)begin
                    // Registered request + two-clock owned VGA read.
                    snapshot_rd_en<=1;snapshot_wait<=3;s_rvalid<=0;
                end else begin
                    s_rvalid <= 1'b1;s_rdata <= rd; s_rresp <= rd_ok ? OKAY : SLVERR;
                end
            end
            if (s_rvalid && s_rready) begin s_rvalid <= 1'b0; s_arready <= 1'b1; end
        end
    end

endmodule
