// ============================================================================
// gesture_autonomous_top_v5_7c (Phase 3 S3).  Generated from the unchanged
// gesture_autonomous_top_v5.v, the top of both implemented four-class builds
// (final flow after update_phase2_l2_autonomous_final_timing.tcl, HDMI debug).
// Seven-class changes: cnn_core_7c (7 logits, top1-top2 margin), *_7c
// scheduler/CDC/confirm filter, NO_DETECTION = 7, LEDs {1, class} (0000 no
// detection, 1111 fatal); debug_candidate_class / debug_stable_class carry
// seven-class codes.  CONFIRM_COUNTS / GATED_CODES / MARGIN_MIN: see
// class_confirm_filter_7c (MARGIN_MIN = 0: margin gate off).
// ----------------------------------------------------------------------------
// Phase 2-L2 autonomous production top, timing-closed bbox pipeline revision.
// PS is limited to clocks/reset and initial bitstream loading.  Runtime has no
// AXI control, USB, model writer, model CRC, output-map BRAM or interrupt path.
// ============================================================================
`timescale 1ns / 1ps

module gesture_autonomous_top_v5_7c #(
    parameter LOCATOR_MODEL_FILE     = "locator_model_blob.mem",
    parameter CLASSIFIER_WEIGHT_FILE = "weights_all.mem",
    parameter CLASSIFIER_DESC_FILE   = "layer_descriptors.mem",
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
    output wire [3:0] leds,
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
    output wire [2:0] debug_stable_class
);

    wire init_cmd_valid, init_cmd_ready, init_cmd_read;
    wire [6:0] init_device_addr;
    wire [15:0] init_register_addr;
    wire [7:0] init_write_data;
    wire sccb_done, sccb_ack_error;
    wire [7:0] sccb_read_data_unused;
    wire sccb_busy_unused, camera_init_done, camera_init_error;

    ov5640_init_fsm #(.INIT_FILE(OV5640_INIT_FILE)) u_camera_init (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n), .xclk_locked(xclk_locked),
        .camera_reset_n(camera_reset_n), .camera_pwdn(camera_pwdn),
        .cmd_valid(init_cmd_valid), .cmd_ready(init_cmd_ready),
        .cmd_read(init_cmd_read), .device_addr(init_device_addr),
        .register_addr(init_register_addr), .write_data(init_write_data),
        .cmd_done(sccb_done), .cmd_ack_error(sccb_ack_error),
        .init_done(camera_init_done), .init_error(camera_init_error)
    );

    sccb_master_sync u_sccb (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n),
        .cmd_valid(init_cmd_valid), .cmd_ready(init_cmd_ready),
        .cmd_read(init_cmd_read), .device_addr(init_device_addr),
        .register_addr(init_register_addr), .write_data(init_write_data),
        .read_data(sccb_read_data_unused), .busy(sccb_busy_unused),
        .done(sccb_done), .ack_error(sccb_ack_error),
        .scl_drive_low(sccb_scl_drive_low),
        .sda_drive_low(sccb_sda_drive_low), .sda_in(sccb_sda_in)
    );

    wire capture_enable_request;
    reg capture_enable;
    wire [1:0] camera_buffer_release, camera_buffer_valid;
    wire [31:0] camera_frame_id_0, camera_frame_id_1;
    wire camera_frame_published, camera_latest_buffer;
    wire [31:0] camera_latest_frame_id;
    wire camera_mem_we;
    wire [12:0] camera_mem_write_addr;
    wire [31:0] camera_mem_write_data;
    wire [31:0] frame_drop_count_unused, format_error_count_unused;
    wire fifo_overflow;
    wire stream_roi_armed_unused, stream_roi_busy_unused;
    wire stream_roi_done_unused, stream_roi_error_unused;
    wire [31:0] stream_roi_tag_unused, stream_roi_frame_unused;
    wire stream_roi_we_unused;
    wire [7:0] stream_roi_addr_unused;
    wire [31:0] stream_roi_data_unused;

    always @(posedge clk_100mhz) begin
        if (!rst_100mhz_n)
            capture_enable <= 1'b0;
        else
            capture_enable <= capture_enable_request;
    end

    ov5640_l2_frontend #(
        .Y_BYTE_PHASE(0), .VSYNC_ACTIVE_HIGH(1), .FIFO_ADDR_WIDTH(10)
    ) u_camera_frontend (
        .pclk(pclk), .pclk_rst_n(pclk_rst_n), .dvp_data(dvp_data),
        .dvp_href(dvp_href), .dvp_vsync(dvp_vsync),
        .capture_enable(capture_enable), .sys_clk(clk_100mhz),
        .sys_rst_n(rst_100mhz_n), .buffer_release(camera_buffer_release),
        .roi_desc_arm(1'b0), .roi_desc_x0(10'd0), .roi_desc_y0(10'd0),
        .roi_desc_side(10'd1), .roi_desc_tag(32'd0),
        .buffer_valid_mask(camera_buffer_valid),
        .buffer_frame_id_0(camera_frame_id_0),
        .buffer_frame_id_1(camera_frame_id_1),
        .frame_published(camera_frame_published),
        .latest_buffer_id(camera_latest_buffer),
        .latest_frame_id(camera_latest_frame_id),
        .mem_we(camera_mem_we), .mem_word_addr(camera_mem_write_addr),
        .mem_wdata(camera_mem_write_data),
        .roi_desc_armed(stream_roi_armed_unused),
        .roi_busy(stream_roi_busy_unused),
        .roi_done_pulse(stream_roi_done_unused),
        .roi_error_pulse(stream_roi_error_unused),
        .roi_completed_tag(stream_roi_tag_unused),
        .roi_source_frame_id(stream_roi_frame_unused),
        .roi_word_we(stream_roi_we_unused),
        .roi_word_addr(stream_roi_addr_unused),
        .roi_word_data(stream_roi_data_unused),
        .frame_drop_count(frame_drop_count_unused),
        .format_error_count(format_error_count_unused),
        .fifo_overflow_sticky(fifo_overflow)
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
    wire [87:0] locator_model_addr;
    wire [255:0] locator_model_data;
    wire locator_busy, locator_done, locator_input_release_unused;
    wire locator_stall_unused, locator_debug_acc_valid_unused;
    wire [2:0] locator_debug_layer_unused;
    wire [17:0] locator_debug_acc_index_unused;
    wire [31:0] locator_debug_acc_data_unused;
    wire locator_debug_act_valid_unused;
    wire [14:0] locator_debug_act_index_unused;
    wire [7:0] locator_debug_act_data_unused;

    locator_model_rom_8lane #(.MEM_INIT_FILE(LOCATOR_MODEL_FILE))
    u_locator_model (
        .clk(clk_100mhz), .lane_rd_en(locator_model_en),
        .lane_rd_addr(locator_model_addr), .lane_rd_data(locator_model_data)
    );

    locator_cnn_engine_8lane u_locator (
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

    locator_bbox_roi_fixed_v4 u_bbox (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n), .start(bbox_start),
        .cell_index(bbox_cell), .confidence_i32(bbox_confidence),
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
    wire roi_busy, roi_done, roi_error;
    wire [31:0] roi_completed_tag_unused, roi_completed_frame_unused;
    wire roi_word_we;
    wire [7:0] roi_word_addr;
    wire [31:0] roi_word_data;
    wire camera_read_en = locator_busy ? locator_input_en :
                          roi_busy ? roi_read_en : 1'b0;
    wire [12:0] camera_read_addr = locator_busy ? locator_input_addr : roi_read_addr;

    camera_locator_input_bram u_camera_memory (
        .clk(clk_100mhz), .camera_we(camera_mem_we),
        .camera_word_addr(camera_mem_write_addr), .camera_wdata(camera_mem_write_data),
        .locator_en(camera_read_en), .locator_word_addr(camera_read_addr),
        .locator_rdata(camera_read_data)
    );

    same_frame_roi_128x128 u_same_frame_roi (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n), .start(roi_start),
        .buffer_id(roi_buffer_id), .desc_x0(roi_x0), .desc_y0(roi_y0),
        .desc_side(roi_side), .desc_tag(roi_tag),
        .buffer_valid_mask(camera_buffer_valid),
        .buffer_frame_id_0(camera_frame_id_0),
        .buffer_frame_id_1(camera_frame_id_1), .read_grant(!locator_busy),
        .camera_read_en(roi_read_en), .camera_read_word_addr(roi_read_addr),
        .camera_read_data(camera_read_data), .busy(roi_busy),
        .done_pulse(roi_done), .error_pulse(roi_error),
        .completed_tag(roi_completed_tag_unused),
        .completed_source_frame_id(roi_completed_frame_unused),
        .roi_word_we(roi_word_we), .roi_word_addr(roi_word_addr),
        .roi_word_data(roi_word_data)
    );

    wire classifier_request, classifier_request_busy;
    wire classifier_result_pulse;
    wire [8:0] classifier_result_class;
    wire [15:0] classifier_result_margin;
    wire classifier_start, classifier_busy, classifier_done;
    wire [8:0] classifier_class;
    wire [15:0] classifier_margin;
    wire classifier_desc_en;
    wire [7:0] classifier_desc_addr;
    wire [31:0] classifier_desc_data;
    wire classifier_weight_en;
    wire [15:0] classifier_weight_addr;
    wire [7:0] classifier_weight_data;
    wire classifier_input_en;
    wire [13:0] classifier_input_addr;
    wire [7:0] classifier_input_data;

    classifier_roi_bram u_classifier_input (
        .wr_clk(clk_100mhz), .wr_en(roi_word_we),
        .wr_word_addr(roi_word_addr), .wr_data(roi_word_data),
        .rd_clk(clk_50mhz), .rd_en(classifier_input_en),
        .rd_byte_addr(classifier_input_addr[9:0]), .rd_data(classifier_input_data)
    );

    cnn_desc_mem #(.MEM_INIT_FILE(CLASSIFIER_DESC_FILE)) u_classifier_desc (
        .clk(clk_50mhz), .wr_en(1'b0), .wr_addr(8'd0), .wr_data(32'd0),
        .rd_en(classifier_desc_en), .rd_addr(classifier_desc_addr),
        .rd_data(classifier_desc_data)
    );

    weight_bram #(.MEM_INIT_FILE(CLASSIFIER_WEIGHT_FILE)) u_classifier_weights (
        .clk(clk_50mhz), .we_a(1'b0), .addr_a(16'd0), .din_a(32'd0),
        .dout_a(), .en_b(classifier_weight_en), .addr_b(classifier_weight_addr),
        .dout_b(classifier_weight_data)
    );

    cnn_core_7c u_classifier (
        .clk(clk_50mhz), .rst_n(rst_50mhz_n), .start(classifier_start),
        .busy(classifier_busy), .done(classifier_done),
        .desc_bram_en(classifier_desc_en), .desc_bram_addr(classifier_desc_addr),
        .desc_bram_data(classifier_desc_data), .w_bram_en(classifier_weight_en),
        .w_bram_addr(classifier_weight_addr), .w_bram_data(classifier_weight_data),
        .in_bram_en(classifier_input_en), .in_bram_addr(classifier_input_addr),
        .in_bram_data(classifier_input_data), .final_class_id(classifier_class),
        .final_margin(classifier_margin)
    );

    classifier_cdc_bridge_7c u_classifier_bridge (
        .sys_clk(clk_100mhz), .sys_rst_n(rst_100mhz_n),
        .request_pulse(classifier_request), .request_busy(classifier_request_busy),
        .result_pulse(classifier_result_pulse), .result_class(classifier_result_class),
        .result_margin(classifier_result_margin),
        .classifier_clk(clk_50mhz), .classifier_rst_n(rst_50mhz_n),
        .classifier_start(classifier_start), .classifier_busy(classifier_busy),
        .classifier_done(classifier_done), .classifier_class(classifier_class),
        .classifier_margin(classifier_margin)
    );

    wire class_candidate_valid;
    wire [2:0] class_candidate, stable_class;
    wire [15:0] class_candidate_margin;
    wire stable_changed_unused;
    wire [2:0] gated_class_unused;
    wire [3:0] class_leds;
    wire fatal_error;
    wire [3:0] scheduler_state_unused;

    autonomous_pipeline_ctrl_7c #(.NUM_CLASSES(7)) u_scheduler (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n),
        .camera_init_done(camera_init_done), .camera_init_error(camera_init_error),
        .fifo_overflow(fifo_overflow), .camera_buffer_valid(camera_buffer_valid),
        .camera_latest_buffer(camera_latest_buffer),
        .camera_frame_id_0(camera_frame_id_0), .camera_frame_id_1(camera_frame_id_1),
        .capture_enable(capture_enable_request),
        .camera_buffer_release(camera_buffer_release),
        .locator_busy(locator_busy), .locator_done(locator_done),
        .locator_start(locator_start), .locator_input_buffer(locator_input_buffer),
        .locator_frame_id(locator_frame_id), .top1_cell(top1_cell),
        .top1_confidence(top1_confidence), .top1_dx(top1_dx), .top1_dy(top1_dy),
        .top1_width(top1_width), .top1_height(top1_height),
        .bbox_start(bbox_start), .bbox_busy(bbox_busy), .bbox_done(bbox_done),
        .bbox_detected(bbox_detected), .bbox_cell(bbox_cell),
        .bbox_confidence(bbox_confidence), .bbox_dx(bbox_dx), .bbox_dy(bbox_dy),
        .bbox_width(bbox_width), .bbox_height(bbox_height),
        .bbox_roi_x0(bbox_roi_x0), .bbox_roi_y0(bbox_roi_y0),
        .bbox_roi_side(bbox_roi_side), .roi_busy(roi_busy), .roi_done(roi_done),
        .roi_error(roi_error), .roi_start(roi_start), .roi_buffer_id(roi_buffer_id),
        .roi_x0(roi_x0), .roi_y0(roi_y0), .roi_side(roi_side), .roi_tag(roi_tag),
        .classifier_request_busy(classifier_request_busy),
        .classifier_request(classifier_request),
        .classifier_result_pulse(classifier_result_pulse),
        .classifier_result_class(classifier_result_class),
        .classifier_result_margin(classifier_result_margin),
        .class_candidate_valid(class_candidate_valid),
        .class_candidate(class_candidate), .class_candidate_margin(class_candidate_margin),
        .fatal_error(fatal_error),
        .state_debug(scheduler_state_unused)
    );

    class_confirm_filter_7c #(
        .CONFIRM_COUNTS(CONFIRM_COUNTS), .GATED_CODES(GATED_CODES), .MARGIN_MIN(MARGIN_MIN)
    ) u_class_filter (
        .clk(clk_100mhz), .rst_n(rst_100mhz_n),
        .candidate_valid(class_candidate_valid), .candidate_class(class_candidate),
        .candidate_margin(class_candidate_margin),
        .output_class(stable_class), .output_changed(stable_changed_unused),
        .gated_class(gated_class_unused), .leds(class_leds)
    );

    assign leds = fatal_error ? 4'b1111 : class_leds;
    assign debug_camera_we              = camera_mem_we;
    assign debug_camera_word_addr       = camera_mem_write_addr;
    assign debug_camera_wdata           = camera_mem_write_data;
    assign debug_camera_frame_published = camera_frame_published;
    assign debug_camera_latest_frame_id = camera_latest_frame_id;
    assign debug_result_valid           = class_candidate_valid;
    assign debug_result_frame_id        = locator_frame_id;
    assign debug_result_detected        = bbox_detected;
    assign debug_raw_x0                 = bbox_raw_x0;
    assign debug_raw_y0                 = bbox_raw_y0;
    assign debug_raw_x1                 = bbox_raw_x1;
    assign debug_raw_y1                 = bbox_raw_y1;
    assign debug_ema_x0                 = bbox_ema_x0;
    assign debug_ema_y0                 = bbox_ema_y0;
    assign debug_ema_x1                 = bbox_ema_x1;
    assign debug_ema_y1                 = bbox_ema_y1;
    assign debug_roi_x0                 = bbox_roi_x0;
    assign debug_roi_y0                 = bbox_roi_y0;
    assign debug_roi_side               = bbox_roi_side;
    assign debug_candidate_class        = class_candidate;
    assign debug_stable_class           = stable_class;
endmodule
