# Full XC7Z020 implementation. Only routed, passing results are staged.
set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set project_name Gesture_Roarm_ClosedLoop
set bd_name roarm_closed_loop
set project_dir [file join $root_dir vivado_roarm_closed_loop]
if {[info exists ::env(ROARM_BUILD_DIR)]} {set project_dir [file normalize $::env(ROARM_BUILD_DIR)]}
set report_dir [file join $root_dir reports roarm_closed_loop_implemented]
if {[info exists ::env(ROARM_REPORT_DIR)]} {set report_dir [file normalize $::env(ROARM_REPORT_DIR)]}
file mkdir $report_dir
source [file join $script_dir phase3_s1_resource_gate.tcl]
open_project [file join $project_dir ${project_name}.xpr]
set rq_source [file join $root_dir rtl cnn requant_fixed31_pipeline.v]
if {[llength [get_files -quiet $rq_source]] == 0} {add_files -norecurse $rq_source}
set pin_xdc [file join $root_dir constraints roarm_closed_loop_pins.xdc]
if {[llength [get_files -quiet $pin_xdc]] == 0} {add_files -fileset constrs_1 -norecurse $pin_xdc}
reset_run synth_1
launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property STATUS [get_runs synth_1]] ne "synth_design Complete!"} {error "Synthesis failed"}
reset_run impl_1
set_property strategy Performance_ExplorePostRoutePhysOpt [get_runs impl_1]
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {[get_property STATUS [get_runs impl_1]] ne "write_bitstream Complete!"} {error "Implementation failed"}
open_run impl_1
set util_text [report_utilization -return_string]
s1gate::write_text [file join $report_dir utilization_implemented.rpt] $util_text
report_utilization -hierarchical -file [file join $report_dir utilization_hier_implemented.rpt]
set timing_text [report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -return_string]
s1gate::write_text [file join $report_dir timing_implemented.rpt] $timing_text
report_cdc -file [file join $report_dir cdc_implemented.rpt]
report_clock_interaction -file [file join $report_dir clock_interaction_implemented.rpt]
report_methodology -file [file join $report_dir methodology_implemented.rpt]
report_route_status -file [file join $report_dir route_status.rpt]
report_drc -file [file join $report_dir drc_implemented.rpt]
report_io -file [file join $report_dir io_implemented.rpt]
set util [s1gate::utilization $util_text]
set timing [s1gate::timing $timing_text]
puts [s1gate::result_line ROARM_IMPL_DESIGN whole_design $util {}]
puts "ROARM_TIMING=$timing"
set problems {}
foreach {key capacity} {LUT_TOTAL 53200 FF 106400 BRAM_TILE 140 DSP 220} {
    set value [dict get $util $key]
    set max_percent 100
    if {[info exists ::env(ROARM_UPGRADE)] && $::env(ROARM_UPGRADE) eq "1"} {set max_percent 85}
    set limit [expr {$capacity * $max_percent / 100.0}]
    if {![s1gate::is_number $value] || $value > $limit} {lappend problems "$key=$value capacity=$capacity"}
}
foreach key {WNS WHS} {
    set value [dict get $timing $key]
    if {![s1gate::is_number $value] || $value < 0} {lappend problems "$key=$value"}
}
if {[llength [get_drc_violations -quiet -filter {SEVERITY == Error}]] != 0} {lappend problems "DRC errors"}
set bit_src [file join $project_dir ${project_name}.runs impl_1 ${bd_name}_wrapper.bit]
set hwh_src [file join $project_dir ${project_name}.gen sources_1 bd $bd_name hw_handoff ${bd_name}.hwh]
foreach f [list $bit_src $hwh_src] {if {![file exists $f]} {lappend problems "Missing $f"}}
s1gate::write_text [file join $report_dir build_gate.txt] "UTIL=$util\nTIMING=$timing\nPROBLEMS=$problems\nCDC requires report review before packaging\n"
if {[llength $problems] != 0} {puts "GATE_FAIL: $problems"; exit 11}
file copy -force $bit_src [file join $report_dir roarm_closed_loop.bit]
file copy -force $hwh_src [file join $report_dir roarm_closed_loop.hwh]
write_hw_platform -fixed -include_bit -force -file [file join $report_dir roarm_closed_loop.xsa]
puts "PASS: full implementation, timing and DRC gates. Review CDC before deployment packaging."
close_project
exit 0

