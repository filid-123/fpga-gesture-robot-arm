# Synthesize, implement and write the Phase 3 S5 vision+motion bitstream (candidate v0.1.0),
# derived from build_phase3_s4_task.tcl (S4 v0.1.1).
# Status in the S5 package: NOT_RUN_ENV_UNAVAILABLE (no Vivado run, no BIT/HWH exists).
#
# Refuses to run until constraints/phase3_s1_armpath_pins.xdc exists, has no TBD left and places
# all six arm pins away from the frozen OV5640 JA/JB pins AND the four S3 LED pins.
#
# After routing it ALWAYS prints the full figures first:
#   PHASE3_S5_IMPL_TOP      build=s5_0 ...              phase3_s5_vision_motion_top (BD cell)
#   PHASE3_S5_IMPL_VISION   build=u_vision ...          S3 v0.1.1 top (unchanged, keep_hierarchy)
#   PHASE3_S5_IMPL_TASK     build=u_task ...            S4 v0.1.1 top (unchanged, keep_hierarchy)
#   PHASE3_S5_IMPL_MOTION   build=u_task/u_motion ...   S1 + S2 inside S4
#   PHASE3_S5_IMPL_ADAPTER  build=top-vision-task ...   S5 increment (adapter + glue)
#   PHASE3_S5_IMPL_DESIGN   build=whole_design ...      adds PS7/SmartConnect/resets/xclk wizard
#   PHASE3_S5_IMPL_TIMING   WNS=.. TNS=.. TNS_FAILING=.. WHS=.. THS=.. THS_FAILING=..
#   PHASE3_S5_IMPL_BUDGET   total=<verdict> increment=<verdict> [details]
# Gates: WNS >= 0, WHS >= 0, no DRC error, u_motion keeps the S1/S2 mapping (3 RAMB36 / 0 RAMB18 /
# 14 DSP), the S5 increment uses no BRAM/DSP, BIT/HWH present, budgets of
# scripts/phase3_s5_resource_budget.tcl.  Result (exactly one): PASS (exit 0) / RESULT: GATE_FAIL (11) /
# RESULT: OVER_BUDGET (12) / RESULT: OVER_BUDGET_AND_GATE_FAIL (13); nothing is staged on failure.
# Output: reports/phase3_s5_vision_motion_implemented/phase3_s5_vision_motion.{bit,hwh,xsa} + S5_BUILD_INFO.json

set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set project_dir [file join $root_dir vivado_phase3_s5_vision_motion]
set project_name "Gesture_Phase3_S5_VisionMotion"
set bd_name "phase3_s5_vision_motion"
set project_file [file join $project_dir ${project_name}.xpr]
set report_dir [file join $root_dir reports phase3_s5_vision_motion_implemented]
set pin_xdc [file join $root_dir constraints phase3_s1_armpath_pins.xdc]

if {![file exists $project_file]} {
    error "Missing S5 project. Run scripts/create_phase3_s5_project.tcl first."
}
source [file join $script_dir phase3_s5_resource_budget.tcl]

# ---- pin file check (before any long run) ----------------------------------------------------
if {![file exists $pin_xdc]} {
    error "Missing $pin_xdc. Copy phase3_s1_armpath_pins_TEMPLATE.xdc and fill the measured pins."
}
set fh [open $pin_xdc r]
set pin_text [read $fh]
close $fh
array set pin_of {}
foreach line [split $pin_text "\n"] {
    set s [string trim $line]
    if {$s eq "" || [string index $s 0] eq "#"} { continue }
    if {[string first "TBD" $s] >= 0} { error "$pin_xdc still contains TBD: $s" }
    if {[regexp {PACKAGE_PIN\s+([A-Z]+[0-9]+)} $s -> pin] && [regexp {get_ports\s+\{?([A-Za-z0-9_]+)\}?\]} $s -> port]} {
        set pin_of($port) $pin
    }
}
# OV5640 JA/JB pins (phase2_l2_autonomous_ov5640.xdc) and S3 LEDs (phase2_l2_autonomous_leds.xdc)
set reserved_pins {Y18 Y19 Y16 Y17 U19 W18 W19 W14 U18 Y14 T11 T10 V16 W16 V12 W13 R14 P14 N16 M14}
set used_pins {}
foreach port {arm_uart_tx arm_uart_rx bus_tx bus_rx bus_dir motion_enable_in} {
    if {![info exists pin_of($port)]} { error "$pin_xdc has no PACKAGE_PIN for $port" }
    set pin $pin_of($port)
    if {[lsearch -exact $reserved_pins $pin] >= 0} { error "$port on $pin collides with the OV5640 or LED pins" }
    if {[lsearch -exact $used_pins $pin] >= 0} { error "$pin assigned to more than one arm port" }
    lappend used_pins $pin
}
puts "S5_ARM_PINS=[join $used_pins ,]"
file mkdir $report_dir

