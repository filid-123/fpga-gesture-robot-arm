`timescale 1ns / 1ps

module weight_bram #(
    parameter MEM_INIT_FILE = "weights_all.mem",
    parameter integer WORDS = 16384
)(
    input  wire        clk,
    
    // Port A (PS Write Port via AXI Slave - 32-bit word access)
    input  wire        we_a,
    input  wire [15:0] addr_a, // Byte address from AXI (must be 4-byte aligned)
    input  wire [31:0] din_a,
    output reg  [31:0] dout_a,
    
    // Port B (PL Read Port via Engine - 8-bit byte access)
    input  wire        en_b,
    input  wire [15:0] addr_b, // Exact byte address
    output reg  [7:0]  dout_b
);

    // 64KB Weight Array = 16,384 words of 32 bits
    (* ram_style="block" *) reg [31:0] mem [0:WORDS-1];

    initial begin
        $readmemh(MEM_INIT_FILE, mem);
    end

    // Port A: 32-bit Write/Read
    always @(posedge clk) begin
        if (we_a) begin
            mem[addr_a[15:2]] <= din_a;
        end
        dout_a <= mem[addr_a[15:2]];
    end

    // Port B: 8-bit Read via Mux
    reg [31:0] dout_b_word;
    reg [1:0]  addr_b_lsb;

    always @(posedge clk) begin
        if (en_b) begin
            dout_b_word <= mem[addr_b[15:2]];
            addr_b_lsb  <= addr_b[1:0];
        end
    end

    always @(*) begin
        case (addr_b_lsb)
            2'd0: dout_b = dout_b_word[7:0];
            2'd1: dout_b = dout_b_word[15:8];
            2'd2: dout_b = dout_b_word[23:16];
            2'd3: dout_b = dout_b_word[31:24];
        endcase
    end

endmodule
