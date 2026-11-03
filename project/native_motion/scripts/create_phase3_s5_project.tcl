# Recreate the Phase 3 S5 pure-FPGA-mode project for PYNQ-Z2 (candidate v0.1.0): ONE design
# with the S3 v0.1.1 seven-class vision chain and the S4 v0.1.1 task controller (S2 v0.2.3 /
# S1 v0.1.1 inside), joined by the S5 vision event adapter.  LED build (no HDMI).
# Status in the S5 package: NOT_RUN_ENV_UNAVAILABLE (author had no Vivado).
#
# Derived from create_phase3_s3_gesture7_project.tcl (S3 v0.1.1) and
# create_phase3_s4_task_project.tcl (S4 v0.1.1):
#   PS7 FCLK_CLK0 50 MHz  -> S3 classifier domain (clk_50mhz), as S3
#   PS7 FCLK_CLK1 100 MHz -> S3 system domain clk_100mhz = S4 s_axi_aclk = GP0 = SmartConnect
#                            (ONE net: the script checks it; S4 is built with VIS_ASYNC = 0)
#   OV5640 pclk / 24 MHz xclk wizard / SCCB IOBUF / LEDs exactly as S3
#   PS7 GP0 -> SmartConnect (5 MI) -> s5_0 (phase3_s5_vision_motion_top):
#     s_axi_traj 0x43C2_0000 (S1, ABI 0x3002)   s_axi_arm 0x43C3_0000 (S1, ABI 0x3101)
#     s_axi_plan 0x43C4_0000 (S2, ABI 0x3201)   s_axi_s4  0x43C5_0000 (S4, ABI 0x3401, PROPOSED)
#     s_axi_vis  0x43C6_0000 (S5 adapter, ABI 0x3501, PROPOSED)
#   IRQ_F2P[3:0] = {irq_s4, irq_plan, irq_arm, irq_traj} (as S4).
#   Arm pins as S1: arm_uart_tx/rx, bus_tx/rx/dir, motion_enable_in.
# Constraints: S3 phase2_l2_autonomous_ov5640.xdc, _leds.xdc, _cdc.xdc (late; clk_fpga_0/1 and
# ov5640_pclk asynchronous, unchanged), S1 phase3_s1_armpath_timing.xdc and the FILLED
# phase3_s1_armpath_pins.xdc (build_phase3_s5.tcl refuses TBD / camera / LED pins).
# The S3 classifier package is an explicit input (GESTURE7_PACKAGE), gated as in S3: SYNTHETIC_* /
# RTL_TEST_* packages are refused unless GESTURE7_ALLOW_TEST_WEIGHTS=1 (resource/timing build only).
# No existing project or bitstream is opened or modified.

set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set project_dir [file join $root_dir vivado_phase3_s5_vision_motion]
set project_name "Gesture_Phase3_S5_VisionMotion"
set bd_name "phase3_s5_vision_motion"
set part_name "xc7z020clg400-1"
set board_name "tul.com.tw:pynq-z2:part0:1.0"
set traj_base 0x43C20000
set arm_base  0x43C30000
set plan_base 0x43C40000
set s4_base   0x43C50000
set vis_base  0x43C60000

set_param ips.enableInterfaceArrayInference false
set board_store [xhub::get_xstores xilinx_board_store]
if {[llength $board_store] == 0} {
    error "Vivado xilinx_board_store is unavailable."
}
set board_repo [get_property LOCAL_ROOT_DIR $board_store]
set_param board.repoPaths [list $board_repo]
if {[lsearch -exact [get_board_parts -quiet *pynq*z2*] $board_name] < 0} {
    error "Missing $board_name. Run scripts/install_pynq_z2_board_part.tcl first."
}
if {[file exists $project_dir]} {
    error "Refusing to overwrite $project_dir; move it away first."
}

