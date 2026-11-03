if {$argc != 2} {error "Usage: vivado -mode batch -source inspect_roarm_timing.tcl -tclargs checkpoint.dcp report_prefix"}
set checkpoint [file normalize [lindex $argv 0]]
set prefix [file normalize [lindex $argv 1]]
open_checkpoint $checkpoint
report_timing -delay_type max -max_paths 20 -file ${prefix}_paths.rpt
foreach {label pattern} {conv *u_classifier/conv_inst* dense *u_classifier/dense_inst* locator *u_locator* geometry *u_bbox* roi *u_same_frame_roi* filter *u_confirm* frame *u_retained*} {
 set cells [get_cells -hier -quiet -filter "NAME =~ $pattern && IS_SEQUENTIAL == 1"]
 if {[llength $cells] > 0} {report_timing -delay_type max -max_paths 3 -to $cells -file ${prefix}_${label}_paths.rpt}
}
exit 0
