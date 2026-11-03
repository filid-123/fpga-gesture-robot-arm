// ============================================================================
// Phase 2-L2 camera control/status AXI4-Lite slave.
// AW and W are accepted independently. Persistent camera/source controls are
// separated from pulse commands for buffer release and SCCB transactions.
// ============================================================================
`timescale 1ns / 1ps

module camera_l2_axi_lite #(
    parameter integer C_S_AXI_DATA_WIDTH = 32,
    parameter integer C_S_AXI_ADDR_WIDTH = 8,
    parameter [31:0]  ABI_VERSION        = 32'h0000_0403
)(
    input  wire                              S_AXI_ACLK,
    input  wire                              S_AXI_ARESETN,
    input  wire [C_S_AXI_ADDR_WIDTH-1:0]     S_AXI_AWADDR,
    input  wire [2:0]                        S_AXI_AWPROT,
    input  wire                              S_AXI_AWVALID,
    output wire                              S_AXI_AWREADY,
    input  wire [C_S_AXI_DATA_WIDTH-1:0]     S_AXI_WDATA,
    input  wire [(C_S_AXI_DATA_WIDTH/8)-1:0] S_AXI_WSTRB,
    input  wire                              S_AXI_WVALID,
    output wire                              S_AXI_WREADY,
    output wire [1:0]                        S_AXI_BRESP,
    output wire                              S_AXI_BVALID,
    input  wire                              S_AXI_BREADY,
    input  wire [C_S_AXI_ADDR_WIDTH-1:0]     S_AXI_ARADDR,
    input  wire [2:0]                        S_AXI_ARPROT,
    input  wire                              S_AXI_ARVALID,
    output wire                              S_AXI_ARREADY,
    output wire [C_S_AXI_DATA_WIDTH-1:0]     S_AXI_RDATA,
    output wire [1:0]                        S_AXI_RRESP,
    output wire                              S_AXI_RVALID,
    input  wire                              S_AXI_RREADY,

    output reg         capture_enable,
    output reg         input_source_camera,
    output reg         camera_reset_n,
    output reg         camera_pwdn,
    output reg         clear_status,
    output reg  [1:0]  buffer_release,
    output reg         sccb_start,
    output reg         sccb_read,
    output reg  [6:0]  sccb_device_addr,
    output reg  [15:0] sccb_register_addr,
    output reg  [7:0]  sccb_write_data,
    output reg  [12:0] debug_word_addr,
    output reg         roi_desc_arm,
    output reg  [9:0]  roi_desc_x0,
    output reg  [9:0]  roi_desc_y0,
    output reg  [9:0]  roi_desc_side,
    output reg  [31:0] roi_desc_tag,
    output reg         classifier_input_select,
    output reg         roi_same_frame_mode,
    output reg         roi_buffer_id,

    input  wire        locator_busy,
    input  wire        classifier_busy,
    input  wire        xclk_locked,
    input  wire        sccb_busy,
    input  wire        sccb_done_sticky,
    input  wire        sccb_ack_error_sticky,
    input  wire        sccb_read_valid_sticky,
    input  wire [7:0]  sccb_read_data,
    input  wire        fifo_overflow_sticky,
    input  wire        frame_published_sticky,
    input  wire [1:0]  buffer_valid_mask,
    input  wire        latest_buffer_id,
    input  wire [31:0] buffer_frame_id_0,
    input  wire [31:0] buffer_frame_id_1,
    input  wire [31:0] latest_frame_id,
    input  wire [31:0] frame_drop_count,
    input  wire [31:0] format_error_count,
    input  wire        roi_desc_armed,
    input  wire        roi_busy,
    input  wire        roi_same_frame_busy,
    input  wire        roi_done_sticky,
    input  wire        roi_error_sticky,
    input  wire [31:0] roi_completed_tag,
    input  wire [31:0] roi_source_frame_id,
    input  wire [31:0] debug_word_data
);

    localparam [7:0] REG_CONTROL        = 8'h00;
    localparam [7:0] REG_STATUS         = 8'h04;
    localparam [7:0] REG_ABI_VERSION    = 8'h08;
    localparam [7:0] REG_FRAME_ID_0     = 8'h0c;
    localparam [7:0] REG_FRAME_ID_1     = 8'h10;
    localparam [7:0] REG_LATEST_FRAME   = 8'h14;
    localparam [7:0] REG_DROP_COUNT     = 8'h18;
    localparam [7:0] REG_FORMAT_ERRORS  = 8'h1c;
    localparam [7:0] REG_SCCB_ADDRESS   = 8'h20;
    localparam [7:0] REG_SCCB_DATA      = 8'h24;
    localparam [7:0] REG_BUFFER_RELEASE = 8'h28;
    localparam [7:0] REG_SCCB_START     = 8'h2c;
    localparam [7:0] REG_CLEAR_STATUS   = 8'h30;
    localparam [7:0] REG_DEBUG_WORD_ADDR = 8'h34;
    localparam [7:0] REG_DEBUG_WORD_DATA = 8'h38;
    localparam [7:0] REG_ROI_XY          = 8'h3c;
    localparam [7:0] REG_ROI_SIZE        = 8'h40;
    localparam [7:0] REG_ROI_TAG         = 8'h44;
    localparam [7:0] REG_ROI_CONTROL     = 8'h48;
    localparam [7:0] REG_ROI_STATUS      = 8'h4c;
    localparam [7:0] REG_ROI_DONE_TAG    = 8'h50;
    localparam [7:0] REG_ROI_FRAME_ID    = 8'h54;

    reg aw_pending;
    reg [C_S_AXI_ADDR_WIDTH-1:0] awaddr_hold;
    reg w_pending;
    reg [31:0] wdata_hold;
    reg [3:0] wstrb_hold;
    reg axi_bvalid;
    reg [1:0] axi_bresp;
    reg axi_rvalid;
    reg [31:0] axi_rdata;
    reg [1:0] axi_rresp;

    wire aw_accept = S_AXI_AWVALID && S_AXI_AWREADY;
    wire w_accept = S_AXI_WVALID && S_AXI_WREADY;
    wire write_commit = aw_pending && w_pending && !axi_bvalid;
    wire ar_accept = S_AXI_ARVALID && S_AXI_ARREADY;
    wire debug_target_valid = buffer_valid_mask[debug_word_addr[12]];

    assign S_AXI_AWREADY = !aw_pending && !axi_bvalid;
    assign S_AXI_WREADY  = !w_pending && !axi_bvalid;
    assign S_AXI_BVALID  = axi_bvalid;
    assign S_AXI_BRESP   = axi_bresp;
    assign S_AXI_ARREADY = !axi_rvalid;
    assign S_AXI_RVALID  = axi_rvalid;
    assign S_AXI_RDATA   = axi_rdata;
    assign S_AXI_RRESP   = axi_rresp;

    always @(posedge S_AXI_ACLK) begin
        if (!S_AXI_ARESETN) begin
            aw_pending          <= 1'b0;
            awaddr_hold         <= {C_S_AXI_ADDR_WIDTH{1'b0}};
            w_pending           <= 1'b0;
            wdata_hold          <= 32'd0;
            wstrb_hold          <= 4'd0;
            axi_bvalid          <= 1'b0;
            axi_bresp           <= 2'b00;
            capture_enable      <= 1'b0;
            input_source_camera <= 1'b0;
            camera_reset_n      <= 1'b0;
            camera_pwdn         <= 1'b1;
            clear_status        <= 1'b0;
            buffer_release      <= 2'b00;
            sccb_start          <= 1'b0;
            sccb_read           <= 1'b0;
            sccb_device_addr    <= 7'h3c;
            sccb_register_addr  <= 16'd0;
            sccb_write_data     <= 8'd0;
            debug_word_addr     <= 13'd0;
            roi_desc_arm        <= 1'b0;
            roi_desc_x0         <= 10'd0;
            roi_desc_y0         <= 10'd0;
            roi_desc_side       <= 10'd32;
            roi_desc_tag        <= 32'd0;
            classifier_input_select <= 1'b0;
            roi_same_frame_mode <= 1'b0;
            roi_buffer_id       <= 1'b0;
        end else begin
            clear_status   <= 1'b0;
            buffer_release <= 2'b00;
            sccb_start     <= 1'b0;
            roi_desc_arm   <= 1'b0;

            if (aw_accept) begin
                awaddr_hold <= S_AXI_AWADDR;
                aw_pending <= 1'b1;
            end
            if (w_accept) begin
                wdata_hold <= S_AXI_WDATA;
                wstrb_hold <= S_AXI_WSTRB;
                w_pending <= 1'b1;
            end

            if (write_commit) begin
                aw_pending <= 1'b0;
                w_pending <= 1'b0;
                axi_bvalid <= 1'b1;
                axi_bresp <= 2'b00;

                if ((awaddr_hold[1:0] != 2'b00) || (wstrb_hold != 4'b1111)) begin
                    axi_bresp <= 2'b10;
                end else begin
                    case (awaddr_hold)
                        REG_CONTROL: begin
                            if (wdata_hold[31:4] != 0 ||
                                (locator_busy &&
                                 (wdata_hold[1] != input_source_camera)) ||
                                (wdata_hold[0] &&
                                 (!wdata_hold[2] || wdata_hold[3] ||
                                  !xclk_locked))) begin
                                axi_bresp <= 2'b10;
                            end else begin
                                capture_enable <= wdata_hold[0];
                                input_source_camera <= wdata_hold[1];
                                camera_reset_n <= wdata_hold[2];
                                camera_pwdn <= wdata_hold[3];
                            end
                        end
                        REG_SCCB_ADDRESS: begin
                            if (sccb_busy || wdata_hold[31:23] != 0)
                                axi_bresp <= 2'b10;
                            else begin
                                sccb_device_addr <= wdata_hold[22:16];
                                sccb_register_addr <= wdata_hold[15:0];
                            end
                        end
                        REG_SCCB_DATA: begin
                            if (sccb_busy || wdata_hold[31:8] != 0)
                                axi_bresp <= 2'b10;
                            else
                                sccb_write_data <= wdata_hold[7:0];
                        end
                        REG_BUFFER_RELEASE: begin
                            if (locator_busy || wdata_hold[31:2] != 0 ||
                                ((wdata_hold[1:0] & ~buffer_valid_mask) != 0) ||
                                (roi_same_frame_busy &&
                                 wdata_hold[roi_buffer_id]))
                                axi_bresp <= 2'b10;
                            else
                                buffer_release <= wdata_hold[1:0];
                        end
                        REG_SCCB_START: begin
                            if (sccb_busy || !wdata_hold[0] ||
                                wdata_hold[31:2] != 0)
                                axi_bresp <= 2'b10;
                            else begin
                                sccb_read <= wdata_hold[1];
                                sccb_start <= 1'b1;
                            end
                        end
                        REG_CLEAR_STATUS: begin
                            if (wdata_hold != 32'd1)
                                axi_bresp <= 2'b10;
                            else
                                clear_status <= 1'b1;
                        end
                        REG_DEBUG_WORD_ADDR: begin
                            if (locator_busy || roi_same_frame_busy ||
                                wdata_hold[31:13] != 0 ||
                                !buffer_valid_mask[wdata_hold[12]])
                                axi_bresp <= 2'b10;
                            else
                                debug_word_addr <= wdata_hold[12:0];
                        end

                        REG_ROI_XY: begin
                            if (roi_desc_armed || roi_busy || classifier_busy ||
                                wdata_hold[31:26] != 0 || wdata_hold[15:10] != 0 ||
                                wdata_hold[9:0] >= 640 ||
                                wdata_hold[25:16] >= 480)
                                axi_bresp <= 2'b10;
                            else begin
                                roi_desc_x0 <= wdata_hold[9:0];
                                roi_desc_y0 <= wdata_hold[25:16];
                            end
                        end
                        REG_ROI_SIZE: begin
                            if (roi_desc_armed || roi_busy || classifier_busy ||
                                wdata_hold[31:10] != 0 ||
                                wdata_hold[9:0] < 1 || wdata_hold[9:0] > 480)
                                axi_bresp <= 2'b10;
                            else
                                roi_desc_side <= wdata_hold[9:0];
                        end
                        REG_ROI_TAG: begin
                            if (roi_desc_armed || roi_busy || classifier_busy)
                                axi_bresp <= 2'b10;
                            else
                                roi_desc_tag <= wdata_hold;
                        end
                        REG_ROI_CONTROL: begin
                            if (wdata_hold[31:4] != 0 ||
                                (classifier_busy &&
                                 (wdata_hold[1] != classifier_input_select)) ||
                                (wdata_hold[0] &&
                                 (roi_desc_armed || roi_busy || classifier_busy ||
                                  !capture_enable || !wdata_hold[1] ||
                                  (wdata_hold[2] &&
                                   (locator_busy ||
                                    !buffer_valid_mask[wdata_hold[3]] ||
                                    roi_desc_side < 10'd1 ||
                                    roi_desc_side > 10'd128 ||
                                    roi_desc_x0 >= 10'd128 ||
                                    roi_desc_y0 >= 10'd128 ||
                                    ({1'b0, roi_desc_x0} +
                                     {1'b0, roi_desc_side} > 11'd128) ||
                                    ({1'b0, roi_desc_y0} +
                                     {1'b0, roi_desc_side} > 11'd128))) ||
                                  (!wdata_hold[2] &&
                                   (roi_desc_side < 10'd32 ||
                                    ({1'b0, roi_desc_x0} +
                                     {1'b0, roi_desc_side} > 11'd640) ||
                                    ({1'b0, roi_desc_y0} +
                                     {1'b0, roi_desc_side} > 11'd480))))))
                                axi_bresp <= 2'b10;
                            else begin
                                classifier_input_select <= wdata_hold[1];
                                roi_same_frame_mode <= wdata_hold[2];
                                roi_buffer_id <= wdata_hold[3];
                                if (wdata_hold[0])
                                    roi_desc_arm <= 1'b1;
                            end
                        end
                        default: axi_bresp <= 2'b10;
                    endcase
                end
            end else if (axi_bvalid && S_AXI_BREADY) begin
                axi_bvalid <= 1'b0;
            end
        end
    end

    always @(posedge S_AXI_ACLK) begin
        if (!S_AXI_ARESETN) begin
            axi_rvalid <= 1'b0;
            axi_rdata <= 32'd0;
            axi_rresp <= 2'b00;
        end else begin
            if (ar_accept) begin
                axi_rvalid <= 1'b1;
                axi_rdata <= 32'd0;
                axi_rresp <= 2'b00;
                if (S_AXI_ARADDR[1:0] != 2'b00) begin
                    axi_rresp <= 2'b10;
                end else begin
                    case (S_AXI_ARADDR)
                        REG_CONTROL: axi_rdata <= {
                            28'd0, camera_pwdn, camera_reset_n,
                            input_source_camera, capture_enable
                        };
                        REG_STATUS: axi_rdata <= {
                            18'd0, camera_pwdn, camera_reset_n, xclk_locked,
                            sccb_read_valid_sticky, frame_published_sticky,
                            latest_buffer_id, buffer_valid_mask,
                            fifo_overflow_sticky, sccb_ack_error_sticky,
                            sccb_done_sticky, sccb_busy,
                            input_source_camera, capture_enable
                        };
                        REG_ABI_VERSION:   axi_rdata <= ABI_VERSION;
                        REG_FRAME_ID_0:    axi_rdata <= buffer_frame_id_0;
                        REG_FRAME_ID_1:    axi_rdata <= buffer_frame_id_1;
                        REG_LATEST_FRAME:  axi_rdata <= latest_frame_id;
                        REG_DROP_COUNT:    axi_rdata <= frame_drop_count;
                        REG_FORMAT_ERRORS: axi_rdata <= format_error_count;
                        REG_SCCB_ADDRESS:  axi_rdata <= {9'd0, sccb_device_addr, sccb_register_addr};
                        REG_SCCB_DATA:     axi_rdata <= {23'd0, sccb_read_valid_sticky, sccb_read_data};
                        REG_DEBUG_WORD_ADDR: axi_rdata <= {19'd0, debug_word_addr};
                        REG_DEBUG_WORD_DATA: begin
                            if (locator_busy || roi_same_frame_busy ||
                                !debug_target_valid)
                                axi_rresp <= 2'b10;
                            else
                                axi_rdata <= debug_word_data;
                        end

                        REG_ROI_XY:
                            axi_rdata <= {6'd0, roi_desc_y0, 6'd0, roi_desc_x0};
                        REG_ROI_SIZE:
                            axi_rdata <= {22'd0, roi_desc_side};
                        REG_ROI_TAG:
                            axi_rdata <= roi_desc_tag;
                        REG_ROI_CONTROL:
                            axi_rdata <= {
                                28'd0, roi_buffer_id, roi_same_frame_mode,
                                classifier_input_select, 1'b0
                            };
                        REG_ROI_STATUS:
                            axi_rdata <= {
                                25'd0, roi_same_frame_busy, classifier_busy,
                                roi_error_sticky,
                                roi_done_sticky, roi_busy, roi_desc_armed,
                                classifier_input_select
                            };
                        REG_ROI_DONE_TAG:
                            axi_rdata <= roi_completed_tag;
                        REG_ROI_FRAME_ID:
                            axi_rdata <= roi_source_frame_id;
                        default: axi_rresp <= 2'b10;
                    endcase
                end
            end else if (axi_rvalid && S_AXI_RREADY) begin
                axi_rvalid <= 1'b0;
            end
        end
    end

    wire _unused_ok = &{1'b0, S_AXI_AWPROT, S_AXI_ARPROT};
endmodule
