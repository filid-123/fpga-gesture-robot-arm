// ============================================================================
// Phase2-only small-frame frontend; no VGA source RAM or unused stream ROI.
// DVP bytes are converted to Gray8 coordinate tokens in PCLK, crossed through
// a Gray-pointer async FIFO, then packed as locator-compatible ping/pong BRAM
// words in the 100 MHz system domain.
// ============================================================================
`timescale 1ns / 1ps

module ov5640_phase2_frontend #(
    parameter integer HD_PREVIEW=0,
    parameter integer Y_BYTE_PHASE      = 0,
    parameter integer VSYNC_ACTIVE_HIGH = 1,
    parameter integer FIFO_ADDR_WIDTH   = 10,
    parameter integer CYCLES_PER_MS = 100000
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

    output wire [1:0]  buffer_valid_mask,
    output wire [31:0] buffer_frame_id_0,
    output wire [31:0] buffer_frame_id_1,
    output wire        frame_published,
    output wire        latest_buffer_id,
    output wire [31:0] latest_frame_id,

    output wire        mem_we,
    output wire [12:0] mem_word_addr,
    output wire [31:0] mem_wdata,

    output wire [31:0] buffer_timestamp_ms_0, buffer_timestamp_ms_1, now_ms,

    output wire preview_we,output wire[13:0]preview_addr,output wire[31:0]preview_data,
    output wire preview_published,output wire[31:0]preview_id,
    output wire [31:0] frame_drop_count,
    output wire [31:0] format_error_count,
    output wire        fifo_overflow_sticky
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

    wire preview_accept;wire[31:0]preview_frame_id;
    pl_letterbox_640x480 #(.CYCLES_PER_MS(CYCLES_PER_MS)) u_letterbox (
        .clk(sys_clk),
        .rst_n(sys_rst_n),
        .pixel_valid(token_valid),
        .pixel_ready(token_ready),
        .pixel_data(token_data[7:0]),
        .pixel_x(token_data[17:8]),
        .pixel_y(token_data[27:18]),
        .pixel_sof(token_data[28]),
        .buffer_release(buffer_release),
        .buffer_valid_mask(buffer_valid_mask),
        .buffer_frame_id_0(buffer_frame_id_0),
        .buffer_frame_id_1(buffer_frame_id_1),
        .frame_published(frame_published),
        .latest_buffer_id(latest_buffer_id),
        .latest_frame_id(latest_frame_id),
        .mem_we(mem_we),
        .mem_word_addr(mem_word_addr),
        .mem_wdata(mem_wdata),
        .buffer_timestamp_ms_0(buffer_timestamp_ms_0),
        .buffer_timestamp_ms_1(buffer_timestamp_ms_1),.now_ms(now_ms),
        .preview_accept_sof(preview_accept),.preview_frame_id(preview_frame_id),
        .frame_drop_count(frame_drop_count),
        .format_error_count(format_error_count)
    );

    generate if(HD_PREVIEW!=0)begin:g_preview
     preview_gray256 tap(.clk(sys_clk),.rst_n(sys_rst_n),.valid(token_valid && token_ready),
      .accept_sof(preview_accept),.frame_id(preview_frame_id),.gray(token_data[7:0]),.x(token_data[17:8]),.y(token_data[27:18]),
      .we(preview_we),.addr(preview_addr),.data(preview_data),.published(preview_published),.published_id(preview_id));
    end else begin:g_no_preview
     assign preview_we=0;assign preview_addr=0;assign preview_data=0;assign preview_published=0;assign preview_id=0;
    end endgenerate
endmodule
