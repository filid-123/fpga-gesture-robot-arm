// ============================================================================
// Testbench: tb_s4_a_palm_timeout
// Purpose  : S4 integration scenario 4 (a_palm_timeout) of golden/s4/s4_scenarios.mem,
//            same-clock vision levels + change pulse.  Body: tb_s4_task_body.vh.
// Truth boundary: supplementary Icarus run only (XSim NOT_RUN_ENV_UNAVAILABLE).
// ============================================================================

`timescale 1ns / 1ps

module tb_s4_a_palm_timeout;
    localparam integer SCEN = 4;
    localparam integer VISA = 0;
`include "tb_s4_task_body.vh"
endmodule