set_param ips.enableInterfaceArrayInference false
set board_store [xhub::get_xstores xilinx_board_store]
if {[llength $board_store] != 0} { set_param board.repoPaths [list [get_property LOCAL_ROOT_DIR $board_store]] }

open_project $project_file
if {[llength [get_files -quiet -of_objects [get_filesets constrs_1] $pin_xdc]] == 0} {
    add_files -fileset constrs_1 -norecurse $pin_xdc
}
reset_run synth_1
launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property STATUS [get_runs synth_1]] ne "synth_design Complete!"} {
    error "S5 synthesis failed: [get_property STATUS [get_runs synth_1]]"
}
reset_run impl_1
set_property strategy Performance_ExplorePostRoutePhysOpt [get_runs impl_1]
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {[get_property STATUS [get_runs impl_1]] ne "write_bitstream Complete!"} {
    error "S5 implementation/bitstream failed: [get_property STATUS [get_runs impl_1]]"
}

open_run impl_1
set design_util_text [report_utilization -return_string]
s1gate::write_text [file join $report_dir utilization_implemented.rpt] $design_util_text
report_utilization -hierarchical -file [file join $report_dir utilization_hier_implemented.rpt]
set timing_text [report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -return_string]
s1gate::write_text [file join $report_dir timing_implemented.rpt] $timing_text
report_cdc -file [file join $report_dir cdc_implemented.rpt]
report_clock_interaction -file [file join $report_dir clock_interaction_implemented.rpt]
report_methodology -file [file join $report_dir methodology_implemented.rpt]
report_route_status -file [file join $report_dir route_status.rpt]
report_drc -file [file join $report_dir drc_implemented.rpt]
report_io -file [file join $report_dir io_implemented.rpt]

set problems {}
set budget_failures 0
proc s5_cell_util {pattern label report_dir problems_var} {
    upvar $problems_var problems
    set cells [get_cells -quiet -hier -filter "NAME =~ $pattern && IS_PRIMITIVE == 0"]
    if {[llength $cells] != 1} {
        lappend problems "cell $pattern found [llength $cells] times (expected 1, keep_hierarchy)"
        return [s1gate::utilization ""]
    }
    set text [report_utilization -cells $cells -return_string]
    s1gate::write_text [file join $report_dir utilization_${label}_implemented.rpt] $text
    return [s1gate::utilization $text]
}
set top_util    [s5_cell_util {*/s5_0}                  top    $report_dir problems]
set vision_util [s5_cell_util {*/s5_0/inst/u_vision}    vision $report_dir problems]
set task_util   [s5_cell_util {*/s5_0/inst/u_task}      task   $report_dir problems]
set motion_util [s5_cell_util {*/s5_0/inst/u_task/u_motion} motion $report_dir problems]
set inc_util [s4gate::sub [s4gate::sub $top_util $vision_util] $task_util]
set design_util [s1gate::utilization $design_util_text]
set timing [s1gate::timing $timing_text]

