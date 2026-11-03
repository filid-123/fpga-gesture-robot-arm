`timescale 1ns / 1ps

module cnn_act_bram #(
    parameter integer SECOND_WRITE=0,
    parameter integer ADDR_BITS = 14
)(
    input  wire        clk,

    // Port A: Write (from CNN Engine)
    input  wire        we_en,
    input  wire [13:0] we_addr,
    input  wire [7:0]  we_data,

    // Port B: Read (from CNN Engine or PS)
    input  wire        rd_en,
    input  wire [13:0] rd_addr,
    input wire we2_en,input wire [13:0] we2_addr,input wire [7:0] we2_data,
    output reg  [7:0]  rd_data
);

    // 16KB Memory for activations (sufficient for max 8192 bytes C1 output)
    (* ram_style="block" *) reg [7:0] mem [0:(1<<ADDR_BITS)-1];

    // Port A
    always @(posedge clk) begin
        if (we_en) begin
            if (^we_data === 1'bx) begin
                $display("[%0t] [ACT_BRAM] ERROR: Writing X! addr=%d", $time, we_addr);
            end
            mem[we_addr[ADDR_BITS-1:0]] <= we_data;
        end
    end

    // Port B uses one shared address for read/write, the standard TDP template.
    // The destination's read value is unused while the second lane writes it.
    wire b_write=(SECOND_WRITE!=0) && we2_en;
    wire [ADDR_BITS-1:0] b_addr=b_write?we2_addr[ADDR_BITS-1:0]:rd_addr[ADDR_BITS-1:0];
    always @(posedge clk) begin
        if (b_write || rd_en) begin
            if(b_write)mem[b_addr]<=we2_data;
            rd_data <= mem[b_addr];
        end
    end

endmodule
