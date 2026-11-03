# Wrapper-aware offline inspection. The original checks are preserved with
# explicit new hierarchy paths; no hardware manager or device API is invoked.
set f [open [file join [file dirname [info script]] inspect_mode_a_restock_netlist.tcl] r]
set script [read $f];close $f
set script [string map {
 *u_display/status_cdc/ *u_display/u_telemetry/status_cdc/
 *u_display/canvas/ *u_display/u_scan/canvas/
 *u_task/u_fsm* *u_task/u_task_control/u_fsm*
 *u_task/u_regs* *u_task/u_task_control/u_regs*
} $script]
set script [string map {"*u_display/$path/data1_reg*" "*u_display/*$path/data1_reg*" "*u_display/$path/data2_reg*" "*u_display/*$path/data2_reg*"} $script]
set extra {
set native_ram [get_cells -hier -filter {NAME =~ *g_b_program*u_player*channel_ram* && REF_NAME == RAMB36E1}]
if {[llength $native_ram]!=6} {error "Expected six lossless native route RAMB36 memories: $native_ram"}
puts $out "B_NATIVE_Q16_ROUTE_RAMB36=6 CHANNELS=6 DEPTH=2048 OFFSET_BITS=18"
foreach c $native_ram {puts $out "B_NATIVE_RAM=$c"}
set speed [get_cells -hier -filter {NAME =~ *u_arm_backend*u_core/frame_speed_reg* && REF_NAME =~ FD*}]
if {[llength $speed]==0} {error "B speed context missing"}
puts $out "B_PHASE_SPEED_CONTEXT=1"
}
set marker {puts $out "RESULT=PHASE2_POSITIVE_IOB_INPUT_TIMING_AND_NO_REDUNDANT_FRONTEND_PASS"}
if {[string first $marker $script]<0} {error "Inspection anchor changed"}
set script [string map [list $marker "$extra\n$marker"] $script]
eval $script
