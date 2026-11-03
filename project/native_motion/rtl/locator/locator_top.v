// ============================================================================
// Phase 2-L1 locator control/data top.
// USE_CNN_CORE=0 preserves the fast control-path stub regression;
// USE_CNN_CORE=1 selects the bit-exact five-layer Locator datapath.
// ============================================================================
`timescale 1ns / 1ps

module locator_top #(
    parameter integer C_S_AXI_DATA_WIDTH = 32,
    parameter integer C_S_AXI_ADDR_WIDTH = 14,
    parameter integer USE_CNN_CORE = 0,
    parameter integer LOCATOR_OUTPUT_LANES = 8
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

    // Native port B of the 32 KiB input ping/pong BRAM.
    output wire                              input_bram_en,
    output wire [12:0]                       input_bram_addr,
    input  wire [31:0]                       input_bram_data,

    // Native port B of the 16 KiB output ping/pong BRAM.
    output wire                              output_bram_we,
    output wire [11:0]                       output_bram_addr,
    output wire [31:0]                       output_bram_data,

    output reg                               irq_to_ps,
    output wire                              busy_to_camera
);

    wire cmd_start;
    wire cmd_soft_reset;
    wire cmd_model_commit;
    wire cmd_model_invalidate;
    wire cmd_clear_error;
    wire cmd_clear_irq;
    wire cmd_output_release;
    wire [1:0] output_release_mask;
    wire model_dirty;
    wire axi_error_event;
    wire [7:0] axi_error_code;
    wire axi_drop_event;

    wire [31:0] cfg_input_buffer_id;
    wire [31:0] cfg_input_frame_id;
    wire [1:0]  irq_enable;
    wire [31:0] model_word_count;
    wire [31:0] desc_word_count;
    wire [31:0] expected_model_crc;
    wire [31:0] expected_desc_crc;
    wire [31:0] model_version;
    wire [31:0] desc_version;

    wire model_wr_en;
    wire [10:0] model_wr_addr;
    wire [31:0] model_wr_data;
    wire desc_wr_en;
    wire [9:0] desc_wr_addr;
    wire [31:0] desc_wr_data;

    wire start_allowed;
    wire [7:0] start_error_code;
    wire release_allowed;
    wire status_idle;
    wire status_busy;
    wire status_done;
    wire status_error;
    wire model_valid;
    wire model_error;
    wire [7:0] error_code;
    wire [1:0] input_free_mask;
    wire [1:0] output_valid_mask;
    wire output_buffer_id;
    wire [31:0] output_frame_id_0;
    wire [31:0] output_frame_id_1;
    wire [1:0] irq_status;
    wire irq_to_ps_raw;
    wire [31:0] stall_count;
    wire [31:0] drop_count;
    wire [31:0] top1_cell_0;
    wire [31:0] top1_conf_0;
    wire [31:0] top1_dx_0;
    wire [31:0] top1_dy_0;
    wire [31:0] top1_width_0;
    wire [31:0] top1_height_0;
    wire [31:0] top1_cell_1;
    wire [31:0] top1_conf_1;
    wire [31:0] top1_dx_1;
    wire [31:0] top1_dy_1;
    wire [31:0] top1_width_1;
    wire [31:0] top1_height_1;

    wire commit_start;
    wire commit_abort;
    wire commit_busy;
    wire commit_done;
    wire commit_success;
    wire [7:0] commit_error_code;
    wire [31:0] computed_model_crc;
    wire [31:0] computed_desc_crc;

    wire model_rd_en;
    wire [10:0] model_rd_addr;
    wire [31:0] model_rd_data;
    wire commit_model_rd_en;
    wire [10:0] commit_model_rd_addr;
    wire core_model_rd_en;
    wire [10:0] core_model_rd_addr;
    wire [7:0] core_model_lane_rd_en;
    wire [87:0] core_model_lane_rd_addr;
    wire [255:0] core_model_lane_rd_data;
    wire desc_rd_en;
    wire [9:0] desc_rd_addr;
    wire [31:0] desc_rd_data;

    wire core_start;
    wire core_input_buffer_id;
    wire core_output_buffer_id;
    wire [31:0] core_frame_id;
    wire core_busy;
    wire core_done;
    wire core_input_release;
    wire core_stall;
    wire core_rst_n = s_axi_aresetn && !cmd_soft_reset;

    locator_axi_lite_slave #(
        .C_S_AXI_DATA_WIDTH(C_S_AXI_DATA_WIDTH),
        .C_S_AXI_ADDR_WIDTH(C_S_AXI_ADDR_WIDTH)
    ) u_axi (
        .S_AXI_ACLK(s_axi_aclk),
        .S_AXI_ARESETN(s_axi_aresetn),
        .S_AXI_AWADDR(s_axi_awaddr),
        .S_AXI_AWPROT(s_axi_awprot),
        .S_AXI_AWVALID(s_axi_awvalid),
        .S_AXI_AWREADY(s_axi_awready),
        .S_AXI_WDATA(s_axi_wdata),
        .S_AXI_WSTRB(s_axi_wstrb),
        .S_AXI_WVALID(s_axi_wvalid),
        .S_AXI_WREADY(s_axi_wready),
        .S_AXI_BRESP(s_axi_bresp),
        .S_AXI_BVALID(s_axi_bvalid),
        .S_AXI_BREADY(s_axi_bready),
        .S_AXI_ARADDR(s_axi_araddr),
        .S_AXI_ARPROT(s_axi_arprot),
        .S_AXI_ARVALID(s_axi_arvalid),
        .S_AXI_ARREADY(s_axi_arready),
        .S_AXI_RDATA(s_axi_rdata),
        .S_AXI_RRESP(s_axi_rresp),
        .S_AXI_RVALID(s_axi_rvalid),
        .S_AXI_RREADY(s_axi_rready),
        .cmd_start(cmd_start),
        .cmd_soft_reset(cmd_soft_reset),
        .cmd_model_commit(cmd_model_commit),
        .cmd_model_invalidate(cmd_model_invalidate),
        .cmd_clear_error(cmd_clear_error),
        .cmd_clear_irq(cmd_clear_irq),
        .cmd_output_release(cmd_output_release),
        .output_release_mask(output_release_mask),
        .model_dirty(model_dirty),
        .axi_error_event(axi_error_event),
        .axi_error_code(axi_error_code),
        .axi_drop_event(axi_drop_event),
        .cfg_input_buffer_id(cfg_input_buffer_id),
        .cfg_input_frame_id(cfg_input_frame_id),
        .irq_enable(irq_enable),
        .model_word_count(model_word_count),
        .desc_word_count(desc_word_count),
        .expected_model_crc(expected_model_crc),
        .expected_desc_crc(expected_desc_crc),
        .model_version(model_version),
        .desc_version(desc_version),
        .model_wr_en(model_wr_en),
        .model_wr_addr(model_wr_addr),
        .model_wr_data(model_wr_data),
        .desc_wr_en(desc_wr_en),
        .desc_wr_addr(desc_wr_addr),
        .desc_wr_data(desc_wr_data),
        .start_allowed(start_allowed),
        .start_error_code(start_error_code),
        .status_idle(status_idle),
        .status_busy(status_busy),
        .status_done(status_done),
        .status_error(status_error),
        .model_valid(model_valid),
        .model_error(model_error),
        .error_code(error_code),
        .input_free_mask(input_free_mask),
        .output_valid_mask(output_valid_mask),
        .output_buffer_id(output_buffer_id),
        .output_frame_id_0(output_frame_id_0),
        .output_frame_id_1(output_frame_id_1),
        .irq_status(irq_status),
        .computed_model_crc(computed_model_crc),
        .computed_desc_crc(computed_desc_crc),
        .stall_count(stall_count),
        .drop_count(drop_count),
        .top1_cell_0(top1_cell_0),
        .top1_conf_0(top1_conf_0),
        .top1_dx_0(top1_dx_0),
        .top1_dy_0(top1_dy_0),
        .top1_width_0(top1_width_0),
        .top1_height_0(top1_height_0),
        .top1_cell_1(top1_cell_1),
        .top1_conf_1(top1_conf_1),
        .top1_dx_1(top1_dx_1),
        .top1_dy_1(top1_dy_1),
        .top1_width_1(top1_width_1),
        .top1_height_1(top1_height_1)
    );

    locator_model_mem #(
        .READ_REPLICAS((USE_CNN_CORE != 0 && LOCATOR_OUTPUT_LANES == 8) ? 8 : 1)
    ) u_model_mem (
        .clk(s_axi_aclk),
        .wr_en(model_wr_en),
        .wr_addr(model_wr_addr),
        .wr_data(model_wr_data),
        .rd_en(model_rd_en),
        .rd_addr(model_rd_addr),
        .rd_data(model_rd_data),
        .lane_rd_en(core_model_lane_rd_en),
        .lane_rd_addr(core_model_lane_rd_addr),
        .lane_rd_data(core_model_lane_rd_data)
    );

    locator_desc_mem u_desc_mem (
        .clk(s_axi_aclk),
        .wr_en(desc_wr_en),
        .wr_addr(desc_wr_addr),
        .wr_data(desc_wr_data),
        .rd_en(desc_rd_en),
        .rd_addr(desc_rd_addr),
        .rd_data(desc_rd_data)
    );

    locator_model_commit_fsm u_commit (
        .clk(s_axi_aclk),
        .rst_n(s_axi_aresetn),
        .start(commit_start),
        .abort(commit_abort),
        .model_word_count(model_word_count),
        .desc_word_count(desc_word_count),
        .expected_model_crc(expected_model_crc),
        .expected_desc_crc(expected_desc_crc),
        .model_version(model_version),
        .desc_version(desc_version),
        .model_rd_en(commit_model_rd_en),
        .model_rd_addr(commit_model_rd_addr),
        .model_rd_data(model_rd_data),
        .desc_rd_en(desc_rd_en),
        .desc_rd_addr(desc_rd_addr),
        .desc_rd_data(desc_rd_data),
        .busy(commit_busy),
        .done(commit_done),
        .success(commit_success),
        .error_code(commit_error_code),
        .computed_model_crc(computed_model_crc),
        .computed_desc_crc(computed_desc_crc)
    );

    // MODEL_COMMIT and inference are mutually exclusive by control contract.
    // Give the CRC walker explicit priority so a commit can never observe an
    // address driven by the compute core.
    assign model_rd_en   = commit_busy ? commit_model_rd_en   : core_model_rd_en;
    assign model_rd_addr = commit_busy ? commit_model_rd_addr : core_model_rd_addr;

    locator_ctrl_fsm u_ctrl (
        .clk(s_axi_aclk),
        .rst_n(s_axi_aresetn),
        .cmd_start(cmd_start),
        .cmd_soft_reset(cmd_soft_reset),
        .cmd_model_commit(cmd_model_commit),
        .cmd_model_invalidate(cmd_model_invalidate),
        .cmd_clear_error(cmd_clear_error),
        .cmd_clear_irq(cmd_clear_irq),
        .cmd_output_release(cmd_output_release),
        .output_release_mask(output_release_mask),
        .model_dirty(model_dirty),
        .axi_error_event(axi_error_event),
        .axi_error_code(axi_error_code),
        .axi_drop_event(axi_drop_event),
        .cfg_input_buffer_id(cfg_input_buffer_id),
        .cfg_input_frame_id(cfg_input_frame_id),
        .irq_enable(irq_enable),
        .start_allowed(start_allowed),
        .start_error_code(start_error_code),
        .release_allowed(release_allowed),
        .commit_start(commit_start),
        .commit_abort(commit_abort),
        .commit_busy(commit_busy),
        .commit_done(commit_done),
        .commit_success(commit_success),
        .commit_error_code(commit_error_code),
        .core_start(core_start),
        .core_input_buffer_id(core_input_buffer_id),
        .core_output_buffer_id(core_output_buffer_id),
        .core_frame_id(core_frame_id),
        .core_done(core_done),
        .core_input_release(core_input_release),
        .core_stall(core_stall),
        .status_idle(status_idle),
        .status_busy(status_busy),
        .status_done(status_done),
        .status_error(status_error),
        .model_valid(model_valid),
        .model_error(model_error),
        .error_code(error_code),
        .input_free_mask(input_free_mask),
        .output_valid_mask(output_valid_mask),
        .output_buffer_id(output_buffer_id),
        .output_frame_id_0(output_frame_id_0),
        .output_frame_id_1(output_frame_id_1),
        .irq_status(irq_status),
        .irq_to_ps(irq_to_ps_raw),
        .stall_count(stall_count),
        .drop_count(drop_count)
    );

    // Register the sticky IRQ level in its source clock domain before the
    // two-flop destination synchronizer.  Besides giving the CDC path a clean
    // register-to-register launch, the one-cycle latency is harmless because
    // irq_status remains asserted until CLEAR_IRQ.
    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn)
            irq_to_ps <= 1'b0;
        else
            irq_to_ps <= irq_to_ps_raw;
    end

    generate
        if (USE_CNN_CORE == 0) begin : g_stub_core
            assign core_model_rd_en   = 1'b0;
            assign core_model_rd_addr = 11'd0;
            assign core_model_lane_rd_en = 8'd0;
            assign core_model_lane_rd_addr = 88'd0;
            locator_stub_engine u_stub (
                .clk(s_axi_aclk),
                .rst_n(core_rst_n),
                .start(core_start),
                .input_buffer_id(core_input_buffer_id),
                .output_buffer_id(core_output_buffer_id),
                .frame_id(core_frame_id),
                .input_bram_en(input_bram_en),
                .input_bram_addr(input_bram_addr),
                .input_bram_data(input_bram_data),
                .output_bram_we(output_bram_we),
                .output_bram_addr(output_bram_addr),
                .output_bram_data(output_bram_data),
                .busy(core_busy),
                .done(core_done),
                .input_release(core_input_release),
                .stall(core_stall)
            );
        end else if (LOCATOR_OUTPUT_LANES == 8) begin : g_cnn_core_8lane
            wire        debug_acc_valid_unused;
            wire [2:0]  debug_layer_unused;
            wire [17:0] debug_acc_index_unused;
            wire [31:0] debug_acc_data_unused;
            wire        debug_act_valid_unused;
            wire [14:0] debug_act_index_unused;
            wire [7:0]  debug_act_data_unused;

            assign core_model_rd_en   = 1'b0;
            assign core_model_rd_addr = 11'd0;

            locator_cnn_engine_8lane u_cnn (
                .clk(s_axi_aclk),
                .rst_n(core_rst_n),
                .start(core_start),
                .input_buffer_id(core_input_buffer_id),
                .output_buffer_id(core_output_buffer_id),
                .frame_id(core_frame_id),
                .input_bram_en(input_bram_en),
                .input_bram_addr(input_bram_addr),
                .input_bram_data(input_bram_data),
                .output_bram_we(output_bram_we),
                .output_bram_addr(output_bram_addr),
                .output_bram_data(output_bram_data),
                .model_lane_rd_en(core_model_lane_rd_en),
                .model_lane_rd_addr(core_model_lane_rd_addr),
                .model_lane_rd_data(core_model_lane_rd_data),
                .busy(core_busy),
                .done(core_done),
                .input_release(core_input_release),
                .stall(core_stall),
                .debug_acc_valid(debug_acc_valid_unused),
                .debug_layer(debug_layer_unused),
                .debug_acc_index(debug_acc_index_unused),
                .debug_acc_data(debug_acc_data_unused),
                .debug_act_valid(debug_act_valid_unused),
                .debug_act_index(debug_act_index_unused),
                .debug_act_data(debug_act_data_unused)
            );
        end else begin : g_cnn_core_scalar
            wire        debug_acc_valid_unused;
            wire [2:0]  debug_layer_unused;
            wire [17:0] debug_acc_index_unused;
            wire [31:0] debug_acc_data_unused;
            wire        debug_act_valid_unused;
            wire [14:0] debug_act_index_unused;
            wire [7:0]  debug_act_data_unused;

            assign core_model_lane_rd_en = 8'd0;
            assign core_model_lane_rd_addr = 88'd0;

            locator_cnn_engine u_cnn (
                .clk(s_axi_aclk),
                .rst_n(core_rst_n),
                .start(core_start),
                .input_buffer_id(core_input_buffer_id),
                .output_buffer_id(core_output_buffer_id),
                .frame_id(core_frame_id),
                .input_bram_en(input_bram_en),
                .input_bram_addr(input_bram_addr),
                .input_bram_data(input_bram_data),
                .output_bram_we(output_bram_we),
                .output_bram_addr(output_bram_addr),
                .output_bram_data(output_bram_data),
                .model_rd_en(core_model_rd_en),
                .model_rd_addr(core_model_rd_addr),
                .model_rd_data(model_rd_data),
                .busy(core_busy),
                .done(core_done),
                .input_release(core_input_release),
                .stall(core_stall),
                .debug_acc_valid(debug_acc_valid_unused),
                .debug_layer(debug_layer_unused),
                .debug_acc_index(debug_acc_index_unused),
                .debug_acc_data(debug_acc_data_unused),
                .debug_act_valid(debug_act_valid_unused),
                .debug_act_index(debug_act_index_unused),
                .debug_act_data(debug_act_data_unused)
            );
        end
    endgenerate

    locator_top1_reducer u_top1_reducer (
        .clk(s_axi_aclk),
        .rst_n(core_rst_n),
        .start(core_start),
        .output_buffer_id(core_output_buffer_id),
        .done(core_done),
        .output_we(output_bram_we),
        .output_addr(output_bram_addr),
        .output_data(output_bram_data),
        .top1_cell_0(top1_cell_0),
        .top1_conf_0(top1_conf_0),
        .top1_dx_0(top1_dx_0),
        .top1_dy_0(top1_dy_0),
        .top1_width_0(top1_width_0),
        .top1_height_0(top1_height_0),
        .top1_cell_1(top1_cell_1),
        .top1_conf_1(top1_conf_1),
        .top1_dx_1(top1_dx_1),
        .top1_dy_1(top1_dy_1),
        .top1_width_1(top1_width_1),
        .top1_height_1(top1_height_1)
    );

    assign busy_to_camera = status_busy;

    wire _unused_core_busy = core_busy;

endmodule
