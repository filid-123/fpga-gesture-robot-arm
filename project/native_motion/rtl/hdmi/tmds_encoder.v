// DVI/HDMI TMDS channel encoder. Control symbols are emitted while DE is low;
// the running disparity is reset at every blanking interval.
`timescale 1ns / 1ps

module tmds_encoder (
    input  wire       pixel_clk,
    input  wire       rst_n,
    input  wire [7:0] video_data,
    input  wire       data_enable,
    input  wire       control_0,
    input  wire       control_1,
    output reg  [9:0] tmds_word
);
    reg [8:0] q_m;
    reg [3:0] ones_data;
    reg [3:0] ones_qm;
    reg       use_xnor;
    reg signed [5:0] balance;
    reg signed [6:0] disparity;
    integer i;

    always @(*) begin
        ones_data = 4'd0;
        for (i = 0; i < 8; i = i + 1)
            ones_data = ones_data + video_data[i];

        use_xnor = (ones_data > 4'd4) ||
                   ((ones_data == 4'd4) && !video_data[0]);
        q_m[0] = video_data[0];
        for (i = 1; i < 8; i = i + 1)
            q_m[i] = use_xnor ? ~(q_m[i-1] ^ video_data[i]) :
                                (q_m[i-1] ^ video_data[i]);
        q_m[8] = ~use_xnor;

        ones_qm = 4'd0;
        for (i = 0; i < 8; i = i + 1)
            ones_qm = ones_qm + q_m[i];
        balance = $signed({1'b0, ones_qm, 1'b0}) - 6'sd8;
    end

    always @(posedge pixel_clk) begin
        if (!rst_n) begin
            disparity <= 7'sd0;
            tmds_word <= 10'b1101010100;
        end else if (!data_enable) begin
            disparity <= 7'sd0;
            case ({control_1, control_0})
                2'b00: tmds_word <= 10'b1101010100;
                2'b01: tmds_word <= 10'b0010101011;
                2'b10: tmds_word <= 10'b0101010100;
                default: tmds_word <= 10'b1010101011;
            endcase
        end else if ((disparity == 0) || (balance == 0)) begin
            tmds_word <= {~q_m[8], q_m[8],
                          q_m[8] ? q_m[7:0] : ~q_m[7:0]};
            disparity <= q_m[8] ? (disparity + balance) :
                                  (disparity - balance);
        end else if (((disparity > 0) && (balance > 0)) ||
                     ((disparity < 0) && (balance < 0))) begin
            tmds_word <= {1'b1, q_m[8], ~q_m[7:0]};
            disparity <= disparity - balance + (q_m[8] ? 7'sd2 : 7'sd0);
        end else begin
            tmds_word <= {1'b0, q_m[8], q_m[7:0]};
            disparity <= disparity + balance - (q_m[8] ? 7'sd0 : 7'sd2);
        end
    end
endmodule
