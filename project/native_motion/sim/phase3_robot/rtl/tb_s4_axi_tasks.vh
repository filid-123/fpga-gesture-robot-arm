// ============================================================================
// Include : tb_s4_axi_tasks.vh
// Purpose : AXI4-Lite master tasks of the S4 testbenches for the four PS-facing
//           windows of phase3_s4_task_top (traj_*, arm_*, plan_*, s4_*).  Every
//           task has a bounded wait and checks the response code.  Window w:
//           0 traj (8-bit address), 1 arm, 2 plan, 3 s4.
// ============================================================================

    localparam [1:0] RESP_OKAY = 2'b00, RESP_SLVERR = 2'b10;
    localparam integer AXI_WAIT_LIMIT = 20000;

    task axi_write;
        input integer w;
        input [11:0]  addr;
        input [31:0]  data;
        input [1:0]   expect_resp;
        integer guard;
        reg     aw_ok, w_ok, b_ok;
        reg [1:0] resp;
        begin
            @(negedge clk);
            case (w)
                0: begin traj_awaddr = addr[7:0]; traj_awvalid = 1'b1; traj_wdata = data; traj_wstrb = 4'hF;
                         traj_wvalid = 1'b1; traj_bready = 1'b1; end
                1: begin arm_awaddr = addr; arm_awvalid = 1'b1; arm_wdata = data; arm_wstrb = 4'hF;
                         arm_wvalid = 1'b1; arm_bready = 1'b1; end
                2: begin plan_awaddr = addr; plan_awvalid = 1'b1; plan_wdata = data; plan_wstrb = 4'hF;
                         plan_wvalid = 1'b1; plan_bready = 1'b1; end
                default: begin s4_awaddr = addr; s4_awvalid = 1'b1; s4_wdata = data; s4_wstrb = 4'hF;
                         s4_wvalid = 1'b1; s4_bready = 1'b1; end
            endcase
            guard = 0; aw_ok = 1'b0; w_ok = 1'b0; b_ok = 1'b0;
            while (!b_ok) begin
                @(posedge clk);
                case (w)
                    0: begin if (traj_awready) aw_ok = 1'b1; if (traj_wready) w_ok = 1'b1;
                             if (traj_bvalid) begin b_ok = 1'b1; resp = traj_bresp; end end
                    1: begin if (arm_awready) aw_ok = 1'b1; if (arm_wready) w_ok = 1'b1;
                             if (arm_bvalid) begin b_ok = 1'b1; resp = arm_bresp; end end
                    2: begin if (plan_awready) aw_ok = 1'b1; if (plan_wready) w_ok = 1'b1;
                             if (plan_bvalid) begin b_ok = 1'b1; resp = plan_bresp; end end
                    default: begin if (s4_awready) aw_ok = 1'b1; if (s4_wready) w_ok = 1'b1;
                             if (s4_bvalid) begin b_ok = 1'b1; resp = s4_bresp; end end
                endcase
                #1;
                if (aw_ok) case (w) 0: traj_awvalid = 1'b0; 1: arm_awvalid = 1'b0; 2: plan_awvalid = 1'b0;
                                    default: s4_awvalid = 1'b0; endcase
                if (w_ok) case (w) 0: traj_wvalid = 1'b0; 1: arm_wvalid = 1'b0; 2: plan_wvalid = 1'b0;
                                   default: s4_wvalid = 1'b0; endcase
                guard = guard + 1;
                if (guard > AXI_WAIT_LIMIT) $fatal(1, "FAIL: AXI write timeout window %0d @0x%03h", w, addr);
            end
            @(negedge clk);
            case (w) 0: traj_bready = 1'b0; 1: arm_bready = 1'b0; 2: plan_bready = 1'b0; default: s4_bready = 1'b0; endcase
            if (resp !== expect_resp)
                $fatal(1, "FAIL: AXI write window %0d @0x%03h data 0x%08h resp %0d expected %0d", w, addr, data,
                       resp, expect_resp);
        end
    endtask

    task axi_read;
        input  integer w;
        input  [11:0] addr;
        output [31:0] data;
        integer guard;
        reg     ar_ok, r_ok;
        reg [1:0] resp;
        begin
            @(negedge clk);
            case (w)
                0: begin traj_araddr = addr[7:0]; traj_arvalid = 1'b1; traj_rready = 1'b1; end
                1: begin arm_araddr = addr; arm_arvalid = 1'b1; arm_rready = 1'b1; end
                2: begin plan_araddr = addr; plan_arvalid = 1'b1; plan_rready = 1'b1; end
                default: begin s4_araddr = addr; s4_arvalid = 1'b1; s4_rready = 1'b1; end
            endcase
            guard = 0; ar_ok = 1'b0; r_ok = 1'b0;
            while (!r_ok) begin
                @(posedge clk);
                case (w)
                    0: begin if (traj_arready) ar_ok = 1'b1; if (traj_rvalid) begin r_ok = 1'b1; data = traj_rdata; resp = traj_rresp; end end
                    1: begin if (arm_arready) ar_ok = 1'b1; if (arm_rvalid) begin r_ok = 1'b1; data = arm_rdata; resp = arm_rresp; end end
                    2: begin if (plan_arready) ar_ok = 1'b1; if (plan_rvalid) begin r_ok = 1'b1; data = plan_rdata; resp = plan_rresp; end end
                    default: begin if (s4_arready) ar_ok = 1'b1; if (s4_rvalid) begin r_ok = 1'b1; data = s4_rdata; resp = s4_rresp; end end
                endcase
                #1;
                if (ar_ok) case (w) 0: traj_arvalid = 1'b0; 1: arm_arvalid = 1'b0; 2: plan_arvalid = 1'b0;
                                    default: s4_arvalid = 1'b0; endcase
                guard = guard + 1;
                if (guard > AXI_WAIT_LIMIT) $fatal(1, "FAIL: AXI read timeout window %0d @0x%03h", w, addr);
            end
            @(negedge clk);
            case (w) 0: traj_rready = 1'b0; 1: arm_rready = 1'b0; 2: plan_rready = 1'b0; default: s4_rready = 1'b0; endcase
            if (resp !== RESP_OKAY) $fatal(1, "FAIL: AXI read window %0d @0x%03h resp %0d", w, addr, resp);
        end
    endtask

    task axi_wait;                       // poll until (reg & mask) == value
        input integer w;
        input [11:0]  addr;
        input [31:0]  mask;
        input [31:0]  value;
        input integer limit_cycles;
        reg   [31:0]  v;
        integer start;
        begin
            start = cycle;
            axi_read(w, addr, v);
            while ((v & mask) !== (value & mask)) begin
                if (cycle - start > limit_cycles)
                    $fatal(1, "FAIL: window %0d reg 0x%03h = 0x%08h, waiting for 0x%08h (mask 0x%08h)", w, addr, v,
                           value, mask);
                repeat (20) @(posedge clk);
                axi_read(w, addr, v);
            end
        end
    endtask
