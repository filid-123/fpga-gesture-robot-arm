// ============================================================================
// Testbench: tb_s4_a_refuse_not_home
// Purpose  : S4 integration scenario 9 (a_refuse_not_home) of golden/s4/s4_scenarios.mem,
//            same-clock vision levels + change pulse.  Body: tb_s4_task_body.vh.
// Truth boundary: supplementary Icarus run only (XSim NOT_RUN_ENV_UNAVAILABLE).
// ============================================================================

`timescale 1ns / 1ps

module tb_s4_a_refuse_not_home;
    localparam integer SCEN = 9;
    localparam integer VISA = 0;
`include "tb_s4_task_body.vh"
endmodule
