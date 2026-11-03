// Four true dual-read ROM copies supply eight independent weight addresses.
// 4096x32 logical model, from the frozen Rain v0.4 integer package.
`timescale 1ns / 1ps
module locator_context_rom_8lane #(
    parameter MEM_INIT_FILE = "model_rom_16k.mem"
)(
    input wire clk,
    input wire [7:0] lane_rd_en,
    input wire [95:0] lane_rd_addr,
    output wire [255:0] lane_rd_data
);
    genvar pair;
    generate for (pair=0; pair<4; pair=pair+1) begin: g_pair
        (* rom_style="block" *) reg [31:0] mem [0:4095];
        reg [31:0] a, b;
        initial $readmemh(MEM_INIT_FILE, mem);
        always @(posedge clk)
            if (lane_rd_en[2*pair])
                a <= mem[lane_rd_addr[(24*pair)+:12]];
        always @(posedge clk)
            if (lane_rd_en[2*pair+1])
                b <= mem[lane_rd_addr[(24*pair+12)+:12]];
        assign lane_rd_data[(64*pair)+:64] = {b,a};
    end endgenerate
endmodule
