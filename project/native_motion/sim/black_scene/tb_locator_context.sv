`timescale 1ns/1ps
module tb_locator_context;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0,start=0;
    wire in_en, out_we,busy,done,release_unused,stall_unused;
    wire [12:0] in_addr;
    reg [31:0] in_data;
    wire [11:0] out_addr;
    wire [31:0] out_data;
    wire [7:0] rom_en;
    wire [95:0] rom_addr;
    wire [255:0] rom_data;
    wire acc_valid,act_valid;
    wire [2:0] layer;
    wire [17:0] acc_index;
    wire [31:0] acc_data;
    wire [14:0] act_index;
    wire [7:0] act_data;
    reg [31:0] image [0:4095];
    reg [31:0] a0 [0:131071],a1[0:49151],a2[0:16383],a3[0:6143],a4[0:1279],a5[0:2047],a6[0:1023];
    reg [31:0] u0 [0:8191],u1[0:3071],u2[0:1023],u3[0:1535],u5[0:511];
    reg [43:0] stream [0:1279];
    string pkg="model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027";
    string folder;
    integer n,samples=26,first=0,outputs,accs,acts,cycles,total_cycles,ignored_start;
    reg checking=0;
    reg [31:0] expected_acc,expected_act_word;
    reg [7:0] expected_act;
    locator_context_rom_8lane #(.MEM_INIT_FILE("model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027/quantized/locator/model_rom_16k.mem")) rom
        (.clk(clk),.lane_rd_en(rom_en),.lane_rd_addr(rom_addr),.lane_rd_data(rom_data));
    locator_cnn_engine_context_8lane dut (
        .clk(clk),.rst_n(rst_n),.start(start),.input_buffer_id(1'b0),.output_buffer_id(1'b0),.frame_id(32'd42),
        .input_bram_en(in_en),.input_bram_addr(in_addr),.input_bram_data(in_data),
        .output_bram_we(out_we),.output_bram_addr(out_addr),.output_bram_data(out_data),
        .model_lane_rd_en(rom_en),.model_lane_rd_addr(rom_addr),.model_lane_rd_data(rom_data),
        .busy(busy),.done(done),.input_release(release_unused),.stall(stall_unused),
        .debug_acc_valid(acc_valid),.debug_layer(layer),.debug_acc_index(acc_index),.debug_acc_data(acc_data),
        .debug_act_valid(act_valid),.debug_act_index(act_index),.debug_act_data(act_data));
    always @(posedge clk) if(in_en) in_data<=image[in_addr[11:0]];
    always @(negedge clk) if(checking) begin
        cycles=cycles+1;
        if(cycles>10000000) $fatal(1,"FAIL: locator timeout");
        if(acc_valid) begin
            case(layer)
                0: expected_acc=a0[acc_index]; 1: expected_acc=a1[acc_index];
                2: expected_acc=a2[acc_index]; 3: expected_acc=a3[acc_index];
                4: expected_acc=a4[acc_index]; 5: expected_acc=a5[acc_index];
                6: expected_acc=a6[acc_index]; default: $fatal(1,"FAIL: invalid debug layer");
            endcase
            if($isunknown(acc_data) || $isunknown(expected_acc) || acc_data!==expected_acc)
                $fatal(1,"FAIL: sample=%0d layer=%0d acc[%0d] got=%h expected=%h",n,layer,acc_index,acc_data,expected_acc);
            accs=accs+1;
        end
        if(act_valid) begin
            case(layer)
                0:expected_act_word=u0[act_index>>2];1:expected_act_word=u1[act_index>>2];
                2:expected_act_word=u2[act_index>>2];3:expected_act_word=u3[act_index>>2];
                5:expected_act_word=u5[act_index>>2];default:$fatal(1,"FAIL: invalid activation layer");
            endcase
            expected_act=expected_act_word>>(8*(act_index&3));
            if($isunknown(act_data) || $isunknown(expected_act) || act_data!==expected_act)
                $fatal(1,"FAIL: sample=%0d layer=%0d act[%0d] got=%h expected=%h",n,layer,act_index,act_data,expected_act);
            acts=acts+1;
        end
        if(out_we) begin
            if($isunknown({out_addr,out_data}) || $isunknown(stream[outputs]) || outputs>=1280 || {out_addr,out_data}!==stream[outputs])
                $fatal(1,"FAIL: output sample=%0d word=%0d got=%h expected=%h",n,outputs,{out_addr,out_data},stream[outputs]);
            outputs=outputs+1;
        end
        if(done && (out_we || outputs!=1280)) $fatal(1,"FAIL: DONE before final output settled");
    end
    initial begin
        ignored_start=$value$plusargs("SAMPLES=%d",samples);
        ignored_start=$value$plusargs("FIRST=%d",first);
        total_cycles=0;
        repeat(5) @(negedge clk); rst_n=1;
        for(n=first;n<first+samples;n=n+1) begin
            folder=$sformatf("%s/golden_integer/sample_%02d/",pkg,n);
            $readmemh({folder,"locator_input_u8.mem"},image);
            $readmemh({folder,"locator_conv1_acc_i32.mem"},a0);
            $readmemh({folder,"locator_conv2_acc_i32.mem"},a1);
            $readmemh({folder,"locator_conv3_acc_i32.mem"},a2);
            $readmemh({folder,"locator_conv4_acc_i32.mem"},a3);
            $readmemh({folder,"locator_conv5_acc_i32.mem"},a4);
            $readmemh({folder,"locator_g1_acc_i32.mem"},a5);
            $readmemh({folder,"locator_g2_acc_i32.mem"},a6);
            $readmemh({folder,"locator_conv1_pool_u8.mem"},u0);
            $readmemh({folder,"locator_conv2_pool_u8.mem"},u1);
            $readmemh({folder,"locator_conv3_pool_u8.mem"},u2);
            $readmemh({folder,"locator_conv4_u8.mem"},u3);
            $readmemh({folder,"locator_g1_u8.mem"},u5);
            $readmemh({folder,"locator_output_stream_addr12_data32.mem"},stream);
            @(negedge clk); outputs=0;accs=0;acts=0;cycles=0;checking=1;start=1;
            @(negedge clk); start=0;
            repeat(100) @(negedge clk); start=1; // ignored while busy; no new frame accepted
            @(negedge clk); start=0;
            wait(done); @(negedge clk); #1; checking=0;
            if(accs!=207104 || acts!=57344) $fatal(1,"FAIL: layer counts acc=%0d act=%0d",accs,acts);
            total_cycles=total_cycles+cycles;
            $display("PASS: locator sample_%02d all 7 stages, bank residual fusion, 1280 outputs; cycles=%0d",n,cycles);
            repeat(3) @(negedge clk);
        end
        $display("PASS: CONTEXT_LOCATOR samples=%0d cycles_per_frame=%0d",samples,total_cycles/samples);
        $finish;
    end
endmodule