# ---------------------------------------------------------------------------- sources
set s3_sources {
    cnn/cnn_core_7c.v cnn/cnn_core_fsm.v cnn/cnn_desc_mem.v cnn/generic_conv3x3.v cnn/generic_maxpool2x2.v
    cnn/generic_dense_7c.v cnn/cnn_act_bram.v cnn/weight_bram.v cnn/mac_lane.v cnn/requant_unit.v
    camera/classifier_roi_bram.v camera/ov5640_capture.v camera/cdc_async_fifo.v camera/pl_letterbox_640x480.v
    camera/pl_roi_nearest_32x32.v camera/same_frame_roi_128x128.v camera/ov5640_l2_frontend.v
    camera/camera_locator_input_bram.v camera/sccb_master_sync.v camera/camera_sccb_iobuf.v
    camera/ov5640_xclk_forward.v locator/locator_act_bank_4k.v locator/locator_cnn_engine_8lane.v
    locator/locator_top1_reducer.v autonomous/locator_model_rom_8lane.v autonomous/locator_bbox_roi_fixed_v4.v
    autonomous/class_confirm_filter_7c.v autonomous/classifier_cdc_bridge_7c.v autonomous/ov5640_init_fsm.v
    autonomous/autonomous_pipeline_ctrl_7c.v autonomous/gesture_autonomous_top_v5_7c.v
}
set motion_sources {
    robot/trajectory_smoothstep_q16_16.v robot/trajectory_stream_scheduler.v robot/trajectory_axi_lite_top.v
    robot/arm_uart_tx.v robot/arm_uart_rx.v robot/arm_half_duplex_dir_ctrl.v robot/arm_joint_unit_mapper.v
    robot/arm_frame_formatter.v robot/arm_json_feedback_parser.v robot/arm_so101_status_parser.v
    robot/arm_feedback_watchdog.v robot/arm_motion_permission_gate.v robot/arm_backend_core.v
    robot/arm_backend_axi_top.v
    robot/planner_seq_mult.v robot/planner_seq_div.v robot/planner_p2p_core.v robot/planner_axi_top.v
    robot/motion_sample_mux.v robot/phase3_s2_motion_top.v
    robot/s4_axil_window.v robot/s4_motion_link.v robot/s4_task_regs.v robot/s4_task_fsm.v robot/phase3_s4_task_top.v
}
set s5_sources {
    integration/s5_vision_event_adapter.v integration/phase3_s5_vision_motion_top.v
}
set source_files {}
foreach f [concat $s3_sources $motion_sources $s5_sources] {
    set path [file join $root_dir rtl $f]
    if {![file exists $path]} { error "Missing S1/S2/S3/S4/S5 source (merge first): $path" }
    lappend source_files $path
}

# S3 classifier package gate (as create_phase3_s3_gesture7_project.tcl)
if {![info exists ::env(GESTURE7_PACKAGE)]} {
    error "Set GESTURE7_PACKAGE to an exported seven-class package directory."
}
set gesture7_package [file normalize $::env(GESTURE7_PACKAGE)]
set gesture7_manifest [file join $gesture7_package gesture7_manifest.json]
if {![file exists $gesture7_manifest]} { error "Missing $gesture7_manifest" }
set fh [open $gesture7_manifest r]
set manifest_text [read $fh]
close $fh
if {![regexp {"status":\s*"([A-Z0-9_]+)"} $manifest_text -> gesture7_status]} {
    error "No status field in $gesture7_manifest"
}
if {![regexp {"num_classes":\s*7\M} $manifest_text]} { error "$gesture7_manifest is not a seven-class package" }
set allow_test [expr {[info exists ::env(GESTURE7_ALLOW_TEST_WEIGHTS)] && $::env(GESTURE7_ALLOW_TEST_WEIGHTS) eq "1"}]
if {[regexp {^(SYNTHETIC|RTL_TEST)} $gesture7_status] && !$allow_test} {
    error "Package status $gesture7_status is not a trained model; set GESTURE7_ALLOW_TEST_WEIGHTS=1 only for a resource/timing build."
}
puts "S5_GESTURE7_PACKAGE=$gesture7_package"
puts "S5_GESTURE7_PACKAGE_STATUS=$gesture7_status"
if {$allow_test} { puts "WARNING: TEST WEIGHTS ALLOWED - resource/timing build only, never deploy as a gesture model." }

set init_files [list \
    [file join $gesture7_package layer_descriptors.mem] \
    [file join $gesture7_package weights_all.mem] \
    [file join $root_dir quantized_locator_v16_failure_adaptation locator_model_blob.mem] \
    [file join $root_dir rtl autonomous ov5640_vga_yuyv.mem] \
]
foreach f $init_files { if {![file exists $f]} { error "Missing BRAM initialization file: $f" } }

