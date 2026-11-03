// ============================================================================
// Block Name : s4_task_regs
// Description: AXI4-Lite register window of the Phase 3 S4 task controller
//              (ABI 0x0000_3401, proposed 0x43C5_0000 / 4 KiB; register map in
//              docs/PHASE3_S4_TASK_REGISTER_MAP_CN.md and ps/robot/s4_task_axi_driver.py).
//   * CONTROL (0x000, W1P, exactly one bit) -> cmd_valid/cmd_index to the FSM;
//     several bits -> not executed, CMD_REJECTED (reason MULTI_BIT).
//   * Configuration, joint limits, planner VMAX/AMAX, path descriptors and the
//     keypoint / segment tables are accepted only while cfg_unlock=1 (FSM in
//     OFF or IDLE); the mode-B path FIFO also in WAIT_PATH (fifo_unlock).  A
//     locked write is ignored and raises CONFIG_LOCKED (event bit 14).  These
//     rejections answer OKAY: a bus error on PYNQ MMIO kills the PS process, the
//     EVENT/CMD_RESULT registers carry the reason.  Only an unmapped address or a
//     partial write (WSTRB != 0xF) is SLVERR.
//   * EVENT (0x00C) sticky, write-1-to-clear; irq = |(EVENT & IRQ_ENABLE).
//   * Tables: keypoints 64 x 6 x int32 Q16.16 (KP_ADDR = {kp, ch}), segments
//     64 x 2 words (SEG_ADDR = {seg, word}), FIFO 32 segments x 8 words; one
//     write port (AXI) and one synchronous read port (FSM) each.
// Target FPGA: Xilinx Zynq-7020 (PYNQ-Z2)
// Clock Domain: clk (100 MHz s_axi_aclk)
// Tray-exit patch (TRAY_EXIT = 1 only): ABI 0x0000_3402, MODE_CFG[4] tray_exit, PATH_TRAY at 0x120
// ({count[13:8], first[5:0]}, locked and write-only like the other descriptors).  TRAY_EXIT = 0:
// ABI 0x0000_3401, MODE_CFG[4] reads 0, 0x120 is unmapped (SLVERR) - the v0.1.1 register map.
// Truth boundary: source candidate; supplementary Icarus run only.
// ============================================================================