puts [s1gate::result_line PHASE3_S5_IMPL_TOP s5_0 $top_util {}]
puts [s1gate::result_line PHASE3_S5_IMPL_VISION u_vision $vision_util {}]
puts [s1gate::result_line PHASE3_S5_IMPL_TASK u_task $task_util {}]
puts [s1gate::result_line PHASE3_S5_IMPL_MOTION u_task/u_motion $motion_util {}]
puts [s1gate::result_line PHASE3_S5_IMPL_ADAPTER top-vision-task $inc_util {}]
puts [s1gate::result_line PHASE3_S5_IMPL_DESIGN whole_design $design_util {}]
set timing_fields {}
foreach key {WNS TNS TNS_FAILING WHS THS THS_FAILING} { lappend timing_fields "${key}=[dict get $timing $key]" }
puts "PHASE3_S5_IMPL_TIMING [join $timing_fields { }]"

lassign [s4gate::verdict $top_util $s5gate::total_budget] total_verdict total_details
lassign [s4gate::verdict $inc_util $s5gate::increment_budget] inc_verdict inc_details
set details {}
foreach d $total_details { lappend details "total:$d" }
foreach d $inc_details { lappend details "increment:$d" }
puts [string trimright "PHASE3_S5_IMPL_BUDGET total=$total_verdict increment=$inc_verdict [join $details ,]"]
if {$total_verdict ne "WITHIN_BUDGET" || $inc_verdict ne "WITHIN_BUDGET"} { set budget_failures 1 }

foreach {key label} {WNS setup WHS hold} {
    set value [dict get $timing $key]
    if {![s1gate::is_number $value]} {
        lappend problems "$label slack unavailable in the timing summary"
    } elseif {$value < 0.0} {
        lappend problems "$label slack $key=$value ns"
    }
}
foreach key {RAMB36 RAMB18 DSP} {
    if {[dict get $inc_util $key] ne "0"} { lappend problems "S5 increment uses [dict get $inc_util $key] $key (expected 0)" }
}
set drc_errors [get_drc_violations -quiet -filter {SEVERITY == Error}]
if {[llength $drc_errors] != 0} { lappend problems "DRC errors: $drc_errors" }
set bit_src [file join $project_dir ${project_name}.runs impl_1 ${bd_name}_wrapper.bit]
set hwh_src [file join $project_dir ${project_name}.gen sources_1 bd $bd_name hw_handoff ${bd_name}.hwh]
if {![file exists $bit_src] || [file size $bit_src] < 1000000} { lappend problems "bitstream missing or unexpectedly small: $bit_src" }
if {![file exists $hwh_src] || [file size $hwh_src] < 1000} { lappend problems "HWH missing or unexpectedly small: $hwh_src" }
foreach problem $problems { puts "FAIL: $problem" }

set code [s1gate::exit_code [llength $problems] $budget_failures]
if {$code == 0} {
    set bit_file [file join $report_dir ${bd_name}.bit]
    set hwh_file [file join $report_dir ${bd_name}.hwh]
    file copy -force $bit_src $bit_file
    file copy -force $hwh_src $hwh_file
    file copy -force [file join $project_dir S5_BUILD_INFO.json] [file join $report_dir S5_BUILD_INFO.json]
    set xsa_file [file join $report_dir ${bd_name}.xsa]
    write_hw_platform -fixed -include_bit -force -file $xsa_file
    puts "PHASE3_S5_BIT=$bit_file"
    puts "PHASE3_S5_HWH=$hwh_file"
    puts "PHASE3_S5_XSA=$xsa_file"
    puts "PASS: Phase 3 S5 vision+motion implementation and bitstream completed within budget."
} else {
    switch -- $code {
        11 { puts "RESULT: GATE_FAIL (see FAIL lines)" }
        12 { puts "RESULT: OVER_BUDGET (total [s4gate::budget_text $s5gate::total_budget], increment [s4gate::budget_text $s5gate::increment_budget]; see PHASE3_S5_IMPL_BUDGET)" }
        default { puts "RESULT: OVER_BUDGET_AND_GATE_FAIL (see FAIL and PHASE3_S5_IMPL_BUDGET lines)" }
    }
    puts "NOTE: nothing staged for deployment; raw run outputs stay under $project_dir"
}
close_project
exit $code