create_project $project_name $project_dir -part $part_name
set_property BOARD_PART_REPO_PATHS [list $board_repo] [current_project]
set_property BOARD_PART $board_name [current_project]
set_property TARGET_LANGUAGE Verilog [current_project]
file mkdir $project_dir
set build_info [open [file join $project_dir S5_BUILD_INFO.json] w]
puts $build_info [format {{"schema": "gesture.phase3.s5_build_info.v1", "gesture7_package": "%s", "gesture7_package_status": "%s", "test_weights_allowed": %s}} $gesture7_package $gesture7_status [expr {$allow_test ? "true" : "false"}]]
close $build_info
add_files -norecurse $source_files
add_files -norecurse $init_files

set xdc_dir [file join $root_dir constraints]
add_files -fileset constrs_1 -norecurse [file join $xdc_dir phase2_l2_autonomous_ov5640.xdc] \
    [file join $xdc_dir phase2_l2_autonomous_leds.xdc] [file join $xdc_dir phase3_s1_armpath_timing.xdc]
set cdc_xdc [file join $xdc_dir phase2_l2_autonomous_cdc.xdc]
add_files -fileset constrs_1 -norecurse $cdc_xdc
set_property USED_IN_SYNTHESIS false [get_files $cdc_xdc]
set_property USED_IN_IMPLEMENTATION true [get_files $cdc_xdc]
set_property PROCESSING_ORDER LATE [get_files $cdc_xdc]
set pin_xdc [file join $xdc_dir phase3_s1_armpath_pins.xdc]
if {[file exists $pin_xdc]} {
    add_files -fileset constrs_1 -norecurse $pin_xdc
} else {
    puts "WARNING: $pin_xdc not present; build_phase3_s5.tcl refuses to implement until the arm pins are filled."
}
update_compile_order -fileset sources_1

# ---------------------------------------------------------------------------- block design
create_bd_design $bd_name
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 processing_system7_0
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
    -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} \
    [get_bd_cells processing_system7_0]
set_property -dict [list \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {50} \
    CONFIG.PCW_FPGA1_PERIPHERAL_FREQMHZ {100} \
    CONFIG.PCW_EN_CLK1_PORT {1} \
    CONFIG.PCW_FCLK_CLK1_BUF {TRUE} \
    CONFIG.PCW_USE_M_AXI_GP0 {1} \
    CONFIG.PCW_USE_FABRIC_INTERRUPT {1} \
    CONFIG.PCW_IRQ_F2P_INTR {1} \
    CONFIG.PCW_EN_USB0 {0} \
    CONFIG.PCW_USB0_PERIPHERAL_ENABLE {0} \
] [get_bd_cells processing_system7_0]

create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 const_zero_1
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {0}] [get_bd_cells const_zero_1]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 const_one_1
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {1}] [get_bd_cells const_one_1]
foreach {reset_name clock_pin} {rst_50m FCLK_CLK0 rst_100m FCLK_CLK1} {
    create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 $reset_name
    set_property -dict [list CONFIG.C_AUX_RESET_HIGH {1}] [get_bd_cells $reset_name]
    connect_bd_net [get_bd_pins processing_system7_0/$clock_pin] [get_bd_pins $reset_name/slowest_sync_clk]
    connect_bd_net [get_bd_pins processing_system7_0/FCLK_RESET0_N] [get_bd_pins $reset_name/ext_reset_in]
    connect_bd_net [get_bd_pins const_zero_1/dout] [get_bd_pins $reset_name/aux_reset_in]
    connect_bd_net [get_bd_pins const_one_1/dout] [get_bd_pins $reset_name/dcm_locked]
}

create_bd_cell -type module -reference phase3_s5_vision_motion_top s5_0
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins s5_0/clk_50mhz]
connect_bd_net [get_bd_pins rst_50m/peripheral_aresetn] [get_bd_pins s5_0/rst_50mhz_n]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK1] [get_bd_pins s5_0/clk_100mhz] \
    [get_bd_pins processing_system7_0/M_AXI_GP0_ACLK]
connect_bd_net [get_bd_pins rst_100m/peripheral_aresetn] [get_bd_pins s5_0/rst_100mhz_n]

