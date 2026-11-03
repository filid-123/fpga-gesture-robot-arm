// Exact finite map, avoids a signed /5 combinational divider on the raw box path.
`timescale 1ns/1ps
module hand_y_step_map(input wire clk,rst_n,frame_valid,input wire[8:0]x,y,output reg[6:0]target_step);
 reg valid_q;reg[6:0]y_q;
 always @(posedge clk)begin
  if(!rst_n)begin valid_q<=0;y_q<=64;target_step<=32;end
  else begin
   valid_q<=frame_valid && x<128 && y>=16 && y<=111;
   if(frame_valid)y_q<=y[6:0];
   if(valid_q)begin
    if(y_q<=44)target_step<=64;
    else if(y_q>=84)target_step<=0;
    else case(y_q)
     7'd45:target_step<=7'd62;
     7'd46:target_step<=7'd61;
     7'd47:target_step<=7'd59;
     7'd48:target_step<=7'd58;
     7'd49:target_step<=7'd56;
     7'd50:target_step<=7'd54;
     7'd51:target_step<=7'd53;
     7'd52:target_step<=7'd51;
     7'd53:target_step<=7'd50;
     7'd54:target_step<=7'd48;
     7'd55:target_step<=7'd46;
     7'd56:target_step<=7'd45;
     7'd57:target_step<=7'd43;
     7'd58:target_step<=7'd42;
     7'd59:target_step<=7'd40;
     7'd60:target_step<=7'd38;
     7'd61:target_step<=7'd37;
     7'd62:target_step<=7'd35;
     7'd63:target_step<=7'd34;
     7'd64:target_step<=7'd32;
     7'd65:target_step<=7'd30;
     7'd66:target_step<=7'd29;
     7'd67:target_step<=7'd27;
     7'd68:target_step<=7'd26;
     7'd69:target_step<=7'd24;
     7'd70:target_step<=7'd22;
     7'd71:target_step<=7'd21;
     7'd72:target_step<=7'd19;
     7'd73:target_step<=7'd18;
     7'd74:target_step<=7'd16;
     7'd75:target_step<=7'd14;
     7'd76:target_step<=7'd13;
     7'd77:target_step<=7'd11;
     7'd78:target_step<=7'd10;
     7'd79:target_step<=7'd8;
     7'd80:target_step<=7'd6;
     7'd81:target_step<=7'd5;
     7'd82:target_step<=7'd3;
     7'd83:target_step<=7'd2;
     default:target_step<=32;
    endcase
   end
  end
 end
endmodule
