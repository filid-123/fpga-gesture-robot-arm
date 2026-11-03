`timescale 1ns/1ps
module tb_classifier_real;
    reg clk=0;always #5 clk=~clk; // intended common 100 MHz production clock
    reg rst_n=0,start=0;
    wire busy,done,de,we,ie;wire [7:0] da;wire [15:0] wa;wire [13:0] ia;
    reg [31:0] dd;reg [7:0] wd,idata;
    wire [8:0] result;wire [15:0] margin;
    reg [31:0] descriptors[0:63],weights[0:9871],image[0:255];
    reg [31:0] a0[0:2047],a1[0:511],a2[0:1023],a3[0:255],a4[0:511],a5[0:127],a6[0:15],logits[0:5];
    reg [31:0] expected_word;reg [7:0] expected_byte;
    reg [13:0] write_addr;reg [7:0] write_data;
    reg signed [31:0] best,second;
    reg signed [32:0] wide_margin;
    reg [8:0] expected_class;reg [15:0] expected_margin;
    reg checking=0;integer n,k,writes,logit_count,cycles;
    string pkg="model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027";string folder;
    cnn_core_7c #(.DENSE_PIPELINED_REQUANT(1),.FIXED_SHIFT31(1)) dut(.clk(clk),.rst_n(rst_n),.start(start),.busy(busy),.done(done),
        .desc_bram_en(de),.desc_bram_addr(da),.desc_bram_data(dd),
        .w_bram_en(we),.w_bram_addr(wa),.w_bram_data(wd),
        .in_bram_en(ie),.in_bram_addr(ia),.in_bram_data(idata),.final_class_id(result),.final_margin(margin));
    always @(posedge clk) begin
        if(de)dd<=descriptors[da];if(we)wd<=weights[wa>>2]>>(8*wa[1:0]);
        if(ie)idata<=image[ia>>2]>>(8*ia[1:0]);
    end
    always @(negedge clk)if(checking)begin
        cycles=cycles+1;if(cycles>12000000)$fatal(1,"FAIL: classifier timeout");
        if(dut.ping_we || dut.pong_we)begin
            write_addr=dut.ping_we?dut.ping_addr:dut.pong_addr;
            write_data=dut.ping_we?dut.ping_wdata:dut.pong_wdata;
            case(dut.fsm_inst.layer_idx)
                0:expected_word=a0[write_addr>>2];1:expected_word=a1[write_addr>>2];
                2:expected_word=a2[write_addr>>2];3:expected_word=a3[write_addr>>2];
                4:expected_word=a4[write_addr>>2];5:expected_word=a5[write_addr>>2];
                6:expected_word=a6[write_addr>>2];default:$fatal(1,"FAIL: unexpected classifier write layer");
            endcase
            expected_byte=expected_word>>(8*write_addr[1:0]);
            if($isunknown(write_data) || $isunknown(expected_byte) || write_data!==expected_byte)$fatal(1,"FAIL: classifier sample=%0d layer=%0d addr=%0d got=%h expected=%h",n,dut.fsm_inst.layer_idx,write_addr,write_data,expected_byte);
            writes=writes+1;
        end
        if(dut.dense_inst.state==7 && dut.layer_is_final)begin
            if($isunknown(dut.dense_inst.acc) || $isunknown(logits[logit_count]) || dut.dense_inst.cur_co!=logit_count || dut.dense_inst.acc!==logits[logit_count])
                $fatal(1,"FAIL: final six-class signed logit sample=%0d index=%0d got=%h expected=%h",n,logit_count,dut.dense_inst.acc,logits[logit_count]);
            logit_count=logit_count+1;
        end
    end
    initial begin
        $readmemh({pkg,"/quantized/classifier/layer_descriptors.mem"},descriptors);
        $readmemh({pkg,"/quantized/classifier/weights_all.mem"},weights);
        repeat(4)@(negedge clk);rst_n=1;
        for(n=0;n<26;n=n+1)begin
            folder=$sformatf("%s/golden_integer/sample_%02d/",pkg,n);
            $readmemh({folder,"classifier_input_u8.mem"},image);
            $readmemh({folder,"classifier_conv1_u8.mem"},a0);$readmemh({folder,"classifier_conv1_pool_u8.mem"},a1);
            $readmemh({folder,"classifier_conv2_u8.mem"},a2);$readmemh({folder,"classifier_conv2_pool_u8.mem"},a3);
            $readmemh({folder,"classifier_conv3_u8.mem"},a4);$readmemh({folder,"classifier_conv3_pool_u8.mem"},a5);
            $readmemh({folder,"classifier_fc1_u8.mem"},a6);$readmemh({folder,"classifier_fc2_logits_i32.mem"},logits);
            best=32'sh80000000;second=32'sh80000000;expected_class=0;
            for(k=0;k<6;k=k+1)begin
                if($signed(logits[k])>best)begin second=best;best=logits[k];expected_class=k;end
                else if($signed(logits[k])>second)second=logits[k];
            end
            wide_margin={best[31],best}-{second[31],second};expected_margin=(wide_margin>65535)?65535:wide_margin[15:0];
            @(negedge clk);cycles=0;writes=0;logit_count=0;checking=1;start=1;
            @(negedge clk);start=0;repeat(100)@(negedge clk);start=1;
            @(negedge clk);start=0;wait(done);@(negedge clk);#1;checking=0;
            if(writes!=17984 || logit_count!=6 || result!==expected_class || margin!==expected_margin)
                $fatal(1,"FAIL: classifier completion counts/result/margin");
            $display("PASS: real classifier sample=%0d all 8 stages, six logits, margin; cycles=%0d",n,cycles);
            repeat(4)@(negedge clk);
        end
        $display("PASS: CLASSIFIER_REAL all 26 frozen INT8 samples, trimmed RAM and 100 MHz cycle contract");$finish;
    end
endmodule
