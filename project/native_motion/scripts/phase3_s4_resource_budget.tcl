# Phase 3 S4 resource budgets on top of the UNCHANGED S2 v0.2.3 budget helper
# (scripts/phase3_s2_resource_budget.tcl -> S1 gate phase3_s1_resource_gate.tcl:
# report parsing, verdicts, exit codes).  Sourced by run_phase3_s4_ooc_synth.tcl
# and build_phase3_s4_task.tcl.  Pure Tcl, no Vivado command.
#
#   total     phase3_s4_task_top = S2 motion top (S1 + S2) + S4
#   increment S4 only = total - cell u_motion (u_motion is keep_hierarchy)
# Both values are PROPOSED (config/UNKNOWN_PARAMETERS_S4.yaml); the Yosys raw
# estimate of the increment is ~6.7k LUT / ~5.0k FF / 3 RAMB18 / 0 DSP
# (reports/yosys_resource_estimate.json, not Vivado).  The S1/S2 budgets are not
# changed.  Vision (S3) resources are separate; never add them to these numbers
# to claim a whole-system result.

source [file join [file dirname [file normalize [info script]]] phase3_s2_resource_budget.tcl]

namespace eval s4gate {
    variable total_budget     {LUT_TOTAL 17000 FF 13500 BRAM_TILE 11.0 DSP 16}
    variable increment_budget {LUT_TOTAL 7500 FF 6000 BRAM_TILE 3.0 DSP 0}
}

proc s4gate::verdict {util budget} {
    return [s2gate::verdict $util $budget]
}

# a - b per key (total minus u_motion); a missing value stays "".
proc s4gate::sub {a b} {
    set result [dict create]
    foreach key [dict keys $a] {
        set x [dict get $a $key]
        set y [dict get $b $key]
        if {[s1gate::is_number $x] && [s1gate::is_number $y]} {
            set d [expr {$x - $y}]
            if {$d == int($d)} { set d [expr {int($d)}] }
            dict set result $key $d
        } else {
            dict set result $key ""
        }
    }
    return $result
}

proc s4gate::budget_text {budget} {
    return [s2gate::budget_text $budget]
}
