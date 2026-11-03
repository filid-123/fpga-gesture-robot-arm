`timescale 1ns/1ps
// Independent frozen baseline module is extracted from fd397f9 by the runner.
// Compare every raw accumulator write, every activation, and cycle/handshake.
module tb_conv_acc_bram;
    reg clk=0; always #5 clk=~clk;
    reg rst=0,start=0;
    reg [15:0] ci=1;
    reg [8:0] co=2;
    reg [5:0] side=32;
    wire busy_a,busy_b,done_a,done_b,we_a,we_b,ie_a,ie_b,oe_a,oe_b;
    wire [15:0] wa_a,wa_b;
    wire [13:0] ia_a,ia_b,oa_a,oa_b;
    wire [7:0] od_a,od_b;
    reg [7:0] wd_a,wd_b,id_a,id_b;
    reg [7:0] weight[0:65535],image[0:16383];
    integer k,n,cycles,writes,raw_writes;
    reg checking=0;
    baseline_generic_conv3x3 #(.PIPELINED_DOT(1)) reference_dut(
        .clk(clk),.rst_n(rst),.start(start),.busy(busy_a),.done(done_a),
        .Cin(ci),.Cout(co),.InH(side),.InW(side),.weight_offset(32'd0),.bias_offset(32'd50000),
        .quant_M(32'h7fffffff),.quant_shift(8'd31),
        .w_bram_en(we_a),.w_bram_addr(wa_a),.w_bram_data(wd_a),
        .src_bram_en(ie_a),.src_bram_addr(ia_a),.src_bram_data(id_a),
        .dst_bram_en(oe_a),.dst_bram_addr(oa_a),.dst_bram_data(od_a));
    generic_conv3x3 #(.PIPELINED_DOT(1)) dut(
        .clk(clk),.rst_n(rst),.start(start),.busy(busy_b),.done(done_b),
        .Cin(ci),.Cout(co),.InH(side),.InW(side),.weight_offset(32'd0),.bias_offset(32'd50000),
        .quant_M(32'h7fffffff),.quant_shift(8'd31),
        .w_bram_en(we_b),.w_bram_addr(wa_b),.w_bram_data(wd_b),
        .src_bram_en(ie_b),.src_bram_addr(ia_b),.src_bram_data(id_b),
        .dst_bram_en(oe_b),.dst_bram_addr(oa_b),.dst_bram_data(od_b));
    always @(posedge clk) begin
        if(we_a)wd_a<=weight[wa_a]; if(we_b)wd_b<=weight[wa_b];
        if(ie_a)id_a<=image[ia_a]; if(ie_b)id_b<=image[ia_b];
    end
    always @(negedge clk) if(checking && rst) begin
        cycles=cycles+1;
        if(cycles>1000000)$fatal(1,"FAIL: accumulator timeout");
        if({busy_a,done_a,we_a,ie_a,oe_a} !== {busy_b,done_b,we_b,ie_b,oe_b})
            $fatal(1,"FAIL: cycle/control mismatch cycle=%0d",cycles);
        if(we_a && wa_a!==wa_b)$fatal(1,"FAIL: weight address");
        if(ie_a && ia_a!==ia_b)$fatal(1,"FAIL: activation address");
        if(reference_dut.acc_wr_en !== dut.acc_wr_en)$fatal(1,"FAIL: accumulator write enable");
        if(dut.acc_wr_en)begin
            if($isunknown(dut.acc_wr_data) || dut.acc_wr_addr!==reference_dut.acc_wr_addr ||
               dut.acc_wr_data!==reference_dut.acc_wr_data)$fatal(1,"FAIL: raw accumulator mismatch");
            raw_writes=raw_writes+1;
        end
        if(oe_a)begin
            if($isunknown(od_b) || {oa_a,od_a}!=={oa_b,od_b})$fatal(1,"FAIL: requant output");
            writes=writes+1;
        end
    end
    initial begin
        for(k=0;k<65536;k=k+1)weight[k]=(k*73+129)^(k>>3);
        for(k=0;k<16384;k=k+1)image[k]=(k%5==0)?0:(k%7==0)?255:((k*29)^(k>>2));
        for(k=0;k<8;k=k+1)weight[50000+k]=(k%4==3)?8'hff:(k*61);
        repeat(4)@(negedge clk);rst=1;
        // Abort a partially computed layer, then start each shape without
        // resetting RAM contents. Channel zero must replace stale values.
        start=1;@(negedge clk);start=0;repeat(97)@(negedge clk);
        rst=0;repeat(3)@(negedge clk);rst=1;
        for(n=0;n<3;n=n+1)begin
            ci=(n==0)?1:(n==1)?8:16;side=(n==0)?32:(n==1)?16:8;
            cycles=0;writes=0;raw_writes=0;
            @(negedge clk);checking=1;start=1;@(negedge clk);start=0;
            repeat(50)@(negedge clk);start=1;@(negedge clk);start=0;
            wait(done_b);@(negedge clk);#1;checking=0;
            if(writes!=side*side*co || raw_writes!=side*side*co*ci)
                $fatal(1,"FAIL: accumulator counts");
            $display("PASS: ACC_BRAM shape=%0d Cin=%0d raw=%0d outputs=%0d cycles=%0d exact baseline",side,ci,raw_writes,writes,cycles);
            repeat(4)@(negedge clk);
        end
        $display("PASS: ACC_BRAM abort/restart, three shapes, signed weights, exact cycle contract");$finish;
    end
endmodule
