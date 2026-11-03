# Shared resource/timing extraction and budget gate for the Phase 3 S1 scripts
# (sourced by run_phase3_s1_arm_ooc_synth.tcl and build_phase3_s1_armpath.tcl).
#
# Resource figures come ONLY from the text of report_utilization:
#   LUT_TOTAL  = "Slice LUTs" row (7-series; "CLB LUTs" on newer families)
#              = LUT as Logic + LUT as Memory (distributed RAM + shift registers)
#   FF         = "Slice Registers" row, BRAM_TILE = "Block RAM Tile" row,
#   DSP        = "DSPs" row.
# Primitive cells (LUTn, RAM32M, RAM64M, ...) are never counted: a RAM32M uses
# four LUT sites and two LUT5 can share one site, so cell counts are not LUTs.
# Timing comes from the "Design Timing Summary" table of report_timing_summary.
#
# Pure Tcl (no Vivado command inside), so tests/test_vivado_gate_scripts.py can
# exercise it on real Vivado 2026.1 reports without Vivado.

namespace eval s1gate {
    # Motion subsystem budget (trajectory core + arm backend), S1 prompt.
    variable budget {LUT_TOTAL 6000 FF 6000 BRAM_TILE 8.0 DSP 16}
    variable util_rows {
        LUT_TOTAL  {{Slice LUTs} {CLB LUTs}}
        LUT_LOGIC  {{LUT as Logic}}
        LUT_MEMORY {{LUT as Memory}}
        FF         {{Slice Registers} {CLB Registers}}
        BRAM_TILE  {{Block RAM Tile}}
        RAMB36     {{RAMB36/FIFO}}
        RAMB18     {{RAMB18}}
        DSP        {{DSPs}}
    }
}

# "Used" column of the first table row whose first cell (trimmed, trailing '*'
# removed) is one of $labels; "" when no such row exists.  The first match is
# the "1. Slice Logic" / "3. Memory" / "4. DSP" summary row.
proc s1gate::table_value {report labels} {
    foreach line [split $report "\n"] {
        if {![regexp {^\|([^|]*)\|\s*([0-9]+(?:\.[0-9]+)?)\s*\|} $line -> name used]} {
            continue
        }
        set name [string trim [string trimright [string trim $name] "*"]]
        if {[lsearch -exact $labels $name] >= 0} {
            return $used
        }
    }
    return ""
}

# Dict LUT_TOTAL LUT_LOGIC LUT_MEMORY FF BRAM_TILE RAMB36 RAMB18 DSP ("" = missing).
proc s1gate::utilization {report} {
    variable util_rows
    set result [dict create]
    foreach {key labels} $util_rows {
        dict set result $key [table_value $report $labels]
    }
    return $result
}

# Dict WNS TNS TNS_FAILING WHS THS THS_FAILING from the Design Timing Summary
# table; every value is "NA" when the table is absent.
proc s1gate::timing {report} {
    set result [dict create WNS NA TNS NA TNS_FAILING NA WHS NA THS NA THS_FAILING NA]
    set lines [split $report "\n"]
    set start -1
    for {set i 0} {$i < [llength $lines]} {incr i} {
        if {[string match "*Design Timing Summary*" [lindex $lines $i]]} {
            set start $i
            break
        }
    }
    if {$start < 0} {
        return $result
    }
    for {set i $start} {$i < [llength $lines] - 2} {incr i} {
        set line [lindex $lines $i]
        if {[string match "*WNS(ns)*TNS(ns)*WHS(ns)*THS(ns)*" $line]} {
            set values [regexp -all -inline {\S+} [lindex $lines [expr {$i + 2}]]]
            if {[llength $values] >= 8} {
                foreach key {WNS TNS TNS_FAILING {} WHS THS THS_FAILING} value [lrange $values 0 6] {
                    if {$key ne ""} {
                        dict set result $key $value
                    }
                }
            }
            break
        }
    }
    return $result
}

proc s1gate::is_number {value} {
    return [string is double -strict $value]
}

# Budget verdict for a utilization dict: {WITHIN_BUDGET {}} | {OVER_BUDGET {details}}
# | {UNREADABLE {details}}.  Checked against the full budget, all four resources.
proc s1gate::budget_verdict {util} {
    variable budget
    set over {}
    set missing {}
    foreach {key limit} $budget {
        set value [dict get $util $key]
        if {![is_number $value]} {
            lappend missing "${key}=missing"
        } elseif {$value > $limit} {
            lappend over "${key}=${value}>${limit}"
        }
    }
    if {[llength $missing] > 0} {
        return [list UNREADABLE [concat $missing $over]]
    }
    if {[llength $over] > 0} {
        return [list OVER_BUDGET $over]
    }
    return [list WITHIN_BUDGET {}]
}

# One machine-readable line: "<prefix> build=<tag> LUT_TOTAL=.. .. [WNS=.. THS_FAILING=..]".
# Pass an empty timing dict for a resource-only line.
proc s1gate::result_line {prefix tag util timing} {
    set fields [list "build=$tag"]
    foreach key {LUT_TOTAL LUT_LOGIC LUT_MEMORY FF BRAM_TILE RAMB36 RAMB18 DSP} {
        set value [dict get $util $key]
        lappend fields "${key}=[expr {$value eq {} ? {MISSING} : $value}]"
    }
    if {[dict size $timing] > 0} {
        foreach key {WNS TNS TNS_FAILING WHS THS THS_FAILING} {
            lappend fields "${key}=[dict get $timing $key]"
        }
    }
    return "$prefix [join $fields { }]"
}

# LUT_TOTAL must equal LUT_LOGIC + LUT_MEMORY in a well-formed report; returns
# "" when consistent, else a description (reported, the total row stays the
# official figure).
proc s1gate::lut_split_note {util} {
    set total [dict get $util LUT_TOTAL]
    set logic [dict get $util LUT_LOGIC]
    set memory [dict get $util LUT_MEMORY]
    if {![is_number $total] || ![is_number $logic] || ![is_number $memory]} {
        return "LUT split rows missing"
    }
    if {$total != $logic + $memory} {
        return "Slice LUTs ($total) != LUT as Logic ($logic) + LUT as Memory ($memory)"
    }
    return ""
}

proc s1gate::write_text {path text} {
    set fh [open $path w]
    puts -nonewline $fh $text
    close $fh
}

# Exit code shared by both scripts: 0 all gates met and within budget;
# 11 a timing/mapping/DRC/file gate failed; 12 over budget or unreadable
# utilization; 13 both.
proc s1gate::exit_code {gate_failures budget_failures} {
    set code 0
    if {$gate_failures > 0} { set code 11 }
    if {$budget_failures > 0} { set code [expr {$code == 11 ? 13 : 12}] }
    return $code
}
