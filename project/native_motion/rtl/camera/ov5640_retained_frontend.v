// ============================================================================
// Phase 2-L2 camera front-end integration shell.
// DVP bytes are converted to Gray8 coordinate tokens in PCLK, crossed through
// a Gray-pointer async FIFO, then packed as locator-compatible ping/pong BRAM
// words in the 100 MHz system domain.
// ============================================================================
`timescale 1ns / 1ps

module ov5640_retained_frontend #(
    parameter integer Y_BYTE_PHASE      = 0,
    parameter integer VSYNC_ACTIVE_HIGH = 1,
    parameter integer FIFO_ADDR_WIDTH   = 10
)(
    input  wire        pclk,
    input  wire        pclk_rst_n,
    input  wire [7:0]  dvp_data,
    input  wire        dvp_href,
    input  wire        dvp_vsync,
    input  wire        capture_enable,

    input  wire        sys_clk,
    input  wire        sys_rst_n,
    input  wire [1:0]  buffer_release,
    input  wire        roi_desc_arm,
    input  wire [9:0]  roi_desc_x0,
    input  wire [9:0]  roi_desc_y0,
    input  wire [9:0]  roi_desc_side,
    input  wire [31:0] roi_desc_tag,

    output wire [1:0]  buffer_valid_mask,
    output wire [31:0] buffer_frame_id_0,
    output wire [31:0] buffer_frame_id_1,
    output wire        frame_published,
    output wire        latest_buffer_id,
    output wire [31:0] latest_frame_id,

    output wire        mem_we,
    output wire [12:0] mem_word_addr,
    output wire [31:0] mem_wdata,

    output wire        roi_desc_armed,
    output wire        roi_busy,
    output wire        roi_done_pulse,
    output wire        roi_error_pulse,
    output wire [31:0] roi_completed_tag,
    output wire [31:0] roi_source_frame_id,
    output wire        roi_word_we,
    output wire [7:0]  roi_word_addr,
    output wire [31:0] roi_word_data,

    output wire [31:0] frame_drop_count,
    output wire [31:0] format_error_count,
    output wire        fifo_overflow_sticky,
    input wire source_rd_en,
    input wire [16:0] source_word_addr,
    output wire [31:0] source_data,
    output wire [31:0] frame_timestamp_ms,
    output wire [31:0] now_ms,
    output wire [2:0] debug_capture_state
);

    wire       cap_valid;
    wire [7:0] cap_y;
    wire [9:0] cap_x;
    wire [9:0] cap_y_coord;
    wire       cap_sof;

    // capture_enable is a persistent software control written in the
    // 100 MHz AXI domain. Synchronize it before it gates PCLK-domain state.
    (* ASYNC_REG = "TRUE" *) reg capture_enable_pclk_sync1;
    (* ASYNC_REG = "TRUE" *) reg capture_enable_pclk_sync2;

    always @(posedge pclk) begin
        if (!pclk_rst_n) begin
            capture_enable_pclk_sync1 <= 1'b0;
            capture_enable_pclk_sync2 <= 1'b0;
        end else begin
            capture_enable_pclk_sync1 <= capture_enable;
            capture_enable_pclk_sync2 <= capture_enable_pclk_sync1;
        end
    end

    ov5640_capture #(
        .Y_BYTE_PHASE(Y_BYTE_PHASE),
        .VSYNC_ACTIVE_HIGH(VSYNC_ACTIVE_HIGH)
    ) u_capture (
        .pclk(pclk),
        .rst_n(pclk_rst_n),
        .enable(capture_enable_pclk_sync2),
        .dvp_data(dvp_data),
        .dvp_href(dvp_href),
        .dvp_vsync(dvp_vsync),
        .pixel_valid(cap_valid),
        .pixel_y(cap_y),
        .pixel_x(cap_x),
        .pixel_y_coord(cap_y_coord),
        .pixel_sof(cap_sof)
    );

    wire [28:0] fifo_wr_data = {cap_sof, cap_y_coord, cap_x, cap_y};
    wire        fifo_full;
    wire        fifo_wr_overflow;
    wire [28:0] fifo_rd_data;
    wire        fifo_rd_valid;
    wire        fifo_empty;
    wire        fifo_rd_underflow;
    wire        fifo_rd_en;

    cdc_async_fifo #(
        .DATA_WIDTH(29),
        .ADDR_WIDTH(FIFO_ADDR_WIDTH)
    ) u_fifo (
        .wr_clk(pclk),
        .wr_rst_n(pclk_rst_n),
        .wr_en(cap_valid),
        .wr_data(fifo_wr_data),
        .wr_full(fifo_full),
        .wr_overflow(fifo_wr_overflow),
        .rd_clk(sys_clk),
        .rd_rst_n(sys_rst_n),
        .rd_en(fifo_rd_en),
        .rd_data(fifo_rd_data),
        .rd_valid(fifo_rd_valid),
        .rd_empty(fifo_empty),
        .rd_underflow(fifo_rd_underflow)
    );

    reg fifo_overflow_pclk;
    (* ASYNC_REG = "TRUE" *) reg fifo_overflow_sync1;
    (* ASYNC_REG = "TRUE" *) reg fifo_overflow_sync2;

    always @(posedge pclk) begin
        if (!pclk_rst_n)
            fifo_overflow_pclk <= 1'b0;
        else if (fifo_wr_overflow)
            fifo_overflow_pclk <= 1'b1;
    end

    always @(posedge sys_clk) begin
        if (!sys_rst_n) begin
            fifo_overflow_sync1 <= 1'b0;
            fifo_overflow_sync2 <= 1'b0;
        end else begin
            fifo_overflow_sync1 <= fifo_overflow_pclk;
            fifo_overflow_sync2 <= fifo_overflow_sync1;
        end
    end

    assign fifo_overflow_sticky = fifo_overflow_sync2;

    // Registered FIFO output is moved through a one-entry elastic token buffer.
    // At most one read is outstanding, preventing data loss while padding rows
    // temporarily backpressure the letterbox writer.
    reg        read_pending;
    reg        token_valid;
    reg [28:0] token_data;
    wire       token_ready;

    assign fifo_rd_en = !read_pending && !token_valid && !fifo_empty;

    always @(posedge sys_clk) begin
        if (!sys_rst_n) begin
            read_pending <= 1'b0;
            token_valid  <= 1'b0;
            token_data   <= 29'd0;
        end else begin
            if (fifo_rd_en)
                read_pending <= 1'b1;
            if (fifo_rd_valid) begin
                token_data   <= fifo_rd_data;
                token_valid  <= 1'b1;
                read_pending <= 1'b0;
            end
            if (token_valid && token_ready)
                token_valid <= 1'b0;
        end
    end

    wire retained_valid;
    retained_gray_frame u_retained (
        .clk(sys_clk),.rst_n(sys_rst_n),.pixel_valid(token_valid),.pixel_ready(token_ready),
        .pixel_data(token_data[7:0]),.pixel_x(token_data[17:8]),.pixel_y(token_data[27:18]),
        .pixel_sof(token_data[28]),.release_frame(buffer_release[0]),
        .frame_valid(retained_valid),.frame_id(buffer_frame_id_0),.published(frame_published),
        .frame_timestamp_ms(frame_timestamp_ms),.now_ms(now_ms),
        .loc_we(mem_we),.loc_word_addr(mem_word_addr),.loc_data(mem_wdata),
        .source_rd_en(source_rd_en),.source_word_addr(source_word_addr),.source_data(source_data),
        .frame_drop_count(frame_drop_count),.format_error_count(format_error_count),
        .debug_capture_state(debug_capture_state));
    assign buffer_valid_mask={1'b0,retained_valid};
    assign buffer_frame_id_1=32'd0;
    assign latest_buffer_id=1'b0;
    assign latest_frame_id=buffer_frame_id_0;
    // The retired next-frame nearest ROI path is not instantiated.
    assign roi_desc_armed=1'b0; assign roi_busy=1'b0;
    assign roi_done_pulse=1'b0; assign roi_error_pulse=1'b0;
    assign roi_completed_tag=32'd0; assign roi_source_frame_id=32'd0;
    assign roi_word_we=1'b0; assign roi_word_addr=8'd0; assign roi_word_data=32'd0;
endmodule
