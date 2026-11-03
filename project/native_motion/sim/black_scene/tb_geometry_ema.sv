`timescale 1ns/1ps
module tb_geometry_ema;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,start=0;
    reg [319:0] vectors[0:45];
    reg [31:0] ts=0;
    reg [7:0] peak_cell=0;
    reg signed [31:0] conf=0,dx=0,dy=0,w=0,h=0;
    wire busy,done,det;
    wire [9:0] x,y,side;
    wire [8:0] rx0,ry0,rx1,ry1,ex0,ey0,ex1,ey1;
    integer n,cycles;
    locator_bbox_roi_black #(.USE_EMA(1),.ALPHA_FILE("native_motion/geometry_alpha_q16.mem")) dut(
        .clk(clk),.rst_n(rst_n),.start(start),.timestamp_ms(ts),.cell_index(peak_cell),
        .confidence_i32(conf),.dx_i32(dx),.dy_i32(dy),.width_i32(w),.height_i32(h),
        .busy(busy),.done(done),.detected(det),.roi_x0(x),.roi_y0(y),.roi_side(side),
        .raw_box_x0(rx0),.raw_box_y0(ry0),.raw_box_x1(rx1),.raw_box_y1(ry1),
        .ema_box_x0(ex0),.ema_box_y0(ey0),.ema_box_x1(ex1),.ema_box_y1(ey1));
    initial begin
        $readmemh("native_motion/sim/black_scene/generated/geometry_ema_cases.mem",vectors);
        repeat(4) @(negedge clk);rst_n=1;
        for(n=0;n<46;n=n+1) begin
            conf=vectors[n][31:0];dx=vectors[n][63:32];dy=vectors[n][95:64];
            w=vectors[n][127:96];h=vectors[n][159:128];peak_cell=vectors[n][167:160];ts=vectors[n][230:199];
            start=1;@(negedge clk);start=0;cycles=0;
            while(!done) begin @(negedge clk);cycles=cycles+1;if(cycles>1000)$fatal(1,"FAIL: geometry timeout");end
            if(det!==vectors[n][168] || x!==vectors[n][178:169] || y!==vectors[n][188:179] || side!==vectors[n][198:189])
                $fatal(1,"FAIL: geometry sample=%0d det=%b ROI=%0d/%0d/%0d expected=%0d/%0d/%0d",n,det,x,y,side,vectors[n][178:169],vectors[n][188:179],vectors[n][198:189]);
            $display("PASS: black geometry sample=%0d fixed-point EMA source ROI",n);
            repeat(3) @(negedge clk);
        end
        $display("PASS: GEOMETRY_BLACK 46 timestamp EMA/jump/loss/gap vectors");$finish;
    end
endmodule
