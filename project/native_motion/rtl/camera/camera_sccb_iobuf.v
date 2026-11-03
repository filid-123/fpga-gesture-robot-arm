// Open-drain SCCB pads. The masters only drive logic 0; external pull-ups
// produce logic 1. SIOC input is intentionally unused (no clock stretching).
`timescale 1ns / 1ps

module camera_sccb_iobuf (
    input  wire scl_drive_low,
    input  wire sda_drive_low,
    output wire sda_in,
    inout  wire ov5640_scl,
    inout  wire ov5640_sda
);
    wire scl_in_unused;

    IOBUF u_scl_iobuf (
        .I(1'b0),
        .T(~scl_drive_low),
        .O(scl_in_unused),
        .IO(ov5640_scl)
    );

    IOBUF u_sda_iobuf (
        .I(1'b0),
        .T(~sda_drive_low),
        .O(sda_in),
        .IO(ov5640_sda)
    );
endmodule
