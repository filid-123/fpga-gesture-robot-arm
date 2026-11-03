`timescale 1ns / 1ps

module generic_maxpool2x2 #(parameter integer FIXED_GEOMETRY=0) (
    input  wire        clk,
    input  wire        rst_n,

    // Control
    input  wire        start,
    output reg         busy,
    output reg         done,

    // Layer Parameters
    input  wire [15:0] Cin,
    input  wire [5:0]  InH,
    input  wire [5:0]  InW,

    // Activation Source BRAM (Read-only, 8-bit)
    output reg         src_bram_en,
    output reg  [13:0] src_bram_addr,
    input  wire [7:0]  src_bram_data,

    // Activation Dest BRAM (Write-only, 8-bit)
    output reg         dst_bram_en,
    output reg  [13:0] dst_bram_addr,
    output reg  [7:0]  dst_bram_data
);

    localparam S_IDLE           = 0;
    localparam S_LOAD_ROW0      = 1;
    localparam S_LOAD_ROW0_LAT  = 2;
    localparam S_LOAD_ROW0_WAIT = 3;
    localparam S_LOAD_ROW1      = 4;
    localparam S_LOAD_ROW1_LAT  = 5;
    localparam S_LOAD_ROW1_WAIT = 6;
    localparam S_COMPUTE        = 7;
    localparam S_NEXT_CH        = 8;
    localparam S_DONE           = 9;

    reg [3:0] state;

    reg [15:0] cur_c;
    reg [5:0] out_y, out_x;
    reg [5:0] load_col;

    reg [7:0] rbuf0 [0:31];
    reg [7:0] rbuf1 [0:31];

    wire [5:0] out_h = InH >> 1;
    wire [5:0] out_w = InW >> 1;

    wire [7:0] p0 = rbuf0[{out_x, 1'b0}];
    wire [7:0] p1 = rbuf0[{out_x, 1'b0} + 1];
    wire [7:0] p2 = rbuf1[{out_x, 1'b0}];
    wire [7:0] p3 = rbuf1[{out_x, 1'b0} + 1];

    wire [7:0] max01 = (p0 > p1) ? p0 : p1;
    wire [7:0] max23 = (p2 > p3) ? p2 : p3;
    wire [7:0] pool_max = (max01 > max23) ? max01 : max23;
    function [13:0] map_address;
        input [15:0] channel;input [6:0] row;input [5:0] col;
        begin if(FIXED_GEOMETRY!=0)begin
            case(InW)
                32:map_address=(channel<<10)+(row<<5)+col;
                16:map_address=(channel<<8)+(row<<4)+col;
                8:map_address=(channel<<6)+(row<<3)+col;
                default:map_address=0;
            endcase
        end else map_address=channel*(InH*InW)+row*InW+col;end
    endfunction
    function [13:0] output_address;
        input [15:0] channel;input [5:0] row,col;
        begin if(FIXED_GEOMETRY!=0)begin
            case(InW)
                32:output_address=(channel<<8)+(row<<4)+col;
                16:output_address=(channel<<6)+(row<<3)+col;
                8:output_address=(channel<<4)+(row<<2)+col;
                default:output_address=0;
            endcase
        end else output_address=channel*(out_h*out_w)+row*out_w+col;end
    endfunction

    always @(posedge clk) begin
        if (!rst_n) begin
            state <= S_IDLE;
            busy <= 0;
            done <= 0;
            src_bram_en <= 0;
            dst_bram_en <= 0;
        end else begin
            src_bram_en <= 0;
            dst_bram_en <= 0;

            case (state)
                S_IDLE: begin
                    done <= 0;
                    if (start) begin
                        busy <= 1;
                        cur_c <= 0;
                        out_y <= 0;
                        out_x <= 0;
                        load_col <= 0;
                        state <= S_LOAD_ROW0;
                    end
                end

                S_LOAD_ROW0: begin
                    src_bram_en <= 1;
                    src_bram_addr <= map_address(cur_c,{out_y,1'b0},load_col);
                    state <= S_LOAD_ROW0_LAT;
                end

                S_LOAD_ROW0_LAT: begin
                    src_bram_en <= 1;
                    src_bram_addr <= map_address(cur_c,{out_y,1'b0},load_col) + 1;
                    state <= S_LOAD_ROW0_WAIT;
                end

                S_LOAD_ROW0_WAIT: begin
                    rbuf0[load_col] <= src_bram_data;
                    if (load_col == InW - 1) begin
                        load_col <= 0;
                        state <= S_LOAD_ROW1;
                    end else begin
                        load_col <= load_col + 1;
                        src_bram_en <= 1;
                        src_bram_addr <= map_address(cur_c,{out_y,1'b0},load_col) + 2;
                        state <= S_LOAD_ROW0_WAIT;
                    end
                end

                S_LOAD_ROW1: begin
                    src_bram_en <= 1;
                    src_bram_addr <= map_address(cur_c,{out_y,1'b1},load_col);
                    state <= S_LOAD_ROW1_LAT;
                end

                S_LOAD_ROW1_LAT: begin
                    src_bram_en <= 1;
                    src_bram_addr <= map_address(cur_c,{out_y,1'b1},load_col) + 1;
                    state <= S_LOAD_ROW1_WAIT;
                end

                S_LOAD_ROW1_WAIT: begin
                    rbuf1[load_col] <= src_bram_data;
                    if (load_col == InW - 1) begin
                        load_col <= 0;
                        state <= S_COMPUTE;
                    end else begin
                        load_col <= load_col + 1;
                        src_bram_en <= 1;
                        src_bram_addr <= map_address(cur_c,{out_y,1'b1},load_col) + 2;
                        state <= S_LOAD_ROW1_WAIT;
                    end
                end

                S_COMPUTE: begin
                    dst_bram_en <= 1;
                    dst_bram_addr <= output_address(cur_c,out_y,out_x);
                    dst_bram_data <= pool_max;

                    if (out_x == out_w - 1) begin
                        out_x <= 0;
                        if (out_y == out_h - 1) begin
                            state <= S_NEXT_CH;
                        end else begin
                            out_y <= out_y + 1;
                            state <= S_LOAD_ROW0;
                        end
                    end else begin
                        out_x <= out_x + 1;
                    end
                end

                S_NEXT_CH: begin
                    if (cur_c == Cin - 1) begin
                        state <= S_DONE;
                    end else begin
                        cur_c <= cur_c + 1;
                        out_y <= 0;
                        out_x <= 0;
                        state <= S_LOAD_ROW0;
                    end
                end

                S_DONE: begin
                    busy <= 0;
                    done <= 1;
                    state <= S_IDLE;
                end
                
                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
