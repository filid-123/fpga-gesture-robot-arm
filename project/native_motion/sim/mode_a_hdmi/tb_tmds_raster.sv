`timescale 1ns/1ps
// Receiver checks the physical serialized stream, not the renderer DE alone.
module tb_tmds_raster;
 reg p=0,p5=0,r=0;
 always #20 p=~p;
 always #4 p5=~p5;
 wire[9:0] x,y;wire av,hs,vs,fs;
 video_timing_640x480 timing(p,r,x,y,av,hs,vs,fs);
 wire[7:0] rr,gg,bb;wire de,ho,vo;wire[13:0]addr;
 reg[31:0] data;
 // Distinct source bytes expose stale/rotated pixels and word-boundary damage.
 always @(posedge p)data<={addr[7:0]+8'd3,addr[7:0]+8'd2,addr[7:0]+8'd1,addr[7:0]};
 mode_a_renderer #(.HD_PREVIEW(1)) renderer(p,r,x,y,av,hs,vs,addr,data,
  1'b1,1'b1,9'd20,9'd24,9'd100,9'd100,3'd4,1'b1,1'b1,1'b1,
  32'h00100005,32'd0,8'd16,8'd5,8'd145,rr,gg,bb,de,ho,vo,8'd0,8'd0);
 wire[9:0]tw[0:2];wire cp,cn;wire[2:0]dp,dn;
 tmds_encoder eb(p,r,bb,de,ho,vo,tw[0]);
 tmds_encoder eg(p,r,gg,de,1'b0,1'b0,tw[1]);
 tmds_encoder er(p,r,rr,de,1'b0,1'b0,tw[2]);
 tmds_serializer_7series serial(p,p5,r,tw[0],tw[1],tw[2],cp,cn,dp,dn);
 reg[26:0] expected[0:1259999];integer wr=0,rd=0;
 always @(posedge p) if(r)begin expected[wr]={de,ho,vo,rr,gg,bb};wr=wr+1;end
 function automatic bit control(input[9:0]w);
  control=(w==10'b1101010100 || w==10'b0010101011 || w==10'b0101010100 || w==10'b1010101011);
 endfunction
 function automatic[7:0]decode(input[9:0]w);
  reg[7:0]m;integer i;
  begin m=w[9]?~w[7:0]:w[7:0];decode[0]=m[0];
   for(i=1;i<8;i=i+1)decode[i]=m[i]^m[i-1]^!w[8];end
 endfunction
 reg[9:0]rx[0:2];integer edgecount=0,phase=-1,words=0,i,offset=-1;
 reg[26:0]actual;reg rxhs,rxvs;integer pixels=0,rows=0,linewords=0,lowhs=0,lastrow=-1;
 reg seenactive=0,oldactive=0,seen_vsync=0;integer f;
 always @(p5)begin
  #0.2;
  if(r)begin
   edgecount=edgecount+1;
   for(i=0;i<3;i=i+1)rx[i]={dp[i],rx[i][9:1]};
   if(phase<0 && edgecount>80 && control(rx[0]) && rx[1]==10'b1101010100 && rx[2]==10'b1101010100)
    phase=edgecount%10;
   if(phase>=0 && edgecount%10==phase)begin
    if(dp!==~dn)$fatal(1,"Differential data");
    actual=0;
    if(control(rx[0]))begin
     case(rx[0])
      10'b1101010100:begin rxhs=0;rxvs=0;end
      10'b0010101011:begin rxhs=1;rxvs=0;end
      10'b0101010100:begin rxhs=0;rxvs=1;end
      10'b1010101011:begin rxhs=1;rxvs=1;end
     endcase
     if(!control(rx[1]) || !control(rx[2]))$fatal(1,"Control lane misalignment");
     actual={1'b0,rxhs,rxvs,24'd0};if(!rxvs)seen_vsync=1;
    end else actual={1'b1,rxhs,rxvs,decode(rx[2]),decode(rx[1]),decode(rx[0])};
    // Acquire the first active pixel using its full RGB and blanking predecessor.
    if(offset<0 && actual[26] && seen_vsync)begin
     // Acquisition is the first active word of the second complete frame.
     for(i=419990;i<wr;i=i+1)if(expected[i][26] && !expected[i-1][26] && expected[i][23:0]===actual[23:0] && offset<0)begin rd=i;offset=i;end
     if(offset<0)$fatal(1,"Cannot align first active pixel");
    end
    if(offset>=0)begin
     if(actual[26]!==expected[rd][26])$fatal(1,"DE word mismatch word%0d rx%h expected%h",rd,actual,expected[rd]);
     if(actual[26])begin
      if(actual[23:0]!==expected[rd][23:0])$fatal(1,"RGB word mismatch word%0d rx%h expected%h",rd,actual,expected[rd]);
      pixels=pixels+1;
      if(!oldactive)begin
       if(seenactive && linewords!=800)$fatal(1,"Line period %0d",linewords);
       if(seenactive && lowhs!=96)$fatal(1,"HS width %0d",lowhs);
       seenactive=1;rows=rows+1;linewords=0;lowhs=0;
      end
      if(rows<=480)$fwrite(f,"%c%c%c",actual[23:16],actual[15:8],actual[7:0]);
     end else begin
      if(actual[25:24]!==expected[rd][25:24])$fatal(1,"Sync word mismatch word%0d rx%h expected%h",rd,actual,expected[rd]);
      if(!rxhs)lowhs=lowhs+1;
     end
     linewords=linewords+1;oldactive=actual[26];rd=rd+1;words=words+1;
     if(words==420000)begin
      $fclose(f);
      if(pixels!=307200 || rows!=480)$fatal(1,"Raster counts %0d %0d",pixels,rows);
      $display("PASS: real serialized TMDS receiver: 420000 words, 307200 exact RGB pixels, 480 rows, HS96/line800, DE and both sync signals aligned");$finish;
     end
    end
   end
  end
 end
 initial begin f=$fopen("receiver.rgb","wb");repeat(9)@(negedge p);r=1;end
 initial begin #40000000;$fatal(1,"Receiver timeout");end
endmodule
