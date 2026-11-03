// Both input memories have the same one-cycle read latency. Source selection
// must remain static from Locator START until its input-release event.
`timescale 1ns / 1ps

module locator_input_source_mux (
    input  wire        select_camera,
    input  wire [31:0] ps_input_data,
    input  wire [31:0] camera_input_data,
    output wire [31:0] locator_input_data
);
    assign locator_input_data = select_camera ? camera_input_data : ps_input_data;
endmodule
