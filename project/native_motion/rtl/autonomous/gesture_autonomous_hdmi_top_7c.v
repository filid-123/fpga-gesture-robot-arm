// gesture_autonomous_hdmi_top_7c (Phase 3 S3): generated from the unchanged
// gesture_autonomous_hdmi_top.v; instantiates gesture_autonomous_top_v5_7c and
// hdmi_debug_output_7c (seven-class labels, 7 = NO DETECTION).
// HDMI debug wrapper around the timing-closed autonomous gesture pipeline.
// The inference path is unchanged; the display branch only consumes registered
// camera writes and result metadata.
`timescale 1ns / 1ps

module gesture_autonomous_hdmi_top_7c #(
    parameter LOCATOR_MODEL_FILE     = "locator_model_blob.mem",
    parameter CLASSIFIER_WEIGHT_FILE = "weights_all.mem",
    parameter CLASSIFIER_DESC_FILE   = "layer_descriptors.mem",
    parameter OV5640_INIT_FILE       = "ov5640_vga_yuyv.mem"
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
    input  wire       hdmi_pixel_clk,
    input  wire       hdmi_pixel_clk_5x,
    input  wire       hdmi_pixel_rst_n,
    output wire       camera_reset_n,
    output wire       camera_pwdn,
    output wire       sccb_scl_drive_low,
    output wire       sccb_sda_drive_low,
    input  wire       sccb_sda_in,
    output wire [3:0] leds,
    output wire       hdmi_clk_p,
    output wire       hdmi_clk_n,
    output wire [2:0] hdmi_data_p,
    output wire [2:0] hdmi_data_n
);
    wire debug_camera_we;
    wire [12:0] debug_camera_word_addr;
    wire [31:0] debug_camera_wdata;
    wire debug_camera_frame_published;
    wire [31:0] debug_camera_latest_frame_id;
    wire debug_result_valid;
    wire [31:0] debug_result_frame_id;
    wire debug_result_detected;
    wire [8:0] debug_raw_x0, debug_raw_y0, debug_raw_x1, debug_raw_y1;
    wire [8:0] debug_ema_x0, debug_ema_y0, debug_ema_x1, debug_ema_y1;
    wire [9:0] debug_roi_x0, debug_roi_y0, debug_roi_side;
    wire [2:0] debug_candidate_class, debug_stable_class;

    gesture_autonomous_top_v5_7c #(
        .LOCATOR_MODEL_FILE(LOCATOR_MODEL_FILE),
        .CLASSIFIER_WEIGHT_FILE(CLASSIFIER_WEIGHT_FILE),
        .CLASSIFIER_DESC_FILE(CLASSIFIER_DESC_FILE),
        .OV5640_INIT_FILE(OV5640_INIT_FILE)
    ) u_autonomous (
        .clk_100mhz(clk_100mhz), .rst_100mhz_n(rst_100mhz_n),
        .clk_50mhz(clk_50mhz), .rst_50mhz_n(rst_50mhz_n),
        .pclk(pclk), .pclk_rst_n(pclk_rst_n),
        .dvp_data(dvp_data), .dvp_href(dvp_href), .dvp_vsync(dvp_vsync),
        .xclk_locked(xclk_locked),
        .camera_reset_n(camera_reset_n), .camera_pwdn(camera_pwdn),
        .sccb_scl_drive_low(sccb_scl_drive_low),
        .sccb_sda_drive_low(sccb_sda_drive_low),
        .sccb_sda_in(sccb_sda_in), .leds(leds),
        .debug_camera_we(debug_camera_we),
        .debug_camera_word_addr(debug_camera_word_addr),
        .debug_camera_wdata(debug_camera_wdata),
        .debug_camera_frame_published(debug_camera_frame_published),
        .debug_camera_latest_frame_id(debug_camera_latest_frame_id),
        .debug_result_valid(debug_result_valid),
        .debug_result_frame_id(debug_result_frame_id),
        .debug_result_detected(debug_result_detected),
        .debug_raw_x0(debug_raw_x0), .debug_raw_y0(debug_raw_y0),
        .debug_raw_x1(debug_raw_x1), .debug_raw_y1(debug_raw_y1),
        .debug_ema_x0(debug_ema_x0), .debug_ema_y0(debug_ema_y0),
        .debug_ema_x1(debug_ema_x1), .debug_ema_y1(debug_ema_y1),
        .debug_roi_x0(debug_roi_x0), .debug_roi_y0(debug_roi_y0),
        .debug_roi_side(debug_roi_side),
        .debug_candidate_class(debug_candidate_class),
        .debug_stable_class(debug_stable_class)
    );

    hdmi_debug_output_7c u_hdmi (
        .sys_clk(clk_100mhz), .sys_rst_n(rst_100mhz_n),
        .pixel_clk(hdmi_pixel_clk), .pixel_clk_5x(hdmi_pixel_clk_5x),
        .pixel_rst_n(hdmi_pixel_rst_n),
        .camera_we(debug_camera_we),
        .camera_word_addr(debug_camera_word_addr),
        .camera_wdata(debug_camera_wdata),
        .camera_frame_published(debug_camera_frame_published),
        .camera_latest_frame_id(debug_camera_latest_frame_id),
        .result_valid(debug_result_valid),
        .result_frame_id(debug_result_frame_id),
        .result_detected(debug_result_detected),
        .result_raw_x0(debug_raw_x0), .result_raw_y0(debug_raw_y0),
        .result_raw_x1(debug_raw_x1), .result_raw_y1(debug_raw_y1),
        .result_ema_x0(debug_ema_x0), .result_ema_y0(debug_ema_y0),
        .result_ema_x1(debug_ema_x1), .result_ema_y1(debug_ema_y1),
        .result_roi_x0(debug_roi_x0), .result_roi_y0(debug_roi_y0),
        .result_roi_side(debug_roi_side),
        .result_candidate_class(debug_candidate_class),
        .stable_class(debug_stable_class),
        .tmds_clk_p(hdmi_clk_p), .tmds_clk_n(hdmi_clk_n),
        .tmds_data_p(hdmi_data_p), .tmds_data_n(hdmi_data_n)
    );
endmodule
