`timescale 1ns / 1ps

module tb_tmds_encoder;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg [7:0] data = 8'd0;
    reg de = 1'b0;
    reg c0 = 1'b0;
    reg c1 = 1'b0;
    wire [9:0] encoded;
    reg signed [6:0] reference_disparity;
    reg [9:0] expected;
    reg [8:0] qm;
    reg [3:0] ones_data;
    reg [3:0] ones_qm;
    reg use_xnor;
    reg signed [5:0] balance;
    integer i;

    always #5 clk = ~clk;

    tmds_encoder dut (
        .pixel_clk(clk), .rst_n(rst_n), .video_data(data),
        .data_enable(de), .control_0(c0), .control_1(c1),
        .tmds_word(encoded)
    );

    task step;
        input step_de;
        input step_c0;
        input step_c1;
        input [7:0] step_data;
        begin
            de = step_de;
            c0 = step_c0;
            c1 = step_c1;
            data = step_data;

            if (!step_de) begin
                reference_disparity = 0;
                case ({step_c1, step_c0})
                    2'b00: expected = 10'b1101010100;
                    2'b01: expected = 10'b0010101011;
                    2'b10: expected = 10'b0101010100;
                    default: expected = 10'b1010101011;
                endcase
            end else begin
                ones_data = 0;
                for (i = 0; i < 8; i = i + 1)
                    ones_data = ones_data + step_data[i];
                use_xnor = (ones_data > 4) ||
                           ((ones_data == 4) && !step_data[0]);
                qm[0] = step_data[0];
                for (i = 1; i < 8; i = i + 1)
                    qm[i] = use_xnor ? ~(qm[i-1] ^ step_data[i]) :
                                      (qm[i-1] ^ step_data[i]);
                qm[8] = ~use_xnor;
                ones_qm = 0;
                for (i = 0; i < 8; i = i + 1)
                    ones_qm = ones_qm + qm[i];
                balance = $signed({1'b0, ones_qm, 1'b0}) - 6'sd8;

                if ((reference_disparity == 0) || (balance == 0)) begin
                    expected = {~qm[8], qm[8],
                                qm[8] ? qm[7:0] : ~qm[7:0]};
                    reference_disparity = qm[8] ?
                        reference_disparity + balance :
                        reference_disparity - balance;
                end else if (((reference_disparity > 0) && (balance > 0)) ||
                             ((reference_disparity < 0) && (balance < 0))) begin
                    expected = {1'b1, qm[8], ~qm[7:0]};
                    reference_disparity = reference_disparity - balance +
                                          (qm[8] ? 2 : 0);
                end else begin
                    expected = {1'b0, qm[8], qm[7:0]};
                    reference_disparity = reference_disparity + balance -
                                          (qm[8] ? 0 : 2);
                end
            end
            @(posedge clk);
            @(negedge clk);
            if (encoded !== expected)
                $fatal(1, "TMDS mismatch de=%0d c=%0b data=%02x expected=%03x actual=%03x",
                       step_de, {step_c1, step_c0}, step_data,
                       expected, encoded);
        end
    endtask

    initial begin
        reference_disparity = 0;
        repeat (4) @(posedge clk);
        rst_n = 1'b1;
        @(negedge clk);
        step(0, 0, 0, 8'h00);
        step(0, 1, 0, 8'h00);
        step(0, 0, 1, 8'h00);
        step(0, 1, 1, 8'h00);
        step(1, 0, 0, 8'h00);
        step(1, 0, 0, 8'hFF);
        step(1, 0, 0, 8'h01);
        step(1, 0, 0, 8'h7F);
        step(1, 0, 0, 8'h80);
        step(1, 0, 0, 8'h55);
        step(1, 0, 0, 8'hAA);
        step(1, 0, 0, 8'h33);
        step(1, 0, 0, 8'hCC);
        $display("PASS: TMDS control symbols and running-disparity data encoding are bit-exact");
        $finish;
    end

    initial begin
        #10000;
        $fatal(1, "TMDS encoder test timeout");
    end
endmodule
