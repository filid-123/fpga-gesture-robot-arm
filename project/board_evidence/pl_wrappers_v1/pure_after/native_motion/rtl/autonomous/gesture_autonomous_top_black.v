// Rain black_scene_vision_v1_int8_20261013: context locator and six-class classifier.
// Phase2 small ping/pong frames; nearest same-frame ROI; frozen real CNNs.
// Alternative preprocessing contract; no claim of original PIL-input equivalence.
// All CNN/control in 100 MHz; snapshot is calibration-only and inhibits live qualification.
`timescale 1ns / 1ps

module gesture_autonomous_top_black #(
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
    input  wire       clk_100mhz,
    input  wire       rst_100mhz_n,
    input  wire       clk_50mhz,
    input  wire       rst_50mhz_n,
    input  wire       pclk,
    input  wire       pclk_rst_n,
    input  wire [7:0] dvp_data,
    input  wire       dvp_href,
    input  wire       dvp_vsync,
    input  wire       xclk_locked,
    output wire       camera_reset_n,
    output wire       camera_pwdn,
    output wire       sccb_scl_drive_low,
    output wire       sccb_sda_drive_low,
    input  wire       sccb_sda_in,
    input wire camera_cmd_start,camera_cmd_read,
    input wire [15:0] camera_cmd_addr,
    input wire [7:0] camera_cmd_data,
    output wire camera_cmd_ready,camera_cmd_busy,camera_cmd_done,camera_cmd_error,
    output wire [7:0] sensor_read_data,
    output wire [3:0] leds,
    output wire debug_loc_start,debug_loc_done,debug_cls_start,debug_cls_done,
    output wire[31:0] debug_job_id,
    output wire debug_preview_we,output wire[13:0]debug_preview_addr,output wire[31:0]debug_preview_data,
    output wire debug_preview_published,output wire[31:0]debug_preview_id,
    output wire       debug_camera_we,
    output wire [12:0] debug_camera_word_addr,
    output wire [31:0] debug_camera_wdata,
    output wire       debug_camera_frame_published,
    output wire [31:0] debug_camera_latest_frame_id,
    output wire       debug_result_valid,
    output wire [31:0] debug_result_frame_id,
    output wire       debug_result_detected,
    output wire [8:0] debug_raw_x0,
    output wire [8:0] debug_raw_y0,
    output wire [8:0] debug_raw_x1,
    output wire [8:0] debug_raw_y1,
    output wire [8:0] debug_ema_x0,
    output wire [8:0] debug_ema_y0,
    output wire [8:0] debug_ema_x1,
    output wire [8:0] debug_ema_y1,
    output wire [9:0] debug_roi_x0,
    output wire [9:0] debug_roi_y0,
    output wire [9:0] debug_roi_side,
    output wire [2:0] debug_candidate_class,
    output wire [2:0] debug_stable_class,
    output wire debug_filter_valid,
    input wire snapshot_enable,
    input wire snapshot_rd_en,
    input wire [16:0] snapshot_word_addr,
    output wire [31:0] snapshot_data,
    output wire snapshot_ready,
    output wire [31:0] snapshot_frame_id,
    output wire [31:0] snapshot_timestamp_ms,
    output wire [31:0] debug_frame_timestamp_ms,debug_now_ms,
    output wire [15:0] debug_margin,
    output wire [2:0] debug_model_class,
    output wire signed [31:0] debug_confidence_i32,
    output wire [31:0] debug_camera_status,debug_frame_drop_count,debug_format_error_count
);

    
    wire  init_cmd_ready;
    
    
    
    wire [31:0] frame_timestamp_ms_0,frame_timestamp_ms_1,now_ms;
    wire roi_busy;
    wire [3:0] scheduler_state_unused;
    reg snapshot_locked,snapshot_buffer;
    // Snapshot locks one bank only after the whole pipeline is quiescent.
    // Both old banks retire on exit; classification never restarts an aged snapshot.
    wire snapshot_exit=snapshot_locked && !snapshot_enable;
    reg [31:0] job_timestamp_ms;
    wire sccb_done, sccb_ack_error;
    wire [7:0] sccb_read_data_unused;
    wire sccb_busy_unused, camera_init_done, camera_init_error;
    wire master_ready;
    wire runtime_select=(CAMERA_CONTROL!=0) && camera_init_done && !camera_init_error;
    assign init_cmd_ready=master_ready && !runtime_select;
    assign camera_cmd_ready=runtime_select && master_ready;
    assign camera_cmd_busy=sccb_busy_unused;
    assign camera_cmd_done=runtime_select && sccb_done;
    assign camera_cmd_error=sccb_ack_error;
    assign sensor_read_data=sccb_read_data_unused;

    

    // SCCB SDA is an external asynchronous input. At 100 kHz it is stable
    // for microseconds before the ACK/read sample; two 100 MHz stages preserve
    // that phase while keeping metastability out of the command state machine.
    (* ASYNC_REG = "TRUE" *) reg sccb_sda_meta, sccb_sda_sync;
    always @(posedge clk_100mhz) begin
        if(!rst_100mhz_n) begin sccb_sda_meta<=1'b1; sccb_sda_sync<=1'b1; end
        else begin sccb_sda_meta<=sccb_sda_in; sccb_sda_sync<=sccb_sda_meta; end
    end
    

    wire capture_enable_request;
    reg capture_enable;
    wire [1:0] camera_buffer_release, camera_buffer_valid;
    wire [31:0] camera_frame_id_0, camera_frame_id_1;
    wire camera_frame_published, camera_latest_buffer;
    wire snapshot_select=camera_buffer_valid[camera_latest_buffer]?camera_latest_buffer:camera_buffer_valid[1];
    wire [31:0] camera_latest_frame_id;
    wire camera_mem_we;
    wire [12:0] camera_mem_write_addr;
    wire [31:0] camera_mem_write_data;
    wire [31:0] frame_drop_count, format_error_count;
    wire [2:0] capture_state={1'b0,camera_buffer_valid};
    reg [1:0] deferred_release;
    wire [1:0] effective_release=(camera_buffer_release|deferred_release|({2{snapshot_exit}}&camera_buffer_valid))&{2{!snapshot_enable}};
    wire fifo_overflow;

    always @(posedge clk_100mhz) begin
        if (!rst_100mhz_n)
            capture_enable <= 1'b0;
        else
            capture_enable <= capture_enable_request;
    end

    // A snapshot can suppress a release issued by an in-flight LOC/ROI job.
    // Remember it, then invalidate that frame exactly once on snapshot exit.
    // Otherwise the old frame is selected again when live processing resumes.
    always @(posedge clk_100mhz) begin
        if(!rst_100mhz_n) deferred_release<=2'b00;
        else if(snapshot_enable) deferred_release<=deferred_release|camera_buffer_release;
        else deferred_release<=2'b00;
    end

    

    wire locator_start, locator_input_buffer;
    wire [31:0] locator_frame_id;
    wire locator_input_en;
    wire [12:0] locator_input_addr;
    wire [31:0] camera_read_data;
    
    
    
    
    
    
    
    wire  locator_busy, locator_done;
    
    
    
    
    
    
    

    

    

    wire [31:0] top1_cell, top1_confidence, top1_dx, top1_dy;
    wire [31:0] top1_width, top1_height;
    
    
    

    

    
    
    
    
    
    
    

    always @(posedge clk_100mhz) begin
        if(!rst_100mhz_n) job_timestamp_ms<=0;
        else if(locator_start) job_timestamp_ms<=locator_input_buffer?frame_timestamp_ms_1:frame_timestamp_ms_0;
    end
    

    wire roi_start, roi_buffer_id;
    wire [9:0] roi_x0, roi_y0, roi_side;
    wire [31:0] roi_tag;
    wire roi_read_en;
    wire [12:0] roi_read_addr;
    wire roi_done, roi_error;
    
    
    
    
    wire camera_read_en=locator_input_en || roi_read_en || (snapshot_ready && snapshot_rd_en);
    wire [12:0] camera_read_addr=locator_input_en?locator_input_addr:
        (roi_read_en?roi_read_addr:{snapshot_buffer,snapshot_word_addr[11:0]});
    function [8:0] floor_div5;
        input [10:0] value;reg [21:0] product;
        begin product=value*11'd1639;floor_div5=product[21:13];end
    endfunction
    // Map the frozen source-space descriptor onto the Phase2 content grid.
    // The alternative contract is floor(x/5),16+floor(y/5),ceil(side/5).
    // Scheduler inserts a full cycle before ROI start. Register the small
    // descriptor in that existing interval, cutting geometry-to-address CE.
    reg [9:0] small_x,small_y,small_side;
    always @(posedge clk_100mhz) begin
        if(!rst_100mhz_n) begin small_x<=0;small_y<=16;small_side<=1;end
        else begin
            small_x<=floor_div5({1'b0,roi_x0});
            small_y<=10'd16+floor_div5({1'b0,roi_y0});
            small_side<=floor_div5({1'b0,roi_side}+11'd4);
        end
    end

    

    
    always @(posedge clk_100mhz) begin
        if(!rst_100mhz_n)begin snapshot_locked<=0;snapshot_buffer<=0;end
        else if(!snapshot_enable)snapshot_locked<=0;
        else if(!snapshot_locked && |camera_buffer_valid && scheduler_state_unused==4'd1 && !roi_busy && !locator_busy)begin
            snapshot_locked<=1;snapshot_buffer<=snapshot_select;
        end
    end
    assign snapshot_data=camera_read_data;
    assign snapshot_ready=snapshot_enable && snapshot_locked && camera_buffer_valid[snapshot_buffer]
        && scheduler_state_unused==4'd1 && !roi_busy && !locator_busy;
    assign snapshot_frame_id=snapshot_buffer?camera_frame_id_1:camera_frame_id_0;
    assign snapshot_timestamp_ms=snapshot_buffer?frame_timestamp_ms_1:frame_timestamp_ms_0;

    wire classifier_request, classifier_request_busy;
    wire roi_write_bank,classifier_read_bank;
    wire classifier_result_pulse;
    wire [8:0] classifier_result_class;
    wire [15:0] classifier_result_margin;
    wire classifier_start, classifier_busy, classifier_done;
    assign debug_loc_start=locator_start;assign debug_loc_done=locator_done;
    assign debug_cls_start=classifier_start;assign debug_cls_done=classifier_result_pulse;
    assign debug_job_id=locator_frame_id;
    wire [8:0] classifier_class;
    wire [15:0] classifier_margin;
    
    
    
    
    
    
    
    wire classifier_input_en;
    wire [13:0] classifier_input_addr;
    wire [7:0] classifier_input_data;

    

    

    

    

    reg classifier_done_q;
    always @(posedge clk_100mhz) begin
        if(!rst_100mhz_n) classifier_done_q<=1'b0;
        else classifier_done_q<=classifier_done;
    end
    assign classifier_start=classifier_request;
    assign classifier_request_busy=classifier_busy;
    assign classifier_result_pulse=classifier_done && !classifier_done_q;
    assign classifier_result_class=classifier_class;
    assign classifier_result_margin=classifier_margin;

    wire class_candidate_valid;
    wire [2:0] class_candidate, stable_class;
    wire [15:0] class_candidate_margin;
    
    
    wire [3:0] class_leds;
    wire fatal_error;
    wire[31:0]obs_id,obs_ts;wire obs_detected;
    wire[2:0]obs_model;
    wire[8:0]obs_raw_x0,obs_raw_y0,obs_raw_x1,obs_raw_y1;
    wire[8:0]obs_ema_x0,obs_ema_y0,obs_ema_x1,obs_ema_y1;
    wire[9:0]obs_roi_x0,obs_roi_y0,obs_roi_side;
    wire signed[31:0]obs_conf;


    

    wire filter_valid;
    
    assign debug_filter_valid=filter_valid && !snapshot_enable;
    // Read-only observability of existing state/counters; no new decisions.
    assign debug_camera_status={10'd0,1'b1,snapshot_buffer,camera_buffer_valid[1],capture_state,scheduler_state_unused,
        deferred_release[0],snapshot_ready,snapshot_enable,classifier_busy,roi_busy,
        locator_busy,(|camera_buffer_valid),fifo_overflow,capture_enable,
        camera_init_error,camera_init_done,xclk_locked};
    assign debug_frame_drop_count=frame_drop_count;
    assign debug_format_error_count=format_error_count;
    assign debug_frame_timestamp_ms=obs_ts;
    assign debug_now_ms=now_ms;
    assign debug_margin=class_candidate_margin;
    assign debug_model_class=obs_model;
    assign debug_confidence_i32=obs_conf;

    assign leds = fatal_error ? 4'b1111 : class_leds;
    assign debug_camera_we              = camera_mem_we;
    assign debug_camera_word_addr       = camera_mem_write_addr;
    assign debug_camera_wdata           = camera_mem_write_data;
    assign debug_camera_frame_published = camera_frame_published;
    assign debug_camera_latest_frame_id = camera_latest_frame_id;
    assign debug_result_valid           = class_candidate_valid;
    assign debug_result_frame_id        = obs_id;
    assign debug_result_detected        = obs_detected;
    assign debug_raw_x0                 = obs_raw_x0;
    assign debug_raw_y0                 = obs_raw_y0;
    assign debug_raw_x1                 = obs_raw_x1;
    assign debug_raw_y1                 = obs_raw_y1;
    assign debug_ema_x0                 = obs_ema_x0;
    assign debug_ema_y0                 = obs_ema_y0;
    assign debug_ema_x1                 = obs_ema_x1;
    assign debug_ema_y1                 = obs_ema_y1;
    assign debug_roi_x0                 = obs_roi_x0;
    assign debug_roi_y0                 = obs_roi_y0;
    assign debug_roi_side               = obs_roi_side;
    assign debug_candidate_class        = class_candidate;
    assign debug_stable_class           = stable_class;
vision_acquisition_pipeline #(
    .LOCATOR_MODEL_FILE(LOCATOR_MODEL_FILE),
    .CLASSIFIER_WEIGHT_FILE(CLASSIFIER_WEIGHT_FILE),
    .CLASSIFIER_DESC_FILE(CLASSIFIER_DESC_FILE),
    .GEOMETRY_ALPHA_FILE(GEOMETRY_ALPHA_FILE),
    .HD_PREVIEW(HD_PREVIEW),
    .CLASSIFIER_LANES(CLASSIFIER_LANES),
    .GEOMETRY_EMA(GEOMETRY_EMA),
    .CAMERA_CONTROL(CAMERA_CONTROL),
    .OBJECT_HOLD_MS(OBJECT_HOLD_MS),
    .PALM_HOLD_MS(PALM_HOLD_MS),
    .FIST_HOLD_MS(FIST_HOLD_MS),
    .OV5640_INIT_FILE(OV5640_INIT_FILE),
    .CONFIRM_COUNTS(CONFIRM_COUNTS),
    .GATED_CODES(GATED_CODES),
    .MARGIN_MIN(MARGIN_MIN)
) u_acquisition(
    .camera_buffer_valid(camera_buffer_valid),
    .camera_cmd_addr(camera_cmd_addr),
    .camera_cmd_data(camera_cmd_data),
    .camera_cmd_read(camera_cmd_read),
    .camera_cmd_start(camera_cmd_start),
    .camera_frame_id_0(camera_frame_id_0),
    .camera_frame_id_1(camera_frame_id_1),
    .camera_frame_published(camera_frame_published),
    .camera_init_done(camera_init_done),
    .camera_init_error(camera_init_error),
    .camera_latest_buffer(camera_latest_buffer),
    .camera_latest_frame_id(camera_latest_frame_id),
    .camera_mem_we(camera_mem_we),
    .camera_mem_write_addr(camera_mem_write_addr),
    .camera_mem_write_data(camera_mem_write_data),
    .camera_pwdn(camera_pwdn),
    .camera_reset_n(camera_reset_n),
    .capture_enable(capture_enable),
    .clk_100mhz(clk_100mhz),
    .debug_preview_addr(debug_preview_addr),
    .debug_preview_data(debug_preview_data),
    .debug_preview_id(debug_preview_id),
    .debug_preview_published(debug_preview_published),
    .debug_preview_we(debug_preview_we),
    .dvp_data(dvp_data),
    .dvp_href(dvp_href),
    .dvp_vsync(dvp_vsync),
    .effective_release(effective_release),
    .fifo_overflow(fifo_overflow),
    .format_error_count(format_error_count),
    .frame_drop_count(frame_drop_count),
    .frame_timestamp_ms_0(frame_timestamp_ms_0),
    .frame_timestamp_ms_1(frame_timestamp_ms_1),
    .init_cmd_ready(init_cmd_ready),
    .master_ready(master_ready),
    .now_ms(now_ms),
    .pclk(pclk),
    .pclk_rst_n(pclk_rst_n),
    .rst_100mhz_n(rst_100mhz_n),
    .runtime_select(runtime_select),
    .sccb_ack_error(sccb_ack_error),
    .sccb_busy_unused(sccb_busy_unused),
    .sccb_done(sccb_done),
    .sccb_read_data_unused(sccb_read_data_unused),
    .sccb_scl_drive_low(sccb_scl_drive_low),
    .sccb_sda_drive_low(sccb_sda_drive_low),
    .sccb_sda_sync(sccb_sda_sync),
    .xclk_locked(xclk_locked)
);
vision_locator_compute #(
    .LOCATOR_MODEL_FILE(LOCATOR_MODEL_FILE),
    .CLASSIFIER_WEIGHT_FILE(CLASSIFIER_WEIGHT_FILE),
    .CLASSIFIER_DESC_FILE(CLASSIFIER_DESC_FILE),
    .GEOMETRY_ALPHA_FILE(GEOMETRY_ALPHA_FILE),
    .HD_PREVIEW(HD_PREVIEW),
    .CLASSIFIER_LANES(CLASSIFIER_LANES),
    .GEOMETRY_EMA(GEOMETRY_EMA),
    .CAMERA_CONTROL(CAMERA_CONTROL),
    .OBJECT_HOLD_MS(OBJECT_HOLD_MS),
    .PALM_HOLD_MS(PALM_HOLD_MS),
    .FIST_HOLD_MS(FIST_HOLD_MS),
    .OV5640_INIT_FILE(OV5640_INIT_FILE),
    .CONFIRM_COUNTS(CONFIRM_COUNTS),
    .GATED_CODES(GATED_CODES),
    .MARGIN_MIN(MARGIN_MIN)
) u_locator_compute(
    .camera_read_data(camera_read_data),
    .clk_100mhz(clk_100mhz),
    .locator_busy(locator_busy),
    .locator_done(locator_done),
    .locator_frame_id(locator_frame_id),
    .locator_input_addr(locator_input_addr),
    .locator_input_buffer(locator_input_buffer),
    .locator_input_en(locator_input_en),
    .locator_start(locator_start),
    .rst_100mhz_n(rst_100mhz_n),
    .top1_cell(top1_cell),
    .top1_confidence(top1_confidence),
    .top1_dx(top1_dx),
    .top1_dy(top1_dy),
    .top1_height(top1_height),
    .top1_width(top1_width)
);
vision_schedule_qualifier #(
    .LOCATOR_MODEL_FILE(LOCATOR_MODEL_FILE),
    .CLASSIFIER_WEIGHT_FILE(CLASSIFIER_WEIGHT_FILE),
    .CLASSIFIER_DESC_FILE(CLASSIFIER_DESC_FILE),
    .GEOMETRY_ALPHA_FILE(GEOMETRY_ALPHA_FILE),
    .HD_PREVIEW(HD_PREVIEW),
    .CLASSIFIER_LANES(CLASSIFIER_LANES),
    .GEOMETRY_EMA(GEOMETRY_EMA),
    .CAMERA_CONTROL(CAMERA_CONTROL),
    .OBJECT_HOLD_MS(OBJECT_HOLD_MS),
    .PALM_HOLD_MS(PALM_HOLD_MS),
    .FIST_HOLD_MS(FIST_HOLD_MS),
    .OV5640_INIT_FILE(OV5640_INIT_FILE),
    .CONFIRM_COUNTS(CONFIRM_COUNTS),
    .GATED_CODES(GATED_CODES),
    .MARGIN_MIN(MARGIN_MIN)
) u_pipeline_control(
    .camera_buffer_release(camera_buffer_release),
    .camera_buffer_valid(camera_buffer_valid),
    .camera_frame_id_0(camera_frame_id_0),
    .camera_frame_id_1(camera_frame_id_1),
    .camera_init_done(camera_init_done),
    .camera_init_error(camera_init_error),
    .camera_latest_buffer(camera_latest_buffer),
    .capture_enable_request(capture_enable_request),
    .class_candidate(class_candidate),
    .class_candidate_margin(class_candidate_margin),
    .class_candidate_valid(class_candidate_valid),
    .class_leds(class_leds),
    .classifier_read_bank(classifier_read_bank),
    .classifier_request(classifier_request),
    .classifier_request_busy(classifier_request_busy),
    .classifier_result_class(classifier_result_class),
    .classifier_result_margin(classifier_result_margin),
    .classifier_result_pulse(classifier_result_pulse),
    .clk_100mhz(clk_100mhz),
    .effective_release(effective_release),
    .fatal_error(fatal_error),
    .fifo_overflow(fifo_overflow),
    .filter_valid(filter_valid),
    .frame_timestamp_ms_0(frame_timestamp_ms_0),
    .frame_timestamp_ms_1(frame_timestamp_ms_1),
    .job_timestamp_ms(job_timestamp_ms),
    .locator_busy(locator_busy),
    .locator_done(locator_done),
    .locator_frame_id(locator_frame_id),
    .locator_input_buffer(locator_input_buffer),
    .locator_start(locator_start),
    .now_ms(now_ms),
    .obs_conf(obs_conf),
    .obs_detected(obs_detected),
    .obs_ema_x0(obs_ema_x0),
    .obs_ema_x1(obs_ema_x1),
    .obs_ema_y0(obs_ema_y0),
    .obs_ema_y1(obs_ema_y1),
    .obs_id(obs_id),
    .obs_model(obs_model),
    .obs_raw_x0(obs_raw_x0),
    .obs_raw_x1(obs_raw_x1),
    .obs_raw_y0(obs_raw_y0),
    .obs_raw_y1(obs_raw_y1),
    .obs_roi_side(obs_roi_side),
    .obs_roi_x0(obs_roi_x0),
    .obs_roi_y0(obs_roi_y0),
    .obs_ts(obs_ts),
    .roi_buffer_id(roi_buffer_id),
    .roi_busy(roi_busy),
    .roi_done(roi_done),
    .roi_error(roi_error),
    .roi_side(roi_side),
    .roi_start(roi_start),
    .roi_tag(roi_tag),
    .roi_write_bank(roi_write_bank),
    .roi_x0(roi_x0),
    .roi_y0(roi_y0),
    .rst_100mhz_n(rst_100mhz_n),
    .scheduler_state_unused(scheduler_state_unused),
    .snapshot_enable(snapshot_enable),
    .stable_class(stable_class),
    .top1_cell(top1_cell),
    .top1_confidence(top1_confidence),
    .top1_dx(top1_dx),
    .top1_dy(top1_dy),
    .top1_height(top1_height),
    .top1_width(top1_width)
);
vision_roi_memory_pipeline #(
    .LOCATOR_MODEL_FILE(LOCATOR_MODEL_FILE),
    .CLASSIFIER_WEIGHT_FILE(CLASSIFIER_WEIGHT_FILE),
    .CLASSIFIER_DESC_FILE(CLASSIFIER_DESC_FILE),
    .GEOMETRY_ALPHA_FILE(GEOMETRY_ALPHA_FILE),
    .HD_PREVIEW(HD_PREVIEW),
    .CLASSIFIER_LANES(CLASSIFIER_LANES),
    .GEOMETRY_EMA(GEOMETRY_EMA),
    .CAMERA_CONTROL(CAMERA_CONTROL),
    .OBJECT_HOLD_MS(OBJECT_HOLD_MS),
    .PALM_HOLD_MS(PALM_HOLD_MS),
    .FIST_HOLD_MS(FIST_HOLD_MS),
    .OV5640_INIT_FILE(OV5640_INIT_FILE),
    .CONFIRM_COUNTS(CONFIRM_COUNTS),
    .GATED_CODES(GATED_CODES),
    .MARGIN_MIN(MARGIN_MIN)
) u_roi_memory(
    .classifier_input_addr(classifier_input_addr),
    .camera_buffer_valid(camera_buffer_valid),
    .camera_frame_id_0(camera_frame_id_0),
    .camera_frame_id_1(camera_frame_id_1),
    .camera_mem_we(camera_mem_we),
    .camera_mem_write_addr(camera_mem_write_addr),
    .camera_mem_write_data(camera_mem_write_data),
    .camera_read_addr(camera_read_addr),
    .camera_read_data(camera_read_data),
    .camera_read_en(camera_read_en),
    .classifier_input_data(classifier_input_data),
    .classifier_input_en(classifier_input_en),
    .classifier_read_bank(classifier_read_bank),
    .clk_100mhz(clk_100mhz),
    .locator_busy(locator_busy),
    .roi_buffer_id(roi_buffer_id),
    .roi_busy(roi_busy),
    .roi_done(roi_done),
    .roi_error(roi_error),
    .roi_read_addr(roi_read_addr),
    .roi_read_en(roi_read_en),
    .roi_start(roi_start),
    .roi_tag(roi_tag),
    .roi_write_bank(roi_write_bank),
    .rst_100mhz_n(rst_100mhz_n),
    .small_side(small_side),
    .small_x(small_x),
    .small_y(small_y)
);
vision_classifier_compute #(
    .LOCATOR_MODEL_FILE(LOCATOR_MODEL_FILE),
    .CLASSIFIER_WEIGHT_FILE(CLASSIFIER_WEIGHT_FILE),
    .CLASSIFIER_DESC_FILE(CLASSIFIER_DESC_FILE),
    .GEOMETRY_ALPHA_FILE(GEOMETRY_ALPHA_FILE),
    .HD_PREVIEW(HD_PREVIEW),
    .CLASSIFIER_LANES(CLASSIFIER_LANES),
    .GEOMETRY_EMA(GEOMETRY_EMA),
    .CAMERA_CONTROL(CAMERA_CONTROL),
    .OBJECT_HOLD_MS(OBJECT_HOLD_MS),
    .PALM_HOLD_MS(PALM_HOLD_MS),
    .FIST_HOLD_MS(FIST_HOLD_MS),
    .OV5640_INIT_FILE(OV5640_INIT_FILE),
    .CONFIRM_COUNTS(CONFIRM_COUNTS),
    .GATED_CODES(GATED_CODES),
    .MARGIN_MIN(MARGIN_MIN)
) u_classifier_compute(
    .classifier_busy(classifier_busy),
    .classifier_class(classifier_class),
    .classifier_done(classifier_done),
    .classifier_input_addr(classifier_input_addr),
    .classifier_input_data(classifier_input_data),
    .classifier_input_en(classifier_input_en),
    .classifier_margin(classifier_margin),
    .classifier_start(classifier_start),
    .clk_100mhz(clk_100mhz),
    .rst_100mhz_n(rst_100mhz_n)
);

endmodule
