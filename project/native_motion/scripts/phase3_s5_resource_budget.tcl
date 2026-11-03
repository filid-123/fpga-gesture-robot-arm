# Phase 3 S5 resource budgets on top of the UNCHANGED S4 v0.1.1 budget helper
# (phase3_s4_resource_budget.tcl -> S2 v0.2.3 -> S1 v0.1.1 gate: report parsing, verdicts,
# exit codes, s4gate::sub).  Sourced by build_phase3_s5.tcl.  Pure Tcl, no Vivado command.
#
#   total      BD cell s5_0 = S3 vision top + S4 task top (S1/S2 inside) + S5 adapter
#   increment  S5 only = s5_0 - u_vision - u_task (adapter + glue)
# PROPOSED values (config/UNKNOWN_PARAMETERS_S5.yaml).  Reference points, NOT a sum claim:
#   S3 four-class final build, implemented: 11,665 LUT / 5,483 FF / 58.5 BRAM tile / 28 DSP
#   (seven-class Yosys delta about +110 LUT / +148 FF); S4 v0.1.1 task_0, implemented locally:
#   10,489 LUT / 10,339 FF / 4.5 BRAM tile / 14 DSP.  The joint design must be measured; placement
#   and routing of the two blocks together can change both numbers and timing.

source [file join [file dirname [file normalize [info script]]] phase3_s4_resource_budget.tcl]

namespace eval s5gate {
    variable total_budget     {LUT_TOTAL 26000 FF 19000 BRAM_TILE 66.0 DSP 44}
    variable increment_budget {LUT_TOTAL 800 FF 800 BRAM_TILE 0.0 DSP 0}
}
