// ============================================================================
// Testbench: tb_s4_a_line_happy
// Purpose  : S4 integration scenario 1 (a_line_happy) of golden/s4/s4_scenarios.mem,
//            vision through the PS register VISION_SIM.  Body: tb_s4_task_body.vh.
// Truth boundary: supplementary Icarus run only (XSim NOT_RUN_ENV_UNAVAILABLE).
// ============================================================================

`timescale 1ns / 1ps

module tb_s4_a_line_happy;
    localparam integer SCEN = 1;
    localparam integer VISA = 1;
`include "tb_s4_task_body.vh"
endmodule
