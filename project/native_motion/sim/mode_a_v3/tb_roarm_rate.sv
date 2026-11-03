// Real native T105/T1051 templates on unchanged final RTL. Timing is accelerated
// in the TB config only. D5 stays low and no motion sample is supplied.
`timescale 1ns/1ps
module tb_roarm_rate;
  reg clk=0; always #5 clk=~clk;
  reg rst_n=0;
  reg [11:0] awaddr=0,araddr=0;
  reg awvalid=0,wvalid=0,bready=0,arvalid=0,rready=0;
  reg [31:0] wdata=0;
  wire awready,wready,bvalid,arready,rvalid;
  wire [1:0] bresp,rresp;
  wire [31:0] rdata;
  wire tx; reg sample_valid=0,permit=0; reg[191:0] sample_data; wire sample_ready;
  integer motion_count=0,query_count=0,rx_busy=0; event query_received;
  string expected_cmd[0:8];
  reg [1:0] rx_kind=0;
  reg rx_drive=1;
  wire rx=(rx_kind==1)?tx:((rx_kind==2)?rx_drive:1'b1);
  arm_backend_axi_top #(.HAS_ROARM(1),.HAS_SO101(0),.DEBOUNCE_CYCLES(8),.ROARM_FEEDBACK_EVERY(3)) dut(
    .S_AXI_ACLK(clk),.S_AXI_ARESETN(rst_n),
    .S_AXI_AWADDR(awaddr),.S_AXI_AWVALID(awvalid),.S_AXI_AWREADY(awready),
    .S_AXI_WDATA(wdata),.S_AXI_WSTRB(4'hf),.S_AXI_WVALID(wvalid),.S_AXI_WREADY(wready),
    .S_AXI_BRESP(bresp),.S_AXI_BVALID(bvalid),.S_AXI_BREADY(bready),
    .S_AXI_ARADDR(araddr),.S_AXI_ARVALID(arvalid),.S_AXI_ARREADY(arready),
    .S_AXI_RDATA(rdata),.S_AXI_RRESP(rresp),.S_AXI_RVALID(rvalid),.S_AXI_RREADY(rready),
    .native_snap(1'b0),.s_sample_valid(sample_valid),.s_sample_data(sample_data),.s_sample_ready(sample_ready),
    .arm_uart_tx(tx),.arm_uart_rx(rx),.bus_rx(1'b1),.motion_enable_in(permit));
  reg [31:0] writes[0:2047];
  reg [7:0] expected[0:9];
  integer byte_count=0;
  localparam DIV=868;
  initial begin
    expected[0]="{"; expected[1]="\""; expected[2]="T"; expected[3]="\"";
    expected[4]=":"; expected[5]="1"; expected[6]="0"; expected[7]="5";
    expected[8]="}"; expected[9]=8'h0a;
  end

  initial begin : decode
    integer b; reg[7:0] value; string line;
    line="";
    forever begin
      @(negedge tx);repeat(DIV/2)begin @(posedge clk);#1;end
      if(tx!==0)$fatal(1,"FAIL: UART start");
      for(b=0;b<8;b=b+1)begin repeat(DIV)begin @(posedge clk);#1;end value[b]=tx;end
      repeat(DIV)begin @(posedge clk);#1;end
      if(tx!==1)$fatal(1,"FAIL: UART stop");
      line={line,value};
      if(value==10)begin
        if(line=="{\"T\":105}\n")begin
          if(rx_busy)$fatal(1,"FAIL: overlapping feedback requests at 50Hz");
          query_count=query_count+1; ->query_received;
        end else begin
          if(motion_count>=9 || line!=expected_cmd[motion_count])
            $fatal(1,"FAIL: exact native command %0d got %s",motion_count,line);
          motion_count=motion_count+1;
        end
        line="";
      end
    end
  end
  task wr(input [11:0] addr,input [31:0] data);
    integer g;
    begin
      @(negedge clk);awaddr=addr;wdata=data;awvalid=1;wvalid=1;bready=1;g=0;
      while(!(awready&&wready)) begin @(negedge clk);g=g+1;if(g>100)$fatal(1,"FAIL: write ready");end
      @(negedge clk);awvalid=0;wvalid=0;g=0;
      while(!bvalid) begin @(negedge clk);g=g+1;if(g>100)$fatal(1,"FAIL: write response");end
      if(bresp!==0)$fatal(1,"FAIL: write %03h response %d",addr,bresp);
      @(negedge clk);bready=0;
    end
  endtask
  task rd(input [11:0] addr,output [31:0] data);
    integer g;
    begin
      @(negedge clk);araddr=addr;arvalid=1;rready=1;g=0;
      while(!arready)begin @(negedge clk);g=g+1;if(g>100)$fatal(1,"FAIL: read ready");end
      @(negedge clk);arvalid=0;g=0;
      while(!rvalid)begin @(negedge clk);g=g+1;if(g>100)$fatal(1,"FAIL: read response");end
      data=rdata;if(rresp!==0)$fatal(1,"FAIL: read response");
      @(negedge clk);rready=0;
    end
  endtask
  task configure(input [1:0] kind);
    integer i,guard;reg[31:0] value;
    begin
      rst_n=0;rx_kind=kind;rx_drive=1;byte_count=0;
      repeat(10)@(negedge clk);rst_n=1;repeat(20)@(negedge clk);
      for(i=0;i<writes[0];i=i+1)wr(writes[1+2*i][11:0],writes[2+2*i]);
      wr(12'h000,1);guard=0;rd(12'h008,value);
      while((value&3)!=1)begin rd(12'h008,value);guard=guard+1;if(guard>5000)$fatal(1,"FAIL: commit");end
      rd(12'h00c,value);if(value!=0)$fatal(1,"FAIL: pre-mode fault %h",value);
      wr(12'h004,2);
    end
  endtask
  task feedback;
    string msg;integer i,b;
    begin
      msg="{\"T\":1051,\"b\":0.1,\"s\":0.2,\"e\":1.57,\"t\":0,\"r\":0,\"g\":1.4}\n";
      msg=msg.substr(0,msg.len()-3); while(msg.len()<322)msg={msg," "};msg={msg,"}\n"};
      for(i=0;i<msg.len();i=i+1)begin
        @(negedge clk);rx_drive=0;repeat(DIV)@(negedge clk);
        for(b=0;b<8;b=b+1)begin rx_drive=(msg[i]>>b)&1;repeat(DIV)@(negedge clk);end
        rx_drive=1;repeat(DIV)@(negedge clk);
      end
    end
  endtask

  initial forever begin @query_received;rx_busy=1;feedback();rx_busy=0;end
  reg[31:0] value,ignored,fb;integer guard,baseline_requests;
  initial begin
    $readmemh("config.mem",writes);
    expected_cmd[0]="{\"T\":102,\"base\":0.1000,\"shoulder\":0.2000,\"elbow\":1.5700,\"wrist\":0.0000,\"roll\":0.0000,\"hand\":1.4000,\"spd\":200,\"acc\":10}\n";
    expected_cmd[1]="{\"T\":102,\"base\":0.1010,\"shoulder\":0.2000,\"elbow\":1.5700,\"wrist\":0.0000,\"roll\":0.0000,\"hand\":1.4000,\"spd\":200,\"acc\":10}\n";
    expected_cmd[2]="{\"T\":102,\"base\":0.1020,\"shoulder\":0.2000,\"elbow\":1.5700,\"wrist\":0.0000,\"roll\":0.0000,\"hand\":1.4000,\"spd\":200,\"acc\":10}\n";
    expected_cmd[3]="{\"T\":102,\"base\":0.1030,\"shoulder\":0.2000,\"elbow\":1.5700,\"wrist\":0.0000,\"roll\":0.0000,\"hand\":1.4000,\"spd\":200,\"acc\":10}\n";
    expected_cmd[4]="{\"T\":102,\"base\":0.1040,\"shoulder\":0.2000,\"elbow\":1.5700,\"wrist\":0.0000,\"roll\":0.0000,\"hand\":1.4000,\"spd\":200,\"acc\":10}\n";
    expected_cmd[5]="{\"T\":102,\"base\":0.1050,\"shoulder\":0.2000,\"elbow\":1.5700,\"wrist\":0.0000,\"roll\":0.0000,\"hand\":1.4000,\"spd\":200,\"acc\":10}\n";
    expected_cmd[6]="{\"T\":102,\"base\":0.1060,\"shoulder\":0.2000,\"elbow\":1.5700,\"wrist\":0.0000,\"roll\":0.0000,\"hand\":1.4000,\"spd\":200,\"acc\":10}\n";
    expected_cmd[7]="{\"T\":102,\"base\":0.1070,\"shoulder\":0.2000,\"elbow\":1.5700,\"wrist\":0.0000,\"roll\":0.0000,\"hand\":1.4000,\"spd\":200,\"acc\":10}\n";
    expected_cmd[8]="{\"T\":102,\"base\":0.1080,\"shoulder\":0.2000,\"elbow\":1.5700,\"wrist\":0.0000,\"roll\":0.0000,\"hand\":1.4000,\"spd\":200,\"acc\":10}\n";
    configure(2);
    wait(query_count>=1);wait(rx_busy);wait(!rx_busy);repeat(5000)@(negedge clk);
    rd(12'h304,fb);if(fb==0)$fatal(1,"FAIL: no priming feedback");
    wr(12'h004,0);repeat(100)@(negedge clk);
    permit=1;repeat(100)@(negedge clk);wr(12'h004,32'h3);
    wait(dut.u_core.primed);wr(12'h004,32'h103);
    baseline_requests=query_count;

    sample_data=192'h000166660000000000000000000191ec000033330000199a;sample_valid=1;
    guard=0;while(!sample_ready)begin @(negedge clk);guard=guard+1;if(guard>100000)$fatal(1,"FAIL: backend late at 50Hz");end
    @(negedge clk);sample_valid=0;
    repeat(2_000_000-guard-1)@(negedge clk);


    sample_data=192'h000166660000000000000000000191ec00003333000019db;sample_valid=1;
    guard=0;while(!sample_ready)begin @(negedge clk);guard=guard+1;if(guard>100000)$fatal(1,"FAIL: backend late at 50Hz");end
    @(negedge clk);sample_valid=0;
    repeat(2_000_000-guard-1)@(negedge clk);


    sample_data=192'h000166660000000000000000000191ec0000333300001a1d;sample_valid=1;
    guard=0;while(!sample_ready)begin @(negedge clk);guard=guard+1;if(guard>100000)$fatal(1,"FAIL: backend late at 50Hz");end
    @(negedge clk);sample_valid=0;
    repeat(2_000_000-guard-1)@(negedge clk);


    sample_data=192'h000166660000000000000000000191ec0000333300001a5e;sample_valid=1;
    guard=0;while(!sample_ready)begin @(negedge clk);guard=guard+1;if(guard>100000)$fatal(1,"FAIL: backend late at 50Hz");end
    @(negedge clk);sample_valid=0;
    repeat(2_000_000-guard-1)@(negedge clk);


    sample_data=192'h000166660000000000000000000191ec0000333300001aa0;sample_valid=1;
    guard=0;while(!sample_ready)begin @(negedge clk);guard=guard+1;if(guard>100000)$fatal(1,"FAIL: backend late at 50Hz");end
    @(negedge clk);sample_valid=0;
    repeat(2_000_000-guard-1)@(negedge clk);


    sample_data=192'h000166660000000000000000000191ec0000333300001ae1;sample_valid=1;
    guard=0;while(!sample_ready)begin @(negedge clk);guard=guard+1;if(guard>100000)$fatal(1,"FAIL: backend late at 50Hz");end
    @(negedge clk);sample_valid=0;
    repeat(2_000_000-guard-1)@(negedge clk);


    sample_data=192'h000166660000000000000000000191ec0000333300001b23;sample_valid=1;
    guard=0;while(!sample_ready)begin @(negedge clk);guard=guard+1;if(guard>100000)$fatal(1,"FAIL: backend late at 50Hz");end
    @(negedge clk);sample_valid=0;
    repeat(2_000_000-guard-1)@(negedge clk);


    sample_data=192'h000166660000000000000000000191ec0000333300001b64;sample_valid=1;
    guard=0;while(!sample_ready)begin @(negedge clk);guard=guard+1;if(guard>100000)$fatal(1,"FAIL: backend late at 50Hz");end
    @(negedge clk);sample_valid=0;
    repeat(2_000_000-guard-1)@(negedge clk);


    sample_data=192'h000166660000000000000000000191ec0000333300001ba6;sample_valid=1;
    guard=0;while(!sample_ready)begin @(negedge clk);guard=guard+1;if(guard>100000)$fatal(1,"FAIL: backend late at 50Hz");end
    @(negedge clk);sample_valid=0;
    repeat(2_000_000-guard-1)@(negedge clk);

    repeat(6_000_000)@(negedge clk);
    rd(12'h00c,value);if(value!=0)$fatal(1,"FAIL: parser/watchdog at 50Hz %h",value);
    rd(12'h300,value);if(value!=9 || motion_count!=9)$fatal(1,"FAIL: lost/coalesced motion frame");
    if(query_count-baseline_requests!=3)$fatal(1,"FAIL: expected one feedback request per3 motion frames");
    rd(12'h304,fb);if(fb<4)$fatal(1,"FAIL: feedback not accepted");
    wr(12'h004,0);
    $display("PASS: real115200 nine50Hz native exact commands, three decimated queries, 324B feedback, no overlap/errors; RX=%0d",fb);
    $finish;
  end
  initial begin #800000000;$fatal(1,"FAIL: rate watchdog");end
endmodule
