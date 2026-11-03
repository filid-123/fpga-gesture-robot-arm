`timescale 1ns/1ps
module tb_retained_frame;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,pv=0,sof=0,release_frame=0,ren=0;
    reg [9:0] px=0,py=0;reg [7:0] pixel=0;reg [16:0] raddr=0;
    wire ready,valid,published,lwe;wire [31:0] id,ts,now,ld,rd,drops,errors;
    wire [12:0] la;
    integer x,y,j,loc_count,offset,watchdog=0;
    reg checking=0;
    retained_gray_frame #(.CYCLES_PER_MS(100)) dut(.clk(clk),.rst_n(rst_n),.pixel_valid(pv),
        .pixel_ready(ready),.pixel_data(pixel),.pixel_x(px),.pixel_y(py),.pixel_sof(sof),
        .release_frame(release_frame),.frame_valid(valid),.frame_id(id),.published(published),
        .frame_timestamp_ms(ts),.now_ms(now),.loc_we(lwe),.loc_word_addr(la),.loc_data(ld),
        .source_rd_en(ren),.source_word_addr(raddr),.source_data(rd),
        .frame_drop_count(drops),.format_error_count(errors));
    function [7:0] gray(input integer a,input integer b,input integer off);
        begin gray=(a*13+b*7+off)&255;end
    endfunction
    function [31:0] source_word(input integer index,input integer off);
        integer k,row,col;begin row=index/160;col=(index%160)*4;source_word=0;
            for(k=0;k<4;k=k+1) source_word[k*8+:8]=gray(col+k,row,off);end
    endfunction
    function [31:0] locator_word(input integer index,input integer off);
        integer k,row,col;begin row=index/32;col=(index%32)*4;locator_word=0;
            if(row>=16 && row<112)for(k=0;k<4;k=k+1)locator_word[k*8+:8]=gray((col+k)*5,(row-16)*5,off);end
    endfunction
    task token(input integer a,input integer b,input integer off,input bit first);
        begin @(negedge clk);pv=1;px=a;py=b;pixel=gray(a,b,off);sof=first;#1;
            while(!ready) @(negedge clk);
            @(posedge clk);#1;@(negedge clk);pv=0;sof=0;end
    endtask
    task frame(input integer off);
        begin offset=off;loc_count=0;checking=1;
            for(y=0;y<480;y=y+1)for(x=0;x<640;x=x+1)token(x,y,off,x==0&&y==0);
            wait(valid);@(negedge clk);#1;checking=0;
            if(loc_count!=4096)$fatal(1,"FAIL: locator frame word count=%0d",loc_count);
            ren=1;
            for(j=0;j<76800;j=j+1)begin
                raddr=j;repeat(2)@(posedge clk);#1;@(negedge clk);
                if(rd!==source_word(j,off))$fatal(1,"FAIL: full source word=%0d got=%h",j,rd);
            end
            ren=0;$display("PASS: retained VGA offset=%0d full 307200 bytes and 4096 letterbox words",off);
        end
    endtask
    always @(negedge clk) begin
        watchdog=watchdog+1;if(watchdog>4000000)$fatal(1,"FAIL: frame watchdog");
        if(checking && lwe)begin
            if(la!==loc_count[12:0] || ld!==locator_word(loc_count,offset))
                $fatal(1,"FAIL: letterbox word=%0d addr=%0d got=%h expected=%h",loc_count,la,ld,locator_word(loc_count,offset));
            loc_count=loc_count+1;
        end
    end
    initial begin
        repeat(4) @(negedge clk);rst_n=1;frame(0);
        if(id!=1 || errors!=0)$fatal(1,"FAIL: publication identity");
        token(0,0,99,1);token(1,0,99,0);repeat(4)@(negedge clk);
        if(drops!=1 || !valid || lwe || dut.full_we)$fatal(1,"FAIL: retained frame overwrite/drop");
        release_frame=1;@(negedge clk);release_frame=0;
        token(12,0,99,0);if(valid)$fatal(1,"FAIL: partial frame published");
        frame(61);if(id!=2)$fatal(1,"FAIL: second frame identity");
        release_frame=1;@(negedge clk);release_frame=0;
        token(0,0,0,1);token(2,0,0,0);repeat(3)@(negedge clk);
        if(valid || errors!=1)$fatal(1,"FAIL: malformed frame accepted");
        rst_n=0;@(negedge clk);rst_n=1;repeat(2)@(negedge clk);
        if(valid || published)$fatal(1,"FAIL: reset published stale RAM");
        $display("PASS: RETAINED_FRAME ownership/drop/release/identity/format/reset");$finish;
    end
endmodule
