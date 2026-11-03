###############################################################################
# Phase 3 S1 arm-path candidate pin map -- PYNQ-Z2 Arduino D0..D5.
#
# Source: installed TUL PYNQ-Z2 Vivado 2026.1 board file, part0_pins.xml.
# This avoids PMOD JA/JB, which remain reserved for the OV5640 DVP interface.
# Verify the physical Arduino header labels and wiring before loading the
# overlay on a board.  All external signals at the FPGA pins must be 3.3 V.
###############################################################################

# RoArm-M3 UART: Arduino D1 (TX) and D0 (RX).
set_property -dict {PACKAGE_PIN U12 IOSTANDARD LVCMOS33 DRIVE 4 SLEW SLOW} [get_ports arm_uart_tx]
set_property -dict {PACKAGE_PIN T14 IOSTANDARD LVCMOS33 PULLUP TRUE} [get_ports arm_uart_rx]

# SO-ARM101 bench bus: Arduino D2..D4.  Use an external half-duplex buffer;
# never connect these FPGA pins directly to a powered servo bus.

# Motion permission: Arduino D5.  Open/unconnected means no permission.
set_property -dict {PACKAGE_PIN T15 IOSTANDARD LVCMOS33 PULLDOWN TRUE} [get_ports motion_enable_in]
# SCCB SDA feeds only the first ASYNC_REG stage in the physical vision top.
set_false_path -from [get_ports ov5640_sda]
