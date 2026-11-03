###############################################################################
# PYNQ-Z2 HDMI OUT direct-TMDS pins.
# The board routes these four differential pairs directly to the XC7Z020;
# there is no ADV7511 or HDMI-control I2C path in this design.
###############################################################################

set_property -dict {PACKAGE_PIN L16 IOSTANDARD TMDS_33} [get_ports hdmi_clk_p]
set_property -dict {PACKAGE_PIN L17 IOSTANDARD TMDS_33} [get_ports hdmi_clk_n]

set_property -dict {PACKAGE_PIN K17 IOSTANDARD TMDS_33} [get_ports {hdmi_data_p[0]}]
set_property -dict {PACKAGE_PIN K18 IOSTANDARD TMDS_33} [get_ports {hdmi_data_n[0]}]
set_property -dict {PACKAGE_PIN K19 IOSTANDARD TMDS_33} [get_ports {hdmi_data_p[1]}]
set_property -dict {PACKAGE_PIN J19 IOSTANDARD TMDS_33} [get_ports {hdmi_data_n[1]}]
set_property -dict {PACKAGE_PIN J18 IOSTANDARD TMDS_33} [get_ports {hdmi_data_p[2]}]
set_property -dict {PACKAGE_PIN H18 IOSTANDARD TMDS_33} [get_ports {hdmi_data_n[2]}]

# The frame/payload transfer uses a stable-bus plus toggle/acknowledge CDC
# protocol.  The two clocks have a common source but a non-integer 250:63
# relationship, so they must not be timed as an ordinary synchronous bus.
set hdmi_pixel_clock [get_clocks -quiet clk_out1_l2_hdmi_hdmi_clock_wiz_0]
set_clock_groups -asynchronous \
    -group [get_clocks clk_fpga_1] \
    -group $hdmi_pixel_clock
