// Structural wrapper: original instances, parameters and cycles preserved.
`timescale 1ns/1ps
module vision_schedule_qualifier #(
    parameter LOCATOR_MODEL_FILE     = "model_rom_16k.mem",
    parameter CLASSIFIER_WEIGHT_FILE = "weights_all.mem",
    parameter CLASSIFIER_DESC_FILE   = "layer_descriptors.mem",
    parameter GEOMETRY_ALPHA_FILE="geometry_alpha_q16.mem",
    parameter integer HD_PREVIEW=0,
    parameter integer CLASSIFIER_LANES=1,
    parameter integer GEOMETRY_EMA=1,
    parameter integer CAMERA_CONTROL=0,
    parameter integer OBJECT_HOLD_MS=200,PALM_HOLD_MS=300,FIST_HOLD_MS=80,
    parameter OV5640_INIT_FILE       = "ov5640_vga_yuyv.mem",
    parameter [31:0] CONFIRM_COUNTS = {4'd3, 4'd2, 4'd2, 4'd2, 4'd2, 4'd2, 4'd2, 4'd3},
    parameter [7:0]  GATED_CODES    = 8'b0011_1110,
    parameter [15:0] MARGIN_MIN     = 16'd0
)(
    output wire [1:0] camera_buffer_release,
    input wire [1:0] camera_buffer_valid,
    input wire [31:0] camera_frame_id_0,
    input wire [31:0] camera_frame_id_1,
    input wire  camera_init_done,
    input wire  camera_init_error,
    input wire  camera_latest_buffer,
    output wire  capture_enable_request,
    output wire [2:0] class_candidate,
    output wire [15:0] class_candidate_margin,
    output wire  class_candidate_valid,
    output wire [3:0] class_leds,
    output wire  classifier_read_bank,
    output wire  classifier_request,
    input wire  classifier_request_busy,
    input wire [8:0] classifier_result_class,
    input wire [15:0] classifier_result_margin,
    input wire  classifier_result_pulse,
    input wire  clk_100mhz,
    input wire [1:0] effective_release,
    output wire  fatal_error,
    input wire  fifo_overflow,
    output wire  filter_valid,
    input wire [31:0] frame_timestamp_ms_0,
    input wire [31:0] frame_timestamp_ms_1,
    input wire [31:0] job_timestamp_ms,
    input wire  locator_busy,
    input wire  locator_done,
    output wire [31:0] locator_frame_id,
    output wire  locator_input_buffer,
    output wire  locator_start,
    input wire [31:0] now_ms,
    output wire signed[31:0] obs_conf,
    output wire  obs_detected,
    output wire [8:0] obs_ema_x0,
    output wire [8:0] obs_ema_x1,
    output wire [8:0] obs_ema_y0,
    output wire [8:0] obs_ema_y1,
    output wire [31:0] obs_id,
    output wire [2:0] obs_model,
    output wire [8:0] obs_raw_x0,
    output wire [8:0] obs_raw_x1,
    output wire [8:0] obs_raw_y0,
    output wire [8:0] obs_raw_y1,
    output wire [9:0] obs_roi_side,
    output wire [9:0] obs_roi_x0,
    output wire [9:0] obs_roi_y0,
    output wire [31:0] obs_ts,
    output wire  roi_buffer_id,
    input wire  roi_busy,
    input wire  roi_done,
    input wire  roi_error,
    output wire [9:0] roi_side,
    output wire  roi_start,
    output wire [31:0] roi_tag,
    output wire  roi_write_bank,
    output wire [9:0] roi_x0,
    output wire [9:0] roi_y0,
    input wire  rst_100mhz_n,
    output wire [3:0] scheduler_state_unused,
    input wire  snapshot_enable,
    output wire [2:0] stable_class,
    input wire [31:0] top1_cell,
    input wire [31:0] top1_confidence,
    input wire [31:0] top1_dx,
    input wire [31:0] top1_dy,
    input wire [31:0] top1_height,
    input wire [31:0] top1_width
);
wire  bbox_busy;
wire [7:0] bbox_cell;
wire signed [31:0] bbox_confidence;
wire  bbox_detected;
wire  bbox_done;
wire signed [31:0] bbox_dx;
wire signed [31:0] bbox_dy;
wire [8:0] bbox_ema_x0;
wire [8:0] bbox_ema_x1;
wire [8:0] bbox_ema_y0;
wire [8:0] bbox_ema_y1;
wire signed [31:0] bbox_height;
wire [8:0] bbox_raw_x0;
wire [8:0] bbox_raw_x1;
wire [8:0] bbox_raw_y0;
wire [8:0] bbox_raw_y1;
wire [9:0] bbox_roi_side;
wire [9:0] bbox_roi_x0;
wire [9:0] bbox_roi_y0;
wire  bbox_start;
wire signed [31:0] bbox_width;
wire [2:0] gated_class_unused;
wire  stable_changed_unused;
locator_bbox_roi_black #(.ALPHA_FILE(GEOMETRY_ALPHA_FILE),.USE_EMA(GEOMETRY_EMA)) u_bbox (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n), .start(bbox_start),
        .timestamp_ms(job_timestamp_ms),.cell_index(bbox_cell), .confidence_i32(bbox_confidence),
        .dx_i32(bbox_dx), .dy_i32(bbox_dy), .width_i32(bbox_width),
        .height_i32(bbox_height), .busy(bbox_busy), .done(bbox_done),
        .detected(bbox_detected), .roi_x0(bbox_roi_x0),
        .roi_y0(bbox_roi_y0), .roi_side(bbox_roi_side),
        .raw_box_x0(bbox_raw_x0), .raw_box_y0(bbox_raw_y0),
        .raw_box_x1(bbox_raw_x1), .raw_box_y1(bbox_raw_y1),
        .ema_box_x0(bbox_ema_x0), .ema_box_y0(bbox_ema_y0),
        .ema_box_x1(bbox_ema_x1), .ema_box_y1(bbox_ema_y1)
    );
autonomous_overlap_ctrl #(.NUM_CLASSES(6),.TASK_CLASS_MAP(1)) u_scheduler (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n),
        .camera_init_done(camera_init_done), .camera_init_error(camera_init_error),
        .fifo_overflow(fifo_overflow),.pause_new_jobs(snapshot_enable),
        .camera_buffer_valid(snapshot_enable?2'b00:(camera_buffer_valid&~effective_release)),
        .camera_latest_buffer(camera_latest_buffer),
        .camera_frame_id_0(camera_frame_id_0), .camera_frame_id_1(camera_frame_id_1),
        .camera_timestamp_0(frame_timestamp_ms_0),.camera_timestamp_1(frame_timestamp_ms_1),
        .capture_enable(capture_enable_request),
        .camera_buffer_release(camera_buffer_release),
        .locator_busy(locator_busy), .locator_done(locator_done),
        .locator_start(locator_start), .locator_input_buffer(locator_input_buffer),
        .locator_frame_id(locator_frame_id),.locator_timestamp_ms(), .top1_cell(top1_cell),
        .top1_confidence(top1_confidence), .top1_dx(top1_dx), .top1_dy(top1_dy),
        .top1_width(top1_width), .top1_height(top1_height),
        .bbox_start(bbox_start), .bbox_busy(bbox_busy), .bbox_done(bbox_done),
        .bbox_detected(bbox_detected), .bbox_cell(bbox_cell),
        .bbox_confidence(bbox_confidence), .bbox_dx(bbox_dx), .bbox_dy(bbox_dy),
        .bbox_width(bbox_width), .bbox_height(bbox_height),
        .bbox_roi_x0(bbox_roi_x0), .bbox_roi_y0(bbox_roi_y0),
        .bbox_roi_side(bbox_roi_side), .roi_busy(roi_busy), .roi_done(roi_done),
        .bbox_raw_x0(bbox_raw_x0),.bbox_raw_y0(bbox_raw_y0),.bbox_raw_x1(bbox_raw_x1),.bbox_raw_y1(bbox_raw_y1),
        .bbox_ema_x0(bbox_ema_x0),.bbox_ema_y0(bbox_ema_y0),.bbox_ema_x1(bbox_ema_x1),.bbox_ema_y1(bbox_ema_y1),
        .roi_error(roi_error), .roi_start(roi_start), .roi_buffer_id(roi_buffer_id),
        .roi_write_bank(roi_write_bank),.classifier_read_bank(classifier_read_bank),
        .roi_x0(roi_x0), .roi_y0(roi_y0), .roi_side(roi_side), .roi_tag(roi_tag),
        .classifier_request_busy(classifier_request_busy),
        .classifier_request(classifier_request),
        .classifier_result_pulse(classifier_result_pulse),
        .classifier_result_class(classifier_result_class),
        .classifier_result_margin(classifier_result_margin),
        .class_candidate_valid(class_candidate_valid),
        .class_candidate(class_candidate), .class_candidate_margin(class_candidate_margin),
        .result_frame_id(obs_id),.result_timestamp_ms(obs_ts),.result_model_class(obs_model),.result_detected(obs_detected),
        .result_raw_x0(obs_raw_x0),.result_raw_y0(obs_raw_y0),.result_raw_x1(obs_raw_x1),.result_raw_y1(obs_raw_y1),
        .result_ema_x0(obs_ema_x0),.result_ema_y0(obs_ema_y0),.result_ema_x1(obs_ema_x1),.result_ema_y1(obs_ema_y1),
        .result_roi_x0(obs_roi_x0),.result_roi_y0(obs_roi_y0),.result_roi_side(obs_roi_side),.result_confidence(obs_conf),
        .pipeline_idle(),
        .fatal_error(fatal_error),
        .state_debug(scheduler_state_unused)
    );
gesture_time_filter #(.MARGIN_MIN(MARGIN_MIN),.OBJECT_HOLD_MS(OBJECT_HOLD_MS),
        .PALM_HOLD_MS(PALM_HOLD_MS),.FIST_HOLD_MS(FIST_HOLD_MS),
        .OBJECT_MIN_FRAMES(3),.PALM_MIN_FRAMES(3),.FIST_MIN_FRAMES(2)) u_confirm (
        .clk(clk_100mhz),.rst_n(rst_100mhz_n),.now_ms(now_ms),
        .frame_timestamp_ms(obs_ts),.frame_id(obs_id),
        .candidate_valid(class_candidate_valid),.candidate_class(class_candidate),
        .candidate_margin(class_candidate_margin),.output_class(stable_class),
        .output_changed(stable_changed_unused),.output_valid(filter_valid),
        .gated_class(gated_class_unused),.leds(class_leds));
endmodule