create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 ps_axi_fabric
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {5}] [get_bd_cells ps_axi_fabric]
connect_bd_intf_net [get_bd_intf_pins processing_system7_0/M_AXI_GP0] [get_bd_intf_pins ps_axi_fabric/S00_AXI]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK1] [get_bd_pins ps_axi_fabric/aclk]
connect_bd_net [get_bd_pins rst_100m/interconnect_aresetn] [get_bd_pins ps_axi_fabric/aresetn]
foreach {mi intf} {M00_AXI s_axi_traj M01_AXI s_axi_arm M02_AXI s_axi_plan M03_AXI s_axi_s4 M04_AXI s_axi_vis} {
    connect_bd_intf_net [get_bd_intf_pins ps_axi_fabric/$mi] [get_bd_intf_pins s5_0/$intf]
}

create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat:2.1 irq_concat
set_property CONFIG.NUM_PORTS {4} [get_bd_cells irq_concat]
foreach {pin idx} {irq_traj 0 irq_arm 1 irq_plan 2 irq_s4 3} {
    connect_bd_net [get_bd_pins s5_0/$pin] [get_bd_pins irq_concat/In$idx]
}
connect_bd_net [get_bd_pins irq_concat/dout] [get_bd_pins processing_system7_0/IRQ_F2P]

# OV5640 exactly as S3
create_bd_port -dir I -from 7 -to 0 ov5640_data
create_bd_port -dir I -type clk ov5640_pclk
set_property CONFIG.FREQ_HZ {48000000} [get_bd_ports ov5640_pclk]
create_bd_port -dir I ov5640_href
create_bd_port -dir I ov5640_vsync
create_bd_port -dir O ov5640_reset_n
create_bd_port -dir O ov5640_pwdn
connect_bd_net [get_bd_ports ov5640_data] [get_bd_pins s5_0/dvp_data]
connect_bd_net [get_bd_ports ov5640_pclk] [get_bd_pins s5_0/pclk]
connect_bd_net [get_bd_ports ov5640_href] [get_bd_pins s5_0/dvp_href]
connect_bd_net [get_bd_ports ov5640_vsync] [get_bd_pins s5_0/dvp_vsync]
connect_bd_net [get_bd_ports ov5640_reset_n] [get_bd_pins s5_0/camera_reset_n]
connect_bd_net [get_bd_ports ov5640_pwdn] [get_bd_pins s5_0/camera_pwdn]
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_camera_pclk
set_property -dict [list CONFIG.C_AUX_RESET_HIGH {1}] [get_bd_cells rst_camera_pclk]
connect_bd_net [get_bd_ports ov5640_pclk] [get_bd_pins rst_camera_pclk/slowest_sync_clk]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_RESET0_N] [get_bd_pins rst_camera_pclk/ext_reset_in]
connect_bd_net [get_bd_pins const_zero_1/dout] [get_bd_pins rst_camera_pclk/aux_reset_in]
connect_bd_net [get_bd_pins const_one_1/dout] [get_bd_pins rst_camera_pclk/dcm_locked]
connect_bd_net [get_bd_pins rst_camera_pclk/peripheral_aresetn] [get_bd_pins s5_0/pclk_rst_n]
create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 camera_xclk_wiz
set_property -dict [list CONFIG.PRIM_SOURCE {No_buffer} CONFIG.PRIM_IN_FREQ {100.000} \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {24.000} CONFIG.USE_RESET {false} CONFIG.USE_LOCKED {true}] \
    [get_bd_cells camera_xclk_wiz]
create_bd_cell -type module -reference ov5640_xclk_forward ov5640_xclk_forward_0
create_bd_port -dir O -type clk ov5640_xclk
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK1] [get_bd_pins camera_xclk_wiz/clk_in1]
connect_bd_net [get_bd_pins camera_xclk_wiz/clk_out1] [get_bd_pins ov5640_xclk_forward_0/clk_24mhz]
connect_bd_net [get_bd_pins camera_xclk_wiz/locked] [get_bd_pins s5_0/xclk_locked]
connect_bd_net [get_bd_pins ov5640_xclk_forward_0/ov5640_xclk] [get_bd_ports ov5640_xclk]
create_bd_cell -type module -reference camera_sccb_iobuf camera_sccb_iobuf_0
create_bd_port -dir IO ov5640_scl
create_bd_port -dir IO ov5640_sda
connect_bd_net [get_bd_pins s5_0/sccb_scl_drive_low] [get_bd_pins camera_sccb_iobuf_0/scl_drive_low]
connect_bd_net [get_bd_pins s5_0/sccb_sda_drive_low] [get_bd_pins camera_sccb_iobuf_0/sda_drive_low]
connect_bd_net [get_bd_pins camera_sccb_iobuf_0/sda_in] [get_bd_pins s5_0/sccb_sda_in]
connect_bd_net [get_bd_ports ov5640_scl] [get_bd_pins camera_sccb_iobuf_0/ov5640_scl]
connect_bd_net [get_bd_ports ov5640_sda] [get_bd_pins camera_sccb_iobuf_0/ov5640_sda]
create_bd_port -dir O -from 3 -to 0 leds
connect_bd_net [get_bd_pins s5_0/leds] [get_bd_ports leds]

