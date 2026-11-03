// ============================================================================
// autonomous_pipeline_ctrl_7c (Phase 3 S3).  Generated from the unchanged
// autonomous_pipeline_ctrl.v; only the class interface changes:
//   * class codes 0..NUM_CLASSES-1 are classifier results (seven-class model:
//     0 BACKGROUND .. 4 PALM_READY .. 6 OTHER_INVALID);
//   * NO_DETECTION is code 3'd7 (was 3'd4 in the four-class build): Locator
//     miss, ROI error, or a classifier result >= NUM_CLASSES;
//   * the classifier's top1-top2 margin is forwarded with each candidate
//     (0 for NO_DETECTION).
// Frame ownership, engine handshakes and fatal handling are unchanged.
// ----------------------------------------------------------------------------
// Minimal frame-level scheduler for the PS-free production data path.
// Camera, Locator, ROI and classifier remain independently timed engines; this
// FSM owns exactly one retained camera buffer and permits one classifier
// request at a time.
// ============================================================================
`timescale 1ns / 1ps

module autonomous_pipeline_ctrl_7c #(
    parameter integer NUM_CLASSES = 7,
    parameter integer TASK_CLASS_MAP = 0
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        camera_init_done,
    input  wire        camera_init_error,
    input  wire        fifo_overflow,

    input  wire [1:0]  camera_buffer_valid,
    input  wire        camera_latest_buffer,
    input  wire [31:0] camera_frame_id_0,
    input  wire [31:0] camera_frame_id_1,
    output wire        capture_enable,
    output reg  [1:0]  camera_buffer_release,

    input  wire        locator_busy,
    input  wire        locator_done,
    output reg         locator_start,
    output reg         locator_input_buffer,
    output reg  [31:0] locator_frame_id,
    input  wire [31:0] top1_cell,
    input  wire signed [31:0] top1_confidence,
    input  wire signed [31:0] top1_dx,
    input  wire signed [31:0] top1_dy,
    input  wire signed [31:0] top1_width,
    input  wire signed [31:0] top1_height,

    output reg         bbox_start,
    input  wire        bbox_busy,
    input  wire        bbox_done,
    input  wire        bbox_detected,
    output reg  [7:0]  bbox_cell,
    output reg signed [31:0] bbox_confidence,
    output reg signed [31:0] bbox_dx,
    output reg signed [31:0] bbox_dy,
    output reg signed [31:0] bbox_width,
    output reg signed [31:0] bbox_height,
    input  wire [9:0]  bbox_roi_x0,
    input  wire [9:0]  bbox_roi_y0,
    input  wire [9:0]  bbox_roi_side,

    input  wire        roi_busy,
    input  wire        roi_done,
    input  wire        roi_error,
    output reg         roi_start,
    output reg         roi_buffer_id,
    output reg  [9:0]  roi_x0,
    output reg  [9:0]  roi_y0,
    output reg  [9:0]  roi_side,
    output reg  [31:0] roi_tag,

    input  wire        classifier_request_busy,
    output reg         classifier_request,
    input  wire        classifier_result_pulse,
    input  wire [8:0]  classifier_result_class,
    input  wire [15:0] classifier_result_margin,

    output reg         class_candidate_valid,
    output reg  [2:0]  class_candidate,
    output reg  [15:0] class_candidate_margin,
    output reg         fatal_error,
    output reg  [3:0]  state_debug
);

    localparam [3:0] ST_WAIT_INIT    = 4'd0;
    localparam [3:0] ST_WAIT_FRAME   = 4'd1;
    localparam [3:0] ST_START_LOC    = 4'd2;
    localparam [3:0] ST_WAIT_LOC     = 4'd3;
    localparam [3:0] ST_TOP1_SETTLE  = 4'd4;
    localparam [3:0] ST_START_BBOX   = 4'd5;
    localparam [3:0] ST_WAIT_BBOX    = 4'd6;
    localparam [3:0] ST_START_ROI    = 4'd7;
    localparam [3:0] ST_WAIT_ROI     = 4'd8;
    localparam [3:0] ST_START_CLASS  = 4'd9;
    localparam [3:0] ST_WAIT_CLASS   = 4'd10;
    localparam [3:0] ST_FATAL        = 4'd15;
    localparam [2:0] CLASS_NONE      = 3'd7;      // NO_DETECTION sentinel

    reg [3:0] state;
    reg held_camera_buffer;

    // Release is registered. The frame RAM consumes it on the next edge,
    // so its old valid flag must not start another job on that same edge.
    wire [1:0] available_buffers = camera_buffer_valid & ~camera_buffer_release;
    wire latest_is_valid = available_buffers[camera_latest_buffer];
    wire selected_buffer = latest_is_valid ? camera_latest_buffer :
                           available_buffers[1];
    wire [31:0] selected_frame_id = selected_buffer ?
        camera_frame_id_1 : camera_frame_id_0;

    assign capture_enable = camera_init_done && !fatal_error;

    always @(posedge clk) begin
        if (!rst_n) begin
            state                   <= ST_WAIT_INIT;
            held_camera_buffer      <= 1'b0;
            camera_buffer_release   <= 2'b00;
            locator_start           <= 1'b0;
            locator_input_buffer    <= 1'b0;
            locator_frame_id        <= 32'd0;
            bbox_start              <= 1'b0;
            bbox_cell               <= 8'd0;
            bbox_confidence         <= 32'sd0;
            bbox_dx                 <= 32'sd0;
            bbox_dy                 <= 32'sd0;
            bbox_width              <= 32'sd0;
            bbox_height             <= 32'sd0;
            roi_start               <= 1'b0;
            roi_buffer_id           <= 1'b0;
            roi_x0                  <= 10'd0;
            roi_y0                  <= 10'd0;
            roi_side                <= 10'd1;
            roi_tag                 <= 32'd0;
            classifier_request      <= 1'b0;
            class_candidate_valid   <= 1'b0;
            class_candidate         <= CLASS_NONE;
            class_candidate_margin  <= 16'd0;
            fatal_error             <= 1'b0;
            state_debug             <= ST_WAIT_INIT;
        end else begin
            camera_buffer_release <= 2'b00;
            locator_start         <= 1'b0;
            bbox_start            <= 1'b0;
            roi_start             <= 1'b0;
            classifier_request    <= 1'b0;
            class_candidate_valid <= 1'b0;
            state_debug           <= state;

            if (camera_init_error || fifo_overflow) begin
                fatal_error <= 1'b1;
                state <= ST_FATAL;
            end else begin
                case (state)
                    ST_WAIT_INIT: begin
                        if (camera_init_done)
                            state <= ST_WAIT_FRAME;
                    end

                    ST_WAIT_FRAME: begin
                        if (available_buffers != 2'b00) begin
                            held_camera_buffer   <= selected_buffer;
                            locator_input_buffer <= selected_buffer;
                            locator_frame_id     <= selected_frame_id;
                            // Release only an already-published stale buffer;
                            // the selected frame stays owned through ROI.
                            camera_buffer_release <= camera_buffer_valid &
                                ~(selected_buffer ? 2'b10 : 2'b01);
                            state <= ST_START_LOC;
                        end
                    end

                    ST_START_LOC: begin
                        if (!locator_busy) begin
                            locator_start <= 1'b1;
                            state <= ST_WAIT_LOC;
                        end
                    end

                    ST_WAIT_LOC: begin
                        if (locator_done)
                            state <= ST_TOP1_SETTLE;
                    end

                    ST_TOP1_SETTLE: begin
                        bbox_cell       <= top1_cell[7:0];
                        bbox_confidence <= top1_confidence;
                        bbox_dx         <= top1_dx;
                        bbox_dy         <= top1_dy;
                        bbox_width      <= top1_width;
                        bbox_height     <= top1_height;
                        state <= ST_START_BBOX;
                    end

                    ST_START_BBOX: begin
                        if (!bbox_busy) begin
                            bbox_start <= 1'b1;
                            state <= ST_WAIT_BBOX;
                        end
                    end

                    ST_WAIT_BBOX: begin
                        if (bbox_done) begin
                            if (!bbox_detected) begin
                                camera_buffer_release <= held_camera_buffer ?
                                    2'b10 : 2'b01;
                                class_candidate       <= CLASS_NONE;
                                class_candidate_margin <= 16'd0;
                                class_candidate_valid <= 1'b1;
                                state <= ST_WAIT_FRAME;
                            end else begin
                                roi_buffer_id <= held_camera_buffer;
                                roi_x0        <= bbox_roi_x0;
                                roi_y0        <= bbox_roi_y0;
                                roi_side      <= bbox_roi_side;
                                roi_tag       <= locator_frame_id;
                                state <= ST_START_ROI;
                            end
                        end
                    end

                    ST_START_ROI: begin
                        if (!roi_busy) begin
                            roi_start <= 1'b1;
                            state <= ST_WAIT_ROI;
                        end
                    end

                    ST_WAIT_ROI: begin
                        if (roi_error) begin
                            camera_buffer_release <= held_camera_buffer ?
                                2'b10 : 2'b01;
                            class_candidate       <= CLASS_NONE;
                            class_candidate_margin <= 16'd0;
                            class_candidate_valid <= 1'b1;
                            state <= ST_WAIT_FRAME;
                        end else if (roi_done) begin
                            camera_buffer_release <= held_camera_buffer ?
                                2'b10 : 2'b01;
                            state <= ST_START_CLASS;
                        end
                    end

                    ST_START_CLASS: begin
                        if (!classifier_request_busy) begin
                            classifier_request <= 1'b1;
                            state <= ST_WAIT_CLASS;
                        end
                    end

                    ST_WAIT_CLASS: begin
                        if (classifier_result_pulse) begin
                            if (classifier_result_class < NUM_CLASSES) begin
                                // Rain six-class order: background/one/two/three/fist/palm.
                                // S4 ABI order: background/object1/object2/object3/palm/fist.
                                if (TASK_CLASS_MAP != 0 && classifier_result_class == 9'd4)
                                    class_candidate <= 3'd5;
                                else if (TASK_CLASS_MAP != 0 && classifier_result_class == 9'd5)
                                    class_candidate <= 3'd4;
                                else
                                    class_candidate <= classifier_result_class[2:0];
                                class_candidate_margin <= classifier_result_margin;
                            end else begin
                                class_candidate        <= CLASS_NONE;
                                class_candidate_margin <= 16'd0;
                            end
                            class_candidate_valid <= 1'b1;
                            state <= ST_WAIT_FRAME;
                        end
                    end

                    ST_FATAL: begin
                        fatal_error <= 1'b1;
                        camera_buffer_release <= camera_buffer_valid;
                    end

                    default: begin
                        fatal_error <= 1'b1;
                        state <= ST_FATAL;
                    end
                endcase
            end
        end
    end

endmodule
