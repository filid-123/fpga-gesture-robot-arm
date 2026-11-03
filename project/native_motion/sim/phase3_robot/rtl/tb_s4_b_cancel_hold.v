// ============================================================================
// Testbench: tb_s4_b_cancel_hold
// Purpose  : S4 integration scenario 12 (b_cancel_hold) of golden/s4/s4_scenarios.mem,
//            same-clock vision levels + change pulse.  Body: tb_s4_task_body.vh.
// Truth boundary: supplementary Icarus run only (XSim NOT_RUN_ENV_UNAVAILABLE).
// ============================================================================

`timescale 1ns / 1ps

module tb_s4_b_cancel_hold;
    localparam integer SCEN = 12;
    localparam integer VISA = 0;
`include "tb_s4_task_body.vh"
endmodule
