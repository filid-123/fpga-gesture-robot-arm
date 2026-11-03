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

    wire init_cmd_valid, init_cmd_ready, init_cmd_read;
    wire [6:0] init_device_addr;
    wire [15:0] init_register_addr;
    wire [7:0] init_write_data;
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

    ov5640_init_fsm #(.INIT_FILE(OV5640_INIT_FILE)) u_camera_init (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n), .xclk_locked(xclk_locked),
        .camera_reset_n(camera_reset_n), .camera_pwdn(camera_pwdn),
        .cmd_valid(init_cmd_valid), .cmd_ready(init_cmd_ready),
        .cmd_read(init_cmd_read), .device_addr(init_device_addr),
        .register_addr(init_register_addr), .write_data(init_write_data),
        .cmd_done(sccb_done), .cmd_ack_error(sccb_ack_error),
        .init_done(camera_init_done), .init_error(camera_init_error)
    );

    // SCCB SDA is an external asynchronous input. At 100 kHz it is stable
    // for microseconds before the ACK/read sample; two 100 MHz stages preserve
    // that phase while keeping metastability out of the command state machine.
    (* ASYNC_REG = "TRUE" *) reg sccb_sda_meta, sccb_sda_sync;
    always @(posedge clk_100mhz) begin
        if(!rst_100mhz_n) begin sccb_sda_meta<=1'b1; sccb_sda_sync<=1'b1; end
        else begin sccb_sda_meta<=sccb_sda_in; sccb_sda_sync<=sccb_sda_meta; end
    end
    sccb_master_sync u_sccb (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n),
        .cmd_valid(runtime_select ? camera_cmd_start : init_cmd_valid), .cmd_ready(master_ready),
        .cmd_read(runtime_select ? camera_cmd_read : init_cmd_read), .device_addr(init_device_addr),
        .register_addr(runtime_select ? camera_cmd_addr : init_register_addr),
        .write_data(runtime_select ? camera_cmd_data : init_write_data),
        .read_data(sccb_read_data_unused), .busy(sccb_busy_unused),
        .done(sccb_done), .ack_error(sccb_ack_error),
        .scl_drive_low(sccb_scl_drive_low),
        .sda_drive_low(sccb_sda_drive_low), .sda_in(sccb_sda_sync)
    );

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

    ov5640_phase2_frontend #(.HD_PREVIEW(HD_PREVIEW),
        .Y_BYTE_PHASE(0),.VSYNC_ACTIVE_HIGH(1),.FIFO_ADDR_WIDTH(10)
    ) u_camera_frontend (
        .preview_we(debug_preview_we),.preview_addr(debug_preview_addr),.preview_data(debug_preview_data),.preview_published(debug_preview_published),.preview_id(debug_preview_id),
        .pclk(pclk),.pclk_rst_n(pclk_rst_n),.dvp_data(dvp_data),
        .dvp_href(dvp_href),.dvp_vsync(dvp_vsync),.capture_enable(capture_enable),
        .sys_clk(clk_100mhz),.sys_rst_n(rst_100mhz_n),.buffer_release(effective_release),
        .buffer_valid_mask(camera_buffer_valid),.buffer_frame_id_0(camera_frame_id_0),
        .buffer_frame_id_1(camera_frame_id_1),.frame_published(camera_frame_published),
        .latest_buffer_id(camera_latest_buffer),.latest_frame_id(camera_latest_frame_id),
        .mem_we(camera_mem_we),.mem_word_addr(camera_mem_write_addr),.mem_wdata(camera_mem_write_data),
        .buffer_timestamp_ms_0(frame_timestamp_ms_0),.buffer_timestamp_ms_1(frame_timestamp_ms_1),.now_ms(now_ms),
        .frame_drop_count(frame_drop_count),.format_error_count(format_error_count),.fifo_overflow_sticky(fifo_overflow)
    );

    wire locator_start, locator_input_buffer;
    wire [31:0] locator_frame_id;
    wire locator_input_en;
    wire [12:0] locator_input_addr;
    wire [31:0] camera_read_data;
    wire locator_output_we;
    wire [11:0] locator_output_addr;
    wire [31:0] locator_output_data;
    wire [7:0] locator_model_en;
    wire [95:0] locator_model_addr;
    wire [255:0] locator_model_data;
    wire locator_busy, locator_done, locator_input_release_unused;
    wire locator_stall_unused, locator_debug_acc_valid_unused;
    wire [2:0] locator_debug_layer_unused;
    wire [17:0] locator_debug_acc_index_unused;
    wire [31:0] locator_debug_acc_data_unused;
    wire locator_debug_act_valid_unused;
    wire [14:0] locator_debug_act_index_unused;
    wire [7:0] locator_debug_act_data_unused;

    locator_context_rom_8lane #(.MEM_INIT_FILE(LOCATOR_MODEL_FILE))
    u_locator_model (
        .clk(clk_100mhz), .lane_rd_en(locator_model_en),
        .lane_rd_addr(locator_model_addr), .lane_rd_data(locator_model_data)
    );

    locator_cnn_engine_context_8lane u_locator (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n), .start(locator_start),
        .input_buffer_id(locator_input_buffer), .output_buffer_id(1'b0),
        .frame_id(locator_frame_id), .input_bram_en(locator_input_en),
        .input_bram_addr(locator_input_addr), .input_bram_data(camera_read_data),
        .output_bram_we(locator_output_we), .output_bram_addr(locator_output_addr),
        .output_bram_data(locator_output_data), .model_lane_rd_en(locator_model_en),
        .model_lane_rd_addr(locator_model_addr), .model_lane_rd_data(locator_model_data),
        .busy(locator_busy), .done(locator_done),
        .input_release(locator_input_release_unused), .stall(locator_stall_unused),
        .debug_acc_valid(locator_debug_acc_valid_unused),
        .debug_layer(locator_debug_layer_unused),
        .debug_acc_index(locator_debug_acc_index_unused),
        .debug_acc_data(locator_debug_acc_data_unused),
        .debug_act_valid(locator_debug_act_valid_unused),
        .debug_act_index(locator_debug_act_index_unused),
        .debug_act_data(locator_debug_act_data_unused)
    );

    wire [31:0] top1_cell, top1_confidence, top1_dx, top1_dy;
    wire [31:0] top1_width, top1_height;
    wire [31:0] top1_bank1_cell_unused, top1_bank1_conf_unused;
    wire [31:0] top1_bank1_dx_unused, top1_bank1_dy_unused;
    wire [31:0] top1_bank1_width_unused, top1_bank1_height_unused;

    locator_top1_reducer u_top1 (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n), .start(locator_start),
        .output_buffer_id(1'b0), .done(locator_done),
        .output_we(locator_output_we), .output_addr(locator_output_addr),
        .output_data(locator_output_data), .top1_cell_0(top1_cell),
        .top1_conf_0(top1_confidence), .top1_dx_0(top1_dx),
        .top1_dy_0(top1_dy), .top1_width_0(top1_width),
        .top1_height_0(top1_height), .top1_cell_1(top1_bank1_cell_unused),
        .top1_conf_1(top1_bank1_conf_unused),
        .top1_dx_1(top1_bank1_dx_unused), .top1_dy_1(top1_bank1_dy_unused),
        .top1_width_1(top1_bank1_width_unused),
        .top1_height_1(top1_bank1_height_unused)
    );

    wire bbox_start, bbox_busy, bbox_done, bbox_detected;
    wire [7:0] bbox_cell;
    wire signed [31:0] bbox_confidence, bbox_dx, bbox_dy;
    wire signed [31:0] bbox_width, bbox_height;
    wire [9:0] bbox_roi_x0, bbox_roi_y0, bbox_roi_side;
    wire [8:0] bbox_raw_x0, bbox_raw_y0, bbox_raw_x1, bbox_raw_y1;
    wire [8:0] bbox_ema_x0, bbox_ema_y0, bbox_ema_x1, bbox_ema_y1;

    always @(posedge clk_100mhz) begin
        if(!rst_100mhz_n) job_timestamp_ms<=0;
        else if(locator_start) job_timestamp_ms<=locator_input_buffer?frame_timestamp_ms_1:frame_timestamp_ms_0;
    end
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

    wire roi_start, roi_buffer_id;
    wire [9:0] roi_x0, roi_y0, roi_side;
    wire [31:0] roi_tag;
    wire roi_read_en;
    wire [12:0] roi_read_addr;
    wire roi_done, roi_error;
    wire [31:0] roi_completed_tag_unused, roi_completed_frame_unused;
    wire roi_word_we;
    wire [7:0] roi_word_addr;
    wire [31:0] roi_word_data;
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

    camera_locator_input_bram #(.ADDR_BITS(13)) u_camera_memory (
        .clk(clk_100mhz), .camera_we(camera_mem_we),
        .camera_word_addr(camera_mem_write_addr), .camera_wdata(camera_mem_write_data),
        .locator_en(camera_read_en), .locator_word_addr(camera_read_addr),
        .locator_rdata(camera_read_data)
    );

    same_frame_roi_128x128 u_same_frame_roi (
        .clk(clk_100mhz),.rst_n(rst_100mhz_n),.start(roi_start),.buffer_id(roi_buffer_id),
        .desc_x0(small_x),.desc_y0(small_y),.desc_side(small_side),.desc_tag(roi_tag),
        .buffer_valid_mask(camera_buffer_valid),.buffer_frame_id_0(camera_frame_id_0),.buffer_frame_id_1(camera_frame_id_1),
        .read_grant(!locator_busy),.camera_read_en(roi_read_en),.camera_read_word_addr(roi_read_addr),.camera_read_data(camera_read_data),
        .busy(roi_busy),.done_pulse(roi_done),.error_pulse(roi_error),
        .completed_tag(roi_completed_tag_unused),.completed_source_frame_id(roi_completed_frame_unused),
        .roi_word_we(roi_word_we),.roi_word_addr(roi_word_addr),.roi_word_data(roi_word_data));
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
    wire classifier_desc_en;
    wire [7:0] classifier_desc_addr;
    wire [31:0] classifier_desc_data;
    wire classifier_weight2_en;wire[15:0]classifier_weight2_addr;wire[7:0]classifier_weight2_data;
    wire classifier_weight_en;
    wire [15:0] classifier_weight_addr;
    wire [7:0] classifier_weight_data;
    wire classifier_input_en;
    wire [13:0] classifier_input_addr;
    wire [7:0] classifier_input_data;

    classifier_roi_pingpong u_classifier_input (
        .clk(clk_100mhz), .wr_en(roi_word_we),.wr_bank(roi_write_bank),
        .wr_word_addr(roi_word_addr), .wr_data(roi_word_data),
        .rd_en(classifier_input_en),.rd_bank(classifier_read_bank),
        .rd_byte_addr(classifier_input_addr[9:0]), .rd_data(classifier_input_data)
    );

    cnn_desc_mem #(.MEM_INIT_FILE(CLASSIFIER_DESC_FILE)) u_classifier_desc (
        .clk(clk_100mhz), .wr_en(1'b0), .wr_addr(8'd0), .wr_data(32'd0),
        .rd_en(classifier_desc_en), .rd_addr(classifier_desc_addr),
        .rd_data(classifier_desc_data)
    );

    cnn_weight_rom_compact #(.MEM_INIT_FILE(CLASSIFIER_WEIGHT_FILE),.WORDS(9872),.READ_PORTS(CLASSIFIER_LANES)) u_classifier_weights (
        .clk(clk_100mhz), .we_a(1'b0), .addr_a(16'd0), .din_a(32'd0),
        .dout_a(), .en_b(classifier_weight_en), .addr_b(classifier_weight_addr),
        .dout_b(classifier_weight_data),.en_c(classifier_weight2_en),.addr_c(classifier_weight2_addr),.dout_c(classifier_weight2_data)
    );

    cnn_core_7c #(.CONV_LANES(CLASSIFIER_LANES),.DENSE_PIPELINED_REQUANT(1),.FIXED_SHIFT31(1)) u_classifier (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n), .start(classifier_start),
        .busy(classifier_busy), .done(classifier_done),
        .desc_bram_en(classifier_desc_en), .desc_bram_addr(classifier_desc_addr),
        .desc_bram_data(classifier_desc_data), .w_bram_en(classifier_weight_en),
        .w_bram_addr(classifier_weight_addr), .w_bram_data(classifier_weight_data),
        .w2_bram_en(classifier_weight2_en),.w2_bram_addr(classifier_weight2_addr),.w2_bram_data(classifier_weight2_data),
        .in_bram_en(classifier_input_en), .in_bram_addr(classifier_input_addr),
        .in_bram_data(classifier_input_data), .final_class_id(classifier_class),
        .final_margin(classifier_margin)
    );

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
    wire stable_changed_unused;
    wire [2:0] gated_class_unused;
    wire [3:0] class_leds;
    wire fatal_error;
    wire[31:0]obs_id,obs_ts;wire obs_detected;
    wire[2:0]obs_model;
    wire[8:0]obs_raw_x0,obs_raw_y0,obs_raw_x1,obs_raw_y1;
    wire[8:0]obs_ema_x0,obs_ema_y0,obs_ema_x1,obs_ema_y1;
    wire[9:0]obs_roi_x0,obs_roi_y0,obs_roi_side;
    wire signed[31:0]obs_conf;


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

    wire filter_valid;
    gesture_time_filter #(.MARGIN_MIN(MARGIN_MIN),.OBJECT_HOLD_MS(OBJECT_HOLD_MS),
        .PALM_HOLD_MS(PALM_HOLD_MS),.FIST_HOLD_MS(FIST_HOLD_MS),
        .OBJECT_MIN_FRAMES(3),.PALM_MIN_FRAMES(3),.FIST_MIN_FRAMES(2)) u_confirm (
        .clk(clk_100mhz),.rst_n(rst_100mhz_n),.now_ms(now_ms),
        .frame_timestamp_ms(obs_ts),.frame_id(obs_id),
        .candidate_valid(class_candidate_valid),.candidate_class(class_candidate),
        .candidate_margin(class_candidate_margin),.output_class(stable_class),
        .output_changed(stable_changed_unused),.output_valid(filter_valid),
        .gated_class(gated_class_unused),.leds(class_leds));
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
endmodule
