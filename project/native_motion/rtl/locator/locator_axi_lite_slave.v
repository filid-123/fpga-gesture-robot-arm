// ============================================================================
// Phase 2-L1 custom AXI4-Lite slave.
// Owns locator control registers and protected model/descriptor windows.
// AW and W channels are accepted independently; all writes are full 32-bit.
// ============================================================================
`timescale 1ns / 1ps

module locator_axi_lite_slave #(
    parameter integer C_S_AXI_DATA_WIDTH = 32,
    parameter integer C_S_AXI_ADDR_WIDTH = 14,
    parameter [31:0]  ABI_VERSION        = 32'h0000_0302
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

    output reg         cmd_start,
    output reg         cmd_soft_reset,
    output reg         cmd_model_commit,
    output reg         cmd_model_invalidate,
    output reg         cmd_clear_error,
    output reg         cmd_clear_irq,
    output reg         cmd_output_release,
    output reg  [1:0]  output_release_mask,
    output reg         model_dirty,
    output reg         axi_error_event,
    output reg  [7:0]  axi_error_code,
    output reg         axi_drop_event,

    output reg  [31:0] cfg_input_buffer_id,
    output reg  [31:0] cfg_input_frame_id,
    output reg  [1:0]  irq_enable,
    output reg  [31:0] model_word_count,
    output reg  [31:0] desc_word_count,
    output reg  [31:0] expected_model_crc,
    output reg  [31:0] expected_desc_crc,
    output reg  [31:0] model_version,
    output reg  [31:0] desc_version,

    output reg         model_wr_en,
    output reg  [10:0] model_wr_addr,
    output reg  [31:0] model_wr_data,
    output reg         desc_wr_en,
    output reg  [9:0]  desc_wr_addr,
    output reg  [31:0] desc_wr_data,

    input  wire        start_allowed,
    input  wire [7:0]  start_error_code,
    input  wire        status_idle,
    input  wire        status_busy,
    input  wire        status_done,
    input  wire        status_error,
    input  wire        model_valid,
    input  wire        model_error,
    input  wire [7:0]  error_code,
    input  wire [1:0]  input_free_mask,
    input  wire [1:0]  output_valid_mask,
    input  wire        output_buffer_id,
    input  wire [31:0] output_frame_id_0,
    input  wire [31:0] output_frame_id_1,
    input  wire [1:0]  irq_status,
    input  wire [31:0] computed_model_crc,
    input  wire [31:0] computed_desc_crc,
    input  wire [31:0] stall_count,
    input  wire [31:0] drop_count,
    input  wire [31:0] top1_cell_0,
    input  wire [31:0] top1_conf_0,
    input  wire [31:0] top1_dx_0,
    input  wire [31:0] top1_dy_0,
    input  wire [31:0] top1_width_0,
    input  wire [31:0] top1_height_0,
    input  wire [31:0] top1_cell_1,
    input  wire [31:0] top1_conf_1,
    input  wire [31:0] top1_dx_1,
    input  wire [31:0] top1_dy_1,
    input  wire [31:0] top1_width_1,
    input  wire [31:0] top1_height_1
);

    localparam [7:0] ERR_BUSY             = 8'h02;
    localparam [7:0] ERR_INPUT_NOT_FREE   = 8'h04;
    localparam [7:0] ERR_NO_OUTPUT_BUFFER = 8'h05;
    localparam [7:0] ERR_OUTPUT_NOT_VALID = 8'h06;
    localparam [7:0] ERR_AXI_WRITE_FORMAT = 8'h07;
    localparam [7:0] ERR_COMMAND_CONFLICT = 8'h08;
    localparam [7:0] ERR_ACCESS_OR_RANGE  = 8'h09;

    localparam [13:0] REG_CONTROL             = 14'h0000;
    localparam [13:0] REG_STATUS              = 14'h0004;
    localparam [13:0] REG_IRQ_ENABLE          = 14'h0008;
    localparam [13:0] REG_IRQ_STATUS          = 14'h000C;
    localparam [13:0] REG_ABI_VERSION         = 14'h0010;
    localparam [13:0] REG_ERROR_CODE          = 14'h0014;
    localparam [13:0] REG_INPUT_BUFFER_ID     = 14'h0018;
    localparam [13:0] REG_INPUT_FRAME_ID      = 14'h001C;
    localparam [13:0] REG_INPUT_FREE_MASK     = 14'h0020;
    localparam [13:0] REG_OUTPUT_BUFFER_ID    = 14'h0024;
    localparam [13:0] REG_OUTPUT_FRAME_ID_0   = 14'h0028;
    localparam [13:0] REG_OUTPUT_FRAME_ID_1   = 14'h002C;
    localparam [13:0] REG_OUTPUT_VALID_MASK   = 14'h0030;
    localparam [13:0] REG_OUTPUT_RELEASE      = 14'h0034;
    localparam [13:0] REG_MODEL_WORD_COUNT    = 14'h0038;
    localparam [13:0] REG_DESC_WORD_COUNT     = 14'h003C;
    localparam [13:0] REG_EXPECT_MODEL_CRC    = 14'h0040;
    localparam [13:0] REG_COMPUTED_MODEL_CRC  = 14'h0044;
    localparam [13:0] REG_EXPECT_DESC_CRC     = 14'h0048;
    localparam [13:0] REG_COMPUTED_DESC_CRC   = 14'h004C;
    localparam [13:0] REG_MODEL_VERSION       = 14'h0050;
    localparam [13:0] REG_DESC_VERSION        = 14'h0054;
    localparam [13:0] REG_STALL_COUNT         = 14'h0058;
    localparam [13:0] REG_DROP_COUNT          = 14'h005C;
    localparam [13:0] REG_TOP1_CAPABILITY     = 14'h0060;
    localparam [13:0] REG_TOP1_CELL_0         = 14'h0064;
    localparam [13:0] REG_TOP1_CONF_0         = 14'h0068;
    localparam [13:0] REG_TOP1_DX_0           = 14'h006C;
    localparam [13:0] REG_TOP1_DY_0           = 14'h0070;
    localparam [13:0] REG_TOP1_WIDTH_0        = 14'h0074;
    localparam [13:0] REG_TOP1_HEIGHT_0       = 14'h0078;
    localparam [13:0] REG_TOP1_CELL_1         = 14'h007C;
    localparam [13:0] REG_TOP1_CONF_1         = 14'h0080;
    localparam [13:0] REG_TOP1_DX_1           = 14'h0084;
    localparam [13:0] REG_TOP1_DY_1           = 14'h0088;
    localparam [13:0] REG_TOP1_WIDTH_1        = 14'h008C;
    localparam [13:0] REG_TOP1_HEIGHT_1       = 14'h0090;

    reg aw_pending;
    reg [C_S_AXI_ADDR_WIDTH-1:0] awaddr_hold;
    reg w_pending;
    reg [31:0] wdata_hold;
    reg [3:0]  wstrb_hold;
    reg        axi_bvalid;
    reg [1:0]  axi_bresp;
    reg        axi_rvalid;
    reg [31:0] axi_rdata;
    reg [1:0]  axi_rresp;

    wire aw_accept = S_AXI_AWVALID && S_AXI_AWREADY;
    wire w_accept  = S_AXI_WVALID  && S_AXI_WREADY;
    wire write_commit = aw_pending && w_pending && !axi_bvalid;
    wire ar_accept = S_AXI_ARVALID && S_AXI_ARREADY;

    assign S_AXI_AWREADY = !aw_pending && !axi_bvalid;
    assign S_AXI_WREADY  = !w_pending  && !axi_bvalid;
    assign S_AXI_BVALID  = axi_bvalid;
    assign S_AXI_BRESP   = axi_bresp;
    assign S_AXI_ARREADY = !axi_rvalid;
    assign S_AXI_RVALID  = axi_rvalid;
    assign S_AXI_RDATA   = axi_rdata;
    assign S_AXI_RRESP   = axi_rresp;

    function multiple_command_bits;
        input [5:0] value;
        begin
            multiple_command_bits = |(value & (value - 6'd1));
        end
    endfunction

    task reject_write;
        input [7:0] code;
        begin
            axi_bresp       <= 2'b10;
            axi_error_event <= 1'b1;
            axi_error_code  <= code;
        end
    endtask

    always @(posedge S_AXI_ACLK) begin
        if (!S_AXI_ARESETN) begin
            aw_pending              <= 1'b0;
            awaddr_hold             <= {C_S_AXI_ADDR_WIDTH{1'b0}};
            w_pending               <= 1'b0;
            wdata_hold              <= 32'd0;
            wstrb_hold              <= 4'd0;
            axi_bvalid              <= 1'b0;
            axi_bresp               <= 2'b00;
            cmd_start               <= 1'b0;
            cmd_soft_reset          <= 1'b0;
            cmd_model_commit        <= 1'b0;
            cmd_model_invalidate    <= 1'b0;
            cmd_clear_error         <= 1'b0;
            cmd_clear_irq           <= 1'b0;
            cmd_output_release      <= 1'b0;
            output_release_mask     <= 2'b00;
            model_dirty             <= 1'b0;
            axi_error_event         <= 1'b0;
            axi_error_code          <= 8'd0;
            axi_drop_event          <= 1'b0;
            cfg_input_buffer_id     <= 32'd0;
            cfg_input_frame_id      <= 32'd0;
            irq_enable              <= 2'b00;
            model_word_count        <= 32'd0;
            desc_word_count         <= 32'd0;
            expected_model_crc      <= 32'd0;
            expected_desc_crc       <= 32'd0;
            model_version           <= 32'd0;
            desc_version            <= 32'd0;
            model_wr_en             <= 1'b0;
            model_wr_addr           <= 11'd0;
            model_wr_data           <= 32'd0;
            desc_wr_en              <= 1'b0;
            desc_wr_addr            <= 10'd0;
            desc_wr_data            <= 32'd0;
        end else begin
            cmd_start            <= 1'b0;
            cmd_soft_reset       <= 1'b0;
            cmd_model_commit     <= 1'b0;
            cmd_model_invalidate <= 1'b0;
            cmd_clear_error      <= 1'b0;
            cmd_clear_irq        <= 1'b0;
            cmd_output_release   <= 1'b0;
            model_dirty          <= 1'b0;
            axi_error_event      <= 1'b0;
            axi_drop_event       <= 1'b0;
            model_wr_en          <= 1'b0;
            desc_wr_en           <= 1'b0;

            if (aw_accept) begin
                awaddr_hold <= S_AXI_AWADDR;
                aw_pending  <= 1'b1;
            end
            if (w_accept) begin
                wdata_hold <= S_AXI_WDATA;
                wstrb_hold <= S_AXI_WSTRB;
                w_pending  <= 1'b1;
            end

            if (write_commit) begin
                aw_pending <= 1'b0;
                w_pending  <= 1'b0;
                axi_bvalid <= 1'b1;
                axi_bresp  <= 2'b00;

                if ((awaddr_hold[1:0] != 2'b00) || (wstrb_hold != 4'b1111)) begin
                    reject_write(ERR_AXI_WRITE_FORMAT);
                end else if ((awaddr_hold >= 14'h1000) && (awaddr_hold <= 14'h2FFF)) begin
                    if (status_busy) begin
                        reject_write(ERR_BUSY);
                    end else begin
                        model_wr_en   <= 1'b1;
                        model_wr_addr <= (awaddr_hold - 14'h1000) >> 2;
                        model_wr_data <= wdata_hold;
                        model_dirty   <= 1'b1;
                    end
                end else if ((awaddr_hold >= 14'h3000) && (awaddr_hold <= 14'h3FFF)) begin
                    if (status_busy) begin
                        reject_write(ERR_BUSY);
                    end else begin
                        desc_wr_en   <= 1'b1;
                        desc_wr_addr <= (awaddr_hold - 14'h3000) >> 2;
                        desc_wr_data <= wdata_hold;
                        model_dirty  <= 1'b1;
                    end
                end else begin
                    case (awaddr_hold)
                        REG_CONTROL: begin
                            if (wdata_hold[31:6] != 0) begin
                                reject_write(ERR_ACCESS_OR_RANGE);
                            end else if (multiple_command_bits(wdata_hold[5:0])) begin
                                reject_write(ERR_COMMAND_CONFLICT);
                            end else begin
                                case (wdata_hold[5:0])
                                    6'b000001: begin
                                        if (!start_allowed) begin
                                            reject_write(start_error_code);
                                            if ((start_error_code == ERR_BUSY) ||
                                                (start_error_code == ERR_INPUT_NOT_FREE) ||
                                                (start_error_code == ERR_NO_OUTPUT_BUFFER))
                                                axi_drop_event <= 1'b1;
                                        end else begin
                                            cmd_start <= 1'b1;
                                        end
                                    end
                                    6'b000010: cmd_soft_reset       <= 1'b1;
                                    6'b000100: begin
                                        if (status_busy)
                                            reject_write(ERR_BUSY);
                                        else
                                            cmd_model_commit <= 1'b1;
                                    end
                                    6'b001000: begin
                                        if (status_busy)
                                            reject_write(ERR_BUSY);
                                        else
                                            cmd_model_invalidate <= 1'b1;
                                    end
                                    6'b010000: cmd_clear_error <= 1'b1;
                                    6'b100000: cmd_clear_irq   <= 1'b1;
                                    6'b000000: begin end
                                    default: reject_write(ERR_ACCESS_OR_RANGE);
                                endcase
                            end
                        end

                        REG_IRQ_ENABLE: begin
                            if (wdata_hold[31:2] != 0)
                                reject_write(ERR_ACCESS_OR_RANGE);
                            else
                                irq_enable <= wdata_hold[1:0];
                        end

                        REG_INPUT_BUFFER_ID: cfg_input_buffer_id <= wdata_hold;
                        REG_INPUT_FRAME_ID:  cfg_input_frame_id  <= wdata_hold;

                        REG_OUTPUT_RELEASE: begin
                            if (wdata_hold[31:2] != 0) begin
                                reject_write(ERR_ACCESS_OR_RANGE);
                            end else if (((wdata_hold[1:0] & ~output_valid_mask) != 0) &&
                                         (wdata_hold[1:0] != 0)) begin
                                reject_write(ERR_OUTPUT_NOT_VALID);
                            end else begin
                                output_release_mask <= wdata_hold[1:0];
                                cmd_output_release  <= 1'b1;
                            end
                        end

                        REG_MODEL_WORD_COUNT,
                        REG_DESC_WORD_COUNT,
                        REG_EXPECT_MODEL_CRC,
                        REG_EXPECT_DESC_CRC,
                        REG_MODEL_VERSION,
                        REG_DESC_VERSION: begin
                            if (status_busy) begin
                                reject_write(ERR_BUSY);
                            end else begin
                                case (awaddr_hold)
                                    REG_MODEL_WORD_COUNT: model_word_count   <= wdata_hold;
                                    REG_DESC_WORD_COUNT:  desc_word_count    <= wdata_hold;
                                    REG_EXPECT_MODEL_CRC: expected_model_crc <= wdata_hold;
                                    REG_EXPECT_DESC_CRC:  expected_desc_crc  <= wdata_hold;
                                    REG_MODEL_VERSION:    model_version      <= wdata_hold;
                                    REG_DESC_VERSION:     desc_version       <= wdata_hold;
                                    default: begin end
                                endcase
                                model_dirty <= 1'b1;
                            end
                        end

                        default: reject_write(ERR_ACCESS_OR_RANGE);
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
            axi_rdata  <= 32'd0;
            axi_rresp  <= 2'b00;
        end else begin
            if (ar_accept) begin
                axi_rvalid <= 1'b1;
                axi_rdata  <= 32'd0;
                axi_rresp  <= 2'b00;
                if (S_AXI_ARADDR[1:0] != 2'b00) begin
                    axi_rresp <= 2'b10;
                end else begin
                    case (S_AXI_ARADDR)
                        REG_CONTROL:            axi_rdata <= 32'd0;
                        REG_STATUS:             axi_rdata <= {26'd0, model_error, model_valid,
                                                              status_error, status_done,
                                                              status_busy, status_idle};
                        REG_IRQ_ENABLE:         axi_rdata <= {30'd0, irq_enable};
                        REG_IRQ_STATUS:         axi_rdata <= {30'd0, irq_status};
                        REG_ABI_VERSION:        axi_rdata <= ABI_VERSION;
                        REG_ERROR_CODE:         axi_rdata <= {24'd0, error_code};
                        REG_INPUT_BUFFER_ID:    axi_rdata <= cfg_input_buffer_id;
                        REG_INPUT_FRAME_ID:     axi_rdata <= cfg_input_frame_id;
                        REG_INPUT_FREE_MASK:    axi_rdata <= {30'd0, input_free_mask};
                        REG_OUTPUT_BUFFER_ID:   axi_rdata <= {31'd0, output_buffer_id};
                        REG_OUTPUT_FRAME_ID_0:  axi_rdata <= output_frame_id_0;
                        REG_OUTPUT_FRAME_ID_1:  axi_rdata <= output_frame_id_1;
                        REG_OUTPUT_VALID_MASK:  axi_rdata <= {30'd0, output_valid_mask};
                        REG_MODEL_WORD_COUNT:   axi_rdata <= model_word_count;
                        REG_DESC_WORD_COUNT:    axi_rdata <= desc_word_count;
                        REG_EXPECT_MODEL_CRC:   axi_rdata <= expected_model_crc;
                        REG_COMPUTED_MODEL_CRC: axi_rdata <= computed_model_crc;
                        REG_EXPECT_DESC_CRC:    axi_rdata <= expected_desc_crc;
                        REG_COMPUTED_DESC_CRC:  axi_rdata <= computed_desc_crc;
                        REG_MODEL_VERSION:      axi_rdata <= model_version;
                        REG_DESC_VERSION:       axi_rdata <= desc_version;
                        REG_STALL_COUNT:        axi_rdata <= stall_count;
                        REG_DROP_COUNT:         axi_rdata <= drop_count;
                        REG_TOP1_CAPABILITY:    axi_rdata <= 32'h5431_5231; // "T1R1"
                        REG_TOP1_CELL_0:        axi_rdata <= top1_cell_0;
                        REG_TOP1_CONF_0:        axi_rdata <= top1_conf_0;
                        REG_TOP1_DX_0:          axi_rdata <= top1_dx_0;
                        REG_TOP1_DY_0:          axi_rdata <= top1_dy_0;
                        REG_TOP1_WIDTH_0:       axi_rdata <= top1_width_0;
                        REG_TOP1_HEIGHT_0:      axi_rdata <= top1_height_0;
                        REG_TOP1_CELL_1:        axi_rdata <= top1_cell_1;
                        REG_TOP1_CONF_1:        axi_rdata <= top1_conf_1;
                        REG_TOP1_DX_1:          axi_rdata <= top1_dx_1;
                        REG_TOP1_DY_1:          axi_rdata <= top1_dy_1;
                        REG_TOP1_WIDTH_1:       axi_rdata <= top1_width_1;
                        REG_TOP1_HEIGHT_1:      axi_rdata <= top1_height_1;
                        default: begin
                            axi_rdata <= 32'd0;
                            axi_rresp <= 2'b10;
                        end
                    endcase
                end
            end else if (axi_rvalid && S_AXI_RREADY) begin
                axi_rvalid <= 1'b0;
            end
        end
    end

    wire _unused_ok = &{1'b0, S_AXI_AWPROT, S_AXI_ARPROT};

endmodule
