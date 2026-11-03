// Structural wrapper: original instances, parameters and cycles preserved.
`timescale 1ns/1ps
module motion_hand_target_pipeline #(
    parameter integer HAS_ROARM          = 1,
    parameter integer HAS_SO101          = 1,
    parameter integer DEBOUNCE_CYCLES    = 1_000_000,
    parameter integer MIN_PERIOD_CYCLES  = 512,
    parameter integer AXI_TIMEOUT_CYCLES = 4096,
    parameter integer VIS_ASYNC          = 1,
    parameter integer TRAY_EXIT          = 0,
    parameter integer A_TRAY_EXIT        = 0,
    parameter integer PALM_CONTINUITY    = 0,
    parameter integer SLOT_INVENTORY     = 0,
    parameter integer TIMED_WALKTHROUGH  = 0,
    parameter integer HANDOVER_V2        = 0,
    parameter integer HAND_ALIGN_REGIONS = 3,
    parameter integer HAND_ALIGN_LOCATOR = 0,
    parameter integer HAND_ALIGN         = 0,
    parameter integer CONTINUOUS_HAND = 0,
    parameter integer AUTO_RESTOCK = 0,
    parameter integer DYNAMIC_B = 0,
    parameter integer SMOOTH_PROFILE = 0,
    parameter integer ROARM_FEEDBACK_EVERY = 1
)(
    input wire [31:0] status_fsm,
    input wire  align_accept,
    input wire [3:0] align_accepted_cell,
    input wire [31:0] align_accepted_revision,
    input wire  align_palm_confirmed,
    input wire  align_settled,
    input wire  align_waiting,
    input wire  cfg_mode_b,
    input wire  cfg_unlock,
    input wire  clk,
    input wire  fault_latched,
    input wire  fifo_unlock,
    output wire [3:0] ha_cell,
    output wire  ha_ready,
    output wire [31:0] ha_revision,
    output wire  ha_valid,
    input wire [2:0] hand_class,
    input wire [31:0] hand_frame_id,
    input wire  hand_frame_valid,
    input wire [31:0] hand_now_ms,
    input wire [31:0] hand_timestamp_ms,
    input wire [8:0] hand_x,
    input wire [8:0] hand_y,
    output wire [3:0] locked_cell,
    output wire [31:0] map_active_revision,
    input wire [3:0] map_cell,
    input wire  map_commit,
    output wire  map_committed,
    output wire  map_error,
    output wire [3:0] map_error_code,
    output wire  map_locked,
    input wire [15:0] map_mask,
    output wire  map_ready,
    input wire [31:0] map_revision,
    input wire [31:0] map_wdata,
    input wire [1:0] map_word,
    input wire  map_write,
    input wire  rst_n
);
wire [41:0] bundle;
wire [2:0] cls;
wire [31:0] id;
wire [3:0] mapped_cell_wire;
wire  mv;
wire [31:0] revision;
wire  rv;
wire [31:0] ts;
hand_align_region_lut #(.REGION_COUNT(HAND_ALIGN_REGIONS)) u_regions(.clk(clk),.rst_n(rst_n),.task_active(!cfg_unlock && !(DYNAMIC_B!=0 && cfg_mode_b && fifo_unlock)),
            .cfg_write(map_write),.cfg_commit(map_commit),.cfg_cell(map_cell),.cfg_word(map_word),.cfg_wdata(map_wdata),.cfg_revision(map_revision),.cfg_mask(map_mask),
            .cfg_ready(map_ready),.cfg_error(map_error),.committed(map_committed),.cfg_error_code(map_error_code),.active_revision(map_active_revision),
            .lookup_req(hand_frame_valid),.lookup_x(hand_x),.lookup_y(hand_y),.lookup_frame_id(hand_frame_id),.lookup_timestamp_ms(hand_timestamp_ms),.lookup_class(hand_class),
            .response_valid(rv),.mapped_valid(mv),.mapped_cell(mapped_cell_wire),.mapped_bundle(bundle),.mapped_frame_id(id),.mapped_timestamp_ms(ts),.mapped_revision(revision),.mapped_class(cls));
hand_align_target_core #(.PIPELINED_FRESHNESS(CONTINUOUS_HAND),.POSITION_ONLY(HAND_ALIGN_LOCATOR),.EXPLICIT_ACCEPT((HAND_ALIGN_REGIONS==4)?1:0)) u_target(.clk(clk),.rst_n(rst_n),.task_active(!cfg_unlock),.waiting_region(align_waiting),
            .cancel(status_fsm[16]),.fault(fault_latched),.now_ms(hand_now_ms),.max_age_ms(32'd250),.max_gap_ms(32'd250),.hold_ms((HAND_ALIGN_LOCATOR!=0)?16'd80:(HAND_ALIGN_REGIONS==4)?16'd120:16'd200),.min_frames((HAND_ALIGN_LOCATOR!=0)?8'd2:8'd3),
            .response_valid(rv),.mapped_valid(mv),.mapped_cell(mapped_cell_wire),.mapped_bundle(bundle),.mapped_frame_id(id),.mapped_timestamp_ms(ts),.mapped_revision(revision),.mapped_class(cls),
            .accepted_cell_in(align_accepted_cell),.accepted_revision_in(align_accepted_revision),.accept_target(align_accept),.position_settled(align_settled),.palm_confirmed(align_palm_confirmed),.target_valid(ha_valid),.target_cell(ha_cell),.target_revision(ha_revision),
            .locked(map_locked),.delivery_ready(ha_ready),.locked_cell(locked_cell));
endmodule
