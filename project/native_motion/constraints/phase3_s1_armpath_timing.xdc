###############################################################################
# Phase 3 S1 arm-path timing exceptions.  PYNQ-Z2 / XC7Z020-1CLG400C.
# FCLK_CLK0 (100 MHz) is created by the PS7 IP; nothing is redefined here.
# Status in the S1 package: NOT_RUN (no Vivado available to the author).
#
# Every exception below is on a board pin that is asynchronous to FCLK_CLK0
# by construction; none touches an internal register-to-register path.
###############################################################################

# Inputs: each pin feeds only a 2-FF ASYNC_REG synchronizer
#   arm_uart_rx, bus_rx -> arm_uart_rx.v (2-FF sync, then divisor-timed
#                          mid-bit sampling with start-bit glitch rejection)
#   motion_enable_in    -> arm_motion_permission_gate.v (2-FF + debounce)
# The sender is not clocked by FCLK_CLK0, so an input delay would be
# meaningless; the synchronizer, not I/O timing, handles metastability.
set_false_path -from [get_ports {arm_uart_rx bus_rx motion_enable_in}]

# Outputs: registered in arm_backend_core.v with no combinational logic after
# the flop.  The shortest bit time is 1 us (1 Mbaud = 100 FCLK cycles); the
# receiver samples near mid-bit, so a few ns of pad/route skew is < 1 % of the
# bit.  bus_dir is sequenced against bus_tx in RTL by the lead/lag counters
# (arm_half_duplex_dir_ctrl.v, >= 1 cycle, configured in microseconds), not by
# I/O timing.
set_false_path -to [get_ports {arm_uart_tx bus_tx bus_dir}]

# Keep TX and DIR in the IOB flops so their mutual skew is fixed by silicon,
# not by placement (the output flops drive only the pads).
set_property IOB TRUE [get_ports {arm_uart_tx bus_tx bus_dir}]
