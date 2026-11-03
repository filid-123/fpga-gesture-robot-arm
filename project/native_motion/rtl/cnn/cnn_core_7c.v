// ============================================================================
// Block Name : cnn_core_7c
// Description: Phase 3 S3 classifier core.  Generated from the unchanged
//              rtl/cnn/cnn_core.v (four-class build) with one change: the
//              dense engine is generic_dense_7c, which also reports the
//              final-layer top1-top2 logit margin (final_margin, 16-bit
//              saturated).  Conv/pool/dense datapaths, descriptor program,
//              BRAM ports and final_class_id timing are the same as cnn_core.
//              The number of classes is the final descriptor's Cout (7).
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (classifier clock)
// Bit-exact reference: model/gesture7/int_reference.py
// Truth boundary: source candidate; supplementary Icarus run only.
// ============================================================================
`timescale 1ns / 1ps

module cnn_core_7c #(parameter integer CONV_LANES=1,parameter integer DENSE_PIPELINED_REQUANT=0,parameter integer FIXED_SHIFT31=0)(
    input  wire        clk,
    input  wire        rst_n,

    // PS Interface
    input  wire        start,
    output wire        busy,
    output wire        done,

    // Descriptor BRAM (Read-only, 32-bit)
    output wire        desc_bram_en,
    output wire [7:0]  desc_bram_addr,
    input  wire [31:0] desc_bram_data,

    // Weight BRAM (Read-only, 8-bit)
    output wire        w_bram_en,
    output wire [15:0] w_bram_addr,
    input  wire [7:0]  w_bram_data,

    output wire w2_bram_en,output wire[15:0]w2_bram_addr,input wire[7:0]w2_bram_data,
    // Input Image BRAM (Read-only, 8-bit)
    output wire        in_bram_en,
    output wire [13:0] in_bram_addr,
    input  wire [7:0]  in_bram_data,

    // Result
    output wire [8:0]  final_class_id,
    output wire [15:0] final_margin
);

    // ==========================================
    // Ping-Pong BRAMs
    // ==========================================
    wire[1:0]layer_act_dst,active_engine;
    wire conv2_dst_en;wire[13:0]conv2_dst_addr,conv2_src_addr;wire[7:0]conv2_dst_data;wire done_conv2;
    wire        ping_we;
    wire [13:0] ping_addr;
    wire [7:0]  ping_wdata;
    wire [13:0] ping_rd_addr;
    wire [7:0]  ping_rdata;

    cnn_act_bram #(.SECOND_WRITE(CONV_LANES==2),.ADDR_BITS(13)) ping_bram_inst (
        .clk(clk),
        .we2_en(CONV_LANES==2 && active_engine==0 && layer_act_dst==0 && conv2_dst_en),.we2_addr(conv2_dst_addr),.we2_data(conv2_dst_data),
        .we_en(ping_we),
        .we_addr(ping_addr),
        .we_data(ping_wdata),
        .rd_en(1'b1),
        .rd_addr(ping_rd_addr),
        .rd_data(ping_rdata)
    );

    wire        pong_we;
    wire [13:0] pong_addr;
    wire [7:0]  pong_wdata;
    wire [13:0] pong_rd_addr;
    wire [7:0]  pong_rdata;

    cnn_act_bram #(.SECOND_WRITE(CONV_LANES==2),.ADDR_BITS(11)) pong_bram_inst (
        .clk(clk),
        .we2_en(CONV_LANES==2 && active_engine==0 && layer_act_dst==1 && conv2_dst_en),.we2_addr(conv2_dst_addr),.we2_data(conv2_dst_data),
        .we_en(pong_we),
        .we_addr(pong_addr),
        .we_data(pong_wdata),
        .rd_en(1'b1),
        .rd_addr(pong_rd_addr),
        .rd_data(pong_rdata)
    );

    // ==========================================
    // Core Signals
    // ==========================================
    wire [15:0] layer_Cin;
    wire [8:0]  layer_Cout;
    wire [5:0]  layer_InH;
    wire [5:0]  layer_InW;
    wire [31:0] layer_weight_offset;
    wire [31:0] layer_bias_offset;
    wire [31:0] layer_quant_M;
    wire [7:0]  layer_quant_shift;
    wire [1:0]  layer_act_src;

    wire        layer_is_final;
    wire [1:0]  layer_type;

    wire        start_conv, start_pool, start_dense;
    wire        done_conv, done_pool, done_dense;


    cnn_core_fsm fsm_inst (
        .clk(clk),
        .rst_n(rst_n),
        .start(start),
        .busy(busy),
        .done(done),
        .desc_bram_en(desc_bram_en),
        .desc_bram_addr(desc_bram_addr),
        .desc_bram_data(desc_bram_data),
        .layer_Cin(layer_Cin),
        .layer_Cout(layer_Cout),
        .layer_InH(layer_InH),
        .layer_InW(layer_InW),
        .layer_weight_offset(layer_weight_offset),
        .layer_bias_offset(layer_bias_offset),
        .layer_quant_M(layer_quant_M),
        .layer_quant_shift(layer_quant_shift),
        .layer_act_src(layer_act_src),
        .layer_act_dst(layer_act_dst),
        .layer_is_final(layer_is_final),
        .layer_type(layer_type),
        .start_conv(start_conv),
        .start_pool(start_pool),
        .start_dense(start_dense),
        .done_conv(done_conv),
        .done_pool(done_pool),
        .done_dense(done_dense),
        .active_engine(active_engine)
    );

    // ==========================================
    // Memory Muxing
    // ==========================================
    wire [13:0] conv_src_addr;
    wire [13:0] pool_src_addr;
    wire [13:0] dense_src_addr;

    wire [13:0] eng_src_addr =
        (active_engine == 0) ? conv_src_addr :
        (active_engine == 1) ? pool_src_addr :
        (active_engine == 2) ? dense_src_addr : 14'd0;

    assign ping_rd_addr = eng_src_addr;
    assign pong_rd_addr = eng_src_addr;
    assign in_bram_addr = eng_src_addr;
    assign in_bram_en = (layer_act_src == 2);

    wire [7:0] eng_src_data =
        (layer_act_src == 0) ? ping_rdata :
        (layer_act_src == 1) ? pong_rdata :
        (layer_act_src == 2) ? in_bram_data : 8'd0;

    wire        conv_dst_en;
    wire [13:0] conv_dst_addr;
    wire [7:0]  conv_dst_data;

    wire        pool_dst_en;
    wire [13:0] pool_dst_addr;
    wire [7:0]  pool_dst_data;

    wire        dense_dst_en;
    wire [13:0] dense_dst_addr;
    wire [7:0]  dense_dst_data;

    wire        eng_dst_en =
        (active_engine == 0) ? conv_dst_en :
        (active_engine == 1) ? pool_dst_en :
        (active_engine == 2) ? dense_dst_en : 1'b0;

    wire [13:0] eng_dst_addr =
        (active_engine == 0) ? conv_dst_addr :
        (active_engine == 1) ? pool_dst_addr :
        (active_engine == 2) ? dense_dst_addr : 14'd0;

    wire [7:0] eng_dst_data =
        (active_engine == 0) ? conv_dst_data :
        (active_engine == 1) ? pool_dst_data :
        (active_engine == 2) ? dense_dst_data : 8'd0;

    assign ping_we    = (layer_act_dst == 0) ? eng_dst_en : 1'b0;
    assign ping_addr  = eng_dst_addr;
    assign ping_wdata = eng_dst_data;

    assign pong_we    = (layer_act_dst == 1) ? eng_dst_en : 1'b0;
    assign pong_addr  = eng_dst_addr;
    assign pong_wdata = eng_dst_data;

    wire        conv_w_bram_en;
    wire [15:0] conv_w_bram_addr;
    wire        dense_w_bram_en;
    wire [15:0] dense_w_bram_addr;

    assign w_bram_en   = (active_engine == 0) ? conv_w_bram_en : (active_engine == 2) ? dense_w_bram_en : 1'b0;
    assign w_bram_addr = (active_engine == 0) ? conv_w_bram_addr : (active_engine == 2) ? dense_w_bram_addr : 16'd0;

    // ==========================================
    // Conv Engine
    // ==========================================
    generic_conv3x3 #(.COUT_STEP(CONV_LANES),.PIPELINED_DOT(FIXED_SHIFT31)) conv_inst (
        .clk(clk),
        .rst_n(rst_n),
        .start(start_conv),
        .busy(),
        .done(done_conv),
        .Cin(layer_Cin),
        .Cout(layer_Cout),
        .InH(layer_InH),
        .InW(layer_InW),
        .weight_offset(layer_weight_offset),
        .bias_offset(layer_bias_offset),
        .quant_M(layer_quant_M),
        .quant_shift(FIXED_SHIFT31!=0?8'd31:layer_quant_shift),
        .w_bram_en(conv_w_bram_en),
        .w_bram_addr(conv_w_bram_addr),
        .w_bram_data(w_bram_data),
        .src_bram_en(),
        .src_bram_addr(conv_src_addr),
        .src_bram_data(eng_src_data),
        .dst_bram_en(conv_dst_en),
        .dst_bram_addr(conv_dst_addr),
        .dst_bram_data(conv_dst_data)
    );

    generate if(CONV_LANES==2)begin:g_parallel
     generic_conv3x3 #(.COUT_START(1),.COUT_STEP(2),.PIPELINED_DOT(FIXED_SHIFT31)) conv_lane1(
      .clk(clk),.rst_n(rst_n),.start(start_conv),.busy(),.done(done_conv2),
      .Cin(layer_Cin),.Cout(layer_Cout),.InH(layer_InH),.InW(layer_InW),
      .weight_offset(layer_weight_offset),.bias_offset(layer_bias_offset),.quant_M(layer_quant_M),.quant_shift(FIXED_SHIFT31!=0?8'd31:layer_quant_shift),
      .w_bram_en(w2_bram_en),.w_bram_addr(w2_bram_addr),.w_bram_data(w2_bram_data),
      .src_bram_en(),.src_bram_addr(conv2_src_addr),.src_bram_data(eng_src_data),
      .dst_bram_en(conv2_dst_en),.dst_bram_addr(conv2_dst_addr),.dst_bram_data(conv2_dst_data));
     // synthesis translate_off
     always @(posedge clk)if(rst_n && active_engine==0 && busy)begin
      if(conv2_src_addr!==conv_src_addr)$fatal(1,"Parallel source addresses diverged");
      if(done_conv2!==done_conv)$fatal(1,"Parallel completion diverged");
     end
     // synthesis translate_on
    end else begin:g_serial
     assign w2_bram_en=0;assign w2_bram_addr=0;assign conv2_dst_en=0;assign conv2_dst_addr=0;assign conv2_dst_data=0;assign conv2_src_addr=0;assign done_conv2=0;
    end endgenerate

    // ==========================================
    // Pool Engine
    // ==========================================
    generic_maxpool2x2 #(.FIXED_GEOMETRY(FIXED_SHIFT31)) pool_inst (
        .clk(clk),
        .rst_n(rst_n),
        .start(start_pool),
        .busy(),
        .done(done_pool),
        .Cin(layer_Cin),
        .InH(layer_InH),
        .InW(layer_InW),
        .src_bram_en(),
        .src_bram_addr(pool_src_addr),
        .src_bram_data(eng_src_data),
        .dst_bram_en(pool_dst_en),
        .dst_bram_addr(pool_dst_addr),
        .dst_bram_data(pool_dst_data)
    );

    // ==========================================
    // Dense Engine
    // ==========================================
    wire logits_valid;
    wire [8:0] internal_class_id;
    wire [15:0] internal_margin;

    generic_dense_7c #(.PIPELINED_REQUANT(DENSE_PIPELINED_REQUANT)) dense_inst (
        .clk(clk),
        .rst_n(rst_n),
        .start(start_dense),
        .busy(),
        .done(done_dense),
        .Cin(layer_Cin),
        .Cout(layer_Cout),
        .weight_offset(layer_weight_offset),
        .bias_offset(layer_bias_offset),
        .quant_M(layer_quant_M),
        .quant_shift(layer_quant_shift),
        .is_final_layer(layer_is_final),
        .w_bram_en(dense_w_bram_en),
        .w_bram_addr(dense_w_bram_addr),
        .w_bram_data(w_bram_data),
        .src_bram_en(),
        .src_bram_addr(dense_src_addr),
        .src_bram_data(eng_src_data),
        .dst_bram_en(dense_dst_en),
        .dst_bram_addr(dense_dst_addr),
        .dst_bram_data(dense_dst_data),
        .final_class_id(internal_class_id),
        .final_margin(internal_margin),
        .logits_valid(logits_valid)
    );

    // ==========================================
    // Latch Final Class ID
    // ==========================================
    reg [8:0]  latched_class_id;
    reg [15:0] latched_margin;
    always @(posedge clk) begin
        if (!rst_n) begin
            latched_class_id <= 0;
            latched_margin   <= 0;
        end else if (logits_valid) begin
            latched_class_id <= internal_class_id;
            latched_margin   <= internal_margin;
        end
    end

    assign final_class_id = latched_class_id;
    assign final_margin   = latched_margin;

endmodule