`timescale 1ns / 1ps

module s4_task_regs #(
    parameter integer TRAY_EXIT = 0,
    parameter integer SLOT_INVENTORY = 0,
    parameter integer TIMED_WALKTHROUGH = 0,
    parameter integer HANDOVER_V2 = 0,
    parameter integer HAND_ALIGN_REGIONS = 3,
    parameter integer HAND_ALIGN_LOCATOR = 0,
    parameter integer CONTINUOUS_HAND = 0,
    parameter integer AUTO_RESTOCK = 0,
    parameter integer FAST_B = 0,
    parameter integer DYNAMIC_B = 0,
    parameter integer HAND_ALIGN = 0
) (
    input  wire         clk,
    input  wire         rst_n,
    // AXI4-Lite slave
    input  wire [11:0]  s_awaddr,
    input  wire         s_awvalid,
    output reg          s_awready,
    input  wire [31:0]  s_wdata,
    input  wire [3:0]   s_wstrb,
    input  wire         s_wvalid,
    output reg          s_wready,
    output reg  [1:0]   s_bresp,
    output reg          s_bvalid,
    input  wire         s_bready,
    input  wire [11:0]  s_araddr,
    input  wire         s_arvalid,
    output reg          s_arready,
    output reg  [31:0]  s_rdata,
    output reg  [1:0]   s_rresp,
    output reg          s_rvalid,
    input  wire         s_rready,
    output wire         irq,
    // commands to the FSM
    output reg          cmd_valid,
    output reg  [3:0]   cmd_index,
    input  wire         cmd_done,          // FSM result of the pending command
    input  wire [3:0]   cmd_result,
    input  wire [3:0]   cmd_done_index,
    input  wire         cfg_unlock,
    input  wire         fifo_unlock,
    input  wire [15:0]  selected_task_id,
    // configuration outputs
    output reg          cfg_mode_b,
    output reg          cfg_require_line,
    output reg          cfg_hold_policy,
    output reg          cfg_vision_sim,
    output reg  [7:0]   cfg_rearm_mask,
    output reg  [7:0]   cfg_select_mask,
    output reg  [31:0]  cfg_tick_prescale,
    output reg  [15:0]  cfg_t_palm_hold,
    output reg  [15:0]  cfg_t_fist_hold,
    output reg  [15:0]  cfg_t_pre_wait,
    output reg  [15:0]  cfg_t_palm_wait,
    output reg  [15:0]  cfg_blind_periods,
    output reg  [15:0]  cfg_t_arrival,
    output reg  [15:0]  cfg_t_comm,
    output reg  [15:0]  cfg_t_path_wait,
    output reg  [15:0]  cfg_t_heartbeat,
    output reg  [15:0]  cfg_move_margin,
    output reg  [31:0]  cfg_period,
    output reg  [31:0]  cfg_stall,
    output reg  [5:0]   cfg_arrival_mask,
    output reg  [5:0]   cfg_home_kp,
    output reg  [5:0]   cfg_predelivery_kp,
    output reg  [191:0] cfg_joint_min,
    output reg  [191:0] cfg_joint_max,
    output reg  [191:0] cfg_vmax,
    output reg  [191:0] cfg_amax,
    output reg[47:0] cfg_restock_paths,
    output reg[17:0] cfg_restock_release_kps,
    output reg  [143:0] cfg_paths,         // 12 descriptors x {count[5:0], first[5:0]}
    output reg          cfg_tray_exit,     // tray-exit patch
    output reg  [11:0]  cfg_tray_path,     // tray-exit patch
    output reg  [1:0]   req_object,
    output reg  [15:0]  req_task_id,
    output reg  [1:0]   path_object,
    output reg  [15:0]  path_task_id,
    output reg          cfg_b_restock,
    output reg  [5:0]   cfg_b_release_index,
    output reg  [2:0]   sim_class,
    output reg          sim_valid,
    output reg          sim_window_ok,
    output reg          sim_changed,       // one-cycle pulse on VISION_SIM[8]
    // table read ports (synchronous, 1 cycle)
    input  wire [8:0]   kp_raddr,
    input wire [1:0] kp_bank,
    output reg [511:0] cfg_align_pairs,
    output reg [15:0] cfg_align_n,cfg_align_na,
    output reg [HAND_ALIGN_REGIONS-1:0] cfg_banks_ready,
    output reg map_write,map_commit,
    output wire [3:0] map_cell,
    output wire [1:0] map_word,
    output reg [31:0] map_wdata,map_revision,
    output reg [15:0] map_mask,
    input wire map_ready,map_committed,map_error,map_locked,
    input wire [3:0] map_error_code,
    input wire [31:0] map_active_revision,align_debug,align_cells,
    output wire [31:0] kp_rdata,
    input wire kp_mix_enable,
    input wire [6:0] active_step,target_step,
    input wire restock_task,
    input  wire [6:0]   seg_raddr,
    output reg  [31:0]  seg_rdata,
    input  wire [(DYNAMIC_B!=0?9:8)-1:0] fifo_raddr,
    output reg  [31:0]  fifo_rdata,
    output reg  [5:0]   fifo_count,
    input  wire         fifo_clear,        // FSM: PATH_RESET accepted
    // status / events from the FSM
    input  wire [31:0]  status_word,
    input  wire [31:0]  fault_word,
    input  wire [31:0]  progress_word,
    input  wire [31:0]  interaction_status,
    input  wire [31:0]  interaction_timers,
    input  wire [15:0]  event_set,         // pulses
    input  wire [5:0]   cnt_inc,           // pulses: done, cancel, fault, refuse, blind, ps_block
    input  wire [13:0]  dropped_info,      // {window[1:0], addr[11:0]} of the last dropped PS write
    input  wire         poll_done,
    input  wire [15:0]  last_task_id,
    // telemetry of the latest poll
    input  wire [31:0]  t_s1_status,
    input  wire [31:0]  t_s1_error,
    input  wire [31:0]  t_fb_masks,
    input  wire [31:0]  t_fb_age,
    input  wire [31:0]  t_frames,
    input  wire [31:0]  t_pl_status,
    input  wire [31:0]  t_pl_error,
    input  wire [31:0]  t_pl_index,
    input  wire [191:0] t_last
);

    localparam [31:0] ABI = (FAST_B!=0)?32'h0000_340e:(DYNAMIC_B!=0)?32'h0000_340d:(AUTO_RESTOCK!=0)?32'h0000_340b:(CONTINUOUS_HAND!=0)?32'h0000_340a:(HAND_ALIGN!=0 && HAND_ALIGN_LOCATOR!=0)?32'h0000_3409:(HAND_ALIGN!=0 && HAND_ALIGN_REGIONS==4)?32'h0000_3408:(HAND_ALIGN!=0)?32'h0000_3407:(HANDOVER_V2 != 0) ? 32'h0000_3406 : (TIMED_WALKTHROUGH != 0) ? 32'h0000_3405 :
                          ((SLOT_INVENTORY != 0) ? 32'h0000_3404 : 32'h0000_3403);
    localparam [31:0] CAPS = (DYNAMIC_B!=0)?{8'd63,8'd63,8'd64,8'd64}:{8'd32,8'd32,8'd64,8'd64};   // stack, FIFO, segments, keypoints
    localparam [1:0]  OKAY = 2'b00, SLVERR = 2'b10;
    localparam integer EV_CONFIG_LOCKED = 14, EV_CMD_REJECTED = 12;

    // ---------------------------------------------------------------- tables
    (* ram_style = "block" *) reg [31:0] kp_mem   [0:((HAND_ALIGN!=0)?(512*HAND_ALIGN_REGIONS):512)-1];
    (* ram_style = "block" *) reg [31:0] seg_mem  [0:((AUTO_RESTOCK!=0)?256:128)-1];
    (* ram_style = "block" *) reg [31:0] fifo_mem [0:(DYNAMIC_B!=0?511:255)];
    reg         kp_we, seg_we, fifo_we;
    reg  [10:0] kp_waddr;
    reg [1:0] cfg_bank;reg [5:0] map_index,map_write_index;reg map_error_sticky;reg [3:0] map_last_error;
    assign map_cell=map_write_index[5:2];assign map_word=map_write_index[1:0];
    reg  [7:0]  seg_waddr;
    reg [(DYNAMIC_B!=0?9:8)-1:0] fifo_waddr;
    reg  [31:0] tbl_wdata;
    always @(posedge clk) begin
        if (seg_we)  seg_mem[seg_waddr]   <= tbl_wdata;
        if (fifo_we) fifo_mem[fifo_waddr] <= tbl_wdata;
        seg_rdata  <= seg_mem[(AUTO_RESTOCK!=0)?{restock_task,seg_raddr}:{1'b0,seg_raddr}];
        fifo_rdata <= fifo_mem[fifo_raddr];
    end

    // Port A is configuration write / low-anchor read, port B high-anchor read.
    // Configuration is locked during motion; no extra copy of the anchor RAM.
    generate if(CONTINUOUS_HAND!=0)begin:g_continuous
        wire [1:0] low_bank=(active_step<32)?0:1;
        wire [5:0] weight=(active_step<32)?active_step:active_step-32;
        reg [31:0] low_q,high_q;reg [5:0] weight_q;reg mix_q;
        always @(posedge clk)begin
            if(kp_we)kp_mem[kp_waddr]<=tbl_wdata;
            else low_q<=kp_mem[{kp_mix_enable?low_bank:kp_bank,kp_raddr}];
            high_q<=kp_mem[{low_bank+2'd1,kp_raddr}];
            weight_q<=weight;mix_q<=kp_mix_enable;
        end
        wire signed [32:0] delta=$signed({high_q[31],high_q})-$signed({low_q[31],low_q});
        // Four-cycle, one-word-per-clock pipeline: RAM, subtract, multiply, add.
        // Raw precheck words pass through the same latency without truncation.
        reg signed [32:0] delta_q;
        reg signed [39:0] product_q;
        reg [5:0] weight_d2;
        reg [31:0] low_d2,low_d3,result_q;
        reg mix_d2,mix_d3;
        wire signed [39:0] blended=$signed({{8{low_d3[31]}},low_d3})+((product_q+40'sd16)>>>5);
        always @(posedge clk)begin
            delta_q<=delta;weight_d2<=weight_q;low_d2<=low_q;mix_d2<=mix_q;
            product_q<=delta_q*$signed({1'b0,weight_d2});low_d3<=low_d2;mix_d3<=mix_d2;
            result_q<=mix_d3?blended[31:0]:low_d3;
        end
        assign kp_rdata=result_q;
    end else begin:g_discrete
        reg [31:0] q;
        always @(posedge clk)begin
            if(kp_we)kp_mem[kp_waddr]<=tbl_wdata;
            q<=kp_mem[{((HAND_ALIGN!=0)?kp_bank:2'd0),kp_raddr}];
        end
        assign kp_rdata=q;
    end endgenerate

    // ---------------------------------------------------------------- registers
    reg  [15:0] event_sticky, irq_enable;
    reg  [3:0]  res_index, res_code;
    reg  [15:0] cmd_counter;
    reg  [8:0]  kp_addr;
    reg  [7:0]  seg_addr;
    reg[31:0]cnt_restock;
    reg  [2:0]  fifo_word;
    reg         fifo_overflow;
    reg  [31:0] cnt_done, cnt_cancel, cnt_fault, cnt_refuse, cnt_blind, cnt_ps_block, cnt_polls;
    reg  [13:0] last_dropped;
    reg  [15:0] ev_local;              // events raised by this block (blocking temporaries)
    reg  [15:0] ev_clear;
    assign irq = |(event_sticky & irq_enable);

    // AXI write capture
    reg         aw_full, w_full;
    reg  [11:0] aw_addr;
    reg  [31:0] w_data;
    reg  [3:0]  w_strb;

    function automatic is_cfg_addr;    // locked configuration / table registers
        input [11:0] a;
        begin
            is_cfg_addr = ((DYNAMIC_B!=0) && a==12'h38c) || ((a >= 12'h024) && (a <= 12'h054)) || ((a >= 12'h080) && (a <= 12'h11C))
                          || ((AUTO_RESTOCK!=0) && a>=12'h374 && a<=12'h380) || ((TRAY_EXIT != 0) && (a == 12'h120)) || ((HANDOVER_V2!=0) && (a==12'h124 || a==12'h128)) || ((HAND_ALIGN!=0) && (a==12'h12c || a==12'h130 || (a>=12'h300 && a<=12'h310) || (HAND_ALIGN_REGIONS==4 && a>=12'h330 && a<=12'h36c)));
        end
    endfunction

    // A B task is stationary at HOME in WAIT_PATH. Only its path tables and
    // descriptors may change there; mode, joint limits and timing policy stay locked.
    function automatic is_path_cfg_addr;
        input [11:0] a;
        begin
            is_path_cfg_addr = (a==12'h054) || (a>=12'h0e0 && a<=12'h11c) ||
                               (a==12'h12c) || (a==12'h130) || (HAND_ALIGN!=0 && a>=12'h300 && a<=12'h310) ||
                               (a>=12'h330 && a<=12'h36c) || (a==12'h38c);
        end
    endfunction

    function automatic addr_mapped_w;
        input [11:0] a;
        begin
            addr_mapped_w = ((DYNAMIC_B!=0) && a==12'h38c) || (a == 12'h000) || (a == 12'h00C) || (a == 12'h018) || (a >= 12'h024 && a <= 12'h068)
                            || (a >= 12'h080 && a <= 12'h11C) || ((AUTO_RESTOCK!=0) && a>=12'h374 && a<=12'h380) || ((TRAY_EXIT != 0) && (a == 12'h120))
                            || ((HANDOVER_V2!=0) && (a==12'h124 || a==12'h128)) || ((HAND_ALIGN!=0) && (a==12'h12c || a==12'h130 || (a>=12'h300 && a<=12'h310) || (HAND_ALIGN_REGIONS==4 && a>=12'h330 && a<=12'h36c)));
        end
    endfunction

    integer i;
    always @(posedge clk) begin
        if (!rst_n) begin
            s_awready <= 1'b1; s_wready <= 1'b1; s_bvalid <= 1'b0; s_bresp <= OKAY;
            aw_full <= 1'b0; w_full <= 1'b0; aw_addr <= 12'd0; w_data <= 32'd0; w_strb <= 4'd0;
            cmd_valid <= 1'b0; cmd_index <= 4'd0;
            cfg_mode_b <= 1'b0; cfg_require_line <= 1'b0; cfg_hold_policy <= 1'b0; cfg_vision_sim <= 1'b0;
            cfg_rearm_mask <= 8'h81; cfg_select_mask <= 8'h0E;
            cfg_tick_prescale <= 32'd100_000;
            cfg_t_palm_hold <= 16'd300; cfg_t_palm_wait <= 16'd20000; cfg_blind_periods <= 16'd400;
            cfg_t_fist_hold<=16'd1000;cfg_t_pre_wait<=16'd2000;
            cfg_align_pairs<={16{32'h00190064}};cfg_align_n<=100;cfg_align_na<=25;cfg_bank<=0;cfg_banks_ready<=0;map_index<=0;map_write_index<=0;map_write<=0;map_commit<=0;map_wdata<=0;map_revision<=0;map_mask<=0;map_error_sticky<=0;map_last_error<=0;
            cfg_t_arrival <= 16'd500; cfg_t_comm <= 16'd200; cfg_t_path_wait <= 16'd10000;
            cfg_t_heartbeat <= 16'd0; cfg_move_margin <= 16'd200;
            cfg_period <= 32'd1_000_000; cfg_stall <= 32'd50_000_000;
            cfg_arrival_mask <= 6'h3F; cfg_home_kp <= 6'd0; cfg_predelivery_kp <= 6'd1;
            cfg_joint_min <= {6{32'h8000_0000}}; cfg_joint_max <= {6{32'h7FFF_FFFF}};
            cfg_vmax <= 192'd0; cfg_amax <= 192'd0; cfg_paths <= 144'd0;cfg_restock_paths<=0;cfg_restock_release_kps<=0;cnt_restock<=0;
            cfg_tray_exit <= 1'b0; cfg_tray_path <= 12'd0;
            req_object <= 2'd0; req_task_id <= 16'd0; path_object <= 2'd0; path_task_id <= 16'd0;
            cfg_b_restock<=0;cfg_b_release_index<=0;
            sim_class <= 3'd7; sim_valid <= 1'b0; sim_window_ok <= 1'b0; sim_changed <= 1'b0;
            event_sticky <= 16'd0; irq_enable <= 16'd0; res_index <= 4'd0; res_code <= 4'd0; cmd_counter <= 16'd0;
            kp_addr <= 9'd0; seg_addr <= 7'd0; fifo_word <= 3'd0; fifo_count <= 6'd0; fifo_overflow <= 1'b0;
            kp_we <= 1'b0; seg_we <= 1'b0; fifo_we <= 1'b0; kp_waddr <= 9'd0; seg_waddr <= 7'd0; fifo_waddr <= 8'd0;
            tbl_wdata <= 32'd0;
            cnt_done <= 32'd0; cnt_cancel <= 32'd0; cnt_fault <= 32'd0; cnt_refuse <= 32'd0; cnt_blind <= 32'd0;
            cnt_ps_block <= 32'd0; cnt_polls <= 32'd0; last_dropped <= 14'd0;
        end else begin
            cmd_valid <= 1'b0;
            sim_changed <= 1'b0;
            map_write<=0;map_commit<=0;if(map_error)begin map_error_sticky<=1;map_last_error<=map_error_code;end
            kp_we <= 1'b0; seg_we <= 1'b0; fifo_we <= 1'b0;
            ev_local = 16'd0;
            ev_clear = 16'd0;
            // ---- FSM feedback
            if (cmd_done) begin res_index <= cmd_done_index; res_code <= cmd_result; end
            if(AUTO_RESTOCK!=0 && event_set[14])cnt_restock<=cnt_restock+1'b1;
            if (cnt_inc[0]) cnt_done <= cnt_done + 32'd1;
            if (cnt_inc[1]) cnt_cancel <= cnt_cancel + 32'd1;
            if (cnt_inc[2]) cnt_fault <= cnt_fault + 32'd1;
            if (cnt_inc[3]) cnt_refuse <= cnt_refuse + 32'd1;
            if (cnt_inc[4]) cnt_blind <= cnt_blind + 32'd1;
            if (cnt_inc[5]) begin cnt_ps_block <= cnt_ps_block + 32'd1; last_dropped <= dropped_info; end
            if (poll_done) cnt_polls <= cnt_polls + 32'd1;
            if (fifo_clear) begin fifo_count <= 6'd0; fifo_word <= 3'd0; fifo_overflow <= 1'b0;
                if(DYNAMIC_B!=0)begin cfg_b_restock<=0;cfg_b_release_index<=0;end
            end
            // ---- AXI write
            if (s_awvalid && s_awready) begin aw_full <= 1'b1; aw_addr <= s_awaddr; s_awready <= 1'b0; end
            if (s_wvalid && s_wready)   begin w_full <= 1'b1; w_data <= s_wdata; w_strb <= s_wstrb; s_wready <= 1'b0; end
            if (s_bvalid && s_bready) begin s_bvalid <= 1'b0; s_awready <= 1'b1; s_wready <= 1'b1; end
            if (aw_full && w_full && !s_bvalid) begin
                aw_full <= 1'b0; w_full <= 1'b0;
                s_bvalid <= 1'b1;
                if (aw_addr[1:0] != 2'b00 || w_strb != 4'hF || !addr_mapped_w(aw_addr)) begin
                    s_bresp <= SLVERR;
                end else begin
                    s_bresp <= OKAY;
                    if (is_cfg_addr(aw_addr) && !cfg_unlock &&
                        !(DYNAMIC_B!=0 && cfg_mode_b && fifo_unlock && is_path_cfg_addr(aw_addr))) begin
                        ev_local[EV_CONFIG_LOCKED] = 1'b1;
                    end else if ((aw_addr == 12'h068 || (DYNAMIC_B!=0 && aw_addr==12'h05c)) && !fifo_unlock) begin
                        ev_local[EV_CONFIG_LOCKED] = 1'b1;
                    end else begin
                        case (aw_addr)
                            12'h000: begin
                                cmd_counter <= cmd_counter + 16'd1;
                                if (((DYNAMIC_B!=0) ? (w_data[31:13]!=19'd0) : ((SLOT_INVENTORY != 0) ? (w_data[31:12] != 20'd0) : (w_data[31:11] != 21'd0))) ||
                                    w_data == 32'd0 || (w_data & (w_data - 32'd1)) != 32'd0) begin
                                    ev_local[EV_CMD_REJECTED] = 1'b1;
                                    res_code <= 4'd1;                         // MULTI_BIT / reserved
                                    res_index <= 4'hF;
                                end else begin
                                    cmd_valid <= 1'b1;
                                    for (i = 0; i < ((DYNAMIC_B!=0)?13:12); i = i + 1)
                                        if (w_data[i]) cmd_index <= i[3:0];
                                end
                            end
                            12'h00C: ev_clear = w_data[15:0];
                            12'h018: irq_enable <= w_data[15:0];
                            12'h024: begin
                                cfg_mode_b <= w_data[0]; cfg_require_line <= w_data[1]; cfg_hold_policy <= w_data[2];
                                cfg_vision_sim <= w_data[3]; cfg_rearm_mask <= w_data[15:8]; cfg_select_mask <= w_data[23:16];
                                cfg_tray_exit <= (TRAY_EXIT != 0) && w_data[4];
                            end
                            12'h028: cfg_tick_prescale <= (w_data < 32'd16) ? 32'd16 : w_data;
                            12'h02C: cfg_t_palm_hold   <= w_data[15:0];
                            12'h030: cfg_t_palm_wait   <= w_data[15:0];
                            12'h034: cfg_blind_periods <= w_data[15:0];
                            12'h038: cfg_t_arrival     <= w_data[15:0];
                            12'h03C: cfg_t_comm        <= w_data[15:0];
                            12'h040: cfg_t_path_wait   <= w_data[15:0];
                            12'h044: cfg_t_heartbeat   <= w_data[15:0];
                            12'h048: cfg_move_margin   <= w_data[15:0];
                            12'h04C: cfg_period        <= w_data;
                            12'h050: cfg_stall         <= w_data;
                            12'h054: begin
                                cfg_arrival_mask <= w_data[5:0]; cfg_home_kp <= w_data[13:8];
                                cfg_predelivery_kp <= w_data[21:16];
                            end
                            12'h058: begin req_object <= w_data[1:0]; req_task_id <= w_data[31:16]; end
                            12'h05C: begin path_object <= w_data[1:0]; path_task_id <= w_data[31:16]; end
                            12'h38c: begin cfg_b_restock<=w_data[0];cfg_b_release_index<=w_data[13:8];end
                            12'h060: begin
                                sim_class <= w_data[2:0]; sim_valid <= w_data[3]; sim_window_ok <= w_data[4];
                                sim_changed <= w_data[8];
                            end
                            12'h068: begin
                                if (fifo_count >= (DYNAMIC_B!=0?6'd63:6'd32)) begin
                                    fifo_overflow <= 1'b1;
                                    ev_local[EV_CONFIG_LOCKED] = 1'b1;
                                end else begin
                                    fifo_we <= 1'b1; fifo_waddr <= (DYNAMIC_B!=0?{fifo_count,fifo_word}:{1'b0,fifo_count[4:0],fifo_word}); tbl_wdata <= w_data;
                                    fifo_word <= fifo_word + 3'd1;
                                    if (fifo_word == 3'd7) fifo_count <= fifo_count + 6'd1;
                                end
                            end
                            12'h374: if(AUTO_RESTOCK!=0)cfg_restock_paths[11:0]<={w_data[13:8],w_data[5:0]};
                            12'h378: if(AUTO_RESTOCK!=0)begin cfg_restock_paths[23:12]<={w_data[13:8],w_data[5:0]};cfg_restock_release_kps[5:0]<=w_data[21:16];end
                            12'h37c: if(AUTO_RESTOCK!=0)begin cfg_restock_paths[35:24]<={w_data[13:8],w_data[5:0]};cfg_restock_release_kps[11:6]<=w_data[21:16];end
                            12'h380: if(AUTO_RESTOCK!=0)begin cfg_restock_paths[47:36]<={w_data[13:8],w_data[5:0]};cfg_restock_release_kps[17:12]<=w_data[21:16];end
                            12'h110: kp_addr <= w_data[8:0];
                            12'h114: begin
                                kp_we <= 1'b1; kp_waddr <= {((HAND_ALIGN!=0)?cfg_bank:2'd0),kp_addr};
                                if(HAND_ALIGN!=0)begin if(kp_addr==0)cfg_banks_ready[cfg_bank]<=0;if(kp_addr==511)cfg_banks_ready[cfg_bank]<=1;end tbl_wdata <= w_data;
                                kp_addr <= (HAND_ALIGN!=0) ? kp_addr+9'd1 : ((kp_addr[2:0] == 3'd5) ? {kp_addr[8:3] + 6'd1, 3'd0} : kp_addr + 9'd1);
                            end
                            12'h118: seg_addr <= (AUTO_RESTOCK!=0)?w_data[7:0]:{1'b0,w_data[6:0]};
                            12'h120: if (TRAY_EXIT != 0) cfg_tray_path <= {w_data[13:8], w_data[5:0]};
                            12'h12c: if(HAND_ALIGN!=0)begin if(w_data<HAND_ALIGN_REGIONS)cfg_bank<=w_data[1:0];else s_bresp<=SLVERR;end
                            12'h130: if(HAND_ALIGN!=0)begin cfg_align_n<=w_data[15:0];cfg_align_na<=w_data[31:16];end
                            12'h300: if(HAND_ALIGN!=0)map_index<=w_data[5:0];
                            12'h304: if(HAND_ALIGN!=0)begin if(map_ready)begin map_write<=1;map_write_index<=map_index;map_wdata<=w_data;map_index<=map_index+1'b1;end else s_bresp<=SLVERR;end
                            12'h308: if(HAND_ALIGN!=0)map_mask<=w_data[15:0];
                            12'h30c: if(HAND_ALIGN!=0)map_revision<=w_data;
                            12'h310: if(HAND_ALIGN!=0)begin if(map_ready && w_data==1)begin map_commit<=1;map_error_sticky<=0;map_last_error<=0;end else s_bresp<=SLVERR;end
                            12'h124: if(HANDOVER_V2!=0)cfg_t_fist_hold<=w_data[15:0];
                            12'h128: if(HANDOVER_V2!=0)cfg_t_pre_wait<=w_data[15:0];
                            12'h11C: begin
                                seg_we <= 1'b1; seg_waddr <= seg_addr; tbl_wdata <= w_data; seg_addr <= (AUTO_RESTOCK!=0)?(seg_addr+8'd1):{1'b0,(seg_addr[6:0]+7'd1)};
                            end
                            default: begin
                                if(HAND_ALIGN!=0 && HAND_ALIGN_REGIONS==4 && aw_addr>=12'h330 && aw_addr<=12'h36c)
                                    cfg_align_pairs[((aw_addr-12'h330)>>2)*32+:32]<=w_data;
                                else if (aw_addr >= 12'h080 && aw_addr <= 12'h094)
                                    cfg_joint_min[{aw_addr[4:2] - 3'd0, 5'd0} +: 32] <= w_data;
                                else if (aw_addr >= 12'h098 && aw_addr <= 12'h0AC)
                                    cfg_joint_max[{(aw_addr[7:2] - 6'h26), 5'd0} +: 32] <= w_data;
                                else if (aw_addr >= 12'h0B0 && aw_addr <= 12'h0C4)
                                    cfg_vmax[{(aw_addr[7:2] - 6'h2C), 5'd0} +: 32] <= w_data;
                                else if (aw_addr >= 12'h0C8 && aw_addr <= 12'h0DC)
                                    cfg_amax[{(aw_addr[7:2] - 6'h32), 5'd0} +: 32] <= w_data;
                                else if (aw_addr >= 12'h0E0 && aw_addr <= 12'h10C)
                                    cfg_paths[{(aw_addr[7:2] - 6'h38), 3'b000} + {(aw_addr[7:2] - 6'h38), 2'b00} +: 12]
                                        <= {w_data[13:8], w_data[5:0]};
                                // 0x064 FIFO_STATUS is read-only: write ignored
                            end
                        endcase
                    end
                end
            end
            event_sticky <= (event_sticky & ~ev_clear) | event_set | ev_local;   // new events win
        end
    end

    // ---------------------------------------------------------------- AXI read
    reg [31:0] rd;
    reg        rd_ok;
    always @(*) begin
        rd = 32'd0; rd_ok = 1'b1;
        case (s_araddr)
            12'h000: rd = 32'd0;
            12'h004: rd = status_word;
            12'h008: rd = fault_word;
            12'h00C: rd = {16'd0, event_sticky};
            12'h010: rd = ABI;
            12'h014: rd = CAPS;
            12'h018: rd = {16'd0, irq_enable};
            12'h01C: rd = {cmd_counter, 4'd0, res_code, 4'd0, res_index};
            12'h020: rd = progress_word;
            12'h024: rd = {8'd0, cfg_select_mask, cfg_rearm_mask, 3'd0, cfg_tray_exit, cfg_vision_sim, cfg_hold_policy,
                           cfg_require_line, cfg_mode_b};
            12'h028: rd = cfg_tick_prescale;
            12'h02C: rd = {16'd0, cfg_t_palm_hold};
            12'h030: rd = {16'd0, cfg_t_palm_wait};
            12'h034: rd = {16'd0, cfg_blind_periods};
            12'h038: rd = {16'd0, cfg_t_arrival};
            12'h03C: rd = {16'd0, cfg_t_comm};
            12'h040: rd = {16'd0, cfg_t_path_wait};
            12'h044: rd = {16'd0, cfg_t_heartbeat};
            12'h048: rd = {16'd0, cfg_move_margin};
            12'h04C: rd = cfg_period;
            12'h050: rd = cfg_stall;
            12'h054: rd = {10'd0, cfg_predelivery_kp, 2'd0, cfg_home_kp, 2'd0, cfg_arrival_mask};
            12'h058: rd = {req_task_id, 14'd0, req_object};
            12'h05C: rd = {path_task_id, 14'd0, path_object};
            12'h060: rd = {27'd0, sim_window_ok, sim_valid, sim_class};
            12'h064: rd = {22'd0, fifo_overflow, fifo_word, fifo_count};
            12'h110: rd = {23'd0, kp_addr};
            12'h118: rd = {24'd0, seg_addr};
            12'h120: if (TRAY_EXIT == 0) rd_ok = 1'b0;          // PATH_TRAY: write-only (reads 0) / unmapped
            12'h12c: if(HAND_ALIGN!=0)rd={{(30-HAND_ALIGN_REGIONS){1'b0}},cfg_banks_ready,cfg_bank};else rd_ok=0;
            12'h130: if(HAND_ALIGN!=0)rd={cfg_align_na,cfg_align_n};else rd_ok=0;
            12'h300: if(HAND_ALIGN!=0)rd={26'd0,map_index};else rd_ok=0;
            12'h308: if(HAND_ALIGN!=0)rd={16'd0,map_mask};else rd_ok=0;
            12'h30c: if(HAND_ALIGN!=0)rd=map_revision;else rd_ok=0;
            12'h314: if(HAND_ALIGN!=0)rd={16'd0,map_last_error,8'd0,map_error_sticky,map_locked,map_committed,map_ready};else rd_ok=0;
            12'h318: if(HAND_ALIGN!=0)rd=map_active_revision;else rd_ok=0;
            12'h31c: if(HAND_ALIGN!=0)rd=align_debug;else rd_ok=0;
            12'h324: if(CONTINUOUS_HAND!=0)rd={16'd0,1'b0,target_step,1'b0,active_step};else rd_ok=0;
            12'h38c: if(DYNAMIC_B!=0)rd={18'd0,cfg_b_release_index,7'd0,cfg_b_restock};else rd_ok=0;
            12'h390: if(DYNAMIC_B!=0)rd={selected_task_id,14'd0,status_word[21:20]};else rd_ok=0;
            12'h320: if(HAND_ALIGN!=0)rd=align_cells;else rd_ok=0;
            12'h124: if(HANDOVER_V2!=0)rd={16'd0,cfg_t_fist_hold};else rd_ok=0;
            12'h128: if(HANDOVER_V2!=0)rd={16'd0,cfg_t_pre_wait};else rd_ok=0;
            12'h260: if(HANDOVER_V2!=0)rd=interaction_status;else rd_ok=0;
            12'h264: if(HANDOVER_V2!=0)rd=interaction_timers;else rd_ok=0;
            12'h200: rd = t_s1_status;
            12'h204: rd = t_s1_error;
            12'h208: rd = t_fb_masks;
            12'h20C: rd = t_fb_age;
            12'h210: rd = t_frames;
            12'h214: rd = t_pl_status;
            12'h218: rd = t_pl_error;
            12'h21C: rd = t_pl_index;
            12'h220: rd = t_last[31:0];
            12'h224: rd = t_last[63:32];
            12'h228: rd = t_last[95:64];
            12'h22C: rd = t_last[127:96];
            12'h230: rd = t_last[159:128];
            12'h234: rd = t_last[191:160];
            12'h374: if(AUTO_RESTOCK!=0)rd={18'd0,cfg_restock_paths[11:6],2'd0,cfg_restock_paths[5:0]};else rd_ok=0;
            12'h378: if(AUTO_RESTOCK!=0)rd={10'd0,cfg_restock_release_kps[5:0],2'd0,cfg_restock_paths[23:18],2'd0,cfg_restock_paths[17:12]};else rd_ok=0;
            12'h37c: if(AUTO_RESTOCK!=0)rd={10'd0,cfg_restock_release_kps[11:6],2'd0,cfg_restock_paths[35:30],2'd0,cfg_restock_paths[29:24]};else rd_ok=0;
            12'h380: if(AUTO_RESTOCK!=0)rd={10'd0,cfg_restock_release_kps[17:12],2'd0,cfg_restock_paths[47:42],2'd0,cfg_restock_paths[41:36]};else rd_ok=0;
            12'h388: if(AUTO_RESTOCK!=0)rd=cnt_restock;else rd_ok=0;
            12'h240: rd = cnt_done;
            12'h244: rd = cnt_cancel;
            12'h248: rd = cnt_fault;
            12'h24C: rd = cnt_refuse;
            12'h250: rd = cnt_blind;
            12'h254: rd = cnt_ps_block;
            12'h258: rd = {18'd0, last_dropped};
            12'h25C: rd = cnt_polls;
            12'h260: rd = {16'd0, last_task_id};
            default: begin
                // write-only configuration registers read as 0
                if(HAND_ALIGN!=0 && HAND_ALIGN_REGIONS==4 && s_araddr>=12'h330 && s_araddr<=12'h36c)rd=cfg_align_pairs[((s_araddr-12'h330)>>2)*32+:32];
                else if (!((s_araddr >= 12'h068 && s_araddr <= 12'h11C) && s_araddr[1:0] == 2'b00)) rd_ok = 1'b0;
            end
        endcase
        if (s_araddr[1:0] != 2'b00) rd_ok = 1'b0;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            s_arready <= 1'b1; s_rvalid <= 1'b0; s_rdata <= 32'd0; s_rresp <= OKAY;
        end else begin
            if (s_arvalid && s_arready) begin
                s_arready <= 1'b0;
                s_rvalid <= 1'b1;
                s_rdata <= rd_ok ? rd : 32'd0;
                s_rresp <= rd_ok ? OKAY : SLVERR;
            end
            if (s_rvalid && s_rready) begin
                s_rvalid <= 1'b0;
                s_arready <= 1'b1;
            end
        end
    end

endmodule
