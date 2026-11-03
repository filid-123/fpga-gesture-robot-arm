# Offline routed implementation review of the Phase2 profile. No hardware API.
open_project $::env(DIAG_PROJECT)
if {[get_property STATUS [get_runs impl_1]] ne "write_bitstream Complete!"} {error "Implementation incomplete"}
open_run impl_1
set out [open $::env(DIAG_INSPECT_OUT) w]
set cap [get_cells -hier -filter {NAME =~ *u_capture/*dvp_*_iob_reg* && REF_NAME =~ FD*}]
if {[llength $cap]!=10} {error "Not ten capture registers"}
foreach c [lsort $cap] {
 set cp [get_pins -of_objects $c -filter {REF_PIN_NAME == C}]
 if {![get_property IOB $c] || ![string match ILOGIC* [get_property LOC $c]] || [get_property IS_INVERTED $cp]} {error "Not original positive-edge IOB $c"}
 if {[get_clocks -of_objects $cp] ne "ov5640_pclk"} {error "Wrong capture clock"}
 puts $out "POSITIVE_IOB=$c LOC=[get_property LOC $c]"
}
foreach ref {IDELAYE2 IDELAYCTRL} {
 set count [llength [get_cells -hier -filter "REF_NAME == $ref"]]
 if {$count!=0} {error "Unexpected calibration hardware $ref $count"}
 puts $out "EXCLUDED_REFERENCE=$ref COUNT=$count"
}
set mmcms [get_cells -hier -filter {REF_NAME =~ MMCME*}]
if {[llength $mmcms]!=2} {error "Expected camera MMCM plus HDMI MMCM"}
puts $out "CAMERA_AND_HDMI_MMCM_COUNT=2"
foreach pat {*u_retained* *u_input_delay* *u_line_diag* *u_phase_diag* *u_coordinate_diag* *u_register_diag*} {
 if {[llength [get_cells -quiet -hier -filter "NAME =~ $pat"]]} {error "Redundant/paused-route hardware remains $pat"}
 puts $out "EXCLUDED_HIERARCHY=$pat COUNT=0"
}
set camera_ram [get_cells -hier -filter {NAME =~ *u_camera_memory* && REF_NAME =~ RAMB*}]
if {[llength $camera_ram]!=8} {error "Expected one 32KiB pingpong memory mapped to8 RAMB36: $camera_ram"}
foreach c $camera_ram {if {[get_property REF_NAME $c] ne "RAMB36E1"} {error "Unexpected camera RAM type"}}
puts $out "SHARED_CAMERA_RAM_COUNT=8 TYPE=RAMB36E1 PAYLOAD_BYTES=32768"
set roi [get_cells -hier -filter {NAME =~ *u_same_frame_roi* && REF_NAME =~ DSP*}]
if {[llength $roi]} {error "Unexpected DSP in nearest ROI"}
puts $out "NEAREST_ROI_DSP_COUNT=0"
foreach c [lsort [get_cells -hier -filter {REF_NAME == DSP48E1}]] {
 puts $out "ACTUAL_DSP=$c"
}
foreach port [get_ports {ov5640_data[*] ov5640_href ov5640_vsync}] {
 set found [get_timing_paths -from $port -to $cap -delay_type max -max_paths 1]
 if {[llength $found]!=1} {error "Unconstrained DVP input $port"}
 foreach type {max min} {
  set p [get_timing_paths -from $port -to $cap -delay_type $type -max_paths 1]
  if {[llength $p]!=1 || [get_property SLACK $p]<0} {error "Input $type failed $port"}
  puts $out "PHASE2_INPUT PORT=$port TYPE=$type SLACK=[get_property SLACK $p] REQUIREMENT=[get_property REQUIREMENT $p]"
 }
}
report_timing -from [get_ports {ov5640_data[*] ov5640_href ov5640_vsync}] -to $cap -delay_type min_max -max_paths 40 -path_type full_clock_expanded -input_pins -file "$::env(DIAG_INSPECT_OUT).inputs.rpt"
# Same read-only physical skew audit used by the original whole-system review.
# The asynchronous clock grouping remains unchanged in the saved design.
foreach {src dst} {wr_gray_reg wr_gray_rd_sync1_reg rd_gray_reg rd_gray_wr_sync1_reg} {
 set from [get_cells -hier -quiet -filter "NAME =~ */u_fifo/${src}* && IS_SEQUENTIAL == 1"]
 set to [get_cells -hier -quiet -filter "NAME =~ */u_fifo/${dst}* && IS_SEQUENTIAL == 1"]
 set second_name [string map {sync1 sync2} $dst]
 set second [get_cells -hier -quiet -filter "NAME =~ */u_fifo/${second_name}* && IS_SEQUENTIAL == 1"]
 if {[llength $from]!=11 || [llength $to]!=11 || [llength $second]!=11} {error "Gray pointer coverage mismatch"}
 foreach c [concat $to $second] {if {![get_property ASYNC_REG $c]} {error "Missing Gray ASYNC_REG"}}
 set_bus_skew 10.000 -from $from -to $to
 puts $out "GRAY_POINTER_GROUP SOURCE=$src DESTINATION=$dst BITS=11 SYNC_STAGES=2 BOUND_NS=10.000"
}
report_bus_skew -file "$::env(DIAG_INSPECT_OUT).bus_skew.rpt"
report_cdc -details -file $::env(DIAG_CDC_OUT)
foreach {pattern expected} {*slot_available_reg* 3 *roarm_query_phase_reg* 2} {
 set cells [get_cells -hier -quiet -filter "NAME =~ $pattern && REF_NAME =~ FD*"]
 puts $out "MODE_A_STATE_REGISTERS PATTERN=$pattern COUNT=[llength $cells] EXPECTED=$expected"
 if {[llength $cells]!=$expected} {error "Missing expected functional state registers $pattern"}
}
set serializers [get_cells -hier -filter {REF_NAME == OSERDESE2}]
if {[llength $serializers]!=6} {error "Expected3 pairs of master/slave HDMI serializers"}
puts $out "HDMI_SERIALIZERS=[llength $serializers]"
set pixel_clocks [get_clocks -of_objects [get_pins -of_objects $serializers -filter {REF_PIN_NAME == CLKDIV}]]
set serial_clocks [get_clocks -of_objects [get_pins -of_objects $serializers -filter {REF_PIN_NAME == CLK}]]
if {[llength $pixel_clocks]!=1 || [llength $serial_clocks]!=1} {error "HDMI clock coverage"}
set pixel_period [get_property PERIOD $pixel_clocks]
set serial_period [get_property PERIOD $serial_clocks]
if {abs($pixel_period-39.68254)>0.02 || abs($serial_period-7.93651)>0.02} {error "Wrong HDMI clock rates"}
puts $out "HDMI_CLOCKS PIXEL_PERIOD_NS=$pixel_period SERIAL_PERIOD_NS=$serial_period"
foreach path {status_cdc frame} {
 set a [get_cells -hier -filter "NAME =~ *u_display/$path/data1_reg* && REF_NAME =~ FD*"]
 set b [get_cells -hier -filter "NAME =~ *u_display/$path/data2_reg* && REF_NAME =~ FD*"]
 if {[llength $a]==0 || [llength $a]!=[llength $b]} {error "Missing held-payload synchronizers $path"}
 foreach c [concat $a $b] {if {![get_property ASYNC_REG $c]} {error "Missing display ASYNC_REG"}}
 puts $out "HDMI_HELD_PAYLOAD_CDC=$path WIDTH=[llength $a] SYNC_STAGES=2"
}

set frame_ram [get_cells -hier -filter {NAME =~ *u_display/frame/* && REF_NAME == RAMB36E1}]
if {[llength $frame_ram]!=16} {error "Expected four private HDMI image banks"}
puts $out "HDMI_PRIVATE_FRAME_RAMB36=[llength $frame_ram]"
puts $out "RESULT=PHASE2_POSITIVE_IOB_INPUT_TIMING_AND_NO_REDUNDANT_FRONTEND_PASS"
close $out
close_project
exit 0
