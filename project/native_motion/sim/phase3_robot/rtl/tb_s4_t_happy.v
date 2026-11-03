// ============================================================================
// Testbench: tb_s4_t_happy
// Purpose  : tray-exit patch scenario 5 of golden/s4_tray/s4_tray_scenarios.mem (S4 built with
//            TRAY_EXIT = 1), same-clock vision.  Body: tb_s4_tray_task_body.vh.
// Truth boundary: supplementary Icarus run only (XSim NOT_RUN_ENV_UNAVAILABLE).
// ============================================================================

`timescale 1ns / 1ps

module tb_s4_t_happy;
    localparam integer SCEN = 5;
    localparam integer VISA = 0;
    localparam integer TRAY = 1;
`include "tb_s4_tray_task_body.vh"
endmodule
