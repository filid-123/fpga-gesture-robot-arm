# Read-only audit of the implemented DCP. These extra bus-skew checks apply only
# to this in-memory audit; the checkpoint, BIT and build constraints are not edited.
# 10 ns is the faster of the FIFO's two source-clock periods (100/48 MHz).
if {$argc != 2} {error "Usage: review_roarm_cdc.tcl implemented.dcp report_directory"}
open_checkpoint [file normalize [lindex $argv 0]]
set report_dir [file normalize [lindex $argv 1]]
file mkdir $report_dir
foreach {src dst} {wr_gray_reg wr_gray_rd_sync1_reg rd_gray_reg rd_gray_wr_sync1_reg} {
    set from [get_cells -hier -quiet -filter "NAME =~ */u_fifo/${src}* && IS_SEQUENTIAL == 1"]
    set to [get_cells -hier -quiet -filter "NAME =~ */u_fifo/${dst}* && IS_SEQUENTIAL == 1"]
    if {[llength $from] != 11 || [llength $to] != 11} {error "Expected 11 Gray-pointer bits: $src=$from $dst=$to"}
    foreach cell $to {if {![get_property ASYNC_REG $cell]} {error "Missing ASYNC_REG on $cell"}}
    set second_name [string map {sync1 sync2} $dst]
    set second [get_cells -hier -quiet -filter "NAME =~ */u_fifo/${second_name}* && IS_SEQUENTIAL == 1"]
    if {[llength $second] != 11} {error "Expected 11 second-stage pointer synchronizers"}
    foreach cell $second {if {![get_property ASYNC_REG $cell]} {error "Missing ASYNC_REG on $cell"}}
    set_bus_skew 10.000 -from $from -to $to
}
report_cdc -details -file [file join $report_dir cdc_details.rpt]
report_bus_skew -file [file join $report_dir gray_pointer_bus_skew_audit.rpt]
exit 0
