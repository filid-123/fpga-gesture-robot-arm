// ============================================================================
// One bank of the 8-output-lane Locator activation store.
//
// Channels are interleaved by channel[2:0].  Each physical bank therefore
// stores at most 4 KiB and provides one synchronous read plus one write per
// clock.  Eight instances retain the original 32 KiB capacity while allowing
// eight output channels to be committed without a multi-port RAM.
// ============================================================================
`timescale 1ns / 1ps

module locator_act_bank_4k #(
    parameter integer ADDR_BITS = 12
)(
    input  wire        clk,
    input  wire        wr_en,
    input  wire [11:0] wr_addr,
    input  wire [7:0]  wr_data,
    input  wire        rd_en,
    input  wire [11:0] rd_addr,
    output reg  [7:0]  rd_data
);

    (* ram_style = "block" *) reg [7:0] mem [0:(1<<ADDR_BITS)-1];

    always @(posedge clk) begin
        if (wr_en)
            mem[wr_addr[ADDR_BITS-1:0]] <= wr_data;
        if (rd_en)
            rd_data <= mem[rd_addr[ADDR_BITS-1:0]];
    end

endmodule
