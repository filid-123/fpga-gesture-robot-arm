// ============================================================================
// Testbench: tb_s4_a_happy
// Purpose  : S4 integration scenario 0 (a_happy) of golden/s4/s4_scenarios.mem,
//            async vision input (2-FF + stability filter).  Body: tb_s4_task_body.vh.
// Truth boundary: supplementary Icarus run only (XSim NOT_RUN_ENV_UNAVAILABLE).
// ============================================================================

`timescale 1ns / 1ps

module tb_s4_a_happy;
    localparam integer SCEN = 0;
    localparam integer VISA = 1;
`include "tb_s4_task_body.vh"
endmodule
