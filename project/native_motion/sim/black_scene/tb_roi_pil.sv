`timescale 1ns/1ps
module tb_roi_pil;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,start=0;
    reg [9:0] x0=0,y0=0,side=1;
    reg [31:0] tag=42;
    wire busy,done,error,src_en,we;
    wire [16:0] src_addr;
    reg [31:0] src_data,src_stage;
    reg src_en_q=0;
    wire [7:0] addr;
    wire [31:0] data,completed_tag,completed_frame;
    reg [31:0] source[0:76799],expected[0:255],configs[0:15];
    integer n,count,cycles,total_cycles;
    reg checking=0;
    string root="native_motion/sim/black_scene/generated/";
    roi_pil_bilinear_32x32 dut(.clk(clk),.rst_n(rst_n),.start(start),.desc_x0(x0),.desc_y0(y0),
        .desc_side(side),.desc_tag(tag),.frame_valid(1'b1),.frame_id(32'd42),
        .busy(busy),.done_pulse(done),.error_pulse(error),.completed_tag(completed_tag),
        .completed_source_frame_id(completed_frame),.source_rd_en(src_en),.source_word_addr(src_addr),
        .source_data(src_data),.roi_word_we(we),.roi_word_addr(addr),.roi_word_data(data));
    always @(posedge clk) begin
        src_en_q<=src_en;
        if(src_en) begin
            if(src_addr>=76800) $fatal(1,"FAIL: source address out of range");
            src_stage<=source[src_addr];
        end
        if(src_en_q)src_data<=src_stage;
    end
    always @(negedge clk) if(checking) begin
        cycles=cycles+1;
        if(cycles>3000000) $fatal(1,"FAIL: ROI timeout");
        if(error) $fatal(1,"FAIL: unexpected ROI error");
        if(we) begin
            if(count>=256 || addr!==count[7:0] || data!==expected[count])
                $fatal(1,"FAIL: ROI case=%0d word=%0d got=%h expected=%h",n,count,data,expected[count]);
            count=count+1;
        end
        if(done && (we || count!=256 || completed_tag!=42 || completed_frame!=42))
            $fatal(1,"FAIL: ROI DONE/frame contract");
    end
    initial begin
        $readmemh({root,"roi_cases.mem"},configs);
        total_cycles=0;repeat(4) @(negedge clk);rst_n=1;
        // Invalid geometry and mismatched frame must not read source or emit ROI.
        tag=43;start=1;@(negedge clk);start=0;
        if(!error || busy || src_en || we) $fatal(1,"FAIL: mismatched frame accepted");
        tag=42;side=481;start=1;@(negedge clk);start=0;
        if(!error || busy || src_en || we) $fatal(1,"FAIL: oversized ROI accepted");
        for(n=0;n<16;n=n+1) begin
            $readmemh($sformatf("%sroi_case_%02d_source.mem",root,n),source);
            $readmemh($sformatf("%sroi_case_%02d_expected.mem",root,n),expected);
            x0=configs[n][9:0];y0=configs[n][19:10];side=configs[n][29:20];
            @(negedge clk);count=0;cycles=0;checking=1;start=1;
            @(negedge clk);start=0;repeat(20) @(negedge clk);start=1;
            @(negedge clk);start=0; // busy ignores a second start
            wait(done);@(negedge clk);#1;checking=0;
            total_cycles=total_cycles+cycles;
            $display("PASS: PIL ROI case=%0d side=%0d 1024 exact bytes cycles=%0d",n,side,cycles);
            repeat(3) @(negedge clk);
        end
        // Reset in coefficient generation invalidates the job without publishing.
        side=480;start=1;@(negedge clk);start=0;repeat(100) @(negedge clk);
        rst_n=0;@(negedge clk);rst_n=1;@(negedge clk);
        if(busy || done || we) $fatal(1,"FAIL: reset left a valid ROI job");
        $display("PASS: ROI_PIL all 16 cases, frame binding, invalid geometry, busy, reset");$finish;
    end
endmodule