# arm pins as S1
foreach {port dir} {arm_uart_tx O arm_uart_rx I bus_tx O bus_rx I bus_dir O motion_enable_in I} {
    create_bd_port -dir $dir $port
    connect_bd_net [get_bd_ports $port] [get_bd_pins s5_0/$port]
}

foreach {intf base} [list s_axi_traj $traj_base s_axi_arm $arm_base s_axi_plan $plan_base \
                          s_axi_s4 $s4_base s_axi_vis $vis_base] {
    assign_bd_address -offset $base -range 4K -target_address_space [get_bd_addr_spaces processing_system7_0/Data] \
        [get_bd_addr_segs s5_0/$intf/reg0] -force
}

validate_bd_design -force

foreach {object property expected} [list \
    [get_bd_cells processing_system7_0] CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ 50 \
    [get_bd_cells processing_system7_0] CONFIG.PCW_FPGA1_PERIPHERAL_FREQMHZ 100 \
    [get_bd_cells processing_system7_0] CONFIG.PCW_USE_M_AXI_GP0 1 \
    [get_bd_intf_pins processing_system7_0/M_AXI_GP0] CONFIG.FREQ_HZ 100000000 \
    [get_bd_cells ps_axi_fabric] CONFIG.NUM_MI 5 \
    [get_bd_cells irq_concat] CONFIG.NUM_PORTS 4 \
] {
    set actual [get_property $property $object]
    if {$actual ne $expected} { error "S5 BD mismatch: $object $property expected $expected, got $actual" }
}
# One clock net for the S3 system domain, the S4/S5 AXI windows and GP0 (VIS_ASYNC = 0 relies on it).
set clk_net [get_bd_nets -of_objects [get_bd_pins s5_0/clk_100mhz]]
foreach pin {processing_system7_0/M_AXI_GP0_ACLK ps_axi_fabric/aclk processing_system7_0/FCLK_CLK1} {
    if {[get_bd_nets -of_objects [get_bd_pins $pin]] ne $clk_net} {
        error "S5 clock contract: $pin is not on the clk_100mhz net $clk_net"
    }
}
if {[get_bd_nets -of_objects [get_bd_pins s5_0/clk_50mhz]] eq $clk_net} {
    error "S5 clock contract: the 50 MHz classifier clock must not be the 100 MHz net"
}
set offsets {}
foreach seg [get_bd_addr_segs -of_objects [get_bd_addr_spaces processing_system7_0/Data]] {
    lappend offsets [get_property OFFSET $seg]
}
foreach expected [list $traj_base $arm_base $plan_base $s4_base $vis_base] {
    if {[lsearch -exact $offsets $expected] < 0} { error "S5 address map is missing $expected (found: $offsets)" }
}

save_bd_design
set bd_file [get_files [file join $project_dir ${project_name}.srcs sources_1 bd $bd_name ${bd_name}.bd]]
generate_target all $bd_file
make_wrapper -files $bd_file -top
add_files -norecurse [file join $project_dir ${project_name}.gen sources_1 bd $bd_name hdl ${bd_name}_wrapper.v]
set_property top ${bd_name}_wrapper [current_fileset]
update_compile_order -fileset sources_1

puts "PHASE3_S5_PROJECT=[file join $project_dir ${project_name}.xpr]"
puts "PHASE3_S5_MAP traj=$traj_base arm=$arm_base plan=$plan_base s4=$s4_base vis=$vis_base (4K each)"
puts "PASS: Phase 3 S5 vision+motion Block Design created and validated (one 100 MHz net, package status $gesture7_status)."
exit 0
