// ============================================================================
// Locator model state, double-buffer ownership, first-fault and IRQ controller.
// All signals use the AXI/control clock in Phase 2-L1 skeleton.
// ============================================================================
`timescale 1ns / 1ps

module locator_ctrl_fsm #(
    parameter [7:0] ERR_MODEL_INVALID     = 8'h01,
    parameter [7:0] ERR_BUSY              = 8'h02,
    parameter [7:0] ERR_INPUT_ID          = 8'h03,
    parameter [7:0] ERR_INPUT_NOT_FREE    = 8'h04,
    parameter [7:0] ERR_NO_OUTPUT_BUFFER  = 8'h05,
    parameter [7:0] ERR_OUTPUT_NOT_VALID  = 8'h06
)(
    input  wire        clk,
    input  wire        rst_n,

    input  wire        cmd_start,
    input  wire        cmd_soft_reset,
    input  wire        cmd_model_commit,
    input  wire        cmd_model_invalidate,
    input  wire        cmd_clear_error,
    input  wire        cmd_clear_irq,
    input  wire        cmd_output_release,
    input  wire [1:0]  output_release_mask,
    input  wire        model_dirty,
    input  wire        axi_error_event,
    input  wire [7:0]  axi_error_code,
    input  wire        axi_drop_event,

    input  wire [31:0] cfg_input_buffer_id,
    input  wire [31:0] cfg_input_frame_id,
    input  wire [1:0]  irq_enable,

    output wire        start_allowed,
    output reg  [7:0]  start_error_code,
    output wire        release_allowed,

    output reg         commit_start,
    output reg         commit_abort,
    input  wire        commit_busy,
    input  wire        commit_done,
    input  wire        commit_success,
    input  wire [7:0]  commit_error_code,

    output reg         core_start,
    output reg         core_input_buffer_id,
    output reg         core_output_buffer_id,
    output reg  [31:0] core_frame_id,
    input  wire        core_done,
    input  wire        core_input_release,
    input  wire        core_stall,

    output wire        status_idle,
    output wire        status_busy,
    output wire        status_done,
    output reg         status_error,
    output reg         model_valid,
    output reg         model_error,
    output reg  [7:0]  error_code,
    output reg  [1:0]  input_free_mask,
    output reg  [1:0]  output_valid_mask,
    output reg         output_buffer_id,
    output reg  [31:0] output_frame_id_0,
    output reg  [31:0] output_frame_id_1,
    output reg  [1:0]  irq_status,
    output wire        irq_to_ps,
    output reg  [31:0] stall_count,
    output reg  [31:0] drop_count
);

    reg inference_active;
    reg commit_active;
    reg active_input_buffer;
    reg active_output_buffer;
    reg [31:0] active_frame_id;

    wire output_available = (output_valid_mask != 2'b11);

    assign status_busy = inference_active || commit_active || commit_busy;
    assign status_idle = !status_busy;
    assign status_done = |output_valid_mask;
    assign irq_to_ps   = |(irq_status & irq_enable);

    always @(*) begin
        start_error_code = 8'd0;
        if (!model_valid)
            start_error_code = ERR_MODEL_INVALID;
        else if (status_busy)
            start_error_code = ERR_BUSY;
        else if (cfg_input_buffer_id > 32'd1)
            start_error_code = ERR_INPUT_ID;
        else if (!input_free_mask[cfg_input_buffer_id[0]])
            start_error_code = ERR_INPUT_NOT_FREE;
        else if (!output_available)
            start_error_code = ERR_NO_OUTPUT_BUFFER;
    end

    assign start_allowed   = (start_error_code == 8'd0);
    assign release_allowed = ((output_release_mask & ~output_valid_mask) == 2'b00);

    always @(posedge clk) begin
        if (!rst_n) begin
            inference_active    <= 1'b0;
            commit_active       <= 1'b0;
            active_input_buffer <= 1'b0;
            active_output_buffer<= 1'b0;
            active_frame_id     <= 32'd0;
            commit_start        <= 1'b0;
            commit_abort        <= 1'b0;
            core_start          <= 1'b0;
            core_input_buffer_id<= 1'b0;
            core_output_buffer_id<=1'b0;
            core_frame_id       <= 32'd0;
            status_error        <= 1'b0;
            model_valid         <= 1'b0;
            model_error         <= 1'b0;
            error_code          <= 8'd0;
            input_free_mask     <= 2'b11;
            output_valid_mask   <= 2'b00;
            output_buffer_id    <= 1'b0;
            output_frame_id_0   <= 32'd0;
            output_frame_id_1   <= 32'd0;
            irq_status          <= 2'b00;
            stall_count         <= 32'd0;
            drop_count          <= 32'd0;
        end else begin
            commit_start <= 1'b0;
            commit_abort <= 1'b0;
            core_start   <= 1'b0;

            if (cmd_soft_reset) begin
                inference_active  <= 1'b0;
                commit_active     <= 1'b0;
                commit_abort      <= 1'b1;
                input_free_mask   <= 2'b11;
                output_valid_mask <= 2'b00;
                status_error      <= 1'b0;
                model_error       <= 1'b0;
                error_code        <= 8'd0;
                irq_status        <= 2'b00;
                stall_count       <= 32'd0;
                drop_count        <= 32'd0;
            end else begin
                if (cmd_clear_error) begin
                    status_error <= 1'b0;
                    error_code   <= 8'd0;
                end
                if (cmd_clear_irq)
                    irq_status <= 2'b00;

                if (model_dirty || cmd_model_invalidate) begin
                    model_valid <= 1'b0;
                    model_error <= 1'b0;
                end

                if (cmd_model_commit) begin
                    model_valid   <= 1'b0;
                    model_error   <= 1'b0;
                    commit_active <= 1'b1;
                    commit_start  <= 1'b1;
                end

                if (cmd_output_release && release_allowed)
                    output_valid_mask <= output_valid_mask & ~output_release_mask;

                if (cmd_start && start_allowed) begin
                    active_input_buffer    <= cfg_input_buffer_id[0];
                    active_output_buffer   <= !output_valid_mask[0] ? 1'b0 : 1'b1;
                    active_frame_id        <= cfg_input_frame_id;
                    core_input_buffer_id   <= cfg_input_buffer_id[0];
                    core_output_buffer_id  <= !output_valid_mask[0] ? 1'b0 : 1'b1;
                    core_frame_id          <= cfg_input_frame_id;
                    input_free_mask[cfg_input_buffer_id[0]] <= 1'b0;
                    inference_active       <= 1'b1;
                    core_start             <= 1'b1;
                end

                if (core_input_release && inference_active)
                    input_free_mask[active_input_buffer] <= 1'b1;

                if (core_done && inference_active) begin
                    inference_active <= 1'b0;
                    output_buffer_id <= active_output_buffer;
                    output_valid_mask[active_output_buffer] <= 1'b1;
                    if (active_output_buffer == 1'b0)
                        output_frame_id_0 <= active_frame_id;
                    else
                        output_frame_id_1 <= active_frame_id;
                    irq_status[0] <= 1'b1;
                end

                if (commit_done && commit_active) begin
                    commit_active <= 1'b0;
                    if (commit_success) begin
                        model_valid <= 1'b1;
                        model_error <= 1'b0;
                    end else begin
                        model_valid <= 1'b0;
                        model_error <= 1'b1;
                        irq_status[1] <= 1'b1;
                        if (!status_error) begin
                            status_error <= 1'b1;
                            error_code   <= commit_error_code;
                        end
                    end
                end

                if (axi_error_event) begin
                    irq_status[1] <= 1'b1;
                    if (!status_error) begin
                        status_error <= 1'b1;
                        error_code   <= axi_error_code;
                    end
                end

                if (axi_drop_event && drop_count != 32'hFFFF_FFFF)
                    drop_count <= drop_count + 32'd1;
                if (core_stall && status_busy && stall_count != 32'hFFFF_FFFF)
                    stall_count <= stall_count + 32'd1;
            end
        end
    end

endmodule
