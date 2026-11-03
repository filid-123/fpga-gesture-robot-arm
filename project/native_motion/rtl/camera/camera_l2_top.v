// ============================================================================
// Phase 2-L2 camera subsystem top for later Block Design integration.
// It preserves the Phase 2-L1 USB/PS input memory and provides a selectable,
// dedicated camera ping/pong memory with matching one-cycle Locator read.
// ============================================================================
`timescale 1ns / 1ps

module camera_l2_top #(
    parameter integer C_S_AXI_DATA_WIDTH = 32,
    parameter integer C_S_AXI_ADDR_WIDTH = 8,
    parameter integer Y_BYTE_PHASE       = 0,
    parameter integer VSYNC_ACTIVE_HIGH  = 1
)(
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 s_axi_aclk CLK",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_aclk, ASSOCIATED_BUSIF s_axi, ASSOCIATED_RESET s_axi_aresetn, FREQ_HZ 100000000" *)
    input  wire                              s_axi_aclk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 s_axi_aresetn RST",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_aresetn, POLARITY ACTIVE_LOW" *)
    input  wire                              s_axi_aresetn,
    input  wire [C_S_AXI_ADDR_WIDTH-1:0]     s_axi_awaddr,
    input  wire [2:0]                        s_axi_awprot,
    input  wire                              s_axi_awvalid,
    output wire                              s_axi_awready,
    input  wire [C_S_AXI_DATA_WIDTH-1:0]     s_axi_wdata,
    input  wire [(C_S_AXI_DATA_WIDTH/8)-1:0] s_axi_wstrb,
    input  wire                              s_axi_wvalid,
    output wire                              s_axi_wready,
    output wire [1:0]                        s_axi_bresp,
    output wire                              s_axi_bvalid,
    input  wire                              s_axi_bready,
    input  wire [C_S_AXI_ADDR_WIDTH-1:0]     s_axi_araddr,
    input  wire [2:0]                        s_axi_arprot,
    input  wire                              s_axi_arvalid,
    output wire                              s_axi_arready,
    output wire [C_S_AXI_DATA_WIDTH-1:0]     s_axi_rdata,
    output wire [1:0]                        s_axi_rresp,
    output wire                              s_axi_rvalid,
    input  wire                              s_axi_rready,

    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 pclk CLK",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME pclk, ASSOCIATED_RESET pclk_rst_n, FREQ_HZ 48000000" *)
    input  wire        pclk,
    input  wire        pclk_rst_n,
    input  wire [7:0]  dvp_data,
    input  wire        dvp_href,
    input  wire        dvp_vsync,

    input  wire        xclk_locked,
    output wire        camera_reset_n,
    output wire        camera_pwdn,
    output wire        sccb_scl_drive_low,
    output wire        sccb_sda_drive_low,
    input  wire        sccb_sda_in,

    input  wire        locator_busy,
    input  wire        locator_input_en,
    input  wire [12:0] locator_input_word_addr,
    output wire [31:0] camera_input_data,
    output wire        input_source_camera,
    input  wire        classifier_busy,
    output wire        classifier_input_select,
    output wire        classifier_roi_we,
    output wire [7:0]  classifier_roi_word_addr,
    output wire [31:0] classifier_roi_data,
    output reg         irq_to_ps
);

    wire capture_enable;
    wire clear_status;
    wire [1:0] buffer_release;
    wire sccb_start;
    wire sccb_read;
    wire [6:0] sccb_device_addr;
    wire [15:0] sccb_register_addr;
    wire [7:0] sccb_write_data;
    wire [12:0] debug_word_addr;
    wire roi_desc_arm;
    wire [9:0] roi_desc_x0;
    wire [9:0] roi_desc_y0;
    wire [9:0] roi_desc_side;
    wire [31:0] roi_desc_tag;
    wire roi_same_frame_mode;
    wire roi_buffer_id;

    wire [1:0] buffer_valid_mask;
    wire [31:0] buffer_frame_id_0;
    wire [31:0] buffer_frame_id_1;
    wire frame_published;
    wire latest_buffer_id;
    wire [31:0] latest_frame_id;
    wire camera_mem_we;
    wire [12:0] camera_mem_word_addr;
    wire [31:0] camera_mem_wdata;
    wire [31:0] frame_drop_count;
    wire [31:0] format_error_count;
    wire fifo_overflow_sticky;
    wire stream_roi_desc_armed;
    wire stream_roi_busy;
    wire stream_roi_done_pulse;
    wire stream_roi_error_pulse;
    wire [31:0] stream_roi_completed_tag;
    wire [31:0] stream_roi_source_frame_id;
    wire stream_roi_word_we;
    wire [7:0] stream_roi_word_addr;
    wire [31:0] stream_roi_word_data;

    wire same_roi_busy;
    wire same_roi_done_pulse;
    wire same_roi_error_pulse;
    wire [31:0] same_roi_completed_tag;
    wire [31:0] same_roi_source_frame_id;
    wire same_camera_read_en;
    wire [12:0] same_camera_read_addr;
    wire same_roi_word_we;
    wire [7:0] same_roi_word_addr;
    wire [31:0] same_roi_word_data;

    wire roi_desc_armed = stream_roi_desc_armed;
    wire roi_busy = stream_roi_busy || same_roi_busy;
    wire roi_done_pulse = stream_roi_done_pulse || same_roi_done_pulse;
    wire roi_error_pulse = stream_roi_error_pulse || same_roi_error_pulse;
    reg [31:0] roi_completed_tag;
    reg [31:0] roi_source_frame_id;

    wire sccb_busy;
    wire sccb_done;
    wire sccb_ack_error;
    wire [7:0] sccb_read_data;
    reg sccb_done_sticky;
    reg sccb_ack_error_sticky;
    reg sccb_read_valid_sticky;
    reg [7:0] sccb_read_data_latched;
    reg frame_published_sticky;
    reg roi_done_sticky;
    reg roi_error_sticky;
    (* ASYNC_REG = "TRUE" *) reg classifier_busy_sync1;
    (* ASYNC_REG = "TRUE" *) reg classifier_busy_sync2;
    wire same_camera_read_grant = !locator_busy;
    wire camera_mem_read_en = locator_busy ? locator_input_en :
                              same_roi_busy ? same_camera_read_en : 1'b1;
    wire [12:0] camera_mem_read_addr =
        locator_busy ? locator_input_word_addr :
        same_roi_busy ? same_camera_read_addr : debug_word_addr;

    assign classifier_roi_we = same_roi_word_we ? 1'b1 : stream_roi_word_we;
    assign classifier_roi_word_addr = same_roi_word_we ?
        same_roi_word_addr : stream_roi_word_addr;
    assign classifier_roi_data = same_roi_word_we ?
        same_roi_word_data : stream_roi_word_data;

    camera_l2_axi_lite #(
        .C_S_AXI_DATA_WIDTH(C_S_AXI_DATA_WIDTH),
        .C_S_AXI_ADDR_WIDTH(C_S_AXI_ADDR_WIDTH)
    ) u_axi (
        .S_AXI_ACLK(s_axi_aclk), .S_AXI_ARESETN(s_axi_aresetn),
        .S_AXI_AWADDR(s_axi_awaddr), .S_AXI_AWPROT(s_axi_awprot),
        .S_AXI_AWVALID(s_axi_awvalid), .S_AXI_AWREADY(s_axi_awready),
        .S_AXI_WDATA(s_axi_wdata), .S_AXI_WSTRB(s_axi_wstrb),
        .S_AXI_WVALID(s_axi_wvalid), .S_AXI_WREADY(s_axi_wready),
        .S_AXI_BRESP(s_axi_bresp), .S_AXI_BVALID(s_axi_bvalid),
        .S_AXI_BREADY(s_axi_bready),
        .S_AXI_ARADDR(s_axi_araddr), .S_AXI_ARPROT(s_axi_arprot),
        .S_AXI_ARVALID(s_axi_arvalid), .S_AXI_ARREADY(s_axi_arready),
        .S_AXI_RDATA(s_axi_rdata), .S_AXI_RRESP(s_axi_rresp),
        .S_AXI_RVALID(s_axi_rvalid), .S_AXI_RREADY(s_axi_rready),
        .capture_enable(capture_enable),
        .input_source_camera(input_source_camera),
        .camera_reset_n(camera_reset_n), .camera_pwdn(camera_pwdn),
        .clear_status(clear_status), .buffer_release(buffer_release),
        .sccb_start(sccb_start), .sccb_read(sccb_read),
        .sccb_device_addr(sccb_device_addr),
        .sccb_register_addr(sccb_register_addr),
        .sccb_write_data(sccb_write_data),
        .debug_word_addr(debug_word_addr),
        .roi_desc_arm(roi_desc_arm),
        .roi_desc_x0(roi_desc_x0),
        .roi_desc_y0(roi_desc_y0),
        .roi_desc_side(roi_desc_side),
        .roi_desc_tag(roi_desc_tag),
        .classifier_input_select(classifier_input_select),
        .roi_same_frame_mode(roi_same_frame_mode),
        .roi_buffer_id(roi_buffer_id),
        .locator_busy(locator_busy), .xclk_locked(xclk_locked),
        .classifier_busy(classifier_busy_sync2),
        .sccb_busy(sccb_busy),
        .sccb_done_sticky(sccb_done_sticky),
        .sccb_ack_error_sticky(sccb_ack_error_sticky),
        .sccb_read_valid_sticky(sccb_read_valid_sticky),
        .sccb_read_data(sccb_read_data_latched),
        .fifo_overflow_sticky(fifo_overflow_sticky),
        .frame_published_sticky(frame_published_sticky),
        .buffer_valid_mask(buffer_valid_mask),
        .latest_buffer_id(latest_buffer_id),
        .buffer_frame_id_0(buffer_frame_id_0),
        .buffer_frame_id_1(buffer_frame_id_1),
        .latest_frame_id(latest_frame_id),
        .frame_drop_count(frame_drop_count),
        .format_error_count(format_error_count),
        .roi_desc_armed(roi_desc_armed),
        .roi_busy(roi_busy),
        .roi_same_frame_busy(same_roi_busy),
        .roi_done_sticky(roi_done_sticky),
        .roi_error_sticky(roi_error_sticky),
        .roi_completed_tag(roi_completed_tag),
        .roi_source_frame_id(roi_source_frame_id),
        .debug_word_data(camera_input_data)
    );

    ov5640_l2_frontend #(
        .Y_BYTE_PHASE(Y_BYTE_PHASE),
        .VSYNC_ACTIVE_HIGH(VSYNC_ACTIVE_HIGH),
        .FIFO_ADDR_WIDTH(10)
    ) u_frontend (
        .pclk(pclk), .pclk_rst_n(pclk_rst_n),
        .dvp_data(dvp_data), .dvp_href(dvp_href), .dvp_vsync(dvp_vsync),
        .capture_enable(capture_enable),
        .sys_clk(s_axi_aclk), .sys_rst_n(s_axi_aresetn),
        .buffer_release(buffer_release),
        .roi_desc_arm(roi_desc_arm && !roi_same_frame_mode),
        .roi_desc_x0(roi_desc_x0),
        .roi_desc_y0(roi_desc_y0),
        .roi_desc_side(roi_desc_side),
        .roi_desc_tag(roi_desc_tag),
        .buffer_valid_mask(buffer_valid_mask),
        .buffer_frame_id_0(buffer_frame_id_0),
        .buffer_frame_id_1(buffer_frame_id_1),
        .frame_published(frame_published),
        .latest_buffer_id(latest_buffer_id),
        .latest_frame_id(latest_frame_id),
        .mem_we(camera_mem_we), .mem_word_addr(camera_mem_word_addr),
        .mem_wdata(camera_mem_wdata),
        .roi_desc_armed(stream_roi_desc_armed),
        .roi_busy(stream_roi_busy),
        .roi_done_pulse(stream_roi_done_pulse),
        .roi_error_pulse(stream_roi_error_pulse),
        .roi_completed_tag(stream_roi_completed_tag),
        .roi_source_frame_id(stream_roi_source_frame_id),
        .roi_word_we(stream_roi_word_we),
        .roi_word_addr(stream_roi_word_addr),
        .roi_word_data(stream_roi_word_data),
        .frame_drop_count(frame_drop_count),
        .format_error_count(format_error_count),
        .fifo_overflow_sticky(fifo_overflow_sticky)
    );

    same_frame_roi_128x128 u_same_frame_roi (
        .clk(s_axi_aclk),
        .rst_n(s_axi_aresetn),
        .start(roi_desc_arm && roi_same_frame_mode),
        .buffer_id(roi_buffer_id),
        .desc_x0(roi_desc_x0),
        .desc_y0(roi_desc_y0),
        .desc_side(roi_desc_side),
        .desc_tag(roi_desc_tag),
        .buffer_valid_mask(buffer_valid_mask),
        .buffer_frame_id_0(buffer_frame_id_0),
        .buffer_frame_id_1(buffer_frame_id_1),
        .read_grant(same_camera_read_grant),
        .camera_read_en(same_camera_read_en),
        .camera_read_word_addr(same_camera_read_addr),
        .camera_read_data(camera_input_data),
        .busy(same_roi_busy),
        .done_pulse(same_roi_done_pulse),
        .error_pulse(same_roi_error_pulse),
        .completed_tag(same_roi_completed_tag),
        .completed_source_frame_id(same_roi_source_frame_id),
        .roi_word_we(same_roi_word_we),
        .roi_word_addr(same_roi_word_addr),
        .roi_word_data(same_roi_word_data)
    );

    camera_locator_input_bram u_camera_input_mem (
        .clk(s_axi_aclk),
        .camera_we(camera_mem_we),
        .camera_word_addr(camera_mem_word_addr),
        .camera_wdata(camera_mem_wdata),
        .locator_en(camera_mem_read_en),
        .locator_word_addr(camera_mem_read_addr),
        .locator_rdata(camera_input_data)
    );

    sccb_master u_sccb (
        .clk(s_axi_aclk), .rst_n(s_axi_aresetn),
        .cmd_valid(sccb_start), .cmd_ready(),
        .cmd_read(sccb_read),
        .device_addr(sccb_device_addr),
        .register_addr(sccb_register_addr), .write_data(sccb_write_data),
        .read_data(sccb_read_data), .busy(sccb_busy),
        .done(sccb_done), .ack_error(sccb_ack_error),
        .scl_drive_low(sccb_scl_drive_low),
        .sda_drive_low(sccb_sda_drive_low), .sda_in(sccb_sda_in)
    );

    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin
            classifier_busy_sync1 <= 1'b0;
            classifier_busy_sync2 <= 1'b0;
        end else begin
            classifier_busy_sync1 <= classifier_busy;
            classifier_busy_sync2 <= classifier_busy_sync1;
        end
    end

    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin
            sccb_done_sticky <= 1'b0;
            sccb_ack_error_sticky <= 1'b0;
            sccb_read_valid_sticky <= 1'b0;
            sccb_read_data_latched <= 8'd0;
            frame_published_sticky <= 1'b0;
            roi_done_sticky <= 1'b0;
            roi_error_sticky <= 1'b0;
            roi_completed_tag <= 32'd0;
            roi_source_frame_id <= 32'd0;
            irq_to_ps <= 1'b0;
        end else begin
            if (clear_status) begin
                sccb_done_sticky <= 1'b0;
                sccb_ack_error_sticky <= 1'b0;
                sccb_read_valid_sticky <= 1'b0;
                frame_published_sticky <= 1'b0;
                roi_done_sticky <= 1'b0;
                roi_error_sticky <= 1'b0;
                irq_to_ps <= 1'b0;
            end
            if (sccb_done) begin
                sccb_done_sticky <= 1'b1;
                if (sccb_ack_error)
                    sccb_ack_error_sticky <= 1'b1;
                else if (sccb_read) begin
                    sccb_read_data_latched <= sccb_read_data;
                    sccb_read_valid_sticky <= 1'b1;
                end
            end
            if (frame_published)
                frame_published_sticky <= 1'b1;
            if (roi_done_pulse)
                roi_done_sticky <= 1'b1;
            if (stream_roi_done_pulse) begin
                roi_completed_tag <= stream_roi_completed_tag;
                roi_source_frame_id <= stream_roi_source_frame_id;
            end
            if (same_roi_done_pulse) begin
                roi_completed_tag <= same_roi_completed_tag;
                roi_source_frame_id <= same_roi_source_frame_id;
            end
            if (roi_error_pulse)
                roi_error_sticky <= 1'b1;
            if (frame_published || roi_done_pulse || roi_error_pulse)
                irq_to_ps <= 1'b1;
        end
    end
endmodule
