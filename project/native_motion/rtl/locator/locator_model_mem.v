// ============================================================================
// 8 KiB / 2048-word Locator parameter memory.
//
// READ_REPLICAS=1 preserves the scalar/stub implementation. READ_REPLICAS=8
// mirrors every PS write into eight identical BRAM sets, providing one
// independent synchronous read address per output-channel MAC lane without
// changing the model blob or its CRC contract.
// ============================================================================
`timescale 1ns / 1ps

module locator_model_mem #(
    parameter integer READ_REPLICAS = 1
)(
    input  wire         clk,
    input  wire         wr_en,
    input  wire [10:0]  wr_addr,
    input  wire [31:0]  wr_data,

    input  wire         rd_en,
    input  wire [10:0]  rd_addr,
    output wire [31:0]  rd_data,

    input  wire [7:0]   lane_rd_en,
    input  wire [87:0]  lane_rd_addr,
    output wire [255:0] lane_rd_data
);

    (* ram_style = "block" *) reg [31:0] mem  [0:2047];
    (* ram_style = "block" *) reg [31:0] mem1 [0:2047];
    (* ram_style = "block" *) reg [31:0] mem2 [0:2047];
    (* ram_style = "block" *) reg [31:0] mem3 [0:2047];
    (* ram_style = "block" *) reg [31:0] mem4 [0:2047];
    (* ram_style = "block" *) reg [31:0] mem5 [0:2047];
    (* ram_style = "block" *) reg [31:0] mem6 [0:2047];
    (* ram_style = "block" *) reg [31:0] mem7 [0:2047];

    reg [31:0] bank_data [0:7];
    wire bank0_rd_en = rd_en || lane_rd_en[0];
    wire [10:0] bank0_rd_addr = rd_en ? rd_addr : lane_rd_addr[10:0];

    always @(posedge clk) begin
        if (wr_en) begin
            mem[wr_addr] <= wr_data;
            if (READ_REPLICAS == 8) begin
                mem1[wr_addr] <= wr_data;
                mem2[wr_addr] <= wr_data;
                mem3[wr_addr] <= wr_data;
                mem4[wr_addr] <= wr_data;
                mem5[wr_addr] <= wr_data;
                mem6[wr_addr] <= wr_data;
                mem7[wr_addr] <= wr_data;
            end
        end

        if (bank0_rd_en)
            bank_data[0] <= mem[bank0_rd_addr];
        if ((READ_REPLICAS == 8) && lane_rd_en[1])
            bank_data[1] <= mem1[lane_rd_addr[21:11]];
        if ((READ_REPLICAS == 8) && lane_rd_en[2])
            bank_data[2] <= mem2[lane_rd_addr[32:22]];
        if ((READ_REPLICAS == 8) && lane_rd_en[3])
            bank_data[3] <= mem3[lane_rd_addr[43:33]];
        if ((READ_REPLICAS == 8) && lane_rd_en[4])
            bank_data[4] <= mem4[lane_rd_addr[54:44]];
        if ((READ_REPLICAS == 8) && lane_rd_en[5])
            bank_data[5] <= mem5[lane_rd_addr[65:55]];
        if ((READ_REPLICAS == 8) && lane_rd_en[6])
            bank_data[6] <= mem6[lane_rd_addr[76:66]];
        if ((READ_REPLICAS == 8) && lane_rd_en[7])
            bank_data[7] <= mem7[lane_rd_addr[87:77]];
    end

    assign rd_data = bank_data[0];
    assign lane_rd_data = {
        bank_data[7], bank_data[6], bank_data[5], bank_data[4],
        bank_data[3], bank_data[2], bank_data[1], bank_data[0]
    };

endmodule
