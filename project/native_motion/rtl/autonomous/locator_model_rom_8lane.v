// Frozen Locator-v16 parameter ROM with eight synchronous read replicas.
// No PS write port and no runtime CRC/commit path exist in this production ROM.
`timescale 1ns / 1ps

module locator_model_rom_8lane #(
    parameter MEM_INIT_FILE = "locator_model_blob.mem"
)(
    input  wire         clk,
    input  wire [7:0]   lane_rd_en,
    input  wire [87:0]  lane_rd_addr,
    output wire [255:0] lane_rd_data
);

    (* ram_style = "block" *) reg [31:0] mem0 [0:2047];
    (* ram_style = "block" *) reg [31:0] mem1 [0:2047];
    (* ram_style = "block" *) reg [31:0] mem2 [0:2047];
    (* ram_style = "block" *) reg [31:0] mem3 [0:2047];
    (* ram_style = "block" *) reg [31:0] mem4 [0:2047];
    (* ram_style = "block" *) reg [31:0] mem5 [0:2047];
    (* ram_style = "block" *) reg [31:0] mem6 [0:2047];
    (* ram_style = "block" *) reg [31:0] mem7 [0:2047];
    reg [31:0] lane_data [0:7];

    initial begin
        $readmemh(MEM_INIT_FILE, mem0);
        $readmemh(MEM_INIT_FILE, mem1);
        $readmemh(MEM_INIT_FILE, mem2);
        $readmemh(MEM_INIT_FILE, mem3);
        $readmemh(MEM_INIT_FILE, mem4);
        $readmemh(MEM_INIT_FILE, mem5);
        $readmemh(MEM_INIT_FILE, mem6);
        $readmemh(MEM_INIT_FILE, mem7);
    end

    always @(posedge clk) begin
        if (lane_rd_en[0]) lane_data[0] <= mem0[lane_rd_addr[10:0]];
        if (lane_rd_en[1]) lane_data[1] <= mem1[lane_rd_addr[21:11]];
        if (lane_rd_en[2]) lane_data[2] <= mem2[lane_rd_addr[32:22]];
        if (lane_rd_en[3]) lane_data[3] <= mem3[lane_rd_addr[43:33]];
        if (lane_rd_en[4]) lane_data[4] <= mem4[lane_rd_addr[54:44]];
        if (lane_rd_en[5]) lane_data[5] <= mem5[lane_rd_addr[65:55]];
        if (lane_rd_en[6]) lane_data[6] <= mem6[lane_rd_addr[76:66]];
        if (lane_rd_en[7]) lane_data[7] <= mem7[lane_rd_addr[87:77]];
    end

    assign lane_rd_data = {
        lane_data[7], lane_data[6], lane_data[5], lane_data[4],
        lane_data[3], lane_data[2], lane_data[1], lane_data[0]
    };

endmodule
