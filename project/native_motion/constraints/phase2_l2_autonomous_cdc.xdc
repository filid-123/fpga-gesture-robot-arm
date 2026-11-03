###############################################################################
# Autonomous L2 CDC contract, applied during implementation when PS FCLK
# objects exist.  All crossings use async FIFO or explicit toggle/synchronizer
# logic; there are no ordinary data paths between these domains.
###############################################################################

set_clock_groups -asynchronous \
    -group [get_clocks ov5640_pclk] \
    -group [get_clocks clk_fpga_0]
set_clock_groups -asynchronous \
    -group [get_clocks ov5640_pclk] \
    -group [get_clocks clk_fpga_1]
set_clock_groups -asynchronous \
    -group [get_clocks clk_fpga_0] \
    -group [get_clocks clk_fpga_1]

