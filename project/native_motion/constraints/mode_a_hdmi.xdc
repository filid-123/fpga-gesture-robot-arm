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

# Request/acknowledge held payload CDC, independent of camera FIFO domains.
set pixel_clock [get_clocks -quiet -filter {NAME =~ *hdmi_clock_wiz*clk_out1* || NAME =~ clk_out1*hdmi_clock_wiz*}]
if {[llength $pixel_clock]!=1} {error "Require unique HDMI pixel clock"}
set_clock_groups -asynchronous -group [get_clocks clk_fpga_1] -group $pixel_clock
