// ============================================================================
// Block Name : arm_motion_permission_gate
// Description: Logical motion permission for the Phase 3 S1 arm backend.
//              The physical e-stop must cut actuator power independently; this
//              gate only stops the PL from starting new motion frames.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz).  motion_enable_async is an asynchronous pin
//               (fail-safe: high = OK, XDC pulldown so an open wire = stop)
//               and passes a two-flop ASYNC_REG synchronizer.
//
// estop_ok rises only after DEBOUNCE_CYCLES consecutive high samples and falls
// on the first low sample.  estop_event pulses when estop_ok falls while
// LINE mode is armed; the backend latches it as a fatal sticky error, so a
// released e-stop never resumes motion without a PS clear + re-arm.
// Cycle-level equivalent of arm_feedback.PermissionGateModel.
//
// Truth boundary: source candidate.  Supplementary Icarus Verilog run only;
// XSim/synthesis/implementation not run.
// ============================================================================

`timescale 1ns / 1ps

module arm_motion_permission_gate #(
    parameter integer DEBOUNCE_CYCLES = 1_000_000    // 10 ms at 100 MHz
) (
    input  wire clk,
    input  wire rst_n,
    input  wire motion_enable_async,
    input  wire line_mode,
    input  wire arm,
    input  wire config_valid,
    input  wire fault,
    output reg  estop_ok,
    output wire permission,
    output reg  estop_event
);

    localparam integer COUNTER_WIDTH = (DEBOUNCE_CYCLES > 1) ? $clog2(DEBOUNCE_CYCLES) : 1;
    localparam [COUNTER_WIDTH-1:0] COUNT_LAST = DEBOUNCE_CYCLES - 1;

    (* ASYNC_REG = "TRUE" *) reg enable_meta;
    (* ASYNC_REG = "TRUE" *) reg enable_sync;
    reg [COUNTER_WIDTH-1:0] counter;

    assign permission = line_mode && arm && config_valid && !fault && estop_ok;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            enable_meta <= 1'b0;
            enable_sync <= 1'b0;
            counter     <= {COUNTER_WIDTH{1'b0}};
            estop_ok    <= 1'b0;
            estop_event <= 1'b0;
        end else begin
            enable_meta <= motion_enable_async;
            enable_sync <= enable_meta;
            estop_event <= estop_ok && !enable_sync && line_mode && arm;

            if (!enable_sync) begin
                estop_ok <= 1'b0;
                counter  <= {COUNTER_WIDTH{1'b0}};
            end else if (!estop_ok) begin
                if (counter == COUNT_LAST)
                    estop_ok <= 1'b1;
                else
                    counter <= counter + 1'b1;
            end
        end
    end

endmodule
