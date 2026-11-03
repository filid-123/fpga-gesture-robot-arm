// Frozen classifier weights: ten 1024x32 ROM banks, one synchronous byte read.
// No run-time model writer. Legacy weight_bram remains available for rollback.
`timescale 1ns/1ps
module cnn_weight_rom_compact #(
 parameter MEM_INIT_FILE="weights_all.mem",parameter integer WORDS=9872,parameter integer READ_PORTS=1
)(input wire clk,input wire we_a,input wire [15:0] addr_a,input wire [31:0] din_a,
 output wire [31:0] dout_a,input wire en_b,input wire [15:0] addr_b,output wire [7:0] dout_b,
 input wire en_c,input wire[15:0]addr_c,output wire[7:0]dout_c);
 localparam BANKS=(WORDS+1023)/1024;
 wire [31:0] bank_data[0:BANKS-1],bank_c[0:BANKS-1];reg[3:0]bank_qc;reg[1:0]byte_qc;reg [3:0] bank_q;reg [1:0] byte_q;
 genvar bank;
 generate for(bank=0;bank<BANKS;bank=bank+1)begin:g_bank
  reg [31:0] image[0:WORDS-1];
  (* rom_style="block" *) reg [31:0] mem[0:1023];reg [31:0] data,data_c;integer i;
  initial begin
   $readmemh(MEM_INIT_FILE,image);
   for(i=0;i<1024;i=i+1)if(bank*1024+i<WORDS)mem[i]=image[bank*1024+i];else mem[i]=0;
  end
  always @(posedge clk)if(en_b && addr_b[15:12]==bank)data<=mem[addr_b[11:2]];
  if(READ_PORTS==2)always @(posedge clk)if(en_c && addr_c[15:12]==bank)data_c<=mem[addr_c[11:2]];
  assign bank_c[bank]=(READ_PORTS==2)?data_c:32'd0;
  assign bank_data[bank]=data;
 end endgenerate
 always @(posedge clk)if(en_b)begin bank_q<=addr_b[15:12];byte_q<=addr_b[1:0];end
 always @(posedge clk)if(READ_PORTS==2 && en_c)begin bank_qc<=addr_c[15:12];byte_qc<=addr_c[1:0];end
 wire[31:0]word_c=(bank_qc<BANKS)?bank_c[bank_qc]:0;
 assign dout_c=(READ_PORTS==2)?(word_c>>(8*byte_qc)):0;
 wire [31:0] word_data=(bank_q<BANKS)?bank_data[bank_q]:0;
 assign dout_b=word_data>>(8*byte_q);
 assign dout_a=0;
 wire _unused=&{1'b0,we_a,addr_a,din_a};
endmodule
