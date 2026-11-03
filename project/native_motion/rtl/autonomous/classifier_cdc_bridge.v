// ============================================================================
// One-outstanding-request toggle handshake between the 100 MHz pipeline
// scheduler and the 50 MHz classifier.  The result bus is held in the source
// domain for one full classifier cycle before the acknowledgement toggles.
// ============================================================================
`timescale 1ns / 1ps

module classifier_cdc_bridge (
    input  wire       sys_clk,
    input  wire       sys_rst_n,
    input  wire       request_pulse,
    output wire       request_busy,
    output reg        result_pulse,
    output reg  [8:0] result_class,

    input  wire       classifier_clk,
    input  wire       classifier_rst_n,
    output reg        classifier_start,
    input  wire       classifier_busy,
    input  wire       classifier_done,
    input  wire [8:0] classifier_class
);

    reg request_toggle;
    (* ASYNC_REG = "TRUE" *) reg ack_sync1;
    (* ASYNC_REG = "TRUE" *) reg ack_sync2;
    reg ack_seen;
    (* ASYNC_REG = "TRUE" *) reg [8:0] result_sync1;
    (* ASYNC_REG = "TRUE" *) reg [8:0] result_sync2;

    (* ASYNC_REG = "TRUE" *) reg request_sync1;
    (* ASYNC_REG = "TRUE" *) reg request_sync2;
    reg request_seen;
    reg ack_toggle;
    reg [8:0] result_hold;
    reg completion_pending;

    assign request_busy = request_toggle != ack_sync2;

    always @(posedge sys_clk) begin
        if (!sys_rst_n) begin
            request_toggle <= 1'b0;
            ack_sync1      <= 1'b0;
            ack_sync2      <= 1'b0;
            ack_seen       <= 1'b0;
            result_sync1   <= 9'd0;
            result_sync2   <= 9'd0;
            result_pulse   <= 1'b0;
            result_class   <= 9'd0;
        end else begin
            ack_sync1    <= ack_toggle;
            ack_sync2    <= ack_sync1;
            result_sync1 <= result_hold;
            result_sync2 <= result_sync1;
            result_pulse <= 1'b0;

            if (request_pulse && !request_busy)
                request_toggle <= ~request_toggle;

            if (ack_sync2 != ack_seen) begin
                ack_seen     <= ack_sync2;
                result_class <= result_sync2;
                result_pulse <= 1'b1;
            end
        end
    end

    always @(posedge classifier_clk) begin
        if (!classifier_rst_n) begin
            request_sync1     <= 1'b0;
            request_sync2     <= 1'b0;
            request_seen      <= 1'b0;
            ack_toggle        <= 1'b0;
            result_hold       <= 9'd0;
            completion_pending<= 1'b0;
            classifier_start  <= 1'b0;
        end else begin
            request_sync1    <= request_toggle;
            request_sync2    <= request_sync1;
            classifier_start <= 1'b0;

            if ((request_sync2 != request_seen) && !classifier_busy &&
                !completion_pending) begin
                request_seen     <= request_sync2;
                classifier_start <= 1'b1;
            end

            if (classifier_done) begin
                result_hold        <= classifier_class;
                completion_pending <= 1'b1;
            end else if (completion_pending) begin
                ack_toggle         <= request_seen;
                completion_pending <= 1'b0;
            end
        end
    end

endmodule
