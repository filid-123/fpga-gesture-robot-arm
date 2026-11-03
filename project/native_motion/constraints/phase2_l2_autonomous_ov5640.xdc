###############################################################################
# Phase 2-L2 autonomous OV5640 pins and DVP input timing.
# PYNQ-Z2 / XC7Z020-1CLG400C, frozen JA/JB wiring dated 2026-08-24.
###############################################################################

set_property -dict {PACKAGE_PIN Y18 IOSTANDARD LVCMOS33} [get_ports {ov5640_data[0]}]
set_property -dict {PACKAGE_PIN Y19 IOSTANDARD LVCMOS33} [get_ports {ov5640_data[1]}]
set_property -dict {PACKAGE_PIN Y16 IOSTANDARD LVCMOS33} [get_ports {ov5640_data[2]}]
set_property -dict {PACKAGE_PIN Y17 IOSTANDARD LVCMOS33} [get_ports {ov5640_data[3]}]
set_property -dict {PACKAGE_PIN U19 IOSTANDARD LVCMOS33} [get_ports {ov5640_data[4]}]
set_property -dict {PACKAGE_PIN W18 IOSTANDARD LVCMOS33} [get_ports {ov5640_data[5]}]
set_property -dict {PACKAGE_PIN W19 IOSTANDARD LVCMOS33} [get_ports {ov5640_data[6]}]
set_property -dict {PACKAGE_PIN W14 IOSTANDARD LVCMOS33} [get_ports {ov5640_data[7]}]

set_property -dict {PACKAGE_PIN U18 IOSTANDARD LVCMOS33} [get_ports ov5640_pclk]
set_property -dict {PACKAGE_PIN Y14 IOSTANDARD LVCMOS33} [get_ports ov5640_href]
set_property -dict {PACKAGE_PIN T11 IOSTANDARD LVCMOS33} [get_ports ov5640_vsync]

set_property -dict {PACKAGE_PIN T10 IOSTANDARD LVCMOS33 DRIVE 8 SLEW FAST} \
    [get_ports ov5640_xclk]
set_property -dict {PACKAGE_PIN V16 IOSTANDARD LVCMOS33 SLEW SLOW} \
    [get_ports ov5640_scl]
set_property -dict {PACKAGE_PIN W16 IOSTANDARD LVCMOS33 SLEW SLOW} \
    [get_ports ov5640_sda]
set_property -dict {PACKAGE_PIN V12 IOSTANDARD LVCMOS33 DRIVE 8 SLEW SLOW} \
    [get_ports ov5640_reset_n]
set_property -dict {PACKAGE_PIN W13 IOSTANDARD LVCMOS33 DRIVE 8 SLEW SLOW} \
    [get_ports ov5640_pwdn]

create_clock -name ov5640_pclk -period 20.833 [get_ports ov5640_pclk]

# This is the timing envelope already validated by the current working camera
# build.  The source launches the DVP bus on the edge opposite the PL IOB
# capture edge.  The 2..8 ns figures remain a provisional board-level budget
# until they are replaced by oscilloscope measurements.
set autonomous_dvp_ports [get_ports {ov5640_data[*] ov5640_href ov5640_vsync}]
set_input_delay -clock [get_clocks ov5640_pclk] -clock_fall -min 2.000 \
    $autonomous_dvp_ports
set_input_delay -clock [get_clocks ov5640_pclk] -clock_fall -max 8.000 \
    $autonomous_dvp_ports

