# Phase 3 S2 resource budgets on top of the UNCHANGED S1 v0.1.1 gate
# (scripts/phase3_s1_resource_gate.tcl: report parsing, verdicts, exit codes).
# Sourced by run_phase3_s2_ooc_synth.tcl and build_phase3_s2_motion.tcl.
#
# Two budgets, both judged on report_utilization text only ("Slice LUTs" =
# LUT as Logic + LUT as Memory, see the S1 gate):
#   total     motion subsystem = S1 trajectory + S1 arm backend + S2 planner + mux
#   increment S2 only = cells u_planner + u_mux (kept as hierarchy in
#             phase3_s2_motion_top.v)
# Both values are PROPOSED (config/UNKNOWN_PARAMETERS_S2.yaml); the S1 budget
# (6000/6000/8/16) is not changed by S2.  Pure Tcl, no Vivado command.

source [file join [file dirname [file normalize [info script]]] phase3_s1_resource_gate.tcl]

namespace eval s2gate {
    variable total_budget     {LUT_TOTAL 9500 FF 7500 BRAM_TILE 8.0 DSP 16}
    variable increment_budget {LUT_TOTAL 2500 FF 1500 BRAM_TILE 0.0 DSP 0}
}

# budget_verdict of the S1 gate against another budget dict.
proc s2gate::verdict {util budget} {
    set saved $::s1gate::budget
    set ::s1gate::budget $budget
    set result [s1gate::budget_verdict $util]
    set ::s1gate::budget $saved
    return $result
}

# Sum of two utilization dicts (u_planner + u_mux); a missing value stays "".
proc s2gate::add {a b} {
    set result [dict create]
    foreach key [dict keys $a] {
        set x [dict get $a $key]
        set y [dict get $b $key]
        if {[s1gate::is_number $x] && [s1gate::is_number $y]} {
            set sum [expr {$x + $y}]
            if {$sum == int($sum)} { set sum [expr {int($sum)}] }
            dict set result $key $sum
        } else {
            dict set result $key ""
        }
    }
    return $result
}

proc s2gate::budget_text {budget} {
    return "[dict get $budget LUT_TOTAL] LUT / [dict get $budget FF] FF / [dict get $budget BRAM_TILE] BRAM tile / [dict get $budget DSP] DSP"
}
